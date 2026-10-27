"""2.37.0 (W10 P2, P3): her menu is quick and complete. A far candidate (not in her room, not her phone, not a
Sim) keeps its test outcome for FAR_CACHE_S seconds; the first build in a zone writes its near part as soon as the
far part starts; her phone is not capped at the object cap; the phone acts the guard excludes are named."""
import types
import unittest

import test_2160_act as acts
import test_e2
from test_2160_act import GUID

SIM_ID = 9101  # invented id for her Sim


class FakeClock(object):
    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now


def job(object_id, guid, same_room=False, person=False, phone=False, reason_key=None):
    value = {"object_id": object_id, "definition_id": "7", "class": "object_thing", "distance_m": 3.0,
             "same_room": same_room, "room": "5", "guid64": guid, "name": "act_%s" % guid, "text_key": None,
             "person": person}
    if phone:
        value["phone"] = True
    return value


class FarCacheUnitTests(unittest.TestCase):
    def setUp(self):
        test_e2._load_pure()
        from ashley_e1 import act_menu, schema
        self.menu = act_menu
        self.schema = schema
        self.clock = FakeClock(100.0)

    def build(self, jobs, runner, cache=None, **extra):
        return self.menu.MenuBuild(jobs, runner, budget_ms=1e9, max_per_chunk=10000, far=cache, **extra)

    def run_all(self, build):
        while not build.done:
            build.step()
        return build

    def test_the_far_cache_keeps_an_outcome_for_120_seconds_then_lets_it_go(self):
        self.assertEqual(self.menu.FAR_CACHE_S, 120.0)
        cache = self.menu.FarCache(clock=self.clock)
        cache.put(job("9", "77"), True)
        self.clock.now = 219.0
        self.assertEqual(cache.get(job("9", "77"))["ok"], True)
        self.clock.now = 220.0
        self.assertIsNone(cache.get(job("9", "77")))
        cache.put(job("9", "77"), False)
        cache.clear()
        self.assertIsNone(cache.get(job("9", "77")))

    def test_only_far_candidates_are_cacheable(self):
        self.assertTrue(self.menu.is_far(job("1", "7")))
        self.assertFalse(self.menu.is_far(job("1", "7", same_room=True)))
        self.assertFalse(self.menu.is_far(job("1", "7", phone=True)))
        self.assertFalse(self.menu.is_far(job("1", "7", person=True)))

    def test_a_far_candidate_is_not_tested_again_in_the_next_build_and_counts_as_cached(self):
        cache = self.menu.FarCache(clock=self.clock)
        tested = []

        def runner(candidate):
            tested.append(candidate["object_id"])
            return True
        first = self.run_all(self.build([job("2", "7")], runner, cache))
        self.clock.now = 150.0
        jobs = [job("2", "7")]
        second = self.run_all(self.build(jobs, runner, cache))
        self.assertEqual(tested, ["2"])
        self.assertEqual((first.tested, first.cached), (1, 0))
        self.assertEqual((second.tested, second.cached), (0, 1))
        self.assertEqual([kept["object_id"] for kept in second._kept], ["2"])

    def test_a_near_candidate_is_tested_in_every_build(self):
        cache = self.menu.FarCache(clock=self.clock)
        tested = []

        def runner(candidate):
            tested.append(candidate["object_id"])
            return True
        self.run_all(self.build([job("3", "8", same_room=True)], runner, cache))
        self.clock.now = 150.0
        second = self.run_all(self.build([job("3", "8", same_room=True)], runner, cache))
        self.assertEqual(tested, ["3", "3"])
        self.assertEqual((second.tested, second.cached), (1, 0))

    def test_a_cached_refusal_stays_refused_with_its_reason_and_is_counted(self):
        cache = self.menu.FarCache(clock=self.clock)

        def runner(candidate):
            candidate["refused"], candidate["reason_key"] = True, "KEY_NO_WAY"
            return False
        self.run_all(self.build([job("4", "9")], runner, cache))
        self.clock.now = 150.0
        second = self.run_all(self.build([job("4", "9")], lambda candidate: self.fail("tested"), cache))
        self.assertEqual((second.tested, second.cached, second.refused), (0, 1, 1))
        payload = second.payload(1, "5")
        # 2.39.0 (W12 C4): a near object whose acts were all refused is listed with the game's reason; a far one is not.
        self.assertEqual([(item["acts"], [r["reason_key"] for r in item["refusals"]]) for item in payload["objects"]],
                         [([], ["KEY_NO_WAY"])])

    def test_a_candidate_whose_test_raised_is_not_cached(self):
        cache = self.menu.FarCache(clock=self.clock)

        def broken(candidate):
            raise RuntimeError("game")
        self.run_all(self.build([job("5", "10")], broken, cache))
        tested = []
        self.run_all(self.build([job("5", "10")], lambda candidate: tested.append(1) or True, cache))
        self.assertEqual(tested, [1])

    def test_the_near_part_is_handed_over_once_when_the_far_part_starts(self):
        handed = []

        def on_near(build):
            handed.append([item["object_id"] for item in build.payload(1, "4")["objects"]])
        far = job("2", "12")
        far["distance_m"] = 9.0  # R3 (PROBE3-3): a candidate 4 m away or less is near, so the far one is 9 m away
        jobs = [job("1", "11", same_room=True), far, job("3", "13")]
        self.run_all(self.build(jobs, lambda candidate: True, on_near=on_near))
        self.assertEqual(handed, [["1"]])

    def test_no_near_part_is_handed_over_when_there_is_no_far_candidate(self):
        handed = []
        self.run_all(self.build([job("1", "11", same_room=True)], lambda candidate: True,
                                on_near=lambda build: handed.append(build)))
        self.assertEqual(handed, [])

    def test_the_payload_counts_cached_and_names_excluded_phone_acts_on_part_zero_only(self):
        excluded = [{"name": "phone_Thing", "why": "travel"}]
        build = self.run_all(self.build([job("1", "11")], lambda candidate: True, excluded_phone=excluded))
        payload = build.payload(3, "4")
        self.assertEqual((payload["cached"], payload["tested"]), (0, 1))
        self.assertEqual(payload["excluded_phone"], excluded)
        parts = self.menu.parts(dict(payload, objects=payload["objects"] * 17))
        self.assertEqual(len(parts), 2)
        self.assertEqual([part["excluded_phone"] for part in parts], [excluded, None])
        self.assertEqual([part["cached"] for part in parts], [0, 0])

    def test_excluded_phone_names_are_kept_up_to_the_cap_with_their_reason(self):
        self.assertEqual(self.schema.MENU_MAX_EXCLUDED_PHONE, 64)
        kept = []
        for number in range(70):
            self.menu.note_excluded(kept, "phone_act_%d" % number, "travel")
        self.assertEqual(len(kept), 64)
        self.assertEqual(kept[0], {"name": "phone_act_0", "why": "travel"})
        self.menu.note_excluded(kept, "x" * 200, "hidden")
        self.assertEqual(len(kept), 64)

    def test_the_phone_candidate_cap_and_the_refused_phone_cap(self):
        self.assertEqual(self.menu.PHONE_CANDIDATES, 96)
        self.assertEqual(self.schema.MENU_MAX_REFUSED_PHONE, 64)
        self.assertEqual(self.menu.CANDIDATE_ACTS, 16)

    def test_rows_with_cached_and_excluded_phone_validate_and_older_rows_still_do(self):
        payload = {"menu_rev": 1, "room": None, "tested": 1, "cached": 2, "refused": 0, "build_ms": 1.0,
                   "part": 0, "parts": 1, "refused_phone": [], "excluded_phone": [{"name": "n", "why": "pie_picker"}],
                   "objects": []}
        self.schema.validate_record(self.schema.make_record(
            "act_menu", telemetry_session_id="s", wall_timestamp_ms=1, monotonic_ns=1, e2=payload))
        older = dict(payload)
        del older["cached"], older["excluded_phone"]
        row = self.schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1, monotonic_ns=1,
                                      e2=older)
        self.schema.validate_record(row)
        self.assertIsNone(row["e2"]["excluded_phone"])
        self.assertIsNone(row["e2"]["cached"])

    def test_a_bad_excluded_phone_shape_is_refused(self):
        payload = {"menu_rev": 1, "room": None, "tested": 0, "cached": 0, "refused": 0, "build_ms": 1.0,
                   "part": 0, "parts": 1, "refused_phone": None, "excluded_phone": [{"name": "n"}], "objects": []}
        with self.assertRaises(Exception):
            self.schema.validate_record(self.schema.make_record(
                "act_menu", telemetry_session_id="s", wall_timestamp_ms=1, monotonic_ns=1, e2=payload))

    def _menu_object(self, phone, count):
        # 2.39.0 (W12): the object and act keys the writer always sends (on_lot, acts_cut, refusals; variant).
        return {"object_id": "7", "definition_id": None, "class": "phone" if phone else "chair", "distance_m": None,
                "same_room": None, "room": None, "reach": None, "phone": True if phone else None, "spot": None,
                "level": None, "on_lot": None, "acts_cut": 0, "refusals": None,
                "acts": [{"guid64": str(9000 + i), "name": "act_%d" % i, "text_key": None, "variant": None}
                         for i in range(count)]}

    def _validate_menu(self, objects):
        payload = {"menu_rev": 1, "room": None, "tested": 1, "cached": 0, "refused": 0, "build_ms": 1.0,
                   "part": 0, "parts": 1, "refused_phone": [], "excluded_phone": [], "objects": objects}
        self.schema.validate_record(self.schema.make_record(
            "act_menu", telemetry_session_id="s", wall_timestamp_ms=1, monotonic_ns=1, e2=payload))

    def test_her_phone_may_carry_its_own_cap_of_acts_and_another_object_only_eight(self):
        self._validate_menu([self._menu_object(True, self.schema.MENU_MAX_PHONE_ACTS)])
        with self.assertRaises(Exception):
            self._validate_menu([self._menu_object(True, self.schema.MENU_MAX_PHONE_ACTS + 1)])
        with self.assertRaises(Exception):
            self._validate_menu([self._menu_object(False, self.schema.MENU_MAX_ACTS + 1)])

    def test_a_part_too_large_for_its_record_sheds_phone_diagnostics_not_objects(self):
        big = "x" * 128
        objects = [dict(self._menu_object(False, 8), object_id=str(i)) for i in range(15)]
        for item in objects:
            for act in item["acts"]:
                act["name"] = big
        objects.append(self._menu_object(True, self.schema.MENU_MAX_PHONE_ACTS))
        payload = {"menu_rev": 1, "room": None, "tested": 1, "cached": 0, "refused": 0, "build_ms": 1.0,
                   "refused_phone": [{"name": big, "reason_key": "0x" + "f" * 60} for _ in range(64)],
                   "excluded_phone": [{"name": big, "why": "travel"} for _ in range(64)], "objects": objects}
        first = self.menu.parts(payload)[0]
        self.assertEqual(len(first["objects"]), 16)
        self.assertLess(len(first["excluded_phone"]), 64)
        self.assertLessEqual(self.menu._part_bytes(first), self.menu.PART_BYTES_MAX)
        self.schema.validate_record(self.schema.make_record(
            "act_menu", telemetry_session_id="s", wall_timestamp_ms=1, monotonic_ns=1, e2=first))

    def test_a_small_part_keeps_all_its_phone_diagnostics(self):
        payload = {"menu_rev": 1, "room": None, "tested": 1, "cached": 0, "refused": 0, "build_ms": 1.0,
                   "refused_phone": [{"name": "a", "reason_key": None}] * 64,
                   "excluded_phone": [{"name": "b", "why": "hidden"}] * 64, "objects": []}
        first = self.menu.parts(payload)[0]
        self.assertEqual((len(first["refused_phone"]), len(first["excluded_phone"])), (64, 64))

    def test_the_probe_version_is_2_37_1_and_the_schema_is_19(self):
        self.assertEqual(self.schema.PROBE_VERSION, "2.41.4")
        self.assertEqual(self.schema.OBSERVATION_SCHEMA_VERSION, 21)
        self.assertIn(18, self.schema.ACCEPTED_SCHEMA_VERSIONS)
        self.assertIn(19, self.schema.ACCEPTED_SCHEMA_VERSIONS)


