"""W13 fixes (helper, 2026-10-12): the probe's real shapes, checked against the helper. The probe is read here only as
its wire shape (digit-string ids, one-word placements, names of buy categories); every name is invented and the game
is a fake. The room id rule (cmdbox `_digits`) is copied, because the vendored cmdbox is still the 2.39.0 copy."""
import json

from domus_helper import catalog, catalog_ask, reach
from domus_helper.acts import RefBook
from test_w13_helper import CATALOG_NAMES, VERB_ACT, _catalog_db, _courier, _flag, _Mint, _settle, _verb


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


# W13 (H, A4-2, A4-6, A4-16): a list's parts come whole or not at all; a catalogue part keeps its own cap; the lists of an
# earlier game session are not sent to a new one.
def test_a_catalogue_part_of_200_items_is_kept_whole_and_a_list_part_over_its_cap_is_never_stored_half():
    parts = reach.ListParts()
    flags = [{"definition_id": str(number)} for number in range(200)]
    assert parts.take("catalog", {"catalog_rev": "r", "part": 0, "parts": 1, "items": flags},
                      rev_key="catalog_rev") == flags
    people = [{"sim_id": str(number)} for number in range(200)]
    assert parts.take("people", {"list_rev": 1, "part": 0, "parts": 1, "digest": "a" * 64, "count": 200,
                                 "items": people}) is None


def test_a_list_is_completed_only_when_every_part_carries_the_same_digest_and_the_count_it_names():
    parts = reach.ListParts()
    assert parts.take("people", {"list_rev": 1, "part": 0, "parts": 2, "digest": "a" * 64, "count": 2,
                                 "items": [{"x": 1}, {"x": 2}]}) is None
    assert parts.take("people", {"list_rev": 1, "part": 1, "parts": 2, "digest": "b" * 64, "count": 2,
                                 "items": [{"x": 3}]}) is None
    assert parts.take("people", {"list_rev": 1, "part": 0, "parts": 2, "digest": "b" * 64, "count": 2,
                                 "items": [{"x": 4}]}) == [{"x": 4}, {"x": 3}]
    assert parts.take("people", {"list_rev": 2, "part": 0, "parts": 2, "digest": "c" * 64, "count": 2,
                                 "items": [{"x": 5}]}) is None
    assert parts.take("people", {"list_rev": 2, "part": 1, "parts": 2, "digest": "c" * 64, "count": 2,
                                 "items": []}) is None


def test_a_list_whose_parts_hold_fewer_items_than_it_counts_is_never_completed():
    parts = reach.ListParts()
    assert parts.take("things", {"list_rev": 4, "part": 0, "parts": 2, "digest": "d" * 64, "count": 2,
                                 "items": [{"x": 1}]}) is None
    assert parts.take("things", {"list_rev": 4, "part": 1, "parts": 2, "digest": "d" * 64, "count": 2,
                                 "items": []}) is None


def test_the_lists_of_an_earlier_game_session_are_forgotten_when_a_new_session_starts(paths, tmp_path, monkeypatch):
    from test_w13_helper import _Mint, _people_row
    from test_bridge_thalamus import WALL, _append, _bridge, _data
    _data(paths, tmp_path, monkeypatch)
    _append(paths, [_people_row(1)])
    bridge = _bridge(paths, {"ms": WALL}, client=_Mint())
    bridge.tick(WALL)
    assert "people" in bridge._lists
    _append(paths, [{"event_kind": "discovery", "telemetry_session_id": "sess-2", "written_sequence": 2,
                     "wall_timestamp_ms": WALL, "e2": {"discovery_rev": 1, "sections": {}}}])
    bridge.tick(WALL + 1000)
    assert bridge._lists == {} and bridge._households == {}
    assert json.loads(bridge.spool.get_kv("domus_lists"))["lists"] == {}


# W13 (H, A4-9, A4-15): the lists go to Natalis off the acts loop, and a digest she refuses three times waits ten minutes
# with its reason logged once.
def test_a_slow_natalis_on_the_lists_post_does_not_hold_the_tick(paths, tmp_path, monkeypatch):
    import threading
    import time
    from test_w13_helper import _Mint, _people_row
    from test_bridge_thalamus import WALL, _append, _bridge, _data
    _data(paths, tmp_path, monkeypatch)
    _append(paths, [_people_row(1)])
    release = threading.Event()

    class Slow(_Mint):
        def post_lists(self, body):
            release.wait(5)
            return super().post_lists(body)
    client = Slow()
    bridge = _bridge(paths, {"ms": WALL}, client=client)
    started = time.monotonic()
    bridge.tick(WALL)
    assert time.monotonic() - started < 2.0 and client.posted["lists"] == []
    release.set()
    _settle(bridge)
    assert len(client.posted["lists"]) == 1


