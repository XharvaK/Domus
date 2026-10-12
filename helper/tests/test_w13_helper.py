"""2.40.0 (W13 helper): the probe's discovery is kept for the lead, her lists and catalogue reach Natalis in words, verb
acts are their probe commands (gated on 2.40.0), a Sim picked for a phone act is sent with it, a result is said in words,
a broken or dirty thing says so, the RefBook's letters number on their own, and a phone text, a waiting visitor and a
work end are facts. Every name is invented; the game, the probe and Natalis are fakes."""
import hashlib
import json
import re
import sqlite3
import uuid
from types import SimpleNamespace

from domus_helper import acts, catalog, catalog_ask, reach
from domus_helper import bridge as bridge_module
from domus_helper.acts import ActCourier, RefBook, options
from domus_helper.paths import Paths
from domus_helper.spool import Spool
from domus_helper.thalamus.observation import _company_seen, _job
from domus_helper.thalamus.percepts import Extractor
from test_bridge_thalamus import BUILD, WALL, _append, _bridge, _data, _lineage, _log_lines

ACT_ID = "f" * 32
VERB_ACT = "e" * 32


class _Mint:
    """Natalis's sync and its posts, as a fake. The sync answer names the digest of each list Natalis holds (held, which a
    post of that list sets); self.answer adds or replaces answer fields (acts, catalogue asks). A refused list answers None."""

    def __init__(self, **answer):
        self.answer = dict(answer)
        self.bodies = []
        self.posted = {"lists": [], "catalog": []}
        self.held = {}
        self.refuse_lists = False

    def sync_acts(self, body):
        self.bodies.append(json.loads(json.dumps(body)))
        base = {"status": "ok", "applied": len(body["events"]), "acts": [], "lists": dict(self.held), "catalog": []}
        return dict(base, **self.answer)

    def post_lists(self, body):
        if self.refuse_lists:
            return None
        self.posted["lists"].append(body)
        self.held[body["kind"]] = body["digest"]
        return {"status": "ok", "stored": True}

    def post_catalog(self, body):
        self.posted["catalog"].append(body)
        return {"status": "ok"}

    def post_heartbeat(self, body):
        return SimpleNamespace(kind="admitted", status=200)

    def post_observation(self, body, now_ms=None):
        return SimpleNamespace(kind="admitted", status=200)

    def last_events(self):
        return self.bodies[-1]["events"]


def _settle(bridge, limit=5.0):
    """Waits until the list posts of the bridge have finished (they run on their own thread)."""
    import time
    stop = time.monotonic() + limit
    while bridge._lists_busy and time.monotonic() < stop:
        time.sleep(0.01)
    assert not bridge._lists_busy


def _courier(tmp_path, **kw):
    sent = []

    def publish(command, args):
        sent.append((command, args))
        return "cmd%d" % len(sent)
    return ActCourier(Spool(tmp_path / "spool.db"), publish, **kw), sent


def _verb(verb, args=None, **extra):
    act = {"act_id": VERB_ACT, "verb": verb, "object_id": "0", "args": args}
    act.update(extra)
    return act


def _requested(**extra):
    act = {"act_id": ACT_ID, "object_id": "11", "guid64": "4242"}
    act.update(extra)
    return act


def _refused(events, act_id):
    return [event for event in events if event["act_id"] == act_id]


# W13 (H): the refs. One letter per kind, each numbered from 1 on its own; the view's a-refs are as they were.
def test_the_ref_letters_number_on_their_own_and_no_two_kinds_share_a_letter():
    refs = RefBook()
    assert refs.ref(("act", "11", "4242")) == "a1"
    assert refs.ref("501", prefix="p") == "p1"
    assert refs.ref("77", prefix="t") == "t1"
    assert refs.ref("501", prefix="p") == "p1"
    assert refs.ref("501", prefix="t") == "t2"
    assert refs.ref(("act", "11", "4242")) == "a1"
    letters = ("a", "p", "h", "t", "e", "c")
    assert [refs.ref("3", prefix=letter)[0] for letter in letters] == list(letters)


def test_every_verb_and_the_sim_pick_are_gated_on_probe_2_40_0():
    for need in ("go", "save", "event", "buy", "place", "move", "sell", "sim"):
        assert acts.PROBE_NEEDS[need] == (2, 40, 0)
    assert acts.VERBS == ("go", "save", "event", "buy", "place", "move", "sell")


# W13 (D5, D9): a verb act is the probe command of its verb, with Natalis's args and our act id.
def test_a_verb_act_is_sent_as_its_probe_command_with_the_act_id_and_natalis_args(tmp_path):
    courier, sent = _courier(tmp_path)
    client = _Mint(acts=[_verb("buy", {"definition_id": "7", "place": {"beside": "a3"}, "max_price": 300})])
    courier.tick(client, "h", 1000, True, probe="2.40.0")
    assert sent == [("buy", {"definition_id": "7", "place": {"beside": "a3"}, "max_price": 300, "act_id": VERB_ACT})]
    client.answer["acts"] = []
    courier.tick(client, "h", 1100, True, probe="2.40.0")
    assert [event["phase"] for event in _refused(client.last_events(), VERB_ACT)] == ["received"]


TEST_ROOMS = {"3": "Test Kitchen", "4": "Test Den", "5": "Twin Room", "6": "Twin Room"}


# W13 (D9.3): a place names its room as her view does; the probe takes the room's id. No room, or two, is refused here.
def test_a_place_room_name_is_sent_as_its_room_id_matched_ignoring_case(tmp_path):
    courier, sent = _courier(tmp_path, rooms=lambda: TEST_ROOMS)
    place = {"rel": "wall", "room": "test KITCHEN", "facing": "room"}
    courier.tick(_Mint(acts=[_verb("buy", {"definition_id": "7", "place": place})]), "h", 1000, True, probe="2.40.0")
    assert sent == [("buy", {"definition_id": "7", "place": {"rel": "wall", "room_id": "3", "facing": "room"},
                             "act_id": VERB_ACT})]


