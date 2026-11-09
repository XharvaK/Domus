"""D-2/D-3: only a different session with telemetry evidence strictly newer than the marker clears it, and a marker
that exists but cannot be read as a valid active marker stays fail-closed."""
import json
import os

import pytest

from conftest import opened, session_file
from domus_helper import commands


EVIL = bytes([7]) * 32


@pytest.fixture(autouse=True)
def _fresh_process(monkeypatch):
    monkeypatch.setattr(commands, "_PINNED_KEYS", {}, raising=False)
    monkeypatch.setattr(commands, "_FAIL_CLOSED", {}, raising=False)
    monkeypatch.setattr(commands, "_LATEST_SESSIONS", {}, raising=False)


def _marker_path(paths):
    return paths.data_dir / commands.KEY_FAIL_CLOSED_NAME


def _swap_between_sessions(paths):
    key_file = paths.telemetry / "cmd" / "key"
    os.replace(key_file, str(key_file) + ".old")
    key_file.write_text(EVIL.hex(), encoding="ascii")
    commands._PINNED_KEYS.clear()  # a new helper process starts with nothing pinned


def _fail_closed(paths):
    """Cause a mismatch with no telemetry readable, then return the marker it wrote."""
    commands.command_key(paths)
    _swap_between_sessions(paths)
    with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
        commands.publish("status", {}, "helper", paths=paths)
    marker = _marker_path(paths)
    return json.loads(marker.read_text(encoding="utf-8"))


def _row(session_id, wall_timestamp_ms):
    row = opened()
    row["telemetry_session_id"] = session_id
    row["wall_timestamp_ms"] = wall_timestamp_ms
    return row


def _write_rows(path, rows):
    path.write_bytes(b"".join(json.dumps(row).encode("utf-8") + b"\n" for row in rows))


@pytest.mark.parametrize("payload", [b"", b"{not json", b"[]", b'{"active": false}'])
def test_a_marker_that_exists_but_is_not_valid_still_fails_closed(paths, payload):
    marker = _marker_path(paths)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_bytes(payload)

    with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
        commands.publish("status", {}, "helper", paths=paths)

    assert marker.is_file()
    assert not list(paths.inbox.glob("*.json"))


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0,
                    reason="root can read a chmod 000 marker")
def test_an_unreadable_marker_still_fails_closed(paths):
    marker = _marker_path(paths)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({
        "v": 1, "active": True, "telemetry_session_id": "session-old", "wall_timestamp_ms": 1,
    }), encoding="utf-8")
    marker.chmod(0o000)
    try:
        with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
            commands.publish("status", {}, "helper", paths=paths)
    finally:
        marker.chmod(0o600)

    assert marker.is_file()
    assert not list(paths.inbox.glob("*.json"))


def test_a_corrupt_marker_is_not_cleared_by_a_newer_session(paths):
    marker = _marker_path(paths)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("{not json", encoding="utf-8")
    session_file(paths, [_row("session-new", 10 ** 15)])

    with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
        commands.publish("status", {}, "helper", paths=paths)

    assert marker.is_file()
    assert not list(paths.inbox.glob("*.json"))


def test_a_marker_without_a_recorded_session_never_treats_a_later_id_as_a_restart(paths):
    marker = _fail_closed(paths)
    assert marker["telemetry_session_id"] is None
    session_file(paths, [_row("session-new", 10 ** 15)])

    with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
        commands.publish("status", {}, "helper", paths=paths)

    assert _marker_path(paths).is_file()
    assert not list(paths.inbox.glob("*.json"))


def test_a_session_older_than_the_marker_does_not_clear_it(paths):
    marker = _fail_closed(paths)
    session_file(paths, [_row("session-new", marker["wall_timestamp_ms"] - 1)])

    with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
        commands.publish("status", {}, "helper", paths=paths)

    assert _marker_path(paths).is_file()
    assert not list(paths.inbox.glob("*.json"))


def test_a_different_session_older_than_the_marker_still_refuses(paths):
    commands.command_key(paths)
    commands.note_telemetry_session("session-old", wall_timestamp_ms=1_000, paths=paths)
    _swap_between_sessions(paths)
    with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
        commands.publish("status", {}, "helper", paths=paths)

    marker = json.loads(_marker_path(paths).read_text(encoding="utf-8"))
    assert marker["telemetry_session_id"] == "session-old"
    session_file(paths, [_row("session-new", marker["wall_timestamp_ms"] - 1)])

    with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
        commands.publish("status", {}, "helper", paths=paths)

    assert _marker_path(paths).is_file()
    assert not list(paths.inbox.glob("*.json"))


def test_the_same_session_with_a_newer_row_still_refuses(paths):
    commands.command_key(paths)
    commands.note_telemetry_session("session-old", wall_timestamp_ms=1_000, paths=paths)
    _swap_between_sessions(paths)
    with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
        commands.publish("status", {}, "helper", paths=paths)

    marker = json.loads(_marker_path(paths).read_text(encoding="utf-8"))
    session_file(paths, [_row("session-old", marker["wall_timestamp_ms"] + 1)])

    with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
        commands.publish("status", {}, "helper", paths=paths)

    assert _marker_path(paths).is_file()
    assert not list(paths.inbox.glob("*.json"))


def test_a_leftover_session_keeps_refusing_until_a_strictly_newer_session(paths):
    commands.command_key(paths)
    commands.note_telemetry_session("session-old", wall_timestamp_ms=1_000, paths=paths)
    _swap_between_sessions(paths)
    with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
        commands.publish("status", {}, "helper", paths=paths)

    marker = json.loads(_marker_path(paths).read_text(encoding="utf-8"))
    session = session_file(paths, [_row("session-new", marker["wall_timestamp_ms"] - 1)])
    with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
        commands.publish("status", {}, "helper", paths=paths)
    assert _marker_path(paths).is_file()

    _write_rows(session, [_row("session-newer", marker["wall_timestamp_ms"] + 1)])
    commands.publish("status", {}, "helper", paths=paths)

    assert not _marker_path(paths).exists()
    assert len(list(paths.inbox.glob("*.json"))) == 1


def test_note_telemetry_session_needs_a_strictly_newer_wall_timestamp(paths):
    commands.command_key(paths)
    commands.note_telemetry_session("session-old", wall_timestamp_ms=1_000, paths=paths)
    _swap_between_sessions(paths)
    with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
        commands.publish("status", {}, "helper", paths=paths)

    marker = json.loads(_marker_path(paths).read_text(encoding="utf-8"))
    too_early = marker["wall_timestamp_ms"] - 1
    assert commands.note_telemetry_session("session-new", wall_timestamp_ms=too_early, paths=paths) is False
    assert _marker_path(paths).is_file()

    just_late = marker["wall_timestamp_ms"] + 1
    assert commands.note_telemetry_session("session-new", wall_timestamp_ms=just_late, paths=paths) is True
    assert not _marker_path(paths).exists()
