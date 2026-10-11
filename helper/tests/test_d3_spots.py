"""2.35.0 (D3, H1): a spot is one of her options, named from its place, with Go here as its act, a stable ref
keyed by its room, level and kind (not by the probe's number), and never cut before the objects of its room.
Fixtures are invented; the tuning name of Go Here is the game's own, and no game text appears here."""
from domus_helper.acts import RefBook, options

LABELS = {"4": "the back room with the table", "5": "the hall"}


def spot(object_id, room, level, kind="room", distance=2.0, same=True):
    return {"object_id": object_id, "class": "spot", "room": room, "level": level, "spot": kind,
            "distance_m": distance, "same_room": same,
            "acts": [{"guid64": "7001", "name": "terrain-gohere", "text_key": None}]}


def thing(object_id, room, distance=1.0, same=True):
    return {"object_id": object_id, "class": "object_thing", "room": room, "distance_m": distance,
            "same_room": same, "acts": [{"guid64": "4001", "name": "Read", "text_key": None}]}


def menu(*objects, room="4"):
    return {"room": room, "objects": list(objects)}


def only(result):
    assert len(result) == 1
    return result[0]


def test_a_spot_is_named_by_its_room_label_when_known_and_its_act_is_go_here():
    entry = only(options(menu(spot("1", "4", 0)), room="4", room_labels=LABELS))
    assert entry["object"] == "the back room with the table"
    assert entry["room"] == "the back room with the table"
    assert entry["object_id"] == "1"
    assert [act["text"] for act in entry["acts"]] == ["Go here"]
    assert entry["near"] is True


def test_a_spot_outdoors_at_the_front_door_or_upstairs_is_named_as_its_place():
    cases = [
        (spot("2", "0", 0), "outside"),
        (spot("3", "0", 0, kind="front_door"), "the front door, outside"),
        (spot("4", "2", 1, same=False), "a room upstairs"),
        (spot("5", "3", 0, same=False), "a room"),
    ]
    for item, name in cases:
        entry = only(options(menu(item, room="4"), room="4", room_labels=LABELS))
        assert entry["object"] == name, item["object_id"]


def test_the_front_door_is_named_as_the_front_door_even_with_no_label():
    entry = only(options(menu(spot("3", "0", 0, kind="front_door"), room="0"), room="0", room_labels={}))
    assert entry["object"] == "the front door, outside"
    assert "room" not in entry  # no label is known for it, so it names no room (as an object with none)


def test_the_spot_act_text_is_go_here_whatever_the_probe_names_the_act():
    item = spot("1", "4", 0)
    item["acts"][0]["text_key"] = "123"
    entry = only(options(menu(item), room="4", resolve=lambda key: "Some words", room_labels=LABELS))
    assert [act["text"] for act in entry["acts"]] == ["Go here"]


def test_a_spot_ref_is_keyed_by_its_room_level_and_kind_so_it_keeps_its_ref_when_its_number_changes():
    book = RefBook()
    first = options(menu(spot("1", "4", 0), thing("11", "4")), room="4", refs=book)
    second = options(menu(thing("11", "4"), spot("9", "4", 0)), room="4", refs=book)
    first_ref = {entry["object_id"]: entry["acts"][0]["ref"] for entry in first}
    second_ref = {entry["object_id"]: entry["acts"][0]["ref"] for entry in second}
    assert second_ref["9"] == first_ref["1"]  # the same room, level and kind: the same ref, a new number
    assert second_ref["11"] == first_ref["11"]
    front = options(menu(spot("3", "4", 0, kind="front_door")), room="4", refs=book)
    assert only(front)["acts"][0]["ref"] != first_ref["1"]  # another kind of spot in that room is another ref
    upstairs = options(menu(spot("1", "4", 1)), room="4", refs=book)
    assert only(upstairs)["acts"][0]["ref"] not in (first_ref["1"], only(front)["acts"][0]["ref"])


def test_spots_are_listed_with_their_room_and_are_never_cut_before_the_objects_of_their_room():
    # Her menu order: room 4's objects, its spot, room 5's objects, then room 5's spot.
    objects = [thing("o1", "4"), thing("o2", "4"), spot("s4", "4", 0),
               thing("o3", "5", distance=8.0, same=False), spot("s5", "5", 0, distance=8.0, same=False)]
    cut = {}
    result = options(menu(*objects), room="4", room_labels=LABELS, cut=cut, objects_limit=2)
    assert [entry["object_id"] for entry in result] == ["s4", "o1"]
    assert [entry["room"] for entry in result] == ["the back room with the table"] * 2
    assert cut["objects"] == 3
    assert cut["rooms"] == ["the back room with the table", "the hall"]
