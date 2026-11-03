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
