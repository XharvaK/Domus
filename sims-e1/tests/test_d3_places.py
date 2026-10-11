"""2.35.0 (D3): going places on the lot. The menu lists a standable spot per room (and level) with objects,
and the front door outside; its act is the game's Go Here. Fakes only: the game's own search, terrain and pick
are stubbed here, and the names the probe reads from the game are checked where they are used."""
import types
import unittest

import test_e2

GUID = "4242"
GO_HERE_GUID = 5151


class ReadBook(object):
    guid64 = int(GUID)
    allow_user_directed = True


GoHere = type("terrain-gohere", (object,), {"guid64": GO_HERE_GUID, "allow_user_directed": True})


class _Terrain(object):
    def super_affordances(self, context=None):
        yield GoHere


class _Place(object):
    """An object on the lot: its position carries the room the game's lookup gives it."""
    is_sim = False

    def __init__(self, object_id, x, z, level, room, affordances=(ReadBook,)):
        self.id = int(object_id)
        self.position = types.SimpleNamespace(x=x, y=0.0, z=z, room=room)
        self.level = level
        self.zone_id = 1
        self.routing_surface = "surface-%d" % level
        self.definition = types.SimpleNamespace(id=500 + self.id)
        self._affordances = list(affordances)

    def is_on_active_lot(self):
        return True

    def super_affordances(self, context=None):
        for item in self._affordances:
            yield item


