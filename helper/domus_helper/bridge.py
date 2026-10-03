"""Helper bridge: spool telemetry, heartbeat, and flush the observation outbox."""
import argparse
import time
import uuid

from . import fingerprints as fingerprint_reader
from .attachment import AttachmentMonitor
from .cursor import TelemetryCursor
from .paths import Paths
from .spool import Spool
from .transport import AshleyClient, load_credentials

_AUTO = object()
HEARTBEAT_EVERY_MS = 60_000


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

    def tick(self, now):
        self.cursor.read_new()
        latest = self.spool.latest_record()
        observed = self.monitor.observe(now, self._mono(), self._process(), latest)
        self._state = observed["state"]
        self._telemetry_only = observed["telemetry_only"]
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
        }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m domus_helper.bridge")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float)
    args = parser.parse_args(argv)
    bridge = Bridge()
    if args.once:
        bridge.tick(int(time.time() * 1000))
        return 0
    if args.interval is None:
        parser.error("pass --once or --interval")
    while True:
        try:
            bridge.tick(int(time.time() * 1000))
            time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
