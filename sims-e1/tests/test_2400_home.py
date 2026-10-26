"""2.40.0 (W13 P2, probe: home): the things list and the catalogue (their shapes, bounds and parts), her save (the
floor, the lock, the slot), and her home edits (buy, place, move, sell): each refusal and its code, the order of the
charge and the create, the refund and removal after a failed placement, the routes reported, and the result facts.

Fakes only: the actuator, observers, services and the clock are replaced; no game, no live services. One class runs
the real probe dispatch through the act harness (test_2160_act), so the commands reach home.py from the inbox."""
import importlib.util
import json
import math
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
        self.refuse_phases = ()
        self.refuse_results = False
        self.raise_phases = ()
        self.refuse_catalog = False
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
        if self.refuse_results and payload.get("result") is not None:
            return False
        if phase in self.refuse_phases:
            return False
        if phase in self.raise_phases:
            raise RuntimeError("row")
        row = dict(payload)
        row["act_id"], row["phase"] = act_id, phase
        self.events.append(row)
        return True

    def _say(self, connection, text):
        self.lines.append(text)

    def _event(self, kind, payload):
        self.emitted.append((kind, payload))
        return not (kind == "catalog" and self.refuse_catalog)

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
        self.take_refused = False
        self.put_back_refused = False
        self.buy_flags = 128
        self.placement_flags = 0
        self.wall_items = []
        self.rooms_forgotten = 0
        self.removal_queued = False
        self.queued = []
        self.near_raises = False
        self.busy = False
        self.remove_refused = False
        self.charge_refused = False
        self.money_hidden = False
        self.money_hidden_after_charge = False
        self.refund_refused = False
        self.spot_error = None
        self.save_fires = False
        self.earnings = []
        self.zone = 7
        self.order = []

    # reads
    def at_home(self, household_id):
        return self.home

    def build_mode(self):
        return self.build

    def current_zone(self):
        return self.zone

    def room_of(self, obj):
        return "5"

    def is_wall_placed(self, obj):
        return obj.wall

    def near_objects(self, obj, radius):
        self.order.append("near")
        if self.near_raises:
            raise RuntimeError("near")
        return list(obj.near)

    def save_busy(self):
        return self.busy

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
        """The zone's object manager: a thing she carries is not in it (SEAM2-2)."""
        found = self.objects.get(str(object_id))
        return None if found is not None and found.inventory else found

    def find_thing(self, object_id):
        return self.objects.get(str(object_id))

    def find_spot(self, obj, sim, place, wall_item=False, lot=None):
        self.calls.append(("find_spot", place["rel"]))
        self.wall_items.append(wall_item)
        if self.spot_error is not None:
            raise self.spot_error
        return self.spot

    def object_placement_flags(self, obj):
        return self.placement_flags

    def against_wall(self, obj, lot=None):
        return obj.wall

    def forget_rooms(self):
        self.rooms_forgotten += 1
        self.order.append("forget")

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

    def definition_buy_flags(self, defn):
        return self.buy_flags

    def definition_placement_flags(self, defn):
        return self.placement_flags

    def household_funds(self, household_id):
        return self.funds

    def can_afford(self, funds, amount):
        return funds.can_afford(amount)

    def value_of(self, obj):
        return obj.value

    def save_slot(self):
        return self.slot

    def catalog_rows(self, wanted=None):
        return self.catalog

    def things_rows(self, listed=None, limit=None):
        return None if self.things is None else (self.things, len(self.things))

    # effects
    def funds_try_remove(self, funds, amount, sim):
        self.calls.append(("try_remove", amount))
        if self.charge_refused:
            return False
        taken = funds.try_remove(amount, "x", sim, True)
        if self.money_hidden_after_charge:
            self.money_hidden = True
        return taken

    def funds_money(self, funds):
        return None if self.money_hidden else funds.money

    def funds_add(self, funds, amount, sim, count_as_earnings=True):
        self.calls.append(("add", amount))
        self.earnings.append(count_as_earnings)
        if self.refund_refused:
            return False
        funds.add(amount, "x")
        return True

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
        if self.remove_refused:
            return False
        obj.removed = True
        if self.removal_queued:
            self.queued.append(obj.id)
        else:
            self.objects.pop(obj.id, None)
        return True

    def place(self, obj, spot):
        self.calls.append(("place", obj.id))
        if self.place_error is not None:
            raise self.place_error
        self.placed = True

    def take_from_inventory(self, sim, obj):
        self.calls.append(("take", obj.id))
        if self.take_refused:
            return False
        obj.inventory = False
        return True

    def return_to_inventory(self, sim, obj):
        self.calls.append(("put_back", obj.id))
        if self.put_back_refused:
            return False
        obj.inventory = True
        return True

    def sell_object(self, obj):
        self.calls.append(("sell", obj.id))
        if self.sell_error is not None:
            raise self.sell_error
        obj.removed = True
        if self.removal_queued:
            self.queued.append(obj.id)
        else:
            self.objects.pop(obj.id, None)

    def process_queue(self):
        """The game finishes the removals it queued (its reset service), so the object is gone from the zone."""
        for object_id in self.queued:
            self.objects.pop(object_id, None)
        self.queued = []

    def object_gone(self, object_id):
        return str(object_id) not in self.objects

    def save_now(self, slot_id, slot_name):
        self.calls.append(("save", slot_id, slot_name))
        if self.save_error is not None:
            raise self.save_error
        if self.save_fires:
            for callback in list(self.callbacks):
                callback()

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


def _read_things(actuator, limit=600):
    """The raw things rows the actuator reads (every thing kept, up to the limit), without their total."""
    read = actuator.things_rows(lambda name: True, limit)
    return None if read is None else read[0]


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


class ThingStateTests(unittest.TestCase):
    """HOME-22/30: a thing's states are read from the object (observers' reader, at most four), and a state's name and
    value are cut to 64 characters."""

    def setUp(self):
        self.home, self.actuator = modules()[1], modules()[0].e2_actuator

    def test_a_long_state_name_or_value_is_cut_to_sixty_four(self):
        state = self.home.shape_state({"state": "s" * 80, "value": "v" * 80})
        self.assertEqual((len(state["state"]), len(state["value"])), (64, 64))

    def test_the_states_of_a_thing_are_at_most_four(self):
        found = dict(("state%d" % index, "value%d" % index) for index in range(9))
        with mock.patch.object(self.actuator.observers, "_object_states", lambda obj: found):
            states = self.actuator._thing_states(object())
        self.assertEqual(len(states), 4)
        self.assertEqual(set(states[0]), {"state", "value"})

    def test_an_unreadable_state_reader_gives_no_states(self):
        with mock.patch.object(self.actuator.observers, "_object_states", lambda obj: None):
            self.assertEqual(self.actuator._thing_states(object()), [])


class ThingsListTests(HomeCase):
    def raw(self, **overrides):
        row = {"object_id": 41, "definition_id": 55, "name_key": 123, "class_name": "Chair", "where": "room",
               "room_id": 5, "value": 40, "made_by_her": None, "states": [{"state": "dirty", "value": 3}],
               "in_use": False, "count": None, "placement_flags": 0}
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

    def test_at_most_four_states(self):
        many = [{"state": "s%d" % i, "value": i} for i in range(9)]
        item = self.home.shape_thing(self.raw(states=many))
        self.assertEqual(len(item["states"]), 4)

    def test_a_thing_placement_is_the_one_word_of_its_definition_flags(self):
        """HOME-23 / S3: wall from the wall flags, surface from REQUIRES_SLOT, else floor; unreadable is None."""
        words = [self.home.shape_thing(self.raw(placement_flags=flags))["placement"]
                 for flags in (1, 8388608, 268435456, 1024, 1024 | 1, 0, None)]
        self.assertEqual(words, ["wall", "wall", "wall", "surface", "wall", "floor", None])

    def test_build_items_are_not_things(self):
        rows = [self.raw(class_name="Wall"), self.raw(class_name="FrontDoor", object_id=42),
                self.raw(class_name="WallLight", object_id=43)]
        kept = [item["object_id"] for item in self.home.things_items(rows)]
        self.assertEqual(kept, ["43"])

    def test_at_most_six_hundred_things(self):
        rows = [self.raw(object_id=1000 + index) for index in range(700)]
        self.assertEqual(len(self.home.things_items(rows)), self.home.THINGS_MAX)

    def test_the_things_list_carries_the_total_it_was_given(self):
        """SEAM2-4 / T1: a list given a total carries it; without one, its total is the items it holds."""
        self.assertEqual(self.home.things_items([self.raw()], total=9).total, 9)
        self.assertEqual(self.home.things_items([self.raw()]).total, 1)

    def test_a_thing_with_a_bad_room_fails_the_record_check(self):
        item = self.home.shape_thing(self.raw())
        item["room_id"] = "room five"
        with self.assertRaises(self.schema.SchemaError):
            self.schema._validate_thing(item)