def test_a_place_room_name_that_is_no_room_or_more_than_one_is_refused_by_the_helper_and_never_sent(tmp_path):
    courier, sent = _courier(tmp_path, rooms=lambda: TEST_ROOMS)
    client = _Mint(acts=[_verb("move", {"object_id": "9", "place": {"rel": "in", "room": "Test Attic"}})])
    courier.tick(client, "h", 1000, True, probe="2.40.0")
    other = "c" * 32
    client.answer["acts"] = [_verb("move", {"object_id": "9", "place": {"rel": "in", "room": "Twin Room"}},
                                   act_id=other)]
    courier.tick(client, "h", 1100, True, probe="2.40.0")
    client.answer["acts"] = []
    courier.tick(client, "h", 1200, True, probe="2.40.0")
    assert sent == []
    everything = [event for body in client.bodies for event in body["events"]]
    assert _refused(everything, VERB_ACT)[0]["detail"] == {
        "code": "UNKNOWN_ROOM", "by": "helper", "detail": "rooms known: Test Den; Test Kitchen; Twin Room; Twin Room"}
    assert _refused(everything, other)[0]["detail"]["code"] == "UNKNOWN_ROOM"


def test_a_verb_act_on_a_probe_older_than_2_40_is_refused_by_the_helper_and_never_sent(tmp_path):
    courier, sent = _courier(tmp_path)
    client = _Mint(acts=[_verb("sell", {"object_id": "5"})])
    courier.tick(client, "h", 1000, True, probe="2.39.0")
    client.answer["acts"] = []
    courier.tick(client, "h", 1100, True, probe="2.39.0")
    assert sent == []
    assert _refused(client.last_events(), VERB_ACT) == [
        {"act_id": VERB_ACT, "phase": "rejected", "at_ms": 1000, "detail": {"code": "PROBE_TOO_OLD", "by": "helper"}}]


def test_a_verb_the_helper_does_not_know_is_refused_with_args_invalid(tmp_path):
    courier, sent = _courier(tmp_path)
    client = _Mint(acts=[_verb("fly")])
    courier.tick(client, "h", 1000, True, probe="2.40.0")
    client.answer["acts"] = []
    courier.tick(client, "h", 1100, True, probe="2.40.0")
    assert sent == []
    assert _refused(client.last_events(), VERB_ACT)[0]["detail"] == {"code": "ARGS_INVALID", "by": "helper"}


def test_a_verb_act_that_carries_a_guid_or_a_sim_or_odd_args_is_refused(tmp_path):
    courier, sent = _courier(tmp_path)
    cases = [("save", None, {"guid64": "4242"}), ("go", ["zone"], {}), ("go", None, {"sim_id": "55"})]
    for index, (verb, args, extra) in enumerate(cases):
        act_id = "%032x" % (index + 1)
        client = _Mint(acts=[dict(_verb(verb, args, **extra), act_id=act_id)])
        courier.tick(client, "h", 1000 + index, True, probe="2.40.0")
        client.answer["acts"] = []
        courier.tick(client, "h", 2000 + index, True, probe="2.40.0")
        assert _refused(client.last_events(), act_id)[0]["detail"]["code"] == "ARGS_INVALID"
    assert sent == []


# W13 (D4.1): a Sim picked for a phone act goes with the act; on an older probe, or for a window, it is refused.
def test_a_sim_picked_for_a_phone_act_is_sent_with_the_act(tmp_path):
    courier, sent = _courier(tmp_path)
    courier.tick(_Mint(acts=[_requested(sim_id="55")]), "h", 1000, True, probe="2.40.0")
    assert sent == [("act", {"act_id": ACT_ID, "object_id": "11", "guid64": "4242", "sim_id": "55"})]


def test_a_sim_on_a_probe_older_than_2_40_is_refused_and_a_sim_id_that_is_not_digits_is_invalid(tmp_path):
    courier, sent = _courier(tmp_path)
    client = _Mint(acts=[_requested(sim_id="55")])
    courier.tick(client, "h", 1000, True, probe="2.39.0")
    client.answer["acts"] = []
    courier.tick(client, "h", 1100, True, probe="2.39.0")
    assert sent == []
    assert _refused(client.last_events(), ACT_ID)[0]["detail"]["code"] == "PROBE_TOO_OLD"
    other = "a" * 32
    client = _Mint(acts=[_requested(act_id=other, sim_id="Ana")])
    courier.tick(client, "h", 2000, True, probe="2.40.0")
    client.answer["acts"] = []
    courier.tick(client, "h", 2100, True, probe="2.40.0")
    assert sent == []
    assert _refused(client.last_events(), other)[0]["detail"]["code"] == "ARGS_INVALID"


def test_a_sim_on_a_window_is_refused_because_a_window_names_no_sim(tmp_path):
    courier, sent = _courier(tmp_path)
    other = "b" * 32
    client = _Mint(acts=[_requested(act_id=other, object_id="dialog:9", guid64="3", sim_id="55")])
    courier.tick(client, "h", 1000, True, probe="2.40.0")
    client.answer["acts"] = []
    courier.tick(client, "h", 1100, True, probe="2.40.0")
    assert sent == []
    assert _refused(client.last_events(), other)[0]["detail"]["code"] == "ARGS_INVALID"


