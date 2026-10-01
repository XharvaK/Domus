"""Host paths; no game imports or filesystem writes."""
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SIMS_ROOT = r"C:\Users\Xharv\OneDrive\Belgeler\Electronic Arts\The Sims 4"


@dataclass(frozen=True)
class Paths:
    sims_root: Path

    @classmethod
    def from_env(cls):
        return cls(Path(os.environ.get("DOMUS_SIMS_ROOT", DEFAULT_SIMS_ROOT)))

    @property
    def telemetry(self):
        return self.sims_root / "AshleyE1Telemetry"

    @property
    def inbox(self):
        return self.telemetry / "cmd" / "inbox"

    @property
    def outbox(self):
        return self.telemetry / "cmd" / "outbox"

    @property
    def done(self):
        return self.telemetry / "cmd" / "done"

    @property
    def ledger(self):
        return self.telemetry / "ashley_e2_lineage_ledger.jsonl"

    def check_inbox(self):
        # Reject redirected directories: publication must stay inside cmd/inbox.
        expected = self.sims_root.resolve() / "AshleyE1Telemetry" / "cmd" / "inbox"
        if self.inbox.resolve() != expected:
            raise ValueError("inbox must not be redirected by a symlink")
