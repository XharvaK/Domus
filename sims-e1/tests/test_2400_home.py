"""2.40.0 (W13 P2, probe: home): the things list and the catalogue (their shapes, bounds and parts), her save (the
floor, the lock, the slot), and her home edits (buy, place, move, sell): each refusal and its code, the order of the
charge and the create, the refund and removal after a failed placement, the routes reported, and the result facts.

Fakes only: the actuator, observers, services and the clock are replaced; no game, no live services. One class runs
the real probe dispatch through the act harness (test_2160_act), so the commands reach home.py from the inbox."""
import importlib.util
import json
import os
import types
import unittest
from unittest import mock

import test_2160_act as acts
from test_binding import load_probe

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SPEC = importlib.util.spec_from_file_location("p2_check_guards",
                                              os.path.join(ROOT, "tools", "check_guards.py"))
guards = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guards)

ACT = "e" * 32
ACT_TWO = "f" * 32


def modules():
    """The probe's home, cmdbox and schema, loaded with the fake game modules."""
    package, probe, _calls = load_probe()
    from ashley_e1 import cmdbox, home, schema
    return probe, home, cmdbox, schema


class FakeTime(object):
    def __init__(self, now=1000.0):
        self.now = now

    def time(self):
        return self.now


class FakeFunds(object):
    def __init__(self, money):
        self.money = money

    def can_afford(self, amount):
        return self.money >= amount

    def try_remove(self, amount, reason, sim, require_full_amount):
        if self.money < amount:
            return False
        self.money -= amount
        return True

    def add(self, amount, reason):
        self.money += amount


class FakeObj(object):
    def __init__(self, object_id, class_name="Chair", owner="9", value=40, is_sim=False, portal=False,
                 in_use=False, inventory=False, spot=None, reach=(None, None), near=()):
        self.id = object_id
        self.class_name = class_name
        self.owner = owner
        self.value = value
        self.is_sim = is_sim
        self.portal = portal
        self.in_use = in_use
        self.inventory = inventory
        self.spot = spot
        self.reach = reach
        self.near = list(near)
        self.wall = False
        self.removed = False


class FakeControl(object):
    """The controller's part the home commands use: the act records, the lines, the sample state and the events."""

    def __init__(self):
        self.act_ids = set()
        self.events = []
        self.lines = []
        self.emitted = []
        self.state = "SAMPLING"
        self.lineage_class = None
        self.designated_sim_id = None

    def available(self):
        return True

    def _state(self):
        return self.state

    def _armed_snapshot(self):
        return {"sim_id": "7"}

    def _act_event(self, act_id, phase, **payload):
        row = dict(payload)
        row["act_id"], row["phase"] = act_id, phase
        self.events.append(row)

    def _say(self, connection, text):
        self.lines.append(text)

    def _event(self, kind, payload):
        self.emitted.append((kind, payload))
        return True

    def phases(self):
        return [(row["phase"], row.get("code")) for row in self.events]


class FakeActuator(object):
    """The game's reads and effects, as home.py calls them. Effects are recorded in calls."""

    def __init__(self):
        self.home = True
        self.build = False
        self.slot = (2, "Test Slot", False, None)
        self.money = 500
        self.funds = FakeFunds(self.money)
        self.price = 150
        self.tags = []
        self.defs = {"55": object()}
        self.objects = {}
        self.lot = []
        self.placed = False
        self.calls = []
        self.spot = {"translation": "at", "orientation": "o", "routing_surface": "s", "slot": None}
        self.created = []
        self.create_fail = False
        self.place_error = None
        self.sell_error = None
        self.save_error = None
        self.callbacks = []
        self.catalog = None
        self.things = None
        self.wall_for = {}

    # reads
    def at_home(self, household_id):
        return self.home

    def build_mode(self):
        return self.build

    def room_of(self, obj):
        return "5"

    def is_wall_placed(self, obj):
        return obj.wall

    def near_objects(self, obj, radius):
        return list(obj.near)

    def lot_objects(self):
        return list(self.lot)

    def class_name(self, obj):
        return obj.class_name

    def is_portal(self, obj):
        return obj.portal

    def reachable(self, sim, obj):
        before, after = obj.reach
        return after if self.placed else before

    def is_sim(self, obj):
        return obj.is_sim

    def owner_of(self, obj):
        return obj.owner

    def in_use(self, obj):
        return obj.in_use

    def in_inventory(self, obj):
        return obj.inventory

    def find_object(self, object_id):
        return self.objects.get(str(object_id))

    def find_spot(self, obj, sim, place):
        self.calls.append(("find_spot", place["rel"]))
        return self.spot

    def spot_of(self, obj):
        return obj.spot

    def spot_key(self, spot):
        return None if spot is None else tuple(spot["translation"])

    def definition(self, def_id):
        return self.defs.get(str(def_id))

    def definition_price(self, defn):
        return self.price

    def definition_tags(self, defn):
        return list(self.tags)

    def household_funds(self, household_id):
        return self.funds

    def can_afford(self, funds, amount):
        return funds.can_afford(amount)

    def funds_money(self, funds):
        return funds.money

    def value_of(self, obj):
        return obj.value

    def save_slot(self):
        return self.slot

    def catalog_rows(self):
        return self.catalog

    def things_rows(self):
        return self.things

    # effects
    def funds_try_remove(self, funds, amount, sim):
        self.calls.append(("try_remove", amount))
        return funds.try_remove(amount, "x", sim, True)

    def funds_add(self, funds, amount, sim):
        self.calls.append(("add", amount))
        funds.add(amount, "x")

    def create_unplaced(self, defn):
        self.calls.append(("create",))
        if self.create_fail:
            return None
        obj = FakeObj("900%d" % len(self.created), class_name="Chair")
        self.created.append(obj)
        self.objects[obj.id] = obj
        return obj

    def remove_created(self, obj):
        self.calls.append(("remove_created", obj.id))
        obj.removed = True
        self.objects.pop(obj.id, None)
        return True

    def place(self, obj, spot):
        self.calls.append(("place", obj.id))
        if self.place_error is not None:
            raise self.place_error
        self.placed = True

    def sell_object(self, obj):
        self.calls.append(("sell", obj.id))
        if self.sell_error is not None:
            raise self.sell_error
        obj.removed = True
        self.objects.pop(obj.id, None)

    def save_now(self, slot_id, slot_name):
        self.calls.append(("save", slot_id, slot_name))
        if self.save_error is not None:
            raise self.save_error

    def subscribe_saves(self, callback):
        self.callbacks.append(callback)

    def unsubscribe_saves(self, callback):
        self.callbacks.remove(callback)


