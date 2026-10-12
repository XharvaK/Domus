"""W13 fixes (helper, 2026-10-12): the probe's real shapes, checked against the helper. The probe is read here only as
its wire shape (digit-string ids, one-word placements, names of buy categories); every name is invented and the game
is a fake. The room id rule (cmdbox `_digits`) is copied, because the vendored cmdbox is still the 2.39.0 copy."""
import json

from domus_helper import catalog, catalog_ask, reach
from domus_helper.acts import RefBook
from test_w13_helper import CATALOG_NAMES, VERB_ACT, _catalog_db, _courier, _flag, _Mint, _verb


def _probe_flag(definition, categories, placement, price, purchasable=True):
    """A catalogue item as the probe writes it (2.40.0): the id is a digit string, the placement is one word."""
    return {"definition_id": str(definition), "price": price, "buy_category": categories,
            "placement": placement, "tags": ["Test"], "purchasable": purchasable}


def test_a_probe_row_with_a_digit_string_id_is_stored_and_found_by_its_words(tmp_path, monkeypatch):
    paths = _catalog_db(tmp_path, monkeypatch, [(301, 1301)])
    assert catalog.store_flags(paths, "1.128", [_probe_flag(301, ["COMFORT"], ["floor"], 80)]) == 1
    assert catalog.has_flags(paths, "1.128")
    assert catalog.search(paths, "1.128", "test chair", resolve=CATALOG_NAMES.get) == (
        1, [{"definition_id": 301, "name": "Test Chair", "price": 80, "placement": "floor", "category": "comfort"}])


def test_a_dump_with_no_usable_rows_keeps_the_flags_it_would_have_replaced(tmp_path, monkeypatch):
    paths = _catalog_db(tmp_path, monkeypatch, [(301, 1301)])
    catalog.store_flags(paths, "1.128", [_probe_flag(301, ["COMFORT"], ["floor"], 80)])
    assert catalog.store_flags(paths, "1.128", [{"definition_id": None}, "x", {"definition_id": "x1"}]) == 0
    assert catalog.search(paths, "1.128", "test chair", resolve=CATALOG_NAMES.get)[0] == 1


def test_an_item_the_probe_could_not_read_a_category_for_is_never_offered(tmp_path, monkeypatch):
    paths = _catalog_db(tmp_path, monkeypatch, [(309, 1301)])
    catalog.store_flags(paths, "1.128", [_probe_flag(309, [], None, 80)])
    assert catalog.search(paths, "1.128", "test chair", resolve=CATALOG_NAMES.get) == (0, [])
    catalog.store_flags(paths, "1.128", [_probe_flag(309, None, ["floor"], 80)])
    assert catalog.search(paths, "1.128", "test chair", resolve=CATALOG_NAMES.get) == (0, [])


def test_an_answer_names_one_placement_word_and_a_filter_matches_that_word(tmp_path, monkeypatch):
    paths = _catalog_db(tmp_path, monkeypatch, [(304, 1304)])
    catalog.store_flags(paths, "1.128", [_probe_flag(304, ["LIGHTING"], ["wall"], 30)])
    matched, items = catalog.search(paths, "1.128", "lamp", placement="wall", resolve=CATALOG_NAMES.get)
    assert matched == 1 and items[0]["placement"] == "wall" and items[0]["category"] == "lighting"
    assert catalog.search(paths, "1.128", "lamp", placement="floor", resolve=CATALOG_NAMES.get) == (0, [])


def test_a_probe_placement_list_keeps_one_word_and_a_category_list_keeps_its_names(tmp_path, monkeypatch):
    paths = _catalog_db(tmp_path, monkeypatch, [(304, 1304)])
    catalog.store_flags(paths, "1.128", [_probe_flag(304, ["LIGHTING", "DECOR"], ["wall", "floor"], 30)])
    assert catalog.search(paths, "1.128", "lamp", placement="floor", resolve=CATALOG_NAMES.get) == (0, [])
    matched, items = catalog.search(paths, "1.128", "lamp", placement="wall", resolve=CATALOG_NAMES.get)
    assert matched == 1 and items[0]["placement"] == "wall" and items[0]["category"] == "decor, lighting"


# W13 (H, S4/S5): a room is a digit string on every wire, and a room's label comes from the things in it.
def _digits(value):
    """cmdbox._digits (2.40.0): a copy of the probe's rule, for the vendored cmdbox is still 2.39.0."""
    return type(value) is str and 1 <= len(value) <= 20 and all(ch in "0123456789" for ch in value)


def _probe_place_ok(place):
    """cmdbox._place_ok (2.40.0): a copy of the probe's rule for a wall or in place; facing is an id or 'room'."""
    if type(place) is not dict or 'rel' not in place:
        return False
    if place['rel'] not in ('wall', 'in'):
        return False
    if set(place) - {'rel', 'room_id', 'facing'} or 'room_id' not in place:
        return False
    if not _digits(place['room_id']):
        return False
    return 'facing' not in place or place['facing'] == 'room' or _digits(place['facing'])


def test_a_place_in_a_room_is_sent_with_its_room_id_as_digits_the_probe_accepts(tmp_path):
    courier, sent = _courier(tmp_path, rooms=lambda: {"3": "the room with the Test Bed"})
    place = {"rel": "wall", "room": "The Room With The Test Bed", "facing": "room"}
    courier.tick(_Mint(acts=[_verb("buy", {"definition_id": "7", "place": place})]), "h", 1000, True, probe="2.40.0")
    assert len(sent) == 1
    moved = sent[0][1]["place"]
    assert moved == {"rel": "wall", "room_id": "3", "facing": "room"}
    assert _probe_place_ok(moved)


