"""2.30.0: she sees what her Sim wants and fears now, read from the game's whim slots with plain reads."""
import types
import unittest

import test_215_senses as senses


class _Factory(object):
    def __init__(self, key):
        self._string_id = key


class _TimeOfDay(object):
    def __init__(self, hour, minute):
        self._hm = (hour, minute)

    def hour(self):
        return self._hm[0]

    def minute(self):
        return self._hm[1]


class FakeWant_ReadBook(object):
    pass


class FakeFear_BeingAlone(object):
    pass


class _Goal(object):
    def __init__(self, name_key, tip_key=None, count=0, iterations=1, locked=False, expiry=None):
        self.display_name = _Factory(name_key)
        self.display_tooltip = None if tip_key is None else _Factory(tip_key)
        self._count, self._iterations, self._locked = count, iterations, locked
        self.expiration_time = expiry

    @property
    def score(self):
        raise AssertionError("goal.score runs tests; never read it")


class _Unreadable(object):
    @property
    def goal_instance(self):
        raise RuntimeError("unreadable slot")


def _slot(whim, goal, kind="SHORT_TERM"):
    return types.SimpleNamespace(whim=whim, goal_instance=goal, whim_type=types.SimpleNamespace(name=kind))


class WantsTests(unittest.TestCase):
    def setUp(self):
        senses.SelfTests.setUp(self)

    def _info(self, slots):
        info = senses.SelfTests._sim_info(self)
        info._whim_tracker = types.SimpleNamespace(_whim_slots=slots)
        return info

    def test_wants_and_fears_fears_first(self):
        slots = [
            _slot(FakeWant_ReadBook, _Goal(0x8001, 0x8101, count=1, iterations=3, locked=True, expiry=_TimeOfDay(22, 30))),
            _slot(None, None),
            _slot(FakeFear_BeingAlone, _Goal(0x8002), kind="CONFRONTATION"),
        ]
        wants = self.probe.observers.read_self(self._info(slots))["wants"]
        self.assertEqual(wants, [
            {"want": "FakeFear_BeingAlone", "text_key": str(0x8002), "tip_key": None, "fear": True,
             "locked": False, "done": 0, "of": 1, "until": None},
            {"want": "FakeWant_ReadBook", "text_key": str(0x8001), "tip_key": str(0x8101), "fear": False,
             "locked": True, "done": 1, "of": 3, "until": [22, 30]}])

    def test_one_bad_slot_never_drops_the_rest(self):
        slots = [_Unreadable(), _slot(FakeWant_ReadBook, _Goal(0x8001, expiry=_TimeOfDay(25, 0)))]
        wants = self.probe.observers.read_self(self._info(slots))["wants"]
        self.assertEqual([(item["want"], item["until"]) for item in wants], [("FakeWant_ReadBook", None)])

    def test_no_tracker_is_none_and_empty_slots_are_an_empty_list(self):
        info = senses.SelfTests._sim_info(self)
        info._whim_tracker = None
        self.assertIsNone(self.probe.observers.read_self(info)["wants"])
        self.assertEqual(self.probe.observers.read_self(self._info([_slot(None, None)]))["wants"], [])

    def test_at_most_eight(self):
        slots = [_slot(type("FakeWant_%d" % i, (object,), {}), _Goal(0x8000 + i)) for i in range(12)]
        self.assertEqual(len(self.probe.observers.read_self(self._info(slots))["wants"]), 8)

    def test_schema_13_accepts_wants_and_rejects_a_bad_entry(self):
        ds3 = senses.ds3
        ds3.PollOnceTests.setUp(self)
        self.lab._whim_tracker = types.SimpleNamespace(
            _whim_slots=[_slot(FakeWant_ReadBook, _Goal(0x8001, 0x8101, expiry=_TimeOfDay(9, 0)))])
        row = ds3.PollOnceTests.row(self)
        self.assertEqual(row["schema_version"], 19)
        self.assertEqual(row["self"]["wants"][0]["until"], [9, 0])
        self.probe.schema.validate_record(row)
        for bad in ({"fear": "yes"}, {"until": [24, 0]}, {"extra": 1}, {"done": 1.5}):
            broken = dict(row, self=dict(row["self"], wants=[dict(row["self"]["wants"][0], **bad)]))
            with self.assertRaises(Exception):
                self.probe.schema.validate_record(broken)


if __name__ == "__main__":
    unittest.main()