class FakeObservers(object):
    ALL_HIDDEN_REASONS = object()

    def __init__(self, info, sim):
        self.info, self.sim = info, sim

    def select_lab_body(self, infos, flags):
        return self.info, self.sim

    def build_mode(self):
        return False

    def active_sim_id(self):
        return None


class HomeCase(unittest.TestCase):
    """Loads the probe once per test, and swaps the home module's game parts for fakes."""

    def setUp(self):
        self.probe, self.home, self.cmdbox, self.schema = modules()
        self.actuator = FakeActuator()
        info = types.SimpleNamespace(id=7, household_id=9)
        sim = object()
        self.clock = FakeTime()
        patches = [
            mock.patch.object(self.home, "e2_actuator", self.actuator),
            mock.patch.object(self.home, "observers", FakeObservers(info, sim)),
            mock.patch.object(self.home, "services", types.SimpleNamespace(
                sim_info_manager=lambda: types.SimpleNamespace(get_all=lambda: [info]))),
            mock.patch.object(self.home, "time", self.clock),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.sim = sim
        self.control = FakeControl()

    def run_cmd(self, name, args, act_id=ACT):
        args = dict(args)
        if name != "catalog_dump":
            args["act_id"] = act_id
        return self.home.dispatch(self.control, name, args, "helper")

    def object_facts(self, row):
        return row.get("result")


def _place(rel="on", target="41", **extra):
    place = {"rel": rel}
    if rel in ("on", "beside", "instead"):
        place["target_id"] = target
    else:
        place["room_id"] = target
    place.update(extra)
    return place


class SaveRuleTests(unittest.TestCase):
    def setUp(self):
        self.home = modules()[1]

    def test_never_saved_may_save(self):
        self.assertIsNone(self.home.save_gate(None, 5000.0))

    def test_inside_the_floor_says_the_whole_seconds_left(self):
        left = self.home.save_gate(1000.0, 1000.0 + 60.0)
        self.assertEqual(left, self.home.SAVE_FLOOR_S - 60 + 1)

    def test_at_the_floor_she_may_save_again(self):
        self.assertIsNone(self.home.save_gate(1000.0, 1000.0 + self.home.SAVE_FLOOR_S))

    def test_the_floor_is_fifteen_real_minutes(self):
        self.assertEqual(self.home.SAVE_FLOOR_S, 900)


class ThingsListTests(HomeCase):
    def raw(self, **overrides):
        row = {"object_id": 41, "definition_id": 55, "name_key": 123, "class_name": "Chair", "where": "room",
               "room_id": 5, "value": 40, "made_by_her": None, "states": [{"state": "dirty", "value": 3}],
               "in_use": False, "count": None, "placement": "floor"}
        row.update(overrides)
        return row

    def test_a_room_thing_keeps_its_room_and_a_plain_shape(self):
        item = self.home.shape_thing(self.raw())
        self.assertEqual(item["object_id"], "41")
        self.assertEqual(item["room_id"], "5")
        self.assertEqual(item["states"], [{"state": "dirty", "value": 3}])
        self.assertEqual(set(item), set(self.schema.THING_KEYS))

    def test_a_room_thing_without_a_room_is_left_out(self):
        self.assertIsNone(self.home.shape_thing(self.raw(room_id=None)))

    def test_an_inventory_thing_has_no_room(self):
        item = self.home.shape_thing(self.raw(where="inventory", room_id=5))
        self.assertEqual((item["where"], item["room_id"]), ("inventory", None))

    def test_no_id_or_unknown_place_is_left_out(self):
        self.assertIsNone(self.home.shape_thing(self.raw(object_id=None)))
        self.assertIsNone(self.home.shape_thing(self.raw(where="garden")))

    def test_at_most_four_states_and_a_known_placement(self):
        many = [{"state": "s%d" % i, "value": i} for i in range(9)]
        item = self.home.shape_thing(self.raw(states=many, placement="ceiling"))
        self.assertEqual(len(item["states"]), 4)
        self.assertIsNone(item["placement"])

    def test_build_items_are_not_things(self):
        rows = [self.raw(class_name="Wall"), self.raw(class_name="FrontDoor", object_id=42),
                self.raw(class_name="WallLight", object_id=43)]
        kept = [item["object_id"] for item in self.home.things_items(rows)]
        self.assertEqual(kept, ["43"])

    def test_at_most_six_hundred_things(self):
        rows = [self.raw(object_id=1000 + index) for index in range(700)]
        self.assertEqual(len(self.home.things_items(rows)), self.home.THINGS_MAX)

    def test_the_things_record_validates(self):
        items = self.home.things_items([self.raw(), self.raw(object_id=42, where="inventory", room_id=None,
                                                            count=2)])
        for payload in self.home.list_parts("things", 1, items):
            row = self.schema.make_record("lists", telemetry_session_id="s" * 32, wall_timestamp_ms=1,
                                          monotonic_ns=2, e2=dict(payload))
            self.schema.validate_record(row)

    def test_a_thing_with_a_bad_room_fails_the_record_check(self):
        item = self.home.shape_thing(self.raw())
        item["room_id"] = "room five"
        with self.assertRaises(self.schema.SchemaError):
            self.schema._validate_thing(item)

    def test_parts_hold_at_most_one_hundred_twenty_eight_items(self):
        items = [{"n": index} for index in range(300)]
        parts = self.home.list_parts("things", 2, items)
        self.assertEqual([len(part["items"]) for part in parts], [128, 128, 44])
        self.assertEqual([part["part"] for part in parts], [0, 1, 2])
        self.assertEqual({part["parts"] for part in parts}, {3})
        self.assertEqual({part["list_rev"] for part in parts}, {2})

    def test_an_empty_list_is_one_empty_part(self):
        parts = self.home.list_parts("things", 1, [])
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0]["items"], [])

    def test_a_part_stays_under_its_byte_budget(self):
        big = [{"text": "x" * 900} for _ in range(120)]
        for part in self.home.list_parts("things", 1, big):
            self.assertLessEqual(len(self.home.json.dumps(part["items"])), self.home.LIST_PART_BYTES + 2048)

    def test_the_digest_ignores_key_order_and_follows_the_items(self):
        one = [{"a": 1, "b": 2}]
        self.assertEqual(self.home.items_digest(one), self.home.items_digest([{"b": 2, "a": 1}]))
        self.assertNotEqual(self.home.items_digest(one), self.home.items_digest([{"a": 1, "b": 3}]))

    def test_a_list_is_written_when_its_digest_changes_and_checked_once_a_minute(self):
        self.actuator.things = [self.raw()]
        self.assertTrue(self.home.write_things(self.control, now=100.0))
        self.assertEqual([kind for kind, _ in self.control.emitted], ["lists"])
        self.assertEqual(self.control.emitted[0][1]["list_rev"], 1)
        self.assertFalse(self.home.write_things(self.control, now=130.0))
        self.actuator.things = [self.raw(), self.raw(object_id=42)]
        self.assertFalse(self.home.write_things(self.control, now=130.0))
        self.assertTrue(self.home.write_things(self.control, now=161.0))
        self.assertEqual(self.control.emitted[-1][1]["list_rev"], 2)

    def test_a_forced_write_goes_out_even_when_the_digest_is_the_same(self):
        self.actuator.things = [self.raw()]
        self.home.write_things(self.control, now=100.0)
        self.assertTrue(self.home.write_things(self.control, force=True, now=101.0))
        self.assertEqual(self.control.emitted[-1][1]["list_rev"], 2)