# W13 (D9.3): the probe's result facts of a verb act are words in its event, at most 400 characters.
def test_the_result_of_a_finished_verb_act_is_words_in_its_event(tmp_path):
    courier, _sent = _courier(tmp_path, result_words=lambda result, start=None: "In the Test Kitchen. Costs §%d." % result["price"])
    courier.tick(_Mint(acts=[_verb("buy", {"definition_id": "7", "place": {"in": "Test Kitchen"}})]), "h", 1000, True,
                 probe="2.40.0")
    courier.on_row({"event_kind": "act_event", "telemetry_session_id": "s", "wall_timestamp_ms": 2000,
                    "e2": {"act_id": VERB_ACT, "phase": "FINISHED", "result": {"price": 120}}})
    finished = [event for event in courier._events if event["act_id"] == VERB_ACT and event["phase"] == "finished"]
    assert finished[0]["detail"]["result"] == "In the Test Kitchen. Costs §120."


def test_a_result_is_cut_to_400_characters(tmp_path):
    courier, _sent = _courier(tmp_path, result_words=lambda result, start=None: "x" * 900)
    courier.tick(_Mint(acts=[_verb("move", {"object_id": "5"})]), "h", 1000, True, probe="2.40.0")
    courier.on_row({"event_kind": "act_event", "telemetry_session_id": "s", "wall_timestamp_ms": 2000,
                    "e2": {"act_id": VERB_ACT, "phase": "FINISHED", "result": {"room_id": 3}}})
    assert len([e for e in courier._events if e["phase"] == "finished"][0]["detail"]["result"]) == 400


def test_a_words_function_that_fails_says_nothing_and_the_event_is_still_written(tmp_path):
    def broken(result, start=None):
        raise KeyError("room")
    courier, _sent = _courier(tmp_path, result_words=broken)
    courier.tick(_Mint(acts=[_verb("move", {"object_id": "5"})]), "h", 1000, True, probe="2.40.0")
    courier.on_row({"event_kind": "act_event", "telemetry_session_id": "s", "wall_timestamp_ms": 2000,
                    "e2": {"act_id": VERB_ACT, "phase": "FINISHED", "result": {"room_id": 3}}})
    finished = [e for e in courier._events if e["phase"] == "finished"]
    assert finished and "result" not in finished[0].get("detail", {})


def test_each_sync_answer_is_handed_to_the_answer_hook_with_its_session(tmp_path):
    seen = []
    courier, _sent = _courier(tmp_path, answered=lambda answer, client, session: seen.append((answer, session)))
    courier.tick(_Mint(lists={"people": "d1"}), "h", 1000, True, probe="2.40.0")
    assert seen and seen[0][1] == "h" and seen[0][0]["lists"] == {"people": "d1"}


# W13 (D4.1, D9.6): a phone act that needs a Sim says so, and a thing that is broken or dirty says its state.
def test_a_needs_sim_act_is_marked_and_a_thing_in_her_list_names_its_states():
    menu = {"room": "3", "objects": [
        {"object_id": "11", "class": "object_test_phone", "room": "3", "distance_m": 1.0,
         "acts": [{"guid64": "4242", "name": "phone_Invite", "needs_sim": True}]},
        {"object_id": "12", "class": "object_test_chair", "room": "3", "distance_m": 2.0,
         "acts": [{"guid64": "5151", "name": "chair_Sit"}]}]}
    found = {entry["object_id"]: entry for entry in options(menu, room="3", states={"12": ["Dirty", "Broken"]})}
    assert found["11"]["acts"][0]["needs_sim"] is True
    assert "needs_sim" not in found["12"]["acts"][0]
    assert found["12"]["states"] == ["Dirty", "Broken"]
    assert "states" not in found["11"]


# W13 (H): the lists, in words. A list is held until every part is in; its digest is of the words sent.
def test_a_list_is_held_until_every_part_has_come_and_a_newer_revision_starts_over():
    parts = reach.ListParts()
    same = {"digest": "a" * 64, "count": 2}
    assert parts.take("people", dict(same, list_rev=1, part=0, parts=2, items=[{"sim_id": "1"}])) is None
    assert parts.take("people", dict(same, list_rev=1, part=5, parts=2, items=[])) is None
    assert parts.take("people", dict(same, list_rev=1, part=1, parts=2, items=[{"sim_id": "2"}])) == [
        {"sim_id": "1"}, {"sim_id": "2"}]
    assert parts.take("people", dict(same, list_rev=2, part=0, parts=2, items=[{"sim_id": "3"}])) is None
    assert parts.take("people", {"list_rev": 3, "part": 0, "parts": 1, "digest": "b" * 64, "count": 1,
                                 "items": [{"sim_id": "9"}]}) == [{"sim_id": "9"}]
    assert parts.take("catalog", {"catalog_rev": "x", "part": 0, "parts": 1, "items": [{"definition_id": 4}]},
                      rev_key="catalog_rev") == [{"definition_id": 4}]


def test_people_are_listed_in_words_with_their_refs_labels_and_tracks():
    raw = [{"sim_id": 501, "first_name": "Test", "last_name": "Person", "labels": ["Friend", "Best Friend"],
            "tracks": {"Romance": 40}, "household_id": 9, "has_home": True, "on_lot": False, "waiting": False},
           {"sim_id": "502", "first_name": "Ana", "last_name": "", "labels": [], "tracks": {},
            "household_id": 8, "has_home": False, "on_lot": True, "waiting": True}]
    words = reach.list_words("people", raw, refs=RefBook())
    assert words == [
        {"ref": "p1", "id": "501", "name": "Test Person", "how": "Friend, Best Friend; Romance 40",
         "home": True, "here": False, "waiting": False},
        {"ref": "p2", "id": "502", "name": "Ana", "how": "", "home": False, "here": True, "waiting": True}]


def test_places_say_their_kind_and_whose_home_a_household_place_is():
    raw = [{"zone_id": 4, "kind": "home", "lot_name": "Test Lot"},
           {"zone_id": 6, "kind": "household", "lot_name": "", "household_id": 9},
           {"zone_id": 7, "kind": "venue", "lot_name": "Test Cafe", "venue": "cafe_Venue"},
           {"zone_id": 8, "kind": "park"}]
    words = reach.list_words("places", raw, refs=RefBook(), households={"9": "Ana"})
    assert words == [
        {"ref": "h1", "id": "4", "name": "Test Lot", "kind": "home", "what": "your home"},
        {"ref": "h2", "id": "6", "name": "Ana's home", "kind": "household", "what": "Ana"},
        {"ref": "h3", "id": "7", "name": "Test Cafe", "kind": "venue", "what": "cafe Venue"}]


