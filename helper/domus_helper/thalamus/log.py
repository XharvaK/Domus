"""Append-only decision log with a byte quota. Never deletes today's file."""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from domus_helper.thalamus.parameters import DECISION_LOG_QUOTA_BYTES


class DecisionLog:
    def __init__(self, data_dir, quota=DECISION_LOG_QUOTA_BYTES):
        self.dir = Path(data_dir) / "thalamus"
        self.quota = quota
        self._lock = threading.Lock()

    def write(self, record):
        # HELPER2-9: the tick and the list post thread both write; a write and its trim run under one lock.
        with self._lock:
            self.dir.mkdir(parents=True, exist_ok=True)
            wall_ms = int(record["wall_ms"])
            day = datetime.fromtimestamp(wall_ms / 1000.0, timezone.utc).strftime("%Y%m%d")
            path = self.dir / ("decisions-%s.jsonl" % day)
            line = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            self._trim(day)

    def _trim(self, today):
        while self._total() > self.quota:
            oldest = self._oldest_other(today)
            if oldest is None:
                return
            oldest.unlink()

    def _oldest_other(self, today):
        found = []
        for path in self.dir.glob("decisions-*.jsonl"):
            stamp = path.name[len("decisions-"):-len(".jsonl")]
            if stamp == today or not path.is_file():
                continue
            found.append((stamp, path))
        if not found:
            return None
        found.sort()
        return found[0][1]

    def _total(self):
        return sum(path.stat().st_size for path in self.dir.glob("decisions-*.jsonl") if path.is_file())
