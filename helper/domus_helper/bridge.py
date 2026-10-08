"""Helper bridge: spool telemetry, heartbeat, and flush the observation outbox."""
import argparse
import dataclasses
import json
import sqlite3
import time
import uuid
from types import SimpleNamespace

from . import commands
from . import fingerprints as fingerprint_reader
from . import pace
from .vendor import schema
from .acts import OPTIONS_LIMIT, ActCourier, act_names, dialog_options, options as act_options, people_names, queue_options
from .attachment import AttachmentMonitor
from . import inputs as game_inputs
from . import overlay as overlay_pages
from .director import Director
from .talk import Talk
from . import notebook
from .diary import DiaryWatch
from .proof import Trace
from .contract import ContractError
from .cursor import TelemetryCursor
from .paths import Paths
from .spool import OutboxConflict, Spool
from .thalamus.core import decide, prune
from .thalamus.log import DecisionLog
from .thalamus.observation import build
from .thalamus.parameters import Parameters
from .thalamus.percepts import Extractor
from .thalamus.scorer import load_scorer, run_scorer
from .thalamus.types import Context, ThalamusState
from .transport import AshleyClient, load_credentials
from .windows import WindowLog, withheld_of

_AUTO = object()
HEARTBEAT_EVERY_MS = 60_000
_CAMERA_PROBE = (2, 21, 0)
_TALK_PROBE = (2, 26, 0)
# W3h: a pace command that could not be written is tried again after this long.
PACE_RETRY_MS = 30_000
# HE17: the newest row is kept in the spool when it changed, and at most this often.
ROW_WRITE_EVERY_MS = 30_000
# HE16: the wakes a quiet game makes (no new row), and the window an observation stays valid for.
CLOCK_WAKES = ("check", "boredom")
OBSERVATION_WINDOW_MS = 600_000


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


def _wall(record):
    wall = record.get("wall_timestamp_ms") if isinstance(record, dict) else None
    return wall if type(wall) is int else 0


def _ticks(record):
    game = record.get("game") if isinstance(record, dict) else None
    return game.get("ticks") if isinstance(game, dict) else None


def _trace(item):
    return {
        "key": item.key,
        "raw": item.raw,
        "h_before": item.h_before,
        "h_after": item.h_after,
        "salience": item.salience,
        "novelty": item.novelty,
    }


