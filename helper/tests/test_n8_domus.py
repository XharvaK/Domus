"""N8 (Domus after the first live play): the helper's fixes for the menu, the refs, the pictures and the words.
Fixtures are invented; tuning names are the game's own interaction names, and no game text appears here."""
import json

import pytest

from domus_helper.acts import OPENS_SCREEN, WITHHELD_SEED, MenuParts, RefBook, dialog_options, options, queue_options
from domus_helper.contract import ContractError, validate_observation


def phone_menu(*names):
    acts = [{"guid64": str(5000 + index), "name": name, "text_key": None} for index, name in enumerate(names)]
    return {"room": "1", "objects": [{"object_id": "21", "class": "object_phone", "distance_m": 0.5,
                                      "same_room": True, "acts": acts}]}


def test_the_seed_names_open_a_screen_before_the_notebook_has_seen_them():
    acts = options(phone_menu("phone_PlanEvent", "phone_CallOver_EventNPC"))[0]["acts"]
    assert acts[0]["opens"] == OPENS_SCREEN
    assert "opens" not in acts[1]
    assert [act["guid64"] for act in acts] == ["5000", "5001"]


def test_the_seed_covers_the_planner_create_a_sim_change_sim_and_outfit_screens():
    for name in ("phone_PlanEvent", "terrain-createsim_female-adult", "terrain-createsim_male-teen",
                 "dresser_ChangeSim", "PlanOutfit", "tent_PlanOutfit", "dresser_TryOnOutfits_Start",
                 "Dresser_TryOnOutfit_00"):
        assert name in WITHHELD_SEED
        assert options(phone_menu(name))[0]["acts"][0]["opens"] == OPENS_SCREEN


# F3: stable refs for one helper session.
def thing(object_id, *acts, distance=1.0):
    """An object in the probe's menu: acts are (guid64, tuning name) pairs."""
    return {"object_id": object_id, "class": "object_thing", "distance_m": distance, "same_room": True,
            "acts": [{"guid64": guid, "name": name, "text_key": None} for guid, name in acts]}


def refs_of(result):
    return {(item["object_id"], act["guid64"]): act["ref"] for item in result for act in item["acts"]}


def test_a_ref_keeps_its_meaning_as_objects_reorder_appear_vanish_and_come_back():
    book = RefBook()

    def view(*objects):
        return refs_of(options({"room": "1", "objects": list(objects)}, refs=book))

    a = thing("21", ("4001", "Read"), ("4002", "Sit"))
    b = thing("22", ("4003", "Wave"))
    first = view(a, b)
    assert first == {("21", "4001"): "a1", ("21", "4002"): "a2", ("22", "4003"): "a3"}
    assert view(b, a) == first
    third = view(b, a, thing("23", ("4004", "Poke")))
    assert third[("23", "4004")] == "a4" and all(third[key] == first[key] for key in first)
    fourth = view(b, thing("23", ("4004", "Poke")))
    assert ("21", "4001") not in fourth and fourth[("23", "4004")] == "a4"
    fifth = view(thing("24", ("4005", "Hum")), a, b)
    assert fifth[("21", "4001")] == "a1" and fifth[("21", "4002")] == "a2"
    assert fifth[("24", "4005")] == "a5"  # a new number: a1 is never given to something else


def test_a_queue_item_and_a_question_row_keep_their_refs_when_the_views_change():
    book = RefBook()
    queue_row = {"interactions": {"observed": [{"interaction_id": "901", "membership": "RUNNING",
                                                "affordance_text": "<class 'sims.Stir'>"}]}}
    question = {"telemetry_session_id": "s", "dialogs": {"open": [{
        "dialog_id": "51", "held": True, "cause": "hers", "title_key": None, "text_key": None,
        "rows": [{"option_id": "7", "name_key": None, "enabled": True, "price": None}],
        "responses": [{"response": "cancel", "text_key": None}]}]}}
    first = dialog_options(question, refs=book) + queue_options(queue_row, refs=book)
    assert [act["ref"] for entry in first for act in entry["acts"]] == ["a1", "a2", "a3"]
    again = dialog_options(question, refs=book) + queue_options(queue_row, refs=book)
    assert [act["ref"] for entry in again for act in entry["acts"]] == ["a1", "a2", "a3"]
    assert queue_options({}, refs=book) == []
    back = queue_options(queue_row, refs=book)
    assert back[0]["acts"][0]["ref"] == "a3"


# F4 part 2: the whole lot, identical texts once, rooms and nearness, and a cut that is named.
def lot(objects=150, rooms=8, acts=2):
    """An invented lot: objects spread over rooms; each object offers acts (guid64 by object and index)."""
    menu_objects = []
    for index in range(objects):
        room = str(index % rooms + 1)
        menu_objects.append({"object_id": str(1000 + index), "class": "object_thing", "room": room,
                             "distance_m": float(index % 40) + 0.5, "same_room": room == "1",
                             "acts": [{"guid64": str(50000 + index * 10 + number), "name": "thing_Act%d" % number,
                                       "text_key": "k%d" % number} for number in range(acts)]})
    return {"room": "1", "objects": menu_objects}


ROOM_LABELS = {"%d" % number: "Room %d" % number for number in range(1, 9)}


def test_identical_act_texts_on_one_object_are_listed_once_with_the_first_ref():
    texts = {"lamp": "All Lights"}
    menu = {"room": "1", "objects": [{"object_id": "31", "class": "object_lamp", "room": "1", "distance_m": 1.0,
                                      "same_room": True,
                                      "acts": [{"guid64": str(6000 + n), "name": "lamp_All%d" % n, "text_key": "lamp"}
                                               for n in range(4)]}]}
    acts = options(menu, texts.get)[0]["acts"]
    assert [(act["guid64"], act["text"]) for act in acts] == [("6000", "All Lights")]
    assert acts[0]["ref"] == "a1"