class ThingsWiringTests(HomeCase):
    """HOME-1 / CORE-1: the things list has a reader in the probe's lists tick, as people and places do, so it is
    written (and rewritten when it changes) through reach.ListWriter. home.py keeps no writer of its own."""

    def raw(self, **overrides):
        row = {"object_id": 41, "definition_id": 55, "name_key": 123, "class_name": "Chair", "where": "room",
               "room_id": 5, "value": 40, "made_by_her": None, "states": [], "in_use": False, "count": None,
               "placement": "floor"}
        row.update(overrides)
        return row

    def tick(self, rows, force=True):
        written = []
        writer = self.probe.reach.ListWriter(lambda kind, row: written.append((kind, row)) or True)
        readers = self.probe._lists_readers()
        with mock.patch.object(self.probe.e2_actuator, "things_rows",
                               lambda *args: None if rows is None else (rows, len(rows))):
            kinds = writer.tick({"things": readers["things"]}, force=force)
        return kinds, written

    def test_the_lists_readers_include_things(self):
        self.assertIn("things", self.probe._lists_readers())

    def test_a_things_tick_writes_the_shaped_rows(self):
        kinds, written = self.tick([self.raw()])
        self.assertEqual(kinds, ["things"])
        kind, row = written[0]
        self.assertEqual((kind, row["list_rev"], row["items"][0]["object_id"]), ("things", 1, "41"))

    def test_an_unreadable_home_writes_no_things_list(self):
        self.assertEqual(self.tick(None)[0], [])

    def test_an_unchanged_list_is_not_written_again(self):
        rows = [self.raw()]
        writer = self.probe.reach.ListWriter(lambda kind, row: True)
        readers = self.probe._lists_readers()
        with mock.patch.object(self.probe.e2_actuator, "things_rows",
                               lambda *args: None if rows is None else (rows, len(rows))):
            self.assertEqual(writer.tick({"things": readers["things"]}, force=True), ["things"])
            self.assertEqual(writer.tick({"things": readers["things"]}, force=True), [])

    def test_the_things_reader_passes_the_total_on(self):
        """SEAM2-4 / T1: the probe's things reader gives the writer the total the game's read counted."""
        with mock.patch.object(self.probe.e2_actuator, "things_rows", lambda *args: ([self.raw()], 7)):
            items = self.probe._lists_readers()["things"]()
        self.assertEqual(items.total, 7)
        self.assertEqual(items[0]["object_id"], "41")

    def test_the_written_rows_carry_the_total_and_a_total_that_changes_alone_is_written_again(self):
        """T1: the writer puts the reader's total on every part; the same items with a new total are a new list."""
        written = []
        writer = self.probe.reach.ListWriter(lambda kind, row: written.append(row) or True)
        reader = self.probe._lists_readers()["things"]
        rows = [self.raw()]
        with mock.patch.object(self.probe.e2_actuator, "things_rows", lambda *args: (rows, 7)):
            self.assertEqual(writer.tick({"things": reader}, force=True), ["things"])
        with mock.patch.object(self.probe.e2_actuator, "things_rows", lambda *args: (rows, 8)):
            self.assertEqual(writer.tick({"things": reader}, force=True), ["things"])
            self.assertEqual(writer.tick({"things": reader}, force=True), [])
        self.assertEqual([row["total"] for row in written], [7, 8])
        self.assertEqual(written[0]["digest"], written[1]["digest"])

    def test_the_lists_record_takes_an_optional_whole_total(self):
        """T1: total is an optional whole number on a things record; a negative one is refused."""
        def record(total):
            row = {"kind": "things", "list_rev": 1, "part": 0, "parts": 1, "digest": "0" * 64, "count": 1,
                   "items": list(self.home.things_items([self.raw()])), "total": total}
            return self.schema.make_record("lists", telemetry_session_id="s" * 32, wall_timestamp_ms=1,
                                           monotonic_ns=2, e2=row)

        self.schema.validate_record(record(9))
        with self.assertRaises(self.schema.SchemaError):
            self.schema.validate_record(record(-1))

    def test_the_written_things_rows_validate(self):
        _kinds, written = self.tick([self.raw(), self.raw(object_id=42, where="inventory", room_id=None, count=2)])
        self.assertTrue(written)
        for _kind, row in written:
            record = self.schema.make_record("lists", telemetry_session_id="s" * 32, wall_timestamp_ms=1,
                                             monotonic_ns=2, e2=dict(row))
            self.schema.validate_record(record)


class CatalogSchemaTests(unittest.TestCase):
    """S3: a catalogue item's placement is exactly one word (wall, surface or floor), or None when unread."""

    def item(self, placement):
        return {"definition_id": "77", "price": 120, "buy_category": ["DECOR"], "placement": placement,
                "tags": [], "purchasable": True}

    def test_one_placement_word_is_accepted(self):
        schema = modules()[3]
        schema._validate_catalog_record({"catalog_rev": "1.128", "part": 0, "parts": 1,
                                         "items": [self.item(["wall"]), self.item(None)]})

    def test_two_placement_words_are_refused(self):
        schema = modules()[3]
        with self.assertRaises(schema.SchemaError):
            schema._validate_catalog_record({"catalog_rev": "1.128", "part": 0, "parts": 1,
                                             "items": [self.item(["wall", "floor"])]})


class CatalogTests(HomeCase):
    def raw(self, **overrides):
        row = {"definition_id": 77, "price": 120, "tags": ["Comfort"], "class_name": "Sofa", "sim": False,
               "buy_flags": 128, "placement_flags": 0}
        row.update(overrides)
        return row

    def test_a_store_item_with_a_price_is_a_catalogue_item(self):
        items = self.home.catalog_items([self.raw()])
        self.assertEqual(items, [{"definition_id": "77", "price": 120, "buy_category": ["DECOR"],
                                  "placement": ["floor"], "tags": ["Comfort"], "purchasable": True}])

    def test_sims_build_items_and_things_outside_the_store_are_left_out(self):
        """HOME-4 / S3: only what the store lists (a buy category) is offered; a Sim and a build item never are."""
        rows = [self.raw(sim=True), self.raw(class_name="Wall", definition_id=78),
                self.raw(class_name="FrontDoor", definition_id=79), self.raw(buy_flags=0, definition_id=80),
                self.raw(buy_flags=1, definition_id=81), self.raw(buy_flags=None, definition_id=82),
                self.raw(price=-1, definition_id=83), self.raw(price=0, definition_id=84)]
        kept = self.home.catalog_items(rows)
        self.assertEqual([item["definition_id"] for item in kept], ["84"])

    def test_a_free_store_item_is_listed_and_purchasable(self):
        """HOME-31 / S3: a price of zero is a store price, so it is purchasable."""
        item = self.home.shape_catalog(self.raw(price=0))
        self.assertTrue(item["purchasable"])

    def test_the_buy_categories_are_the_names_of_the_set_bits(self):
        """S3 (dis build_buy BuyCategory): UNUSED 1, UNUSED_2 16 and DEFAULT 2^31 are ignored."""
        mask = 2 | 4 | 8 | 32 | 64 | 128 | 256 | 512 | 2048 | 4096 | 8192 | 1 | 16 | 2 ** 31
        self.assertEqual(self.home.buy_category_names(mask),
                         ["APPLIANCES", "ELECTRONICS", "ENTERTAINMENT", "LIGHTING", "PLUMBING", "DECOR", "KIDS",
                          "STORAGE", "COMFORT", "SURFACE", "VEHICLE"])
        self.assertEqual(self.home.buy_category_names(1), [])
        self.assertIsNone(self.home.buy_category_names(None))

    def test_the_placement_is_one_word_from_the_placement_flags(self):
        """S3 (dis build_buy PlacementFlags): wall flags, then REQUIRES_SLOT as surface, else floor."""
        words = [self.home.shape_catalog(self.raw(placement_flags=flags))["placement"]
                 for flags in (1, 2, 4, 8388608, 268435456, 1024, 1024 | 2, 0)]
        self.assertEqual(words, [["wall"]] * 5 + [["surface"], ["wall"], ["floor"]])
        self.assertIsNone(self.home.shape_catalog(self.raw(placement_flags=None))["placement"])

    def test_a_hidden_tag_is_not_purchasable(self):
        self.assertIsNone(self.home.shape_catalog(self.raw(tags=["Debug Only"])))

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

    def test_a_catalogue_part_the_game_refuses_is_said_partial(self):
        """HOME-19: CATALOG_PARTIAL written/parts when any part was not written, never a count of all the items."""
        self.actuator.catalog = [self.raw(definition_id=1000 + index) for index in range(300)]
        self.control.refuse_catalog = True
        self.assertFalse(self.run_cmd("catalog_dump", {}))
        self.assertEqual(self.control.lines[-1], "CATALOG_PARTIAL 0/2")

    def test_catalog_dump_says_when_the_definitions_cannot_be_read(self):
        self.actuator.catalog = None
        self.assertFalse(self.run_cmd("catalog_dump", {}))
        self.assertEqual(self.control.lines[-1], "CATALOG_UNREADABLE")
        self.assertEqual(self.control.emitted, [])


