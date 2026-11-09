"""AU NB-1: a cmd/key swapped between sessions while a live probe may already have pinned it must leave the helper
fail-closed: it refuses the swapped key, replaces it for the next game start, and issues no commands until a restart."""
import hashlib
import os

import pytest

from domus_helper import commands


EVIL = bytes([7]) * 32


@pytest.fixture(autouse=True)
def _fresh_process(monkeypatch):
    monkeypatch.setattr(commands, "_PINNED_KEYS", {}, raising=False)
    monkeypatch.setattr(commands, "_FAIL_CLOSED", {}, raising=False)


def _fingerprint(key):
    return hashlib.sha256(key.hex().encode("ascii")).hexdigest()


def _swap_between_sessions(paths):
    key_file = paths.telemetry / "cmd" / "key"
    os.replace(key_file, str(key_file) + ".old")
    key_file.write_text(EVIL.hex(), encoding="ascii")
    commands._PINNED_KEYS.clear()  # a new helper process starts with nothing pinned


def test_probe_first_mismatch_fails_closed_and_says_restart(paths, capsys):
    """The game started after the swap, so the probe pinned the swapped key; the helper must not silently issue
    commands under the fresh key."""
    first = commands.command_key(paths)
    _swap_between_sessions(paths)

    fresh = commands.command_key(paths)

    err = capsys.readouterr().err
    assert "DOMUS_KEY_MISMATCH" in err
    assert "restart the game" in err.lower()
    assert fresh not in (EVIL, first)
    key_file = paths.telemetry / "cmd" / "key"
    assert key_file.read_text(encoding="ascii") == fresh.hex()
    assert (paths.data_dir / "cmd_key.sha256").read_text(encoding="ascii").strip() == _fingerprint(fresh)
    with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
        commands.publish("status", {}, "helper", paths=paths)
    with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
        commands.send("status", {}, "helper", timeout_s=0.01, paths=paths)
    assert not list(paths.inbox.glob("*.json"))


def test_a_publish_that_finds_the_mismatch_itself_writes_nothing(paths, capsys):
    """No earlier command_key call: the first publish is the one that notices the swap, and it must not go out."""
    commands.command_key(paths)
    _swap_between_sessions(paths)

    with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
        commands.publish("status", {}, "helper", paths=paths)

    err = capsys.readouterr().err
    assert "DOMUS_KEY_MISMATCH" in err
    assert "restart the game" in err.lower()
    assert not list(paths.inbox.glob("*.json"))
    assert (paths.telemetry / "cmd" / "key").read_text(encoding="ascii") != EVIL.hex()


def test_expire_pending_that_finds_the_mismatch_itself_claims_nothing(paths):
    commands.command_key(paths)
    command_id = commands.publish("status", {}, "helper", paths=paths)
    _swap_between_sessions(paths)
    with pytest.raises(commands.CommandKeyFailClosed, match="restart the game"):
        commands.expire_pending(paths)
    assert (paths.inbox / (command_id + ".json")).exists()


def test_first_create_and_unchanged_key_still_issue(paths, capsys):
    commands.publish("status", {}, "helper", paths=paths)  # first create
    commands._PINNED_KEYS.clear()
    commands._FAIL_CLOSED.clear()
    commands.command_key(paths)  # unchanged key, new helper process
    commands.publish("status", {}, "helper", paths=paths)
    assert "DOMUS_KEY_MISMATCH" not in capsys.readouterr().err
    assert len(list(paths.inbox.glob("*.json"))) == 2
