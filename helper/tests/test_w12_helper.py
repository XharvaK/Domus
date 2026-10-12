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


# E8: a money token is words, not a dropped gap ("brought home some money today"; with an amount, §).
def test_a_money_token_is_words_and_never_dropped(tmp_path):
    from domus_helper import tokens
    subject = tokens.names_of("Ida Vale")
    assert tokens.fill("{0.SimFirstName} brought home {1.Money} today", subject=subject) == (
        "Ida brought home some money today")
    assert tokens.fill("{0.SimFirstName} brought home {1.Money} today", subject=subject, number=1500) == (
        "Ida brought home §1,500 today")


# E4/E5: the probe's first and last name fields are the names; the last name is never a suffix.
def test_names_come_from_the_probe_fields_and_a_suffix_is_not_a_last_name():
    from domus_helper import tokens
    assert tokens.names_of("Ida Ann Vale III") == {"first": "Ida", "last": "Vale", "full": "Ida Ann Vale III"}
    assert tokens.names_from("Ida", "Vale", "Ida Vale") == {"first": "Ida", "last": "Vale", "full": "Ida Vale"}
    assert tokens.names_from("Ida", None, None) == {"first": "Ida", "last": "", "full": "Ida"}
    assert tokens.names_from(None, None, "Ida Vale") == tokens.names_of("Ida Vale")
    assert tokens.names_from("", "", None) is None
    assert tokens.names_from("I" * 80, "Vale", None)["first"] == "I" * 64


# E4: the body's gender ("F" or "M") picks the form of a pair in her own words.
def test_her_gender_picks_the_form_of_a_pair():
    from domus_helper import tokens
    words = tokens.Words(lambda key: "{M0.he}{F0.she} is hungry")
    words.her = tokens.names_from("Ida", "Vale", None)
    assert words(1) == "he is hungry"
    words.gender = "F"
    assert words(1) == "she is hungry"


def test_the_bridge_names_her_and_her_gender_from_the_probes_fields(paths, tmp_path, monkeypatch):
    # E4/E5 through the bridge: the body's first and last name fields and gender reach the words of her view.
    from test_bridge_thalamus import WALL, _bridge, _data
    _data(paths, tmp_path, monkeypatch)
    bridge = _bridge(paths, {"ms": WALL})
    bridge._set_her({"body": {"sim_id": "ASH", "gender": "F", "first_name": "Ida", "last_name": "Vale III"},
                     "presence": [{"id": "ASH", "is_body": True, "name": "Ida Vale III"}]})
    assert bridge._resolve_text.her == {"first": "Ida", "last": "Vale III", "full": "Ida Vale III"}
    assert bridge._resolve_text.gender == "F"
    bridge._set_her({"presence": [{"id": "ASH", "is_body": True, "name": "Ida Vale"}]})
    assert bridge._resolve_text.her == {"first": "Ida", "last": "Vale", "full": "Ida Vale"}
    assert bridge._resolve_text.gender is None