class BuildNameTests(unittest.TestCase):
    """HOME-27: the build classes by their last CamelCase word, checked against the game's class names (index: Door,
    HalfWall, Terrain are the build classes; no decor class is named *Wall, *Window or *Floor)."""

    def setUp(self):
        self.home = modules()[1]

    def test_the_game_build_classes_are_build_items(self):
        for name in ("Door", "HalfWall", "Terrain"):
            self.assertTrue(self.home.is_build_class(name), name)

    def test_furniture_and_decor_are_not_build_items(self):
        for name in ("GameObject", "Sofa", "WallLight", "Mirror", "Bed", "IndoorPlant"):
            self.assertFalse(self.home.is_build_class(name), name)


class RouteKindTests(unittest.TestCase):
    """HOME2-7 / W13 R2: a route kind is the class name's last word (a door is a portal): decor whose name only contains
    a route word (a toilet-paper roll, bed sheets) is no route, and a bed, toilet or fridge is one."""

    def setUp(self):
        self.home = modules()[1]

    def test_a_bed_toilet_or_fridge_by_its_last_word_is_its_route(self):
        cases = {"SingleBed": "bed", "BunkBed": "bed", "Toilet": "toilet", "Fridge": "fridge",
                 "MiniRefrigerator": "fridge"}
        for name, kind in cases.items():
            self.assertEqual(self.home.route_kind(name, False), kind, name)

    def test_decor_with_a_route_word_inside_its_name_is_no_route(self):
        for name in ("ToiletPaper", "BedSheets", "BedsideLamp", "FridgeMagnet", "Chair"):
            self.assertIsNone(self.home.route_kind(name, False), name)

    def test_a_portal_is_a_door_whatever_its_name(self):
        self.assertEqual(self.home.route_kind("Chair", True), "door")


class CatalogReadTests(unittest.TestCase):
    """HOME2-6 (probe half) / W13 R2: a Sim or a build item is left out before its price, tags and flags are read; the
    other definitions are read as before."""

    class Defn(object):
        def __init__(self, def_id, cls_name, is_sim=False):
            self.id = def_id
            self.cls = type(cls_name, (object,), {})
            self.is_sim = is_sim

    def setUp(self):
        modules_ = modules()
        self.actuator, self.home = modules_[0].e2_actuator, modules_[1]
        self.defs = [self.Defn(1, "Chair"), self.Defn(2, "Wall"), self.Defn(3, "Teen", is_sim=True),
                     self.Defn(4, "Lamp")]
        self.reads = []
        self.manager = types.SimpleNamespace(loaded_definitions=self.defs)
        services = types.SimpleNamespace(definition_manager=lambda: self.manager)

        def recorder(name, value):
            def read(defn):
                self.reads.append((name, defn.id))
                return value
            return read

        patches = [mock.patch.object(self.actuator, "services", services),
                   mock.patch.object(self.actuator, "definition_price", recorder("price", 10)),
                   mock.patch.object(self.actuator, "definition_tags", recorder("tags", [])),
                   mock.patch.object(self.actuator, "definition_buy_flags", recorder("buy", 128)),
                   mock.patch.object(self.actuator, "definition_placement_flags", recorder("placement", 0))]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_a_sim_and_a_build_item_are_skipped_before_any_flag_is_read(self):
        rows = self.actuator.catalog_rows(self.home.catalog_wanted)
        self.assertEqual([row["definition_id"] for row in rows], [1, 4])
        self.assertEqual(sorted({defn_id for _name, defn_id in self.reads}), [1, 4])

    def test_without_a_filter_every_definition_is_read(self):
        rows = self.actuator.catalog_rows()
        self.assertEqual([row["definition_id"] for row in rows], [1, 2, 3, 4])

    def test_a_catalogue_the_game_cannot_list_is_none(self):
        self.manager.loaded_definitions = None
        self.assertIsNone(self.actuator.catalog_rows(self.home.catalog_wanted))


class WallKindsTests(unittest.TestCase):
    """S2: wall_kinds is parallel to wall_has, each a door or a window; the schema refuses any other word."""

    def setUp(self):
        self.home = modules()[1]
        self.schema = modules()[3]

    def test_a_door_and_a_window_on_the_wall_are_named_in_order(self):
        near = [{"object_id": "1", "distance": 0.4, "portal": True, "window": False},
                {"object_id": "2", "distance": 0.5, "portal": False, "window": True},
                {"object_id": "3", "distance": 0.9, "portal": False, "window": False}]
        facts = self.home.placement_facts("5", True, near)
        self.assertEqual((facts["wall_has"], facts["wall_kinds"]), (["1", "2"], ["door", "window"]))
        self.assertEqual(facts["beside"], ["3"])

    def test_no_wall_means_no_wall_kinds(self):
        facts = self.home.placement_facts("5", False, [{"object_id": "1", "distance": 0.4, "portal": True,
                                                         "window": False}])
        self.assertEqual((facts["wall_has"], facts["wall_kinds"]), ([], []))

    def test_the_schema_accepts_doors_and_windows_only_and_parallel_to_wall_has(self):
        self.schema._validate_home_facts({"wall_has": ["1", "2"], "wall_kinds": ["door", "window"]})
        for bad in ({"wall_has": ["1"], "wall_kinds": ["cabinet"]}, {"wall_has": ["1"], "wall_kinds": []}):
            with self.assertRaises(self.schema.SchemaError):
                self.schema._validate_home_facts(bad)


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
        result = dict((key, facts[key]) for key in self.schema.RESULT_KEYS if key != "value")
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
    def test_a_save_while_the_game_is_saving_is_busy(self):
        """HOME-16: a save that starts while the game's save timeline is open would replace it: SAVE_BUSY, no save."""
        self.actuator.busy = True
        self.assertFalse(self.run_cmd("save", {}))
        self.assertEqual(self.control.phases(), [("REJECTED", "SAVE_BUSY")])
        self.assertEqual(self.actuator.calls, [])

    def test_a_save_while_hers_is_still_waiting_for_its_callback_is_busy(self):
        self.assertTrue(self.run_cmd("save", {}))
        self.assertFalse(self.run_cmd("save", {}, act_id=ACT_TWO))
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "SAVE_BUSY"))

    def test_a_save_timeline_that_cannot_be_read_is_a_failed_save(self):
        self.actuator.busy = None
        self.assertFalse(self.run_cmd("save", {}))
        self.assertEqual(self.control.events[-1]["detail"], "timeline unreadable")
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "SAVE_FAILED"))

    def test_a_finished_row_the_schema_refuses_becomes_an_unknown_row_without_the_result(self):
        """CORE-9: the game's callback never raises into the game; a refused row is UNKNOWN ROW_INVALID."""
        self.control.refuse_phases = ("FINISHED",)
        self.assertTrue(self.run_cmd("save", {}))
        self.actuator.callbacks[0]()
        self.assertEqual(self.control.phases()[-1], ("UNKNOWN", "ROW_INVALID"))
        self.assertIsNone(self.home.state_of(self.control).pending_save)

    def test_a_save_callback_that_fails_is_unknown_and_does_not_raise_into_the_game(self):
        self.control.raise_phases = ("FINISHED",)
        self.assertTrue(self.run_cmd("save", {}))
        self.actuator.callbacks[0]()
        self.assertIsNone(self.home.state_of(self.control).pending_save)

    def test_a_save_is_accepted_and_finished_when_the_game_says_so(self):
        self.assertTrue(self.run_cmd("save", {}))
        self.assertEqual(self.control.phases(), [("ACCEPTED", None)])
        self.assertEqual(self.actuator.calls, [("save", 2, "Test Slot")])
        self.assertEqual(len(self.actuator.callbacks), 1)
        self.actuator.callbacks[0]()
        self.assertEqual(self.control.phases(), [("ACCEPTED", None), ("FINISHED", "SAVED")])

    def test_a_save_the_game_finishes_inside_its_own_call_is_finished(self):
        """HOME2-8 / W13 R2: the game may call back before the save call returns; the save is waiting before the call."""
        self.actuator.save_fires = True
        self.assertTrue(self.run_cmd("save", {}))
        self.assertEqual(self.control.phases(), [("ACCEPTED", None), ("FINISHED", "SAVED")])
        self.assertIsNone(self.home.state_of(self.control).pending_save)
        self.assertEqual(self.control.lines, ["ACT_ACCEPTED " + ACT, "ACT_FINISHED SAVED"])

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