class W10MenuTests(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.probe = self.base.probe
        self.probe._MENU_FAR.clear()
        self.probe._menu_reset()
        self.allowed = {int(GUID)}
        self.tested = []

        def test_super(affordance, target, context):
            self.tested.append(str(getattr(target, "id", None)))
            return affordance.guid64 in self.allowed
        self.base.sim.test_super_affordance = test_super
        self.things = [acts._Thing(11, 2.0, [acts.ReadBook]), acts._Thing(12, 30.0, [acts.ReadBook])]
        self.probe._lot_snapshot = lambda: (list(self.things), None)
        self.rooms = {11: "4", 12: "5"}
        room_of = self.probe.observers._room
        self.addCleanup(setattr, self.probe.observers, "_room", room_of)
        self.probe.observers._room = lambda obj, position: self.rooms.get(getattr(obj, "id", None))
        self.clock = {"s": 100.0}
        now_s = self.probe._now_s
        self.addCleanup(setattr, self.probe, "_now_s", now_s)
        self.probe._now_s = lambda: self.clock["s"]
        self.zone = {"current": object()}
        current_zone = self.probe._current_zone
        self.addCleanup(setattr, self.probe, "_current_zone", current_zone)
        self.probe._current_zone = lambda: self.zone["current"]
        self.row = {"event_kind": "presence_snapshot",
                    "zone": {"position": {"x": 0.0, "y": 0.0, "z": 0.0, "level": 0}, "room": "4"}}
        self.base.LedgerWriter.records = [self.base.continuing()[0]]
        self.assertTrue(self.probe._cmd_arm("HOME"))
        self.assertTrue(self.probe._cmd_start())
        self.base.tick()
        # The sampler's own ticks may have built a menu already: each test starts from no build and no menu.
        self.probe._menu_reset()
        self.probe._MENU_FAR.clear()
        self.tested[:] = []
        self.baseline = len(self.base.e2("act_menu"))

    def tearDown(self):
        writer = self.base.LedgerWriter.instances[-1] if self.base.LedgerWriter.instances else None
        if writer is not None:
            writer.finish()

    def build_at(self, seconds):
        """Starts and finishes a build at this time (a build starts when none is running and REBUILD_S passed)."""
        self.clock["s"] = seconds
        for _ in range(4):
            self.probe._menu_tick(self.row)

    def menus(self):
        return self.base.e2("act_menu")[self.baseline:]

    def phone(self, affordances):
        sim = self.base.sim
        sim.id = SIM_ID
        sim._phone_affordances = affordances
        return sim

    def test_her_phone_offers_past_sixteen_are_all_candidates(self):
        many = [type("PhoneW10Act%d" % i, (object,), {"guid64": 8000 + i, "allow_user_directed": True})
                for i in range(20)]
        self.phone(many)
        self.things = []
        jobs, _room = self.probe._menu_jobs(self.row)
        phone = [candidate for candidate in jobs if candidate.get("phone") is True]
        self.assertEqual(len(phone), 20)

    def test_a_phone_act_the_guard_excludes_is_named_with_why_before_the_test(self):
        def named(name, **attributes):
            values = {"guid64": 8100, "allow_user_directed": True}
            values.update(attributes)
            return type(name, (object,), values)
        self.phone([named("PhoneW10Ring"),
                    named("PhoneW10PieMenu"),
                    named("PhoneW10VisitLot"),
                    named("phone_Cheat_CallPolice", guid64=8101),
                    named("PhoneW10Idle", allow_user_directed=False, guid64=8102),
                    named("PhoneW10Tidy", cheat=True, guid64=8103)])
        self.things = []
        self.allowed = {8100, 8101, 8102, 8103}
        jobs, room = self.probe._menu_jobs(self.row)
        build = self.probe.act_menu.MenuBuild(jobs, self.probe._menu_test, budget_ms=1e9, max_per_chunk=10000,
                                              spots=jobs.spots, excluded_phone=jobs.excluded_phone)
        while not build.done:
            build.step()
        payload = build.payload(1, room)
        self.assertEqual(payload["excluded_phone"], [
            {"name": "PhoneW10PieMenu", "why": "pie_picker"},
            {"name": "PhoneW10VisitLot", "why": "travel"},
            {"name": "phone_Cheat_CallPolice", "why": "deny_name"},
            {"name": "PhoneW10Idle", "why": "not_user_directed"},
            {"name": "PhoneW10Tidy", "why": "hidden"}])
        self.assertEqual([act["name"] for act in payload["objects"][0]["acts"]], ["PhoneW10Ring"])

    def test_the_first_build_in_a_zone_writes_its_near_part_and_then_the_whole_menu(self):
        self.build_at(100.0)
        menus = self.menus()
        self.assertEqual([[item["object_id"] for item in menu["objects"]] for menu in menus], [["11"], ["11", "12"]])
        self.assertEqual([menu["menu_rev"] for menu in menus], [1, 1])
        self.assertEqual([(menu["part"], menu["parts"]) for menu in menus], [(0, 1), (0, 1)])
        for row in self.base.rows("act_menu"):
            self.probe.schema.validate_record(row)

    def test_a_first_build_with_no_near_object_writes_only_the_whole_menu(self):
        self.rooms = {}  # no object in her room: the near part is empty, so nothing is written before the menu
        self.build_at(100.0)
        menus = self.menus()
        # R3 (PROBE3-3): the object 2 m away is near, so the near part holds it; the whole menu follows.
        self.assertEqual([[item["object_id"] for item in menu["objects"]] for menu in menus], [["11"], ["11", "12"]])
        self.assertEqual([menu.get("near") for menu in menus], [True, None])

    def test_a_later_build_in_the_same_zone_writes_once_when_it_finishes(self):
        self.build_at(100.0)
        self.allowed = set()  # her near act is refused now; the far one is cached for 120 s
        self.build_at(125.0)
        menus = self.menus()
        # 2.39.0 (W12 C1): the later build writes its near part as its far part starts, then its whole menu.
        self.assertEqual(len(menus), 4)
        # 2.39.0 (W12 C4): her near object, all acts refused now, is listed with the game's reasons as well.
        self.assertEqual((menus[3]["menu_rev"], [item["object_id"] for item in menus[3]["objects"]]), (2, ["11", "12"]))
        self.assertEqual(menus[3]["cached"], 1)

    def test_a_far_candidate_is_not_tested_again_within_120_seconds_and_a_near_one_always_is(self):
        self.build_at(100.0)
        self.assertEqual(self.tested.count("12"), 1)
        self.assertEqual(self.tested.count("11"), 1)
        self.build_at(150.0)
        self.assertEqual(self.tested.count("12"), 1)
        self.assertEqual(self.tested.count("11"), 2)
        self.build_at(230.0)
        self.assertEqual(self.tested.count("12"), 2)

    def test_a_zone_change_clears_the_far_cache(self):
        self.build_at(100.0)
        self.zone["current"] = object()
        self.build_at(150.0)
        self.assertEqual(self.tested.count("12"), 2)
        self.assertEqual(self.tested.count("11"), 2)


class FarKindTests(unittest.TestCase):
    """2.38.0 (W11 P3): a far candidate's outcome is also kept by (definition id, guid64), so identical far objects
    share one test per kind of act; reach is still asked per object; near candidates are never shared."""

    def setUp(self):
        test_e2._load_pure()
        from ashley_e1 import act_menu
        self.menu = act_menu
        self.clock = FakeClock(100.0)

    build = FarCacheUnitTests.build
    run_all = FarCacheUnitTests.run_all

    def kind_job(self, object_id, guid, definition=7, same_room=False):
        value = job(object_id, guid, same_room=same_room)
        value["definition_id"] = definition
        return value

    def test_fifty_identical_far_objects_with_three_acts_cost_three_real_tests(self):
        cache = self.menu.FarCache(clock=self.clock)
        tested = []
        jobs = [self.kind_job(str(number), guid) for number in range(1, 51) for guid in ("71", "72", "73")]

        def runner(candidate):
            tested.append((candidate["definition_id"], candidate["guid64"]))
            return True
        build = self.run_all(self.build(jobs, runner, cache))
        self.assertEqual(sorted(tested), [(7, "71"), (7, "72"), (7, "73")])
        self.assertEqual((build.tested, build.cached), (3, 147))
        self.assertEqual(len(build._kept), 150)

    def test_a_definition_hit_in_a_later_build_is_not_tested_again(self):
        cache = self.menu.FarCache(clock=self.clock)
        self.run_all(self.build([self.kind_job("1", "71")], lambda candidate: True, cache))
        self.clock.now = 150.0
        second = self.run_all(self.build([self.kind_job("2", "71")], lambda candidate: self.fail("tested"), cache))
        self.assertEqual((second.tested, second.cached), (0, 1))
        self.assertEqual([kept["object_id"] for kept in second._kept], ["2"])

    def test_a_definition_outcome_lapses_with_the_same_120_seconds(self):
        cache = self.menu.FarCache(clock=self.clock)
        cache.put(self.kind_job("1", "71"), True)
        self.clock.now = 219.0
        self.assertIsNotNone(cache.get(self.kind_job("2", "71")))
        self.clock.now = 220.0
        self.assertIsNone(cache.get(self.kind_job("2", "71")))

    def test_another_definition_or_guid_is_tested_on_its_own(self):
        cache = self.menu.FarCache(clock=self.clock)
        tested = []
        jobs = [self.kind_job("1", "71", definition=7), self.kind_job("2", "71", definition=8),
                self.kind_job("3", "72", definition=7)]
        self.run_all(self.build(jobs, lambda candidate: tested.append(candidate["object_id"]) or True, cache))
        self.assertEqual(tested, ["1", "2", "3"])

    def test_an_object_without_a_definition_is_only_kept_by_its_own_id(self):
        cache = self.menu.FarCache(clock=self.clock)
        tested = []
        jobs = [self.kind_job("1", "71", definition=None), self.kind_job("2", "71", definition=None)]
        self.run_all(self.build(jobs, lambda candidate: tested.append(candidate["object_id"]) or True, cache))
        self.assertEqual(tested, ["1", "2"])

    def test_near_objects_with_one_definition_are_each_tested(self):
        cache = self.menu.FarCache(clock=self.clock)
        tested = []
        jobs = [self.kind_job("1", "71", same_room=True), self.kind_job("2", "71", same_room=True)]
        build = self.run_all(self.build(jobs, lambda candidate: tested.append(candidate["object_id"]) or True, cache))
        self.assertEqual(tested, ["1", "2"])
        self.assertEqual((build.tested, build.cached), (2, 0))

    def test_reach_is_asked_for_each_object_even_when_its_outcome_is_cached(self):
        cache = self.menu.FarCache(clock=self.clock)
        asked = []

        def reach(candidate):
            asked.append(candidate["object_id"])
            candidate["reach"] = "R" + candidate["object_id"]
        def runner(candidate):
            reach(candidate)  # the probe's runner asks reach first, then the game's test
            return True
        self.run_all(self.build([self.kind_job("1", "71")], runner, cache, reach=reach))
        self.clock.now = 150.0
        second = self.run_all(self.build([self.kind_job("2", "71")], lambda candidate: self.fail("tested"),
                                         cache, reach=reach))
        self.assertEqual(asked, ["1", "2"])
        payload = second.payload(1, "5")
        self.assertEqual([(item["object_id"], item["reach"]) for item in payload["objects"]], [("2", "R2")])

    def test_a_cached_refusal_by_definition_stays_refused_for_the_next_object(self):
        cache = self.menu.FarCache(clock=self.clock)

        def runner(candidate):
            candidate["refused"], candidate["reason_key"] = True, "KEY_NO_WAY"
            return False
        self.run_all(self.build([self.kind_job("1", "71")], runner, cache))
        # 2.39.0 (W12 C3): a refusal is kept by its object only; the identical object is tested again (one occupied
        # object does not hide its kin). Only a pass is shared by definition.
        second = self.run_all(self.build([self.kind_job("2", "71")], lambda candidate: True, cache))
        self.assertEqual((second.tested, second.cached, second.refused), (1, 0, 0))


if __name__ == "__main__":
    unittest.main()
