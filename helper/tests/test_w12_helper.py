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


# ---- the act menu and the dialogs (A7, C2, C4, C9, C10, C12, G1, G3, hold_left_s) ----
from domus_helper.acts import dialog_options, options  # noqa: E402

TEXTS = {"90": "Use the toilet", "91": "The toilet is dirty.", "92": "Snack", "93": "Snack, sweet",
         "94": "Snack, savoury", "1": "What do you want to cook?", "4": "Grilled Cheese", "2": "OK"}


def _obj(object_id, room, distance, **extra):
    item = {"object_id": object_id, "class": "object_plate", "room": room, "distance_m": distance,
            "same_room": room == "4", "acts": [{"guid64": str(7000 + int(object_id)), "name": "thing_%s" % object_id,
                                                "text_key": None}]}
    item.update(extra)
    return item


# C2, C9, G3: room 0 is outside, never near by room; an object on her lot outside says so.
def test_outside_is_outside_never_near_by_room_and_names_its_place():
    menu = {"room": "0", "objects": [
        _obj("31", "0", 30.0, on_lot=True), _obj("32", "0", 40.0, on_lot=False), _obj("33", "0", 2.5, on_lot=True)]}
    listed = options(menu, room="0")
    assert [entry["where"] for entry in listed] == ["outside, on your lot, 2.5 m", "outside, on your lot, 30.0 m",
                                                    "outside, off your lot, 40.0 m"]
    assert [entry["near"] for entry in listed] == [True, False, False]
    assert all(entry["room"] == "outside" for entry in listed)


def test_a_thing_in_the_house_is_not_near_her_when_she_is_outside():
    menu = {"room": "0", "objects": [_obj("34", "4", 30.0, same_room=False)]}
    assert options(menu, room="0")[0]["near"] is False


# C10: an object off her lot says so, whatever its room.
def test_an_object_off_her_lot_is_named_off_her_lot():
    menu = {"room": "4", "objects": [_obj("35", "4", 3.0, on_lot=False, same_room=True)]}
    assert options(menu, room="4")[0]["where"] == "off your lot, 3.0 m"


# C4: a refused act on a near object says why, in the game's own words; a far one does not.
def test_a_refused_act_on_a_near_object_says_why_in_the_games_words():
    refusals = [{"text_key": "90", "reason_key": "91"}]
    near = _obj("36", "4", 1.5, refusals=refusals)
    far = _obj("37", "5", 20.0, refusals=refusals)
    listed = options({"room": "4", "objects": [near, far]}, resolve=TEXTS.get, room="4")
    assert listed[0]["refused"] == ["Use the toilet: refused: The toilet is dirty."]
    assert "refused" not in listed[1]


# C12: acts cut for one object are said on that object; the probe's dropped objects join the cut line.
def test_the_acts_cut_per_object_and_the_probes_dropped_objects_are_named():
    menu = {"room": "4", "dropped": {"objects": 4, "rooms": ["7"]},
            "objects": [_obj("38", "4", 1.0, acts_cut=3)]}
    cut = {}
    listed = options(menu, room="4", cut=cut)
    assert listed[0]["acts_cut"] == 3
    assert cut == {"objects": 4, "rooms": ["room 7"]}


def test_an_object_with_no_cut_says_nothing_about_acts_cut():
    listed = options({"room": "4", "objects": [_obj("39", "4", 1.0)]}, room="4")
    assert "acts_cut" not in listed[0]


# G1: a pie-menu choice is its own act; its guid64 carries the variant, and its words are its own.
def test_a_pie_menu_choice_is_its_own_act_with_its_variant_in_the_guid():
    menu = {"room": "4", "objects": [_obj("40", "4", 1.0, acts=[
        {"guid64": "7040", "name": "fridge_Snack", "text_key": "92", "variant": 2},
        {"guid64": "7040", "name": "fridge_Snack", "text_key": "93", "variant": 3},
        {"guid64": "7041", "name": "fridge_Cook", "text_key": "94"}])]}
    listed = options(menu, resolve=TEXTS.get, room="4")[0]["acts"]
    assert [act["guid64"] for act in listed] == ["7040v2", "7040v3", "7041"]
    assert [act["text"] for act in listed] == ["Snack", "Snack, sweet", "Snack, savoury"]


# A7: every enabled row of a picker is listed; past the probe's 40 the count says how many are shown.
def _picker(enabled, hold=None):
    rows = [{"option_id": str(10 + index), "name_key": "4", "enabled": True} for index in range(enabled)]
    dialog = {"dialog_id": "600", "held": True, "cause": "hers", "owner_id": "100", "title_key": "1",
              "responses": [{"response": "ok", "text_key": "2"}], "rows": rows}
    if hold is not None:
        dialog["hold_left_s"] = hold
    return {"presence": [{"id": "100", "is_body": True, "name": "Her"}], "dialogs": {"open": [dialog]}}


def test_every_enabled_row_of_a_picker_is_listed_up_to_40_and_the_count_says_how_many():
    assert len(dialog_options(_picker(15), TEXTS.get)[0]["acts"]) == 15  # the rows; the ok is the row pick
    many = dialog_options(_picker(45), TEXTS.get)[0]
    assert len([act for act in many["acts"] if act["guid64"] != "ok"]) == 40
    assert many["where"] == "asked now, 40 of 45 choices"


# hold_left_s: the time left on a held window rides with the window (whole seconds).
def test_a_held_windows_time_left_rides_with_it():
    assert dialog_options(_picker(2, hold=120), TEXTS.get)[0]["hold_left_s"] == 120
    assert "hold_left_s" not in dialog_options(_picker(2), TEXTS.get)[0]


# Her own response name for a custom button ("response_<N>") reads as a choice, never a bare number.
def test_a_custom_response_is_a_choice_with_its_number_named():
    row = {"presence": [{"id": "100", "is_body": True, "name": "Her"}], "dialogs": {"open": [
        {"dialog_id": "601", "held": True, "cause": "hers", "owner_id": "100", "title_key": "1",
         "responses": [{"response": "response_3", "text_key": None}], "rows": []}]}}
    assert dialog_options(row, TEXTS.get)[0]["acts"] == [
        {"ref": "a1", "guid64": "response_3", "text": "choice 3"}]
