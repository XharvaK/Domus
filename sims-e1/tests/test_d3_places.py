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

    def test_a_person_is_never_the_anchor_of_a_spot_only_an_object_is(self):
        # The Sim is nearest the group's centre, so an anchor that counted people would search from her position.
        desk = _Place(11, -2.0, 0.0, 0, "4")
        bed = _Place(12, 2.0, 0.0, 0, "4")
        sim = _Place(13, 0.0, 0.0, 0, "4")
        sim.is_sim = True
        self.things = [desk, sim, bed]
        _build, payload = self.menu()
        self.assertEqual([s["object_id"] for s in self.spots(payload)], ["1"])
        self.assertIn(self.asked[0][0], (-2.0, 2.0))
        self.assertNotIn(0.0, [start_x for start_x, _z, _surface in self.asked])

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

    def test_a_front_door_facing_in_gets_its_spot_from_behind_and_none_when_neither_side_is_outdoors(self):
        self.things = [_Place(11, 2.0, 0.0, 0, "4")]
        self.door = _Place(15, 30.0, 0.0, 0, "4", affordances=())
        self.door.forward = types.SimpleNamespace(x=1.0, y=0.0, z=0.0)  # facing into the house (x > 30 is room 4)
        self.actuator.Vector3 = lambda x, y, z: types.SimpleNamespace(x=x, y=y, z=z, room="0" if x < 30.0 else "4")
        _build, payload = self.menu()
        front = [s for s in self.spots(payload) if s["spot"] == "front_door"]
        self.assertEqual([s["room"] for s in front], ["0"])
        self.assertIn((29.0, 0.0, "surface-0"), self.asked)  # one metre behind the door, which is outdoors
        self.actuator.Vector3 = lambda x, y, z: types.SimpleNamespace(x=x, y=y, z=z, room="4")
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


class _FakePoint(object):
    id = 9001

    def __init__(self, location):
        self.location = location


class _FakeLocation(object):
    def __init__(self, transform, surface):
        self.transform, self.surface = transform, surface


class _FakeTransform(object):
    def __init__(self, position, orientation):
        self.position, self.orientation = position, orientation


class _FakePick(object):
    def __init__(self, pick_type, target, location, routing_surface):
        self.pick_type, self.target, self.location, self.routing_surface = pick_type, target, location, routing_surface


class _Refused(object):
    """A preflight refusal: falsy, with the game's tooltip (its string key is what the probe reads)."""

    def __bool__(self):
        return False

    tooltip = types.SimpleNamespace(_string_id=4711)