class CatalogTests(HomeCase):
    def raw(self, **overrides):
        row = {"definition_id": 77, "price": 120, "tags": ["Comfort"], "class_name": "Sofa", "sim": False,
               "buy_category": None, "placement": None}
        row.update(overrides)
        return row

    def test_furniture_with_a_price_is_a_catalogue_item(self):
        items = self.home.catalog_items([self.raw()])
        self.assertEqual(items, [{"definition_id": "77", "price": 120, "buy_category": [], "placement": None,
                                  "tags": ["Comfort"], "purchasable": True}])

    def test_sims_build_items_and_free_things_are_left_out(self):
        rows = [self.raw(sim=True), self.raw(class_name="Wall", definition_id=78),
                self.raw(class_name="FrontDoor", definition_id=79), self.raw(price=0, definition_id=80)]
        kept = self.home.catalog_items(rows)
        self.assertEqual([item["definition_id"] for item in kept], ["80"])
        self.assertFalse(kept[0]["purchasable"])

    def test_a_hidden_tag_is_not_purchasable(self):
        item = self.home.shape_catalog(self.raw(tags=["Debug Only"]))
        self.assertFalse(item["purchasable"])

    def test_a_catalogue_part_holds_at_most_256_items_and_validates(self):
        rows = [self.raw(definition_id=1000 + index) for index in range(600)]
        items = self.home.catalog_items(rows)
        parts = self.home.catalog_parts("1.128", items)
        self.assertEqual([len(part["items"]) for part in parts], [256, 256, 88])
        for payload in parts:
            row = self.schema.make_record("catalog", telemetry_session_id="s" * 32, wall_timestamp_ms=1,
                                          monotonic_ns=2, e2=dict(payload))
            self.schema.validate_record(row)

    def test_catalog_dump_writes_the_parts_and_says_how_many(self):
        self.actuator.catalog = [self.raw(), self.raw(definition_id=78, price=40)]
        self.assertTrue(self.run_cmd("catalog_dump", {}))
        kinds = [kind for kind, _ in self.control.emitted]
        self.assertEqual(kinds, ["catalog"])
        self.assertEqual(self.control.emitted[0][1]["catalog_rev"], self.schema.SIMS_BUILD)
        self.assertEqual(self.control.lines[-1], "CATALOG_WRITTEN 2")

    def test_catalog_dump_says_when_the_definitions_cannot_be_read(self):
        self.actuator.catalog = None
        self.assertFalse(self.run_cmd("catalog_dump", {}))
        self.assertEqual(self.control.lines[-1], "CATALOG_UNREADABLE")
        self.assertEqual(self.control.emitted, [])


