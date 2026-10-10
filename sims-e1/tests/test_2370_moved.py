"""2.32.0 (HE5): an object of the 16 nearest that moved over 0.5 m, or into another room, between two samples is
named as moved (from and to room). A baseline names none, and an object someone holds is not moved by its own place.
The 16 nearest objects also name their room (near_rooms), which the helper uses for object_room facts."""
import types
import unittest

import test_e2


class _Obj(object):
    def __init__(self, object_id, x, z=0.0):
        self.id = object_id
        self.position = types.SimpleNamespace(x=x, y=0.0, z=z)
        self.level = 0
        self.zone_id = 1
        self.definition = types.SimpleNamespace(id=900 + object_id)
        self.state_component = types.SimpleNamespace(_states={})
        self.is_sim = False
        self._reservation_handlers = []


class MovedObjectTests(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.observers = self.base.probe.observers
        self.rooms = {}
        self.observers._OBJECTS_PREV.update(zone=None, wall_ms=None, classes=None, near={}, places={})
        room_of = self.observers._room
        self.addCleanup(setattr, self.observers, "_room", room_of)
        self.observers._room = lambda obj, position: self.rooms.get(obj.id)
        self.body = {"x": 0.0, "y": 0.0, "z": 0.0, "level": 0}

    def sample(self, objects, wall_ms):
        self.base.services.object_manager = lambda: types.SimpleNamespace(
            _objects={item.id: item for item in objects})
        return self.observers.read_object_events(1, self.body, wall_ms)

    def test_the_baseline_names_no_move_but_names_the_near_rooms(self):
        self.rooms = {1: "4"}
        events = self.sample([_Obj(1, 1.0)], 1000)
        self.assertTrue(events["baseline"])
        self.assertEqual(events["moved"], [])
        self.assertEqual(events["near_rooms"], [{"object_id": "1", "class": events["near_rooms"][0]["class"],
                                                  "room": "4"}])

    def test_an_object_moved_over_half_a_metre_is_named_with_its_rooms(self):
        self.rooms = {1: "4"}
        self.sample([_Obj(1, 1.0)], 1000)
        self.sample([_Obj(1, 2.0)], 2000)
        moved = self.sample([_Obj(1, 2.0)], 3000)["moved"]
        self.assertEqual(moved, [])
        self.rooms = {1: "4"}
        self.sample([_Obj(1, 1.0)], 4000)
        moved = self.sample([_Obj(1, 2.0)], 5000)["moved"]
        self.assertEqual([(m["object_id"], m["from_room"], m["to_room"]) for m in moved], [("1", "4", "4")])

    def test_a_small_step_in_the_same_room_is_not_a_move(self):
        self.rooms = {2: "4"}
        self.sample([_Obj(2, 1.0)], 1000)
        self.assertEqual(self.sample([_Obj(2, 1.3)], 2000)["moved"], [])

    def test_a_change_of_room_is_a_move_even_over_a_short_step(self):
        self.rooms = {3: "4"}
        self.sample([_Obj(3, 1.0)], 1000)
        self.rooms = {3: "5"}
        moved = self.sample([_Obj(3, 1.1)], 2000)["moved"]
        self.assertEqual([(m["from_room"], m["to_room"]) for m in moved], [("4", "5")])

    def test_an_object_someone_holds_is_not_moved_by_its_own_place(self):
        self.rooms = {4: "4"}
        held = _Obj(4, 1.0)
        held._reservation_handlers = [object()]
        self.sample([held], 1000)
        held = _Obj(4, 2.0)
        held._reservation_handlers = [object()]
        self.assertEqual(self.sample([held], 2000)["moved"], [])


if __name__ == "__main__":
    unittest.main()
