"""Atomic command publication and id-matched replies over local files."""
import json
import math
import os
import secrets
import stat
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


def command_key(paths):
    """OPENVULN F1/F8: the shared command key in cmd/key. Made once, owner-only (0600), by an exclusive create, so two
    helpers starting together agree on one key. The probe only reads it."""
    key_file = paths.telemetry / "cmd" / "key"
    try:
        descriptor = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(secrets.token_hex(cmdbox.MAC_KEY_BYTES).encode("ascii"))
            handle.flush()
            os.fsync(handle.fileno())
    with open(key_file, "rb") as handle:
        key = cmdbox.parse_key(handle.read(cmdbox.MAC_KEY_FILE_MAX + 1))
    if key is None:
        raise ValueError("cmd/key is not a command key")
    return key


def signed(row, key):
    """The envelope as published: the row with its MAC, serialized."""
    row = dict(row, mac=cmdbox.mac(key, row))
    return row, json.dumps(row, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


def publish(command, args, issuer, *, paths=None):
    """Write one command to the probe's inbox and return its id without waiting (8f: the
    bridge reads what happened from the telemetry, never blocks its tick on a reply)."""
    row, raw = envelope(command, args, issuer)
    _write(row, raw, paths or Paths.from_env())
    return row["id"]


def _write(row, raw, paths):
    paths.check_inbox()
    row, raw = signed(row, command_key(paths))
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
        # Audit N-1: claim the file by an atomic rename first. The probe takes a command the same way, so exactly one
        # side owns it; if the probe got there first the claim fails and the command is left alone.
        claimed = entry.with_name(entry.name + ".cancel")
        try:
            os.replace(entry, claimed)
        except OSError:
            continue
        row = None
        try:
            raw = claimed.read_bytes()
            row, _error = cmdbox.parse(raw, now_ms, ())
        except (OSError, ValueError, UnicodeError, RecursionError):
            row = None
        if row is not None:
            try:
                key = command_key(paths)
            except (OSError, ValueError):
                key = None
            # Only a command we signed is re-signed: one another writer left is never laundered into a signed one.
            if key is None or not cmdbox.mac_ok(key, row):
                row = None  # back untouched; the probe refuses it BAD_MAC
            else:
                row["expires_at_ms"] = min(row["issued_at_ms"], now_ms) - 1
                row, expired = signed(row, key)
        if row is not None:
            temporary = entry.with_name(entry.name + ".tmp")
            try:
                temporary.write_bytes(expired)
                os.replace(temporary, claimed)
            except OSError:
                row = None
                try:
                    temporary.unlink()
                except OSError:
                    pass
        try:
            os.replace(claimed, entry)  # back in the inbox: expired, or untouched when it could not be rewritten
        except OSError:
            continue
        if row is None:
            continue
        cancelled.append(row["id"])
    return cancelled


# OPENVULN F4: the largest reply file the poll reads. A probe reply is a few kilobytes; a larger file is not one.
REPLY_MAX_BYTES = 8 * 1024 * 1024


def _reply_bytes(path):
    """The reply file's bytes, or None while there is no reply to read: missing, or larger than REPLY_MAX_BYTES (read
    no further than the cap, so a planted huge file never fills memory)."""
    # OPENVULN F5: anything but a readable regular file (a folder, a device, no access) is no reply yet, never a crash.
    try:
        with open(path, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                return None
            raw = handle.read(REPLY_MAX_BYTES + 1)
    except OSError:
        return None
    return None if len(raw) > REPLY_MAX_BYTES else raw


def _authentic(payload, paths):
    """OPENVULN F8: a reply is the probe's only when its MAC checks under cmd/key; anything else reads as no reply."""
    try:
        return cmdbox.mac_ok(command_key(paths), payload)
    except (OSError, ValueError):
        return False


def read_reply(command_id, *, paths=None):
    """W12 (B3): the probe's reply to one command of ours, or None while it has not answered. Id-matched and checked
    for shape; a reply the probe is still writing reads as not yet."""
    paths = paths or Paths.from_env()
    try:
        raw = _reply_bytes(paths.outbox / (command_id + ".json"))
        payload = None if raw is None else cmdbox.decode(raw)
    except (ValueError, UnicodeError, RecursionError):
        return None
    if not isinstance(payload, dict) or payload.get("id") != command_id:
        return None
    if not _authentic(payload, paths):
        return None
    payload = dict((name, value) for name, value in payload.items() if name != "mac")
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
        raw = _reply_bytes(reply_path)
        try:
            payload = None if raw is None else cmdbox.decode(raw)
        except (ValueError, UnicodeError, RecursionError):
            payload = None
        if isinstance(payload, dict) and payload.get("id") == row["id"] and _authentic(payload, paths):
            payload = dict((name, value) for name, value in payload.items() if name != "mac")
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
