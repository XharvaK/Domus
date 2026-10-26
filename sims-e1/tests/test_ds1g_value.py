"""DS1G 2.3.3: live commodity stored value is _value, not _modified_value."""
import os
import sys
import unittest


SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from test_ds1f_motive import GUIDS, Component, Sim, Tracker, read


def forbid(name):
    def raising(*args, **kwargs):
        raise AssertionError("forbidden %s" % name)
    return raising


class LiveCommodity(object):
    """Value slot set. _modified_value declared and left unset."""

    __slots__ = (
        "guid64", "_value", "_modified_value", "_last_update",
        "min_value", "max_value", "get_value", "_update_value",
        "get_statistic", "commodity_tracker",
    )

    def __init__(self, guid, value, updated=1000, minimum=0, maximum=100,
                 modified=None, set_modified=False):
        self.guid64 = guid
        self._value = value
        self._last_update = updated
        self.min_value = minimum
        self.max_value = maximum
        if set_modified:
            self._modified_value = modified
        self.get_value = forbid("get_value")
        self._update_value = forbid("_update_value")
        self.get_statistic = forbid("get_statistic")
        self.commodity_tracker = forbid("commodity_tracker")


class ValueFieldTests(unittest.TestCase):
    def test_unset_modified_slot_still_yields_six_values(self):
        values = (10, 20, 30, 40, 51, 100)
        tracker = Tracker([
            LiveCommodity(guid, value) for guid, value in zip(GUIDS, values)])
        probe, motives = read(Sim(Component(tracker)))
        self.assertEqual(probe.observers.motive_diag()["matched"], 6)
        self.assertEqual(probe.observers.motive_diag()["stage"], "ok")
        got = dict((row["id"], row["value"]) for row in motives)
        self.assertEqual(got, {
            "hunger": 10, "energy": 20, "bladder": 30,
            "hygiene": 40, "fun": 51, "social": 100,
        })

    def test_stored_value_wins_when_modified_slot_is_also_set(self):
        tracker = Tracker([
            LiveCommodity(16656, 25, modified=90, set_modified=True)])
        probe, motives = read(Sim(Component(tracker)))
        self.assertEqual(motives[0]["value"], 25)
        self.assertEqual(probe.observers.motive_diag()["stage"], "ok")

    def test_fakes_raise_on_forbidden_commodity_methods(self):
        entry = LiveCommodity(16656, 25)
        for name in ("get_value", "_update_value", "get_statistic", "commodity_tracker"):
            with self.assertRaises(AssertionError):
                getattr(entry, name)()