class ResultFactTests(HomeCase):
    def test_the_wall_names_what_it_backs_on_and_what_is_beside(self):
        near = [{"object_id": "1", "distance": 0.4, "portal": True, "window": False},
                {"object_id": "2", "distance": 0.9, "portal": False, "window": True},
                {"object_id": "3", "distance": 1.0, "portal": False, "window": False},
                {"object_id": "4", "distance": 1.2, "portal": False, "window": False},
                {"object_id": "5", "distance": 1.4, "portal": False, "window": False},
                {"object_id": "6", "distance": 3.0, "portal": False, "window": False}]
        facts = self.home.placement_facts("5", True, near)
        self.assertEqual(facts["wall_has"], ["1", "2"])
        self.assertEqual(facts["beside"], ["3", "4", "5"])
        self.assertTrue(facts["wall"])

    def test_a_free_standing_thing_has_no_wall_words(self):
        near = [{"object_id": "1", "distance": 0.4, "portal": True, "window": False}]
        facts = self.home.placement_facts("5", False, near)
        self.assertEqual(facts["wall_has"], [])
        self.assertEqual(facts["beside"], ["1"])

    def test_beside_holds_at_most_four(self):
        near = [{"object_id": str(index), "distance": 0.1 * index, "portal": False, "window": False}
                for index in range(1, 9)]
        self.assertEqual(len(self.home.placement_facts("5", False, near)["beside"]), 4)

    def test_a_route_is_lost_only_when_the_game_reads_false_now(self):
        self.assertEqual(self.home.routes_lost({"bed": True, "toilet": True, "door": True},
                                               {"bed": False, "toilet": None, "door": None}), ["bed"])
        self.assertEqual(self.home.routes_lost({"fridge": True}, {"fridge": False}), ["fridge"])
        self.assertEqual(self.home.routes_lost({"bed": None}, {"bed": False}), [])

    def test_the_result_validates_as_an_act_event_row(self):
        facts = self.home.placement_facts("5", True, [{"object_id": "1", "distance": 0.2, "portal": True,
                                                      "window": False}], lost=["bed"], price=150, funds=350)
        result = dict((key, facts[key]) for key in self.home.RESULT_KEYS if key != "value")
        row = self.schema.make_record("act_event", telemetry_session_id="s" * 32, wall_timestamp_ms=1,
                                      monotonic_ns=2, e2=dict(act_id=ACT, phase="FINISHED", code="PLACED",
                                                              object_id="41", guid64=None, interaction_id=None,
                                                              tuning_name=None, finishing_type=None, detail=None,
                                                              reason_key=None, closed=None, resumed=None,
                                                              owner=None, started=None, aliases=None,
                                                              result=result))
        self.schema.validate_record(row)

    def test_a_result_with_text_or_a_stray_key_fails(self):
        with self.assertRaises(self.schema.SchemaError):
            self.schema._validate_result({"room_id": "5", "note": "a chair"})
        with self.assertRaises(self.schema.SchemaError):
            self.schema._validate_result({"routes_lost": ["garden"]})