def test_a_list_natalis_refuses_three_times_waits_ten_minutes_and_its_reason_is_logged_once(paths, tmp_path,
                                                                                            monkeypatch):
    from domus_helper import bridge as bridge_module
    from domus_helper.transport import SyncRefused
    from test_w13_helper import _Mint, _people_row
    from test_bridge_thalamus import WALL, _append, _bridge, _data
    data = _data(paths, tmp_path, monkeypatch)
    _append(paths, [_people_row(1)])
    attempts = []

    class Refusing(_Mint):
        def post_lists(self, body):
            attempts.append(body["digest"])
            return SyncRefused("bad_items")
    mono = {"ms": 0}
    bridge = _bridge(paths, mono, client=Refusing())
    bridge.tick(WALL)
    for step in range(1, 6):
        mono["ms"] = step * bridge_module.LIST_RETRY_MS
        bridge.tick(WALL + step * bridge_module.LIST_RETRY_MS)
        _settle(bridge)
    assert len(attempts) == 3
    mono["ms"] += bridge_module.LIST_REFUSED_WAIT_MS
    bridge.tick(WALL + mono["ms"])
    _settle(bridge)
    assert len(attempts) == 4
    lines = [json.loads(line) for path in sorted((data / "thalamus").glob("decisions-*.jsonl"))
             for line in path.read_text(encoding="utf-8").splitlines()]
    refused = [line for line in lines if line.get("error") == "refused"]
    assert len(refused) == 1 and refused[0]["reason"] == "bad_items" and refused[0]["kind"] == "people"


# W13 (H, A4-17, A4-18, A6-28): a malformed probe row never stops the bridge, and the discovery file keeps the probe's
# payload (its session and revision) with the section names in the log.
def test_a_reach_row_that_raises_any_error_is_logged_by_its_class_and_never_stops_the_bridge(paths, tmp_path,
                                                                                            monkeypatch):
    from test_bridge_thalamus import WALL, _bridge, _data
    data = _data(paths, tmp_path, monkeypatch)
    bridge = _bridge(paths, {"ms": WALL}, client=None)

    def malformed():
        raise IndexError("row")
    bridge._reach_quietly(malformed)
    lines = [json.loads(line) for path in sorted((data / "thalamus").glob("decisions-*.jsonl"))
             for line in path.read_text(encoding="utf-8").splitlines()]
    assert [line for line in lines if line.get("trigger") == "reach"][0]["error"] == "IndexError"


def test_the_discovery_file_keeps_the_probes_payload_and_the_log_names_its_sections(paths, tmp_path, monkeypatch):
    from test_bridge_thalamus import BUILD, WALL, _append, _bridge, _data, _log_lines
    data = _data(paths, tmp_path, monkeypatch)
    row = {"event_kind": "discovery", "written_sequence": 1, "wall_timestamp_ms": WALL,
           "monotonic_ns": WALL * 1_000_000, "telemetry_session_id": "sess-1", "sims_build": BUILD,
           "probe_version": "2.40.0", "e2": {"discovery_rev": 3, "sections": {"pickers": [{"guid": "1"}]}}}
    _append(paths, [row])
    bridge = _bridge(paths, {"ms": WALL}, client=None)
    bridge.tick(WALL)
    saved = json.loads((data / "discovery" / "sess-1.json").read_text(encoding="utf-8"))
    assert saved == {"telemetry_session_id": "sess-1", "discovery_rev": 3,
                     "e2": {"discovery_rev": 3, "sections": {"pickers": [{"guid": "1"}]}}}
    lines = [line for line in _log_lines(data) if line.get("trigger") == "discovery"]
    assert lines[0]["sections"] == ["pickers"]


# W13 (H, S2, A4-10): a door or a window on a wall is named by its kind.
def test_a_door_or_a_window_on_the_wall_is_named_by_its_kind_not_as_something():
    text = reach.result_words({"room_id": "3", "wall": True, "wall_has": ["11", "12"],
                               "wall_kinds": ["door", "window"]},
                              name_of={"11": "Test Door"}.get, room_of={"3": "Test Kitchen"}.get)
    assert text == "In Test Kitchen, against a wall with a door and a window."
    assert reach.result_words({"wall": True, "wall_has": ["12"]}, name_of={}.get) == "against a wall with something."


# W13 (H, A6-22, A6-24): a person with no readable name is kept as "unnamed"; a household's place says whose home it is
# in its name and the owner's first name in what.
def test_a_person_with_no_readable_name_is_kept_as_unnamed():
    raw = [{"sim_id": "9", "first_name": None, "last_name": "", "labels": [], "tracks": {}}]
    skipped = []
    assert reach.list_words("people", raw, refs=RefBook(), skipped=skipped) == [
        {"ref": "p1", "id": "9", "name": "unnamed", "how": "", "home": False, "here": False, "waiting": False}]
    assert skipped == []


