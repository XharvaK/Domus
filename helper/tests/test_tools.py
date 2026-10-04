import pytest

from domus_helper import mcp_server as mcp
from conftest import replier


@pytest.mark.parametrize("tool,args", [(mcp.status, ()), (mcp.arm, ("lab_e1",)),
    (mcp.start, ()), (mcp.stop, ()), (mcp.disarm, ()), (mcp.prepare, ("1",)),
    (mcp.sit, ("a" * 16,)), (mcp.sit_trial, ("1",)), (mcp.trial, ("1", "2")), (mcp.pause, ()),
    (mcp.release, ()), (mcp.verdicts, ()), (mcp.telemetry, ([],)), (mcp.lineage, ()),
    (mcp.detected_build, ()), (mcp.fingerprints, ())])
def test_all_tools_require_game(paths, monkeypatch, tool, args):
    monkeypatch.setattr(mcp, "game_running", lambda: False)
    with pytest.raises(mcp.SafetyError, match="TS4_x64"):
        tool(*args)
    assert not list(paths.inbox.iterdir())


@pytest.mark.parametrize("name", ["start", "prepare", "sit", "sit_trial", "trial", "pause", "release"])
def test_actuation_requires_lab(paths, monkeypatch, name):
    monkeypatch.setattr(mcp, "game_running", lambda: True)
    with replier(paths, lambda row: dict(status="OK", code=None,
                                       result={"armed_name": "UNARMED"})):
        with pytest.raises(mcp.SafetyError, match="LAB"):
            mcp.DomusTools().command(name)
    assert [__import__('json').loads(p.read_bytes())["command"]
            for p in paths.inbox.glob("*.json")] == ["status"]


def test_arm_postcheck_and_invalid_save(paths, monkeypatch):
    monkeypatch.setattr(mcp, "game_running", lambda: True)
    with replier(paths, lambda row: dict(status="OK", code=None,
                                       result={"armed_name": "UNARMED"})):
        with pytest.raises(mcp.SafetyError, match="arming"):
            mcp.arm("lab_e1")
        with pytest.raises(mcp.SafetyError, match="arm requires"):
            mcp.arm("personal")


def test_tasklist(monkeypatch):
    from subprocess import CompletedProcess
    def process(args, **kwargs):
        assert args == ["tasklist", "/FI", "IMAGENAME eq TS4_x64.exe", "/FO", "CSV", "/NH"]
        return CompletedProcess(args, 0, '"TS4_x64.exe","123"\n')
    monkeypatch.setattr(mcp.subprocess, "run", process)
    assert mcp.game_running()
    monkeypatch.setattr(mcp.subprocess, "run", lambda *a, **k: CompletedProcess([], 0, 'INFO: No tasks'))
    assert not mcp.game_running()


def test_status_rejection_blocks_tool(paths, monkeypatch):
    monkeypatch.setattr(mcp, "game_running", lambda: True)
    with replier(paths, lambda row: dict(status="REJECTED", code="TEST", result={})):
        with pytest.raises(mcp.CommandFailed):
            mcp.telemetry([], 1)


def test_invalid_agent_name(paths, monkeypatch):
    monkeypatch.setenv("DOMUS_AGENT_NAME", "Owner Name")
    with pytest.raises(ValueError, match="DOMUS_AGENT_NAME"):
        mcp.DomusTools()
