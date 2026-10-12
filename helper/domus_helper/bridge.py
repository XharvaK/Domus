"""Helper bridge: spool telemetry, heartbeat, and flush the observation outbox."""
import argparse
import json
import secrets
import sqlite3
import threading
import time
import uuid
from types import SimpleNamespace

from . import catalog
from . import catalog_ask
from . import commands
from . import fingerprints as fingerprint_reader
from . import pace
from . import reach
from .vendor import schema
from .acts import OPTIONS_LIMIT, OPTIONS_OBJECTS_LIMIT, ActCourier, MenuParts, RefBook, act_names, act_words_by_guid, dialog_options, merge_near, options as act_options, people_heard, people_names, queue_options
from .attachment import AttachmentMonitor
from . import inputs as game_inputs
from . import overlay as overlay_pages
from .director import Director
from .talk import Talk
from . import notebook
from .diary import DiaryWatch
from . import memory
from .proof import Trace
from .contract import ContractError, options_why, refusal_text
from .cursor import TelemetryCursor
from .paths import Paths
from .spool import OutboxConflict, Spool
from . import coalesce
from . import tokens
from .thalamus.log import DecisionLog
from .thalamus.observation import SeenMemory, build
from .thalamus.percepts import Extractor
from .thalamus.types import Percept
from .transport import AshleyClient, SyncRefused, load_credentials
from .windows import WindowLog, withheld_of

_AUTO = object()
HEARTBEAT_EVERY_MS = 60_000
_CAMERA_PROBE = (2, 21, 0)
_TALK_PROBE = (2, 26, 0)
# W12 (F5): the commands this helper sends are gated on the probe that understands them.
_PACE_PROBE = (2, 31, 0)
_NEAR_PROBE = (2, 39, 0)
# W13 (H): the verb acts, the Sim picker and the catalogue dump need the probe that writes and reads them.
_VERB_PROBE = (2, 40, 0)
# HELPER2-4: after a verb act ends, the probe is asked for fresh lists no more often than this.
LISTS_NOW_EVERY_MS = 10_000
# W13 (H): the catalogue dump is asked for again no sooner than this, while the catalogue still lacks the game's flags.
CATALOG_DUMP_EVERY_MS = 10 * 60_000
# W13 (H): a list Natalis did not take is sent again no sooner than this.
LIST_RETRY_MS = 60_000
# W13 (H, A4-15): a list Natalis refused this many times in a row (the same digest) waits this long before it is sent again.
LIST_REFUSALS = 3
LIST_REFUSED_WAIT_MS = 10 * 60_000
# W12 (F3): a body row older than this, from before this helper started, is not a view of now.
STALE_BODY_MS = 120_000
# W12 (F4): a refused view's changes go back in the queue this many times in a row, then they are let go (logged).
REQUEUE_LIMIT = 3
# W3h: a pace command that could not be written is tried again after this long.
PACE_RETRY_MS = 30_000
# HE17: the newest row is kept in the spool when it changed, and at most this often.
ROW_WRITE_EVERY_MS = 30_000


def _body_sample(record):
    # A body sample is a presence snapshot. Live 2026-10-08: a session checkpoint carries an empty
    # body (motives [], no zone, no interactions); taken as her latest sample, it told her she was
    # doing nothing while she played the piano, and she queued the piano again.
    return (isinstance(record, dict)
            and record.get("event_kind") == "presence_snapshot"
            and "motives" in record)


def _probe_ok(probe, least=_CAMERA_PROBE):
    if not isinstance(probe, str):
        return False
    try:
        return tuple(int(part) for part in probe.split(".")) >= least
    except (TypeError, ValueError):
        return False


def _ticks(record):
    game = record.get("game") if isinstance(record, dict) else None
    return game.get("ticks") if isinstance(game, dict) else None