def test_a_household_place_is_named_for_its_owner_and_what_is_the_owners_first_name():
    raw = [{"zone_id": 6, "kind": "household", "lot_name": "", "household_id": 9}]
    assert reach.list_words("places", raw, refs=RefBook(), households={"9": "Ana"}) == [
        {"ref": "h1", "id": "6", "name": "Ana's home", "kind": "household", "what": "Ana"}]
    assert reach.list_words("places", raw, refs=RefBook(), households={})[0]["what"] == "a household"


# W13 (H, A6-8): a visitor waiting at the door is said so on the presence item or on any of its situations.
def test_a_company_entry_is_waiting_when_one_of_its_situations_says_so():
    from domus_helper.thalamus.observation import _company_seen
    item = {"id": "601", "name": "Test Visitor", "distance_m": 2.0, "on_lot": True,
            "situations": [{"situation": "Test Visit", "waiting": True}]}
    assert _company_seen(item, None)["waiting"] is True
    assert "waiting" not in _company_seen(dict(item, situations=[{"situation": "Test Visit"}]), None)


# W13 (H, S1): her phone. A notice (the game's phone notification, from the probe's real op: the owner's phone, and the
# guid64 of the phone act it notifies) and a call held for her are facts; a text is no longer a kind.
def test_a_notice_on_her_phone_is_a_fact_naming_the_phone_act_it_is_about():
    from domus_helper.thalamus.percepts import Extractor
    extractor = Extractor()
    extractor.act_words = {"4242": "Test Phone Act"}
    row = {"event_kind": "phone", "telemetry_session_id": "s", "written_sequence": 1, "wall_timestamp_ms": 1000,
           "e2": {"kind": "notice", "from_sim_id": None, "notifies": "4242"}}
    phone = [p for p in extractor.step(row) if p.kind == "phone"]
    assert len(phone) == 1 and dict(phone[0].facts) == {"kind": "notice", "act": "Test Phone Act"}
    unnamed = dict(row, written_sequence=2, e2={"kind": "notice", "from_sim_id": None, "notifies": "9999"})
    assert [dict(p.facts) for p in extractor.step(unnamed) if p.kind == "phone"] == [{"kind": "notice"}]


def test_a_call_held_for_her_is_a_fact_with_its_callers_name_when_it_is_known():
    from domus_helper.thalamus.percepts import Extractor
    extractor = Extractor()
    extractor.people_names = {"501": "Test Person"}
    row = {"event_kind": "phone", "telemetry_session_id": "s", "written_sequence": 1, "wall_timestamp_ms": 1000,
           "e2": {"kind": "call", "from_sim_id": "501", "notifies": None}}
    assert [dict(p.facts) for p in extractor.step(row) if p.kind == "phone"] == [
        {"kind": "call", "from": "Test Person"}]
    unknown = dict(row, written_sequence=2, e2={"kind": "call", "from_sim_id": None, "notifies": None})
    assert [dict(p.facts) for p in extractor.step(unknown) if p.kind == "phone"] == [{"kind": "call"}]
    text = dict(row, written_sequence=3, e2={"kind": "text", "from_sim_id": "501", "notifies": None})
    assert [p for p in extractor.step(text) if p.kind == "phone"] == []


def test_the_act_words_of_a_menu_map_each_guid_to_the_game_words_for_it():
    from domus_helper.acts import act_words_by_guid
    menu = {"objects": [{"object_id": "11", "acts": [{"guid64": "4242", "name": "phone_Notice", "text_key": "k1"},
                                                    {"name": "no_guid", "text_key": "k2"}]}]}
    assert act_words_by_guid(menu, resolve={"k1": "Test Phone Act"}.get) == {"4242": "Test Phone Act"}
    assert act_words_by_guid(None) == {}


def test_the_bridge_names_a_notices_act_from_the_newest_menu(paths, tmp_path, monkeypatch):
    from test_bridge_thalamus import BUILD, WALL, _append, _bridge, _data
    _data(paths, tmp_path, monkeypatch)
    menu = {"menu_rev": 1, "room": "4", "objects": [
        {"object_id": "11", "class": "object_phone", "distance_m": 1.0, "same_room": True,
         "acts": [{"guid64": "4242", "name": "phone_Read", "text_key": None}]}]}
    _append(paths, [{"event_kind": "act_menu", "written_sequence": 1, "wall_timestamp_ms": WALL,
                     "monotonic_ns": WALL * 1_000_000, "telemetry_session_id": "sess-1", "sims_build": BUILD,
                     "probe_version": "2.40.0", "e2": menu}])
    bridge = _bridge(paths, {"ms": WALL})
    bridge.tick(WALL)
    assert bridge._extractor.act_words == {"4242": "phone Read"}  # humanized, as the menu has no words for it
