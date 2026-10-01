"""Atomic command publication and id-matched replies over local files."""
import json
import math
import os
import time
import uuid
from dataclasses import dataclass

from .paths import Paths
from .vendor import cmdbox


class InboxNotAnswering(TimeoutError):
    pass


@dataclass(frozen=True)
class Reply:
    id: str
    status: str
    code: str | None
    result: dict
    issuer: str | None


def envelope(command, args, issuer):
    now = time.time_ns() // 1_000_000
    row = dict(v=1, id=uuid.uuid4().hex, issued_at_ms=now,
               expires_at_ms=now + 30_000, issuer=issuer, command=command, args=args)
    raw = json.dumps(row, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    _, error = cmdbox.parse(raw, now, ())
    if error:
        raise ValueError(error)
    return row, raw


def send(command, args, issuer, timeout_s=15, *, paths=None):
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError("timeout_s must be positive and finite")
    row, raw = envelope(command, args, issuer)
    paths = paths or Paths.from_env()
    paths.check_inbox()
    # Do not bootstrap cmd directories: the probe/Owner owns their creation.
    temporary = paths.inbox / (row["id"] + ".json.tmp")
    destination = paths.inbox / (row["id"] + ".json")
    if destination.exists():
        raise FileExistsError(destination)
    created = False
    try:
        with temporary.open("xb") as handle:
            created = True
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        # This is the only file we may remove, and only if publication failed.
        if created and temporary.exists():
            temporary.unlink()
    deadline = time.monotonic() + timeout_s
    reply_path = paths.outbox / (row["id"] + ".json")
    while True:
        try:
            payload = cmdbox.decode(reply_path.read_bytes())
        except FileNotFoundError:
            payload = None
        if isinstance(payload, dict) and payload.get("id") == row["id"]:
            if (set(payload) != {"id", "status", "code", "result", "issuer"}
                    or payload["status"] not in ("OK", "REJECTED", "ERROR")
                    or not isinstance(payload["result"], dict)
                    or payload["issuer"] != issuer
                    or (payload["code"] is not None and not isinstance(payload["code"], str))):
                raise ValueError("invalid reply")
            return Reply(**payload)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise InboxNotAnswering(
                "type ashley_e1.inbox in the game console once (D11 pending)")
        time.sleep(min(0.25, remaining))
