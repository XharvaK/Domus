"""W2h in the helper: the window facts her portrait carries (held windows shown, screens only the
User's hands can use, identity windows), the question fields (held, whose, rules), and the
shedding order. Invented strings only."""
import json

from domus_helper.spool import Spool
from domus_helper.thalamus import observation
from domus_helper.windows import WINDOW_MS, WindowLog, withheld_of

NOW = 2_000_000
ACT = "c" * 32
TEXTS = {"1": "Pick some", "2": "OK", "9": "Tip Amount"}


def _speed(phase, code=None, detail=None, at=NOW, session="s"):
    return {"event_kind": "speed_event", "telemetry_session_id": session, "wall_timestamp_ms": at,
            "e2": {"phase": phase, "code": code, "detail": detail}}


def _act(phase, act_id=ACT, code=None, tuning="bookshelf_ReadBook", at=NOW, session="s"):
    return {"event_kind": "act_event", "telemetry_session_id": session, "wall_timestamp_ms": at,
            "e2": {"act_id": act_id, "phase": phase, "code": code, "tuning_name": tuning, "detail": None}}


def _log(tmp_path):
    return WindowLog(Spool(tmp_path / "spool.db"))


def test_each_window_fact_is_recorded_as_it_happened(tmp_path):
    log = _log(tmp_path)
    log.on_row(_speed("DIALOG_SHOWN", code="TIMEOUT", detail="dialog 555 act %s" % ACT), NOW)
    log.on_row(_speed("DIALOG_SHOWN", code="NOT_ANSWERABLE:UiColorPicker", detail="dialog 556"), NOW + 1)
    log.on_row(_speed("DIALOG_SHOWN", code="IDENTITY_USER", detail="dialog 557"), NOW + 2)
    assert log.recent(NOW + 60_002, "s") == [
        {"event": "DIALOG_SHOWN", "code": "TIMEOUT", "ago_min": 1},
        {"event": "DIALOG_SHOWN", "code": "NOT_ANSWERABLE:UiColorPicker", "ago_min": 1},
        {"event": "DIALOG_SHOWN", "code": "IDENTITY_USER", "ago_min": 1}]


def test_a_screen_her_act_would_have_opened_is_named_by_the_acts_tuning_name(tmp_path):
    log = _log(tmp_path)
    log.on_row(_act("PUSHED"), NOW - 10)
    log.on_row(_speed("SCREEN_WITHHELD", code="msg_17", detail="dialog 9 act %s" % ACT), NOW)
    assert log.recent(NOW, "s") == [{"event": "SCREEN_WITHHELD", "code": "bookshelf_ReadBook", "ago_min": 0}]


def test_a_screen_nobody_could_name_is_still_a_fact_with_the_act_named(tmp_path):
    log = _log(tmp_path)
    log.on_row(_act("PUSHED"), NOW - 10)
    log.on_row(_speed("UNKNOWN_SCREEN", detail="act %s" % ACT), NOW)
    log.on_row(_speed("UNKNOWN_SCREEN", detail="act %s" % ("d" * 32)), NOW + 1)
    assert log.recent(NOW + 1, "s") == [
        {"event": "UNKNOWN_SCREEN", "code": "bookshelf_ReadBook", "ago_min": 0},
        {"event": "UNKNOWN_SCREEN", "code": "unnamed", "ago_min": 0}]


def test_an_act_that_ended_on_a_withheld_screen_is_one_window_with_its_speed_event(tmp_path):
    log = _log(tmp_path)
    log.on_row(_act("FINISHED", code="SCREEN_WITHHELD:msg_17", tuning="vase_Arrange"), NOW)
    log.on_row(_speed("SCREEN_WITHHELD", detail="act %s" % ACT), NOW)
    assert log.recent(NOW, "s") == [{"event": "SCREEN_WITHHELD", "code": "vase_Arrange", "ago_min": 0}]
    assert withheld_of(_act("FINISHED", code="SCREEN_WITHHELD:msg_17", tuning="vase_Arrange")) == (
        "vase_Arrange", "msg_17")
    assert withheld_of(_act("FINISHED", code="FINISHED_OK", tuning="vase_Arrange")) is None
    assert withheld_of(_act("FINISHED", code="SCREEN_WITHHELD:msg_17", tuning=None)) is None