class Bridge:
    def __init__(self, paths=None, *, client=_AUTO, process=_AUTO, detected_build=_AUTO, mono=None):
        self.paths = paths or Paths.from_env()
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        self.spool = Spool(self.paths.data_dir / "spool.db")
        self.cursor = TelemetryCursor(self.spool, self.paths)
        self.helper_session = uuid.uuid4().hex
        self._mono = mono or (lambda: int(time.monotonic() * 1000))
        self._process = fingerprint_reader._process if process is _AUTO else (lambda: process)
        if detected_build is _AUTO:
            try:
                self.detected_build = fingerprint_reader.detected_build(paths=self.paths)["detected_build"]
            except (OSError, FileNotFoundError, ValueError, UnicodeError, KeyError):
                self.detected_build = None
        else:
            self.detected_build = detected_build
        self.monitor = AttachmentMonitor(self.detected_build)
        # S0: moodlet names in the game's own words (local string index; None if absent).
        from .strings import Resolver
        # 2.37.0 (W10 H3): every game text for her view is in words (her names, no tokens); see tokens.Words.
        self._resolve_text = tokens.Words(Resolver(self.paths))
        creds = load_credentials(self.paths)
        if client is _AUTO:
            self.client = None if creds.disabled else AshleyClient(creds.url, creds.token)
            self._disabled = creds.disabled
        else:
            self.client = client
            self._disabled = None
        self._state = None
        self._telemetry_only = False
        self._last_heartbeat = None
        self._last_heartbeat_ms = None
        self._tried_attached = None
        self._tried_inputs = None
        self._log = DecisionLog(self.paths.data_dir)
        self._loaded = False
        self._coalesced = coalesce.Pending()  # D2: the changes waiting for their view
        self._extractor = Extractor(resolve=self._resolve_text)  # 2.36.0 (D6): notices and her self in words
        self._last_rowid = 0
        self._obs_seq = 0
        self._last_row = None
        self._last_body_row = None
        self._seen = None  # SS4-v2: who she sees, by handle (set when the state loads; kept in memory only)
        self._fires = 0  # views sent (the status keeps the name)
        self._enqueued = 0
        self._last_fire_reason = None
        self._last_fire_wall_ms = None
        # 8f: the probe's newest menu of what she can do ({session, payload}), and the courier
        # that carries her requested acts to the probe (only when Ashley is reachable).
        self._menu = None
        # W14 (D3): the last whole menu of the session (kept under its telemetry session), which a near part is merged with.
        self._whole_menu = None
        # W14 (S2): no whole menu has arrived in this helper session yet (the view says the choices are still coming).
        self._whole_seen = False
        self._refs = RefBook()  # N8 (F3): the refs of this helper session (reset at each attachment)
        self._menu_parts = MenuParts()  # N8 (F4): a menu arrives in parts; the whole one is the menu
        self._catalog = None
        # W13 (H): the lists as Natalis holds them (kind -> {digest, items}) and the households' first names, both kept in
        # the spool; the parts of a list still arriving; the names and conditions derived from the lists; the catalogue dump.
        self._lists = {}
        self._households = {}
        self._rooms_table = {}  # W13 (S5): room id -> label, from the newest things list
        self._lists_session = None  # W13 (A4-16): the telemetry session the lists belong to
        self._list_parts = reach.ListParts()
        self._list_retry_ms = {}
        self._list_refusals = {}  # W13 (A4-15): kind -> [digest, refusals in a row]
        self._lists_lock = threading.Lock()  # W13 (A4-9): the lists are read and written under it (a post thread reads them)
        self._lists_busy = False  # W13 (A4-9): one post pass at a time
        self._index = reach.index({})
        self._catalog_checked_ms = None
        self._catalog_no_build_logged = False  # HELPER2-14
        self._lists_now_owed = False  # HELPER2-4: a verb act ended and the lists are not asked for yet
        self._lists_now_sent_ms = None
        self._acts = None if self.client is None else ActCourier(
            self.spool, lambda command, args: commands.publish(command, args, "helper", paths=self.paths),
            resolve=self._resolve_text, memory=self._answer_memory,
            reply=lambda command_id: commands.read_reply(command_id, paths=self.paths), log=self._log.write,
            say=self._say_words, her_name=self._her_first, answered=self._answered,
            result_words=self._result_words, rooms=self._room_labels, ended=self._verb_act_ended)
        # W12 (B2): the refs are kept for one game session; the view's attachment says which epoch of refs it uses.
        self._refs_epoch = 0
        self._refs_session = None
        self._body_fresh = False  # W12 (F3): a body row of this run has come (a restored one is not news)
        self._spot_stages_last = None
        self._requeued = 0  # W12 (F4): views refused in a row whose changes went back in the queue
        # E3: the overlay pages' state (served by main() on this PC only).
        self.overlay = overlay_pages.Overlay(self.spool, self.paths.data_dir, int(time.time() * 1000), self._resolve_text,
                                             trace=Trace(self.spool, self.paths.data_dir), helper_build=_helper_build())
        self.director = None if self.client is None else Director(
            self.spool, lambda command, args: commands.publish(command, args, "helper", paths=self.paths))
        # 2.26.0: social talk on the User's screen; local only, so it works without Ashley too.
        self.talk = Talk(self.spool, lambda command, args: commands.publish(command, args, "helper", paths=self.paths))
        if self._acts is not None:
            self.overlay.answered = self._acts.answered_dialogs
        self.notebook = notebook.Notebook(self.paths.data_dir / notebook.DB_NAME)
        # W2h: the window facts (held windows shown, screens only the User's hands can use).
        self._windows = WindowLog(self.spool)
        self.diary = DiaryWatch(self.spool, self.paths) if self.client is not None else None
        self._outcomes_mtime = None
        self._outcomes_checked_ms = None
        self._probe_warned = None
        # W3h: her pace. The settings file, what the probe last applied, and the decision costs.
        self._pace_settings = pace.PaceSettings(self.paths.data_dir)
        self._pace_log = pace.PaceLog(self.spool)
        self._pace_block = None
        self._pace_streak = 0
        self._pace_mismatch = False
        self._pace_attached = False
        self._pace_sent = None
        self._pace_sent_ms = None
        self._pace_retry_ms = None
        self._row_written = {}

    def tick(self, now):
        self._maybe_rebuild_procedures(now)
        self.cursor.read_new()
        latest = self.spool.latest_record()
        probe = latest.get("probe_version") if isinstance(latest, dict) else None
        if isinstance(probe, str) and probe != schema.PROBE_VERSION and probe != self._probe_warned:
            print("probe %s is installed; this helper expects %s" % (probe, schema.PROBE_VERSION))
            self._probe_warned = probe
        observed = self.monitor.observe(now, self._mono(), self._process(), latest)
        self._state = observed["state"]
        self._follow_refs(latest)
        self._telemetry_only = observed["telemetry_only"]
        self._advance_thalamus(now)
        # E1b: a flipped game-only switch goes out at once, not with the next minute's heartbeat.
        # Live 2026-10-08: so does attaching; the first heartbeat goes before the save loads, and
        # her first game moments waited a minute for the next one.
        inputs = game_inputs.current(self.spool)
        attached = self._state == "attached"
        if self.client is not None and (
            self._last_heartbeat_ms is None or now - self._last_heartbeat_ms >= HEARTBEAT_EVERY_MS
            or inputs != self._tried_inputs or attached != self._tried_attached
        ):
            body = {
                "v": 1,
                "helper_session": self.helper_session,
                "sent_at_ms": now,
                "attached": self._state == "attached",
            }
            if inputs == game_inputs.GAME_ONLY:
                body["inputs"] = inputs
            if isinstance(probe, str) and len(probe) <= 16:
                body["probe_version"] = probe
            result = self.client.post_heartbeat(body)
            self._last_heartbeat = {"kind": result.kind, "status": result.status}
            if result.kind not in ("admitted", "duplicate"):
                self._log.write({"wall_ms": now, "trigger": "heartbeat", "error": str(result.kind)})  # W12 (F6)
            self._last_heartbeat_ms = now
            self._tried_inputs = inputs
            self._tried_attached = attached
        # A9-2: the act round trip goes before the observation flush, so a slow Ashley backlog cannot push an act past its expiry.
        if self.client is not None and self._acts is not None and hasattr(self.client, "sync_acts"):
            written = self._acts.tick(self.client, self.helper_session, now, self._state == "attached", probe=probe)
            self._pace_log.received(written)
            self.overlay.answered = self._acts.answered_dialogs
            if self._acts.take_look():
                self._send_look(now)
        self._send_due(now)
        if self.client is not None:
            self.spool.flush(self.client, now)
            for kind in self.spool.last_failures:
                self._log.write({"wall_ms": now, "trigger": "observation_post", "error": str(kind)})  # W12 (F6)
            if self.spool.last_expired:
                self._log.write({"wall_ms": now, "trigger": "observation_post", "error": "expired",
                                 "count": self.spool.last_expired})  # W12 (F3): the newest state goes in the next view
        self._pace_tick(now, probe)
        self._catalog_dump(now, probe)
        self._lists_now_due(now, probe)
        self.overlay.poll(self.client, self.helper_session, now)
        self.overlay.act_name = self._act_names()
        self.overlay.publish(now, self._state == "attached")
        if self.director is not None:
            live = self.overlay.published.get("mode") == "live" and _probe_ok(probe)
            self.director.tick(now, live)
        self.talk.tick(now, self._state == "attached" and _probe_ok(probe, _TALK_PROBE))

    def _menu_shown(self, session, payload, clock_ms):
        """W14 (D3, S2): the menu she sees for a complete set of menu parts. A whole menu replaces everything and is kept
        as the session's whole menu. A near part is merged with that whole menu (acts.merge_near): her room and what is
        near her come from the near part, the far rooms from the whole. Any whole menu marks the choices as come."""
        if payload.get("near") is not True:
            self._whole_seen = True
            self._whole_menu = {"session": session, "payload": payload, "at_ms": clock_ms}
            return payload
        whole = self._whole_menu
        if not isinstance(whole, dict) or whole.get("session") != session:
            return payload
        return merge_near(payload, whole.get("payload"))

    def _options(self, row, cut=None):
        """8f: her options from the newest menu of this telemetry session; 2.18.0: a question
        the game is asking her (an open dialog that is hers) comes first, menu or not."""
        if not isinstance(row, dict):
            return []
        asked = dialog_options(row, self._resolve_text, refs=self._refs)
        asked += queue_options(row, refs=self._refs, act_name=self._act_names())
        menu = self._menu
        if not isinstance(menu, dict) or menu.get("session") != row.get("telemetry_session_id"):
            return asked
        if self._catalog is None:
            try:
                from .catalog import Catalog
                self._catalog = Catalog(self.paths)
            except Exception:
                self._catalog = False
        room = OPTIONS_LIMIT - len(json.dumps(asked).encode("utf-8")) - 2 if asked else OPTIONS_LIMIT
        # 2.37.0 (W10 H3): act texts keep their tokens here; clean_text fills a person's name or drops them.
        listed = act_options(menu.get("payload"), self._resolve_text.raw, self._catalog or None,
                             people=people_names(row, self._seen_ids()), refs=self._refs, limit=max(0, room),
                             heard=people_heard(row, self._seen_ids()),
                             withheld=self._withheld_names(), room=(row.get("zone") or {}).get("room"),
                             room_labels=self._room_labels(), cut=cut,
                             objects_limit=max(0, OPTIONS_OBJECTS_LIMIT - len(asked)),
                             states=self._index["states"])  # W13 (D9.6): what is broken or dirty, from the things list
        return asked + listed

    def status(self):
        if self.client is None and self._disabled:
            transport = {"enabled": False, "reason": self._disabled}
        else:
            transport = {"enabled": True}
        return {
            "attachment": self._state,
            "telemetry_only": self._telemetry_only,
            "spool": {"rows": self.spool.row_count(), "gaps": len(self.spool.gaps())},
            "outbox": self.spool.outbox_counts(),
            "refusals": self.spool.refusal_counts(),
            "last_heartbeat": self._last_heartbeat,
            "inputs": game_inputs.current(self.spool),
            "transport": transport,
            "thalamus": self.thalamus_status(),
            "probe": self._probe_status(),
        }

    def _probe_status(self):
        latest = self.spool.latest_record()
        probe = latest.get("probe_version") if isinstance(latest, dict) else None
        if not isinstance(probe, str):
            probe = None
        return {"installed": probe, "expected": schema.PROBE_VERSION,
                "match": probe == schema.PROBE_VERSION}

    def thalamus_status(self):
        """The view sender's counts. `fires` is the views sent; `pending` the changes still waiting."""
        self._load_state()
        return {
            "fires": self._fires,
            "last_fire_reason": self._last_fire_reason,
            "last_fire_wall_ms": self._last_fire_wall_ms,
            "pending": len(self._coalesced.items),
            "enqueued": self._enqueued,
        }

    def _load_state(self):
        if self._loaded:
            return
        self._loaded = True
        raw = self.spool.get_kv("coalescer_state")
        if raw:
            self._coalesced = coalesce.from_list(json.loads(raw))
        raw = self.spool.get_kv("extractor_state")
        if raw:
            self._extractor = Extractor.from_dict(json.loads(raw), resolve=self._resolve_text)
        # Not persisted: the held handles are rebuilt from her body samples as they come (the key is kept in the spool).
        self._seen = SeenMemory(self._heard_key())
        self._last_rowid = int(self.spool.get_kv("last_rowid") or 0)
        self._obs_seq = int(self.spool.get_kv("obs_seq") or 0)
        raw = self.spool.get_kv("last_row")
        self._last_row = json.loads(raw) if raw else None
        raw = self.spool.get_kv("last_body_row")
        self._last_body_row = json.loads(raw) if raw else None
        self._set_her(self._last_body_row)
        raw = self.spool.get_kv("act_menu")
        self._menu = json.loads(raw) if raw else None
        raw = self.spool.get_kv("act_menu_whole")  # W14 (D3): the whole menu a near part is merged with
        self._whole_menu = json.loads(raw) if raw else None
        raw = self.spool.get_kv("domus_lists")  # W13 (H): the lists Natalis holds, kept across restarts
        if raw:
            held = json.loads(raw)
            self._lists = held.get("lists") or {}
            self._households = held.get("households") or {}
            self._rooms_table = held.get("rooms") or {}
            self._lists_session = held.get("session")
        self._set_index()
        self._fires = int(self.spool.get_kv("thalamus_fires") or 0)
        self._enqueued = int(self.spool.get_kv("thalamus_enqueued") or 0)
        self._last_fire_reason = self.spool.get_kv("thalamus_last_reason") or None
        wall = self.spool.get_kv("thalamus_last_wall_ms")
        self._last_fire_wall_ms = int(wall) if wall else None

    def _heard_key(self):
        """SS4-v2: the per-install key of the handles of the Sims she hears. Made once, kept in the spool."""
        key = self.spool.get_kv("heard_key")
        if not key:
            key = secrets.token_hex(32)
            self.spool.put_kv("heard_key", key)
        return key

    def _seen_ids(self):
        """SS4-v2: the presence ids she sees at her body's latest sample (None before the state loads)."""
        self._load_state()
        return self._seen.seen_ids if self._seen is not None else None

    def _advance_thalamus(self, wall_ms):
        # D50: one clock, the wall clock. Rows carry the wall time they were written; the tick
        # carries now. The game's monotonic clock restarts at every launch and the bridge's own
        # (uptime) at every boot, so neither one is used for timing.
        # D2: nothing here judges a change. Each one waits in the coalescer until its view goes.
        self._load_state()
        for rowid, record in self.spool.rows_after(self._last_rowid):
            kind = record.get("event_kind") if isinstance(record, dict) else None
            written = record.get("wall_timestamp_ms") if isinstance(record, dict) else None
            clock_ms = written if type(written) is int and 0 <= written <= wall_ms else wall_ms
            if kind == "act_menu" and isinstance(record.get("e2"), dict):
                # HE12: the menu keeps its wall time and its room; its labels are read against her room now.
                # N8 (F4): a menu is shown once all its parts have come (see MenuParts).
                session = record.get("telemetry_session_id")
                taken = self._menu_parts.take(session, record["e2"])
                if taken is not None:
                    shown = self._menu_shown(session, taken, clock_ms)  # W14 (D3): a near part never replaces the whole
                    self._menu = {"session": session, "payload": shown, "at_ms": clock_ms}
                    self._log_spot_stages(shown, clock_ms)  # W12 (C11): the spot stages, read from the log
                    self._extractor.act_words = act_words_by_guid(shown, self._resolve_text.raw)  # W13 (S1)
                    self._notebook_quietly(
                        lambda: self.notebook.observe_menu(self._world(), shown, clock_ms))
            elif kind == "presence_snapshot":
                self._notebook_quietly(
                    lambda: self.notebook.observe_presence(self._world(), record, clock_ms))
                if self.diary is not None:
                    self._notebook_quietly(
                        lambda: self.diary.tick(clock_ms, record, self._world()))
            if kind == "act_event" and self._acts is not None:
                self._acts.on_row(record)
            if kind in ("discovery", "lists", "catalog"):
                # W13 (H): the probe's facts for the lead and for her lists and catalogue; nothing here reaches her view directly.
                self._reach_quietly(lambda: self._reach_row(kind, record, clock_ms))
            self._windows.on_row(record, clock_ms)
            self._pace_log.on_row(record)
            block = record.get("pace") if isinstance(record, dict) else None
            if isinstance(block, dict):
                self._pace_observe(block, clock_ms)
            held = withheld_of(record)
            if held is not None:
                self._notebook_quietly(lambda: self.notebook.observe_withheld(held[0], held[1], clock_ms))
            if self._acts is not None and isinstance(record, dict) and "dialogs" in record:
                self._acts.on_sample(record)
            self.overlay.on_row(record, wall_ms)
            if self.director is not None:
                self.director.on_row(record, wall_ms)
            self.talk.on_row(record, wall_ms, _body_sample(record))
            self._coalesced = coalesce.add(self._coalesced, self._extractor.step(record), clock_ms)
            self._last_row = record
            if _body_sample(record):
                self._last_body_row = record
                self._body_fresh = True
                self._set_her(record)
                self._seen.observe(record)
            self._last_rowid = rowid

    def _follow_refs(self, latest):
        """W12 (B2): the refs of her menu are kept for one game session. An attach flip keeps them; a new telemetry
        session (a new game) starts its own, and the view's attachment changes with the epoch."""
        session = latest.get("telemetry_session_id") if isinstance(latest, dict) else None
        if session is None:
            return
        self._lists_for(session)
        if session == self._refs_session:
            return
        if self._refs_session is not None:
            self._refs = RefBook()
            self._refs_epoch += 1
        self._refs_session = session

    def _lists_for(self, session):
        """W13 (A4-16): a new game session's lists come from its own probe, never the last game's: the lists, households
        and room labels held are dropped (the spool is written again) when the session is not the one they belong to."""
        self._load_state()  # the spooled lists and their session come first, so the check is against them
        if session is None or session == self._lists_session:
            return
        with self._lists_lock:
            self._lists, self._households, self._rooms_table = {}, {}, {}
        self._lists_session = session
        self._set_index()
        self._spool_lists()

    def _spool_lists(self):
        self.spool.put_kv("domus_lists", json.dumps({"lists": self._lists, "households": self._households,
                                                     "rooms": self._rooms_table, "session": self._lists_session}))

    def _attachment(self):
        """W12 (B2): the view's attachment: the helper session, with the refs epoch once the refs have been reset."""
        return self.helper_session if self._refs_epoch == 0 else "%s:%d" % (self.helper_session, self._refs_epoch)

    def _send_due(self, wall_ms):
        """W12 (F1): the diary and the views go after the acts round trip, and a view waits while that round trip failed,
        so no view shows an act's effect before the act's record is with Mint. The changes wait with it."""
        if self._acts is None or self._acts.sync_ok:
            self._send_diary(wall_ms)
            self._flush_views(wall_ms)
        self._persist_thalamus(wall_ms)

    def _body_is_restored(self, wall_ms):
        """W12 (F3): the newest body row is from before this helper started and is too old to be a view of now: no
        view goes from it (the first view after a start must not be an expired wake)."""
        if self._body_fresh or self._last_body_row is None:
            return False
        written = self._last_body_row.get("wall_timestamp_ms")
        return type(written) is not int or wall_ms - written > STALE_BODY_MS

    def _her_first(self):
        """W12 (S2): her first name, as her words are said in it."""
        return (self._resolve_text.her or {}).get("first")

    def _say_words(self, text, object_id):
        """W12 (S2): one talk line in her name (her words to the Sim the act targets)."""
        self.talk.say(text, sim_id=object_id)

    def _log_spot_stages(self, menu, clock_ms):
        """W12 (C11): the menu's spot counters, written to the decision log when they change."""
        stages = menu.get("spot_stages")
        if not isinstance(stages, dict) or stages == self._spot_stages_last:
            return
        self._spot_stages_last = stages
        clean = {str(key)[:32]: value for key, value in list(stages.items())[:16]
                 if isinstance(value, (int, bool)) and not isinstance(value, float)}
        self._log.write({"wall_ms": clock_ms, "trigger": "spot_stages", "stages": clean})

    def _flush_views(self, wall_ms):
        """D2: a view goes when the coalescer says so; nothing pending sends nothing. W12 (F3): not from a restored row."""
        reason = coalesce.due(self._coalesced, wall_ms)
        if reason is None or self._body_is_restored(wall_ms):
            return
        percepts, self._coalesced = coalesce.take(self._coalesced)
        self._send_view(percepts, reason, wall_ms)

    def _set_her(self, row):
        """2.37.0 (W10 H3): her names, from the presence row of her body (the probe's is_body entry), for the words of
        her view. None until a body row names her."""
        display = first = last = None
        for item in (row.get("presence") or []) if isinstance(row, dict) else []:
            if isinstance(item, dict) and item.get("is_body") is True:
                display = item.get("name")
                first, last = item.get("first_name"), item.get("last_name")
                break
        # W12 (E4, E5): the body's own name fields and gender (the probe's keys; absent on an older probe).
        body = row.get("body") if isinstance(row, dict) and isinstance(row.get("body"), dict) else {}
        first = body.get("first_name", first)
        last = body.get("last_name", last)
        self._resolve_text.her = tokens.names_from(first, last, display)
        self._resolve_text.gender = body.get("gender") if body.get("gender") in ("F", "M") else None

    def _send_look(self, wall_ms):
        """D2 (H3): Ashley asked for a look at her body now. One view, from the newest body row, with a look percept;
        the changes waiting go with it. With no body row yet nothing is sent, and the log says so."""
        latest = self.spool.latest_record()
        if _probe_ok(latest.get("probe_version") if isinstance(latest, dict) else None, _NEAR_PROBE):
            # W12 (C1): a look asks for the near part of the menu now (her room and what is near her, read at the write).
            try:
                commands.publish("menu_near", {}, "helper", paths=self.paths)
            except (OSError, ValueError):
                pass
        body = self._last_body_row
        if body is None:
            self._log.write({"wall_ms": wall_ms, "trigger": "look", "percepts": 0, "kinds": [],
                             "enqueued": False, "observation_id": None, "error": "no_body_row"})
            return
        percepts, self._coalesced = coalesce.take(self._coalesced)
        self._send_view(percepts + (Percept("look", "self", "", "asked"),), "look", wall_ms, event=body)

    def _send_view(self, percepts, trigger, wall_ms, event=None):
        """One view of her body now, carrying these changes. Salience is 0: the view says what changed, not what
        matters. One line in the decision log per view sent. event: the row the view is about (default the newest)."""
        self._fires += 1
        self._last_fire_reason = trigger
        self._last_fire_wall_ms = wall_ms
        enqueued = False
        observation_id = None
        error = None
        requeued = False
        dropped_percepts = 0
        ctx = self._obs_ctx(wall_ms, event)
        decision = SimpleNamespace(percepts=[(percept, 0.0) for percept in percepts], reason=trigger)
        obs = build(decision, ctx)
        dropped = None
        if self.client is not None and not self._telemetry_only:
            refusal = self._enqueue_view(obs, wall_ms)
            if isinstance(refusal, ContractError) and refusal.where in ("options", "options_cut"):
                # 2.37.0 (W10 H2): her choices are left out of this view, never the whole view. It is sent again at once
                # without options and without a cut, and a percept says her choices are missing and why.
                dropped = options_why(ctx.get("options"), refusal.where)
                percept = Percept("options_dropped", "self", "", "normal", facts=(("why", dropped),))
                decision = SimpleNamespace(percepts=[(item, 0.0) for item in list(percepts) + [percept]],
                                           reason=trigger)
                obs = build(decision, dict(ctx, options=[], options_cut={}))
                refusal = self._enqueue_view(obs, wall_ms)
            if refusal is None:
                enqueued = True
                self._requeued = 0
                self._pace_log.observed(_ticks(self._last_body_row or self._last_row))
                observation_id = obs["observation_id"]
                self._obs_seq += 1
                self._enqueued += 1
            else:
                # 2.37.0 (W10 H1): the log says what was refused and on which key, not only the class's name.
                error = refusal_text(refusal) if isinstance(refusal, ContractError) else type(refusal).__name__
                # W12 (F4): a refused view drops nothing: its changes wait for the next view, a few times over.
                if self._requeued < REQUEUE_LIMIT and percepts:
                    self._requeued += 1
                    self._coalesced = coalesce.add(self._coalesced, percepts, wall_ms)
                    requeued = True
                else:
                    self._requeued = 0
                    dropped_percepts = len(percepts)
        line = {
            "wall_ms": wall_ms,
            "trigger": trigger,
            "percepts": len(percepts),
            "kinds": sorted({percept.kind for percept in percepts}),
            "enqueued": enqueued,
            "observation_id": observation_id,
        }
        if dropped is not None:
            line["options_dropped"] = dropped
        if error is not None:
            line["error"] = error
        if requeued:
            line["requeued"] = True
        if dropped_percepts:
            line["dropped_percepts"] = dropped_percepts
        self._log.write(line)

    def _enqueue_view(self, obs, wall_ms):
        """2.37.0 (W10 H1): the spool takes the view (None) or refuses it (the ContractError or OutboxConflict)."""
        try:
            self.spool.enqueue_observation(obs, wall_ms)
        except (ContractError, OutboxConflict) as exc:
            return exc
        return None

    def _send_diary(self, wall_ms):
        if self.diary is None or self.client is None or self._telemetry_only or self._last_row is None:
            return
        pending = self.diary.pending()
        if not pending:
            return
        # build() only reads attributes. Percept rejects kinds outside the thalamus set,
        # and sleep_onset is a diary percept, not one of those.
        percept = SimpleNamespace(
            kind="sleep_onset", subject="self", object=None, bucket="body",
            urgency="always_through", facts={"onset_minute": pending.get("onset_minute")})
        decision = SimpleNamespace(percepts=[(percept, 1.0)], reason="sleep_onset", fired=True)
        try:
            obs = build(decision, self._obs_ctx(wall_ms))
            obs["day"] = pending["day"]
            self.spool.enqueue_observation(obs, wall_ms)
        except (ContractError, OutboxConflict):
            return
        self._obs_seq += 1
        self._enqueued += 1
        self.diary.clear()

    def _obs_ctx(self, wall_ms, event=None):
        # Portrait, dialogs and presence come from the latest body sample. Timing and
        # identity of this decision stay on the newest row, which may be an event.
        body = self._last_body_row or self._last_row
        session = body.get("telemetry_session_id") if isinstance(body, dict) else None
        options_cut = {}  # N8 (F4): what the options left out, named in the view (filled by _options)
        return {
            "helper_session": self._attachment(),
            "obs_seq": self._obs_seq,
            "slot_id": self._extractor.slot_id,
            "guid": self._extractor.guid,
            "lineage_class": self._extractor.lineage_class,
            "row": body,
            "event_row": self._last_row if event is None else event,
            "resolve_text": self._resolve_text,
            "act_name": self._act_names(),
            "room_labels": self._room_labels(),
            "seen": self._seen,
            "options": self._options(body, cut=options_cut),
            "options_cut": options_cut,
            "choices_pending": not self._whole_seen,  # W14 (S2): the game's choices have not come in this session
            "notebook": self._notebook_slice(wall_ms),
            "windows": self._windows.recent(wall_ms, session),
            "pace": pace.portrait(self._pace_block, self._pace_log.costs()),
        }

    def _pace_observe(self, block, now_ms):
        """W3h: the probe's applied pace, row by row. Three rows in a row that differ from the
        wanted values ask for one resend (at most once a minute, so a refused clock is not
        re-asked for every row)."""
        self._pace_block = block
        if not pace.applied_differs(block, self._pace_settings.values):
            self._pace_streak = 0
            return
        self._pace_streak += 1
        if self._pace_streak >= pace.MISMATCH_ROWS:
            self._pace_streak = 0
            if self._pace_sent_ms is None or now_ms - self._pace_sent_ms >= pace.MISMATCH_EVERY_MS:
                self._pace_mismatch = True

    def _pace_tick(self, now, probe=None):
        """W3h: the probe's pace follows the settings. Sent when the game attaches, when a setting
        changes, and when the probe's rows show other values. Nothing is sent while detached.
        W12 (F5): not sent to a probe that predates the pace command."""
        settings = self._pace_settings.refresh()
        if self._state != "attached" or not _probe_ok(probe, _PACE_PROBE):
            self._pace_attached = False
            return
        wanted = (settings["need_drain"], settings["slow_time"])
        due = not self._pace_attached or wanted != self._pace_sent or self._pace_mismatch
        if not due or (self._pace_retry_ms is not None and now < self._pace_retry_ms):
            return
        try:
            commands.publish("pace", {"need_drain": wanted[0], "slow_time": wanted[1]}, "helper",
                             paths=self.paths)
        except (ValueError, OSError) as error:
            self._pace_retry_ms = now + PACE_RETRY_MS
            print("pace not sent: %s" % type(error).__name__)
            return
        self._pace_attached = True
        self._pace_sent = wanted
        self._pace_sent_ms = now
        self._pace_mismatch = False
        self._pace_retry_ms = None

    def _act_names(self):
        """HE1: the game's own words for her acts, from the newest menu's text keys (humanized as fallback)."""
        # 2.37.0 (W10 H3): act texts keep their tokens here; clean_text drops them (an act's words never say her name).
        return act_names(self._menu.get("payload") if isinstance(self._menu, dict) else None, self._resolve_text.raw)

    def _world(self):
        slot = self._extractor.slot_id
        return "unknown" if slot is None else "slot%s" % slot

    def _answer_memory(self, asks, client, helper_session):
        """D7b: her questions to the game's memory, answered off the tick from the records of this world."""
        memory.handle_asks_in_background(asks, client, helper_session=helper_session, world=self._world(),
                                         read_records=self.diary.read_records)

    def _reach_quietly(self, fn):
        """W13 (H, A4-17): a probe row the lists, the catalogue or the discovery file read never stops the bridge. Any
        error is logged by its class name (its text is never logged)."""
        try:
            fn()
        except Exception as error:
            self._log.write({"wall_ms": int(time.time() * 1000), "trigger": "reach", "error": type(error).__name__})

    def _reach_row(self, kind, record, clock_ms):
        """W13 (H): a discovery record (a file, and one log line); one part of a list, or of the catalogue, kept whole."""
        e2 = record.get("e2") if isinstance(record.get("e2"), dict) else record
        if kind == "discovery":
            name = reach.write_discovery(self.paths.data_dir / "discovery", record)
            if name is not None:
                sections = e2.get("sections") if isinstance(e2.get("sections"), dict) else {}
                self._log.write({"wall_ms": clock_ms, "trigger": "discovery", "file": name,
                                 "sections": sorted(str(key)[:32] for key in sections)[:32]})
        elif kind == "lists":
            self._lists_for(record.get("telemetry_session_id"))
            list_kind = e2.get("kind")
            raw = self._list_parts.take(list_kind, e2) if list_kind in reach.KINDS else None
            if raw is not None:
                self._store_list(list_kind, raw, total=self._list_parts.totals.get(list_kind))
        else:
            raw = self._list_parts.take("catalog", e2, rev_key="catalog_rev")
            if raw is not None and self.detected_build is not None:
                stored = catalog.store_flags(self.paths, self.detected_build, raw)
                self._log.write({"wall_ms": clock_ms, "trigger": "catalog", "items": len(raw)})
                if stored == 0:
                    # HOME2-6: the game answered the dump with no usable row for this build; it is not asked again for it.
                    self.spool.put_kv("catalog_answered", self.detected_build)
            elif raw is not None and not self._catalog_no_build_logged:
                # HELPER2-14: the catalogue is not stored without the game's build; said once, not per part.
                self._catalog_no_build_logged = True
                self._log.write({"wall_ms": clock_ms, "trigger": "catalog", "error": "no_build", "items": len(raw)})

    def _store_list(self, kind, raw, total=None):
        """W13 (H): a whole list, in words, held as Natalis will hold it. Its digest is what the sync answer is checked
        against, so a list is sent again only when its words change. total is the probe's count of the list (HELPER2-3);
        without one, the total is the count before the helper's own byte cut."""
        if kind == "people":
            self._households = reach.households_of(raw)
        if kind == "things":
            # W13 (S5): the room labels come from this list, and the things are placed by them.
            with self._lists_lock:
                self._rooms_table = reach.room_labels(raw, resolve=self._resolve_text.raw, catalog=self._catalog_lookup())
        skipped = []
        words = reach.list_words(kind, raw, refs=self._refs, rooms=self._room_labels(), resolve=self._resolve_text.raw,
                                 catalog=self._catalog_lookup(), households=self._households, skipped=skipped)
        items = reach.fit(words)
        # Natalis takes a total no smaller than the items it is sent (T1): the probe's total, or the words before the cut.
        total = max(total if total is not None else len(words), len(items))
        if skipped or len(items) < len(words):
            # W13 (H): what Natalis's shape left out, by reason and count (never the names).
            reasons = {}
            for reason in skipped:
                reasons[reason] = reasons.get(reason, 0) + 1
            self._log.write({"wall_ms": int(time.time() * 1000), "trigger": "lists", "kind": kind,
                             "skipped": reasons, "cut": len(words) - len(items)})
        with self._lists_lock:
            # HELPER2-10: the game session the list was built from; a post after the session changed is dropped.
            self._lists[kind] = {"digest": reach.digest(items, total), "items": items, "total": total,
                                 "session": self._lists_session}
        self._set_index()
        self._spool_lists()

    def _set_index(self):
        """W13 (H): the names and conditions of things and places, and the names of people, from the lists held. The
        people's names also serve the phone (a text or call names its sender)."""
        self._index = reach.index(self._lists)
        self._extractor.people_names = self._index["people"]

    def _catalog_lookup(self):
        if self._catalog is None:
            try:
                self._catalog = catalog.Catalog(self.paths)
            except Exception:
                self._catalog = False
        return self._catalog or None

    def _result_words(self, result, start=None):
        """W13 (D9.3): a verb act's result facts in words: names from the things and places she holds, rooms from the
        labels of her things' rooms (S5). start is the act's own start, for an event (S7)."""
        rooms = self._room_labels()
        return reach.result_words(result, name_of=self._index["things"].get, room_of=rooms.get,
                                  place_of=self._index["places"].get, start=start)

    def _answered(self, answer, client, helper_session):
        """W13 (H): what a sync answer asks of the helper. A list Natalis does not hold at its digest is sent off the acts
        loop (A4-9); a catalogue ask is searched and answered on its own thread."""
        if not isinstance(answer, dict):
            return
        held = answer.get("lists")
        if isinstance(held, dict) and hasattr(client, "post_lists"):
            self._post_lists_later(held, client, helper_session)
        catalog_ask.handle_asks_in_background(answer.get("catalog") or [], client, helper_session=helper_session,
                                              refs=self._refs, search=self._catalog_search)

    def _post_lists_later(self, held, client, helper_session):
        """W13 (A4-9): the lists Natalis lacks are posted on a daemon thread, one pass at a time, so a slow Natalis never
        holds the acts loop (the view and the acts for that tick wait with it)."""
        with self._lists_lock:
            if self._lists_busy:
                return
            self._lists_busy = True
        threading.Thread(target=self._post_lists, args=(held, client, helper_session), name="domus-lists",
                         daemon=True).start()

    def _post_lists(self, held, client, helper_session):
        try:
            for kind in reach.KINDS:
                with self._lists_lock:
                    entry = self._lists.get(kind)
                if entry is None or held.get(kind) == entry["digest"]:
                    continue
                self._post_list(kind, entry, client, helper_session)
        finally:
            with self._lists_lock:
                self._lists_busy = False

    def _post_list(self, kind, entry, client, helper_session):
        """W13 (H, A4-15): one list, posted unless its retry wait runs. A failed round trip waits LIST_RETRY_MS. A list
        Natalis refuses waits LIST_RETRY_MS for each of its first refusals; after LIST_REFUSALS of the same digest it
        waits LIST_REFUSED_WAIT_MS, and its reason is logged once, at that point."""
        now = self._mono()
        with self._lists_lock:
            built = entry.get("session")
            current = self._lists_session
        if built is not None and built != current:
            return  # HELPER2-10: an older game's list is not Natalis's list of this one
        # HELPER2-7: a refusal's wait belongs to its digest; a failed round trip's wait belongs to the kind.
        if now < self._list_retry_ms.get(kind, 0) or now < self._list_retry_ms.get((kind, entry["digest"]), 0):
            return
        body = {"v": 1, "helper_session": helper_session, "kind": kind, "digest": entry["digest"],
                "items": entry["items"], "total": entry.get("total", len(entry["items"]))}
        try:
            sent = client.post_lists(body)
        except Exception:
            sent = None
        if isinstance(sent, dict):
            self._list_refusals.pop(kind, None)
            return
        if isinstance(sent, SyncRefused):
            held_digest, refusals = self._list_refusals.get(kind, [None, 0])
            refusals = refusals + 1 if held_digest == entry["digest"] else 1
            self._list_refusals[kind] = [entry["digest"], refusals]
            # HELPER2-7: a refused digest waits by itself; a corrected list of the kind is not held back by it.
            wait = LIST_REFUSED_WAIT_MS if refusals >= LIST_REFUSALS else LIST_RETRY_MS
            self._list_retry_ms[(kind, entry["digest"])] = now + wait
            if refusals == LIST_REFUSALS:
                self._log.write({"wall_ms": int(time.time() * 1000), "trigger": "lists", "error": "refused",
                                 "kind": kind, "reason": sent.reason or "unknown", "refusals": refusals})
            return
        self._log.write({"wall_ms": int(time.time() * 1000), "trigger": "lists", "error": "not_sent", "kind": kind})
        self._list_retry_ms[kind] = now + LIST_RETRY_MS

    def _catalog_search(self, words, max_price, placement):
        """W13 (H): the purchasable furniture and decor matched on words, from the catalogue of the running game."""
        if self.detected_build is None:
            return 0, []
        return catalog.search(self.paths, self.detected_build, words, max_price=max_price, placement=placement,
                              resolve=self._resolve_text.raw)

    def _catalog_dump(self, now, probe):
        """W13 (H, P2): the probe writes the catalogue once per game version. It is asked for while she is attached, on a
        probe that has the command, when the catalogue holds no flags for this build; checked again at most every
        CATALOG_DUMP_EVERY_MS."""
        if self.client is None or self.detected_build is None or self._state != "attached" or not _probe_ok(probe, _VERB_PROBE):
            return
        if self._catalog_checked_ms is not None and now - self._catalog_checked_ms < CATALOG_DUMP_EVERY_MS:
            return
        self._catalog_checked_ms = now
        if catalog.has_flags(self.paths, self.detected_build) or self.spool.get_kv("catalog_answered") == self.detected_build:
            return
        try:
            commands.publish("catalog_dump", {}, "helper", paths=self.paths)
        except (ValueError, OSError) as error:
            print("catalogue dump not asked: %s" % type(error).__name__)

    def _verb_act_ended(self):
        """HELPER2-4: a verb act ended, so her lists may have changed: they are asked for on the next tick (see
        _lists_now_due)."""
        self._lists_now_owed = True

    def _lists_now_due(self, now, probe):
        """HELPER2-4: the probe is asked for fresh lists (lists_now) once a verb act has ended, at most once per
        LISTS_NOW_EVERY_MS; an ask that falls inside that wait is made when the wait is over. Needs a probe with the
        command."""
        if not self._lists_now_owed or self.client is None or not _probe_ok(probe, _VERB_PROBE):
            return
        if self._lists_now_sent_ms is not None and now - self._lists_now_sent_ms < LISTS_NOW_EVERY_MS:
            return
        self._lists_now_owed = False
        self._lists_now_sent_ms = now
        try:
            commands.publish("lists_now", {}, "helper", paths=self.paths)
        except (ValueError, OSError) as error:
            self._log.write({"wall_ms": now, "trigger": "lists_now", "error": type(error).__name__})

    def _notebook_quietly(self, fn):
        try:
            fn()
        except (sqlite3.Error, ValueError, TypeError, KeyError, OSError):
            pass

    def _withheld_names(self):
        try:
            return self.notebook.withheld_names()
        except (sqlite3.Error, ValueError, TypeError, KeyError):
            return set()

    def _room_labels(self):
        """W13 (S5): the room labels of her things' rooms (room id -> label), from the newest things list; {} until one."""
        return dict(self._rooms_table)

    def _notebook_slice(self, wall_ms):
        try:
            return self.notebook.slice(self._world(), (self._menu or {}).get("payload"), wall_ms)
        except (sqlite3.Error, ValueError, TypeError, KeyError):
            return None

    def _maybe_rebuild_procedures(self, now):
        checked = self._outcomes_checked_ms
        if checked is not None and now - checked < 600_000:
            return
        self._outcomes_checked_ms = now
        folder = self.paths.data_dir / "outcomes"
        mtimes = [path.stat().st_mtime for path in folder.glob("*.jsonl")] if folder.is_dir() else []
        newest = max(mtimes) if mtimes else None
        if newest is None or newest == self._outcomes_mtime:
            return
        self._outcomes_mtime = newest
        self._notebook_quietly(lambda: self.notebook.rebuild_procedures(
            notebook.load_outcome_records(self.paths), now))

    def _row_due(self, key, value, now_ms):
        """HE17: a newest row is written when it changed since its last write, and no sooner than 30 s after it."""
        last = self._row_written.get(key)
        due = last is None or (last[0] != value and now_ms - last[1] >= ROW_WRITE_EVERY_MS)
        if due:
            self._row_written[key] = (value, now_ms)
        return due

    def _persist_thalamus(self, now_ms):
        rows = {}
        for key, row in (("last_row", self._last_row), ("last_body_row", self._last_body_row)):
            value = json.dumps(row)
            if self._row_due(key, value, now_ms):
                rows[key] = value
        values = {
            "coalescer_state": json.dumps(coalesce.to_list(self._coalesced)),
            "extractor_state": json.dumps(self._extractor.to_dict()),
            "last_rowid": str(self._last_rowid),
            "obs_seq": str(self._obs_seq),
            "act_menu": json.dumps(self._menu),
            "act_menu_whole": json.dumps(self._whole_menu),  # W14 (D3)
            "thalamus_fires": str(self._fires),
            "thalamus_enqueued": str(self._enqueued),
            "thalamus_last_reason": "" if self._last_fire_reason is None else self._last_fire_reason,
            "thalamus_last_wall_ms": "" if self._last_fire_wall_ms is None else str(self._last_fire_wall_ms),
        }
        values.update(rows)
        self.spool.put_many_kv(values)


