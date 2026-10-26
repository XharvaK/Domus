"""2.32.0 (HE7): the notable conditions of the 16 nearest objects (spoiled, dirty, broken, burning ...) are named on
every sample and on the zone baseline. A negated state ("Not Burning") is not notable. Invented names only."""
import types
import unittest

import test_e2


class _State(object):
    def __init__(self, name):
        self.__name__ = name


class _Obj(object):
    def __init__(self, object_id, x, states):
        self.id = object_id
        self.position = types.SimpleNamespace(x=x, y=0.0, z=0.0)
        self.level = 0
        self.zone_id = 1
        self.definition = types.SimpleNamespace(id=900 + object_id)
        self.state_component = types.SimpleNamespace(_states={_State(key): _State(value)
                                                              for key, value in states.items()})
        self.is_sim = False


class NearConditionTests(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.observers = self.base.probe.observers
        self.schema = self.base.probe.schema

    def test_only_the_notable_last_words_count_and_a_negation_never_does(self):
        notable = self.observers._notable_state
        self.assertTrue(notable("Freshness_Spoiled"))
        self.assertTrue(notable("Cleanliness_Dirty"))
        self.assertFalse(notable("FireState_Not_Burning"))
        self.assertFalse(notable("Brokenness_Unbroken"))
        self.assertFalse(notable("Freshness_Fresh"))
        self.assertFalse(notable(None))

    def test_the_sixteen_nearest_objects_name_their_notable_states_on_every_sample(self):
        objects = {1: _Obj(1, 0.5, {"Freshness": "Freshness_Spoiled"}),
                   2: _Obj(2, 1.0, {"Cleanliness": "Cleanliness_Fresh"}),
                   3: _Obj(3, 30.0, {"Cleanliness": "Cleanliness_Dirty"})}
        self.base.services.object_manager = lambda: types.SimpleNamespace(_objects=objects)
        body = {"x": 0.0, "y": 0.0, "z": 0.0, "level": 0}
        baseline = self.observers.read_object_events(1, body, 1000)
        self.assertTrue(baseline["baseline"])
        # Object 3 is 30 m away but among the 16 nearest in this small lot, and it is dirty; 2 is fresh.
        self.assertEqual([item["object_id"] for item in baseline["near_conditions"]], ["1", "3"])
        self.assertEqual(baseline["near_conditions"][0]["states"][0]["value"], "Freshness_Spoiled")
        later = self.observers.read_object_events(1, body, 2000)
        self.assertFalse(later["baseline"])
        self.assertEqual([item["object_id"] for item in later["near_conditions"]], ["1", "3"])

    def test_the_condition_list_is_compact_and_capped(self):
        objects = {index: _Obj(index, 0.1 * index, {"K%d" % s: "Wear_Dirty" for s in range(9)})
                   for index in range(1, 25)}
        self.base.services.object_manager = lambda: types.SimpleNamespace(_objects=objects)
        events = self.observers.read_object_events(1, {"x": 0.0, "y": 0.0, "z": 0.0, "level": 0}, 1000)
        self.assertEqual(len(events["near_conditions"]), self.schema.MAX_NEAR_CONDITIONS)
        self.assertTrue(all(len(item["states"]) <= self.schema.MAX_NEAR_STATES
                            for item in events["near_conditions"]))


if __name__ == "__main__":
    unittest.main()
