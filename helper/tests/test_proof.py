import json

import pytest

from domus_helper import inputs, overlay, proof
from domus_helper.spool import Spool

NOW = 1_800_000_000_000
DAY = 86_400_000


class Feed:
    def __init__(self, items):
        self.items = items

    def post_feed(self, body):
        return {"status": "ok", "items": self.items}


def lines(path):
    return path.read_text(encoding="utf-8").splitlines()


def test_a_chain_verifies_and_any_edit_breaks_it(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    try:
        trace = proof.Trace(spool, tmp_path)
        first = trace.shown("p1", {"line": "Toast."}, {"build": "a"}, NOW)
        assert trace.shown("p1", {"line": "Toast."}, {"build": "a"}, NOW + 1) is None
        second = trace.shown("p2", {"held": True}, {"build": "a"}, NOW + 2)
        assert first["prev_hash"] == proof.GENESIS and second["prev_hash"] == first["sha256"]
        files = sorted((tmp_path / proof.DIR).glob("trace-*.jsonl"))
        assert len(files) == 1
        ok, count, last, bad = proof.verify_lines(lines(files[0]))
        assert (ok, count, last, bad) == (True, 2, second["sha256"], None)
        tampered = lines(files[0])
        tampered[0] = tampered[0].replace("Toast.", "Toast!")
        assert proof.verify_lines(tampered)[0] is False and proof.verify_lines(tampered)[3] == 0
        # The chain runs on across days, and across a restart (the last hash is in the spool).
        again = proof.Trace(spool, tmp_path).shown("p3", {"quiet": True}, {}, NOW + DAY)
        assert again["prev_hash"] == second["sha256"]
        assert len(list((tmp_path / proof.DIR).glob("trace-*.jsonl"))) == 2
    finally:
        spool.close()


def test_the_days_root_is_written_once(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    try:
        trace = proof.Trace(spool, tmp_path)
        line = trace.shown("p1", {"line": "Toast."}, {}, NOW)
        day = next((tmp_path / proof.DIR).glob("trace-*.jsonl")).stem.split("-")[1]
        assert proof.root(tmp_path, day, NOW) == {"day": day, "lines": 1, "root": line["sha256"], "ok": True}
        proof.root(tmp_path, day, NOW + 1)
        assert len(lines(tmp_path / proof.DIR / "roots.jsonl")) == 1
        assert proof.root(tmp_path, "19990101") == {"day": "19990101", "lines": 0, "root": None, "ok": True}
    finally:
        spool.close()


def test_the_ledger_is_chained_and_kinds_are_fixed(paths, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    assert proof.main(["ledger", "arranged", "approved a video site", "--link", "https://example.invalid/x"]) == 0
    assert proof.main(["ledger", "unarranged", "a friend mentioned it"]) == 0
    with pytest.raises(SystemExit):
        proof.main(["ledger", "rumour", "no such kind"])
    capsys.readouterr()
    entries = lines(tmp_path / proof.DIR / "ledger.jsonl")
    assert [json.loads(line)["kind"] for line in entries] == ["arranged", "unarranged"]
    assert proof.verify_lines(entries)[0] is True
    assert proof.main(["verify", str(tmp_path / proof.DIR / "ledger.jsonl")]) == 0


def test_the_overlay_traces_a_pass_once_and_only_when_shown(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    try:
        inputs.set_mode(spool, tmp_path, inputs.GAME_ONLY, NOW)
        trace = proof.Trace(spool, tmp_path)
        view = overlay.Overlay(spool, tmp_path, NOW - overlay.HUMAN_HAND_MS - 1, trace=trace, helper_build="h123")
        view.on_row({"event_kind": "presence_snapshot", "probe_version": "2.20.1", "game": {}}, NOW)
        view.poll(Feed([{"inputs": "game_only", "pass": "journal:1", "line": "Toast.",
                         "regime": {"build": "b1", "model": "m", "request_id": "r1"}}]), "h1", NOW)
        state = view.publish(NOW, attached=False)
        assert state["mode"] == "curtain" and not (tmp_path / proof.DIR).exists()
        state = view.publish(NOW + 1, attached=True)
        assert state["passes"] == [{"at_ms": None, "line": "Toast."}]
        view.publish(NOW + 2, attached=True)
        traced = [json.loads(line) for line in lines(next((tmp_path / proof.DIR).glob("trace-*.jsonl")))]
        assert len(traced) == 1
        assert traced[0]["pass"] == "journal:1" and traced[0]["shown"] == {"at_ms": None, "line": "Toast."}
        assert traced[0]["regime"] == {"build": "b1", "model": "m", "request_id": "r1", "inputs": "game_only",
                                       "helper_build": "h123", "probe_version": "2.20.1"}
    finally:
        spool.close()