class RoomGridWatchTests(HomeCase):
    """HOME2-4 / W13 R2: the room grids are read again after a zone change and after build mode ends (the User may have
    changed walls there); a steady tick keeps them."""

    def test_the_grids_are_dropped_when_build_mode_ends(self):
        self.home.tick(self.control, 1000.0)
        base = self.actuator.rooms_forgotten
        self.actuator.build = True
        self.home.tick(self.control, 1001.0)
        self.assertEqual(self.actuator.rooms_forgotten, base)
        self.actuator.build = False
        self.home.tick(self.control, 1002.0)
        self.assertEqual(self.actuator.rooms_forgotten, base + 1)
        self.home.tick(self.control, 1003.0)
        self.assertEqual(self.actuator.rooms_forgotten, base + 1)

    def test_the_grids_are_dropped_when_the_zone_changes(self):
        self.home.tick(self.control, 1000.0)
        base = self.actuator.rooms_forgotten
        self.actuator.zone = 8
        self.home.tick(self.control, 1001.0)
        self.assertEqual(self.actuator.rooms_forgotten, base + 1)


class BodyTests(HomeCase):
    """HOME2-3 / W13 R2: the observers raise when her body is ambiguous or unreadable; that is refused BODY_UNAVAILABLE."""

    def raising_body(self, infos, flags):
        raise RuntimeError("LabIdentityAmbiguous")

    def test_an_ambiguous_body_is_body_unavailable_for_a_buy(self):
        self.home.observers.select_lab_body = self.raising_body
        self.assertFalse(self.run_cmd("buy", {"definition_id": "55", "place": _place("wall", "5")}))
        self.assertEqual(self.control.phases(), [("REJECTED", "BODY_UNAVAILABLE")])
        self.assertEqual(self.actuator.calls, [])

    def test_an_unreadable_body_is_body_unavailable_for_a_save(self):
        self.home.observers.select_lab_body = self.raising_body
        self.assertFalse(self.run_cmd("save", {}))
        self.assertEqual(self.control.phases(), [("REJECTED", "BODY_UNAVAILABLE")])
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

    def test_a_free_store_item_is_bought_for_nothing(self):
        """HOME-31 / S3: a store price of zero is purchasable; nothing is charged."""
        self.actuator.price = 0
        self.assertTrue(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases()[-1], ("FINISHED", "PLACED"))
        self.assertEqual(self.actuator.funds.money, 500)

    def test_an_item_the_store_does_not_list_is_not_purchasable(self):
        """HOME-4 / S3: a loaded definition with a price but no buy category is not for sale."""
        for index, flags in enumerate((0, 1, None)):
            self.actuator.buy_flags = flags
            self.assertFalse(self.run_cmd("buy", self.args, act_id=("%d" % index) * 32))
            self.assertEqual(self.control.events[-1]["code"], "NOT_PURCHASABLE")
            self.assertEqual(self.control.events[-1]["phase"], "REJECTED")

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

    def test_a_failed_placement_removes_what_it_made_then_refunds_it(self):
        self.actuator.place_error = RuntimeError("refused")
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "PLACE_FAILED"))
        self.assertEqual(self.control.events[-1]["detail"], "RuntimeError")
        calls = [c[0] for c in self.actuator.calls]
        self.assertEqual(calls, ["create", "find_spot", "try_remove", "place", "remove_created", "add"])
        self.assertEqual(self.actuator.funds.money, 500)

    def test_a_refund_of_a_failed_purchase_is_not_earnings(self):
        """SEAM2-10 / W13 R2: the refund of a purchase that failed is not counted as earnings (as an event's is not)."""
        self.actuator.place_error = RuntimeError("refused")
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.actuator.earnings, [False])

    def test_a_failed_placement_is_refunded_only_once_the_game_has_removed_the_object(self):
        """HOME-11: the refund waits for the removal to finish; a failed path never refunds while the object exists."""
        self.actuator.removal_queued = True
        self.actuator.place_error = RuntimeError("refused")
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases(), [("ACCEPTED", None)])
        self.home.tick(self.control, 1000.0)
        self.assertEqual(self.actuator.funds.money, 350)
        self.actuator.process_queue()
        self.home.tick(self.control, 1001.0)
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "PLACE_FAILED"))
        self.assertEqual(self.actuator.funds.money, 500)

    def test_a_fact_that_cannot_be_read_still_finishes_the_placement(self):
        """HOME-13: the object is placed and she was charged; a failed fact leaves the fact out, and FINISHED still goes."""
        self.actuator.near_raises = True
        self.assertTrue(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases()[-1], ("FINISHED", "PLACED"))
        self.assertEqual(self.control.events[-1]["result"]["beside"], [])

    def test_a_removal_the_game_refuses_after_a_failed_placement_is_unknown_and_not_refunded(self):
        self.actuator.place_error = RuntimeError("refused")
        self.actuator.remove_refused = True
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases()[-1], ("UNKNOWN", "REMOVE_UNCONFIRMED"))
        self.assertEqual(self.control.events[-1]["object_id"], "9000")
        self.assertEqual(self.actuator.funds.money, 350)

    def test_an_object_still_there_after_thirty_seconds_is_unknown_and_not_refunded(self):
        self.actuator.removal_queued = True
        self.actuator.place_error = RuntimeError("refused")
        self.run_cmd("buy", self.args)
        self.home.tick(self.control, 1000.0)
        self.home.tick(self.control, 1031.0)
        self.assertEqual(self.control.phases()[-1], ("UNKNOWN", "REMOVE_UNCONFIRMED"))
        self.assertEqual(self.control.events[-1]["object_id"], "9000")
        self.assertEqual(self.actuator.funds.money, 350)

    def test_a_charge_that_cannot_be_read_removes_the_object_and_refunds_nothing(self):
        """HOME-10 / SEAM2-5 / T4: whether she paid is not known, so the object is removed (no refund) and the act says so."""
        self.actuator.money_hidden_after_charge = True
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases()[-1], ("UNKNOWN", "CHARGE_UNKNOWN"))
        self.assertIn("not refunded", self.control.events[-1]["detail"])
        self.assertTrue(self.actuator.created[0].removed)
        self.assertEqual(self.actuator.funds.money, 350)

    def test_a_charge_removal_the_game_queues_is_settled_once_it_is_gone(self):
        self.actuator.money_hidden_after_charge = True
        self.actuator.removal_queued = True
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases(), [("ACCEPTED", None)])
        self.actuator.process_queue()
        self.home.tick(self.control, 1001.0)
        self.assertEqual(self.control.phases()[-1], ("UNKNOWN", "CHARGE_UNKNOWN"))
        self.assertEqual(self.actuator.funds.money, 350)

    def test_a_charge_removal_still_there_after_thirty_seconds_says_remove_unconfirmed(self):
        self.actuator.money_hidden_after_charge = True
        self.actuator.removal_queued = True
        self.run_cmd("buy", self.args)
        self.home.tick(self.control, 1000.0)
        self.home.tick(self.control, 1031.0)
        self.assertEqual(self.control.phases()[-1], ("UNKNOWN", "REMOVE_UNCONFIRMED"))
        self.assertEqual(self.control.events[-1]["object_id"], "9000")
        self.assertEqual(self.actuator.funds.money, 350)

    def test_a_charge_the_game_will_not_remove_is_unknown_with_the_object_id(self):
        self.actuator.money_hidden_after_charge = True
        self.actuator.remove_refused = True
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases()[-1], ("UNKNOWN", "REMOVE_UNCONFIRMED"))
        self.assertEqual(self.control.events[-1]["object_id"], "9000")

    def test_a_spot_search_that_raises_removes_what_it_made_and_says_spot_failed(self):
        """HOME2-2 / T4: nothing is charged before the spot is found, so a search that raises removes the object."""
        self.actuator.spot_error = RuntimeError("points")
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases(), [("ACCEPTED", None), ("REJECTED", "SPOT_FAILED")])
        self.assertEqual(self.control.events[-1]["detail"], "RuntimeError")
        self.assertTrue(self.actuator.created[0].removed)
        self.assertNotIn("try_remove", [c[0] for c in self.actuator.calls])
        self.assertEqual(self.actuator.funds.money, 500)

    def test_a_spot_failure_whose_removal_is_refused_keeps_the_object_id(self):
        self.actuator.spot_error = RuntimeError("points")
        self.actuator.remove_refused = True
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases()[-1], ("UNKNOWN", "REMOVE_UNCONFIRMED"))
        self.assertEqual(self.control.events[-1]["object_id"], "9000")
        self.assertEqual(self.actuator.funds.money, 500)

    def test_a_charge_the_funds_refuse_removes_the_object_and_takes_nothing(self):
        self.actuator.charge_refused = True
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "NO_FUNDS"))
        self.assertTrue(self.actuator.created[0].removed)
        self.assertEqual(self.actuator.funds.money, 500)

    def test_a_refund_that_fails_is_said_in_the_refusal(self):
        self.actuator.place_error = RuntimeError("refused")
        self.actuator.refund_refused = True
        self.assertFalse(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "PLACE_FAILED"))
        self.assertEqual(self.control.events[-1]["detail"], "refund failed")
        self.assertEqual(self.actuator.funds.money, 350)

    def test_a_placed_purchase_whose_facts_the_schema_refuses_is_still_finished_with_its_object(self):
        """SEAM2-9 / W13 R2: a refused FINISHED row keeps its phase and object id; only its facts are left out."""
        self.control.refuse_results = True
        self.assertTrue(self.run_cmd("buy", self.args))
        self.assertEqual(self.control.phases()[-1], ("FINISHED", "PLACED"))
        self.assertEqual(self.control.events[-1]["object_id"], "9000")
        self.assertIsNone(self.control.events[-1]["result"])

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

    def test_the_result_names_the_facing_object_and_whether_it_backs_on_a_wall(self):
        self.actuator.spot = dict(self.actuator.spot, facing_id="9")
        self.item.wall = True
        self.assertTrue(self.run_cmd("place", self.args()))
        result = self.control.events[-1]["result"]
        self.assertEqual((result["facing_id"], result["wall"]), ("9", True))

    def test_a_wall_item_is_searched_against_a_wall(self):
        """HOME-5: the definition's wall flags reach the search, so a wall item is placed against a wall."""
        self.actuator.placement_flags = 1
        self.assertTrue(self.run_cmd("place", self.args()))
        self.assertEqual(self.actuator.wall_items, [True])

    def test_the_rooms_are_kept_for_the_facts_and_dropped_once_the_edit_is_done(self):
        """HOME2-5 / W13 R2: the grid is read once per edit, so it is not dropped before the facts that read it."""
        self.assertTrue(self.run_cmd("place", self.args()))
        self.assertEqual(self.actuator.order, ["near", "forget"])

    def test_an_inventory_item_leaves_her_inventory_when_it_is_placed(self):
        """HOME-2: the game's own removal from the inventory comes before the move, so the item is not in two places."""
        self.assertTrue(self.run_cmd("place", self.args()))
        self.assertFalse(self.item.inventory)
        self.assertEqual([c[0] for c in self.actuator.calls if c[0] in ("take", "place")], ["take", "place"])

    def test_a_placement_the_game_refuses_puts_the_item_back_in_her_inventory(self):
        self.actuator.place_error = RuntimeError("refused")
        self.assertFalse(self.run_cmd("place", self.args()))
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "PLACE_FAILED"))
        self.assertTrue(self.item.inventory)

    def test_a_put_back_that_fails_is_unknown_with_the_object_id(self):
        self.actuator.place_error = RuntimeError("refused")
        self.actuator.put_back_refused = True
        self.assertFalse(self.run_cmd("place", self.args()))
        self.assertEqual(self.control.phases()[-1], ("UNKNOWN", "PLACE_FAILED"))
        self.assertEqual(self.control.events[-1]["object_id"], "41")

    def test_an_item_the_game_does_not_release_is_refused_before_the_move(self):
        self.actuator.take_refused = True
        self.assertFalse(self.run_cmd("place", self.args()))
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "PLACE_FAILED"))
        self.assertNotIn("place", [c[0] for c in self.actuator.calls])

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

    def test_instead_on_a_target_that_stands_and_was_never_moved_is_not_free(self):
        """A6-19: the target still stands and she never moved or sold it: NOT_FREE, not NO_SPOT."""
        self.actuator.objects["77"] = FakeObj("77", spot={"translation": (1.0, 0.0, 2.0)})
        self.assertFalse(self.run_cmd("place", self.args(place={"rel": "instead", "target_id": "77"})))
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "NOT_FREE"))

    def test_instead_on_a_target_moved_away_takes_the_spot_it_left(self):
        self.actuator.objects["77"] = FakeObj("77", spot={"translation": (5.0, 0.0, 5.0)})
        self.home.state_of(self.control).vacated["77"] = {"translation": (1.0, 0.0, 2.0), "orientation": None,
                                                          "routing_surface": None, "slot": None}
        self.assertTrue(self.run_cmd("place", self.args(place={"rel": "instead", "target_id": "77"})))
        self.assertEqual(self.control.phases()[-1], ("FINISHED", "PLACED"))

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

    def test_an_inventory_item_is_not_moved_it_is_placed(self):
        """S6 IN_INVENTORY: a move of an item in her inventory is refused; the item is placed instead."""
        self.bed.inventory = True
        self.assertFalse(self.run_cmd("move", self.args()))
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "IN_INVENTORY"))
        self.assertNotIn("place", [c[0] for c in self.actuator.calls])

    def test_a_move_forgets_the_sampled_rooms_after_the_edit(self):
        self.assertTrue(self.run_cmd("move", self.args()))
        self.assertEqual(self.actuator.rooms_forgotten, 1)

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

    def test_an_object_whose_use_cannot_be_read_is_not_moved(self):
        """HOME2-10: only a known False lets an object move; an unreadable use is refused as unreadable."""
        self.bed.in_use = None
        self.assertFalse(self.run_cmd("move", self.args()))
        self.assertEqual(self.control.phases(), [("REJECTED", "IN_USE")])
        self.assertEqual(self.control.events[-1]["detail"], "unreadable")
        self.assertNotIn("place", [c[0] for c in self.actuator.calls])

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
    """HOME-9: a sale is paid only once the game has finished the removal (destroy only queues it); the act is FINISHED
    SOLD on a later tick, and UNKNOWN SELL_UNCONFIRMED, not paid, when the object is still there after 30 s."""

    def setUp(self):
        super(SellTests, self).setUp()
        self.chair = FakeObj("41", value=40)
        self.actuator.objects["41"] = self.chair

    def tick(self, now):
        self.home.tick(self.control, now)

    def test_a_sale_is_accepted_and_not_paid_until_the_game_has_removed_it(self):
        self.actuator.removal_queued = True
        self.assertTrue(self.run_cmd("sell", {"object_id": "41"}))
        self.assertEqual(self.control.phases(), [("ACCEPTED", None)])
        self.tick(1000.0)
        self.assertEqual(self.control.phases(), [("ACCEPTED", None)])
        self.assertEqual(self.actuator.funds.money, 500)

    def test_once_the_removal_is_finished_the_sale_is_paid_and_finished(self):
        self.actuator.removal_queued = True
        self.run_cmd("sell", {"object_id": "41"})
        self.actuator.process_queue()
        self.tick(1001.0)
        self.assertEqual(self.control.phases(), [("ACCEPTED", None), ("FINISHED", "SOLD")])
        result = self.control.events[-1]["result"]
        self.assertEqual((result["value"], result["funds"]), (40, 540))
        self.assertEqual(self.actuator.funds.money, 540)
        self.tick(1002.0)
        self.assertEqual(len(self.control.events), 2)

    def test_a_sale_completes_on_the_next_tick_when_the_game_removes_at_once(self):
        self.assertTrue(self.run_cmd("sell", {"object_id": "41"}))
        self.assertEqual(self.control.phases(), [("ACCEPTED", None)])
        self.tick(1000.0)
        self.assertEqual(self.control.phases()[-1], ("FINISHED", "SOLD"))
        self.assertEqual(self.actuator.funds.money, 540)

    def test_an_object_still_there_after_thirty_seconds_is_unknown_and_not_paid(self):
        self.actuator.removal_queued = True
        self.run_cmd("sell", {"object_id": "41"})
        self.tick(1000.0)
        self.tick(1029.0)
        self.assertEqual(self.control.phases(), [("ACCEPTED", None)])
        self.tick(1031.0)
        self.assertEqual(self.control.phases()[-1], ("UNKNOWN", "SELL_UNCONFIRMED"))
        self.assertEqual(self.control.events[-1]["object_id"], "41")
        self.assertEqual(self.actuator.funds.money, 500)

    def test_an_item_she_carries_is_sold_like_any_other(self):
        """SEAM2-2: a thing in her inventory is found (find_thing) and sold; it is paid once the game has removed it."""
        self.chair.inventory = True
        self.assertTrue(self.run_cmd("sell", {"object_id": "41"}))
        self.assertEqual(self.control.phases(), [("ACCEPTED", None)])
        self.tick(1000.0)
        self.assertEqual(self.control.phases()[-1], ("FINISHED", "SOLD"))
        self.assertEqual(self.actuator.funds.money, 540)

    def test_a_second_sale_of_an_object_whose_sale_is_pending_is_refused(self):
        """HOME2-1 / T4: the first sale's act would never get its row, and its money would be overwritten; the second
        sale is refused SELL_PENDING, and the first is paid once, when the game has removed the object."""
        self.actuator.removal_queued = True
        self.assertTrue(self.run_cmd("sell", {"object_id": "41"}))
        self.assertFalse(self.run_cmd("sell", {"object_id": "41"}, act_id=ACT_TWO))
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "SELL_PENDING"))
        self.assertEqual(self.control.events[-1]["act_id"], ACT_TWO)
        self.actuator.process_queue()
        self.tick(1001.0)
        self.assertEqual(self.control.phases(), [("ACCEPTED", None), ("REJECTED", "SELL_PENDING"),
                                                 ("FINISHED", "SOLD")])
        self.assertEqual(self.actuator.funds.money, 540)

    def test_an_object_whose_use_cannot_be_read_is_not_sold(self):
        """HOME2-10: only a known False lets an object go; an unreadable use is refused as unreadable."""
        self.chair.in_use = None
        self.assertFalse(self.run_cmd("sell", {"object_id": "41"}))
        self.assertEqual(self.control.events[-1]["code"], "IN_USE")
        self.assertEqual(self.control.events[-1]["detail"], "unreadable")
        self.assertFalse(self.chair.removed)

    def test_a_sale_counts_as_earnings(self):
        """SEAM2-10 / W13 R2: a sale is earnings (funds_add with count_as_earnings True)."""
        self.assertTrue(self.run_cmd("sell", {"object_id": "41"}))
        self.tick(1000.0)
        self.assertEqual(self.actuator.earnings, [True])

    def test_a_settlement_that_raises_ends_its_act_unknown_and_is_not_settled_again(self):
        """HOME2-12 / W13 R2: a raise in the settlement is UNKNOWN E2_EXCEPTION for the act, and the removal is not
        settled a second time."""
        self.actuator.removal_queued = True
        self.run_cmd("sell", {"object_id": "41"})
        self.actuator.process_queue()

        def broken(funds, amount, sim, count_as_earnings=True):
            raise RuntimeError("row")

        self.actuator.funds_add = broken
        self.tick(1001.0)
        self.assertEqual(self.control.phases()[-1], ("UNKNOWN", "E2_EXCEPTION:RuntimeError"))
        del self.actuator.funds_add
        self.tick(1002.0)
        self.assertEqual(len(self.control.events), 2)
        self.assertEqual(self.actuator.funds.money, 500)

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

    def test_a_removal_the_game_refuses_now_is_rejected_and_not_paid(self):
        self.actuator.sell_error = RuntimeError("no")
        self.assertFalse(self.run_cmd("sell", {"object_id": "41"}))
        self.assertEqual(self.control.phases()[-1], ("REJECTED", "SELL_FAILED"))
        self.tick(1000.0)
        self.assertEqual(self.actuator.funds.money, 500)