def test_things_name_their_room_or_inventory_and_one_with_no_readable_place_is_left_out():
    names = {"111": "Test Chair"}
    raw = [{"object_id": 77, "definition_id": 9, "name_key": "111", "where": {"where": "room", "room_id": 3},
            "value": 60, "made_by_her": True, "states": [{"state": "Dirty", "value": "Dirty"}],
            "in_use": False, "count": None, "placement": "floor"},
           {"object_id": "78", "name_key": "111", "where": "inventory", "in_use": True, "count": 2, "value": 20},
           {"object_id": "79", "name_key": "111", "value": 5}]
    skipped = []
    words = reach.list_words("things", raw, refs=RefBook(), rooms={"3": "Test Kitchen"}, resolve=names.get,
                             skipped=skipped)
    assert words == [
        {"ref": "t2", "id": "78", "name": "Test Chair", "where": "inventory", "states": [], "in_use": True,
         "value": 20, "made_by_her": None, "placement": None, "count": 2},
        {"ref": "t1", "id": "77", "name": "Test Chair", "where": "Test Kitchen", "states": ["Dirty"],
         "in_use": False, "value": 60, "made_by_her": True, "placement": "floor"}]
    assert skipped == ["where"]


def test_a_thing_takes_its_name_from_the_catalogue_when_its_own_name_is_not_given():
    names = {"222": "Test Table"}

    def catalog_entry(definition_id):
        return {"name_key": "222"} if definition_id == 5 else None
    raw = [{"object_id": "80", "definition_id": 5, "where": "outside", "value": 9}]
    words = reach.list_words("things", raw, refs=RefBook(), resolve=names.get, catalog=catalog_entry)
    assert words[0]["name"] == "Test Table" and words[0]["where"] == "outside"


def test_states_are_words_at_most_four():
    raw = [{"object_id": "81", "name_key": "222", "where": "inventory", "value": 1,
            "states": [{"state": "Broken", "value": "Broken_Broken"}, {"state": "Dirty", "value": "Dirty_Dirty"},
                       {"state": "Spoiled", "value": "Spoiled"}, {"state": "A", "value": "A_One"},
                       {"state": "B", "value": "B_Two"}]}]
    states = reach.list_words("things", raw, refs=RefBook(), resolve={"222": "Test Table"}.get)[0]["states"]
    assert len(states) == 4 and states[0] == "Broken Broken"


def test_events_are_named_and_priced_when_the_price_is_readable():
    names = {"222": "Test Party"}
    raw = [{"situation_id": 5000, "name_key": "222", "cost": 150, "schedulable": True},
           {"situation_id": "5001", "name_key": "999", "cost": None},
           {"situation_id": "5002", "name_key": "222"}]
    skipped = []
    assert reach.list_words("events", raw, refs=RefBook(), resolve=names.get, skipped=skipped) == [
        {"ref": "e1", "id": "5000", "name": "Test Party", "cost": 150},
        {"ref": "e2", "id": "5002", "name": "Test Party", "cost": None}]
    assert skipped == ["name"]


def test_the_digest_is_the_sha256_of_the_canonical_items_and_changes_with_them():
    items = [{"ref": "p1", "id": "1", "name": "Test"}]
    raw = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert reach.digest(items) == hashlib.sha256(raw).hexdigest()
    assert reach.digest(items) != reach.digest([dict(items[0], name="Other")])


