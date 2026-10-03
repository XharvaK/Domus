import json

from domus_helper import calibration
from domus_helper import mcp_server as mcp
from conftest import replier

AUTO = "InteractionSource.AUTONOMY"
PIE = "InteractionSource.PIE_MENU"


def snap(seq, ticks, wall, running=True, motives=None, speed="NORMAL", paused=False,
         source=AUTO, aff="A", iid="i", sim="sim"):
    entries = []
    if running:
        entries.append({
            "interaction_id": iid, "entry_key": iid, "affordance_id": aff,
            "membership": "RUNNING", "source_raw": source, "source_norm": "UNKNOWN",
        })
    return {
        "event_kind": "presence_snapshot", "written_sequence": seq,
        "wall_timestamp_ms": wall, "telemetry_session_id": "sess",
        "game": {"ticks": ticks, "clock_speed": speed, "paused": paused},
        "body": {"sim_id": sim}, "motives": motives or [],
        "interactions": {"observed": entries},
    }


def test_running_span_duration():
    rows = [snap(1, 10, 1000), snap(2, 12, 1500), snap(3, 16, 2000, running=False)]
    found = calibration.analyze(rows)
    group = found["durations"][0]
    assert group["control"] == "AUTONOMY"
    assert group["n"] == 1
    assert group["median_ticks"] == 6
    assert group["median_wall_ms"] == 1000
    assert group["ambiguous"] == 0
    assert found["coverage"]["autonomy_spans"] == 1


def test_sequence_gap_is_ambiguous():
    rows = [snap(1, 0, 0), snap(2, 5, 10), snap(4, 9, 20, running=False)]
    found = calibration.analyze(rows)
    group = found["durations"][0]
    assert group["n"] == 0
    assert group["ambiguous"] == 1
    assert found["coverage"]["gaps"] == 1
    assert found["coverage"]["autonomy_spans"] == 0


def test_paused_interval_excluded_from_rates():
    rows = [
        snap(1, 0, 0, motives=[{"id": "hunger", "value": 10}]),
        snap(2, 4, 10, paused=True, motives=[{"id": "hunger", "value": 6}]),
        snap(3, 8, 20, running=False, motives=[{"id": "hunger", "value": 2}]),
    ]
    assert calibration.analyze(rows)["rates"] == []


def test_autonomy_separated_from_pie():
    rows = [
        snap(1, 0, 0, source=AUTO, aff="sit", iid="a"),
        snap(2, 4, 10, running=False),
        snap(3, 4, 10, source=PIE, aff="sit", iid="b"),
        snap(4, 9, 20, running=False),
    ]
    found = calibration.analyze(rows)
    controls = [row for row in found["durations"] if row["control"] == "AUTONOMY"]
    others = [row for row in found["durations"] if row["control"] is None]
    assert len(controls) == 1 and controls[0]["source_raw"] == AUTO
    assert len(others) == 1 and others[0]["source_raw"] == PIE
    assert found["coverage"]["affordances"] == 1
    assert found["coverage"]["autonomy_spans"] == 1


def test_nearest_rank_median_iqr():
    assert calibration._nearest_rank([1, 2, 3, 4, 5], 50) == 3
    assert calibration._iqr([1, 2, 3, 4, 5]) == [2, 4]
    assert calibration._nearest_rank([10, 30], 50) == 10
    rows = []
    seq = 1
    for end in (1, 2, 3, 4, 5):
        rows.append(snap(seq, 0, 0, iid="n%d" % end))
        seq += 1
        rows.append(snap(seq, end, end * 10, running=False))
        seq += 1
    found = calibration.analyze(rows)
    group = found["durations"][0]
    assert group["n"] == 5
    assert group["median_ticks"] == 3
    assert group["iqr_ticks"] == [2, 4]


def test_write_report_is_deterministic(tmp_path, monkeypatch):
    rows = [snap(1, 0, 0, motives=[{"id": "fun", "value": 1}]),
            snap(2, 2, 20, running=False, motives=[{"id": "fun", "value": 5}])]
    monkeypatch.setattr(calibration.telemetry, "rows", lambda session: rows)
    monkeypatch.setattr(calibration, "resolve_session", lambda token, paths=None: tmp_path / token)
    first = calibration.write_report("sess", tmp_path / "one")
    second = calibration.write_report("sess", tmp_path / "two")
    assert first.read_bytes() == second.read_bytes()
    assert first.name == "calibration_sess.json"


def test_idle_rate_and_activity():
    rows = [
        snap(1, 0, 0, running=False, motives=[{"id": "fun", "value": 10}]),
        snap(2, 5, 50, running=False, motives=[{"id": "fun", "value": 0}]),
    ]
    rate = calibration.analyze(rows)["rates"][0]
    assert rate["activity"] == []
    assert rate["median_rate"] == -2.0
    assert rate["n"] == 1


def test_calibrate_command_is_exposed(paths, monkeypatch):
    assert "calibrate" not in mcp.ACTUATING
    monkeypatch.setattr(mcp, "game_running", lambda: True)
    seen = []

    def handler(row):
        seen.append(row)
        return dict(status="OK", code=None, result={"ok": True})

    with replier(paths, handler):
        mcp.calibrate()
    assert ("calibrate", {}) in [(row["command"], row["args"]) for row in seen]