class GuardListTests(unittest.TestCase):
    """CORE-6/16 and HOME-2: the placement and inventory calls are the actuator's alone, and the archive check requires
    the build modules too; the object creator is the one name imported from objects.system."""

    def test_placement_and_inventory_calls_are_actuator_only(self):
        for name in ("create_object", "move_to", "add_child", "try_remove_object_by_id",
                     "clear_previous_inventory", "player_try_add_object", "save_using", "destroy"):
            self.assertIn(name, guards.ACTUATOR_ONLY_CALLS, name)

    def test_a_placement_call_outside_the_actuator_is_a_finding(self):
        findings = guards.scan_text("def place(obj):\n    obj.move_to(translation=None)\n", "home.py")
        self.assertTrue(any("move_to" in finding for finding in findings), findings)

    def test_the_object_creator_is_the_only_name_narrowed_from_objects_system(self):
        self.assertEqual(guards.NARROW_GAME_IMPORTS["objects.system"], {"create_object"})
        findings = guards.scan_text("from objects.system import create_object, destroy_all\n", "home.py")
        self.assertTrue(findings, findings)

    def test_the_build_modules_are_in_the_archive_check(self):
        for name in ("atlas", "tuned", "act_menu", "home", "reach"):
            self.assertIn(name, guards.PRODUCTION_MODULES)

    def test_a_result_list_item_is_at_most_twenty_characters(self):
        """CORE-14: a result's list item is a game id (at most 20 digits) or a short word; longer is refused."""
        schema = modules()[3]
        schema._validate_result({"beside": ["1" * 20]})
        with self.assertRaises(schema.SchemaError):
            schema._validate_result({"beside": ["1" * 21]})


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


