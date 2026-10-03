"""Incremental telemetry reader. Offsets persist in the spool."""
import json

from .telemetry import latest_session, segments


def _segment_index(session, path):
    if path.name == session.name:
        return 0
    return int(path.name[len(session.name) + 1:])


def _complete_lines(path, offset):
    size = path.stat().st_size
    if offset > size:
        offset = 0
    with path.open("rb") as handle:
        handle.seek(offset)
        data = handle.read()
    end = data.rfind(b"\n")
    if end < 0:
        return offset, []
    chunk = data[:end + 1]
    lines = []
    pos = offset
    for raw in chunk.splitlines(keepends=True):
        lines.append((pos, raw))
        pos += len(raw)
    return pos, lines


class TelemetryCursor:
    def __init__(self, spool, paths):
        self.spool = spool
        self.paths = paths

    def read_new(self):
        try:
            session = latest_session(paths=self.paths)
        except FileNotFoundError:
            return []
        found = []
        key = session.name
        for path in segments(session):
            if not path.is_file():
                continue
            segment = _segment_index(session, path)
            offset = self.spool.cursor_offset(key, segment)
            new_offset, lines = _complete_lines(path, offset)
            for line_offset, raw in lines:
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError:
                    record = None
                if isinstance(record, dict):
                    found.append(record)
                    self.spool.ingest(key, segment, line_offset, record, raw_len=len(raw))
                else:
                    self.spool.note_cursor(key, segment, line_offset + len(raw))
        return found