class Bridge:
    def __init__(self, paths=None, *, client=_AUTO, process=_AUTO, detected_build=_AUTO, mono=None, scorer=_AUTO):
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
        self._resolve_text = Resolver(self.paths)
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
        self._params = Parameters()
        self._context = Context()
        self._log = DecisionLog(self.paths.data_dir)
        self._loaded = False
        self._thalamus = ThalamusState()
        self._extractor = Extractor()
        self._last_rowid = 0
        self._obs_seq = 0
        self._last_row = None
        self._last_body_row = None
        self._fires = 0
        self._enqueued = 0
        self._last_fire_reason = None
        self._last_fire_wall_ms = None
        self._theta = self._params.theta0
        # 8f: the probe's newest menu of what she can do ({session, payload}), and the courier
        # that carries her requested acts to the probe (only when Ashley is reachable).
        self._menu = None
        self._catalog = None
        self._acts = None if self.client is None else ActCourier(
            self.spool, lambda command, args: commands.publish(command, args, "helper", paths=self.paths),
            resolve=self._resolve_text)
        # E3: the overlay pages' state (served by main() on this PC only).
        self.overlay = overlay_pages.Overlay(self.spool, self.paths.data_dir, int(time.time() * 1000), self._resolve_text,
                                             trace=Trace(self.spool, self.paths.data_dir), helper_build=_helper_build())
        self.director = None if self.client is None else Director(
            self.spool, lambda command, args: commands.publish(command, args, "helper", paths=self.paths))
        # 2.26.0: social talk on the User's screen; local only, so it works without Ashley too.
        self.talk = Talk(self.spool, lambda command, args: commands.publish(command, args, "helper", paths=self.paths))
        if self._acts is not None:
            self.overlay.answered = self._acts.answered_dialogs
        if scorer is _AUTO:
            self.scorer, self._scorer_note = load_scorer()
        else:
            self.scorer = scorer
            self._scorer_note = None
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
            self._last_heartbeat_ms = now
            self._tried_inputs = inputs
            self._tried_attached = attached
        if self.client is not None:
            self.spool.flush(self.client, now)
        if self.client is not None and self._acts is not None and hasattr(self.client, "sync_acts"):
            written = self._acts.tick(self.client, self.helper_session, now, self._state == "attached")
            self._pace_log.received(written)
            self.overlay.answered = self._acts.answered_dialogs
        self._pace_tick(now)
        self.overlay.poll(self.client, self.helper_session, now)
        self.overlay.act_name = self._act_names()
        self.overlay.publish(now, self._state == "attached")
        if self.director is not None:
            live = self.overlay.published.get("mode") == "live" and _probe_ok(probe)
            self.director.tick(now, live)
        self.talk.tick(now, self._state == "attached" and _probe_ok(probe, _TALK_PROBE))

    def _options(self, row):
        """8f: her options from the newest menu of this telemetry session; 2.18.0: a question
        the game is asking her (an open dialog that is hers) comes first, menu or not."""
        if not isinstance(row, dict):
            return []
        asked = dialog_options(row, self._resolve_text)
        asked += queue_options(row, start=sum(len(item["acts"]) for item in asked), act_name=self._act_names())
        menu = self._menu
        if not isinstance(menu, dict) or menu.get("session") != row.get("telemetry_session_id"):
            return asked
        if self._catalog is None:
            try:
                from .catalog import Catalog
                self._catalog = Catalog(self.paths)
            except Exception:
                self._catalog = False
        count = sum(len(item["acts"]) for item in asked)
        room = OPTIONS_LIMIT - len(json.dumps(asked).encode("utf-8")) - 2 if asked else OPTIONS_LIMIT
        listed = act_options(menu.get("payload"), self._resolve_text, self._catalog or None,
                             people=people_names(row), start=count, limit=max(0, room),
                             withheld=self._withheld_names(), room=(row.get("zone") or {}).get("room"))
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
        self._load_thalamus()
        note = self._scorer_note
        return {
            "fires": self._fires,
            "last_fire_reason": self._last_fire_reason,
            "last_fire_wall_ms": self._last_fire_wall_ms,
            "pending": len(self._thalamus.pending),
            "theta": self._theta,
            "keys": len(self._thalamus.keys),
            "enqueued": self._enqueued,
            "scorer": note if note else type(self.scorer).__name__,
        }

    def _load_thalamus(self):
        if self._loaded:
            return
        self._loaded = True
        raw = self.spool.get_kv("thalamus_state")
        if raw:
            self._thalamus = ThalamusState.from_dict(json.loads(raw))
        raw = self.spool.get_kv("extractor_state")
        if raw:
            self._extractor = Extractor.from_dict(json.loads(raw))
        self._last_rowid = int(self.spool.get_kv("last_rowid") or 0)
        self._obs_seq = int(self.spool.get_kv("obs_seq") or 0)
        raw = self.spool.get_kv("last_row")
        self._last_row = json.loads(raw) if raw else None
        raw = self.spool.get_kv("last_body_row")
        self._last_body_row = json.loads(raw) if raw else None
        raw = self.spool.get_kv("act_menu")
        self._menu = json.loads(raw) if raw else None
        self._fires = int(self.spool.get_kv("thalamus_fires") or 0)
        self._enqueued = int(self.spool.get_kv("thalamus_enqueued") or 0)
        self._last_fire_reason = self.spool.get_kv("thalamus_last_reason") or None
        wall = self.spool.get_kv("thalamus_last_wall_ms")
        self._last_fire_wall_ms = int(wall) if wall else None
        theta = self.spool.get_kv("thalamus_theta")
        if theta is not None:
            self._theta = float(theta)

    def _advance_thalamus(self, wall_ms):
        # D50: one clock for the thalamus, the wall clock. Rows carry the wall time they were
        # written; the tick carries now. The game's monotonic clock restarts at every launch
        # and the bridge's own (uptime) at every boot, and the thalamus never moves time
        # back, so either one froze it after a restart (live 2026-10-05: arousal 43 against
        # threshold 1 and no fire).
        self._load_thalamus()
        for rowid, record in self.spool.rows_after(self._last_rowid):
            kind = record.get("event_kind") if isinstance(record, dict) else None
            written = record.get("wall_timestamp_ms") if isinstance(record, dict) else None
            clock_ms = written if type(written) is int and 0 <= written <= wall_ms else wall_ms
            if kind == "act_menu" and isinstance(record.get("e2"), dict):
                # HE12: the menu keeps its wall time and its room; its labels are read against her room now.
                self._menu = {"session": record.get("telemetry_session_id"), "payload": record["e2"],
                              "at_ms": clock_ms}
                self._notebook_quietly(
                    lambda: self.notebook.observe_menu(self._world(), record["e2"], clock_ms))
            elif kind == "presence_snapshot":
                self._notebook_quietly(
                    lambda: self.notebook.observe_presence(self._world(), record, clock_ms))
                if self.diary is not None:
                    self._notebook_quietly(
                        lambda: self.diary.tick(clock_ms, record, self._world()))
            if kind == "act_event" and self._acts is not None:
                self._acts.on_row(record)
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
            percepts = self._extractor.step(record)
            if self._acts is not None and self._acts.planned > 0:
                # H0.5: between the steps of her plan she is idle for a moment; that is not a
                # decision point (Ashley sends the next step in the same round trip).
                percepts = [dataclasses.replace(p, urgency="normal") if p.bucket == "idle" else p
                            for p in percepts]
            self._thalamus, decision = decide(
                self._thalamus, percepts, clock_ms, self._params, self._points())
            self._theta = decision.theta
            self._last_row = record
            if _body_sample(record):
                self._last_body_row = record
            self._last_rowid = rowid
            seq = record.get("written_sequence") if isinstance(record, dict) else None
            self._on_decision(decision, percepts, wall_ms, clock_ms, seq if type(seq) is int else None)
        self._send_diary(wall_ms)
        self._thalamus, decision = decide(
            self._thalamus, [], wall_ms, self._params, self._points())
        self._theta = decision.theta
        self._on_decision(decision, [], wall_ms, wall_ms, None)
        lineage = self._extractor.lineage_id
        self._thalamus = prune(self._thalamus, wall_ms, self._params, lineage)
        self._persist_thalamus(wall_ms)

    def _points(self):
        """H0.5: the live bridge wakes her at decision points. Before the first snapshot her body
        counts as idle."""
        return dataclasses.replace(self._context, busy=self._extractor.busy is True)

    def _on_decision(self, decision, percepts, wall_ms, clock_ms, row_seq):
        if not percepts and not decision.fired:
            return
        enqueued = False
        observation_id = None
        scorer = None
        if decision.fired:
            self._fires += 1
            self._last_fire_reason = decision.reason
            self._last_fire_wall_ms = wall_ms
            if decision.percepts and self._last_row is not None and decision.reason in CLOCK_WAKES and (
                    wall_ms - _wall(self._last_row) > OBSERVATION_WINDOW_MS):
                # HE16: a check or boredom wake is built from the newest row; a row this old would only expire.
                scorer = {"skipped": "stale_row"}
            elif decision.percepts and self._last_row is not None:
                obs = build(decision, self._obs_ctx(wall_ms))
                scorer = run_scorer(self.scorer, json.loads(json.dumps(obs)))
                if self.client is not None and not self._telemetry_only:
                    try:
                        self.spool.enqueue_observation(obs, wall_ms)
                    except (ContractError, OutboxConflict) as exc:
                        scorer = {"error": "%s: %s" % (type(exc).__name__, exc)}
                    else:
                        enqueued = True
                        self._pace_log.observed(_ticks(self._last_body_row or self._last_row))
                        observation_id = obs["observation_id"]
                        self._obs_seq += 1
                        self._enqueued += 1
        self._log.write({
            "wall_ms": wall_ms,
            "clock_ms": clock_ms,
            "ticks": _ticks(self._last_row),
            "urgency": sorted({percept.urgency for percept, _ in decision.percepts}),
            "row_seq": row_seq,
            "fired": decision.fired,
            "reason": decision.reason,
            "theta": decision.theta,
            "arousal": decision.arousal,
            "traces": [_trace(item) for item in decision.trace],
            "enqueued": enqueued,
            "observation_id": observation_id,
            "scorer": scorer,
        })

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

    def _obs_ctx(self, wall_ms):
        # Portrait, dialogs and presence come from the latest body sample. Timing and
        # identity of this decision stay on the newest row, which may be an event.
        body = self._last_body_row or self._last_row
        session = body.get("telemetry_session_id") if isinstance(body, dict) else None
        return {
            "helper_session": self.helper_session,
            "obs_seq": self._obs_seq,
            "slot_id": self._extractor.slot_id,
            "guid": self._extractor.guid,
            "lineage_class": self._extractor.lineage_class,
            "row": body,
            "event_row": self._last_row,
            "resolve_text": self._resolve_text,
            "act_name": self._act_names(),
            "options": self._options(body),
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

    def _pace_tick(self, now):
        """W3h: the probe's pace follows the settings. Sent when the game attaches, when a setting
        changes, and when the probe's rows show other values. Nothing is sent while detached."""
        settings = self._pace_settings.refresh()
        if self._state != "attached":
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
        return act_names(self._menu.get("payload") if isinstance(self._menu, dict) else None, self._resolve_text)

    def _world(self):
        slot = self._extractor.slot_id
        return "unknown" if slot is None else "slot%s" % slot

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
            "thalamus_state": json.dumps(self._thalamus.to_dict()),
            "extractor_state": json.dumps(self._extractor.to_dict()),
            "last_rowid": str(self._last_rowid),
            "obs_seq": str(self._obs_seq),
            "act_menu": json.dumps(self._menu),
            "thalamus_fires": str(self._fires),
            "thalamus_enqueued": str(self._enqueued),
            "thalamus_last_reason": "" if self._last_fire_reason is None else self._last_fire_reason,
            "thalamus_last_wall_ms": "" if self._last_fire_wall_ms is None else str(self._last_fire_wall_ms),
            "thalamus_theta": str(self._theta),
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
