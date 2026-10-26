"""Incremental telemetry reader. Offsets persist in the spool."""
import json

from .telemetry import latest_session, segments

# W12 (F2): one tick reads at most this many lines, and no more than this many bytes of a segment at a time. A segment
# is at most 8 MiB (the probe's writer rolls it), so one read always holds a whole line and the cursor never stalls.
LINES_PER_TICK = 500
CHUNK_BYTES = 8 * 1024 * 1024


def _segment_index(session, path):
    if path.name == session.name:
        return 0
    return int(path.name[len(session.name) + 1:])


def _complete_lines(path, offset, max_lines=LINES_PER_TICK):
    size = path.stat().st_size
    if offset > size:
        offset = 0
    with path.open("rb") as handle:
        handle.seek(offset)
        data = handle.read(CHUNK_BYTES)
    end = data.rfind(b"\n")
    if end < 0:
        return offset, []
    chunk = data[:end + 1]
    lines = []
    pos = offset
    for raw in chunk.splitlines(keepends=True)[:max_lines]:
        lines.append((pos, raw))
        pos += len(raw)
    return pos, lines


class TelemetryCursor:
    def __init__(self, spool, paths):
        self.spool = spool
        self.paths = paths
        # The newest telemetry file: its records are the running game's. The bridge follows this file's session, so a
        # previous session's rows (the last ones in the spool) are not taken for it at start.
        self.newest = None

    def read_new(self):
        """The new rows of the newest session, at most LINES_PER_TICK lines a tick; the batch is one commit (W12 F2)."""
        try:
            session = latest_session(paths=self.paths)
        except FileNotFoundError:
            self.newest = None
            return []
        self.newest = session.name
        found = []
        entries = []
        key = session.name
        budget = LINES_PER_TICK
        for path in segments(session):
            if budget <= 0:
                break
            if not path.is_file():
                continue
            segment = _segment_index(session, path)
            offset = self.spool.cursor_offset(key, segment)
            _new_offset, lines = _complete_lines(path, offset, budget)
            budget -= len(lines)
            for line_offset, raw in lines:
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError:
                    record = None
                if isinstance(record, dict):
                    found.append(record)
                    entries.append((segment, line_offset, record, len(raw)))
                else:
                    entries.append((segment, line_offset, None, len(raw)))
        if entries:
            self.spool.ingest_batch(key, entries)
        return found