def _helper_build():
    """E4: the commit this helper runs from, for the proof trace (None outside a checkout)."""
    import subprocess
    from pathlib import Path
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parent,
                                capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    sha = result.stdout.strip()
    return sha[:40] if result.returncode == 0 and sha else None


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m domus_helper.bridge")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float)
    parser.add_argument("--with-game", action="store_true",
                        help="live as long as the game: exit once it has been closed for GAME_DRAIN_S")
    args = parser.parse_args(argv)
    bridge = Bridge()
    if args.once:
        bridge.tick(int(time.time() * 1000))
        print(json.dumps(bridge.status(), sort_keys=True))
        return 0
    if args.interval is None:
        parser.error("pass --once or --interval")
    if overlay_pages.serve(bridge.overlay) is None:
        print("overlay pages not served: port %d is taken" % overlay_pages.PORT)
    archived_at = None
    # The watcher starts the bridge only once it has seen the game; a check that fails while the
    # game is still launching must not end the bridge before the usual drain.
    game_seen_at = time.time() if args.with_game else None
    while True:
        try:
            now = time.time()
            if args.with_game:
                if bridge._process() is not None:
                    game_seen_at = now
                elif game_seen_at is None or now - game_seen_at >= GAME_DRAIN_S:
                    return 0
            if archived_at is None or now - archived_at >= ARCHIVE_EVERY_S:
                archived_at = now
                _archive_quietly(now)
                _strings_quietly()
                _prune_done_quietly(now)  # W12 (F6): finished commands older than seven days leave cmd/done
            bridge.tick(int(now * 1000))
            time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0


