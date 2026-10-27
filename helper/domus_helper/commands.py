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


class EnvelopeInvalid(ValueError):
    """The envelope is not one the probe accepts (its cmdbox refusal, or a ttl out of range): HELPER2-8, the only
    ValueError from publishing that is her act's ARGS_INVALID."""
    pass


@dataclass(frozen=True)
class Reply:
    id: str
    status: str
    code: str | None
    result: dict
    issuer: str | None


def envelope(command, args, issuer, ttl_ms=30_000):
    if not 1_000 <= ttl_ms <= 60_000:
        raise EnvelopeInvalid("ttl_ms must be from 1000 to 60000")
    now = time.time_ns() // 1_000_000
    row = dict(v=1, id=uuid.uuid4().hex, issued_at_ms=now,
               expires_at_ms=now + ttl_ms, issuer=issuer, command=command, args=args)
    raw = json.dumps(row, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    _, error = cmdbox.parse(raw, now, ())
    if error:
        raise EnvelopeInvalid(error)
    return row, raw


def publish(command, args, issuer, *, paths=None):
    """Write one command to the probe's inbox and return its id without waiting (8f: the
    bridge reads what happened from the telemetry, never blocks its tick on a reply)."""
    row, raw = envelope(command, args, issuer)
    _write(row, raw, paths or Paths.from_env())
    return row["id"]


def _write(row, raw, paths):
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


# W12 (F6): a finished command's file (cmd/done) is kept for this long, then it may go.
DONE_KEEP_MS = 7 * 24 * 3600 * 1000


def prune_done(paths, now_ms):
    """W12 (F6): the probe's finished-command files (cmd/done) older than seven days are removed, one named file at a
    time, through a path this function builds for each one. The probe checks a command's id against done/ only for a
    command that can still arrive (its time to live is a minute at most), so a file this old answers no live question.
    Returns the names removed. Never raises on a file it cannot remove."""
    folder = paths.done
    if not folder.is_dir():
        return []
    cutoff_ms = now_ms - DONE_KEEP_MS
    removed = []
    for entry in sorted(folder.iterdir()):
        if entry.suffix != ".json" or not entry.is_file():
            continue
        try:
            modified_ms = entry.stat().st_mtime * 1000
        except OSError:
            continue
        if modified_ms >= cutoff_ms:
            continue
        try:
            entry.unlink()
        except OSError:
            continue
        removed.append(entry.name)
    return removed


def expire_pending(paths, now_ms=None):
    """R4/L4: cancel every command the probe has not taken yet, through cmdbox's own expiry path, so a probe that
    reads the file later refuses it EXPIRED (an act is then refused to her as EXPIRED too). Returns the ids cancelled."""
    now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    cancelled = []
    for entry in sorted(paths.inbox.glob("*.json")):
        try:
            raw = entry.read_bytes()
        except OSError:
            continue
        try:
            row, _error = cmdbox.parse(raw, now_ms, ())
        except (ValueError, UnicodeError, RecursionError):
            continue
        if row is None:
            continue
        row["expires_at_ms"] = min(row["issued_at_ms"], now_ms) - 1
        raw = json.dumps(row, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        temporary = entry.with_name(entry.name + ".tmp")
        try:
            temporary.write_bytes(raw)
            os.replace(temporary, entry)
        except OSError:
            try:
                temporary.unlink()
            except OSError:
                pass
            continue
        cancelled.append(row["id"])
    return cancelled


def read_reply(command_id, *, paths=None):
    """W12 (B3): the probe's reply to one command of ours, or None while it has not answered. Id-matched and checked
    for shape; a reply the probe is still writing reads as not yet."""
    paths = paths or Paths.from_env()
    try:
        payload = cmdbox.decode((paths.outbox / (command_id + ".json")).read_bytes())
    except (FileNotFoundError, ValueError, UnicodeError, RecursionError):
        return None
    if not isinstance(payload, dict) or payload.get("id") != command_id:
        return None
    if payload.get("status") not in ("OK", "REJECTED", "ERROR") or not isinstance(payload.get("result"), dict):
        return None
    return payload


def send(command, args, issuer, timeout_s=15, *, paths=None):
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError("timeout_s must be positive and finite")
    ttl_ms = min(60_000, max(1_000, int(timeout_s * 1000)))
    row, raw = envelope(command, args, issuer, ttl_ms=ttl_ms)
    paths = paths or Paths.from_env()
    _write(row, raw, paths)
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