def test_only_the_last_half_hour_of_her_session_newest_last_at_most_four(tmp_path):
    log = _log(tmp_path)
    log.on_row(_speed("DIALOG_SHOWN", code="TIMEOUT", detail="dialog 1"), NOW - WINDOW_MS - 1)
    log.on_row(_speed("DIALOG_SHOWN", code="TIMEOUT", detail="dialog 2", session="other"), NOW)
    for index in range(5):
        log.on_row(_speed("DIALOG_SHOWN", code="IDENTITY_USER", detail="dialog %d" % (10 + index)), NOW + index)
    recent = log.recent(NOW + 5, "s")
    assert len(recent) == 4
    assert [item["code"] for item in recent] == ["IDENTITY_USER"] * 4
    assert log.recent(NOW + 5, "other") == [{"event": "DIALOG_SHOWN", "code": "TIMEOUT", "ago_min": 0}]


def test_windows_survive_a_restart_and_unrelated_speed_events_are_not_kept(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    log = WindowLog(spool)
    log.on_row(_speed("REQUEST_PUSHED", detail="act %s" % ACT), NOW)
    log.on_row(_speed("DIALOG_SHOWN", code="TIMEOUT", detail="dialog 5 act %s" % ACT), NOW + 1)
    again = WindowLog(spool)
    assert again.recent(NOW + 2, "s") == [{"event": "DIALOG_SHOWN", "code": "TIMEOUT", "ago_min": 0}]
    assert len(json.loads(spool.get_kv("windows"))["entries"]) == 1


def _row(running=(), queued=(), asked=None, presence=None):
    observed = [{"affordance_text": "<class 'sims4.tuning.instances.%s'>" % name, "membership": "RUNNING"}
                for name in running]
    observed += [{"affordance_text": "<class 'sims4.tuning.instances.%s'>" % name, "membership": "QUEUED"}
                 for name in queued]
    row = {"presence": presence or [{"id": "100", "is_body": True, "name": "Her"}],
           "interactions": {"observed": observed}}
    if asked is not None:
        row["dialogs"] = {"open": asked, "closed": [], "truncated": False}
    return row


def test_a_question_says_whether_it_is_held_whose_it_is_and_its_rules():
    asked = [
        {"dialog_id": "600", "owner_id": "100", "cause": "hers", "held": True, "title_key": "1",
         "responses": [{"response": "ok", "text_key": "2"}], "select": {"min": 1, "max": 3},
         "counts": {"max_in_row": 4, "max_rows": 2},
         "text_inputs": [{"name": "tip", "min_length": 1, "max_length": 6, "numeric": True,
                          "min_value": 0, "max_value": 50, "profanity_checked": False,
                          "restricted": True, "default_key": "9"},
                         {"name": "note", "min_length": 0, "max_length": None, "numeric": False,
                          "min_value": None, "max_value": None, "profanity_checked": True,
                          "restricted": False, "default_key": None}]},
        {"dialog_id": "601", "owner_id": "100", "cause": "user", "title_key": "1", "responses": []},
        {"dialog_id": "602", "owner_id": "42", "title_key": "1", "responses": []},
    ]
    portrait = observation._portrait(_row(asked=asked), TEXTS.get)
    first, user, older = portrait["asked"]
    assert first["held"] is True and first["whose"] == "yours"
    assert first["answer_rules"]["select"] == {"min": 1, "max": 3}
    assert first["answer_rules"]["counts"] == {"max_in_row": 4, "max_rows": 2}
    assert first["answer_rules"]["text"][0] == {"name": "tip", "label": "Tip Amount", "min_length": 1,
                                                "max_length": 6, "numeric": True, "min_value": 0,
                                                "max_value": 50, "profanity_checked": False, "restricted": True}
    assert first["answer_rules"]["text"][1]["label"] == "note"
    assert (user["held"], user["whose"]) == (False, "the User's")
    assert (older["held"], older["whose"]) == (False, "the User's")
    assert "answer_rules" not in user


def test_a_window_dropped_without_an_answer_is_a_fact_with_its_reason(tmp_path):
    log = _log(tmp_path)
    log.on_row(_speed("DIALOG_DROPPED", code="VANISHED", detail="dialog 555 act %s" % ACT), NOW)
    log.on_row(_speed("DIALOG_DROPPED", code="ZONE_CHANGE", detail="dialog 556"), NOW + 1)
    log.on_row(_speed("DIALOG_DROPPED", code="NOT_A_REASON", detail="dialog 557"), NOW + 2)
    assert log.recent(NOW + 3, "s") == [
        {"event": "DIALOG_DROPPED", "code": "VANISHED", "ago_min": 0},
        {"event": "DIALOG_DROPPED", "code": "ZONE_CHANGE", "ago_min": 0}]


def test_a_picker_with_one_row_has_no_rule_in_the_portrait_either(tmp_path):
    asked = [{"dialog_id": "600", "owner_id": "100", "cause": "hers", "held": True, "title_key": "1",
              "responses": [{"response": "ok", "text_key": "2"}], "select": {"min": 1, "max": 1}},
             {"dialog_id": "601", "owner_id": "100", "cause": "hers", "held": True, "title_key": "1",
              "responses": [{"response": "ok", "text_key": "2"}], "select": {"min": 1, "max": 0}}]
    first, unlimited = observation._portrait(_row(asked=asked), TEXTS.get)["asked"]
    assert "answer_rules" not in first
    assert unlimited["answer_rules"] == {"select": {"min": 1, "max": 0}}


def test_the_portrait_carries_window_facts_newest_last():
    windows = [{"event": "DIALOG_SHOWN", "code": "TIMEOUT", "ago_min": 9}]
    assert observation._portrait(_row(), TEXTS.get, windows=windows)["windows"] == windows
    assert observation._portrait(_row(), TEXTS.get)["windows"] == []


def test_windows_shed_oldest_first_before_running():
    windows = [{"event": "DIALOG_SHOWN", "code": "IDENTITY_USER", "ago_min": n} for n in (4, 3, 2, 1)]
    row = _row(running=["cook_Stew", "piano_Play"])
    full = observation._portrait(row, TEXTS.get, windows=windows)
    lower = len(json.dumps(full, separators=(",", ":")).encode("utf-8")) - 1
    observation._PORTRAIT_LIMIT, saved = lower, observation._PORTRAIT_LIMIT
    try:
        fitted = observation._portrait(row, TEXTS.get, windows=windows)
    finally:
        observation._PORTRAIT_LIMIT = saved
    assert fitted["running"] == full["running"]
    assert [item["ago_min"] for item in fitted["windows"]] == [3, 2, 1]


def test_a_crowded_portrait_still_fits_the_limit_with_windows():
    running = ["bookshelf_Read%d" % index for index in range(8)]
    queued = ["piano_Practice%d" % index for index in range(8)]
    windows = [{"event": "UNKNOWN_SCREEN", "code": "vase_Arrange%d" % index, "ago_min": index} for index in range(4)]
    portrait = observation._portrait(_row(running=running, queued=queued), TEXTS.get, windows=windows)
    assert len(json.dumps(portrait, separators=(",", ":")).encode("utf-8")) <= observation._PORTRAIT_LIMIT


def test_the_bridge_hands_her_session_window_facts_to_each_observation(paths, monkeypatch):
    from domus_helper.bridge import Bridge
    monkeypatch.setenv("DOMUS_ASHLEY_TOKEN", "")
    bridge = Bridge(paths, process=(None, None), detected_build=None, client=None)
    bridge._windows.on_row(_speed("DIALOG_SHOWN", code="TIMEOUT", detail="dialog 5 act %s" % ACT), NOW)
    bridge._last_body_row = {"telemetry_session_id": "s", "presence": []}
    assert bridge._obs_ctx(NOW + 1000)["windows"] == [{"event": "DIALOG_SHOWN", "code": "TIMEOUT", "ago_min": 0}]
    bridge._last_body_row = {"telemetry_session_id": "other", "presence": []}
    assert bridge._obs_ctx(NOW + 1000)["windows"] == []
