"""Atomic command publication and id-matched replies over local files."""
import hashlib
import json
import math
import os
import secrets
import stat
import sys
import time
import uuid
from dataclasses import dataclass

from . import telemetry as telemetry_reader
from .paths import Paths
from .vendor import cmdbox, schema


class InboxNotAnswering(TimeoutError):
    pass


class EnvelopeInvalid(ValueError):
    """The envelope is not one the probe accepts (its cmdbox refusal, or a ttl out of range): HELPER2-8, the only
    ValueError from publishing that is her act's ARGS_INVALID."""
    pass


class CommandKeyFailClosed(ValueError):
    """AU NB-1: cmd/key was swapped between sessions and replaced; the running game may still hold the old key, so a
    command signed under the fresh key would only be refused BAD_MAC. The game must be restarted first."""
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


_PINNED_KEYS = {}
_FAIL_CLOSED = {}
_LATEST_SESSIONS = {}
KEY_FINGERPRINT_NAME = "cmd_key.sha256"
KEY_FAIL_CLOSED_NAME = "cmd_key.fail_closed"
_MARKER_MAX_BYTES = 4096
_CORRUPT_MARKER = {"active": True, "corrupt": True}
_FAIL_CLOSED_MESSAGE = (
    "DOMUS_KEY_FAIL_CLOSED (DOMUS_KEY_MISMATCH): cmd/key changed between sessions and was replaced; the running "
    "game may still hold the old key. You must restart the game, then the helper, before commands can be issued.")


def _fingerprint(key):
    return hashlib.sha256(key.hex().encode("ascii")).hexdigest()


def _key_file(paths):
    return str(paths.telemetry / "cmd" / "key")


def _fail_closed_file(paths):
    return paths.data_dir / KEY_FAIL_CLOSED_NAME


def _session_id(value):
    """A telemetry_session_id the committed schema would accept (vendor/schema.py validates it as a string id)."""
    if not isinstance(value, str) or not value or len(value) > schema.MAX_ID_LENGTH:
        return None
    return value


def _read_fail_closed(paths):
    """D-1/D-3: the fail-closed marker on disk. Disk is authoritative across helper processes; only a missing marker
    returns None. A file that exists but is unreadable, empty, malformed, too large, or not an active marker still
    fails closed: it is reported as a corrupt marker, which carries no session evidence and can never be cleared."""
    path = _fail_closed_file(paths)
    try:
        os.lstat(path)  # a dangling link still occupies the marker name, so it still fails closed
    except FileNotFoundError:
        return None
    except OSError:
        return _CORRUPT_MARKER
    try:
        raw = path.read_bytes()
    except OSError:
        return _CORRUPT_MARKER
    if not raw or len(raw) > _MARKER_MAX_BYTES:
        return _CORRUPT_MARKER
    try:
        marker = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError, RecursionError):
        return _CORRUPT_MARKER
    if not isinstance(marker, dict) or marker.get("active") is not True:
        return _CORRUPT_MARKER
    return marker