class SpotActTests(unittest.TestCase):
    """2.35.0 (D3, P2): an act that names a spot is Go Here at the spot's point, with the game's pick, through
    the same checks and push as any other act."""

    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.probe = self.base.probe
        self.actuator = self.probe.e2_actuator
        self.zone = object()
        self.probe._current_zone = lambda: self.zone
        self.pool = False
        self.allowed = True
        self.refusal = None
        self.tested = []
        self.actuator.terrain_object = lambda: _Terrain()
        self.actuator.TerrainPoint = _FakePoint
        self.actuator.Location = _FakeLocation
        self.actuator.Transform = _FakeTransform
        self.actuator.PickInfo = _FakePick
        self.actuator.PickType = types.SimpleNamespace(PICK_TERRAIN="PICK_TERRAIN", PICK_POOL_SURFACE="PICK_POOL_SURFACE")
        self.actuator.is_location_pool = lambda position, level: self.pool
        self.spot = {"position": "P1", "orientation": "O1", "routing_surface": "S1", "level": 1, "room": "4",
                     "kind": "room"}
        self.probe._E2.publish_spots(self.zone, {"1": self.spot})

        def test_super_affordance(affordance, target, context):
            self.tested.append((affordance.guid64, target, context))
            return self.refusal if self.refusal is not None else self.allowed
        self.base.sim.test_super_affordance = test_super_affordance

    def tearDown(self):
        writer = self.base.LedgerWriter.instances[-1] if self.base.LedgerWriter.instances else None
        if writer is not None:
            writer.finish()

    def ready(self):
        self.base.LedgerWriter.records = [self.base.continuing()[0]]
        self.assertTrue(self.probe._cmd_arm("HOME"))
        self.assertTrue(self.probe._cmd_start())
        self.base.tick()
        self.probe._E2.publish_spots(self.zone, {"1": self.spot})  # arming clears the session's spots

    def act(self, object_id="1", guid64=str(GO_HERE_GUID)):
        self.acts = getattr(self, "acts", 0) + 1
        act_id = "%032x" % self.acts
        connection = self.probe._InboxReply("helper")
        ok = self.probe._inbox_dispatch(
            {"command": "act", "args": {"act_id": act_id, "object_id": object_id, "guid64": guid64}}, connection)
        self.last_act_id = act_id
        return ok, connection

    def events(self):
        return self.base.e2("act_event")

    def test_an_act_on_a_spot_is_go_here_at_its_point_with_the_games_pick(self):
        self.ready()
        ok, connection = self.act()
        self.assertTrue(ok)
        self.assertTrue(connection.lines[-1].startswith("ACT_PUSHED " + self.last_act_id))
        guid, point, context = self.base.pushes[-1]
        self.assertEqual((guid, point), (GO_HERE_GUID, 9001))
        self.assertIsInstance(context.pick, _FakePick)
        self.assertEqual(context.pick.pick_type, "PICK_TERRAIN")
        self.assertIs(context.pick.target, self.tested[-1][1])  # the game's pick names the same point it targets
        self.assertEqual(context.pick.location, "P1")
        self.assertEqual(context.pick.routing_surface, "S1")
        self.assertEqual(self.tested[-1][0], GO_HERE_GUID)
        self.assertEqual(self.tested[-1][1].location.transform.position, "P1")
        self.assertEqual(self.tested[-1][1].location.transform.orientation, "O1")
        self.assertEqual(self.tested[-1][1].location.surface, "S1")
        phases = [(e["phase"], e["object_id"], e["guid64"], e["tuning_name"]) for e in self.events()]
        self.assertEqual(phases, [("ACCEPTED", "1", str(GO_HERE_GUID), "terrain-gohere"),
                                  ("PUSHED", "1", str(GO_HERE_GUID), "terrain-gohere")])

    def test_a_pool_spot_takes_the_pool_pick(self):
        self.pool = True
        self.ready()
        self.assertTrue(self.act()[0])
        self.assertEqual(self.base.pushes[-1][2].pick.pick_type, "PICK_POOL_SURFACE")

    def test_an_act_on_a_spot_the_newest_build_does_not_hold_is_no_object(self):
        self.ready()
        ok, connection = self.act(object_id="2")
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT NO_OBJECT")
        self.probe._E2.publish_spots(self.zone, {})
        ok, connection = self.act(object_id="1")
        self.assertEqual(connection.lines[-1], "ACT_REJECT NO_OBJECT")
        self.assertEqual(self.base.pushes, [])

    def test_a_spot_of_another_zone_is_no_object(self):
        self.ready()
        self.probe._current_zone = lambda: object()
        ok, connection = self.act()
        self.assertEqual(connection.lines[-1], "ACT_REJECT NO_OBJECT")

    def test_an_act_that_is_not_go_here_at_a_spot_is_not_offered(self):
        self.ready()
        ok, connection = self.act(guid64="4242")
        self.assertEqual(connection.lines[-1], "ACT_REJECT NOT_OFFERED")
        self.assertEqual(self.base.pushes, [])

    def test_the_game_refusing_go_here_is_a_refusal_with_its_reason(self):
        self.refusal = _Refused()
        self.ready()
        ok, connection = self.act()
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT GAME_REFUSED")
        rejected = [e for e in self.events() if e["phase"] == "REJECTED"][-1]
        self.assertEqual((rejected["code"], rejected["reason_key"]), ("GAME_REFUSED", "4711"))
        self.assertEqual(self.base.pushes, [])

    def test_the_spot_the_newest_menu_build_found_is_the_one_the_act_names(self):
        bed = types.SimpleNamespace(id=11, zone_id=1, routing_surface="S0", level=0, is_sim=False,
                                    position=types.SimpleNamespace(x=2.0, y=0.0, z=0.0, room="4"),
                                    definition=types.SimpleNamespace(id=511),
                                    super_affordances=lambda context=None: iter([]), is_on_active_lot=lambda: True)
        row = {"event_kind": "presence_snapshot",
               "zone": {"position": {"x": 0.0, "y": 0.0, "z": 0.0, "level": 0}, "room": "4"}}
        self.base.sim.test_super_affordance = lambda affordance, target, context: True
        self.ready()  # armed and sampling first; the lot is read by the menu only
        self.probe._E2.publish_spots(self.zone, {})  # only the menu's own build may supply the spot
        self.probe._lot_snapshot = lambda: ([bed], None)
        self.probe.observers._room = lambda obj, position: obj.position.room
        self.actuator.front_door = lambda: None
        self.actuator.spot_start = lambda obj, kind, side=1.0: obj.position
        self.actuator.standable_spot = lambda sim, start, surface: (
            types.SimpleNamespace(x=start.x, y=0.0, z=start.z, room=start.room), "facing")
        self.actuator.room_at = lambda obj, position, level: position.room
        self.actuator.spot_target = lambda sim, spot, owner=False: (
            _FakePoint(_FakeLocation(_FakeTransform(spot["position"], spot["orientation"]), spot["routing_surface"])),
            "context")
        self.probe._menu_tick(row)  # starts the build
        self.probe._menu_tick(row)  # finishes it: its spots are the ones an act may name
        self.assertEqual(sorted(self.probe._E2.spots), ["1"])
        self.assertEqual(self.probe._E2.spots["1"]["room"], "4")
        ok, connection = self.act(object_id="1")
        self.assertTrue(ok, connection.lines)
        self.assertEqual(self.base.pushes[-1][0], GO_HERE_GUID)


class _RefusedWithoutKey(object):
    def __bool__(self):
        return False

    tooltip = None