class CommandShapeTests(unittest.TestCase):
    def setUp(self):
        self.cmdbox = modules()[2]

    def parse(self, command, args):
        raw = json.dumps({"v": 1, "id": "a" * 32, "issued_at_ms": 1000, "expires_at_ms": 5000,
                          "issuer": "helper", "command": command, "args": args}).encode("utf-8")
        return self.cmdbox.parse(raw, 2000, set())

    def test_the_home_commands_are_in_the_vocabulary(self):
        for name in ("save", "buy", "place", "move", "sell", "catalog_dump"):
            self.assertIn(name, self.cmdbox.COMMANDS)

    def test_save_takes_only_its_act(self):
        self.assertIsNone(self.parse("save", {"act_id": "b" * 32})[1])
        self.assertEqual(self.parse("save", {"act_id": "b" * 32, "x": 1})[1], "BAD_ARGS")

    def test_buy_needs_an_item_and_a_place(self):
        good = {"act_id": "b" * 32, "definition_id": "55", "place": {"rel": "wall", "room_id": "5"}}
        self.assertIsNone(self.parse("buy", good)[1])
        self.assertIsNone(self.parse("buy", dict(good, max_price=300))[1])
        self.assertEqual(self.parse("buy", dict(good, max_price=-1))[1], "BAD_ARGS")
        missing = dict(good)
        del missing["place"]
        self.assertEqual(self.parse("buy", missing)[1], "BAD_ARGS")

    def test_a_place_names_one_relation_with_its_own_key(self):
        base = {"act_id": "b" * 32, "object_id": "41"}
        self.assertIsNone(self.parse("place", dict(base, place={"rel": "on", "target_id": "7"}))[1])
        self.assertIsNone(self.parse("move", dict(base, place={"rel": "in", "room_id": "5", "facing": "room"}))[1])
        self.assertIsNone(self.parse("move", dict(base, place={"rel": "beside", "target_id": "7",
                                                              "facing": "8"}))[1])
        self.assertEqual(self.parse("place", dict(base, place={"rel": "on", "room_id": "5"}))[1], "BAD_ARGS")
        self.assertEqual(self.parse("place", dict(base, place={"rel": "wall", "target_id": "7"}))[1], "BAD_ARGS")
        self.assertEqual(self.parse("place", dict(base, place={"rel": "beside", "target_id": "7",
                                                              "facing": "north"}))[1], "BAD_ARGS")
        self.assertEqual(self.parse("place", dict(base, place={"rel": "above", "target_id": "7"}))[1], "BAD_ARGS")

    def test_sell_names_an_object(self):
        self.assertIsNone(self.parse("sell", {"act_id": "b" * 32, "object_id": "41"})[1])
        self.assertEqual(self.parse("sell", {"act_id": "b" * 32, "object_id": "x"})[1], "BAD_ARGS")

    def test_catalog_dump_takes_no_args(self):
        self.assertIsNone(self.parse("catalog_dump", {})[1])
        self.assertEqual(self.parse("catalog_dump", {"act_id": "b" * 32})[1], "BAD_ARGS")


class SaveTests(HomeCase):
    def test_a_save_is_accepted_and_finished_when_the_game_says_so(self):
        self.assertTrue(self.run_cmd("save", {}))
        self.assertEqual(self.control.phases(), [("ACCEPTED", None)])
        self.assertEqual(self.actuator.calls, [("save", 2, "Test Slot")])
        self.assertEqual(len(self.actuator.callbacks), 1)
        self.actuator.callbacks[0]()
        self.assertEqual(self.control.phases(), [("ACCEPTED", None), ("FINISHED", "SAVED")])

    def test_a_save_callback_with_no_save_waiting_does_nothing(self):
        self.assertTrue(self.run_cmd("save", {}))
        self.actuator.callbacks[0]()
        self.actuator.callbacks[0]()
        self.assertEqual(self.control.phases().count(("FINISHED", "SAVED")), 1)

    def test_no_player_slot_is_refused(self):
        self.actuator.slot = (1, None, False, None)
        self.assertFalse(self.run_cmd("save", {}))
        self.assertEqual(self.control.phases(), [("REJECTED", "NO_PLAYER_SLOT")])
        self.assertEqual(self.actuator.calls, [])

    def test_the_lock_is_refused_with_its_tooltip_key(self):
        self.actuator.slot = (2, "Test Slot", True, "424242")
        self.assertFalse(self.run_cmd("save", {}))
        self.assertEqual(self.control.events[-1]["code"], "SAVE_LOCKED")
        self.assertEqual(self.control.events[-1]["reason_key"], "424242")

    def test_a_second_save_inside_the_floor_is_too_soon(self):
        self.assertTrue(self.run_cmd("save", {}))
        self.actuator.callbacks[0]()
        self.clock.now += 300.0
        self.assertFalse(self.run_cmd("save", {}, act_id=ACT_TWO))
        last = self.control.events[-1]
        self.assertEqual(last["code"], "SAVE_TOO_SOON")
        self.assertIn("s", last["detail"])

    def test_after_the_floor_she_saves_again(self):
        self.assertTrue(self.run_cmd("save", {}))
        self.actuator.callbacks[0]()
        self.clock.now += self.home.SAVE_FLOOR_S
        self.assertTrue(self.run_cmd("save", {}, act_id=ACT_TWO))

    def test_a_save_the_game_refuses_is_failed_and_does_not_hold_the_floor(self):
        self.actuator.save_error = RuntimeError("no")
        self.assertFalse(self.run_cmd("save", {}))
        self.assertEqual(self.control.phases(), [("ACCEPTED", None), ("REJECTED", "SAVE_FAILED")])
        self.actuator.save_error = None
        self.assertTrue(self.run_cmd("save", {}, act_id=ACT_TWO))

    def test_a_duplicate_act_id_runs_once(self):
        self.assertTrue(self.run_cmd("save", {}))
        self.assertFalse(self.run_cmd("save", {}))
        self.assertIn("ACT_REJECT DUPLICATE", self.control.lines)

    def test_a_save_that_is_never_confirmed_is_unknown_later(self):
        self.assertTrue(self.run_cmd("save", {}))
        self.clock.now += self.home.SAVE_CONFIRM_S
        self.assertFalse(self.run_cmd("save", {}, act_id=ACT_TWO))
        self.assertIn(("UNKNOWN", "SAVE_UNCONFIRMED"), self.control.phases())

    def test_she_is_not_sampling_nothing_is_saved(self):
        self.control.state = "ARMED"
        self.assertFalse(self.run_cmd("save", {}))
        self.assertEqual(self.control.phases(), [("REJECTED", "NOT_SAMPLING")])
        self.assertEqual(self.actuator.calls, [])


