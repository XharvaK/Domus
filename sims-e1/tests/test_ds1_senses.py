"""DS1-2 red-first: motives, moodlets, mood reads with tripwire."""
import os
import sys
import types
import unittest


SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)
if "ashley_e1" not in sys.modules:
    package = types.ModuleType("ashley_e1")
    package.__path__ = [os.path.join(SRC, "ashley_e1")]
    sys.modules["ashley_e1"] = package

from test_binding import load_probe


FORBIDDEN = (
    "get_statistic", "get_value", "get_timeout_time",
    "get_active_whimset_data", "potential_interactions", "_update_value",
)


def hostile(name):
    def raising(*args, **kwargs):
        raise AssertionError("forbidden call %s executed" % name)
    return raising


class FakeBuff:
    def __init__(self, guid, mood_type=None, mood_weight=0):
        self.guid64 = guid
        self.mood_type = mood_type
        self.mood_weight = mood_weight


class FakeBuffs:
    def __init__(self, entries=(), mood=None, intensity=None):
        self._entries = list(entries)
        self._mood = mood
        self._intensity = intensity
        for name in FORBIDDEN:
            setattr(self, name, hostile("Buffs.%s" % name))

    def __iter__(self):
        return iter(self._entries)

    def get_mood(self):
        return self._mood

    def get_mood_intensity(self):
        return self._intensity


class FakeCommodity:
    def __init__(self, guid, value, updated, minimum=0, maximum=100):
        self.guid64 = guid
        self._value = value
        self._last_update = updated
        self.min_value = minimum
        self.max_value = maximum
        for name in FORBIDDEN:
            setattr(self, name, hostile("commodity.%s" % name))


class FakeTracker:
    def __init__(self, commodities=()):
        self._commodities = list(commodities)
        for name in FORBIDDEN:
            setattr(self, name, hostile("tracker.%s" % name))

    def get_all_commodities(self):
        return list(self._commodities)


class FakeComponent:
    def __init__(self, tracker):
        self._tracker = tracker

    def get_commodity_tracker(self, create=True):
        if create:
            raise AssertionError("get_commodity_tracker create")
        return self._tracker


class FakeSimInfo:
    def __init__(self, tracker=None, buffs=None):
        self._component = None if tracker is None else FakeComponent(tracker)
        self.Buffs = buffs or FakeBuffs()
        for name in FORBIDDEN:
            setattr(self, name, hostile("sim_info.%s" % name))

    def get_component(self, kind):
        del kind
        return self._component

    @property
    def commodity_tracker(self):
        raise AssertionError("forbidden commodity_tracker")


def make_row(context, sim_info):
    _, probe, _ = load_probe()
    return probe.observers.read_senses(sim_info, context["ticks"], context)


def validate_senses(probe, senses):
    row = probe.schema.make_record(
        "presence_snapshot",
        telemetry_session_id="00000000-0000-4000-8000-000000000031",
        wall_timestamp_ms=1, monotonic_ns=2, observation_complete=True,
        attestation=probe.schema.attestation("LAB_E1"),
        save={"save_slot_guid": "g", "slot_id": "s"},
        body={"sim_id": "sim", "instantiated": True, "is_selectable": True,
              "is_selected": None, "posture": None},
        interactions={"observed": [], "queue_truncated": False,
                      "running_truncated": False, "observation_complete": True},
        presence=[], social=[], mood=senses["mood"], motives=senses["motives"],
        sim_signals=senses["sim_signals"],
    )
    return probe.schema.validate_record(row)


