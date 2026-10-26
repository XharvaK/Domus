"""Host paths; no game imports or filesystem writes."""
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SIMS_ROOT = r"C:\Users\Xharv\OneDrive\Belgeler\Electronic Arts\The Sims 4"
DEFAULT_GAME_ROOT = r"E:\SteamLibrary\steamapps\common\The Sims 4"
DEFAULT_DATA_DIR = r"E:\Domus"


@dataclass(frozen=True)
class Paths:
    sims_root: Path
    game_root: "Path | None" = None

    @classmethod
    def from_env(cls):
        game = os.environ.get("DOMUS_GAME_ROOT")
        return cls(Path(os.environ.get("DOMUS_SIMS_ROOT", DEFAULT_SIMS_ROOT)),
                   Path(game) if game else None)

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

    @property
    def atlas_dir(self):
        return self.telemetry / "atlas"

    @property
    def data_dir(self):
        """D49 (2026-10-05): not under AppData. A packaged app (the Claude desktop
        app) has its writes to AppData redirected into its own package folder, so a
        helper started from it and one started by the daily task or a terminal saw two
        different data folders. On the User's machine it lives on E: (the User's
        choice; C: is nearly full)."""
        configured = os.environ.get("DOMUS_DATA_DIR")
        if configured:
            return Path(configured)
        return Path(DEFAULT_DATA_DIR)

    @property
    def atlas_db(self):
        return self.data_dir / "atlas.db"

    def check_inbox(self):
        # Reject redirected directories: publication must stay inside cmd/inbox.
        expected = self.sims_root.resolve() / "AshleyE1Telemetry" / "cmd" / "inbox"
        if self.inbox.resolve() != expected:
            raise ValueError("inbox must not be redirected by a symlink")
