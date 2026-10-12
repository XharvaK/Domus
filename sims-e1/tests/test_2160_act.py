"""2.16.0 (8f): Ashley acts. The menu of what she can do near her body, and her chosen
action pushed exactly as named, once, with ACCEPTED written before the push."""
import types
import unittest

import test_e2
from test_e2 import CHAIR, PIE

GUID = "4242"
ACT = "a" * 32


class ReadBook(object):
    guid64 = int(GUID)
    allow_user_directed = True


class AutonomousOnly(object):
    guid64 = int(GUID)
    allow_user_directed = False


class Greet(object):
    guid64 = int(GUID)
    is_social = True
    allow_user_directed = True


class Propose(object):
    __name__ = "social_Romance_Propose"
    guid64 = 4345
    is_social = True
    allow_user_directed = True


class PowerConsumption(object):
    guid64 = 4343
    allow_user_directed = True
    cheat = True


class DebugOnly(object):
    guid64 = 4344
    allow_user_directed = True
    debug = True


class _Offer:
    def __init__(self, object_id, affordances):
        self.id = int(object_id)
        self._affordances = affordances

    def super_affordances(self, context=None):
        for item in self._affordances:
            yield item


class ActCommandTests(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.probe = self.base.probe
        self.base.objects[CHAIR] = _Offer(CHAIR, [ReadBook])
        self.tested = []
        self.allowed = True

        def test_super_affordance(affordance, target, context):
            self.tested.append((affordance.guid64, target.id))
            return self.allowed

        self.base.sim.test_super_affordance = test_super_affordance

    def tearDown(self):
        writer = self.base.LedgerWriter.instances[-1] if self.base.LedgerWriter.instances else None
        if writer is not None:
            writer.finish()

    def ready(self, name="HOME"):
        self.base.LedgerWriter.records = [self.base.continuing()[0]]
        self.assertTrue(self.probe._cmd_arm(name))
        self.assertTrue(self.probe._cmd_start())
        self.base.tick()

    def act(self, act_id=ACT, object_id=CHAIR, guid64=GUID):
        connection = self.probe._InboxReply("helper")
        ok = self.probe._inbox_dispatch(
            {"command": "act", "args": {"act_id": act_id, "object_id": object_id, "guid64": guid64}},
            connection)
        return ok, connection

    def events(self):
        return self.base.e2("act_event")

    def test_her_choice_is_pushed_exactly_and_its_end_is_recorded(self):
        self.ready()
        ok, connection = self.act()
        self.assertTrue(ok)
        self.assertTrue(connection.lines[-1].startswith("ACT_PUSHED " + ACT))
        self.assertEqual([(guid, target) for guid, target, _ in self.base.pushes], [(int(GUID), int(CHAIR))])
        self.assertEqual(self.tested, [(int(GUID), int(CHAIR))])
        phases = [(e["phase"], e["object_id"], e["guid64"], e["tuning_name"]) for e in self.events()]
        self.assertEqual(phases, [("ACCEPTED", CHAIR, GUID, "ReadBook"), ("PUSHED", CHAIR, GUID, "ReadBook")])
        self.assertEqual(self.events()[-1]["interaction_id"], "777")
        interaction = self.base.pushes and None
        del interaction
        for row in self.base.rows("act_event"):
            self.probe.schema.validate_record(row)

    def test_the_finish_is_recorded_with_how_it_ended(self):
        self.ready()
        captured = []
        original = self.base.sim.push_super_affordance

        def capture(affordance, target, context):
            result = original(affordance, target, context)
            captured.append(result.execute_result.interaction)
            return result

        self.base.sim.push_super_affordance = capture
        self.assertTrue(self.act()[0])
        interaction = captured[-1]
        self.assertEqual(len(interaction.callbacks), 1)
        interaction.callbacks[0](interaction)
        last = self.events()[-1]
        self.assertEqual((last["phase"], last["finishing_type"], last["interaction_id"]),
                         ("FINISHED", "FinishingType.NATURAL", "777"))
        self.assertEqual(interaction.cancels, [])

    def test_an_act_id_runs_once(self):
        self.ready()
        self.assertTrue(self.act()[0])
        ok, connection = self.act()
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT DUPLICATE")
        self.assertEqual(len(self.base.pushes), 1)

    def test_each_refusal_is_recorded_and_nothing_is_pushed(self):
        self.ready()
        cases = [
            (dict(guid64="999999"), None, "NOT_OFFERED"),
            (dict(object_id="31337"), None, "NO_OBJECT"),
            ({}, [Greet], "EXCLUDED"),
            ({}, [AutonomousOnly], "NOT_USER_DIRECTED"),
        ]
        for index, (args, offers, code) in enumerate(cases):
            self.base.objects[CHAIR] = _Offer(CHAIR, offers or [ReadBook])
            ok, connection = self.act(act_id="%032x" % (index + 1), **args)
            self.assertFalse(ok, code)
            self.assertEqual(connection.lines[-1], "ACT_REJECT %s" % code)
            self.assertEqual(self.events()[-1]["phase"], "REJECTED")
            self.assertEqual(self.events()[-1]["code"], code)
        self.base.objects[CHAIR] = _Offer(CHAIR, [ReadBook])
        self.allowed = False
        ok, connection = self.act(act_id="%032x" % 99)
        self.assertEqual(connection.lines[-1], "ACT_REJECT GAME_REFUSED")
        self.assertEqual(self.base.pushes, [])
        self.assertNotIn("ACCEPTED", [e["phase"] for e in self.events()])

    def test_a_social_toward_another_sim_is_hers_and_never_toward_a_thing(self):
        # 2.17.0 (live 2026-10-06: the welcome wagon waited at her door, ungreeted).
        self.ready()
        neighbour = _Offer(CHAIR, [Greet])
        neighbour.is_sim = True
        self.base.objects[CHAIR] = neighbour
        ok, connection = self.act(act_id="%032x" % 1)
        self.assertTrue(ok, connection.lines)
        # 2.37.1 (User 2026-10-12): Propose is a judgement name, hers to choose toward a Sim now.
        neighbour._affordances = [Propose]
        ok, connection = self.act(act_id="%032x" % 2, guid64="4345")
        self.assertTrue(ok, connection.lines)
        # A social toward a thing stays out, whatever the social is named.
        self.base.objects[CHAIR] = _Offer(CHAIR, [Greet])
        ok, connection = self.act(act_id="%032x" % 3)
        self.assertEqual(connection.lines[-1], "ACT_REJECT EXCLUDED")
        self.base.objects[CHAIR] = _Offer(CHAIR, [Propose])
        ok, connection = self.act(act_id="%032x" % 4, guid64="4345")
        self.assertEqual(connection.lines[-1], "ACT_REJECT EXCLUDED")

    def test_a_failed_push_is_rejected_after_acceptance(self):
        self.ready()
        self.base.push_ok = False
        ok, connection = self.act()
        self.assertFalse(ok)
        self.assertEqual([e["phase"] for e in self.events()], ["ACCEPTED", "REJECTED"])
        self.assertIn(self.events()[-1]["code"], ("PUSH_REFUSED", "PUSH_FAILED"))

    def test_an_error_after_acceptance_is_unknown_never_rejected(self):
        self.ready()

        def boom(affordance, target, context):
            raise RuntimeError("game")

        self.base.sim.push_super_affordance = boom
        ok, connection = self.act()
        self.assertFalse(ok)
        self.assertEqual([e["phase"] for e in self.events()], ["ACCEPTED", "UNKNOWN"])
        self.assertEqual(self.events()[-1]["code"], "E2_EXCEPTION:RuntimeError")

    def test_busy_or_in_distress_she_may_still_choose(self):
        self.ready()
        self.base.sim.si_state = [types.SimpleNamespace(
            id=9, guid64=1, affordance="x", target=types.SimpleNamespace(id=int(CHAIR)),
            context=types.SimpleNamespace(source=PIE))]
        self.probe.observers.read_motives = lambda *args, **kwargs: [{"id": "bladder", "band": "distress"}]
        self.assertTrue(self.act()[0])

    def test_lab_saves_act_too_and_calibrate_refuses(self):
        self.ready("LAB_E1")
        self.assertTrue(self.act()[0])
        self.probe._cmd_calibrate()
        ok, connection = self.act(act_id="b" * 32)
        self.assertFalse(ok)
        self.assertEqual(connection.code, "CALIBRATE_OBSERVE_ONLY")

    def test_not_sampling_refuses(self):
        self.base.LedgerWriter.records = [self.base.continuing()[0]]
        self.assertTrue(self.probe._cmd_arm("HOME"))
        ok, connection = self.act()
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT NOT_SAMPLING")

    def test_cmdbox_shapes(self):
        from ashley_e1 import cmdbox
        good = {"act_id": ACT, "object_id": CHAIR, "guid64": GUID}
        base = {"v": 1, "id": "c" * 32, "issued_at_ms": 1000, "expires_at_ms": 2000,
                "issuer": "helper", "command": "act"}
        import json
        def check(args):
            payload = dict(base, args=args)
            return cmdbox.parse(json.dumps(payload).encode("utf-8"), 1500, set())
        self.assertIsNone(check(good)[1])
        for bad in (dict(good, act_id="xyz"), dict(good, guid64="12a"), dict(good, extra="1"),
                    {"act_id": ACT, "object_id": CHAIR}):
            self.assertEqual(check(bad)[1], "BAD_ARGS", bad)


class MenuBuildTests(unittest.TestCase):
    def setUp(self):
        test_e2._load_pure()
        from ashley_e1 import act_menu, schema
        self.menu = act_menu
        self.schema = schema

    def job(self, object_id, guid, distance=1.0, same_room=True):
        return {"object_id": object_id, "definition_id": "7", "class": "object_bookshelf",
                "distance_m": distance, "same_room": same_room, "guid64": guid,
                "name": "bookshelf_Read_%s" % guid, "text_key": "123"}

    def test_her_room_then_her_lot_then_off_the_lot(self):
        # 2.16.2 (live 2026-10-05): on the sidewalk the street came first and she was blind.
        items = [{"object_id": "street", "distance_m": 1.0, "same_room": False, "on_lot": False},
                 {"object_id": "bed", "distance_m": 14.0, "same_room": False, "on_lot": True},
                 {"object_id": "desk", "distance_m": 12.0, "same_room": True, "on_lot": True},
                 {"object_id": "fridge", "distance_m": 9.0, "same_room": False, "on_lot": True},
                 {"object_id": "lost", "distance_m": None, "same_room": False, "on_lot": None},
                 {"object_id": "stored", "distance_m": None, "same_room": False, "on_lot": True}]
        self.assertEqual([item["object_id"] for item in self.menu.ordered(items)],
                         ["desk", "fridge", "bed", "stored", "street"])

    def test_objects_offering_nothing_never_use_a_slot(self):
        items = [{"object_id": str(i), "definition_id": str(i), "room": "r%d" % (i % 20), "on_lot": True,
                  "same_room": False, "distance_m": float(i)} for i in range(100)]
        offers = lambda item: ["act"] if int(item["object_id"]) % 3 == 0 else []
        picked = [item["object_id"] for item, _acts in self.menu.pick(items, offers)]
        # 2.34.0 (F4): every object that offers something, room by room in the order the rooms first appear.
        self.assertEqual(picked, [str(i) for i in sorted(range(0, 100, 3), key=lambda i: (i % 20, i))])
        self.assertEqual(len(picked), 34)

    def test_the_offers_of_an_object_are_read_only_when_the_build_asks_for_the_next_one(self):
        items = [{"object_id": str(i), "room": "r0", "on_lot": True, "same_room": True, "distance_m": 1.0}
                 for i in range(50)]
        reads = []

        def offers(item):
            reads.append(item["object_id"])
            return ["act"]

        pairs = self.menu.iter_pick(items, offers)
        self.assertEqual(reads, [])
        next(pairs)
        self.assertEqual(reads, ["0"])
        next(pairs)
        self.assertEqual(reads, ["0", "1"])

    def test_every_object_is_listed_grouped_by_room_with_fixtures_last(self):
        here = [{"object_id": "h%d" % i, "definition_id": "d%d" % i, "same_room": True, "on_lot": True,
                 "room": "4", "distance_m": float(i)} for i in range(10)]
        chairs = [{"object_id": "c%d" % i, "definition_id": "chair", "same_room": False, "on_lot": True,
                   "room": "5", "distance_m": 10.0 + i} for i in range(4)]
        kitchen = [{"object_id": "k%d" % i, "definition_id": "k%d" % i, "same_room": False, "on_lot": True,
                    "room": "6", "distance_m": 20.0 + i} for i in range(5)]
        unknown = [{"object_id": "u%d" % i, "definition_id": "u%d" % i, "same_room": False, "on_lot": True,
                    "room": None, "distance_m": 30.0 + i} for i in range(4)]
        street = [{"object_id": "s%d" % i, "definition_id": "s%d" % i, "same_room": False, "on_lot": False,
                   "room": None, "distance_m": 1.0 + i} for i in range(5)]
        items = self.menu.ordered(here + chairs + kitchen + unknown + street)
        ids = [item["object_id"] for item, _acts in self.menu.pick(items, lambda item: ["act"])]
        # 2.34.0 (F4): every object: her room, then each room in turn, what is off the lot last.
        self.assertEqual(ids, ["h%d" % i for i in range(10)] + ["c%d" % i for i in range(4)] +
                         ["k%d" % i for i in range(5)] + ["u%d" % i for i in range(4)] + ["s%d" % i for i in range(5)])

    def test_the_far_bedroom_makes_the_menu_and_fixtures_come_last(self):
        # Live 2026-10-06: tired and hungry, her menu was the piano room and the bathroom.
        def thing(oid, room, distance, klass="object_x", same=False):
            return {"object_id": oid, "definition_id": oid, "class": klass, "room": room, "on_lot": True,
                    "same_room": same, "distance_m": distance}
        items = self.menu.ordered(
            [thing("piano%d" % i, "1", 1.0 + i, same=True) for i in range(6)]
            + [thing("bath%d" % i, "2", 3.0 + i) for i in range(6)]
            + [thing("kitchen_light", "3", 9.0, "object_light_wall"), thing("fridge", "3", 11.0, "object_fridge")]
            + [thing("bed", "4", 15.0, "object_bed_double")])
        ids = [item["object_id"] for item, _acts in self.menu.pick(items, lambda item: ["act"])]
        self.assertIn("bed", ids)  # 2.34.0 (F4): every object is listed, so the far bedroom is never cut
        self.assertLess(ids.index("fridge"), ids.index("kitchen_light"))

    def test_identical_choices_are_each_listed_and_people_never_fold(self):
        # 2.19.0 folded three mirrors with the same five acts into one slot; 2.34.0 (F4) lists every object,
        # and the helper lists the same words once per object.
        def thing(oid, room, distance, person=False):
            return {"object_id": oid, "definition_id": oid, "room": room, "on_lot": True,
                    "same_room": False, "distance_m": distance, "person": person}
        acts = {"mirror1": ["a", "b"], "mirror2": ["b", "a"], "mirror3": ["a", "b"], "sink": ["a"],
                "fridge": ["c"], "anna": ["g"], "ben": ["g"]}
        offers = lambda item: [{"guid64": guid} for guid in acts[item["object_id"]]]
        items = self.menu.ordered([thing("mirror1", "1", 1.0), thing("mirror2", "2", 2.0),
                                   thing("mirror3", "3", 3.0), thing("sink", "1", 4.0),
                                   thing("fridge", "3", 5.0), thing("anna", None, 6.0, True),
                                   thing("ben", None, 7.0, True)])
        ids = [item["object_id"] for item, _acts in self.menu.pick(items, offers)]
        self.assertEqual(sorted(ids), ["anna", "ben", "fridge", "mirror1", "mirror2", "mirror3", "sink"])

    def test_a_build_runs_in_small_steps_and_keeps_what_the_game_allows(self):
        clock = {"t": 0.0}
        def runner(job):
            clock["t"] += 0.004
            if job["guid64"] == "boom":
                raise RuntimeError("x")
            return job["guid64"] != "no"
        jobs = [self.job("1", "a"), self.job("1", "no"), self.job("1", "boom"), self.job("2", "b", 2.0)]
        build = self.menu.MenuBuild(jobs, runner, budget_ms=5.0, clock=lambda: clock["t"])
        build.step()
        self.assertFalse(build.done)
        while not build.done:
            build.step()
        payload = build.payload(3, "12")
        self.assertEqual((payload["tested"], payload["refused"], payload["menu_rev"], payload["room"]), (4, 2, 3, "12"))
        self.assertEqual([(o["object_id"], [a["guid64"] for a in o["acts"]]) for o in payload["objects"]],
                         [("1", ["a"]), ("2", ["b"])])
        row = self.schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1,
                                      monotonic_ns=1, e2=payload)
        self.schema.validate_record(row)

    def test_caps_and_sameness(self):
        jobs = [self.job(str(o), str(a), float(o)) for o in range(30) for a in range(12)]
        build = self.menu.MenuBuild(jobs, lambda job: True, budget_ms=1e9, max_per_chunk=10_000)
        build.step()
        payload = build.payload(1, None)
        self.assertEqual(len(payload["objects"]), 30)
        self.assertTrue(all(len(o["acts"]) == self.schema.MENU_MAX_ACTS for o in payload["objects"]))
        again = dict(payload, menu_rev=2, build_ms=99.0)
        self.assertTrue(self.menu.same_menu(payload, again))
        self.assertFalse(self.menu.same_menu(payload, dict(payload, room="5")))
        self.assertFalse(self.menu.same_menu(None, payload))
        empty = self.menu.MenuBuild([], lambda job: True)
        empty.step()
        self.assertTrue(empty.done)

    def test_a_lot_is_written_in_parts_that_each_validate_and_add_up(self):
        clock = {"t": 0.0}

        def offers_clock(item):
            clock["t"] += 0.001
            return [{"guid64": "1"}]

        items = [{"object_id": str(i), "definition_id": str(i), "class": "object_c", "room": str(i % 8),
                  "on_lot": True, "same_room": False, "distance_m": float(i)} for i in range(150)]

        def job_list():
            for item, acts in self.menu.iter_pick(items, offers_clock):
                for act in acts:
                    yield dict(act, object_id=item["object_id"], definition_id=item["definition_id"],
                               distance_m=item["distance_m"], same_room=item["same_room"], room=item["room"],
                               name="object_c_Act", text_key=None)

        build = self.menu.MenuBuild(job_list(), lambda job: True, budget_ms=8.0, max_per_chunk=80,
                                    clock=lambda: clock["t"])
        steps = 0
        while not build.done:
            build.step()
            steps += 1
        self.assertGreater(steps, 1)  # a full lot is not read in one tick
        payload = build.payload(4, "1")
        parts = self.menu.parts(payload)
        self.assertEqual(len(parts), 10)
        self.assertEqual(sum(len(part["objects"]) for part in parts), 150)
        self.assertEqual([part["part"] for part in parts], list(range(10)))
        for part in parts:
            row = self.schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1,
                                          monotonic_ns=1, e2=part)
            self.schema.validate_record(row)
        self.assertEqual(self.menu.parts(dict(payload, objects=[]))[0]["parts"], 1)