def test_a_list_too_big_for_one_body_is_cut_from_its_end_and_what_is_sent_fits():
    items = [{"ref": "t%d" % number, "id": str(number), "name": "x" * 400} for number in range(600)]
    kept = reach.fit(items)
    assert 0 < len(kept) < 600 and kept == items[:len(kept)]
    assert len(json.dumps(kept, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) <= reach.LIST_BYTES
    assert reach.fit(items[:3]) == items[:3]


def test_a_purchase_says_where_it_is_what_it_is_beside_what_it_faces_and_what_it_cuts_off():
    names = {"11": "Test Wall Shelf", "12": "Test Lamp", "13": "Test Table"}
    text = reach.result_words(
        {"room_id": 3, "wall": True, "wall_has": [11], "beside": [12, 13], "facing_id": 13,
         "routes_lost": ["door", "fridge", "rug"], "price": 120, "funds": 880},
        name_of=names.get, room_of={"3": "Test Kitchen"}.get)
    assert text == ("In Test Kitchen, against a wall with Test Wall Shelf, beside Test Lamp and Test Table. "
                    "Facing Test Table. Cuts off the way to the door and fridge. Costs §120; you have §880.")


def test_a_sale_an_event_and_a_trip_say_their_money_and_their_time():
    assert reach.result_words({"value": 40, "funds": 500}) == "Worth §40; you have §500."
    assert reach.result_words({"cost": 150, "funds": 350}, start={"day_offset": 1, "hour": 19, "minute": 5}) == (
        "Costs §150; you have §350. Starts at 19:05 tomorrow.")
    assert reach.result_words({"zone_id": 4}, place_of={"4": "Test Lot"}.get) == "Now in Test Lot."
    assert reach.result_words({}) is None


def test_a_discovery_record_is_one_file_per_session_the_newest_kept_and_a_bad_session_writes_nothing(tmp_path):
    folder = tmp_path / "discovery"
    row = {"event_kind": "discovery", "telemetry_session_id": "ab12-3",
           "e2": {"discovery_rev": 2, "sections": {"pickers": [{"guid": "1"}]}}}
    assert reach.write_discovery(folder, row) == "ab12-3.json"
    saved = json.loads((folder / "ab12-3.json").read_text(encoding="utf-8"))
    assert saved == {"telemetry_session_id": "ab12-3", "discovery_rev": 2, "e2": row["e2"]}
    newer = dict(row, e2={"discovery_rev": 3, "sections": {}})
    reach.write_discovery(folder, newer)
    assert json.loads((folder / "ab12-3.json").read_text(encoding="utf-8"))["discovery_rev"] == 3
    assert reach.write_discovery(folder, {"telemetry_session_id": "../escape"}) is None
    assert sorted(path.name for path in folder.iterdir()) == ["ab12-3.json"]


# W13 (H, P2): the catalogue. The probe's flags sit beside the game's names; a search offers furniture and decor only.
def _catalog_db(tmp_path, monkeypatch, rows):
    monkeypatch.setattr(Paths, "data_dir", property(lambda self: tmp_path / "data"))
    paths = Paths(tmp_path / "sims")
    target = catalog.index_path(paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target)
    connection.executescript(catalog.SCHEMA)
    connection.executemany("INSERT INTO catalog VALUES (?, ?, ?, ?, ?)",
                           [(definition, name_key, 0, 10, "test") for definition, name_key in rows])
    connection.commit()
    connection.close()
    return paths


def _flag(definition, categories, placement, price, purchasable=True):
    return {"definition_id": definition, "price": price, "buy_category": categories, "placement": placement,
            "tags": ["Test"], "purchasable": purchasable}


CATALOG_NAMES = {"1301": "Test Chair", "1302": "Test Chair Set", "1303": "Test Chair Panel", "1304": "Pine Lamp",
                 "1305": "Test Chair Hidden", "1306": "Test Vehicle Chair", "1307": "Test Chair Pricey",
                 "1308": "Pine Stool"}


def _catalog_fixture(tmp_path, monkeypatch):
    paths = _catalog_db(tmp_path, monkeypatch, [(301, 1301), (302, 1302), (303, 1303), (304, 1304), (305, 1305),
                                                (306, 1306), (307, 1307), (308, 1308)])
    catalog.store_flags(paths, "1.128", [
        _flag(301, ["COMFORT"], ["floor"], 80),
        _flag(302, ["DECOR"], ["floor"], 150),
        _flag(303, ["ROOF"], ["floor"], 20),
        _flag(304, ["LIGHTING"], ["wall"], 30),
        _flag(305, ["COMFORT"], ["floor"], 60, purchasable=False),
        _flag(306, ["VEHICLE"], ["floor"], 90),
        _flag(307, ["COMFORT"], ["floor"], 900),
        _flag(308, ["COMFORT"], ["floor"], 40)])
    return paths


def test_the_flags_are_kept_per_game_version_and_a_dump_replaces_its_own(tmp_path, monkeypatch):
    paths = _catalog_fixture(tmp_path, monkeypatch)
    assert catalog.has_flags(paths, "1.128") and not catalog.has_flags(paths, "1.129")
    assert catalog.store_flags(paths, "1.128", [_flag(301, ["COMFORT"], ["floor"], 80)]) == 1
    assert catalog.search(paths, "1.128", "test chair", resolve=CATALOG_NAMES.get) == (
        1, [{"definition_id": 301, "name": "Test Chair", "price": 80, "placement": "floor", "category": "comfort"}])


def test_a_search_offers_purchasable_furniture_and_decor_by_words_in_order_and_names_its_price(tmp_path, monkeypatch):
    paths = _catalog_fixture(tmp_path, monkeypatch)
    matched, items = catalog.search(paths, "1.128", "test chair", resolve=CATALOG_NAMES.get)
    assert matched == 3
    assert [item["definition_id"] for item in items] == [301, 307, 302]
    assert items[0] == {"definition_id": 301, "name": "Test Chair", "price": 80, "placement": "floor",
                        "category": "comfort"}
    assert catalog.search(paths, "1.128", "test chair", max_price=200, resolve=CATALOG_NAMES.get)[0] == 2
    matched, items = catalog.search(paths, "1.128", "lamp", placement="wall", resolve=CATALOG_NAMES.get)
    assert matched == 1 and items[0]["placement"] == "wall" and items[0]["category"] == "lighting"
    assert catalog.search(paths, "1.128", "lamp", placement="floor", resolve=CATALOG_NAMES.get) == (0, [])
    assert catalog.search(paths, "1.128", "   ", resolve=CATALOG_NAMES.get) == (0, [])
    assert catalog.search(paths, "1.129", "test chair", resolve=CATALOG_NAMES.get) == (0, [])


def test_a_search_gives_at_most_twelve_items_and_says_how_many_matched(tmp_path, monkeypatch):
    names = {str(1400 + number): "Test Pot %d" % number for number in range(14)}
    paths = _catalog_db(tmp_path, monkeypatch, [(400 + number, 1400 + number) for number in range(14)])
    catalog.store_flags(paths, "1.128", [_flag(400 + number, ["DECOR"], ["floor"], 5) for number in range(14)])
    matched, items = catalog.search(paths, "1.128", "test pot", resolve=names.get)
    assert matched == 14 and len(items) == 12


def test_a_catalogue_ask_is_answered_once_with_its_items_as_c_refs():
    client = _Mint()
    calls = []

    def search(words, max_price, placement):
        calls.append((words, max_price, placement))
        return 2, [{"definition_id": 301, "name": "Test Chair", "price": 80, "placement": "floor", "category": "comfort"},
                   {"definition_id": 302, "name": "Test Chair Set", "price": 150, "placement": "floor",
                    "category": "decor"}]
    ask_id = "ask-" + uuid.uuid4().hex[:8]
    ask = {"ask_id": ask_id, "words": "test chair", "max_price": 100, "placement": "floor", "room": "Test Kitchen"}
    catalog_ask.handle_asks_in_background([ask, ask], client, helper_session="h", refs=RefBook(), search=search,
                                          start=lambda run: run())
    assert client.posted["catalog"] == [{
        "v": 1, "helper_session": "h", "ask_id": ask_id, "matched": 2,
        "items": [{"ref": "c1", "id": "301", "name": "Test Chair", "price": 80, "placement": "floor",
                   "category": "comfort"},
                  {"ref": "c2", "id": "302", "name": "Test Chair Set", "price": 150, "placement": "floor",
                   "category": "decor"}]}]
    assert calls == [("test chair", 100, "floor")]


def test_a_failing_search_answers_nothing_found_and_a_bad_ask_is_not_answered_at_all():
    client = _Mint()

    def failing(words, max_price, placement):
        raise ValueError("no catalogue")
    ask_id = "ask-" + uuid.uuid4().hex[:8]
    catalog_ask.handle_asks_in_background([{"ask_id": ask_id, "words": "chair"}], client, helper_session="h",
                                          refs=RefBook(), search=failing, start=lambda run: run())
    assert client.posted["catalog"][0]["matched"] == 0 and client.posted["catalog"][0]["items"] == []
    catalog_ask.handle_asks_in_background([{"ask_id": "ask-bad-" + ask_id, "words": "   "}], client,
                                          helper_session="h", refs=RefBook(), search=failing, start=lambda run: run())
    assert len(client.posted["catalog"]) == 1


# W13 (D4.3, D4.2, D5.2): a text or call is a fact with its sender's name; a waiting visitor and a work end are in the
# portrait.
def test_a_text_or_a_call_on_her_phone_is_a_percept_with_its_senders_name():
    extractor = Extractor()
    extractor.people_names = {"501": "Test Person"}
    row = {"event_kind": "phone", "telemetry_session_id": "s", "written_sequence": 1, "wall_timestamp_ms": WALL,
           "e2": {"kind": "call", "from_sim_id": "501", "notifies": None}}
    phone = [p for p in extractor.step(row) if p.kind == "phone"]
    assert len(phone) == 1 and dict(phone[0].facts) == {"what": "call", "from": "Test Person"}
    unknown = dict(row, e2={"kind": "call", "from_sim_id": "777", "notifies": None})
    assert dict((p.kind, dict(p.facts)) for p in extractor.step(unknown))["phone"] == {"what": "call"}
    assert [p for p in extractor.step(dict(row, e2={"kind": "email", "from_sim_id": "501"})) if p.kind == "phone"] == []


def test_a_visitor_waiting_at_the_door_is_said_so_and_a_work_end_is_a_clock_minute():
    item = {"id": "601", "name": "Test Visitor", "distance_m": 2.0, "on_lot": True, "waiting": True}
    assert _company_seen(item, None)["waiting"] is True
    assert "waiting" not in _company_seen(dict(item, waiting=False), None)
    job = {"career": "Test Career", "text_key": None, "title_key": None, "level": 2, "at_work": True, "until_min": 1020}
    assert _job(job, None) == {"job": "Test Career", "title": None, "level": 2, "at_work": True, "until_min": 1020}
    assert "until_min" not in _job(dict(job, until_min=None), None)


# The bridge: the probe's rows come in, and the lists, the catalogue and the discovery reach their places.
def test_a_discovery_record_is_kept_in_a_file_for_the_lead_and_logged(paths, tmp_path, monkeypatch):
    data = _data(paths, tmp_path, monkeypatch)
    row = {"event_kind": "discovery", "written_sequence": 1, "wall_timestamp_ms": WALL,
           "monotonic_ns": WALL * 1_000_000, "telemetry_session_id": "sess-1", "sims_build": BUILD,
           "probe_version": "2.40.0", "e2": {"discovery_rev": 1, "sections": {"pickers": [{"guid": "1"}]}}}
    _append(paths, [row])
    bridge = _bridge(paths, {"ms": WALL}, client=_Mint())
    bridge.tick(WALL)
    saved = json.loads((data / "discovery" / "sess-1.json").read_text(encoding="utf-8"))
    assert saved["e2"]["sections"]["pickers"] == [{"guid": "1"}]
    lines = [line for line in _log_lines(data) if line.get("trigger") == "discovery"]
    assert len(lines) == 1 and lines[0]["file"] == "sess-1.json" and "pickers" in lines[0]["sections"]


def _people_row(at, sim="501", name="Person"):
    return {"event_kind": "lists", "telemetry_session_id": "sess-1", "written_sequence": at, "wall_timestamp_ms": WALL,
            "e2": {"kind": "people", "list_rev": 1, "part": 0, "parts": 1, "digest": "a" * 64, "count": 1,
                   "items": [{"sim_id": sim, "first_name": "Test", "last_name": name, "labels": ["Friend"],
                              "tracks": {}, "household_id": 9, "has_home": False, "on_lot": True, "waiting": False}]}}


def test_a_list_is_sent_in_words_until_natalis_holds_its_digest_and_not_sent_again_after(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    _append(paths, [_people_row(1)])
    client = _Mint()
    bridge = _bridge(paths, {"ms": WALL}, client=client)
    bridge.tick(WALL)
    _settle(bridge)
    assert len(client.posted["lists"]) == 1
    body = client.posted["lists"][0]
    assert body["kind"] == "people" and body["helper_session"] == bridge.helper_session
    assert body["items"] == [{"ref": "p1", "id": "501", "name": "Test Person", "how": "Friend", "home": False,
                              "here": True, "waiting": False}]
    assert body["digest"] == reach.digest(body["items"])
    client.answer["lists"] = {"people": body["digest"]}
    bridge.tick(WALL + 1000)
    assert len(client.posted["lists"]) == 1


def test_a_refused_list_waits_its_retry_wait_and_a_restart_keeps_the_list_to_send_again(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    _append(paths, [_people_row(1)])
    client = _Mint()
    client.refuse_lists = True
    mono = {"ms": 0}
    bridge = _bridge(paths, mono, client=client)
    bridge.tick(WALL)
    _settle(bridge)
    assert client.posted["lists"] == []
    mono["ms"] = 1000
    bridge.tick(WALL + 1000)
    _settle(bridge)
    client.refuse_lists = False
    mono["ms"] = bridge_module.LIST_RETRY_MS
    bridge.tick(WALL + bridge_module.LIST_RETRY_MS)
    _settle(bridge)
    assert len(client.posted["lists"]) == 1
    digest = client.posted["lists"][0]["digest"]
    client.held = {}  # Natalis lost its copy: a restarted helper has no new row, so the list comes from the spool
    restarted = _bridge(paths, mono, client=client)
    restarted.tick(WALL + bridge_module.LIST_RETRY_MS + 1000)
    _settle(restarted)
    assert [body["digest"] for body in client.posted["lists"]] == [digest, digest]


def test_the_catalogue_flags_arrive_in_parts_and_are_stored_for_the_running_build(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    flags = [_flag(301, ["COMFORT"], ["floor"], 80), _flag(302, ["DECOR"], ["wall"], 40)]
    _append(paths, [{"event_kind": "catalog", "telemetry_session_id": "sess-1", "written_sequence": 1,
                     "wall_timestamp_ms": WALL,
                     "e2": {"catalog_rev": BUILD, "part": 0, "parts": 2, "items": flags[:1]}},
                    {"event_kind": "catalog", "telemetry_session_id": "sess-1", "written_sequence": 2,
                     "wall_timestamp_ms": WALL,
                     "e2": {"catalog_rev": BUILD, "part": 1, "parts": 2, "items": flags[1:]}}])
    bridge = _bridge(paths, {"ms": WALL}, client=_Mint())
    bridge.tick(WALL)
    assert catalog.has_flags(bridge.paths, BUILD) and not catalog.has_flags(bridge.paths, "1.0.0.0")


def test_the_catalogue_is_asked_for_once_when_its_flags_are_missing_on_a_new_enough_probe(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    asked = []
    monkeypatch.setattr(bridge_module.commands, "publish",
                        lambda command, args, issuer, paths=None: asked.append(command) or "cmd")
    bridge = _bridge(paths, {"ms": WALL}, client=_Mint())
    bridge._state = "attached"
    bridge._catalog_dump(WALL, "2.40.0")
    bridge._catalog_dump(WALL + 1000, "2.40.0")
    assert asked == ["catalog_dump"]
    later = WALL + bridge_module.CATALOG_DUMP_EVERY_MS + 1
    bridge._catalog_dump(later, "2.39.0")
    assert asked == ["catalog_dump"]
    bridge._catalog_dump(later + 1, "2.40.0")
    assert asked == ["catalog_dump", "catalog_dump"]
    catalog.store_flags(bridge.paths, BUILD, [_flag(301, ["COMFORT"], ["floor"], 80)])
    bridge._catalog_dump(later + bridge_module.CATALOG_DUMP_EVERY_MS + 5, "2.40.0")
    assert asked == ["catalog_dump", "catalog_dump"]


def test_a_catalogue_ask_in_a_sync_answer_is_handed_to_the_catalogue_once(paths, tmp_path, monkeypatch):
    _data(paths, tmp_path, monkeypatch)
    handed = []
    monkeypatch.setattr(catalog_ask, "handle_asks_in_background",
                        lambda asks, client, **kw: handed.append((asks, kw["helper_session"])))
    bridge = _bridge(paths, {"ms": WALL}, client=_Mint())
    ask = {"ask_id": "ask-x", "words": "test chair"}
    bridge._answered({"catalog": [ask]}, bridge.client, "h")
    assert handed == [([ask], "h")]


# W13 (H): Natalis checks each body's shape strictly, so every body the helper builds from fake probe rows is checked
# here against its bounds: names clipped and never empty, the keys of each kind and no others, the item limits, the
# body and the event detail sizes.
REF_PATTERN = re.compile(r"^[a-z][0-9]{1,8}$")
LIST_SHAPE = {
    "people": ({"ref", "id", "name", "how", "home", "here", "waiting"}, set()),
    "places": ({"ref", "id", "name", "kind", "what"}, set()),
    "things": ({"ref", "id", "name", "where", "value", "made_by_her", "states", "in_use", "placement"}, {"count"}),
    "events": ({"ref", "id", "name", "cost"}, set()),
}


def _check_list_items(kind, items):
    required, optional = LIST_SHAPE[kind]
    assert len(items) <= reach.LIMITS[kind]
    for item in items:
        assert required <= set(item) <= required | optional, sorted(set(item) ^ required)
        assert REF_PATTERN.match(item["ref"])
        assert isinstance(item["id"], str) and 1 <= len(item["id"]) <= 64
        assert isinstance(item["name"], str) and item["name"].strip() and len(item["name"]) <= 64
        for flag in ("home", "here", "waiting", "in_use"):
            if flag in item:
                assert isinstance(item[flag], bool)
        if "how" in item:
            assert len(item["how"]) <= 80
        if "what" in item:
            assert len(item["what"]) <= 40
        if "where" in item:
            assert 1 <= len(item["where"]) <= 64
        if "made_by_her" in item:
            assert item["made_by_her"] is None or isinstance(item["made_by_her"], bool)
        if "value" in item:
            assert type(item["value"]) is int
        if "count" in item:
            assert type(item["count"]) is int and item["count"] >= 0
        if "placement" in item:
            assert item["placement"] is None or 1 <= len(item["placement"]) <= 16
        if "cost" in item:
            assert item["cost"] is None or type(item["cost"]) is int
        if "states" in item:
            assert len(item["states"]) <= 4 and all(1 <= len(state) <= 40 for state in item["states"])


def test_every_list_built_from_fake_probe_rows_keeps_natalis_bounds_and_an_unnamed_item_is_skipped():
    long_name = "Long " + "n" * 120
    long_state = "S" * 90
    people = [{"sim_id": str(1000 + n), "first_name": "F" * 80, "last_name": "", "labels": ["L" * 50] * 6,
               "tracks": {"T%d" % t: 40 for t in range(6)}, "household_id": 9, "has_home": True,
               "on_lot": n % 2 == 0, "waiting": False} for n in range(205)]
    people.append({"sim_id": "9999", "first_name": "", "last_name": "", "labels": [], "tracks": {}})
    skipped = []
    people_words = reach.list_words("people", people, refs=RefBook(), skipped=skipped)
    _check_list_items("people", people_words)
    assert len(people_words) == 200 and max(len(item["how"]) for item in people_words) <= 80
    assert "over_limit" in skipped and "name" not in skipped  # the unnamed one is kept, past the limit

    places = [{"zone_id": 4, "kind": "home", "lot_name": "H" * 90},
              {"zone_id": 6, "kind": "household", "lot_name": "", "household_id": 9},
              {"zone_id": 7, "kind": "venue", "lot_name": "V" * 90, "venue": "v" * 90}]
    place_words = reach.list_words("places", places, refs=RefBook(), households={"9": "B" * 70})
    _check_list_items("places", place_words)
    assert place_words[1]["what"] == "B" * 40 and place_words[1]["name"] == ("B" * 70 + "'s home")[:64]

    things = [{"object_id": str(50 + n), "name_key": "1", "where": {"where": "room", "room_id": 3},
               "value": n, "made_by_her": None, "states": [{"state": "x", "value": long_state}] * 6,
               "in_use": False, "count": 2, "placement": "floor, wall, surface"} for n in range(610)]
    things.append({"object_id": "900", "name_key": "1", "where": {"where": "room", "room_id": 3}, "value": None})
    things.append({"object_id": "901", "name_key": "2", "where": "outside", "value": 3})
    things.append({"object_id": "902", "name_key": "1", "where": "inventory", "value": 4})
    skipped = []
    thing_words = reach.list_words("things", things, refs=RefBook(), rooms={"3": "R" * 80},
                                   resolve={"1": long_name}.get, skipped=skipped)
    _check_list_items("things", thing_words)
    assert len(thing_words) == 600 and skipped.count("name") == 1 and "value" not in skipped
    assert thing_words[0]["where"] == "inventory" and thing_words[0]["id"] == "902"
    assert thing_words[1]["where"] == "R" * 64 and thing_words[1]["placement"] is None
    assert thing_words[1]["states"] == ["S" * 40]
    assert thing_words[1]["name"] == long_name[:64]

    events = [{"situation_id": 5000, "name_key": "1", "cost": 150}, {"situation_id": 5001, "name_key": "2"},
              {"situation_id": 5002, "name_key": "1", "cost": None}]
    event_words = reach.list_words("events", events, refs=RefBook(), resolve={"1": long_name}.get)
    _check_list_items("events", event_words)
    assert [item["cost"] for item in event_words] == [150, None]

    for items in (people_words, place_words, thing_words, event_words):
        body = json.dumps(reach.fit(items), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        assert len(body) <= reach.LIST_BYTES


def test_a_catalogue_answer_built_from_fake_flags_keeps_natalis_bounds(tmp_path, monkeypatch):
    names = {"1500": "Long Lamp " + "x" * 80, "1501": "", "1502": "Pine Lamp"}
    paths = _catalog_db(tmp_path, monkeypatch, [(500, 1500), (501, 1501), (502, 1502)] +
                        [(600 + n, 1502) for n in range(14)])
    catalog.store_flags(paths, "1.128", [_flag(500, ["LIGHTING"], ["floor"], 9),
                                         _flag(501, ["LIGHTING"], ["floor"], 9),
                                         _flag(502, ["LIGHTING"], ["wall"], 12)] +
                        [_flag(600 + n, ["DECOR"], ["floor"], 3) for n in range(14)])
    matched, items = catalog.search(paths, "1.128", "lamp", resolve=names.get, shown=20)
    assert matched == 16 and len(items) == 16
    body = catalog_ask.answer_body("h", "ask-bounds", matched, items, RefBook())
    assert len(body["items"]) == 12 and body["matched"] == 16
    for item in body["items"]:
        assert REF_PATTERN.match(item["ref"]) and isinstance(item["id"], str)
        assert 1 <= len(item["name"]) <= 64 and type(item["price"]) is int
        assert item["placement"] is None or 1 <= len(item["placement"]) <= 16
        assert len(item["category"]) <= 40
    assert all(item["name"].strip() for item in body["items"])
    assert {item["placement"] for item in body["items"]} <= {"floor", "wall"}


def test_a_sync_event_detail_stays_under_1024_bytes_and_its_result_under_400(tmp_path):
    def detail_of(detail_chars, result_chars):
        folder = tmp_path / ("c%d_%d" % (detail_chars, result_chars))
        folder.mkdir()
        courier, _sent = _courier(folder, result_words=lambda result, start=None: "r" * result_chars)
        courier.tick(_Mint(acts=[_verb("sell", {"object_id": "5"})]), "h", 1000, True, probe="2.40.0")
        courier.on_row({"event_kind": "act_event", "telemetry_session_id": "s", "wall_timestamp_ms": 2000,
                        "e2": {"act_id": VERB_ACT, "phase": "FINISHED", "detail": "d" * detail_chars,
                               "result": {"room_id": 3}}})
        return [e for e in courier._events if e["phase"] == "finished"][0].get("detail", {})

    detail = detail_of(700, 900)
    assert len(json.dumps(detail, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) <= 1024
    assert 0 < len(detail["result"]) <= 400
    assert "result" not in detail_of(1100, 300)