def _write_fail_closed(paths, session_id):
    """D-1/D-2: record fail-closed beside the key fingerprint, fsynced before the key is replaced. The marker names
    the telemetry session seen at the mismatch, when known, so only a different session with a row strictly newer
    than this marker can clear it."""
    marker = {
        "v": 1,
        "active": True,
        "telemetry_session_id": _session_id(session_id),
        "wall_timestamp_ms": int(time.time() * 1000),
    }
    path = _fail_closed_file(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    # D-3: a unique temporary per writer, so two helpers writing the marker cannot truncate or replace each other's
    # temporary file before it reaches the final name.
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(json.dumps(marker, ensure_ascii=True, separators=(",", ":")).encode("utf-8") + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass
    _FAIL_CLOSED[_key_file(paths)] = marker
    return marker


def _clear_fail_closed(paths):
    try:
        _fail_closed_file(paths).unlink()
    except FileNotFoundError:
        pass
    except OSError:
        return False  # the marker is still on disk, so the state is still fail-closed
    _FAIL_CLOSED.pop(_key_file(paths), None)
    return True


def _latest_telemetry_session(paths):
    """D-1/D-2: the newest game session on the telemetry path the bridge already follows, as (session id, wall
    timestamp) from the row that carried the id, or None. The probe writes telemetry_session_id and
    wall_timestamp_ms on each row (session_open and later); rows are schema-validated before they are used."""
    try:
        session = telemetry_reader.latest_session(paths=paths)
        for index, row in enumerate(telemetry_reader.file_rows(session)):
            value = _session_id(row.get("telemetry_session_id"))
            if value is not None:
                return value, row.get("wall_timestamp_ms")
            if index >= 20:
                break
    except (OSError, ValueError, UnicodeError, RecursionError):
        return None
    return None


def _latest_session_evidence(paths):
    """D-2: telemetry's newest session evidence, with the bridge's last reported row as a fallback when no telemetry
    row is readable. Both carry the row's wall timestamp, which must be strictly newer than the marker to clear it."""
    evidence = _latest_telemetry_session(paths)
    if evidence is not None:
        return evidence
    return _LATEST_SESSIONS.get(_key_file(paths))


def _is_new_session(marker, session_id, wall_timestamp_ms=None):
    """D-1/D-2: only a session different from the one held at the mismatch, with a row strictly newer than the marker,
    is a new game. A corrupt marker, or one that holds no session id, never clears: without the old id, a later row
    could still be a leftover from the old game."""
    if marker.get("corrupt") is True:
        return False
    recorded = _session_id(marker.get("telemetry_session_id"))
    if recorded is None or recorded == session_id:
        return False
    recorded_wall = marker.get("wall_timestamp_ms")
    if type(recorded_wall) is not int or type(wall_timestamp_ms) is not int:
        return False
    return wall_timestamp_ms > recorded_wall


def note_telemetry_session(session_id, *, wall_timestamp_ms=None, paths=None):
    """D-1/D-2: the bridge reports the telemetry_session_id and wall timestamp of a row it just saw. If a fail-closed
    marker is active and this is a different session with evidence strictly newer than the marker, the marker is
    cleared. Returns True when cleared. While no new session is seen, the marker stays and commands keep refusing."""
    paths = paths or Paths.from_env()
    session_id = _session_id(session_id)
    if session_id is None:
        return False
    _LATEST_SESSIONS[_key_file(paths)] = (session_id, wall_timestamp_ms)
    marker = _read_fail_closed(paths)
    if marker is None:
        _FAIL_CLOSED.pop(_key_file(paths), None)
        return False
    if not _is_new_session(marker, session_id, wall_timestamp_ms):
        return False
    return _clear_fail_closed(paths)


def _clear_if_new_session(paths):
    """D-1/D-2: before refusing (or reading the key), look for a newer session on the telemetry path the helper
    already uses. This lets the original helper clear itself once the game restarts, without waiting for a bridge
    row hook, but only when the session differs and its row is strictly newer than the marker."""
    if _read_fail_closed(paths) is None:
        _FAIL_CLOSED.pop(_key_file(paths), None)
        return False
    evidence = _latest_session_evidence(paths)
    if evidence is None:
        return False
    session_id, wall_timestamp_ms = evidence
    return note_telemetry_session(session_id, wall_timestamp_ms=wall_timestamp_ms, paths=paths)


def _create_key(key_file):
    """A fresh key by an exclusive create, owner-only; False when the file is already there."""
    try:
        descriptor = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(secrets.token_hex(cmdbox.MAC_KEY_BYTES).encode("ascii"))
        handle.flush()
        os.fsync(handle.fileno())
    return True


def _read_key(key_file):
    if not stat.S_ISREG(os.lstat(key_file).st_mode):
        raise ValueError("cmd/key is not a regular file")
    key = cmdbox.parse_key(_reply_bytes(key_file, cmdbox.MAC_KEY_FILE_MAX))  # bounded, never blocks (F6)
    if key is None:
        raise ValueError("cmd/key is not a command key")
    return key


def _write_fingerprint(path, key):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(_fingerprint(key).encode("ascii") + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def command_key(paths):
    """OPENVULN F1/F8: the shared command key in cmd/key. Made once, owner-only (0600), by an exclusive create, so two
    helpers starting together agree on one key. The probe only reads it.
    AU NB-3: the first key read is pinned for the life of this process, so a later swap of the file by a cmd/ writer
    is not believed; a key file that is a link or not a regular file is refused.
    AU recheck NB-3: the helper keeps the SHA-256 of the key it made in its own data folder, outside cmd/. At the first
    read of each helper process, a cmd/key that does not match (swapped between sessions) is refused with the error
    code DOMUS_KEY_MISMATCH, replaced by a fresh key, and the fingerprint updated. With no fingerprint yet (a helper
    from before this change), the key found is adopted and its fingerprint recorded.
    AU NB-1: the game may have started after the swap and pinned the swapped key for its whole session, so the helper
    also enters a fail-closed state: it refuses to issue commands until the game is restarted.
    D-1: the fail-closed state is written to paths.data_dir beside the fingerprint, so another helper process still
    refuses; it is cleared only when telemetry shows a new game session (note_telemetry_session)."""
    key_file = paths.telemetry / "cmd" / "key"
    _clear_if_new_session(paths)
    pinned = _PINNED_KEYS.get(str(key_file))
    if pinned is not None:
        return pinned
    fingerprint_file = paths.data_dir / KEY_FINGERPRINT_NAME
    created = _create_key(key_file)
    key = _read_key(key_file)
    try:
        recorded = fingerprint_file.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        recorded = None
    if not created and recorded is not None and recorded != _fingerprint(key):
        evidence = _latest_session_evidence(paths)
        _write_fail_closed(paths, evidence[0] if evidence is not None else None)
        print("DOMUS_KEY_MISMATCH: cmd/key is not the key this helper made (changed between sessions); refusing it "
              "and writing a fresh key. You must restart the game, then the helper, before commands can be issued; "
              "the running game may still hold the old key.", file=sys.stderr, flush=True)
        os.remove(key_file)
        if not _create_key(key_file):
            raise ValueError("cmd/key could not be replaced")
        key = _read_key(key_file)
        recorded = None
    if recorded != _fingerprint(key):
        _write_fingerprint(fingerprint_file, key)
    _PINNED_KEYS[str(key_file)] = key
    return key


def _is_fail_closed(paths):
    """D-1: the on-disk marker is authoritative, so a restarted process still refuses; module memory is only a cache."""
    marker = _read_fail_closed(paths)
    if marker is None:
        _FAIL_CLOSED.pop(_key_file(paths), None)
        return False
    _FAIL_CLOSED[_key_file(paths)] = marker
    return True


def _refuse_when_fail_closed(paths):
    """AU NB-1: after a between-sessions mismatch the running game may still hold the swapped key, so no command may
    be signed and written under the fresh one. The game must be restarted first. D-1: a telemetry session newer than
    the one recorded in the marker is evidence of that restart and clears it."""
    _clear_if_new_session(paths)
    if _is_fail_closed(paths):
        raise CommandKeyFailClosed(_FAIL_CLOSED_MESSAGE)


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
    _refuse_when_fail_closed(paths)
    paths.check_inbox()
    key = command_key(paths)
    _refuse_when_fail_closed(paths)  # command_key itself may have just entered fail-closed on a mismatch
    row, raw = signed(row, key)
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
    reads the file later refuses it EXPIRED (an act is then refused to her as EXPIRED too). Returns the ids cancelled.
    AU NB-1: while fail-closed this refuses: rewriting an inbox command would sign it under the fresh key."""
    _refuse_when_fail_closed(paths)
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
            if _is_fail_closed(paths):
                try:
                    os.replace(claimed, entry)  # put the claimed command back before refusing
                except OSError:
                    pass
                _refuse_when_fail_closed(paths)  # raises: the game must be restarted
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


def _reply_bytes(path, limit=REPLY_MAX_BYTES):
    """The reply file's bytes, or None while there is no reply to read: missing, or larger than `limit` (read no
    further than the cap, so a planted huge file never fills memory)."""
    # OPENVULN F5: anything but a readable regular file (a folder, a device, no access) is no reply yet, never a crash.
    # OPENVULN F6: opened without blocking, so a named pipe (or other special file) planted there returns at once
    # instead of holding the poll past its deadline.
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return None
    try:
        with os.fdopen(descriptor, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                return None
            raw = handle.read(limit + 1)
    except OSError:
        return None
    return None if len(raw) > limit else raw


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
