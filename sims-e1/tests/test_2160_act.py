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

    def test_near_keeps_her_room_or_close_things_nearest_first(self):
        items = [{"object_id": "1", "distance_m": 12.0, "same_room": True},
                 {"object_id": "2", "distance_m": 3.0, "same_room": False},
                 {"object_id": "3", "distance_m": 9.0, "same_room": False},
                 {"object_id": "4", "distance_m": None, "same_room": False}]
        self.assertEqual([item["object_id"] for item in self.menu.near(items)], ["2", "1"])

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
        jobs = [self.job(str(o), str(a), float(o)) for o in range(20) for a in range(12)]
        build = self.menu.MenuBuild(jobs, lambda job: True, budget_ms=1e9, max_per_chunk=10_000)
        build.step()
        payload = build.payload(1, None)
        self.assertEqual(len(payload["objects"]), self.schema.MENU_MAX_OBJECTS)
        self.assertTrue(all(len(o["acts"]) == self.schema.MENU_MAX_ACTS for o in payload["objects"]))
        again = dict(payload, menu_rev=2, build_ms=99.0)
        self.assertTrue(self.menu.same_menu(payload, again))
        self.assertFalse(self.menu.same_menu(payload, dict(payload, room="5")))
        self.assertFalse(self.menu.same_menu(None, payload))
        self.assertTrue(self.menu.MenuBuild([], lambda job: True).done)


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
        self.row = {"event_kind": "presence_snapshot",
                    "zone": {"position": {"x": 0.0, "y": 0.0, "z": 0.0, "level": 0}, "room": "4"}}

    def tearDown(self):
        writer = self.base.LedgerWriter.instances[-1] if self.base.LedgerWriter.instances else None
        if writer is not None:
            writer.finish()

    def test_jobs_are_her_near_user_directed_offers(self):
        jobs, room = self.probe._menu_jobs(self.row)
        self.assertEqual(room, "4")
        self.assertEqual([(job["object_id"], job["guid64"], job["name"]) for job in jobs], [("11", GUID, "ReadBook")])
        self.assertEqual((jobs[0]["distance_m"], jobs[0]["definition_id"]), (2.0, "511"))

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
