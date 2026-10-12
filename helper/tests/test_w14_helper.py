"""W14 (helper, Worker D): her menu when the probe writes a near part (D3: a near part never replaces the whole menu, a
whole one does, and a set of parts is one revision in one count of parts), the choices that are still coming (S2), and
the game's words for her body (D8). Every row is invented; the game and Mint are
fakes."""
import json
import re
from pathlib import Path

import pytest

from domus_helper.acts import NEAR_M, MenuParts, merge_near
from domus_helper.contract import validate_observation
from domus_helper.thalamus.observation import build
from domus_helper.thalamus.types import Percept
from test_bridge_thalamus import BUILD, WALL, _append, _bridge, _data, _lineage, _snap


def _obj(object_id, distance=None, same_room=None, phone=None, guid=None):
    return {"object_id": str(object_id), "definition_id": None, "class": "object_test_chair", "distance_m": distance,
            "same_room": same_room, "room": "4", "reach": True, "phone": phone, "spot": None, "level": None,
            "acts": [{"guid64": str(guid or int(object_id) * 10), "name": "test_act", "text_key": None,
                      "variant": None}],
            "on_lot": True, "acts_cut": 0, "refusals": None}


def _menu(rev, objects, part=0, parts=1, near=None, **extra):
    menu = {"menu_rev": rev, "room": "4", "objects": objects, "tested": 3, "refused": 0, "build_ms": 1.0,
            "part": part, "parts": parts, "refused_phone": None, "excluded_phone": None, "dropped": None,
            "spot_stages": None}
    if near:
        menu["near"] = True
    menu.update(extra)
    return menu


def _ids(payload):
    return [item["object_id"] for item in payload["objects"]]


# ----------------------------------------------------------------- D3: the merge rule and the set keys

def test_a_near_part_keeps_the_far_objects_of_the_last_whole_menu():
    whole = _menu(5, [_obj(11, 2.0, True), _obj(22, 9.0, False), _obj(33, phone=True)])
    near = _menu(6, [_obj(11, 1.0, True, guid=110), _obj(44, 3.0, True)], near=True)
    shown = merge_near(near, whole)
    assert _ids(shown) == ["11", "44", "22"]
    assert shown["objects"][0]["acts"][0]["guid64"] == "110"  # the near part's own read wins
    assert shown["menu_rev"] == 6


def test_the_far_rule_is_more_than_near_m_away_and_not_her_room_or_phone():
    whole = _menu(5, [_obj(1, NEAR_M, False), _obj(2, NEAR_M + 0.5, False), _obj(3, None, False),
                      _obj(4, 9.0, True), _obj(5, phone=True), _obj(6, 9.0, None), _obj(7, 9.0, False)])
    shown = merge_near(_menu(6, [], near=True), whole)
    assert _ids(shown) == ["2", "6", "7"]


def test_a_near_part_with_no_whole_menu_is_the_near_part_alone():
    near = _menu(6, [_obj(44, 3.0, True)], near=True)
    assert _ids(merge_near(near, None)) == ["44"]


def test_a_three_part_write_after_a_seventeen_part_write_of_the_same_revision_never_mixes_pieces():
    parts = MenuParts()
    first = [_obj(100 + index) for index in range(5)]
    assert parts.take("s", _menu(7, first[:1], part=0, parts=17)) is None
    for index in range(1, 5):
        assert parts.take("s", _menu(7, first[index:index + 1], part=index, parts=17)) is None
    second = [_obj(200 + index) for index in range(3)]
    assert parts.take("s", _menu(7, second[:1], part=0, parts=3)) is None
    assert parts.take("s", _menu(7, second[1:2], part=1, parts=3)) is None
    whole = parts.take("s", _menu(7, second[2:3], part=2, parts=3))
    assert _ids(whole) == ["200", "201", "202"]
    assert "near" not in whole
    # The 17-part set's remaining pieces start a new set; nothing of the 3-part write is in it.
    assert parts.take("s", _menu(7, [_obj(105)], part=5, parts=17)) is None


def test_a_near_set_and_a_whole_set_of_the_same_revision_do_not_mix():
    parts = MenuParts()
    assert parts.take("s", _menu(8, [_obj(1)], part=0, parts=2)) is None
    near = parts.take("s", _menu(8, [_obj(9, 1.0, True)], part=0, parts=1, near=True))
    assert near is not None and near.get("near") is True and _ids(near) == ["9"]
    # The near write started a new set, so the whole set's first piece is gone: its second piece waits alone.
    assert parts.take("s", _menu(8, [_obj(2)], part=1, parts=2)) is None
    whole = parts.take("s", _menu(8, [_obj(1)], part=0, parts=2))
    assert _ids(whole) == ["1", "2"]
    assert "near" not in whole


