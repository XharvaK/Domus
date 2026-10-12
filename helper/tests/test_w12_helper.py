"""2.39.0 (W12 helper): what she sees and knows about her acts and windows. Every row here is invented, and the
probe's keys are read defensively: the tests build fake rows, with and without the new keys."""
from domus_helper.spool import Spool
from domus_helper.windows import WINDOW_MS, WindowLog

NOW = 3_000_000
ACT = "e" * 32


def _speed(phase, code=None, detail=None, at=NOW, session="s"):
    return {"event_kind": "speed_event", "telemetry_session_id": session, "wall_timestamp_ms": at,
            "e2": {"phase": phase, "code": code, "detail": detail}}


def _log(tmp_path):
    return WindowLog(Spool(tmp_path / "spool.db"))


# A10: every code the probe writes for a window that was released, shown or passed through is a fact.
def test_every_code_the_probe_writes_for_a_shown_window_is_recorded(tmp_path):
    log = _log(tmp_path)
    codes = ["TIMEOUT", "IDENTITY_USER", "NOT_ANSWERABLE:UiColorPicker", "ARM", "STOP",
             "FAILED:OkButton", "PASS_THROUGH"]
    for index, code in enumerate(codes):
        log.on_row(_speed("DIALOG_SHOWN", code=code, detail="dialog %d" % (700 + index)), NOW + index)
    recent = log.recent(NOW + len(codes), "s")
    assert [item["code"] for item in recent] == codes[-4:]  # the portrait keeps four, newest last
    assert all(item["event"] == "DIALOG_SHOWN" for item in recent)


def test_a_pass_through_or_an_arm_is_not_dropped_for_its_code(tmp_path):
    log = _log(tmp_path)
    log.on_row(_speed("DIALOG_SHOWN", code="PASS_THROUGH", detail="dialog 701 act %s" % ACT), NOW)
    log.on_row(_speed("DIALOG_SHOWN", code="ARM", detail="dialog 702"), NOW + 1)
    assert log.recent(NOW + 2, "s") == [
        {"event": "DIALOG_SHOWN", "code": "PASS_THROUGH", "ago_min": 0},
        {"event": "DIALOG_SHOWN", "code": "ARM", "ago_min": 0}]


def test_an_empty_code_is_still_not_a_fact(tmp_path):
    log = _log(tmp_path)
    log.on_row(_speed("DIALOG_SHOWN", code="", detail="dialog 703"), NOW)
    assert log.recent(NOW, "s") == []


def test_the_window_facts_still_expire_after_half_an_hour(tmp_path):
    log = _log(tmp_path)
    log.on_row(_speed("DIALOG_SHOWN", code="ARM", detail="dialog 704"), NOW - WINDOW_MS - 1)
    assert log.recent(NOW, "s") == []