class BuyTests(HomeCase):
    def setUp(self):
        super(BuyTests, self).setUp()
        self.args = {"definition_id": "55", "place": _place("wall", "5")}

    def test_a_purchase_on_the_home_lot_is_placed_and_charged_once(self):
        self.assertTrue(self.run_cmd("buy", self.args))
        self.assertEqual([c[0] for c in self.actuator.calls], ["create", "find_spot", "try_remove", "place"])
        self.assertEqual(self.actuator.calls[2], ("try_remove", 150))
        self.assertNotIn("remove_created", [c[0] for c in self.actuator.calls])
        self.assertEqual(self.control.phases()[-1], ("FINISHED", "PLACED"))
        result = self.control.events[-1]["result"]
        self.assertEqual((result["price"], result["funds"], result["room_id"]), (150, 350, "5"))
        self.assertEqual(self.control.events[-1]["object_id"], "9000")

    def test_a_purchase_off_her_home_lot_is_refused_before_anything(self):
        self.actuator.home = False
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases(), [("REJECTED", "NOT_HOME")])
        self.assertEqual(self.actuator.calls, [])

    def test_build_mode_refuses(self):
        self.actuator.build = True
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases(), [("REJECTED", "BUILD_MODE")])

    def test_a_price_of_zero_is_not_purchasable(self):
        self.actuator.price = 0
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases(), [("REJECTED", "NOT_PURCHASABLE")])

    def test_a_hidden_definition_is_not_purchasable(self):
        self.actuator.tags = ["Cheat"]
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases(), [("REJECTED", "NOT_PURCHASABLE")])

    def test_a_price_above_max_is_refused_with_the_price(self):
        self.assertFalse(self.run_cmd("buy", dict(self.args, max_price=100)))
        self.assertEqual(self.control.events[-1]["code"], "PRICE_ABOVE")
        self.assertEqual(self.control.events[-1]["detail"], "price 150")

    def test_no_money_refuses_before_anything_is_made(self):
        self.actuator.funds = FakeFunds(10)
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases(), [("REJECTED", "NO_FUNDS")])
        self.assertEqual(self.actuator.calls, [])

    def test_no_spot_removes_the_new_object_and_takes_no_money(self):
        self.actuator.spot = None
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases(), [("ACCEPTED", None), ("REJECTED", "NO_SPOT")])
        calls = [c[0] for c in self.actuator.calls]
        self.assertEqual(calls, ["create", "find_spot", "remove_created"])
        self.assertEqual(self.actuator.funds.money, 500)

    def test_a_failed_placement_refunds_and_removes_what_it_made(self):
        self.actuator.place_error = RuntimeError("refused")
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "PLACE_FAILED"))
        calls = [c[0] for c in self.actuator.calls]
        self.assertEqual(calls, ["create", "find_spot", "try_remove", "place", "add", "remove_created"])
        self.assertEqual(self.actuator.funds.money, 500)

    def test_a_game_that_cannot_create_refuses_with_place_failed(self):
        self.actuator.create_fail = True
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases(), [("ACCEPTED", None), ("REJECTED", "PLACE_FAILED")])


class PlaceTests(HomeCase):
    def setUp(self):
        super(PlaceTests, self).setUp()
        self.item = FakeObj("41", inventory=True)
        self.actuator.objects["41"] = self.item

    def args(self, **extra):
        args = {"object_id": "41", "place": _place("in", "5")}
        args.update(extra)
        return args

    def test_an_inventory_item_is_placed_at_its_spot(self):
        self.assertTrue(self.run_cmd("place", self.args()))
        self.assertEqual(self.control.phases(), [("ACCEPTED", None), ("FINISHED", "PLACED")])
        self.assertIsNone(self.control.events[-1]["result"]["price"])

    def test_an_object_that_is_not_in_her_inventory_is_refused(self):
        self.item.inventory = False
        self.assertFalse(self.run_cmd("place", self.args()))
        self.assertEqual(self.control.phases(), [("REJECTED", "NOT_IN_INVENTORY")])

    def test_no_spot_is_refused_and_nothing_is_removed(self):
        self.actuator.spot = None
        self.assertFalse(self.run_cmd("place", self.args()))
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "NO_SPOT"))
        self.assertNotIn("remove_created", [c[0] for c in self.actuator.calls])

    def test_instead_is_refused_while_its_target_still_stands(self):
        target = FakeObj("77", spot={"translation": (1.0, 0.0, 2.0)})
        self.actuator.objects["77"] = target
        self.control.state = "SAMPLING"
        self.home.state_of(self.control).vacated["77"] = {"translation": (1.0, 0.0, 2.0)}
        self.assertFalse(self.run_cmd("place", self.args(place={"rel": "instead", "target_id": "77"})))
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "NOT_FREE"))

    def test_instead_takes_the_spot_a_moved_or_sold_target_left(self):
        self.home.state_of(self.control).vacated["77"] = {"translation": (1.0, 0.0, 2.0), "orientation": None,
                                                          "routing_surface": None, "slot": None}
        self.assertTrue(self.run_cmd("place", self.args(place={"rel": "instead", "target_id": "77"})))
        self.assertEqual(self.control.phases()[-1], ("FINISHED", "PLACED"))

    def test_instead_with_no_record_of_a_spot_is_no_spot(self):
        self.assertFalse(self.run_cmd("place", self.args(place={"rel": "instead", "target_id": "78"})))
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "NO_SPOT"))


