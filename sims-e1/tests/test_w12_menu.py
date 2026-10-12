"""W12-PM (probe 2.39.0 menu): the near part on every build, on her move and on a look (C1); a refusal shared only by
definition when it passed (C3); the reasons of refused near acts (C4); a wall object's no-way reads None (C6); 512
objects and what the cap drops (C8); on_lot (C10); the spot stages (C11); identical texts folded before the caps and
acts cut counted (C12); a pie-menu act offered one entry per choice and pushed by name (G1).

Fakes only. Objects, acts and choices are invented classes; the clock is the fake clock of test_2371b."""
import types
import unittest

import test_2160_act as acts
import test_e2
from test_2160_act import GUID
from test_e2 import _Interaction
from test_ds3_senses import _Wrapper

NEAR = 11        # her room "4", two metres off (invented)
ROOM5 = 12       # a second room, "5"
FRIDGE = 21      # a fridge in her room, with a pie-menu snack act
FAR = 100        # a far object, its id from FAR upwards
FAR_GUID = 7000  # invented guid64s for far acts
ACT = "b" * 32
PIE_GUID = 9000
MAX_CAP = 512


class _Refused(object):
    """A falsy test result with a refusal tooltip, as the game returns it."""

    def __init__(self, key):
        self.tooltip = _Wrapper(key)

    def __bool__(self):
        return False

    def __str__(self):
        return "refused"


def _act(name, guid, text=None):
    attrs = {"guid64": guid, "allow_user_directed": True}
    if text is not None:
        attrs["display_name"] = _Wrapper(text)
    return type(name, (object,), attrs)


class _LotThing(acts._Thing):
    def is_on_active_lot(self):
        return True


class _OffLotThing(acts._Thing):
    def is_on_active_lot(self):
        return False


class _WallThing(acts._Thing):
    """An object whose connectivity answer is set by the test; its placement flags come from wall_flags."""
    is_connected_result = False
    wall_flags = ()

    def is_connected(self, sim):
        return self.is_connected_result

    def _has_placement_flag(self, placement_flag):
        return placement_flag in self.wall_flags


class WallMirror(_WallThing):
    wall_flags = (2,)  # EDGE_AGAINST_WALL, read through the game's own flag method


PlainChair = type("object_chair", (_WallThing,), {})
WallLight = type("object_light_wall", (_WallThing,), {})  # a wall by class name, when no flag is readable


