"""DS1F 2.3.2: pure motive route and motive-read diagnostics."""
import os
import sys
import types
import unittest


SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from test_binding import load_probe


GUIDS = (16656, 16654, 16652, 16657, 16655, 16658)


def install_component_type():
    objects = sys.modules["objects"]
    objects.__path__ = []
    components = types.ModuleType("objects.components")
    components.__path__ = []
    component_types = types.ModuleType("objects.components.types")
    component_types.STATISTIC_COMPONENT = "STATISTIC_COMPONENT"
    sys.modules["objects.components"] = components
    sys.modules["objects.components.types"] = component_types
    return component_types.STATISTIC_COMPONENT


def forbid(name):
    def raising(*args, **kwargs):
        raise AssertionError("forbidden %s" % name)
    return raising


class Commodity:
    def __init__(self, guid, value=25, updated=1000, minimum=0, maximum=100):
        self.guid64 = guid
        self._modified_value = value
        self._last_update = updated
        self.default_value = value
        self.min_value = minimum
        self.max_value = maximum
        self.get_statistic = forbid("get_statistic")
        self.get_value = forbid("get_value")

    def drop(self, field):
        delattr(self, field)


class Component:
    def __init__(self, tracker):
        self.calls = []
        self._tracker = tracker
        self.get_statistic = forbid("component.get_statistic")

    def get_commodity_tracker(self, create=True):
        self.calls.append(create)
        return self._tracker


class Tracker:
    def __init__(self, commodities):
        self._commodities = list(commodities)
        self.get_statistic = forbid("tracker.get_statistic")
        self.get_tracker = forbid("get_tracker")

    def get_all_commodities(self):
        return tuple(self._commodities)


class Sim:
    def __init__(self, component):
        self._component = component
        self.get_statistic = forbid("sim.get_statistic")
        self.asked = []

    def get_component(self, kind):
        self.asked.append(kind)
        return self._component

    @property
    def commodity_tracker(self):
        raise AssertionError("forbidden commodity_tracker")


def read(sim, ticks=1100):
    _, probe, _ = load_probe()
    install_component_type()
    motives = probe.observers.read_motives(sim, ticks)
    return probe, motives


class MotiveRouteTests(unittest.TestCase):
    def test_pure_route_create_false_and_forbidden_names_untouched(self):
        kind_holder = {}

        class CheckingSim(Sim):
            def get_component(self, kind):
                kind_holder["kind"] = kind
                return self._component

        tracker = Tracker([Commodity(16656)])
        component = Component(tracker)
        sim = CheckingSim(component)
        probe, motives = read(sim)
        self.assertEqual(motives[0]["id"], "hunger")
        self.assertEqual(component.calls, [False])
        self.assertEqual(kind_holder["kind"], "STATISTIC_COMPONENT")
        self.assertEqual(probe.observers.motive_diag()["stage"], "ok")

    def test_no_component_and_no_tracker(self):
        probe, motives = read(Sim(None))
        self.assertEqual(motives, [])
        self.assertEqual(probe.observers.motive_diag()["stage"], "no_component")
        probe, motives = read(Sim(Component(None)))
        self.assertEqual(motives, [])
        self.assertEqual(probe.observers.motive_diag()["stage"], "no_tracker")

    def test_no_guid_match_bounds_seen_guids(self):
        commodities = [Commodity(1000 + index) for index in range(45)]
        probe, motives = read(Sim(Component(Tracker(commodities))))
        diag = probe.observers.motive_diag()
        self.assertEqual(motives, [])
        self.assertEqual(diag["stage"], "no_guid_match")
        self.assertEqual(diag["matched"], 0)
        self.assertEqual(len(diag["seen_guids"]), 40)
        self.assertEqual(diag["seen_guids"], sorted(diag["seen_guids"]))
        self.assertEqual(diag["seen_guids"][0], 1000)

    def test_missing_last_update_names_the_field(self):
        commodity = Commodity(16656)
        commodity.drop("_last_update")
        probe, motives = read(Sim(Component(Tracker([commodity]))))
        self.assertEqual(motives, [])
        self.assertEqual(probe.observers.motive_diag()["stage"], "row_error:_last_update")

    def test_six_motives_still_read(self):
        tracker = Tracker([Commodity(guid, 25, 1000) for guid in GUIDS])
        probe, motives = read(Sim(Component(tracker)))
        self.assertEqual(len(motives), 6)
        self.assertEqual(probe.observers.motive_diag()["matched"], 6)
        self.assertEqual(probe.observers.motive_diag()["stage"], "ok")

    def test_status_reply_validates_motive_diag(self):
        probe, _ = read(Sim(Component(Tracker([Commodity(16656)]))))
        status = probe._inbox_status()
        probe.schema.validate_motive_diag(status["motive_diag"])
        self.assertEqual(status["motive_diag"]["matched"], 1)


if __name__ == "__main__":
    unittest.main()
