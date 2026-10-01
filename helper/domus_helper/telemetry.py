"""Read-only schema-v3 telemetry access."""
import json
import re
from pathlib import Path

from .paths import Paths
from .vendor.schema import validate_record

SESSION_NAME = re.compile(r"ashley_e1_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jsonl\Z")


def latest_session(*, paths=None):
    paths = paths or Paths.from_env()
    candidates = [p for p in paths.telemetry.glob("ashley_e1_*.jsonl")
                  if SESSION_NAME.fullmatch(p.name) and p.is_file()]
    if not candidates:
        raise FileNotFoundError("no session telemetry")
    return max(candidates, key=lambda p: (p.stat().st_mtime_ns, p.name))


def segments(session):
    """The probe rotates to <session>.jsonl.1, .2, ... ."""
    session = Path(session)
    rotated = [p for p in session.parent.glob(session.name + ".*")
               if p.name[len(session.name) + 1:].isdigit()]
    return [session] + sorted(rotated, key=lambda p: int(p.name[len(session.name) + 1:]))


def rows(session):
    for segment in segments(session):
        yield from file_rows(segment)


def file_rows(session):
    with Path(session).open("rb") as handle:
        for raw in handle:
            # An active writer may have left a partial final row. Never infer it.
            if not raw.endswith(b"\n"):
                break
            yield validate_record(json.loads(raw))


def tail(kinds, n, *, paths=None, session=None):
    if type(n) is not int or not 1 <= n <= 10000:
        raise ValueError("n must be between 1 and 10000")
    from .vendor.schema import EVENT_KINDS
    if not isinstance(kinds, (list, tuple)) or any(k not in EVENT_KINDS for k in kinds):
        raise ValueError("unknown telemetry kinds")
    from collections import deque
    return list(deque((r for r in rows(session or latest_session(paths=paths))
                       if not kinds or r["event_kind"] in kinds), maxlen=n))


def lineage(*, paths=None):
    paths = paths or Paths.from_env()
    with paths.ledger.open("rb") as handle:
        return [json.loads(raw) for raw in handle if raw.endswith(b"\n")]