class MenuW12Base(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.probe = self.base.probe
        self.probe._MENU_FAR.clear()
        self.probe._menu_reset()
        self.allowed = {int(GUID)} | set(range(FAR_GUID, FAR_GUID + 4000)) | {PIE_GUID}
        self.refuse_pairs = set()
        self.refuse_keys = {}
        self.base.sim.test_super_affordance = self._test
        self.things = []
        self.probe._lot_snapshot = lambda: (list(self.things), None)
        self.rooms = {NEAR: "4", ROOM5: "5", FRIDGE: "4"}
        room_of = self.probe.observers._room
        self.addCleanup(setattr, self.probe.observers, "_room", room_of)
        self.probe.observers._room = lambda obj, position: self.rooms.get(getattr(obj, "id", None), "9")
        self.clock = {"s": 100.0}
        now_s = self.probe._now_s
        self.addCleanup(setattr, self.probe, "_now_s", now_s)
        self.probe._now_s = lambda: self.clock["s"]
        self.zone = {"current": object()}
        current_zone = self.probe._current_zone
        self.addCleanup(setattr, self.probe, "_current_zone", current_zone)
        self.probe._current_zone = lambda: self.zone["current"]
        self.body = {"x": 0.0, "y": 0.0, "z": 0.0, "level": 0}
        self.row = {"event_kind": "presence_snapshot", "zone": {"position": self.body, "room": "4"}}
        self.base.LedgerWriter.records = [self.base.continuing()[0]]
        self.assertTrue(self.probe._cmd_arm("HOME"))
        self.assertTrue(self.probe._cmd_start())
        self.base.tick()
        self.probe._menu_reset()
        self.probe._MENU_FAR.clear()
        self.baseline = len(self.base.e2("act_menu"))

    def tearDown(self):
        writer = self.base.LedgerWriter.instances[-1] if self.base.LedgerWriter.instances else None
        if writer is not None:
            writer.finish()

    def _test(self, affordance, target, context):
        key = (affordance.guid64, target.id)
        if key in self.refuse_pairs:
            return _Refused(self.refuse_keys.get(key, 0x7001))
        return affordance.guid64 in self.allowed

    def written(self):
        return self.base.e2("act_menu")

    def new_rows(self, mark):
        return self.base.e2("act_menu")[mark:]

    def tick(self, seconds, row=None):
        self.clock["s"] = seconds
        self.probe._menu_tick(row or self.row)

    def finish(self, seconds, row=None):
        """Ticks at one clock time until the build in progress is done (a fixed clock: no partial writes)."""
        self.tick(seconds, row)
        guard = 0
        while self.probe._MENU is not None and guard < 2000:
            self.tick(seconds, row)
            guard += 1
        self.assertLess(guard, 2000)

    def object_by_id(self, row, object_id):
        for item in row["objects"]:
            if item["object_id"] == str(object_id):
                return item
        return None

    def near_thing(self, object_id, x, affordances, room_id=None):
        thing = _LotThing(object_id, x, affordances)
        return thing

    def far_thing(self, object_id, affordances, definition=None):
        thing = _OffLotThing(object_id, 30.0, affordances)
        if definition is not None:
            thing.definition = types.SimpleNamespace(id=definition)
        self.rooms[object_id] = "9"
        return thing

    def far_acts(self, first, count, text_base=None):
        out = []
        for index in range(count):
            text = None if text_base is None else text_base + index
            out.append(_act("far_act_%d" % (first + index), first + index, text=text))
        return out


class NearPartTests(MenuW12Base):
    def test_every_build_writes_its_near_part_as_its_far_part_starts(self):
        self.things = [self.near_thing(NEAR, 2.0, [_act("read_book", int(GUID))]),
                       self.far_thing(FAR, [_act("far_one", FAR_GUID)])]
        self.finish(100.0)
        mark = len(self.written())
        self.things = [self.near_thing(NEAR, 2.0, [_act("read_book", int(GUID))]),
                       self.far_thing(FAR, [_act("far_one", FAR_GUID)]),
                       self.far_thing(FAR + 1, [_act("far_two", FAR_GUID + 1)])]
        self.tick(120.0)  # the next build starts (REBUILD_S)
        self.assertIsNotNone(self.probe._MENU)
        self.tick(120.0)  # its first step tests the near candidates, then the far ones
        first = self.new_rows(mark)
        self.assertTrue(first, "the second build wrote no near part")
        self.assertEqual(sorted(item["object_id"] for item in first[0]["objects"]), [str(NEAR)])

    def test_a_move_into_another_room_writes_the_near_part_at_once(self):
        self.things = [self.near_thing(NEAR, 2.0, [_act("read_book", int(GUID))]),
                       self.near_thing(ROOM5, 3.0, [_act("five_act", int(GUID) + 1)])]
        self.allowed.add(int(GUID) + 1)
        self.rooms[ROOM5] = "5"
        self.finish(100.0)
        mark = len(self.written())
        moved = dict(self.row)
        moved["zone"] = {"position": self.body, "room": "5"}
        self.tick(101.0, row=moved)
        new = self.new_rows(mark)
        self.assertEqual(len(new), 1)
        five = self.object_by_id(new[0], ROOM5)
        near = self.object_by_id(new[0], NEAR)
        self.assertIsNotNone(five)
        self.assertIs(five["same_room"], True)
        self.assertIs(near["same_room"], False)

    def test_a_request_writes_one_near_part_and_is_idempotent(self):
        self.things = [self.near_thing(NEAR, 2.0, [_act("read_book", int(GUID))]),
                       self.far_thing(FAR, [_act("far_one", FAR_GUID)])]
        self.finish(100.0)
        mark = len(self.written())
        self.probe.request_menu_near()
        self.probe.request_menu_near()
        self.tick(101.0)
        self.assertEqual(len(self.new_rows(mark)), 1)
        self.tick(102.0)
        self.assertEqual(len(self.new_rows(mark)), 1, "the request is spent by one tick")

    def test_the_near_part_reads_the_distance_when_it_is_written(self):
        thing = self.near_thing(NEAR, 2.0, [_act("read_book", int(GUID))])
        self.things = [thing]
        self.finish(100.0)
        self.assertEqual(self.object_by_id(self.written()[-1], NEAR)["distance_m"], 2.0)
        thing.position = types.SimpleNamespace(x=3.0, y=0.0, z=0.0)
        mark = len(self.written())
        self.probe.request_menu_near()
        self.tick(101.0)
        self.assertEqual(self.object_by_id(self.new_rows(mark)[-1], NEAR)["distance_m"], 3.0)

    def test_the_near_part_leaves_out_far_objects_and_keeps_her_phone(self):
        self.things = [self.near_thing(NEAR, 2.0, [_act("read_book", int(GUID))]),
                       self.far_thing(FAR, [_act("far_one", FAR_GUID)])]
        self.finish(100.0)
        mark = len(self.written())
        self.probe.request_menu_near()
        self.tick(101.0)
        part = self.new_rows(mark)[-1]
        self.assertIsNone(self.object_by_id(part, FAR))
        self.assertIsNotNone(self.object_by_id(part, NEAR))


class FarCacheTests(MenuW12Base):
    def test_a_refused_far_object_does_not_hide_its_identical_kin(self):
        twin_guid = FAR_GUID + 50
        self.allowed.add(twin_guid)
        first = self.far_thing(FAR, [_act("far_twin", twin_guid)], definition=777)
        second = self.far_thing(FAR + 1, [_act("far_twin", twin_guid)], definition=777)
        self.refuse_pairs.add((twin_guid, FAR))
        self.things = [first, second]
        self.finish(100.0)
        final = self.written()[-1]
        self.assertIsNone(self.object_by_id(final, FAR), "the refused object is not on the menu")
        self.assertIsNotNone(self.object_by_id(final, FAR + 1), "its identical kin passed and is on the menu")

    def test_a_passing_far_object_shares_its_outcome_with_identical_kin(self):
        twin_guid = FAR_GUID + 51
        self.allowed.add(twin_guid)
        self.things = [self.far_thing(FAR, [_act("far_twin", twin_guid)], definition=778),
                       self.far_thing(FAR + 1, [_act("far_twin", twin_guid)], definition=778)]
        self.finish(100.0)
        final = self.written()[-1]
        self.assertIsNotNone(self.object_by_id(final, FAR))
        self.assertIsNotNone(self.object_by_id(final, FAR + 1))
        self.assertEqual(final["cached"], 1, "the identical kin's pass came from the cache, not a second test")


class RefusalTests(MenuW12Base):
    def test_a_near_object_lists_the_reasons_of_its_refused_acts(self):
        self.refuse_pairs.add((FAR_GUID + 1, NEAR))
        self.refuse_pairs.add((FAR_GUID + 2, NEAR))
        self.refuse_keys[(FAR_GUID + 1, NEAR)] = 0x7101
        self.refuse_keys[(FAR_GUID + 2, NEAR)] = 0x7102
        self.things = [self.near_thing(NEAR, 2.0, [_act("read_book", int(GUID), text=0x6001),
                                                   _act("bad_one", FAR_GUID + 1, text=0x6002),
                                                   _act("bad_two", FAR_GUID + 2, text=0x6003)])]
        self.finish(100.0)
        item = self.object_by_id(self.written()[-1], NEAR)
        self.assertEqual([act["text_key"] for act in item["acts"]], [str(0x6001)])
        self.assertEqual(item["refusals"], [{"text_key": str(0x6002), "reason_key": str(0x7101)},
                                            {"text_key": str(0x6003), "reason_key": str(0x7102)}])

    def test_a_far_object_has_no_refusal_list(self):
        self.refuse_pairs.add((FAR_GUID + 1, FAR))
        self.things = [self.far_thing(FAR, [_act("read_book", int(GUID)), _act("bad", FAR_GUID + 1)])]
        self.finish(100.0)
        item = self.object_by_id(self.written()[-1], FAR)
        self.assertIsNone(item["refusals"])

    def test_a_near_object_whose_acts_are_all_refused_is_still_listed_with_its_reasons(self):
        self.refuse_pairs.add((FAR_GUID + 1, NEAR))
        self.things = [self.near_thing(NEAR, 2.0, [_act("bad", FAR_GUID + 1, text=0x6010)])]
        self.finish(100.0)
        item = self.object_by_id(self.written()[-1], NEAR)
        self.assertIsNotNone(item)
        self.assertEqual(item["acts"], [])
        self.assertEqual(len(item["refusals"]), 1)

    def test_at_most_eight_refusals_are_kept_per_object(self):
        affordances = []
        for index in range(10):
            guid = FAR_GUID + 20 + index
            self.refuse_pairs.add((guid, NEAR))
            affordances.append(_act("bad_%d" % index, guid, text=0x6100 + index))
        self.things = [self.near_thing(NEAR, 2.0, affordances)]
        self.finish(100.0)
        item = self.object_by_id(self.written()[-1], NEAR)
        self.assertEqual(len(item["refusals"]), self.probe.schema.MENU_MAX_REFUSALS)


class WallTests(MenuW12Base):
    def test_a_wall_object_with_no_way_reads_none_and_a_floor_object_reads_false(self):
        sim = self.base.sim
        wall = WallMirror(NEAR, 2.0, [])
        wall.is_connected_result = False
        floor = PlainChair(FRIDGE, 2.0, [])
        floor.is_connected_result = False
        self.assertIsNone(self.probe.e2_actuator.reachable(sim, wall))
        self.assertIs(self.probe.e2_actuator.reachable(sim, floor), False)
        wall.is_connected_result = True
        self.assertIs(self.probe.e2_actuator.reachable(sim, wall), True)

    def test_a_wall_light_with_no_readable_flag_is_a_wall_by_its_class_name(self):
        light = WallLight(NEAR, 2.0, [])
        light.is_connected_result = False
        light._has_placement_flag = None  # unreadable: the class name is the fallback
        self.assertIsNone(self.probe.e2_actuator.reachable(self.base.sim, light))


class CapTests(unittest.TestCase):
    """The menu's cap and what it drops, at the act_menu level (fake jobs)."""

    def setUp(self):
        import test_2371_menu_speed  # noqa: F401  (the menu module is loaded by the probe base)
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.probe = self.base.probe
        self.menu = self.probe.act_menu

    def tearDown(self):
        writer = self.base.LedgerWriter.instances[-1] if self.base.LedgerWriter.instances else None
        if writer is not None:
            writer.finish()

    def jobs(self, count):
        out = []
        for index in range(count):
            object_id = str(1000 + index)
            out.append({"object_id": object_id, "definition_id": None, "class": "c", "distance_m": 10.0 + index,
                        "same_room": False, "room": str(index % 3), "on_lot": True, "person": False,
                        "guid64": "5", "name": "a", "text_key": "9", "reach_seen": None,
                        "obj": None, "affordance": None, "sim": None, "context": None})
        return out

    def test_the_cap_is_512_objects_and_the_rest_are_counted_with_their_rooms(self):
        self.assertEqual(self.probe.schema.MENU_MAX_OBJECTS, MAX_CAP)
        build = self.menu.MenuBuild(self.jobs(MAX_CAP + 18), lambda job: True, budget_ms=1e9,
                                    max_per_chunk=10000)
        build.step()
        self.assertTrue(build.done)
        payload = build.payload(1, "4")
        self.assertEqual(len(payload["objects"]), MAX_CAP)
        self.assertEqual(payload["dropped"]["objects"], 18)
        self.assertEqual(set(payload["dropped"]["rooms"]), {"0", "1", "2"} & set(payload["dropped"]["rooms"]))
        self.assertTrue(payload["dropped"]["rooms"])

    def test_dropped_and_spot_stages_are_on_part_zero_only(self):
        build = self.menu.MenuBuild(self.jobs(MAX_CAP + 2), lambda job: True, budget_ms=1e9, max_per_chunk=10000,
                                    stages={"anchors": 3, "placement": True, "terrain": True, "offers": 0})
        build.step()
        rows = self.menu.parts(build.payload(1, "4"))
        self.assertGreater(len(rows), 1)
        self.assertEqual(rows[0]["dropped"]["objects"], 2)
        self.assertEqual(rows[0]["spot_stages"]["anchors"], 3)
        for row in rows[1:]:
            self.assertIsNone(row["dropped"])
            self.assertIsNone(row["spot_stages"])
        for row in rows:
            self.probe.schema.validate_record(self.probe.schema.make_record(
                "act_menu", telemetry_session_id="s", wall_timestamp_ms=1, monotonic_ns=1, e2=row))

    def test_a_part_stays_under_the_record_limit_however_many_objects_it_holds(self):
        build = self.menu.MenuBuild([], lambda job: True)
        build.step()
        self.assertTrue(build.done)
        big = dict(build.payload(1, None))
        big["objects"] = [{"object_id": str(i), "definition_id": None, "class": "c" * 96, "distance_m": 1.0,
                           "same_room": True, "room": "4", "reach": True, "phone": None, "spot": None,
                           "level": 0, "on_lot": True, "acts_cut": 0,
                           "refusals": [{"text_key": "1" * 40, "reason_key": "2" * 40} for _ in range(8)],
                           "acts": [{"guid64": str(9000 + k), "name": "n" * 128, "text_key": "1" * 20,
                                     "variant": None} for k in range(8)]}
                          for i in range(512)]
        rows = self.menu.parts(big)
        for row in rows:
            self.assertLessEqual(self.menu._part_bytes(row), self.menu.PART_BYTES_MAX)
        self.assertLessEqual(len(rows), self.probe.schema.MENU_MAX_PARTS)


class OnLotTests(MenuW12Base):
    def test_each_object_says_whether_it_is_on_her_lot(self):
        off = self.far_thing(FAR, [_act("far_one", FAR_GUID)])
        self.things = [self.near_thing(NEAR, 2.0, [_act("read_book", int(GUID))]), off]
        self.finish(100.0)
        final = self.written()[-1]
        self.assertIs(self.object_by_id(final, NEAR)["on_lot"], True)
        self.assertIs(self.object_by_id(final, FAR)["on_lot"], False)


class SpotStageTests(MenuW12Base):
    def test_the_spot_stages_count_how_far_each_spot_got(self):
        original = self.probe.e2_actuator.standable_spot
        self.addCleanup(setattr, self.probe.e2_actuator, "standable_spot", original)
        self.probe.e2_actuator.standable_spot = lambda sim, start, surface: None
        self.probe.e2_actuator.terrain_object = lambda: object()
        self.things = [self.near_thing(NEAR, 2.0, [_act("read_book", int(GUID))])]
        self.finish(100.0)
        stages = self.written()[-1]["spot_stages"]
        self.assertTrue(stages["terrain"] is True)
        self.assertTrue(stages["placement"] in (True, False))
        self.assertGreaterEqual(stages["anchors"], 1)
        self.assertEqual((stages["found"], stages["room"], stages["target"], stages["go_here"], stages["offers"]),
                         (0, 0, 0, 0, 0))


class FoldTests(MenuW12Base):
    def test_identical_texts_fold_before_the_eight_act_cap(self):
        affordances = [_act("dup_%d" % i, int(GUID) + i, text=0x6500) for i in range(10)]
        for i in range(10):
            self.allowed.add(int(GUID) + i)
        affordances += [_act("one_a", FAR_GUID + 1, text=0x6501), _act("one_b", FAR_GUID + 2, text=0x6502)]
        self.allowed.update({FAR_GUID + 1, FAR_GUID + 2})
        self.things = [self.near_thing(NEAR, 2.0, affordances)]
        self.finish(100.0)
        item = self.object_by_id(self.written()[-1], NEAR)
        self.assertEqual(sorted(act["text_key"] for act in item["acts"]), sorted([str(0x6500), str(0x6501),
                                                                                 str(0x6502)]))
        self.assertEqual(item["acts_cut"], 0)

    def test_acts_cut_counts_the_passing_acts_the_cap_leaves_out(self):
        guids = [FAR_GUID + 30 + i for i in range(11)]
        self.allowed.update(guids)
        self.things = [self.near_thing(NEAR, 2.0, [_act("many_%d" % i, guid, text=0x6600 + i)
                                                   for i, guid in enumerate(guids)])]
        self.finish(100.0)
        item = self.object_by_id(self.written()[-1], NEAR)
        self.assertEqual(len(item["acts"]), self.probe.schema.MENU_MAX_ACTS)
        self.assertEqual(item["acts_cut"], 11 - self.probe.schema.MENU_MAX_ACTS)

    def test_the_candidate_cap_counts_distinct_texts(self):
        self.assertEqual(self.probe.act_menu.CANDIDATE_ACTS, 16)
        guids = [FAR_GUID + 60 + i for i in range(35)]
        self.allowed.update(guids)
        affordances = [_act("same_%d" % i, guids[i], text=0x6700) for i in range(20)]
        affordances += [_act("unique_%d" % i, guids[20 + i], text=0x6710 + i) for i in range(15)]
        self.things = [self.near_thing(NEAR, 2.0, affordances)]
        self.finish(100.0)
        item = self.object_by_id(self.written()[-1], NEAR)
        texts = set(act["text_key"] for act in item["acts"])
        self.assertIn(str(0x6700), texts)
        self.assertEqual(len(texts), self.probe.schema.MENU_MAX_ACTS)  # the 8-act cap, after the fold
        self.assertEqual(item["acts_cut"], 16 - self.probe.schema.MENU_MAX_ACTS)  # 16 distinct texts, 8 shown


class _Text(object):
    def __init__(self, key):
        self.hash = key


class _Choice(object):
    """An AffordanceObjectPair as a picker yields it (invented): its proxy affordance, its kwargs, its name key,
    and the test and execute the game runs for a pick. A refusal key makes its test fail."""

    def __init__(self, label, text_key, guid, log, fail_key=None):
        self.affordance = type(label, (object,), {"guid64": guid, "allow_user_directed": True})
        self.text_key = text_key
        self.fail_key = fail_key
        self.log = log
        self.interaction_parameters = {"pick": label}
        self.count = 0

    def name(self, context):
        return None if self.text_key is None else _Text(self.text_key)

    def test(self, context, skip_safe_tests=False):
        if self.fail_key is not None:
            refusal = acts_refusal(self.fail_key)
            return refusal
        return True

    def test_and_execute(self, context):
        result = self.test(context)
        if not result:
            return result
        self.log.append(self.affordance.__name__)
        self.count += 1
        return types.SimpleNamespace(interaction=_Interaction(780 + self.count), __bool__=lambda: True)


def acts_refusal(key):
    return _Refused(key)


def _pie_affordance(choices_now, guid=PIE_GUID, name="fridge_GrabSnack_PieMenu"):
    return type(name, (object,), {
        "guid64": guid, "allow_user_directed": True,
        "potential_interactions": staticmethod(lambda target, context: iter(list(choices_now))),
    })


PIE_LOG = []
SNACK_MILK = _Choice("fridge_Snack_Milk", 0x6801, 9101, PIE_LOG)
SNACK_JUICE = _Choice("fridge_Snack_Juice", 0x6802, 9102, PIE_LOG)
SNACK_COOKIE = _Choice("fridge_Snack_Cookie", 0x6803, 9103, PIE_LOG)


class PieTests(MenuW12Base):
    def setUp(self):
        super().setUp()
        del PIE_LOG[:]
        self.choices = [SNACK_MILK, SNACK_JUICE, SNACK_COOKIE]
        self.pie = _pie_affordance(self.choices)
        self.things = [self.near_thing(FRIDGE, 2.0, [self.pie])]
        self.base.objects[str(FRIDGE)] = self.things[0]

    def dispatch(self, variant, act_id=ACT):
        connection = self.probe._InboxReply("helper")
        ok = self.probe._inbox_dispatch({"command": "act", "args": {
            "act_id": act_id, "object_id": str(FRIDGE), "guid64": str(PIE_GUID), "variant": variant}}, connection)
        return ok, connection

    def test_a_pie_act_is_offered_as_one_entry_per_choice_with_its_own_name(self):
        self.finish(100.0)
        item = self.object_by_id(self.written()[-1], FRIDGE)
        self.assertEqual([(act["variant"], act["name"], act["guid64"], act["text_key"]) for act in item["acts"]],
                         [(0, "fridge_Snack_Milk", str(PIE_GUID), str(0x6801)),
                          (1, "fridge_Snack_Juice", str(PIE_GUID), str(0x6802)),
                          (2, "fridge_Snack_Cookie", str(PIE_GUID), str(0x6803))])
        self.assertNotIn("fridge_GrabSnack_PieMenu", [act["name"] for act in item["acts"]])

    def test_a_pushed_variant_runs_its_own_pair_and_matches_its_choice_by_name_key(self):
        self.finish(100.0)
        ok, connection = self.dispatch(2)
        self.assertTrue(ok)
        self.assertTrue(connection.lines[-1].startswith("ACT_PUSHED " + ACT), connection.lines)
        self.assertEqual(PIE_LOG, ["fridge_Snack_Cookie"])
        self.assertEqual(self.base.pushes, [], "a pie choice carries its own kwargs, so the sim push is not used")

    def test_a_variant_whose_choice_is_gone_is_refused_and_nothing_is_run(self):
        self.finish(100.0)
        self.choices[:] = [SNACK_MILK, SNACK_JUICE]
        ok, connection = self.dispatch(2)
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT VARIANT_GONE")
        self.assertEqual(PIE_LOG, [])

    def test_a_variant_the_published_menu_never_held_is_refused(self):
        self.finish(100.0)
        ok, connection = self.dispatch(7)
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT VARIANT_GONE")

    def test_a_malformed_variant_is_refused_before_anything_else(self):
        self.finish(100.0)
        for index, bad in enumerate((True, "2", -1, 1000)):
            ok, connection = self.dispatch(bad, act_id="%032x" % (0xc0de + index))
            self.assertFalse(ok)
            self.assertEqual(connection.lines[-1], "ACT_REJECT BAD_VARIANT")
        self.assertEqual(PIE_LOG, [])

    def test_a_choice_the_game_refuses_at_the_push_is_refused_with_its_reason_and_not_run(self):
        self.finish(100.0)
        # The choice passed the menu test and refuses now: the push finds it again and runs its own test.
        self.choices[1] = _Choice("fridge_Snack_Juice", 0x6802, 9102, PIE_LOG, fail_key=0x7201)
        ok, connection = self.dispatch(1, act_id="d" * 32)
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT GAME_REFUSED")
        self.assertEqual(PIE_LOG, [])

    def test_the_pie_itself_is_still_not_an_act_and_a_choice_without_a_name_is_not_offered(self):
        self.assertEqual(self.probe.e2_actuator.act_excluded(self.pie, False), "pie_picker")
        self.choices[:] = [SNACK_MILK, _Choice("", None, 9199, PIE_LOG)]
        self.finish(100.0)
        item = self.object_by_id(self.written()[-1], FRIDGE)
        self.assertEqual([act["variant"] for act in item["acts"]], [0])


class ChoiceReadTests(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.e2a = self.base.probe.e2_actuator
        self.log = []

    def test_the_choices_are_read_defensively_and_capped(self):
        class Broken(object):
            def potential_interactions(self, target, context):
                raise RuntimeError("the game refused to enumerate")

        self.assertEqual(self.e2a.pie_choices(Broken(), None, None), [])
        many = [_Choice("c_%d" % i, 0x6900 + i, 9300 + i, self.log) for i in range(40)]
        pie = _pie_affordance(many, guid=9299, name="fridge_Many_PieMenu")
        self.assertEqual(len(self.e2a.pie_choices(pie, None, None)), self.e2a.PIE_CHOICES_MAX)

    def test_a_choice_is_matched_by_its_display_key_then_its_name(self):
        named = _Choice("cookie_pick", 0x6A00, 9400, self.log)
        bare = _Choice("bare_pick", None, 9401, self.log)
        self.assertEqual(self.e2a.choice_names(named, None), (str(0x6A00), str(0x6A00)))
        self.assertEqual(self.e2a.choice_names(bare, None), (None, "bare_pick"))
        pie = _pie_affordance([named, bare], guid=9402)
        self.assertIs(self.e2a.variant_choice(pie, None, None, "bare_pick"), bare)
        self.assertIsNone(self.e2a.variant_choice(pie, None, None, "missing"))


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.schema = self.base.probe.schema

    def _row(self, objects, **extra):
        payload = {"menu_rev": 1, "room": "4", "tested": 1, "cached": 0, "refused": 0, "build_ms": 1.0,
                   "part": 0, "parts": 1, "refused_phone": None, "excluded_phone": None, "objects": objects,
                   "dropped": None, "spot_stages": None}
        payload.update(extra)
        return self.schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1,
                                       monotonic_ns=1, e2=payload)

    def _object(self, acts, **extra):
        item = {"object_id": "7", "definition_id": None, "class": "chair", "distance_m": 1.0, "same_room": True,
                "room": "4", "reach": True, "acts": acts, "phone": None, "spot": None, "level": 0,
                "on_lot": True, "acts_cut": 0, "refusals": None}
        item.update(extra)
        return item

    def test_the_new_keys_validate(self):
        act = {"guid64": "9000", "name": "n", "text_key": "1", "variant": 2}
        row = self._row([self._object([act], acts_cut=3, refusals=[{"text_key": "1", "reason_key": "2"}])],
                        dropped={"objects": 4, "rooms": ["5", "6"]},
                        spot_stages={"anchors": 3, "placement": True, "terrain": True, "offers": 0})
        self.schema.validate_record(row)

    def test_older_rows_without_the_new_keys_still_validate(self):
        older = self._object([{"guid64": "9000", "name": "n", "text_key": None}])
        del older["on_lot"], older["acts_cut"], older["refusals"]
        payload = self._row([older]).copy()
        del payload["e2"]["dropped"], payload["e2"]["spot_stages"]
        self.schema.validate_record(payload)

    def test_an_object_of_refusals_alone_is_allowed_but_no_acts_and_no_refusals_is_not(self):
        self.schema.validate_record(self._row([self._object([], refusals=[{"text_key": "1", "reason_key": None}])]))
        with self.assertRaises(Exception):
            self.schema.validate_record(self._row([self._object([])]))

    def test_nine_refusals_or_a_variant_out_of_range_are_refused(self):
        nine = [{"text_key": str(i), "reason_key": None} for i in range(9)]
        with self.assertRaises(Exception):
            self.schema.validate_record(self._row([self._object([], refusals=nine)]))
        bad_variant = {"guid64": "9000", "name": "n", "text_key": None, "variant": 1000}
        with self.assertRaises(Exception):
            self.schema.validate_record(self._row([self._object([bad_variant])]))

    def test_a_change_of_variant_or_refusals_is_a_different_menu(self):
        act = {"guid64": "9000", "name": "n", "text_key": None, "variant": 0}
        left = {"menu_rev": 1, "room": "4", "objects": [self._object([act])]}
        right = {"menu_rev": 1, "room": "4", "objects": [self._object([dict(act, variant=1)])],
                 "refused_phone": None, "excluded_phone": None}
        left.update({"refused_phone": None, "excluded_phone": None})
        self.assertFalse(self.base.probe.act_menu.same_menu(left, right))


class RequestTests(MenuW12Base):
    def test_the_request_is_a_function_of_the_probe(self):
        self.assertTrue(callable(self.probe.request_menu_near))
        self.probe.request_menu_near()
        self.probe.request_menu_near()
        self.assertTrue(self.probe._MENU_NEAR_REQUESTED)