class PhoneRefusalTests(unittest.TestCase):
    """2.35.0 (D3, P3): the phone's offers the game's preflight refuses are named by tuning name and reason key in the
    menu's part 0 (a diagnostic only: the menu itself is unchanged; D4 is designed from it)."""

    def setUp(self):
        import test_2160_act as acts
        import test_2290_phone as phone
        self.case = acts.MenuSenseTests()
        self.case.setUp()
        self.probe = self.case.probe
        self.case.things = []
        self.case.allowed = {5001, 5002, 5004, 5005, 5006, 5007, 5008, 5009, 5010, int(GUID)}
        self.refusals = {}

        def test_super_affordance(affordance, target, context):
            if affordance.guid64 in self.refusals:
                return self.refusals[affordance.guid64]
            return affordance.guid64 in self.case.allowed
        self.case.base.sim.test_super_affordance = test_super_affordance
        phone.her_phone(self.case.base.sim)

    def tearDown(self):
        self.case.tearDown()

    def _payload(self):
        jobs, room = self.probe._menu_jobs(self.case.row)
        build = self.probe.act_menu.MenuBuild(jobs, self.probe._menu_test, budget_ms=1e9, max_per_chunk=10000)
        while not build.done:
            build.step()
        return build.payload(1, room)

    def test_a_phone_act_the_game_refuses_is_named_with_its_reason_key(self):
        self.refusals[5003] = _Refused()  # PhoneSampleUntested, refused with a tooltip key
        payload = self._payload()
        self.assertEqual(payload["refused_phone"], [{"name": "PhoneSampleUntested", "reason_key": "4711"}])
        self.refusals[5003] = _RefusedWithoutKey()
        self.assertEqual(self._payload()["refused_phone"], [{"name": "PhoneSampleUntested", "reason_key": None}])

    def test_the_refusals_are_phone_acts_only_and_an_object_is_never_named(self):
        import test_2160_act as acts
        self.case.things = [acts._Thing(11, 2.0, [ReadBook])]
        self.refusals[4242] = _Refused()  # an object's act, refused by the game: not a phone act, not named
        payload = self._payload()
        self.assertEqual([item["name"] for item in payload["refused_phone"]], ["PhoneSampleUntested"])

    def test_at_most_sixteen_phone_refusals_are_named_and_the_menu_is_unchanged(self):
        classes = [type("PhoneRefusal%d" % number, (object,), {"guid64": 6000 + number, "allow_user_directed": True})
                   for number in range(20)]
        self.case.base.sim._phone_affordances = classes
        for number in range(20):
            self.refusals[6000 + number] = _RefusedWithoutKey()
        payload = self._payload()
        self.assertEqual(len(payload["refused_phone"]), 16)  # the menu offers at most 16 phone acts to test
        self.assertEqual(payload["objects"], [])  # every phone act is refused: her phone has no entry

    def test_part_zero_carries_the_refusals_and_later_parts_none(self):
        payload = self._payload()
        payload = dict(payload, objects=payload["objects"] * 17)
        parts = self.probe.act_menu.parts(payload)
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0]["refused_phone"], [{"name": "PhoneSampleUntested", "reason_key": None}])
        self.assertIsNone(parts[1]["refused_phone"])

    def test_the_refusals_validate_and_an_older_row_without_them_still_does(self):
        schema = self.probe.schema
        payload = self._payload()
        part = self.probe.act_menu.parts(payload)[0]
        schema.validate_record(schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1,
                                                  monotonic_ns=1, e2=part))
        older = dict(part)
        del older["refused_phone"]
        row = schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1, monotonic_ns=1, e2=part)
        row["e2"] = older
        schema.validate_record(row)
        self.assertIsNone(row["e2"]["refused_phone"])
        row["e2"]["refused_phone"] = "not a list"
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(row)

    def test_a_change_in_the_refusals_is_a_new_menu(self):
        payload = self._payload()
        self.assertTrue(self.probe.act_menu.same_menu(payload, dict(payload)))
        self.assertFalse(self.probe.act_menu.same_menu(payload, dict(payload, refused_phone=[])))


if __name__ == "__main__":
    unittest.main()


class StandableSpotTests(unittest.TestCase):
    """The game's placement.find_good_location returns (position, orientation, reason); position is None on a miss."""

    def setUp(self):
        from test_binding import load_probe
        _package, probe, _calls = load_probe()
        self.actuator = probe.e2_actuator
        self.saved = self.actuator.placement

    def tearDown(self):
        self.actuator.placement = self.saved

    def fake_placement(self, result):
        return types.SimpleNamespace(
            create_starting_location=lambda position=None, routing_surface=None: ("start", position, routing_surface),
            create_fgl_context_for_sim=lambda starting, sim: ("context", starting, sim),
            find_good_location=lambda context: result)

    def test_the_games_three_values_give_the_position_and_orientation(self):
        self.actuator.placement = self.fake_placement(("here", "facing", "FGL Successful"))
        self.assertEqual(self.actuator.standable_spot("sim", "start", "surface"), ("here", "facing"))

    def test_a_search_that_finds_nothing_gives_no_spot(self):
        self.actuator.placement = self.fake_placement((None, None, "FGL Failed: search returned 0 results."))
        self.assertIsNone(self.actuator.standable_spot("sim", "start", "surface"))
