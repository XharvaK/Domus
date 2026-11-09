"""D1 (Domus perception 1): a ref is given only to an act she is shown, and every act the probe left out is
named with its reason code.

The fixtures are invented objects and acts. The refs number from a1 with no gap, even when an object is cut from
one view and appears in the next; an object whose acts were all left out is still listed with the entries and the
plain words of what was hidden."""
from domus_helper.acts import RefBook, options


def obj(object_id, distance, acts, excluded=None, room="1", klass=None):
    item = {"object_id": object_id, "class": klass or "object_thing_%s" % object_id, "room": room,
            "distance_m": distance, "same_room": room == "1",
            "acts": [{"guid64": guid, "name": name, "text_key": None} for guid, name in acts]}
    if excluded is not None:
        item["excluded"] = excluded
    return item


def menu(*objects, room="1"):
    return {"room": room, "objects": list(objects)}


def refs_of(result):
    return {(entry["object_id"], act["guid64"]): act["ref"]
            for entry in result for act in entry["acts"]}


def test_refs_are_given_only_to_printed_acts_and_never_leave_a_gap():
    book = RefBook()
    a = obj("1", 1.0, [("1001", "a_One"), ("1002", "a_Two")])
    b = obj("2", 2.0, [("1003", "b_One"), ("1004", "b_Two")])
    c = obj("3", 3.0, [("1005", "c_One"), ("1006", "c_Two")])
    d = obj("4", 4.0, [("1007", "d_One"), ("1008", "d_Two")])
    first = options(menu(a, b, c, d), refs=book, objects_limit=2)
    assert [entry["object_id"] for entry in first] == ["1", "2"]
    assert list(refs_of(first).values()) == ["a1", "a2", "a3", "a4"]
    # c and d were not shown, so they were given no refs: when d comes back alone its refs are a5 and a6.
    second = options(menu(a, b, d), refs=book)
    refs = refs_of(second)
    assert refs[("4", "1007")] == "a5" and refs[("4", "1008")] == "a6"
    numbers = sorted(int(ref[1:]) for ref in refs.values())
    assert numbers == list(range(1, 7))


def test_an_object_whose_every_act_was_left_out_is_listed_with_its_excluded_entries_and_takes_no_ref():
    hidden = obj("2", 2.0, [], excluded=[
        {"name": "thing_Clean", "why": "PIE_PICKER"},
        {"name": "thing_Hide", "why": "MENU_HIDDEN"},
        {"name": "thing_Auto", "why": "NOT_USER_DIRECTED"},
    ])
    read = obj("3", 3.0, [("1001", "thing_Read")])
    result = options(menu(hidden, read), room="1")
    assert [entry["object_id"] for entry in result] == ["2", "3"]
    shown = result[0]
    assert shown["acts"] == []
    assert shown["excluded"] == hidden["excluded"]
    assert shown["left_out"] == [
        "thing Clean: left out: it opens a menu of choices, not an act",
        "thing Hide: left out: the game keeps it out of your menu",
        "thing Auto: left out: only the game starts it, not you",
    ]
    assert result[1]["acts"][0]["ref"] == "a1"


def test_the_excluded_codes_are_sent_with_the_plain_words_of_each_reason():
    item = obj("7", 1.0, [("1001", "thing_Read")], excluded=[
        {"name": "thing_Full", "why": "CAP"},
        {"name": "thing_Same", "why": "FOLDED"},
        {"name": "thing_Cheat", "why": "DENY_NAME"},
    ])
    [entry] = options(menu(item), room="1")
    assert entry["excluded"] == item["excluded"]
    assert entry["left_out"] == [
        "thing Full: left out: the menu is full",
        "thing Same: left out: the same words as another act here",
        "an act: left out: a debug, cheat or test act",
    ]


def test_an_act_with_the_same_words_twice_is_named_as_folded():
    item = obj("8", 1.0, [("1001", "thing_Read"), ("1002", "thing_ReadAgain")])
    for act in item["acts"]:
        act["text_key"] = "7001"
    [entry] = options(menu(item), resolve={"7001": "Read"}.get, room="1")
    assert [act["text"] for act in entry["acts"]] == ["Read"]
    assert entry["excluded"] == [{"name": "thing_ReadAgain", "why": "FOLDED"}]
    assert entry["left_out"] == ["thing Read Again: left out: the same words as another act here"]
