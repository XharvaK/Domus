"""2.25.0: each menu object says whether the game sees a way from her to it (the check the
game's own autonomy makes); an object she cannot reach is still listed."""
import types
import unittest

import test_2160_act as acts
from test_2160_act import GUID, ReadBook, _Thing


class _Calls(object):
    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def bind(self, thing):
        def is_connected(sim):
            self.asked.append(thing.id)
            answer = self.answers[thing.id]
            if isinstance(answer, Exception):
                raise answer
            return answer
        thing.is_connected = is_connected


class ReachTests(unittest.TestCase):
    def setUp(self):
        self.case = acts.MenuSenseTests()
        self.case.setUp()
        self.probe = self.case.probe

    def tearDown(self):
        self.case.tearDown()

    def _menu(self, things):
        self.case.things = things
        jobs, room = self.probe._menu_jobs(self.case.row)
        build = self.probe.act_menu.MenuBuild(jobs, self.probe._menu_test, budget_ms=1e9, max_per_chunk=10_000)
        build.step()
        return build.payload(1, room)

    def test_version(self):
        self.assertGreaterEqual(tuple(int(x) for x in self.probe.schema.PROBE_VERSION.split(".")), (2, 25, 0))

    def test_reach_is_asked_once_per_object_and_an_unreachable_one_stays_listed(self):
        class BrowseBooks(ReadBook):
            guid64 = 4243
        self.case.allowed = {int(GUID), 4243}
        near, far, odd = _Thing(41, 2.0, [ReadBook, BrowseBooks]), _Thing(42, 9.0, [BrowseBooks]), _Thing(43, 4.0, [ReadBook])
        calls = _Calls({41: True, 42: False, 43: RuntimeError("x")})
        for thing in (near, far, odd):
            calls.bind(thing)
        payload = self._menu([near, far, odd])
        reach = {item["object_id"]: item["reach"] for item in payload["objects"]}
        self.assertEqual(reach.get("41"), True)
        self.assertIn("42", reach)
        self.assertIs(reach["42"], False)
        self.assertEqual(sorted(calls.asked), sorted(set(calls.asked)))
        for item in payload["objects"]:
            if item["object_id"] == "43":
                self.assertIsNone(item["reach"])
        row = self.probe.schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1,
                                            monotonic_ns=1, e2=payload)
        self.probe.schema.validate_record(row)

    def test_a_change_in_reach_is_a_new_menu(self):
        payload = {"menu_rev": 1, "room": "4", "tested": 1, "refused": 0, "build_ms": 1.0, "objects": [
            {"object_id": "1", "definition_id": None, "class": "c", "distance_m": 1.0, "same_room": True,
             "reach": True, "room": None, "acts": [{"guid64": "1", "name": "n", "text_key": None}]}]}
        blocked = dict(payload, objects=[dict(payload["objects"][0], reach=False)])
        self.assertFalse(self.probe.act_menu.same_menu(payload, blocked))

    def test_older_menu_rows_without_reach_still_validate(self):
        schema = self.probe.schema
        payload = {"menu_rev": 1, "room": None, "tested": 1, "refused": 0, "build_ms": 1.0, "part": 0, "parts": 1,
                   "objects": [
            {"object_id": "1", "definition_id": None, "class": "c", "distance_m": 1.0, "same_room": True, "room": None,
             "acts": [{"guid64": "1", "name": "n", "text_key": None}]}]}
        row = schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1, monotonic_ns=1, e2=payload)
        schema.validate_record(row)
        self.assertIsNone(row["e2"]["objects"][0]["reach"])
        row["e2"]["objects"][0]["reach"] = "yes"
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(row)


    # 2.38.0 (W11 P2): a door, gate or archway is a portal. The game's connectivity check answered False for every
    # door on the live lot (the front door too), so a portal's reach is True when the game says so, else None
    # (unknown), never False.
    def test_a_portal_is_never_reported_unreachable_only_unknown(self):
        e2_actuator = self.probe.e2_actuator
        sim = types.SimpleNamespace(id=1)

        class FrontDoor(object):
            def __init__(self, answer):
                self.answer = answer

            def is_connected(self, sim):
                if isinstance(self.answer, Exception):
                    raise self.answer
                return self.answer

        class DoubleDoor(FrontDoor):
            pass

        class Gate(FrontDoor):
            pass

        class Archway(FrontDoor):
            pass

        self.assertIsNone(e2_actuator.reachable(sim, FrontDoor(False)))
        self.assertIsNone(e2_actuator.reachable(sim, DoubleDoor(False)))
        self.assertIsNone(e2_actuator.reachable(sim, Gate(False)))
        self.assertIsNone(e2_actuator.reachable(sim, Archway(False)))
        self.assertIsNone(e2_actuator.reachable(sim, FrontDoor(RuntimeError("game"))))
        self.assertIsNone(e2_actuator.reachable(sim, FrontDoor(None)))
        self.assertIs(e2_actuator.reachable(sim, FrontDoor(True)), True)
        self.assertIs(e2_actuator.reachable(sim, DoubleDoor(True)), True)

    def test_an_object_that_is_not_a_portal_keeps_the_game_answer(self):
        e2_actuator = self.probe.e2_actuator
        sim = types.SimpleNamespace(id=1)

        class Chair(object):
            def __init__(self, answer):
                self.answer = answer

            def is_connected(self, sim):
                return self.answer

        self.assertIs(e2_actuator.reachable(sim, Chair(False)), False)
        self.assertIs(e2_actuator.reachable(sim, Chair(True)), True)
        self.assertIsNone(e2_actuator.reachable(sim, Chair("maybe")))

    def test_a_door_in_the_menu_reads_unknown_and_a_chair_still_reads_no_way(self):
        class Door(object):
            pass

        door, chair = self.case_thing(51, 2.0, Door), self.case_thing(52, 3.0, None)
        chair.is_connected = lambda sim: False
        door.is_connected = lambda sim: False
        self.case.allowed = {int(GUID)}
        payload = self._menu([door, chair])
        reach = {item["object_id"]: item["reach"] for item in payload["objects"]}
        self.assertIsNone(reach.get("51"))
        self.assertIs(reach.get("52"), False)

    def case_thing(self, object_id, x, klass):
        """A menu object of the given class (None: the plain fake)."""
        thing = _Thing(object_id, x, [ReadBook])
        if klass is not None:
            thing.__class__ = type(klass.__name__, (_Thing,), {"is_sim": False})
        return thing


if __name__ == "__main__":
    unittest.main()
