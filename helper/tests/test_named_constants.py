"""R2/R6: one default game folder, and named constants for the transport timeouts (values unchanged)."""
import inspect
from pathlib import Path

from domus_helper import bridge, fingerprints, paths, transport

HELPER = Path(__file__).resolve().parents[1] / "domus_helper"
WINDOWS_DEFAULT = r"E:\SteamLibrary\steamapps\common\The Sims 4"


def test_one_default_game_root():
    assert paths.DEFAULT_GAME_ROOT == WINDOWS_DEFAULT
    assert fingerprints.DEFAULT_GAME_ROOT is paths.DEFAULT_GAME_ROOT
    holders = [p.name for p in HELPER.glob("*.py") if WINDOWS_DEFAULT in p.read_text(encoding="utf-8")]
    assert holders == ["paths.py"]


def test_transport_timeouts_are_named_with_unchanged_values():
    assert transport.SNAPSHOT_TIMEOUT_S == 30
    assert transport.REQUEST_TIMEOUT_S == 10
    assert inspect.signature(transport.AshleyClient.__init__).parameters["timeout_s"].default == transport.REQUEST_TIMEOUT_S
    assert bridge.GIT_TIMEOUT_S == 5
    assert "timeout=GIT_TIMEOUT_S" in inspect.getsource(bridge)