class MoveTests(HomeCase):
    def setUp(self):
        super(MoveTests, self).setUp()
        self.bed = FakeObj("41", class_name="SingleBed", spot={"translation": (0.0, 0.0, 0.0)},
                           reach=(True, False))
        self.actuator.objects["41"] = self.bed
        self.actuator.lot = [self.bed]

    def args(self, **extra):
        args = {"object_id": "41", "place": _place("wall", "5")}
        args.update(extra)
        return args

    def test_a_move_is_finished_and_names_the_bed_she_can_no_longer_reach(self):
        self.assertTrue(self.run_cmd("move", self.args()))
        self.assertEqual(self.control.phases(), [("ACCEPTED", None), ("FINISHED", "MOVED")])
        self.assertEqual(self.control.events[-1]["result"]["routes_lost"], ["bed"])

    def test_a_move_that_cuts_a_route_is_still_done(self):
        self.assertTrue(self.run_cmd("move", self.args()))
        self.assertIn(("place", "41"), self.actuator.calls)

    def test_only_her_objects_move(self):
        self.bed.owner = "10"
        self.assertFalse(self.run_cmd("move", self.args()))
        self.assertEqual(self.control.phases(), [("REJECTED", "NOT_HERS")])

    def test_an_object_in_use_is_not_moved(self):
        self.bed.in_use = True
        self.assertFalse(self.run_cmd("move", self.args()))
        self.assertEqual(self.control.phases(), [("REJECTED", "IN_USE")])

    def test_a_sim_or_a_door_is_not_movable(self):
        self.bed.is_sim = True
        self.assertFalse(self.run_cmd("move", self.args()))
        self.bed.is_sim = False
        self.bed.portal = True
        self.assertFalse(self.run_cmd("move", self.args(), act_id=ACT_TWO))
        self.assertEqual([code for _, code in self.control.phases()][-2:], ["NOT_MOVABLE", "NOT_MOVABLE"])

    def test_a_move_records_where_the_object_was_for_instead(self):
        self.run_cmd("move", self.args())
        self.assertEqual(self.home.state_of(self.control).vacated["41"]["translation"], (0.0, 0.0, 0.0))

    def test_a_failed_move_is_refused_by_the_game(self):
        self.actuator.place_error = RuntimeError("no")
        self.assertFalse(self.run_cmd("move", self.args()))
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "MOVE_FAILED"))


class SellTests(HomeCase):
    def setUp(self):
        super(SellTests, self).setUp()
        self.chair = FakeObj("41", value=40)
        self.actuator.objects["41"] = self.chair

    def test_a_sale_pays_the_value_then_removes_the_object(self):
        self.assertTrue(self.run_cmd("sell", {"object_id": "41"}))
        calls = [c[0] for c in self.actuator.calls]
        self.assertEqual(calls, ["add", "sell"])
        self.assertTrue(self.chair.removed)
        result = self.control.events[-1]["result"]
        self.assertEqual((result["value"], result["funds"]), (40, 540))
        self.assertEqual(self.control.phases()[-1], ("FINISHED", "SOLD"))

    def test_a_sale_never_uses_the_create_removal(self):
        self.run_cmd("sell", {"object_id": "41"})
        self.assertNotIn("remove_created", [c[0] for c in self.actuator.calls])

    def test_a_sim_is_not_sold(self):
        self.chair.is_sim = True
        self.assertFalse(self.run_cmd("sell", {"object_id": "41"}))
        self.assertEqual(self.control.phases(), [("REJECTED", "NOT_SELLABLE")])
        self.assertFalse(self.chair.removed)

    def test_a_door_or_a_window_is_not_sold(self):
        self.chair.portal = True
        self.assertFalse(self.run_cmd("sell", {"object_id": "41"}))
        self.chair.portal = False
        self.chair.class_name = "Window"
        self.assertFalse(self.run_cmd("sell", {"object_id": "41"}, act_id=ACT_TWO))
        self.assertEqual([code for _, code in self.control.phases()], ["NOT_SELLABLE", "NOT_SELLABLE"])

    def test_an_object_in_use_is_not_sold(self):
        self.chair.in_use = True
        self.assertFalse(self.run_cmd("sell", {"object_id": "41"}))
        self.assertEqual(self.control.phases(), [("REJECTED", "IN_USE")])

    def test_an_unreadable_value_is_not_sold(self):
        self.chair.value = None
        self.assertFalse(self.run_cmd("sell", {"object_id": "41"}))
        self.assertEqual(self.control.events[-1]["detail"], "value unreadable")

    def test_a_removal_the_game_refuses_gives_the_money_back(self):
        self.actuator.sell_error = RuntimeError("no")
        self.assertFalse(self.run_cmd("sell", {"object_id": "41"}))
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "SELL_FAILED"))
        self.assertEqual(self.actuator.funds.money, 500)


