import hashlib
import json

from domus_helper import proof
from domus_helper.spool import Spool

NOW = 1_800_000_000_000
DAY = 86_400_000
PENDING = b"\xf0\x10" + b"n" * 16 + b"\x08\x00\x83\xdf\xe3\x0d\x2e\xf9\x0c\x8e\x05\x04calx"


def calendar(answers):
    calls = []

    def submit(url, digest):
        calls.append((url, digest))
        return answers.get(url)
    return submit, calls


def test_a_finished_day_gets_a_standard_proof_per_calendar_once(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    try:
        trace = proof.Trace(spool, tmp_path)
        trace.shown("p1", {"line": "Toast."}, {}, NOW - DAY)
        trace.shown("p2", {"line": "Tea."}, {}, NOW)
        files = sorted((tmp_path / proof.DIR).glob("trace-*.jsonl"))
        yesterday, today = (path.stem.split("-")[1] for path in files)
        submit, calls = calendar({proof.CALENDARS[0]: PENDING, proof.CALENDARS[1]: None})
        results = proof.stamp_finished_days(tmp_path, today, submit)
        assert [result["day"] for result in results] == [yesterday]
        digest = hashlib.sha256(files[0].read_bytes()).digest()
        assert results[0] == {"day": yesterday, "sha256": digest.hex(), "stamped": [files[0].name + ".ots"]}
        assert {url for url, _ in calls} == set(proof.CALENDARS) and all(sent == digest for _, sent in calls)
        written = (files[0].parent / (files[0].name + ".ots")).read_bytes()
        assert written == proof.OTS_MAGIC + b"\x01\x08" + digest + PENDING
        assert len(proof.OTS_MAGIC) == 31
        # Done once: a later pass leaves it alone; the second calendar is tried again on a direct stamp.
        assert proof.stamp_finished_days(tmp_path, today, submit) == []
        submit_b, _ = calendar({proof.CALENDARS[1]: PENDING})
        assert proof.stamp(tmp_path, yesterday, submit_b)["stamped"] == [files[0].name + ".ots", files[0].name + ".ots2"]
    finally:
        spool.close()


def test_no_trace_or_no_calendar_writes_nothing(tmp_path, paths, monkeypatch, capsys):
    submit, _ = calendar({})
    assert proof.stamp(tmp_path, "19990101", submit) == {"day": "19990101", "stamped": [], "reason": "no_trace"}
    spool = Spool(tmp_path / "spool.db")
    try:
        proof.Trace(spool, tmp_path).shown("p1", {"quiet": True}, {}, NOW - DAY)
    finally:
        spool.close()
    day = next((tmp_path / proof.DIR).glob("trace-*.jsonl")).stem.split("-")[1]
    assert proof.stamp(tmp_path, day, submit)["stamped"] == []
    assert not list((tmp_path / proof.DIR).glob("*.ots*"))
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(proof, "_submit", submit)
    assert proof.main(["stamp", day]) == 0
    assert json.loads(capsys.readouterr().out)[0]["stamped"] == []
