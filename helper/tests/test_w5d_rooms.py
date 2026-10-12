"""2.32.0 (HE6): a room is named in her portrait by its label where a room number used to be, and that name is never a
number. The labels come from the things list (reach.room_labels, S5); the portrait only reads them."""
from domus_helper.thalamus import observation


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
