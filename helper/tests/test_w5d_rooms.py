"""2.32.0 (HE6): a room is named by the object families in it ("the room with the fridge and the stove"), and that
name reaches her portrait where a room number used to be. A room with no known object has no name."""
from domus_helper.notebook import Notebook
from domus_helper.thalamus import observation


def _near(*items):
    return {"objects": {"near_rooms": [{"object_id": oid, "class": klass, "room": room}
                                       for oid, klass, room in items], "moved": []}}


def test_a_room_is_named_by_the_families_of_its_objects(tmp_path):
    book = Notebook(tmp_path / "notebook.db")
    book.observe_near_rooms("w", _near(("1", "object_fridge_A", "4"), ("2", "object_stove_B", "4"),
                                       ("3", "object_bed_C", "9")), 1_000)
    assert book.room_labels("w") == {"4": "the room with the fridge and the stove",
                                     "9": "the room with the bed"}
    assert book.room_labels("other-world") == {}
    book.close()


def test_a_moved_object_renames_the_rooms_it_left_and_entered(tmp_path):
    book = Notebook(tmp_path / "notebook.db")
    book.observe_near_rooms("w", _near(("1", "object_fridge_A", "4")), 1_000)
    book.observe_near_rooms("w", {"objects": {"near_rooms": [{"object_id": "1", "class": "object_fridge_A",
                                                              "room": "9"}],
                                              "moved": [{"object_id": "1", "class": "object_fridge_A",
                                                         "from_room": "4", "to_room": "9"}]}}, 2_000)
    assert book.room_labels("w") == {"9": "the room with the fridge"}
    book.close()


def test_the_portrait_names_her_room_and_the_company_rooms_in_words_never_numbers():
    row = {"zone": {"zone_id": 7, "lot_id": 9, "room": "4"},
           "presence": [{"id": "1", "is_body": True, "name": "Ada", "room": "4", "level": 0},
                        {"id": "2", "is_body": False, "name": "Bea", "room": "4", "level": 0,
                         "distance_m": 2.0},
                        {"id": "3", "is_body": False, "name": "Cy", "room": "9", "level": 0,
                         "distance_m": 12.0}]}
    labels = {"4": "the room with the fridge", "9": "the room with the bed"}
    portrait = observation._portrait(row, room_labels=labels)
    assert portrait["zone"] == {"zone_id": 7, "lot_id": 9, "room_label": "the room with the fridge"}
    bea = [item for item in portrait["company"] if item.get("name") == "Bea"][0]
    assert bea["room_label"] == "the room with the fridge" and "room" not in bea
    heard = [item for item in portrait["company"] if item.get("heard")][0]
    assert heard["room_label"] == "the room with the bed" and "room" not in heard
    assert not any(ch.isdigit() for ch in str(portrait["zone"]["room_label"]))
