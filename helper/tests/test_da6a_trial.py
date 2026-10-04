"""DA6A helper: trial is actuating and goes through DomusTools.command."""
import json

import pytest

from domus_helper import mcp_server as mcp
from conftest import replier


def test_trial_reaches_command_on_a_lab_fork(paths, monkeypatch):
    monkeypatch.setattr(mcp, "game_running", lambda: True)
    seen = []

    def handler(row):
        seen.append(row)
        result = {"armed_name": "LAB_E1_FORK"}
        if row["command"] == "status":
            result["sims_build"] = None
        return dict(status="OK", code=None, result=result)

    with replier(paths, handler):
        reply = mcp.trial("12", "34")
    commands = [row["command"] for row in seen]
    assert commands[0] == "status"
    assert "trial" in commands
    trial = next(row for row in seen if row["command"] == "trial")
    assert trial["args"] == {"object_id": "12", "guid64": "34"}
    assert reply["status"] == "OK"


def test_trial_refused_when_not_armed_on_a_lab_save(paths, monkeypatch):
    monkeypatch.setattr(mcp, "game_running", lambda: True)
    with replier(paths, lambda row: dict(status="OK", code=None,
                                       result={"armed_name": "UNARMED", "sims_build": None})):
        with pytest.raises(mcp.SafetyError, match="LAB"):
            mcp.DomusTools().command("trial", {"object_id": "12", "guid64": "34"})
    written = [json.loads(path.read_bytes())["command"] for path in paths.inbox.glob("*.json")]
    assert written == ["status"]
