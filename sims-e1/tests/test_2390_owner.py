"""2.32.0 (PR15): an object of her 16 nearest that changes household owner (a visitor or an NPC taking it) is named,
with the household ids it went from and to. An object with no owner, or with the same owner, names nothing.
Invented ids only."""
import types
import unittest

import test_e2


class _Obj(object):
    def __init__(self, object_id, owner):
        self.id = object_id
        self.position = types.SimpleNamespace(x=1.0, y=0.0, z=0.0)
        self.level = 0
        self.zone_id = 1
        self.definition = types.SimpleNamespace(id=900 + object_id)
        self.state_component = types.SimpleNamespace(_states={})
        self.is_sim = False
        self._reservation_handlers = []
        self.household_owner_id = owner


class OwnerChangeTests(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.observers = self.base.probe.observers
        self.observers._OBJECTS_PREV.update(zone=None, wall_ms=None, classes=None, near={}, places={})
        room_of = self.observers._room
        self.addCleanup(setattr, self.observers, "_room", room_of)
        self.observers._room = lambda obj, position: "4"
        self.body = {"x": 0.0, "y": 0.0, "z": 0.0, "level": 0}

    def sample(self, objects, wall_ms):
        self.base.services.object_manager = lambda: types.SimpleNamespace(
            _objects={item.id: item for item in objects})
        return self.observers.read_object_events(1, self.body, wall_ms)

    def test_an_object_taken_by_another_household_is_named_with_both_owners(self):
        self.sample([_Obj(5, 10)], 1000)
        changed = self.sample([_Obj(5, 20)], 2000)["owner_changed"]
        self.assertEqual([(c["object_id"], c["from_owner"], c["to_owner"]) for c in changed], [("5", "10", "20")])

    def test_no_owner_and_the_same_owner_name_nothing(self):
        self.sample([_Obj(6, None)], 1000)
        self.assertEqual(self.sample([_Obj(6, 30)], 2000)["owner_changed"], [])
        self.sample([_Obj(7, 40)], 3000)
        self.assertEqual(self.sample([_Obj(7, 40)], 4000)["owner_changed"], [])

    def test_the_baseline_names_no_owner_change(self):
        self.sample([_Obj(8, 50)], 1000)
        events = self.sample([_Obj(8, 60)], 1000 + 60_000)
        self.assertTrue(events["baseline"])
        self.assertEqual(events["owner_changed"], [])


if __name__ == "__main__":
    unittest.main()