class RoomSearchTests(unittest.TestCase):
    """HOME-5/6/24/25 and A6-6/18: rooms are found by sampling the lot with the game's own room lookup, a wall search
    starts on the room's border and faces the room, a facing is passed into the start, and a spot must read the room.
    Fakes shaped like the game: a lot's sampling (world.lot.get_uniform_sampling_of_points, z-major), get_room_id,
    create_starting_location (with an orientation), find_good_location (here the start itself) and angle_to_yaw."""

    class Point(object):
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z

    class Lot(object):
        def __init__(self, size_x, size_z):
            self.size_x, self.size_z = size_x, size_z
            self.calls = []

        def get_uniform_sampling_of_points(self, samples_x, samples_z):
            self.calls.append((samples_x, samples_z))
            step_x, step_z = self.size_x / float(samples_x), self.size_z / float(samples_z)
            return [RoomSearchTests.Point((x + 0.5) * step_x, 0.0, (z + 0.5) * step_z)
                    for z in range(samples_z) for x in range(samples_x)]

    class Obj(object):
        def __init__(self, object_id, x=0.0, z=0.0, level=0, wall_flag=False):
            self.id = object_id
            self.position = RoomSearchTests.Point(x, 0.0, z)
            self.level = level
            self.wall_flag = wall_flag
            self.routing_surface = "surface"

        def _has_placement_flag(self, flag):
            return self.wall_flag and flag == 1

    def setUp(self):
        self.actuator = modules()[0].e2_actuator
        self.lot = self.Lot(6.0, 6.0)
        self.room_calls = []
        self.yaw_calls = []
        self.sim = self.Obj("7", x=0.0, z=0.0)
        self.item = self.Obj("41")
        self.objects = {"9": self.Obj("9", x=4.5, z=0.5)}
        self.room_split = 2.0   # room 1 is x < 2 m, room 2 is the rest of the lot

        def room_of(zone_id, position, level):
            self.room_calls.append((zone_id, level))
            return 1 if position.x < self.room_split else 2

        class FakeFgl(object):
            def create_starting_location(self_inner, position=None, orientation=None, routing_surface=None):
                return {"position": position, "orientation": orientation, "surface": routing_surface}

            def create_fgl_context_for_object(self_inner, starting, obj):
                return starting

            def find_good_location(self_inner, context):
                return context["position"], context["orientation"], None

        def yaw(angle):
            self.yaw_calls.append(angle)
            return ("yaw", round(angle, 6))

        services = types.SimpleNamespace(active_lot=lambda: self.lot, current_zone_id=lambda: 7)
        patches = [mock.patch.object(self.actuator, "services", services),
                   mock.patch.object(self.actuator, "get_room_id", room_of),
                   mock.patch.object(self.actuator, "placement", FakeFgl()),
                   mock.patch.object(self.actuator, "angle_to_yaw_quaternion", yaw),
                   mock.patch.object(self.actuator, "find_object",
                                     lambda object_id: self.objects.get(str(object_id))),
                   mock.patch.object(self.actuator, "lot_objects",
                                     lambda: [self.sim, self.item] + list(self.objects.values()))]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.actuator.forget_rooms()
        self.addCleanup(self.actuator.forget_rooms)

    def room_of_spot(self, spot):
        return "1" if spot["translation"].x < self.room_split else "2"

    def test_an_empty_room_is_found_by_sampling(self):
        spot = self.actuator.find_spot(self.item, self.sim, {"rel": "in", "room_id": "2"})
        self.assertIsNotNone(spot)
        self.assertEqual(self.room_of_spot(spot), "2")

    def test_the_lot_is_sampled_once_per_zone_and_level_until_a_home_edit(self):
        """The lot's grid (36 points at 1 m for a 6 m lot, one level) is read once, then kept until forget_rooms."""
        self.actuator.find_spot(self.item, self.sim, {"rel": "in", "room_id": "2"})
        self.assertEqual(self.lot.calls, [(6, 6)])
        self.assertEqual(len(self.room_calls), 36 + 1)   # the grid, and the check that the spot reads the room
        self.actuator.find_spot(self.item, self.sim, {"rel": "wall", "room_id": "1"})
        self.assertEqual(len(self.lot.calls), 1)
        self.actuator.forget_rooms()
        self.actuator.find_spot(self.item, self.sim, {"rel": "in", "room_id": "2"})
        self.assertEqual(self.lot.calls, [(6, 6), (6, 6)])

    def test_the_sampling_is_capped_per_axis(self):
        self.lot = self.Lot(200.0, 200.0)
        self.actuator.forget_rooms()
        self.actuator.find_spot(self.item, self.sim, {"rel": "in", "room_id": "2"})
        self.assertEqual(self.lot.calls, [(self.actuator.ROOM_GRID_MAX, self.actuator.ROOM_GRID_MAX)])
        self.assertLessEqual(len(self.room_calls), self.actuator.ROOM_GRID_MAX ** 2 + 1)

    def test_a_wall_search_starts_on_a_border_cell_and_faces_the_room(self):
        spot = self.actuator.find_spot(self.item, self.sim, {"rel": "wall", "room_id": "2"}, wall_item=True)
        self.assertIsNotNone(spot)
        self.assertEqual(self.room_of_spot(spot), "2")
        self.assertTrue(self.actuator.against_wall(self.Obj("50", x=spot["translation"].x,
                                                            z=spot["translation"].z)))
        self.assertTrue(self.yaw_calls)
        self.assertIsNone(spot["facing_id"])

    def test_a_spot_in_the_middle_of_a_room_is_not_against_a_wall(self):
        self.assertFalse(self.actuator.against_wall(self.Obj("50", x=4.0, z=3.0)))

    def test_the_facing_object_is_applied_as_the_start_orientation(self):
        spot = self.actuator.find_spot(self.item, self.sim, {"rel": "in", "room_id": "2", "facing": "9"})
        self.assertEqual(spot["facing_id"], "9")
        start = spot["translation"]
        expected = math.atan2(4.5 - start.x, 0.5 - start.z)
        self.assertAlmostEqual(self.yaw_calls[-1], expected, places=6)
        self.assertEqual(spot["orientation"], ("yaw", round(expected, 6)))

    def test_facing_the_room_applies_an_orientation_but_names_no_object(self):
        spot = self.actuator.find_spot(self.item, self.sim, {"rel": "in", "room_id": "2", "facing": "room"})
        self.assertIsNone(spot["facing_id"])
        self.assertTrue(self.yaw_calls)

    def test_a_facing_object_that_is_gone_is_not_applied(self):
        spot = self.actuator.find_spot(self.item, self.sim, {"rel": "in", "room_id": "2", "facing": "99"})
        self.assertIsNone(spot["facing_id"])
        self.assertEqual(self.yaw_calls, [])

    def test_a_spot_outside_the_room_is_refused(self):
        self.actuator.get_room_id = lambda zone_id, position, level: 1
        self.assertIsNone(self.actuator.find_spot(self.item, self.sim, {"rel": "in", "room_id": "2"}))

    def test_a_room_the_lot_does_not_have_is_no_spot(self):
        self.assertIsNone(self.actuator.find_spot(self.item, self.sim, {"rel": "in", "room_id": "5"}))

    def test_a_lot_that_cannot_be_read_is_no_spot(self):
        services = types.SimpleNamespace(active_lot=lambda: None, current_zone_id=lambda: 7)
        with mock.patch.object(self.actuator, "services", services):
            self.actuator.forget_rooms()
            self.assertIsNone(self.actuator.find_spot(self.item, self.sim, {"rel": "in", "room_id": "2"}))

    def test_beside_a_wall_target_a_wall_item_starts_along_the_same_wall(self):
        self.objects["9"] = self.Obj("9", x=5.5, z=3.5, wall_flag=True)
        spot = self.actuator.find_spot(self.Obj("41", wall_flag=True), self.sim,
                                       {"rel": "beside", "target_id": "9"}, wall_item=True)
        self.assertIsNotNone(spot)
        self.assertEqual(self.room_of_spot(spot), "2")
        self.assertTrue(self.actuator.against_wall(self.Obj("50", x=spot["translation"].x,
                                                            z=spot["translation"].z)))


    def test_a_lot_passed_in_is_not_read_again_for_the_search_or_the_wall(self):
        """HOME2-5 / W13 R2: the lot's objects are read once per edit and passed to the search and the wall fact."""
        reads = []
        lot = [self.sim, self.item] + list(self.objects.values())

        def counting():
            reads.append(1)
            return lot

        with mock.patch.object(self.actuator, "lot_objects", counting):
            self.actuator.find_spot(self.item, self.sim, {"rel": "wall", "room_id": "1"}, wall_item=True, lot=lot)
            self.actuator.against_wall(self.item, lot=lot)
        self.assertEqual(reads, [])


