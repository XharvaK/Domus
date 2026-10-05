"""Helper bridge: spool telemetry, heartbeat, and flush the observation outbox."""
import argparse
import json
import time
import uuid

from . import commands
from . import fingerprints as fingerprint_reader
from .acts import ActCourier, options as act_options
from .attachment import AttachmentMonitor
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

_AUTO = object()
HEARTBEAT_EVERY_MS = 60_000


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
        self._params = Parameters()
        self._context = Context()
        self._log = DecisionLog(self.paths.data_dir)
        self._loaded = False
        self._thalamus = ThalamusState()
        self._extractor = Extractor()
        self._last_rowid = 0
        self._obs_seq = 0
        self._last_row = None
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
            self.spool, lambda command, args: commands.publish(command, args, "helper", paths=self.paths))
        if scorer is _AUTO:
            self.scorer, self._scorer_note = load_scorer()
        else:
            self.scorer = scorer
            self._scorer_note = None

    def tick(self, now):
        self.cursor.read_new()
        latest = self.spool.latest_record()
        observed = self.monitor.observe(now, self._mono(), self._process(), latest)
        self._state = observed["state"]
        self._telemetry_only = observed["telemetry_only"]
        self._advance_thalamus(now)
        if self.client is not None and (
            self._last_heartbeat_ms is None or now - self._last_heartbeat_ms >= HEARTBEAT_EVERY_MS
        ):
            body = {
                "v": 1,
                "helper_session": self.helper_session,
                "sent_at_ms": now,
                "attached": self._state == "attached",
            }
            probe = latest.get("probe_version") if isinstance(latest, dict) else None
            if isinstance(probe, str) and len(probe) <= 16:
                body["probe_version"] = probe
            result = self.client.post_heartbeat(body)
            self._last_heartbeat = {"kind": result.kind, "status": result.status}
            self._last_heartbeat_ms = now
        if self.client is not None:
            self.spool.flush(self.client, now)
        if self.client is not None and self._acts is not None and hasattr(self.client, "sync_acts"):
            self._acts.tick(self.client, self.helper_session, now, self._state == "attached")

    def _options(self, row):
        """8f: her options from the newest menu of this telemetry session, or none."""
        menu = self._menu
        if not isinstance(menu, dict) or not isinstance(row, dict) or menu.get("session") != row.get("telemetry_session_id"):
            return []
        if self._catalog is None:
            try:
                from .catalog import Catalog
                self._catalog = Catalog(self.paths)
            except Exception:
                self._catalog = False
        return act_options(menu.get("payload"), self._resolve_text, self._catalog or None)

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
            "transport": transport,
            "thalamus": self.thalamus_status(),
        }

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
            if kind == "act_menu" and isinstance(record.get("e2"), dict):
                self._menu = {"session": record.get("telemetry_session_id"), "payload": record["e2"]}
            elif kind == "act_event" and self._acts is not None:
                self._acts.on_row(record)
            percepts = self._extractor.step(record)
            written = record.get("wall_timestamp_ms") if isinstance(record, dict) else None
            clock_ms = written if type(written) is int and 0 <= written <= wall_ms else wall_ms
            self._thalamus, decision = decide(
                self._thalamus, percepts, clock_ms, self._params, self._context)
            self._theta = decision.theta
            self._last_row = record
            self._last_rowid = rowid
            seq = record.get("written_sequence") if isinstance(record, dict) else None
            self._on_decision(decision, percepts, wall_ms, clock_ms, seq if type(seq) is int else None)
        self._thalamus, decision = decide(
            self._thalamus, [], wall_ms, self._params, self._context)
        self._theta = decision.theta
        self._on_decision(decision, [], wall_ms, wall_ms, None)
        lineage = self._extractor.lineage_id
        self._thalamus = prune(self._thalamus, wall_ms, self._params, lineage)
        self._persist_thalamus()

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
            if decision.percepts and self._last_row is not None:
                obs = build(decision, {
                    "helper_session": self.helper_session,
                    "obs_seq": self._obs_seq,
                    "slot_id": self._extractor.slot_id,
                    "guid": self._extractor.guid,
                    "lineage_class": self._extractor.lineage_class,
                    "row": self._last_row,
                    "resolve_text": self._resolve_text,
                    "options": self._options(self._last_row),
                })
                scorer = run_scorer(self.scorer, json.loads(json.dumps(obs)))
                if self.client is not None and not self._telemetry_only:
                    try:
                        self.spool.enqueue_observation(obs, wall_ms)
                    except (ContractError, OutboxConflict) as exc:
                        scorer = {"error": "%s: %s" % (type(exc).__name__, exc)}
                    else:
                        enqueued = True
                        observation_id = obs["observation_id"]
                        self._obs_seq += 1
                        self._enqueued += 1
        self._log.write({
            "wall_ms": wall_ms,
            "clock_ms": clock_ms,
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

    def _persist_thalamus(self):
        self.spool.put_many_kv({
            "thalamus_state": json.dumps(self._thalamus.to_dict()),
            "extractor_state": json.dumps(self._extractor.to_dict()),
            "last_rowid": str(self._last_rowid),
            "obs_seq": str(self._obs_seq),
            "last_row": json.dumps(self._last_row),
            "act_menu": json.dumps(self._menu),
            "thalamus_fires": str(self._fires),
            "thalamus_enqueued": str(self._enqueued),
            "thalamus_last_reason": "" if self._last_fire_reason is None else self._last_fire_reason,
            "thalamus_last_wall_ms": "" if self._last_fire_wall_ms is None else str(self._last_fire_wall_ms),
            "thalamus_theta": str(self._theta),
        })


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
    archived_at = None
    game_seen_at = None
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


if __name__ == "__main__":
    raise SystemExit(main())
