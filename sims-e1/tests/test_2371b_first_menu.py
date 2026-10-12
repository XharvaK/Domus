"""2.37.1 (W10b): the first build in a zone steps with FIRST_BUDGET_MS a tick (8 ms otherwise) and writes the menu
it has so far every FIRST_PARTIAL_S seconds, never before and never once it is done or for a zone she has left;
a later build in the same zone writes no partial menu.

The clock is the fake clock of test_2371_menu_speed (seconds); objects and acts are invented classes."""
import unittest

import test_2160_act as acts
import test_e2
from test_2160_act import GUID

NEAR_ID = 11  # her room (room "4"), invented
FAR_OBJECTS = 50  # objects on the lot out of her room, 16 acts each: 800 candidate acts in all
ACTS_PER_OBJECT = 16  # act_menu.CANDIDATE_ACTS
FAR_GUID = 7000  # invented guid64s for the far acts


def _act(guid):
    return type("FirstMenu2371Act%d" % guid, (object,), {"guid64": guid, "allow_user_directed": True})


class FirstMenuTests(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.probe = self.base.probe
        self.probe._MENU_FAR.clear()
        self.probe._menu_reset()
        self.allowed = {int(GUID)} | set(range(FAR_GUID, FAR_GUID + FAR_OBJECTS * ACTS_PER_OBJECT))
        self.base.sim.test_super_affordance = lambda affordance, target, context: affordance.guid64 in self.allowed
        self.things = [acts._Thing(NEAR_ID, 2.0, [acts.ReadBook])]
        self.probe._lot_snapshot = lambda: (list(self.things), None)
        self.rooms = {NEAR_ID: "4"}
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
        # The sampler's own ticks may have built a menu already: each test starts from no build.
        self.probe._menu_reset()
        self.probe._MENU_FAR.clear()
        self.baseline = len(self.base.e2("act_menu"))

    def tearDown(self):
        writer = self.base.LedgerWriter.instances[-1] if self.base.LedgerWriter.instances else None
        if writer is not None:
            writer.finish()

    def far_things(self):
        things = []
        for index in range(FAR_OBJECTS):
            first = FAR_GUID + index * ACTS_PER_OBJECT
            affordances = [_act(first + offset) for offset in range(ACTS_PER_OBJECT)]
            things.append(acts._Thing(100 + index, 30.0, affordances))
        return things

    def tick(self, seconds):
        self.clock["s"] = seconds
        self.probe._menu_tick(self.row)

    def written_by(self, seconds):
        """Ticks at this time and returns how many act_menu rows that tick wrote."""
        before = len(self.base.e2("act_menu"))
        self.tick(seconds)
        return len(self.base.e2("act_menu")) - before

    def menus(self):
        return self.base.e2("act_menu")[self.baseline:]

    def test_the_first_build_in_a_zone_steps_with_the_first_budget_and_a_later_one_with_8_ms(self):
        self.assertEqual(self.probe.act_menu.FIRST_BUDGET_MS, 20.0)
        self.tick(100.0)  # starts the build; the step comes with the next tick
        self.assertTrue(self.probe._MENU_FIRST)
        self.assertEqual(self.probe._MENU.budget_ms, self.probe.act_menu.FIRST_BUDGET_MS)
        for _ in range(5):
            if self.probe._MENU is None:
                break
            self.tick(100.0)
        self.assertIsNone(self.probe._MENU)
        self.tick(100.0 + self.probe.act_menu.REBUILD_S)  # the next build: her room is the same, the zone too
        self.assertFalse(self.probe._MENU_FIRST)
        self.assertEqual(self.probe._MENU.budget_ms, 8.0)

    def test_the_first_build_writes_what_it_has_every_fifteen_seconds_and_not_before(self):
        self.things = [acts._Thing(NEAR_ID, 2.0, [acts.ReadBook])] + self.far_things()
        self.tick(100.0)
        build = self.probe._MENU
        self.assertTrue(self.probe._MENU_FIRST)
        self.assertGreater(self.written_by(100.0), 0)  # her near part, as the far part starts (2.37.0)
        self.assertFalse(build.done)
        self.assertEqual(self.written_by(114.0), 0)  # 14 s: not yet
        self.assertGreater(self.written_by(115.0), 0)  # 15 s: the menu so far
        self.assertFalse(build.done)
        self.assertEqual(self.written_by(129.0), 0)
        self.assertGreater(self.written_by(130.0), 0)
        self.assertFalse(build.done)
        seconds = 130.0
        for _ in range(200):
            if build.done:
                break
            seconds += 1.0
            self.tick(seconds)
        self.assertTrue(build.done)
        self.assertEqual({row["menu_rev"] for row in self.menus()}, {1})
        # The whole menu follows when the build is done: its parts hold every object she has acts on.
        whole = [row for row in self.menus() if row["part"] is not None]
        objects = [item["object_id"] for row in whole[-(-(FAR_OBJECTS + 1) // 16):] for item in row["objects"]]
        self.assertEqual(sorted(objects, key=int), sorted([str(NEAR_ID)] + [str(100 + index)
                                                                              for index in range(FAR_OBJECTS)],
                                                          key=int))
        for row in self.base.rows("act_menu"):
            self.probe.schema.validate_record(row)

    def test_no_partial_menu_is_written_for_a_zone_she_has_left(self):
        self.things = [acts._Thing(NEAR_ID, 2.0, [acts.ReadBook])] + self.far_things()
        self.tick(100.0)
        self.assertGreater(self.written_by(100.0), 0)
        self.zone["current"] = object()  # she has moved on: the build's objects are another zone's
        self.assertEqual(self.written_by(115.0), 0)

    def test_a_later_build_in_the_same_zone_writes_no_partial_menu(self):
        self.tick(100.0)
        self.tick(100.0)  # the first build (one object, one act) is done
        self.assertIsNone(self.probe._MENU)
        self.things = [acts._Thing(NEAR_ID, 2.0, [acts.ReadBook])] + self.far_things()
        self.tick(100.0 + self.probe.act_menu.REBUILD_S)
        build = self.probe._MENU
        self.assertFalse(self.probe._MENU_FIRST)
        written = []
        seconds = 100.0 + self.probe.act_menu.REBUILD_S
        for _ in range(200):
            if build.done:
                break
            seconds += 15.0
            written.append(self.written_by(seconds))
        self.assertTrue(build.done)
        # 2.39.0 (W12 C1): the build's near part is written as its far part starts (the first step), then nothing
        # while it is built, then the whole menu when it is done.
        self.assertGreater(written[0], 0)
        self.assertEqual(written[1:-1], [0] * (len(written) - 2))
        self.assertGreater(written[-1], 0)  # the whole menu when it is done


if __name__ == "__main__":
    unittest.main()
