"""R1: the helper test session must never read the real/default game install.

`fingerprints.detected_build()` falls back to the hardcoded Windows
`DEFAULT_GAME_ROOT` when `DOMUS_GAME_ROOT` is unset, so on a machine without
that install the tests fail for the wrong reason. The autouse `fake_game_root`
fixture in conftest.py must provide a temporary fake install instead.
"""
from pathlib import Path

from domus_helper import fingerprints as fp


def test_session_does_not_use_the_windows_default_game_root():
    assert fp.game_root() != Path(fp.DEFAULT_GAME_ROOT)


def test_fake_game_root_is_a_fake_sims_install(fake_game_root):
    ini = Path(fake_game_root) / "Game" / "Bin" / "Default.ini"
    assert ini.is_file(), "fake_game_root must contain Game/Bin/Default.ini"
    assert fp._ini_value(ini.read_bytes().decode("utf-8-sig"), "gameversion") == "1.129.39.1030"


def test_detected_build_resolves_to_the_fake_game_root(fake_game_root):
    detected = fp.detected_build()
    assert detected["game_root"] == str(fake_game_root)
    assert detected["detected_build"] == "1.129.39.1030"
    assert Path(detected["game_root"]) != Path(fp.DEFAULT_GAME_ROOT)


def test_paths_without_a_game_root_use_the_fake_root(fake_game_root, paths):
    assert paths.game_root is None
    detected = fp.detected_build(paths=paths)
    assert detected["game_root"] == str(fake_game_root)
    assert detected["detected_build"] == "1.129.39.1030"
