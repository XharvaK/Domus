"""AU NB-3: the helper pins cmd/key at its first read, so a cmd/ writer cannot swap it under a running helper; a key
file that is a link is refused."""
import os

import pytest

from domus_helper import commands
from domus_helper.paths import Paths


@pytest.fixture(autouse=True)
def _fresh_pin(monkeypatch):
    monkeypatch.setattr(commands, "_PINNED_KEYS", {}, raising=False)


def test_a_swapped_key_file_is_not_believed(tmp_path):
    paths = Paths(tmp_path)
    (paths.telemetry / "cmd").mkdir(parents=True)
    first = commands.command_key(paths)
    key_file = paths.telemetry / "cmd" / "key"
    os.replace(key_file, str(key_file) + ".old")
    key_file.write_text((bytes([7]) * 32).hex(), encoding="ascii")
    assert commands.command_key(paths) == first


def test_a_linked_key_file_is_refused(tmp_path):
    paths = Paths(tmp_path)
    (paths.telemetry / "cmd").mkdir(parents=True)
    real = tmp_path / "elsewhere"
    real.write_text((bytes([7]) * 32).hex(), encoding="ascii")
    try:
        os.symlink(real, paths.telemetry / "cmd" / "key")
    except (OSError, NotImplementedError):
        pytest.skip("no symlinks here")
    with pytest.raises(ValueError):
        commands.command_key(paths)


# AU recheck NB-3: a key swapped between sessions (helper and game closed) is caught at the next helper start: the
# helper refuses it loudly, writes a fresh key and records its fingerprint outside cmd/.
EVIL = bytes([7]) * 32


def _swap_between_sessions(paths):
    key_file = paths.telemetry / "cmd" / "key"
    os.replace(key_file, str(key_file) + ".old")
    key_file.write_text(EVIL.hex(), encoding="ascii")
    commands._PINNED_KEYS.clear()  # a new helper process starts with nothing pinned


def test_a_key_swapped_between_sessions_is_refused_and_replaced(tmp_path, capsys):
    paths = Paths(tmp_path)
    (paths.telemetry / "cmd").mkdir(parents=True)
    first = commands.command_key(paths)
    _swap_between_sessions(paths)
    second = commands.command_key(paths)
    assert second not in (EVIL, first)
    assert (paths.telemetry / "cmd" / "key").read_text(encoding="ascii") == second.hex()
    assert "DOMUS_KEY_MISMATCH" in capsys.readouterr().err
    commands._PINNED_KEYS.clear()
    assert commands.command_key(paths) == second  # the fingerprint now names the fresh key


def test_the_fingerprint_lives_outside_cmd(tmp_path):
    paths = Paths(tmp_path)
    (paths.telemetry / "cmd").mkdir(parents=True)
    key = commands.command_key(paths)
    import hashlib
    stored = (paths.data_dir / "cmd_key.sha256").read_text(encoding="ascii").strip()
    assert stored == hashlib.sha256(key.hex().encode("ascii")).hexdigest()
    assert paths.telemetry not in (paths.data_dir / "cmd_key.sha256").parents


def test_an_unchanged_key_is_kept_across_sessions(tmp_path, capsys):
    paths = Paths(tmp_path)
    (paths.telemetry / "cmd").mkdir(parents=True)
    first = commands.command_key(paths)
    commands._PINNED_KEYS.clear()
    assert commands.command_key(paths) == first
    assert "DOMUS_KEY_MISMATCH" not in capsys.readouterr().err