class SpotMenuTests(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.probe = self.base.probe
        self.actuator = self.probe.e2_actuator
        self.base.sim.test_super_affordance = lambda affordance, target, context: True
        self.things = []
        self.door = None
        self.door_room = "0"
        self.no_spot = set()
        self.asked = []
        self.probe._lot_snapshot = lambda: (list(self.things), None)
        self.probe.observers._room = lambda obj, position: getattr(obj.position, "room", None)
        self.actuator.terrain_object = lambda: _Terrain()
        self.actuator.front_door = lambda: self.door
        self.actuator.Vector3 = lambda x, y, z: types.SimpleNamespace(x=x, y=y, z=z, room=self.door_room)
        self.actuator.standable_spot = self.standable
        self.actuator.room_at = lambda obj, position, level: getattr(position, "room", None)
        # The game's TerrainPoint and pick are not in the fakes (see the P2 tests); a spot's target is any token here.
        self.actuator.spot_target = lambda sim, spot, owner=False: (types.SimpleNamespace(spot=spot), "context")
        self.row = {"event_kind": "presence_snapshot",
                    "zone": {"position": {"x": 0.0, "y": 0.0, "z": 0.0, "level": 0}, "room": "4"}}

    def tearDown(self):
        writer = self.base.LedgerWriter.instances[-1] if self.base.LedgerWriter.instances else None
        if writer is not None:
            writer.finish()

    def standable(self, sim, start, surface):
        """The game's search, as a fake: the start itself when its room has a standable spot."""
        self.asked.append((start.x, start.z, surface))
        if start.x in self.no_spot:
            return None
        return types.SimpleNamespace(x=start.x, y=0.0, z=start.z, room=start.room), "facing"

    def menu(self, row=None):
        """The whole menu of one build, read as the sampling ticks read it (within a generous budget)."""
        jobs, room = self.probe._menu_jobs(row or self.row)
        build = self.probe.act_menu.MenuBuild(jobs, self.probe._menu_test, budget_ms=10000.0, max_per_chunk=10000,
                                              spots=jobs.spots)
        while not build.done:
            build.step()
        return build, build.payload(1, room)

    def spots(self, payload):
        return [item for item in payload["objects"] if item["class"] == "spot"]

    def test_each_room_with_objects_gets_one_spot_listed_after_its_objects(self):
        self.things = [_Place(11, 2.0, 0.0, 0, "4"), _Place(12, 2.0, 1.0, 0, "4"),
                       _Place(13, 12.0, 0.0, 0, "5"), _Place(14, 20.0, 0.0, 1, "6")]
        _build, payload = self.menu()
        spots = self.spots(payload)
        self.assertEqual([(s["object_id"], s["room"], s["level"], s["spot"]) for s in spots],
                         [("1", "4", 0, "room"), ("2", "5", 0, "room"), ("3", "6", 1, "room")])
        for spot in spots:
            self.assertEqual([(a["guid64"], a["name"], a["text_key"]) for a in spot["acts"]],
                             [(str(GO_HERE_GUID), "terrain-gohere", None)])
        order = [item["object_id"] for item in payload["objects"]]
        self.assertEqual(order, ["11", "12", "1", "13", "2", "14", "3"])  # her room's objects, its spot, then the rest

    def test_the_spot_starts_from_the_object_nearest_the_group_centre(self):
        self.things = [_Place(11, 0.0, 0.0, 0, "4"), _Place(12, 4.0, 0.0, 0, "4"), _Place(13, 5.0, 0.0, 0, "4")]
        _build, payload = self.menu()
        self.assertEqual(self.asked, [(4.0, 0.0, "surface-0")])  # the centre is 3.0; 4.0 is nearest
        self.assertEqual([s["object_id"] for s in self.spots(payload)], ["1"])

    def test_a_room_with_no_standable_spot_is_left_out_and_its_objects_stay(self):
        self.things = [_Place(11, 2.0, 0.0, 0, "4"), _Place(12, 12.0, 0.0, 0, "5")]
        self.no_spot = {12.0}
        _build, payload = self.menu()
        self.assertEqual([s["room"] for s in self.spots(payload)], ["4"])
        self.assertIn("12", [item["object_id"] for item in payload["objects"]])

    def test_the_spot_search_runs_only_as_the_build_asks_for_each_spot(self):
        self.things = [_Place(11, 2.0, 0.0, 0, "4"), _Place(12, 12.0, 0.0, 0, "5")]
        jobs, _room = self.probe._menu_jobs(self.row)
        self.assertEqual(self.asked, [])
        list(jobs)
        self.assertEqual(len(self.asked), 2)

    def test_a_spot_search_that_raises_skips_that_spot_only(self):
        self.things = [_Place(11, 2.0, 0.0, 0, "4"), _Place(12, 12.0, 0.0, 0, "5")]
        search = self.standable

        def broken(sim, start, surface):
            if start.x == 12.0:
                raise RuntimeError("search failed")
            return search(sim, start, surface)
        self.actuator.standable_spot = broken
        _build, payload = self.menu()
        self.assertEqual([s["room"] for s in self.spots(payload)], ["4"])
        self.assertIn("12", [item["object_id"] for item in payload["objects"]])

    def test_the_front_door_is_a_spot_outside_and_there_is_none_without_a_door(self):
        self.things = [_Place(11, 2.0, 0.0, 0, "4")]
        self.door = _Place(15, 30.0, 0.0, 0, "0", affordances=())
        self.door.forward = types.SimpleNamespace(x=1.0, y=0.0, z=0.0)
        _build, payload = self.menu()
        front = [s for s in self.spots(payload) if s["level"] == 0 and s["room"] == "0"]
        self.assertEqual([(s["object_id"], s["spot"]) for s in front], [("2", "front_door")])
        self.assertIn((31.0, 0.0, "surface-0"), self.asked)  # one metre in front of the door, on the outdoor side
        self.door = None
        _build, payload = self.menu()
        self.assertEqual([s["spot"] for s in self.spots(payload)], ["room"])

    def test_spot_ids_are_small_from_one_and_keep_their_room_across_builds(self):
        self.things = [_Place(11, 2.0, 0.0, 0, "4"), _Place(12, 12.0, 0.0, 0, "5")]
        first, _payload = self.menu()
        self.things = [_Place(12, 12.0, 0.0, 0, "5"), _Place(11, 2.0, 0.0, 0, "4"), _Place(13, 3.0, 0.0, 0, "4")]
        second, payload = self.menu()
        self.assertEqual(first.spots["1"]["room"], "4")
        self.assertEqual(first.spots["2"]["room"], "5")
        self.assertEqual(second.spots["1"]["room"], "4")  # the room 4 spot kept its id
        self.assertEqual(second.spots["2"]["room"], "5")
        self.assertEqual(sorted(second.spots), ["1", "2"])
        self.assertEqual(second.spots["1"]["level"], 0)
        self.assertEqual(second.spots["1"]["kind"], "room")
        self.assertEqual(second.spots["1"]["position"].x, 2.0)

    def test_the_spot_rows_pass_the_schema(self):
        self.things = [_Place(11, 2.0, 0.0, 0, "4"), _Place(12, 12.0, 0.0, 1, "6")]
        _build, payload = self.menu()
        schema = self.probe.schema
        for part in self.probe.act_menu.parts(payload):
            row = schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1,
                                     monotonic_ns=1, e2=part)
            schema.validate_record(row)
        self.assertEqual(len(self.spots(payload)), 2)


class SpotIdTests(unittest.TestCase):
    def test_a_spot_key_keeps_its_id_and_ids_run_out_at_999(self):
        from test_binding import load_probe
        _package, probe, _calls = load_probe()
        ids = probe.act_menu.SpotIds()
        self.assertEqual(ids.id_for("4", 0, "room"), 1)
        self.assertEqual(ids.id_for("5", 0, "room"), 2)
        self.assertEqual(ids.id_for("4", 0, "room"), 1)
        self.assertEqual(ids.id_for("4", 0, "front_door"), 3)
        self.assertEqual(ids.id_for("4", 1, "room"), 4)
        for number in range(5, 1000):
            ids.id_for("r%d" % number, 0, "room")
        self.assertEqual(ids.id_for("4", 0, "room"), 1)
        self.assertIsNone(ids.id_for("new", 0, "room"))


if __name__ == "__main__":
    unittest.main()
