import hashlib
import json
import os

import pytest

from domus_helper import telemetry, mcp_server
from domus_helper.runs import trial
from domus_helper.vendor import schema
from conftest import event, opened, replier, session_file


def test_latest_tail_validation(paths):
    first = session_file(paths, [opened()])
    second = session_file(paths, [opened(), event("speed_event", 1,
        e2=dict(phase="REQUEST_PUSHED", code=None, detail=None))])
    os.utime(first, (1, 1))
    (paths.telemetry / "ashley_e1_bootstrap_ffffffff.jsonl").write_text('{}\n')
    assert telemetry.latest_session(paths=paths) == second
    assert telemetry.tail(["speed_event"], 1, paths=paths)[0]["written_sequence"] == 1
    with second.open("ab") as handle:
        handle.write(b'{"partial":')
    assert len(list(telemetry.rows(second))) == 2
    with pytest.raises(schema.SchemaError):
        schema.validate_record({"schema_version": 2, "event_kind": "session_open"})


@pytest.mark.parametrize("failure", [None, "REJECTED", "ERROR"])
def test_trial(paths, monkeypatch, tmp_path, failure):
    monkeypatch.setattr(mcp_server, "game_running", lambda: True)
    state = {"armed_name": "UNARMED"}
    calls = []
    session = None
    counter = 0
    before = (paths.sims_root / "saves" / "Slot_00000001.save").read_bytes()
    def handler(row):
        nonlocal session, counter
        name = row["command"]
        calls.append(name)
        result = {"ok": True, "lines": []}
        if name == "status":
            result = dict(state)
        elif name == "arm":
            state["armed_name"] = "LAB_E1"
        elif name == "start":
            session = session_file(paths, [opened()])
        elif name == "sit_trial":
            if failure:
                return dict(status=failure, code="TEST_REJECT", result=result)
            counter += 1
            experiment_id = f"aaaaaaaa-{counter}"
            payload = dict(phase="VERDICT", code="PARTIAL", experiment_id=experiment_id,
                           object_id=row["args"]["object_id"], token=None,
                           interaction_id=None, claims=None, finishing_type=None, detail=None)
            with session.open("ab") as handle:
                handle.write(schema.serialize_record(event("experiment_event", counter, e2=payload)) + b"\n")
            result["lines"] = [f"PUSHED {experiment_id} interaction 77"]
        return dict(status="OK", code=None, result=result)
    out = tmp_path / "evidence"
    with replier(paths, handler):
        if failure:
            with pytest.raises(mcp_server.CommandFailed):
                trial.run("lab_e1", ["123"], 2, out)
        else:
            trial.run("lab_e1", ["123", "456"], 2, out)
    assert calls[-2:] == ["stop", "disarm"]
    assert calls[:5] == ["status", "status", "arm", "status", "status"]
    assert (out / session.name).read_bytes() == session.read_bytes()
    assert (out / paths.ledger.name).read_bytes() == paths.ledger.read_bytes()
    inventory = json.loads((out / "save_inventory.json").read_text())
    assert inventory[0]["sha256"] == hashlib.sha256(before).hexdigest()
    assert inventory[0]["read_only"] is True
    assert (paths.sims_root / "saves" / "Slot_00000001.save").read_bytes() == before
    markdown = (out / "session.md").read_text().splitlines()
    assert [json.loads(line) for line in markdown[1:-1]] == list(telemetry.rows(session))
    if failure is None:
        assert counter == 4


def test_no_output_inside_sims(paths):
    with pytest.raises(ValueError, match="outside"):
        trial.run("lab_e1", ["123"], 1, paths.sims_root / "evidence")
    assert not list(paths.inbox.iterdir())


def test_verdict_correlation(paths):
    session = session_file(paths, [opened(), event("experiment_event", 1, e2=dict(
        phase="VERDICT", code="PARTIAL", experiment_id="aaaaaaaa-1", object_id="123",
        token=None, interaction_id=None, claims=None, finishing_type=None, detail=None))])
    with pytest.raises(TimeoutError, match="aaaaaaaa-2"):
        trial.wait_verdict(session, "aaaaaaaa-2", 0.01)


def test_stale_session_is_not_selected(paths):
    stale = session_file(paths, [opened()])
    with pytest.raises(TimeoutError, match="session telemetry"):
        trial.wait_session(paths, 0.01, {stale})


def test_rotated_verdict_and_evidence(paths, tmp_path):
    session = session_file(paths, [opened()])
    rotated = session.with_name(session.name + ".1")
    verdict = event("experiment_event", 1, e2=dict(phase="VERDICT", code="PARTIAL",
        experiment_id="aaaaaaaa-2", object_id="123", token=None, interaction_id=None,
        claims=None, finishing_type=None, detail=None))
    rotated.write_bytes(schema.serialize_record(verdict) + b"\n")
    assert trial.wait_verdict(session, "aaaaaaaa-2", 0.01) == verdict
    out = tmp_path / "rotation-evidence"
    trial.write_evidence(out, session, paths)
    assert (out / rotated.name).read_bytes() == rotated.read_bytes()
    markdown = (out / "session.md").read_text().splitlines()
    assert len(markdown[1:-1]) == 2


def test_trial_initial_rejection_still_cleans_up(paths, monkeypatch, tmp_path):
    monkeypatch.setattr(mcp_server, "game_running", lambda: True)
    calls = []
    def handler(row):
        calls.append(row["command"])
        return dict(status="REJECTED" if row["command"] == "status" else "OK",
                    code="TEST", result={})
    with replier(paths, handler):
        with pytest.raises(mcp_server.CommandFailed):
            trial.run("lab_e1", ["123"], 1, tmp_path / "out")
    assert calls == ["status", "stop", "disarm"]


def test_cleanup_attempts_disarm_after_stop_error(paths, monkeypatch, tmp_path):
    monkeypatch.setattr(mcp_server, "game_running", lambda: True)
    calls = []
    def handler(row):
        calls.append(row["command"])
        return dict(status="ERROR", code="TEST", result={})
    with replier(paths, handler):
        with pytest.raises(mcp_server.CommandFailed):
            trial.run("lab_e1", ["123"], 1, tmp_path / "out")
    assert calls == ["status", "stop", "disarm"]