class PortalNameTests(unittest.TestCase):
    """HOME-7: a portal is a door, gate or archway by the last word of its class name, never by a substring: an
    'IndoorPlant' or an 'OutdoorBench' is not a door."""

    def setUp(self):
        self.actuator = modules()[0].e2_actuator

    def named(self, name):
        return type(name, (object,), {})()

    def test_a_door_gate_or_archway_is_a_portal(self):
        for name in ("Door", "FrontDoor", "SlidingDoor", "Gate", "WroughtIronGate", "Archway"):
            self.assertTrue(self.actuator.is_portal(self.named(name)), name)

    def test_a_name_that_only_contains_door_is_not_a_portal(self):
        for name in ("IndoorPlant", "OutdoorBench", "Doorbell", "DoorMat"):
            self.assertFalse(self.actuator.is_portal(self.named(name)), name)


class NearObjectTests(unittest.TestCase):
    """HOME-26: what is beside a placed object is another object on the same level, on the lot, that is not a Sim and
    not in an inventory: a sofa on the floor above, her own Sim and an item in her pocket are not beside it."""

    class Point(object):
        def __init__(self, x, z):
            self.x, self.y, self.z = x, 0.0, z

    class Thing(object):
        def __init__(self, object_id, x, z, level=0, sim=False, inventory=False, lot=True):
            self.id = object_id
            self.position = NearObjectTests.Point(x, z)
            self.level = level
            self.is_sim = sim
            self._inventory = inventory
            self._lot = lot

        def is_on_active_lot(self, margin):
            return self._lot

        def is_in_inventory(self):
            return self._inventory

    def setUp(self):
        self.actuator = modules()[0].e2_actuator
        self.things = []
        patch = mock.patch.object(self.actuator, "_all_objects", lambda: list(self.things))
        patch.start()
        self.addCleanup(patch.stop)

    def near(self, subject):
        return sorted(item["object_id"] for item in self.actuator.near_objects(subject, 1.5))

    def test_a_chair_on_the_same_level_on_the_lot_is_beside(self):
        subject = self.Thing("1", 0.0, 0.0)
        self.things = [subject, self.Thing("2", 0.5, 0.0)]
        self.assertEqual(self.near(subject), ["2"])

    def test_a_thing_too_far_away_is_not_asked_whether_it_is_on_the_lot(self):
        """HOME2-5 / W13 R2: the distance is checked before the lot test, so a far thing costs one read."""
        asked = []
        far = self.Thing("6", 9.0, 0.0)
        far.is_on_active_lot = lambda margin: asked.append("6") or True
        subject = self.Thing("1", 0.0, 0.0)
        self.things = [subject, far]
        self.assertEqual(self.near(subject), [])
        self.assertEqual(asked, [])

    def test_the_floor_above_a_Sim_an_inventory_item_and_off_lot_things_are_not_beside(self):
        subject = self.Thing("1", 0.0, 0.0)
        self.things = [subject, self.Thing("2", 0.0, 0.0, level=1), self.Thing("3", 0.2, 0.0, sim=True),
                       self.Thing("4", 0.2, 0.0, inventory=True), self.Thing("5", 0.2, 0.0, lot=False),
                       self.Thing("6", 9.0, 0.0)]
        self.assertEqual(self.near(subject), [])