class SensesTests(unittest.TestCase):
    def test_full_poll_against_tripwire_raises_nothing(self):
        _, probe, _ = load_probe()
        tracker = FakeTracker([FakeCommodity(16656, 60, 1000)])
        sim_info = FakeSimInfo(tracker, FakeBuffs([FakeBuff(111, "Happy", 2)],
                                                  mood=FakeBuff(999), intensity=3))
        row = probe.observers.read_senses(sim_info, 2000, {"ticks": 2000})
        validate_senses(probe, row)

    def test_each_forbidden_name_raises_when_called(self):
        tracker = FakeTracker([FakeCommodity(16656, 60, 1000)])
        sim_info = FakeSimInfo(tracker, FakeBuffs([FakeBuff(111)]))
        for name in ("get_statistic", "get_value", "potential_interactions"):
            with self.subTest(name=name):
                with self.assertRaises(AssertionError):
                    getattr(tracker if name != "potential_interactions" else sim_info, name)()
        with self.assertRaises(AssertionError):
            sim_info.Buffs.get_timeout_time()
        with self.assertRaises(AssertionError):
            sim_info.Buffs.get_active_whimset_data()

    def test_six_motives_found_by_guid_and_normalized(self):
        guids = (16656, 16654, 16652, 16657, 16655, 16658)
        tracker = FakeTracker([FakeCommodity(guid, 25, 1000) for guid in guids])
        row = make_row({"ticks": 1100}, FakeSimInfo(tracker))
        self.assertEqual(len(row["motives"]), 6)
        for motive in row["motives"]:
            self.assertEqual((motive["value"], motive["band"], motive["age_ticks"]),
                             (25, "low", 100))

    def test_motive_boundaries_and_none_cases(self):
        for value, band in ((0, "distress"), (20, "distress"), (21, "low"),
                            (50, "low"), (51, "ok"), (100, "ok")):
            with self.subTest(value=value):
                tracker = FakeTracker([FakeCommodity(16656, value, 5)])
                row = make_row({"ticks": 10}, FakeSimInfo(tracker))
                self.assertEqual((row["motives"][0]["value"], row["motives"][0]["band"]),
                                 (value, band))
        tracker = FakeTracker([FakeCommodity(16656, 7, 5, minimum=50, maximum=50)])
        row = make_row({"ticks": 10}, FakeSimInfo(tracker))
        self.assertIsNone(row["motives"][0]["value"])
        tracker = FakeTracker([FakeCommodity(99999, 50, 5)])
        row = make_row({"ticks": 10}, FakeSimInfo(tracker))
        self.assertEqual(row["motives"], [])
        row = make_row({"ticks": 10}, FakeSimInfo(None))
        self.assertEqual(row["motives"], [])
        entry = FakeCommodity(16656, None, 5)
        entry.default_value = 42
        tracker = FakeTracker([entry])
        row = make_row({"ticks": 10}, FakeSimInfo(tracker))
        self.assertEqual(row["motives"], [])

    def test_moodlets_capped_weighted_and_row_failures_skipped(self):
        entries = [FakeBuff(1000 + i, "Happy", i) for i in range(17)]
        row = make_row({"ticks": 10}, FakeSimInfo(FakeTracker(), FakeBuffs(entries)))
        self.assertEqual(len(row["sim_signals"]), 16)
        self.assertEqual(row["sim_signals"][0]["magnitude"], "w:0")
        self.assertIsNone(row["sim_signals"][0]["game_text"])

        class Broken(object):
            def __init__(self):
                self.guid64 = 1

            @property
            def mood_weight(self):
                raise RuntimeError("boom")

        row = make_row({"ticks": 10},
                       FakeSimInfo(FakeTracker(), FakeBuffs([Broken(), FakeBuff(2, "Sad", 1)])))
        self.assertEqual(len(row["sim_signals"]), 1)
        self.assertEqual(row["sim_signals"][0]["tuning_id"], "2")

    def test_mood_present_and_none(self):
        row = make_row({"ticks": 10},
                       FakeSimInfo(FakeTracker(), FakeBuffs(mood=FakeBuff(777), intensity=4)))
        self.assertEqual(row["mood"]["type"], "777")
        self.assertEqual(row["mood"]["intensity"], 4)
        self.assertIn("name", row["mood"])
        row = make_row({"ticks": 10}, FakeSimInfo(FakeTracker(), FakeBuffs()))
        self.assertIsNone(row["mood"])


if __name__ == "__main__":
    unittest.main()
