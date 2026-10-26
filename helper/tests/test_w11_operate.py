"""2.38.0 (W11 H1, H2): identical objects are one menu entry that says how many there are and in how many rooms;
a Sim she hears on her lot is offered, and says so in where; a Sim off her lot is still not offered.

Fixtures are invented: object classes and act names stand for no game text."""
import json

from domus_helper import acts

ROOM = "1"


def obj(object_id, room, distance, klass="pool_seat", acts_list=(("8100", "seat_Sit"),), same_room=None):
    """An object in the probe's menu, nearest-first when the caller lists them so."""
    return {"object_id": object_id, "class": klass, "room": room, "distance_m": distance,
            "same_room": (room == ROOM) if same_room is None else same_room,
            "acts": [{"guid64": guid, "name": name, "text_key": None} for guid, name in acts_list]}


def menu(*objects):
    return {"room": ROOM, "objects": list(objects)}


def seats(count, rooms=3, guid="8100"):
    """Identical pool seats (same name, same act words), spread over rooms, nearest first."""
    return [obj(str(9000 + number), str(number % rooms + 1), 1.0 + number * 0.5, acts_list=((guid, "seat_Sit"),))
            for number in range(count)]


def size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


# H1: fold identical objects

def test_identical_objects_are_one_entry_that_counts_them_and_their_rooms_and_names_the_nearest():
    result = acts.options(menu(*seats(60)), room=ROOM, room_labels={"1": "Kitchen", "2": "Hall", "3": "Den"})
    assert len(result) == 1
    entry = result[0]
    assert entry["object_id"] == "9000"  # the first in the menu's order, the nearest
    assert entry["object"] == "pool seat"
    assert entry["where"].endswith("; 60 of them in 3 rooms, the nearest is listed")
    assert entry["where"].startswith("here, 1.0 m")
    assert [(act["guid64"], act["text"]) for act in entry["acts"]] == [("8100", "seat Sit")]
    assert entry["acts"][0]["ref"] == "a1"
    assert set(entry) <= {"object", "object_id", "where", "acts", "near", "room"}


def test_identical_objects_in_one_room_say_how_many_without_a_room_count():
    result = acts.options(menu(*[obj(str(9100 + n), ROOM, 1.0 + n) for n in range(5)]), room=ROOM)
    assert len(result) == 1
    assert result[0]["where"].endswith("; 5 of them, the nearest is listed")
    assert "rooms" not in result[0] and "many" not in result[0]


def test_folding_happens_before_the_budget_so_the_objects_behind_identical_ones_are_listed():
    cut = {}
    lamps = [obj(str(9200 + n), "2", 3.0 + n, klass="lamp_%d" % n, acts_list=(("8200", "lamp_On"),))
             for n in range(20)]
    result = acts.options(menu(*(seats(150) + lamps)), room=ROOM, cut=cut, objects_limit=40)
    assert cut == {}
    assert len(result) == 21
    assert [entry["object_id"] for entry in result if entry["object"].startswith("lamp")] == \
        [str(9200 + n) for n in range(20)]


def test_objects_with_another_name_or_other_act_words_are_not_folded():
    other_name = [obj("9301", ROOM, 1.0, klass="pool_seat", acts_list=(("8300", "seat_Sit"),)),
                  obj("9302", ROOM, 2.0, klass="deck_seat", acts_list=(("8300", "seat_Sit"),))]
    other_words = [obj("9303", ROOM, 3.0, klass="bench", acts_list=(("8301", "bench_Sit"),)),
                   obj("9304", ROOM, 4.0, klass="bench", acts_list=(("8302", "bench_Lie"),))]
    result = acts.options(menu(*(other_name + other_words)), room=ROOM)
    assert [entry["object_id"] for entry in result] == ["9301", "9302", "9303", "9304"]
    assert all("of them" not in entry["where"] for entry in result)