# ----------------------------------------------------------------- D3: the bridge keeps what she sees

def _menu_row(seq, e2, session="sess-1"):
    return {"event_kind": "act_menu", "written_sequence": seq, "wall_timestamp_ms": WALL,
            "monotonic_ns": WALL * 1_000_000, "telemetry_session_id": session, "sims_build": BUILD,
            "probe_version": "2.41.0", "e2": e2}


def _tick(bridge, mono, wall):
    mono["ms"] = wall
    bridge.tick(wall)


def test_the_bridge_shows_the_near_part_with_the_far_rooms_and_a_whole_menu_replaces_all(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    mono = {"ms": WALL}
    bridge = _bridge(paths, mono)
    _append(paths, [_lineage(1, WALL), _menu_row(2, _menu(5, [_obj(11, 2.0, True), _obj(22, 9.0, False)]))])
    _tick(bridge, mono, WALL)
    assert _ids(bridge._menu["payload"]) == ["11", "22"]
    _append(paths, [_menu_row(3, _menu(6, [_obj(11, 1.0, True), _obj(44, 3.0, True)], near=True))])
    _tick(bridge, mono, WALL + 1500)
    assert _ids(bridge._menu["payload"]) == ["11", "44", "22"]
    _append(paths, [_menu_row(4, _menu(7, [_obj(55, 1.0, True)]))])
    _tick(bridge, mono, WALL + 3000)
    assert _ids(bridge._menu["payload"]) == ["55"]


def test_a_near_part_of_another_session_does_not_bring_its_far_rooms(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    mono = {"ms": WALL}
    bridge = _bridge(paths, mono)
    _append(paths, [_lineage(1, WALL),
                    _menu_row(2, _menu(5, [_obj(22, 9.0, False)]), session="old-session"),
                    _menu_row(3, _menu(6, [_obj(44, 3.0, True)], near=True))])
    _tick(bridge, mono, WALL)
    assert _ids(bridge._menu["payload"]) == ["44"]


def test_the_whole_menu_of_the_session_survives_a_restart_for_a_near_part(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    mono = {"ms": WALL}
    bridge = _bridge(paths, mono)
    _append(paths, [_lineage(1, WALL), _menu_row(2, _menu(5, [_obj(22, 9.0, False)]))])
    _tick(bridge, mono, WALL)
    bridge._persist_thalamus(WALL + 1000)
    again = _bridge(paths, mono)
    _append(paths, [_menu_row(3, _menu(6, [_obj(44, 3.0, True)], near=True))])
    _tick(again, mono, WALL + 2000)
    assert _ids(again._menu["payload"]) == ["44", "22"]


# ----------------------------------------------------------------- S2: the choices that are still coming

def test_the_view_says_the_choices_are_pending_until_a_whole_menu_has_come(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    mono = {"ms": WALL}
    bridge = _bridge(paths, mono)
    _append(paths, [_lineage(1, WALL), _snap(2, "ok", WALL, 10)])
    _tick(bridge, mono, WALL)
    assert bridge._obs_ctx(WALL)["choices_pending"] is True
    _append(paths, [_menu_row(3, _menu(5, [_obj(11, 2.0, True)])), _snap(4, "low", WALL, 20)])
    _tick(bridge, mono, WALL + 1500)
    assert bridge._obs_ctx(WALL + 1500)["choices_pending"] is False


def test_a_near_part_alone_does_not_end_the_pending_choices(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    mono = {"ms": WALL}
    bridge = _bridge(paths, mono)
    _append(paths, [_lineage(1, WALL), _menu_row(2, _menu(6, [_obj(44, 3.0, True)], near=True))])
    _tick(bridge, mono, WALL)
    assert _ids(bridge._menu["payload"]) == ["44"]
    assert bridge._obs_ctx(WALL)["choices_pending"] is True


class _Decision(object):
    def __init__(self):
        self.percepts = [(Percept("need", "hunger", "", "low", urgency="wake", lineage="3:abc",
                                  facts=(("value", "1"), ("band", "low"))), 0.5)]
        self.reason = "test"
        self.fired = True


def _ctx(pending):
    return {"helper_session": "h", "obs_seq": 1, "slot_id": None, "guid": None, "lineage_class": "PENDING",
            "row": {"telemetry_session_id": "s", "wall_timestamp_ms": WALL}, "event_row": None,
            "choices_pending": pending}


def test_the_observation_carries_choices_pending_true_only_while_it_is_true():
    pending = build(_Decision(), _ctx(True))
    assert pending["choices_pending"] is True
    assert "choices_pending" not in build(_Decision(), _ctx(False))
    assert validate_observation(dict(pending, expires_at_ms=WALL + 1000, source_time_ms=WALL), WALL)["choices_pending"] is True


def test_the_contract_refuses_a_choices_pending_that_is_not_true():
    from domus_helper.contract import ContractError
    base = build(_Decision(), _ctx(False))
    base.update(source_time_ms=WALL, expires_at_ms=WALL + 1000)
    with pytest.raises(ContractError):
        validate_observation(dict(base, choices_pending=False), WALL)
    with pytest.raises(ContractError):
        validate_observation(dict(base, choices_pending="yes"), WALL)


# ----------------------------------------------------------------- D5: room labels, never cut mid-word

def _room_thing(object_id, room, key):
    return {"object_id": str(object_id), "name_key": key, "where": "room", "room_id": room}


def test_a_room_label_takes_as_many_names_as_fit_and_never_cuts_a_name_short():
    from domus_helper import reach
    names = {"k1": "Test Armchair Brocade Extraordinary", "k2": "Test Lamp Standing", "k3": "Test Sink",
             "k4": "Test Armchair Brocade Extraordinary Walnut Rocking Chair"}
    raw = [_room_thing(1, "4", "k1"), _room_thing(2, "4", "k2"), _room_thing(3, "4", "k3"),
           _room_thing(4, "5", "k1"), _room_thing(5, "6", "k4")]
    labels = reach.room_labels(raw, resolve=names.get)
    # Three names are too long, two are too long, one fits: "the room with the A".
    assert labels["4"] == "the room with the Test Armchair Brocade Extraordinary"
    # Room 5 has the same base as room 4, so the " (2)" rule numbers it. Room 6's long name is cut at its last whole word.
    assert labels["5"] == "the room with the Test Armchair Brocade Extraordinary (2)"
    assert labels["6"] == "the room with the Test Armchair Brocade Extraordinary\u2026"


def test_a_room_label_too_long_even_for_one_name_stops_at_its_last_whole_word_with_an_ellipsis():
    from domus_helper import reach
    names = {"k4": "Test Armchair Brocade Extraordinary Walnut Rocking Chair"}
    labels = reach.room_labels([_room_thing(5, "6", "k4")], resolve=names.get)
    assert labels == {"6": "the room with the Test Armchair Brocade Extraordinary\u2026"}
    assert len(labels["6"]) <= reach.WHERE_LIMIT - 6


def test_a_cut_label_is_a_whole_word_prefix_of_the_name_and_two_equal_labels_are_numbered():
    from domus_helper import reach
    text = "the room with the Test Armchair Brocade Extraordinary Walnut Rocking Chair"
    names = {"k4": "Test Armchair Brocade Extraordinary Walnut Rocking Chair"}
    raw = [_room_thing(5, "6", "k4"), _room_thing(6, "7", "k4")]
    labels = reach.room_labels(raw, resolve=names.get)
    assert labels["6"] != labels["7"]
    assert labels["7"].endswith(" (2)")
    base = labels["6"][:-1]
    assert text.startswith(base) and text[len(base)] == " "
    assert all(len(label) <= reach.WHERE_LIMIT for label in labels.values())


def test_a_label_that_fits_is_kept_whole():
    from domus_helper import reach
    names = {"k1": "Test Bed", "k2": "Test Lamp"}
    labels = reach.room_labels([_room_thing(1, "3", "k1"), _room_thing(2, "3", "k2")], resolve=names.get)
    assert labels == {"3": "the room with the Test Bed and the Test Lamp"}


# ----------------------------------------------------------------- D6: a debug or empty game name is not shown

def test_a_menu_object_with_a_debug_or_empty_game_name_is_named_by_its_class():
    from domus_helper import acts
    item = {"object_id": "5", "definition_id": 77, "class": "object_test_bookshelf"}
    catalog = lambda definition: {"name_key": "900"}
    for text in ("** DEBUG **", "", "   ", "*Starred Test Name", "Test DEBUG Bookshelf"):
        assert acts._object_name(item, {"900": text}.get, catalog) == "object test bookshelf", text
    assert acts._object_name(item, {"900": "Test Bookshelf"}.get, catalog) == "Test Bookshelf"


def test_a_thing_with_a_debug_name_takes_its_definition_name_and_one_with_neither_is_left_out():
    from domus_helper import reach
    from domus_helper.acts import RefBook
    names = {"901": "** DEBUG **", "902": "Test Lamp", "903": "*Starred"}
    catalog = lambda definition: {"name_key": "902"} if definition == 77 else None
    assert reach._thing_name({"object_id": 9, "name_key": "901", "definition_id": 77}, names.get, catalog) == "Test Lamp"
    assert reach._thing_name({"object_id": 9, "name_key": "903", "definition_id": 78}, names.get, catalog) is None
    raw = [{"object_id": "9", "name_key": "901", "definition_id": 77, "where": "inventory"}]
    things = reach.list_words("things", raw, refs=RefBook(), resolve=names.get, catalog=catalog)
    assert [thing["name"] for thing in things] == ["Test Lamp"]


# ----------------------------------------------------------------- D7: every left-out code has its plain words

def test_each_left_out_code_the_probe_sends_is_said_in_plain_words_and_an_unknown_code_is_shown_as_itself():
    from domus_helper.acts import options
    from domus_helper.acts import RefBook
    codes = ["pie_picker", "deny_name", "travel", "not_user_directed", "hidden", "a_new_code"]
    phone = {"object_id": "11", "class": "object_phone", "phone": True, "distance_m": 0.0, "same_room": True,
             "acts": [{"guid64": "4242", "name": "phone_Read", "text_key": None}]}
    menu = {"menu_rev": 1, "room": "4", "objects": [phone], "refused_phone": None,
            "excluded_phone": [{"name": "phone_Act%d" % index, "why": code} for index, code in enumerate(codes)]}
    listed = options(menu, resolve={}.get, refs=RefBook())
    lines = listed[0]["left_out"]
    assert lines == [
        "phone Act0: left out: it opens a menu of choices, not an act",
        "phone Act1: left out: a debug or cheat act",
        "phone Act2: left out: it takes you off the lot",
        "phone Act3: left out: only the game starts it, not you",
        "phone Act4: left out: the game keeps it out of your menu",
        "phone Act5: left out: a_new_code"]
    assert not any(code in " ".join(lines) for code in ("deny_name", "not_user_directed", "pie_picker"))


def test_the_left_out_words_never_show_the_debug_code_or_an_internal_name():
    from domus_helper.acts import LEFT_OUT_REASONS, _phone_left_out
    assert set(LEFT_OUT_REASONS) == {"pie_picker", "deny_name", "travel", "not_user_directed", "hidden"}
    for words in LEFT_OUT_REASONS.values():
        assert "_" not in words and "DEBUG" not in words and words[0].islower()
    lines = _phone_left_out({"excluded_phone": [{"name": "phone_Cheat", "why": "deny_name"}]}, {}.get)
    assert lines == ["phone Cheat: left out: a debug or cheat act"]


# ----------------------------------------------------------------- D8: her body is "you" in every text that reaches her

def test_the_words_that_reach_her_say_you_for_her_body():
    from domus_helper import acts
    from domus_helper.acts import RefBook, options
    assert acts.NO_WAY == "the game sees no way for you to get there from where you are now"
    phone = {"object_id": "900", "class": "object_phone", "phone": True, "distance_m": None, "same_room": None,
             "acts": [{"guid64": "6001", "name": "phone_Sample", "text_key": None}]}
    listed = options({"menu_rev": 1, "room": "4", "objects": [phone]}, resolve={}.get, refs=RefBook())
    assert listed[0]["where"] == "with you"


def test_no_string_she_or_her_is_in_the_helper_text_except_the_user_screens_and_ids():
    """A guard: the helper's string literals (not docstrings) never say "she" or "her" for her body. The overlay pages
    are the User's screen (they keep her name), and "queue:her" and "hers" are an id and a probe value."""
    import io
    import tokenize
    from pathlib import Path
    pattern = re.compile(r"\b(she|her|hers|herself|She|Her|Hers)\b")
    allowed_files = {"overlay.py", "overlay_page.py", "talk.py"}
    allowed_strings = {'"queue:her"', '"hers"'}
    root = Path(__file__).resolve().parents[1] / "domus_helper"
    found = []
    for path in sorted(root.rglob("*.py")):
        if "vendor" in path.parts or path.name in allowed_files:
            continue
        for tok in tokenize.generate_tokens(io.StringIO(path.read_text(encoding="utf-8")).readline):
            if tok.type == tokenize.STRING and not tok.string.startswith(('"""', "'''")):
                if tok.string not in allowed_strings and pattern.search(tok.string):
                    found.append((path.name, tok.start[0], tok.string[:60]))
    assert found == []