class FundsEffectTests(unittest.TestCase):
    """HOME-12: a payment or a refund is paid only when the money went up by exactly the amount (read before and after):
    a notice that raises after the money moved still counts; a payment that did not move the money does not."""

    class Funds(object):
        def __init__(self, money, notice_raises=False, adds=True):
            self.money = money
            self.notice_raises = notice_raises
            self.adds = adds
            self.earned = []

        def add(self, amount, reason, count_as_earnings=True):
            self.earned.append(count_as_earnings)
            if self.adds:
                self.money += amount
            if self.notice_raises:
                raise RuntimeError("notice")

    def setUp(self):
        self.actuator = modules()[0].e2_actuator

    def test_a_payment_counts_when_the_money_moved_even_if_the_notice_raised(self):
        funds = self.Funds(500, notice_raises=True)
        self.assertTrue(self.actuator.funds_add(funds, 40, None))
        self.assertEqual(funds.money, 540)

    def test_a_payment_is_earnings_unless_the_caller_says_it_is_not(self):
        """SEAM2-10 / W13 R2: a refund passes count_as_earnings False; a sale passes nothing and counts."""
        funds = self.Funds(500)
        self.assertTrue(self.actuator.funds_add(funds, 40, None, count_as_earnings=False))
        self.assertTrue(self.actuator.funds_add(funds, 40, None))
        self.assertEqual(funds.earned, [False, True])

    def test_a_payment_that_did_not_move_the_money_is_not_paid(self):
        funds = self.Funds(500, adds=False)
        self.assertFalse(self.actuator.funds_add(funds, 40, None))
        self.assertEqual(funds.money, 500)


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


class ThingsRowsReadTests(unittest.TestCase):
    """HOME-18: the things rows are None when her home or her inventory cannot be read, so the writer keeps its last
    list; only a lot that is not her home (at_home False) gives her inventory alone. Never raises."""

    def setUp(self):
        self.actuator = modules()[0].e2_actuator
        self.info = types.SimpleNamespace(household_id=9)
        self.inventory = [types.SimpleNamespace(id=5, definition=types.SimpleNamespace(id=55))]
        self.sim = types.SimpleNamespace(inventory_component=self.inventory)
        self.body = (self.info, self.sim)
        self.home = True
        self.lot = []
        patches = [mock.patch.object(self.actuator, "room_of", lambda obj: "5"),
                   mock.patch.object(self.actuator, "_body", lambda: self.body),
                   mock.patch.object(self.actuator, "at_home", lambda household: self.home),
                   mock.patch.object(self.actuator, "lot_objects", lambda: self.lot)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_no_body_is_none(self):
        self.body = (None, None)
        self.assertIsNone(_read_things(self.actuator))

    def test_an_unreadable_home_is_none(self):
        self.home = None
        self.assertIsNone(_read_things(self.actuator))

    def test_an_unreadable_inventory_is_none(self):
        self.sim.inventory_component = None
        self.assertIsNone(_read_things(self.actuator))

    def test_a_lot_that_is_not_her_home_gives_the_inventory_only(self):
        self.home = False
        self.lot.append(types.SimpleNamespace(id=7))
        rows = _read_things(self.actuator)
        self.assertEqual([(row["object_id"], row["where"]) for row in rows], [(5, "inventory")])

    class LotThing(object):
        def __init__(self, object_id):
            self.id = object_id
            self.is_sim = False

        def get_household_owner_id(self):
            return 9

    def test_the_inventory_comes_first_and_the_total_counts_what_the_list_keeps(self):
        """SEAM2-4 / T1: her inventory first, then the lot; a build item is not counted; total is what the list keeps."""
        wall = type("Wall", (self.LotThing,), {})
        self.lot.extend([self.LotThing(100), wall(101), self.LotThing(102)])
        rows, total = self.actuator.things_rows(modules()[1].thing_listed, 600)
        self.assertEqual([row["object_id"] for row in rows], [5, 100, 102])
        self.assertEqual(total, 3)

    def test_only_the_things_the_list_keeps_are_read_in_full(self):
        """HOME2-11 / W13 R2: states are read for the things the list keeps up to its limit, not for the rest."""
        read = []
        self.lot.extend(self.LotThing(100 + index) for index in range(5))
        with mock.patch.object(self.actuator, "_thing_states", lambda obj: read.append(obj.id) or []):
            rows, total = self.actuator.things_rows(lambda name: True, 2)
        self.assertEqual(read, [5, 100])
        self.assertEqual((len(rows), total), (2, 6))

    def test_her_home_and_inventory_are_read_together(self):
        rows = _read_things(self.actuator)
        self.assertEqual([row["where"] for row in rows], ["inventory"])


class InventoryLookupTests(unittest.TestCase):
    """SEAM2-2 (W13 R2): an object she carries is in the inventory manager, not in the zone's object manager. find_object
    falls back to it; object_gone waits until neither manager holds the object."""

    class Manager(object):
        def __init__(self, objects):
            self.objects = objects

        def get(self, object_id):
            return self.objects.get(object_id)

    def setUp(self):
        self.actuator = modules()[0].e2_actuator
        self.zone_object = object()
        self.carried = object()
        self.zone = self.Manager({1: self.zone_object})
        self.inventory = self.Manager({41: self.carried})
        services = types.SimpleNamespace(object_manager=lambda: self.zone,
                                         inventory_manager=lambda: self.inventory)
        patch = mock.patch.object(self.actuator, "services", services)
        patch.start()
        self.addCleanup(patch.stop)

    def test_an_object_in_the_zone_is_found_in_the_object_manager(self):
        self.assertIs(self.actuator.find_thing("1"), self.zone_object)

    def test_a_carried_object_is_found_in_the_inventory_manager(self):
        self.assertIs(self.actuator.find_thing("41"), self.carried)

    def test_find_object_still_reads_the_zone_only(self):
        """The probe's other callers (e2_control's act targets) keep the zone's object manager."""
        self.assertIsNone(self.actuator.find_object("41"))

    def test_an_id_neither_manager_holds_is_none(self):
        self.assertIsNone(self.actuator.find_thing("99"))
        self.assertIsNone(self.actuator.find_thing("not an id"))

    def test_a_carried_object_is_not_gone_until_the_inventory_lets_it_go(self):
        self.assertIs(self.actuator.object_gone("41"), False)
        self.inventory.objects.pop(41)
        self.assertIs(self.actuator.object_gone("41"), True)

    def test_an_object_in_neither_manager_is_gone(self):
        self.assertIs(self.actuator.object_gone("99"), True)

    def test_a_manager_that_cannot_be_read_is_unknown(self):
        self.zone = None
        self.assertIsNone(self.actuator.object_gone("99"))


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
        persistence.save_timeline = None   # the game's persistence service always has one (None: no save open)
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
        self.assertIn("buy", self.probe._OBSERVE_REFUSED)
        self.assertIn("sell", self.probe._OBSERVE_REFUSED)

    def test_calibrate_allows_the_read_only_catalogue_dump(self):
        """CORE-15: the catalogue dump writes the catalogue record only; it is not an act."""
        self.assertNotIn("catalog_dump", self.probe._OBSERVE_REFUSED)

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

    def test_every_sampling_tick_runs_the_home_tick_even_when_nothing_else_is_due(self):
        """HOME-14: the save's confirmation and the removals run on each sample, before the zone check."""
        calls = []
        original = self.probe.home.tick
        self.probe.home.tick = lambda control, now: calls.append(now)
        self.addCleanup(setattr, self.probe.home, "tick", original)
        self.probe._reach_tick({"event_kind": "not_a_presence_snapshot"})
        self.probe._reach_tick({"event_kind": "not_a_presence_snapshot"})
        self.assertEqual(len(calls), 2)

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