class DispatchTests(HomeCase):
    def test_an_exception_inside_a_command_is_unknown_for_its_act(self):
        def broken(*args):
            raise ValueError("boom")

        self.actuator.at_home = broken
        self.assertFalse(self.run_cmd("buy", {"definition_id": "55", "place": _place("wall", "5")}))
        self.assertEqual(self.control.phases()[-1], ("UNKNOWN", "E2_EXCEPTION:ValueError"))

    def test_the_home_module_makes_no_forbidden_or_reflective_calls(self):
        path = os.path.join(ROOT, "src", "ashley_e1", "home.py")
        text = open(path, encoding="utf-8").read()
        self.assertEqual(guards.scan_text(text, "home.py"), [])
        self.assertNotIn(".destroy(", text)
        self.assertNotIn("save_using", text)
        self.assertNotIn("getattr", text)


class ActuatorReadTests(unittest.TestCase):
    """The game's members as the actuator reads them: in_use is a property (27 reads in the game's code, none called),
    and a runtime slot's name is a property too. A read that fails is None, never a guess."""

    def setUp(self):
        self.actuator = modules()[0].e2_actuator

    def test_in_use_is_read_as_the_property_it_is(self):
        self.assertIs(self.actuator.in_use(types.SimpleNamespace(in_use=True)), True)
        self.assertIs(self.actuator.in_use(types.SimpleNamespace(in_use=False)), False)

    def test_an_unreadable_in_use_is_none(self):
        self.assertIsNone(self.actuator.in_use(types.SimpleNamespace()))

    def test_a_slot_takes_the_object_under_its_name_property(self):
        calls = []

        class Slot(object):
            empty = True
            slot_name_or_hash = "joint_top"

            def add_child(self, child, joint):
                calls.append((child, joint))

        obj = object()
        self.actuator.place(obj, {"slot": Slot(), "translation": None, "orientation": None,
                                  "routing_surface": None})
        self.assertEqual(calls, [(obj, "joint_top")])


class ProbeRouteTests(unittest.TestCase):
    """The real probe: the inbox routes a home command to home.py, and its rows validate. The act harness arms her
    body; the game's save and catalogue reads are the fakes of the harness, so only the routing is real here."""

    def setUp(self):
        self.case = acts.ActCommandTests()
        self.case.setUp()
        self.probe = self.case.probe
        self.base = self.case.base
        # The harness's persistence stub has no save lock or slot reads: her slot 2 and an unlocked game, kept on one instance.
        persistence = self.base.services.get_persistence_service()
        persistence.is_save_locked = lambda: False
        persistence.get_save_slot_proto_buff = lambda: types.SimpleNamespace(slot_id=2)
        self.base.services.get_persistence_service = lambda: persistence
        self.case.ready()

    def tearDown(self):
        self.case.tearDown()

    def inbox(self, command, args):
        connection = self.probe._InboxReply("helper")
        ok = self.probe._inbox_dispatch({"command": command, "args": args}, connection)
        return ok, connection

    def test_calibrate_refuses_her_home_edits(self):
        self.assertIn("save", self.probe._OBSERVE_REFUSED)
        self.assertIn("catalog_dump", self.probe._OBSERVE_REFUSED)

    def test_a_save_reaches_home_and_is_recorded(self):
        saved = []
        original = self.probe.e2_actuator.save_now
        self.probe.e2_actuator.save_now = lambda slot, name: saved.append(slot)
        self.addCleanup(setattr, self.probe.e2_actuator, "save_now", original)
        ok, connection = self.inbox("save", {"act_id": ACT})
        self.assertTrue(ok)
        self.assertEqual(connection.lines[-1], "ACT_ACCEPTED " + ACT)
        self.assertEqual(saved, [2])
        for row in self.base.rows("act_event"):
            self.probe.schema.validate_record(row)
        self.assertEqual([e["phase"] for e in self.base.e2("act_event") if e["act_id"] == ACT], ["ACCEPTED"])

    def test_the_catalogue_dump_says_the_definitions_cannot_be_read_in_a_test(self):
        ok, connection = self.inbox("catalog_dump", {})
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "CATALOG_UNREADABLE")

    def test_a_malformed_home_command_is_refused_by_the_box(self):
        raw = json.dumps({"v": 1, "id": "a" * 32, "issued_at_ms": 1, "expires_at_ms": 2,
                          "issuer": "helper", "command": "sell", "args": {"object_id": "x"}})
        self.assertEqual(self.probe.cmdbox.parse(raw.encode("utf-8"), 1, set())[1], "BAD_ARGS")


if __name__ == "__main__":
    unittest.main()
