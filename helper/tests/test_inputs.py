import json

import pytest

from domus_helper import inputs
from domus_helper.bridge import Bridge
from domus_helper.contract import ContractError, validate_heartbeat
from domus_helper.spool import Spool

NOW = 1_800_000_000_000


class Fake:
    def __init__(self):
        self.sent = []

    def post_heartbeat(self, body):
        self.sent.append(body)
        return type("R", (), {"kind": "admitted", "status": 200})()

    def post_observation(self, body, now_ms=None):
        raise AssertionError("no observation")


def test_the_switch_is_kept_and_every_flip_is_logged(paths, tmp_path, monkeypatch):
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    spool = Spool(tmp_path / "spool.db")
    try:
        assert inputs.current(spool) == inputs.FULL
        assert inputs.set_mode(spool, tmp_path, inputs.GAME_ONLY, NOW) == {"inputs": "game_only", "before": "full"}
        assert inputs.current(spool) == inputs.GAME_ONLY
        inputs.set_mode(spool, tmp_path, inputs.FULL, NOW + 1)
        with pytest.raises(ValueError):
            inputs.set_mode(spool, tmp_path, "partial", NOW + 2)
    finally:
        spool.close()
    lines = [json.loads(line) for line in (tmp_path / inputs.LOG).read_text(encoding="utf-8").splitlines()]
    assert lines == [{"at_ms": NOW, "before": "full", "inputs": "game_only"},
                     {"at_ms": NOW + 1, "before": "game_only", "inputs": "full"}]


def test_the_cli_flips_and_shows(paths, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    assert inputs.main(["game-only"]) == 0
    assert inputs.main(["show"]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1]) == {"inputs": "game_only"}


def test_a_flip_goes_out_at_once_and_full_sends_no_key(paths, tmp_path, monkeypatch):
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    client = Fake()
    bridge = Bridge(paths, client=client, process=None, detected_build=None, mono=lambda: 0)
    bridge.tick(NOW)
    assert "inputs" not in client.sent[-1]
    bridge.tick(NOW + 1_000)
    assert len(client.sent) == 1
    inputs.set_mode(bridge.spool, tmp_path, inputs.GAME_ONLY, NOW + 2_000)
    bridge.tick(NOW + 2_000)
    assert len(client.sent) == 2 and client.sent[-1]["inputs"] == "game_only"
    assert bridge.status()["inputs"] == "game_only"
    bridge.tick(NOW + 3_000)
    assert len(client.sent) == 2
    inputs.set_mode(bridge.spool, tmp_path, inputs.FULL, NOW + 4_000)
    bridge.tick(NOW + 4_000)
    assert len(client.sent) == 3 and "inputs" not in client.sent[-1]


def test_the_contract_carries_only_the_two_modes():
    base = {"v": 1, "helper_session": "a" * 32, "sent_at_ms": NOW, "attached": True}
    assert validate_heartbeat({**base, "inputs": "game_only"})["inputs"] == "game_only"
    assert "inputs" not in validate_heartbeat(base)
    with pytest.raises(ContractError):
        validate_heartbeat({**base, "inputs": "partial"})
