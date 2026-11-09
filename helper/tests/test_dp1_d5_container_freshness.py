"""D5 (Domus perception 1): container contents carry freshness in the first view.

A sandwich whose menu object names Freshness_Spoiled (or a bag that holds one) shows
"Spoiled" among its option states without waiting for a later things-list index. Burnt
and Fresh are named the same way. Names and ids are invented; no game text appears here.
"""
from domus_helper.acts import options


def obj(object_id, distance, acts, room="1", klass=None, states=None):
    item = {"object_id": object_id, "class": klass or "object_thing_%s" % object_id, "room": room,
            "distance_m": distance, "same_room": room == "1",
            "acts": [{"guid64": guid, "name": name, "text_key": None} for guid, name in acts]}
    if states is not None:
        item["states"] = states
    return item


def menu(*objects, room="1"):
    return {"room": room, "objects": list(objects)}


def test_a_sandwich_names_spoiled_from_its_own_menu_states_without_the_things_index():
    sandwich = obj("11", 1.0, [("2", "food_Eat")], klass="object_food",
                   states=[{"state": "Freshness", "value": "Freshness_Spoiled"}])
    found = options(menu(sandwich), room="1", states={})
    assert len(found) == 1
    assert found[0]["states"] == ["Spoiled"]


def test_a_bag_that_holds_a_spoiled_sandwich_names_spoiled_on_the_first_view():
    bag = obj("10", 1.0, [("1", "bag_Open")], klass="object_bag", states=["Spoiled"])
    found = options(menu(bag), room="1")
    assert found[0]["states"] == ["Spoiled"]


def test_burnt_and_fresh_are_named_from_the_freshness_value():
    burnt = obj("12", 1.0, [("3", "food_Eat")], klass="object_food",
                states=[{"state": "Freshness", "value": "Freshness_Burnt"}])
    fresh = obj("13", 1.0, [("4", "food_Eat")], klass="object_food",
                states=["Freshness_Fresh"])
    by_id = {entry["object_id"]: entry for entry in options(menu(burnt, fresh), room="1")}
    assert by_id["12"]["states"] == ["Burnt"]
    assert by_id["13"]["states"] == ["Fresh"]


def test_the_things_list_index_still_names_states_when_the_menu_object_has_none():
    chair = obj("12", 2.0, [("5151", "chair_Sit")], klass="object_test_chair")
    found = {entry["object_id"]: entry for entry in options(menu(chair), room="1",
                                                            states={"12": ["Dirty", "Broken"]})}
    assert found["12"]["states"] == ["Dirty", "Broken"]


def test_menu_states_are_bounded_to_four_words_of_at_most_forty_characters():
    item = obj("7", 1.0, [("7001", "thing_Read")],
               states=["w%d" % index for index in range(6)] + ["x" * 41])
    found = options(menu(item), room="1")
    assert found[0]["states"] == ["w0", "w1", "w2", "w3"]


def test_empty_or_unreadable_menu_states_are_ignored():
    empty = obj("8", 1.0, [("8", "thing_Read")], states=[])
    bad = obj("9", 1.0, [("9", "thing_Read")], states="Spoiled")
    by_id = {entry["object_id"]: entry for entry in options(menu(empty, bad), room="1")}
    assert "states" not in by_id["8"]
    assert "states" not in by_id["9"]
