"""Read-only schema-v3 telemetry access."""
import json
import os
import re
import stat
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


def raw_rows(path):
    """Complete lines decoded as JSON, without schema validation.

    Replays of committed evidence predate the schema `file_rows` enforces.
    A partial trailing line is ignored, same as `file_rows`.
    """
    with Path(path).open("rb") as handle:
        for raw in handle:
            if not raw.endswith(b"\n"):
                break
            yield json.loads(raw)


def tail(kinds, n, *, paths=None, session=None):
    if type(n) is not int or not 1 <= n <= 10000:
        raise ValueError("n must be between 1 and 10000")
    from .vendor.schema import EVENT_KINDS
    if not isinstance(kinds, (list, tuple)) or any(k not in EVENT_KINDS for k in kinds):
        raise ValueError("unknown telemetry kinds")
    from collections import deque
    return list(deque((r for r in rows(session or latest_session(paths=paths))
                       if not kinds or r["event_kind"] in kinds), maxlen=n))


# OPENVULN F9: the probe's writer never lets the ledger pass 2 MiB (writer.MAX_LEDGER_BYTES); a larger file is not its.
LEDGER_MAX_BYTES = 2 * 1024 * 1024


def _ledger_bytes(path):
    """The ledger's bytes, read no further than LEDGER_MAX_BYTES, from a regular file opened without blocking.
    Raises ValueError for a ledger larger than the cap (fail closed: nothing is returned from it)."""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("the lineage ledger is not a regular file")
        raw = handle.read(LEDGER_MAX_BYTES + 1)
    if len(raw) > LEDGER_MAX_BYTES:
        raise ValueError("the lineage ledger is larger than 2 MiB, so it is not read")
    return raw


def lineage(*, paths=None):
    paths = paths or Paths.from_env()
    raw = _ledger_bytes(paths.ledger)
    lines = raw.split(b"\n")[:-1]  # a partial trailing line is ignored, as before
    return [json.loads(line) for line in lines]