if __name__ == "__main__":
    unittest.main()


class _Thing(object):
    is_sim = False

    def __init__(self, object_id, x, affordances):
        self.id = int(object_id)
        self.position = types.SimpleNamespace(x=x, y=0.0, z=0.0)
        self.level = 0
        self.zone_id = 1
        self.definition = types.SimpleNamespace(id=500 + int(object_id))
        self._affordances = affordances

    def super_affordances(self, context=None):
        for item in self._affordances:
            yield item


class MenuSenseTests(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.probe = self.base.probe
        self.allowed = {int(GUID)}
        self.base.sim.test_super_affordance = lambda affordance, target, context: affordance.guid64 in self.allowed
        self.things = [_Thing(11, 2.0, [ReadBook, AutonomousOnly, Greet]), _Thing(12, 30.0, [ReadBook]),
                       types.SimpleNamespace(is_sim=True, id=13)]
        self.probe._lot_snapshot = lambda: (list(self.things), None)
        self.rooms = {}
        room_of = self.base.probe.observers._room
        self.addCleanup(setattr, self.base.probe.observers, "_room", room_of)
        self.base.probe.observers._room = lambda obj, position: self.rooms.get(getattr(obj, "id", None))
        self.row = {"event_kind": "presence_snapshot",
                    "zone": {"position": {"x": 0.0, "y": 0.0, "z": 0.0, "level": 0}, "room": "4"}}

    def tearDown(self):
        writer = self.base.LedgerWriter.instances[-1] if self.base.LedgerWriter.instances else None
        if writer is not None:
            writer.finish()

    def _jobs(self, row):
        """2.34.0 (F4): the menu's jobs as a list (the probe hands them over as a lazy sequence)."""
        jobs, room = self.probe._menu_jobs(row)
        return (None if jobs is None else list(jobs)), room

    def test_jobs_are_her_near_user_directed_offers(self):
        self.rooms = {11: "4", 12: "5"}
        jobs, room = self._jobs(self.row)
        self.assertEqual(room, "4")
        # 2.34.0 (F4): every object with her offers, 12 included (identical choices are no longer folded).
        self.assertEqual([(job["object_id"], job["guid64"], job["name"]) for job in jobs],
                         [("11", GUID, "ReadBook"), ("12", GUID, "ReadBook")])
        self.assertEqual((jobs[0]["distance_m"], jobs[0]["definition_id"], jobs[0]["room"]), (2.0, "511", "4"))

    def test_an_object_that_cannot_be_read_mid_build_offers_nothing_and_the_rest_is_listed(self):
        self.rooms = {11: "4", 12: "5"}
        real = self.probe._menu_offers
        self.addCleanup(setattr, self.probe, "_menu_offers", real)

        def offers(item, sim, context):
            if item["object_id"] == "11":
                raise RuntimeError("gone")
            return real(item, sim, context)
        self.probe._menu_offers = offers
        jobs, _room = self._jobs(self.row)
        self.assertEqual([job["object_id"] for job in jobs], ["12"])

    def test_cheat_and_debug_acts_are_hidden(self):
        self.things = [_Thing(11, 2.0, [PowerConsumption, DebugOnly, ReadBook])]
        jobs, _room = self._jobs(self.row)
        self.assertEqual([job["name"] for job in jobs], ["ReadBook"])

    def test_her_lot_comes_before_the_street(self):
        mailbox = _Thing(21, 1.0, [PowerConsumption])
        lily = _Thing(22, 2.0, [ReadBook])
        bed = _Thing(23, 15.0, [ReadBook])
        bed.is_on_active_lot = lambda: True
        lily.is_on_active_lot = lambda: False
        self.things = [mailbox, lily, bed]
        jobs, _room = self._jobs(self.row)
        self.assertEqual([job["object_id"] for job in jobs], ["23", "22"])  # her lot first, then the street

    def test_people_near_her_come_with_their_socials_after_her_room(self):
        neighbour = _Thing(31, 6.0, [Greet, Propose, ReadBook])
        neighbour.is_sim = True
        neighbour.is_on_active_lot = lambda: True
        passerby = _Thing(32, 60.0, [Greet])
        passerby.is_sim = True
        lamp = _Thing(33, 3.0, [ReadBook])
        self.things = [neighbour, passerby, lamp]
        self.allowed = {int(GUID), 4345}
        # 2.32.0 (SS4-v2): the neighbour is in her room, so she sees them.
        self.rooms = {31: "4"}
        jobs, _room = self._jobs(self.row)
        # The neighbour comes first, as a person, greeting and all; the lamp after.
        self.assertEqual((jobs[0]["object_id"], jobs[0]["class"], jobs[0]["guid64"]), ("31", "sim", GUID))
        self.assertEqual(jobs[-1]["object_id"], "33")
        self.assertNotIn("32", [job["object_id"] for job in jobs])
        # 2.37.1 (User 2026-10-12): the neighbour's Propose is hers to choose, so it is on the menu too.
        self.assertIn("4345", [job["guid64"] for job in jobs if job["object_id"] == "31"])

    def test_a_person_she_cannot_see_off_her_lot_is_not_offered(self):
        # 2.32.0 (PR3, SS4-v2): a Sim not on her lot, in another room, is not offered.
        through_wall = _Thing(41, 3.0, [Greet])
        through_wall.is_sim = True
        through_wall.is_on_active_lot = lambda: False
        other_level = _Thing(42, 2.0, [Greet])
        other_level.is_sim = True
        other_level.is_on_active_lot = lambda: False
        other_level.level = 1
        self.things = [through_wall, other_level]
        self.rooms = {41: "5", 42: "4"}
        self.allowed = {int(GUID)}
        jobs, _room = self._jobs(self.row)
        self.assertEqual(jobs, [])

    def test_a_person_she_hears_on_her_lot_is_offered_and_one_off_it_is_not(self):
        # 2.38.0 (W11 H2): a Sim on her lot she cannot see is heard, and her menu offers what she can do with them
        # (the courier at the front door, 14 m off, was heard and had no act). Off the lot, still not offered.
        heard = _Thing(41, 14.0, [Greet])
        heard.is_sim = True
        heard.is_on_active_lot = lambda: True
        heard_other_level = _Thing(43, 2.0, [Greet])
        heard_other_level.is_sim = True
        heard_other_level.is_on_active_lot = lambda: True
        heard_other_level.level = 1
        off_lot = _Thing(42, 2.0, [Greet])
        off_lot.is_sim = True
        off_lot.is_on_active_lot = lambda: False
        self.things = [heard, heard_other_level, off_lot]
        self.rooms = {41: "5", 43: "5", 42: "5"}
        self.allowed = {int(GUID)}
        jobs, _room = self._jobs(self.row)
        self.assertEqual(sorted((job["object_id"], job["class"]) for job in jobs), [("41", "sim"), ("43", "sim")])

    def test_a_pet_on_the_lot_is_a_person_in_her_menu_not_an_object(self):
        # 2.32.0 (PR13): a pet is offered as a person (the helper names it from her presence), in her room.
        pet = _Thing(51, 2.0, [ReadBook])
        pet.sim_info = types.SimpleNamespace(is_pet=True)
        pet.is_on_active_lot = lambda: True
        self.things = [pet]
        self.rooms = {51: "4"}
        jobs, _room = self._jobs(self.row)
        self.assertEqual([(job["object_id"], job["class"]) for job in jobs], [("51", "sim")])

    def test_an_unreadable_lot_is_no_menu_not_an_empty_one(self):
        self.probe._lot_snapshot = lambda: (None, "TUNED_NO_LOT")
        self.assertIsNone(self.probe._menu_jobs(self.row)[0])

    def test_the_menu_is_written_when_it_changes_and_rebuilt_on_a_room_change(self):
        self.base.LedgerWriter.records = [self.base.continuing()[0]]
        self.assertTrue(self.probe._cmd_arm("HOME"))
        self.assertTrue(self.probe._cmd_start())
        self.base.tick()
        now = {"s": 100.0}
        self.probe._now_s = lambda: now["s"]
        self.probe._menu_reset()
        self.probe._menu_tick(self.row)   # starts a build
        self.probe._menu_tick(self.row)   # finishes it and writes the menu
        menus = self.base.e2("act_menu")
        self.assertEqual(len(menus), 1)
        self.assertEqual(menus[0]["objects"][0]["acts"], [{"guid64": GUID, "name": "ReadBook", "text_key": None}])
        self.assertEqual(menus[0]["menu_rev"], 1)
        for row in self.base.rows("act_menu"):
            self.probe.schema.validate_record(row)
        now["s"] += 25.0
        self.probe._menu_tick(self.row)   # a rebuild after REBUILD_S ...
        self.probe._menu_tick(self.row)   # ... that changes nothing writes nothing
        self.assertEqual(len(self.base.e2("act_menu")), 1)
        self.allowed = set()
        # 2.37.0 (W10 P2): a far object's outcome is kept for FAR_CACHE_S (120 s); the time runs out before the room change.
        now["s"] += 125.0
        self.probe._menu_tick(dict(self.row, zone=dict(self.row["zone"], room="5")))
        self.probe._menu_tick(self.row)
        menus = self.base.e2("act_menu")
        self.assertEqual((len(menus), menus[-1]["objects"], menus[-1]["room"], menus[-1]["menu_rev"]), (2, [], "5", 2))

    def test_a_menu_failure_never_stops_sampling(self):
        self.base.LedgerWriter.records = [self.base.continuing()[0]]
        self.assertTrue(self.probe._cmd_arm("HOME"))
        self.assertTrue(self.probe._cmd_start())

        def broken(row):
            raise RuntimeError("menu")

        self.probe._menu_tick = broken
        self.base.tick()
        self.base.tick()
        self.assertEqual(self.probe._STATE, "SAMPLING")
        self.assertEqual(self.probe._MENU_FAILURES, 2)


class BuildListTests(unittest.TestCase):
    def test_every_probe_module_is_in_the_build(self):
        """2.16.0: act_menu.py was missing from build.ps1's module list; the package would
        have failed to import in the game. Every source module must be built."""
        import os
        import re
        root = os.path.join(os.path.dirname(__file__), "..")
        text = open(os.path.join(root, "tools", "build.ps1"), encoding="utf-8").read()
        listed = set(re.findall(r'"([a-z0-9_]+)"', text[text.index("$moduleNames"):text.index("foreach ($moduleName")]))
        sources = {name[:-3] for name in os.listdir(os.path.join(root, "src", "ashley_e1")) if name.endswith(".py")}
        self.assertEqual(sources - listed, set())