def test_a_spot_a_phone_and_a_person_are_never_folded():
    spots = [obj("9401", "0", 4.0, klass="spot", acts_list=(("8400", "terrain_gohere"),)),
             obj("9402", "0", 5.0, klass="spot", acts_list=(("8400", "terrain_gohere"),))]
    for entry in spots:
        entry["spot"] = None  # two outdoor spots: one name, one act word, and still two entries
    phone = [dict(obj("9403", None, None, klass="phone", acts_list=(("8401", "phone_Call"),), same_room=None),
                  phone=True), dict(obj("9404", None, None, klass="phone", acts_list=(("8401", "phone_Call"),),
                                        same_room=None), phone=True)]
    people = [obj("9405", ROOM, 1.0, klass="sim", acts_list=(("8402", "social_Greet"),)),
              obj("9406", ROOM, 2.0, klass="sim", acts_list=(("8402", "social_Greet"),))]
    names = {"9405": "Ann", "9406": "Ann"}  # two people, one name, the same act words
    result = acts.options(menu(*(spots + phone + people)), room=ROOM, people=names)
    assert sorted(entry["object_id"] for entry in result) == ["9401", "9402", "9403", "9404", "9405", "9406"]


def test_a_folded_entry_adds_no_key_the_contract_or_natalis_does_not_read():
    result = acts.options(menu(*seats(3)), room=ROOM, cut={})
    assert set(result[0]) <= {"object", "object_id", "where", "acts", "near", "room"}
    assert "many" not in result[0] and "rooms" not in result[0]


def test_a_folded_entry_is_smaller_than_its_members_and_fits_the_contract_bytes():
    result = acts.options(menu(*seats(160)), room=ROOM, cut={})
    assert len(result) == 1
    assert size(result) < 1024


# H2: people she hears on her lot

PRESENCE = {"presence": [
    {"id": "100", "is_body": True, "name": "Her", "on_lot": True, "distance_m": 0.0},
    {"id": "500", "name": "Courier Ann", "on_lot": True, "distance_m": 14.0, "room": "5"},
    {"id": "501", "name": "Far Bob", "on_lot": False, "distance_m": 30.0, "room": None},
    {"id": "502", "name": "Unknown Cy", "on_lot": None, "distance_m": 9.0, "room": None},
    {"id": "503", "name": "Seen Dee", "on_lot": True, "distance_m": 2.0, "room": "1"}]}


def test_a_sim_she_hears_on_her_lot_is_named_and_a_sim_off_it_is_not():
    names = acts.people_names(PRESENCE, {"100", "503"})
    assert names == {"100": "Her", "500": "Courier Ann", "503": "Seen Dee"}


def test_the_heard_sims_on_her_lot_are_the_ones_she_cannot_see_and_are_on_the_lot():
    assert acts.people_heard(PRESENCE, {"100", "503"}) == {"500"}
    assert acts.people_heard(PRESENCE, None) == set()
    assert acts.people_heard(None, {"100"}) == set()


def test_a_heard_sim_is_offered_with_where_saying_heard_not_seen_and_the_distance():
    names = acts.people_names(PRESENCE, {"100", "503"})
    heard = acts.people_heard(PRESENCE, {"100", "503"})
    people_menu = menu(obj("500", "5", 14.0, klass="sim", acts_list=(("8500", "social_Greet"),), same_room=False),
                       obj("503", ROOM, 2.0, klass="sim", acts_list=(("8500", "social_Greet"),)))
    result = acts.options(people_menu, room=ROOM, people=names, heard=heard)
    by_name = {entry["object"]: entry for entry in result}
    assert by_name["Courier Ann"]["where"] == "heard, not seen, 14.0 m"
    assert by_name["Seen Dee"]["where"] == "here, 2.0 m"
    assert by_name["Courier Ann"]["acts"][0]["text"] == "social Greet"


def test_a_sim_off_her_lot_is_still_not_offered_even_when_the_menu_holds_it():
    names = acts.people_names(PRESENCE, {"100", "503"})
    menu_with_far = menu(obj("501", "7", 30.0, klass="sim", acts_list=(("8501", "social_Greet"),), same_room=False),
                         obj("502", "7", 9.0, klass="sim", acts_list=(("8501", "social_Greet"),), same_room=False))
    result = acts.options(menu_with_far, room=ROOM, people=names,
                          heard=acts.people_heard(PRESENCE, {"100", "503"}))
    assert result == []


def test_without_a_seen_list_the_names_stay_as_they_were():
    assert acts.people_names(PRESENCE) == {"100": "Her", "500": "Courier Ann", "501": "Far Bob",
                                           "502": "Unknown Cy", "503": "Seen Dee"}
