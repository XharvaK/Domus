"""D6 (Domus perception 1): stable short room ids, and same-named objects stay per room.

Sixty identical seats in three rooms are three entries (one per room), never one entry
that says they are in N rooms. Each option names its room as rN plus the label, and the
short ids stay put when a new room appears. Names and ids are invented.
"""
from domus_helper.acts import options


def obj(object_id, room, distance, klass="pool_seat", acts_list=(("8100", "seat_Sit"),)):
    return {"object_id": object_id, "class": klass, "room": room, "distance_m": distance,
            "same_room": room == "1",
            "acts": [{"guid64": guid, "name": name, "text_key": None} for guid, name in acts_list]}


def menu(*objects):
    return {"room": "1", "objects": list(objects)}


def seats(count, rooms=3):
    return [obj(str(9000 + number), str(number % rooms + 1), 1.0 + number * 0.5)
            for number in range(count)]


def test_same_named_objects_in_different_rooms_are_listed_separately():
    result = options(menu(*seats(60)), room="1",
                     room_labels={"1": "Kitchen", "2": "Hall", "3": "Den"})
    assert len(result) == 3
    assert [entry["object_id"] for entry in result] == ["9000", "9001", "9002"]
    for entry in result:
        assert entry["where"].endswith("; 20 of them, the nearest is listed")
        assert "in " not in entry["where"] or "in 3 rooms" not in entry["where"]
        assert "of them in" not in entry["where"]


def test_every_option_names_its_room_with_a_stable_short_id():
    result = options(menu(*seats(6)), room="1",
                     room_labels={"1": "Kitchen", "2": "Hall", "3": "Den"})
    by_id = {entry["object_id"]: entry for entry in result}
    assert by_id["9000"]["room_id"] == "r1"
    assert by_id["9000"]["room"] == "Kitchen"
    assert by_id["9001"]["room_id"] == "r2"
    assert by_id["9001"]["room"] == "Hall"
    assert by_id["9002"]["room_id"] == "r3"
    assert by_id["9002"]["room"] == "Den"
    for entry in result:
        assert entry["room_id"].startswith("r")
        assert entry["room_id"][1:].isdigit()
        assert entry["room"]


def test_a_room_without_a_label_is_still_named_by_its_short_id():
    result = options(menu(obj("1", "4", 2.0, klass="chair")), room="1")
    assert result[0]["room_id"] == "r1"
    assert result[0]["room"] == "r1"


def test_short_ids_stay_put_when_a_new_room_appears():
    book = {}
    first = options(menu(obj("1", "5", 2.0, klass="chair")), room="1", room_refs=book)
    assert first[0]["room_id"] == "r1"
    second = options(menu(obj("2", "1", 1.0, klass="table"), obj("1", "5", 2.0, klass="chair")),
                     room="1", room_refs=book)
    by_id = {entry["object_id"]: entry for entry in second}
    assert by_id["1"]["room_id"] == "r1"
    assert by_id["2"]["room_id"] == "r2"
    assert book == {"5": "r1", "1": "r2"}


def test_assign_room_refs_gives_ids_in_numeric_order_for_a_new_book():
    from domus_helper.acts import assign_room_refs
    book = assign_room_refs(["10", "2", "1"], {})
    assert book == {"1": "r1", "2": "r2", "10": "r3"}


def test_identical_objects_in_one_room_still_fold():
    result = options(menu(*[obj(str(9100 + n), "1", 1.0 + n) for n in range(5)]), room="1")
    assert len(result) == 1
    assert result[0]["where"].endswith("; 5 of them, the nearest is listed")
    assert result[0]["room_id"] == "r1"
