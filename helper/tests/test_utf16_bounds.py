"""NB-4 residual: every option field Natalis measures stays within its cap in UTF-16 units.

Natalis reads the observation with JavaScript strings (UTF-16 code units) and refuses the whole
observation with 400 when one field is over its cap. The helper's own cuts are in code points,
so an emoji-heavy value can pass the helper and fail Natalis. Each test gives one capped field
an emoji-heavy value and asserts the helper's output fits; its ASCII control shows the old
result is unchanged.
"""
from domus_helper.acts import _probe_room_name, _refusals, _serves_of, _state_word, options

EMOJI = "\U0001F600"


def _units(text):
    """What Natalis measures: UTF-16 code units."""
    return len(text.encode("utf-16-le")) // 2


def _no_lone_surrogate(*texts):
    for text in texts:
        text.encode("utf-8")


def _phone_menu(excluded, acts=None):
    phone = {"object_id": "11", "class": "object_phone", "phone": True, "distance_m": 0.0, "same_room": True,
             "acts": acts if acts is not None else [{"guid64": "4242", "name": "phone_Read", "text_key": None}]}
    return {"menu_rev": 1, "room": "4", "objects": [phone], "excluded_phone": excluded}


def _room_object(room="1"):
    return {"object_id": "2", "class": "object_thing_2", "room": room, "distance_m": 2.0,
            "same_room": room == "1",
            "acts": [{"guid64": "7001", "name": "thing_Read", "text_key": None}]}


# left_out: a phone line is at most 160 units (Natalis LEFT_OUT_LINE_MAX).
def test_a_phone_left_out_line_is_at_most_160_utf16_units():
    [entry] = options(_phone_menu([{"name": EMOJI * 80, "why": "hidden"}]))
    [line] = entry["left_out"]
    assert _units(line) <= 160
    _no_lone_surrogate(line)


def test_a_phone_left_out_line_of_ascii_is_unchanged():
    [entry] = options(_phone_menu([{"name": "phone_Hidden", "why": "hidden"}]))
    assert entry["left_out"] == ["phone Hidden: left out: the game keeps it out of your menu"]


def test_a_left_out_remainder_line_is_at_most_160_utf16_units():
    reason = EMOJI * 75
    excluded = [{"name": "phone_Act%02d" % index, "why": reason} for index in range(13)]
    [entry] = options(_phone_menu(excluded))
    assert len(entry["left_out"]) <= 12
    assert any(" more acts: left out: " in line for line in entry["left_out"])
    for line in entry["left_out"]:
        assert _units(line) <= 160
        _no_lone_surrogate(line)


def test_a_capped_left_out_remainder_line_is_at_most_160_utf16_units():
    reason = EMOJI * 75
    excluded = [{"name": "phone_Act%02d" % index, "why": reason} for index in range(12)]
    # Two acts with the same words make one helper excluded line, so the 12 phone lines plus it overflow the cap.
    acts = [{"guid64": "4242", "name": "phone_Read", "text_key": None},
            {"guid64": "4243", "name": "phone_Read", "text_key": None}]
    [entry] = options(_phone_menu(excluded, acts))
    assert len(entry["left_out"]) <= 12
    for line in entry["left_out"]:
        assert _units(line) <= 160
        _no_lone_surrogate(line)


def test_a_left_out_remainder_line_of_ascii_is_unchanged():
    excluded = [{"name": "phone_Act%02d" % index, "why": "hidden"} for index in range(13)]
    [entry] = options(_phone_menu(excluded))
    assert entry["left_out"][-1] == "2 more acts: left out: the game keeps it out of your menu"


# refused: a line is at most 240 units (Natalis REFUSED_LINE_MAX).
def test_a_refusal_line_is_at_most_240_utf16_units():
    item = {"refusals": [{"text_key": "act", "reason_key": "reason"}]}
    texts = {"act": EMOJI * 80, "reason": EMOJI * 130}
    [line] = _refusals(item, texts.get, True)
    assert _units(line) <= 240
    _no_lone_surrogate(line)


def test_a_refusal_line_of_ascii_is_unchanged():
    item = {"refusals": [{"text_key": "90", "reason_key": "91"}]}
    assert _refusals(item, {"90": "Use the toilet", "91": "The toilet is dirty."}.get, True) == [
        "Use the toilet: refused: The toilet is dirty."]


# room: a label is at most 64 units (Natalis ROOM_MAX), in an option and in a cut.
def test_a_room_label_is_at_most_64_utf16_units_in_options_and_in_a_cut():
    label = EMOJI * 33
    [entry] = options({"room": "1", "objects": [_room_object()]}, room="1", room_labels={"1": label})
    assert _units(entry["room"]) <= 64
    _no_lone_surrogate(entry["room"])
    cut_name = _probe_room_name("1", {"1": label})
    assert _units(cut_name) <= 64
    _no_lone_surrogate(cut_name)


def test_a_room_label_of_ascii_is_unchanged():
    label = "the back room with the table"
    [entry] = options({"room": "1", "objects": [_room_object()]}, room="1", room_labels={"1": label})
    assert entry["room"] == label
    assert _probe_room_name("1", {"1": label}) == label
    assert _probe_room_name("1", {"1": "x" * 70}) == "x" * 64


# states: a word is at most 40 units (Natalis STATE_MAX), or it is dropped.
def test_a_state_word_is_at_most_40_utf16_units_or_dropped():
    word = _state_word(EMOJI * 21)
    assert word is None or _units(word) <= 40
    if word is not None:
        _no_lone_surrogate(word)
    item = dict(_room_object(), states=[EMOJI * 21])
    [entry] = options({"room": "1", "objects": [item]}, room="1")
    for state in entry.get("states") or []:
        assert _units(state) <= 40
        _no_lone_surrogate(state)


def test_a_state_word_of_ascii_is_unchanged():
    assert _state_word("Freshness_Spoiled") == "Spoiled"
    assert _state_word("x" * 41) is None
    item = dict(_room_object(), states=["Spoiled"])
    [entry] = options({"room": "1", "objects": [item]}, room="1")
    assert entry["states"] == ["Spoiled"]


# serves: a need id is at most 32 units (Natalis NEED_ID_MAX), or it is dropped.
def test_a_serves_id_is_at_most_32_utf16_units_or_dropped():
    need = EMOJI * 17
    served = _serves_of({"acts": [{"serves": [need]}]})
    assert all(_units(value) <= 32 for value in served)
    _no_lone_surrogate(*served)
    item = _room_object()
    item["acts"][0]["serves"] = [need]
    [entry] = options({"room": "1", "objects": [item]}, room="1")
    for value in entry.get("serves") or []:
        assert _units(value) <= 32
        _no_lone_surrogate(value)


def test_a_serves_id_of_ascii_is_unchanged():
    assert _serves_of({"acts": [{"serves": ["x" * 32, "y" * 33]}]}) == ["x" * 32]
    item = _room_object()
    item["acts"][0]["serves"] = ["bladder"]
    [entry] = options({"room": "1", "objects": [item]}, room="1")
    assert entry["serves"] == ["bladder"]