def test_each_object_carries_its_room_when_known_and_whether_it_is_near():
    menu = {"room": "1", "objects": [
        {"object_id": "41", "class": "object_a", "room": "1", "distance_m": 9.0, "same_room": True,
         "acts": [{"guid64": "7001", "name": "a_Read", "text_key": None}]},
        {"object_id": "42", "class": "object_b", "room": "2", "distance_m": 3.5, "same_room": False,
         "acts": [{"guid64": "7002", "name": "b_Sit", "text_key": None}]},
        {"object_id": "43", "class": "object_c", "room": "3", "distance_m": 12.0, "same_room": False,
         "acts": [{"guid64": "7003", "name": "c_Wave", "text_key": None}]}]}
    result = options(menu, room="1", room_labels={"1": "Kitchen", "2": "Hall"})
    assert [(item["object_id"], item.get("room"), item["near"]) for item in result] == [
        ("41", "Kitchen", True), ("42", "Hall", True), ("43", None, False)]
    assert "room" not in result[2]


def test_a_lot_of_150_objects_in_8_rooms_is_all_listed_with_stable_refs():
    book = RefBook()
    menu = lot(acts=1)
    cut = {}
    result = options(menu, room="1", room_labels=ROOM_LABELS, refs=book, cut=cut)
    assert len(result) == 150 and cut == {}
    assert sorted({item["room"] for item in result}) == sorted(ROOM_LABELS.values())
    refs = refs_of(result)
    assert len(set(refs.values())) == len(refs) == 150
    again = refs_of(options(menu, room="1", room_labels=ROOM_LABELS, refs=book))
    assert again == refs
    assert len(json.dumps(result, separators=(",", ":")).encode("utf-8")) <= 32768
    two = options(lot(acts=2), room="1", room_labels=ROOM_LABELS, cut={})
    assert len(two) == 150 and len(json.dumps(two, separators=(",", ":")).encode("utf-8")) <= 32768


def test_more_than_160_objects_or_too_many_bytes_are_cut_and_named_never_silently():
    cut = {}
    result = options(lot(objects=170, acts=1), room="1", room_labels=ROOM_LABELS, cut=cut)
    assert len(result) == 160
    assert cut["objects"] == 10
    assert set(cut["rooms"]) <= set(ROOM_LABELS.values())
    wide = lot(objects=150, acts=6)
    for item in wide["objects"]:
        for act in item["acts"]:
            act["name"] = "x" * 120 + act["name"][-6:]
    cut = {}
    result = options(wide, room="1", room_labels=ROOM_LABELS, cut=cut)
    assert len(json.dumps(result, separators=(",", ":")).encode("utf-8")) <= 32768
    assert cut["objects"] == 150 - len(result) > 0
    assert cut == {"objects": cut["objects"], "rooms": cut["rooms"]}


def test_the_contract_carries_160_options_and_the_cut_within_32_kib():
    cut = {}
    result = options(lot(objects=170, acts=1), room="1", room_labels=ROOM_LABELS, cut=cut)
    body = {"v": 1, "observation_id": "h.1", "world": "slot8", "branch": "b", "session": "s", "attachment": "h",
            "body": "1", "snapshot": "1", "seq": 1, "source_time_ms": 1000, "expires_at_ms": 2000,
            "lineage_class": "CURRENT", "percepts": [{"kind": "need", "salience": 0.1, "facts": {}}],
            "options": result, "options_cut": cut}
    normalized = validate_observation(body, 1500)
    assert normalized["options"] == result and normalized["options_cut"] == cut
    with pytest.raises(ContractError):
        validate_observation(dict(body, options=[{"object": "x"}] * 161), 1500)
    with pytest.raises(ContractError):
        validate_observation(dict(body, options_cut={"objects": "ten"}), 1500)


# F4 part 1 on the helper side: a menu arrives in parts and is shown once whole.
def test_a_menu_in_parts_is_shown_only_once_all_its_parts_have_come_in_order():
    parts = MenuParts()
    first = {"menu_rev": 3, "room": "1", "tested": 4, "refused": 1, "build_ms": 2.0, "part": 0, "parts": 3,
             "objects": [{"object_id": "1"}]}
    second = dict(first, part=1, objects=[{"object_id": "2"}])
    third = dict(first, part=2, objects=[{"object_id": "3"}])
    assert parts.take("s", third) is None
    assert parts.take("s", first) is None
    whole = parts.take("s", second)
    assert [item["object_id"] for item in whole["objects"]] == ["1", "2", "3"]
    assert (whole["menu_rev"], whole["room"], whole["part"], whole["parts"]) == (3, "1", 0, 1)


def test_a_lone_part_of_an_older_menu_is_dropped_by_the_next_revision_and_an_old_row_is_whole():
    parts = MenuParts()
    assert parts.take("s", {"menu_rev": 3, "room": None, "objects": [{"object_id": "1"}], "part": 0,
                            "parts": 2}) is None
    newer = {"menu_rev": 4, "room": None, "objects": [{"object_id": "9"}], "part": 0, "parts": 1}
    assert [item["object_id"] for item in parts.take("s", newer)["objects"]] == ["9"]
    assert parts.take("s", {"menu_rev": 5, "room": None, "objects": [], "part": 1, "parts": 2}) is None
    assert parts.take("s", {"menu_rev": 5, "room": None, "objects": [], "part": 5, "parts": 2}) is None
    assert parts.take("s", {"menu_rev": 1, "room": None, "objects": [{"object_id": "7"}]})["objects"] == [
        {"object_id": "7"}]