def test_room_labels_come_from_the_things_in_each_room_and_equal_labels_are_numbered_in_room_order():
    names = {"111": "Test Bed", "222": "Test Lamp", "333": "Test Stool", "444": "Test Sink"}
    raw = [{"object_id": "1", "name_key": "111", "where": {"where": "room", "room_id": 3}},
           {"object_id": "2", "name_key": "222", "where": {"where": "room", "room_id": "3"}},
           {"object_id": "3", "name_key": "111", "where": {"where": "room", "room_id": "7"}},
           {"object_id": "4", "name_key": "111", "where": {"where": "room", "room_id": "5"}},
           {"object_id": "5", "name_key": "999", "where": {"where": "room", "room_id": "9"}},
           {"object_id": "6", "name_key": "333", "where": "inventory"},
           {"object_id": "7", "name_key": "444", "room_id": "8"}]
    assert reach.room_labels(raw, resolve=names.get) == {
        "3": "the room with the Test Bed and the Test Lamp",
        "5": "the room with the Test Bed",
        "7": "the room with the Test Bed (2)",
        "8": "the room with the Test Sink"}


def test_a_thing_is_placed_in_its_room_label_and_one_in_an_unlabelled_room_is_left_out_never_a_room():
    names = {"111": "Test Bed"}
    raw = [{"object_id": "10", "name_key": "111", "where": {"where": "room", "room_id": "4"}, "value": 5},
           {"object_id": "11", "name_key": "111", "where": {"where": "room", "room_id": "3"}, "value": 5}]
    skipped = []
    words = reach.list_words("things", raw, refs=RefBook(), rooms={"3": "the room with the Test Bed"},
                             resolve=names.get, skipped=skipped)
    assert [item["where"] for item in words] == ["the room with the Test Bed"]
    assert skipped == ["where"]


def test_an_unknown_room_names_the_rooms_she_knows_and_no_more_than_eight(tmp_path):
    rooms = {str(number): "the room with the Test %d" % number for number in range(3, 12)}
    courier, sent = _courier(tmp_path, rooms=lambda: rooms)
    courier.tick(_Mint(acts=[_verb("move", {"object_id": "9", "place": {"rel": "in", "room": "Test Attic"}})]),
                 "h", 1000, True, probe="2.40.0")
    assert sent == []
    refused = [event for event in courier._events if event["phase"] == "rejected"]
    assert refused[0]["detail"]["code"] == "UNKNOWN_ROOM"
    named = refused[0]["detail"]["detail"]
    assert named.startswith("rooms known: ") and 1 <= named.count("the room with") <= 8 and len(named) <= 200


# W13 (H, A4-19, A6-30, S7): a verb is recorded before it is sent; a refused envelope says its code; an event's
# words say its start from its own args.
def test_a_verb_is_recorded_as_sent_before_its_command_goes_out(tmp_path):
    from domus_helper.acts import ActCourier
    from domus_helper.spool import Spool
    seen = []

    def publish(command, args):
        seen.append(json.loads(Spool(tmp_path / "spool.db").get_kv("acts_known") or "{}"))
        return "cmd1"
    courier = ActCourier(Spool(tmp_path / "spool.db"), publish)
    courier.tick(_Mint(acts=[_verb("sell", {"object_id": "5"})]), "h", 1000, True, probe="2.40.0")
    assert len(seen) == 1 and VERB_ACT in seen[0] and seen[0][VERB_ACT]["answered"] is True


def test_an_envelope_refusal_is_args_invalid_with_the_probes_code_in_its_detail(tmp_path):
    from domus_helper.acts import ActCourier
    from domus_helper.spool import Spool

    def publish(command, args):
        raise ValueError("BAD_ARGS")
    courier = ActCourier(Spool(tmp_path / "spool.db"), publish)
    courier.tick(_Mint(acts=[_verb("sell", {"object_id": "5"})]), "h", 1000, True, probe="2.40.0")
    refused = [event for event in courier._events if event["phase"] == "rejected"]
    assert refused[0]["detail"] == {"code": "ARGS_INVALID", "by": "helper", "detail": "BAD_ARGS"}


def test_an_event_is_worded_from_the_start_its_own_args_name(tmp_path):
    from domus_helper.acts import ActCourier
    from domus_helper.spool import Spool
    words = []
    courier = ActCourier(Spool(tmp_path / "spool.db"), lambda command, args: "cmd1",
                         result_words=lambda result, start=None: words.append(start) or "ok")
    event = {"situation_id": "5", "guests": [], "start": {"day_offset": 1, "hour": 20, "minute": 0}}
    courier.tick(_Mint(acts=[_verb("event", event)]), "h", 1000, True, probe="2.40.0")
    courier.on_row({"event_kind": "act_event", "telemetry_session_id": "s", "wall_timestamp_ms": 2000,
                    "e2": {"act_id": VERB_ACT, "phase": "FINISHED", "result": {"start_min": 1440 * 738000}}})
    assert words == [{"day_offset": 1, "hour": 20, "minute": 0}]
    assert reach.result_words({"start_min": 5}, start="now") == "Starts now."