# D38: the probe stops recording when its telemetry folder is full (1 GiB since
# 2.15.2); finished sessions older than a day move to the helper's data folder
# (verified gzip) at start and every 6 h.
ARCHIVE_EVERY_S = 6 * 3600

# The bridge lives with the game (tools/bridge.ps1 starts it when TS4_x64.exe appears). After the
# game closes it keeps ticking this long: the probe's last rows are read and sent, and Ashley gets
# a heartbeat with attached false.
GAME_DRAIN_S = 150


def _strings_quietly():
    """S0: build or refresh the local string and catalogue indexes (each skipped when
    nothing changed)."""
    from pathlib import Path
    from . import catalog, strings
    from .paths import DEFAULT_GAME_ROOT
    paths = Paths.from_env()
    if paths.game_root is None:
        paths = Paths(paths.sims_root, Path(DEFAULT_GAME_ROOT))
    try:
        strings.build(paths)
    except Exception as error:
        print("string index skipped: %s" % type(error).__name__)
    try:
        catalog.build(paths)
    except Exception as error:
        print("catalogue index skipped: %s" % type(error).__name__)


def _prune_done_quietly(now):
    try:
        removed = commands.prune_done(Paths.from_env(), int(now * 1000))
    except OSError as error:
        print("command folder not pruned: %s" % type(error).__name__)
        return
    if removed:
        print("command replies pruned: %d" % len(removed))


def _archive_quietly(now):
    from . import telemetry_archive
    try:
        telemetry_archive.run(paths=Paths.from_env(), now=now, out=lambda line: None)
    except Exception as error:
        print("telemetry archive skipped: %s" % type(error).__name__)
    # E4: finished days of the proof trace get their OpenTimestamps proof.
    from datetime import datetime
    from . import proof
    try:
        for result in proof.stamp_finished_days(Paths.from_env().data_dir, datetime.now().strftime("%Y%m%d")):
            print("proof stamp %s: %s" % (result["day"], ", ".join(result["stamped"]) or "no calendar answered"))
    except Exception as error:
        print("proof stamp skipped: %s" % type(error).__name__)


def _crash_logged(argv=None):
    """Run main; a crash leaves its traceback in <data>/bridge_crash.log (the watcher's console may not show it)."""
    try:
        return main(argv)
    except Exception:
        import traceback
        try:
            from datetime import datetime, timezone
            path = Paths.from_env().data_dir / "bridge_crash.log"
            with open(path, "a", encoding="utf-8") as handle:
                stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
                handle.write("== %s\n%s\n" % (stamp, traceback.format_exc()))
        except Exception:
            pass
        raise


if __name__ == "__main__":
    raise SystemExit(_crash_logged())
