"""C2 (Owner 2026-10-26, probe 2.41.3): a failed needs or moodlets read is never a silent []: read_senses names the
fault, and the body row carries it in missingness, so the helper can say senses are unavailable."""
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
from test_ds1_senses import FakeBuff, FakeBuffs, FakeCommodity, FakeSimInfo, FakeTracker, validate_senses


class RaisingComponentSim(FakeSimInfo):
    def get_component(self, kind):
        raise AttributeError("component moved")


class RaisingTracker(FakeTracker):
    def get_all_commodities(self):
        raise AttributeError("get_all_commodities moved")


class RaisingBuffsSim(FakeSimInfo):
    @property
    def Buffs(self):
        raise AttributeError("Buffs moved")

    @Buffs.setter
    def Buffs(self, value):
        pass


class BadBuff(object):
    @property
    def guid64(self):
        raise AttributeError("guid64 moved")


class SensesFaultTests(unittest.TestCase):
    def setUp(self):
        _, self.probe, _ = load_probe()
        self.observers = self.probe.observers

    def test_a_healthy_read_has_no_faults(self):
        sim = FakeSimInfo(FakeTracker([FakeCommodity(16656, 60, 1000)]), FakeBuffs([FakeBuff(111, "Happy", 2)]))
        senses = self.observers.read_senses(sim, 2000, None)
        self.assertEqual(senses["faults"], {})
        self.assertEqual(self.observers.senses_missingness(senses["faults"]), {})

    def test_a_needs_read_error_is_named(self):
        senses = self.observers.read_senses(RaisingComponentSim(FakeTracker()), 10, None)
        self.assertEqual(senses["motives"], [])
        self.assertEqual(senses["faults"]["motives"], "component_error")
        senses = self.observers.read_senses(FakeSimInfo(RaisingTracker()), 10, None)
        self.assertEqual(senses["faults"]["motives"], "commodities_error")
        senses = self.observers.read_senses(FakeSimInfo(None), 10, None)
        self.assertEqual(senses["faults"]["motives"], "no_component")

    def test_a_moodlets_read_error_is_named(self):
        senses = self.observers.read_senses(RaisingBuffsSim(FakeTracker([FakeCommodity(16656, 60, 1)])), 10, None)
        self.assertEqual(senses["sim_signals"], [])
        self.assertEqual(senses["faults"], {"sim_signals": "buffs_error"})
        sim = FakeSimInfo(FakeTracker([FakeCommodity(16656, 60, 1)]), FakeBuffs([BadBuff(), BadBuff()]))
        senses = self.observers.read_senses(sim, 10, None)
        self.assertEqual(senses["faults"], {"sim_signals": "entry_error"})

    def test_faults_go_in_the_rows_missingness_and_the_row_still_validates(self):
        missing = self.observers.senses_missingness({"motives": "no_tracker", "sim_signals": "buffs_error"})
        self.assertEqual(missing["motives"], {"status": "UNKNOWN", "detail": "senses unavailable: no_tracker"})
        self.assertEqual(missing["sim_signals"], {"status": "UNKNOWN", "detail": "senses unavailable: buffs_error"})
        senses = self.observers.read_senses(RaisingBuffsSim(None), 10, None)
        row = validate_senses(self.probe, senses)
        self.assertIsNotNone(row)

    def test_n1_some_unreadable_moodlets_are_a_named_partial_read(self):
        sim = FakeSimInfo(FakeTracker([FakeCommodity(16656, 60, 1)]),
                          FakeBuffs([FakeBuff(111, "Happy", 2), FakeBuff(112, "Happy", 1), BadBuff()]))
        senses = self.observers.read_senses(sim, 10, None)
        self.assertEqual(len(senses["sim_signals"]), 2)
        self.assertEqual(senses["faults"], {"sim_signals": "partial:1 unreadable"})
        missing = self.observers.senses_missingness(senses["faults"])
        self.assertEqual(missing["sim_signals"], {"status": "MISSING", "detail": "senses partial: 1 unreadable"})

    def test_n2_an_error_mid_iteration_keeps_what_was_read(self):
        class Breaking(FakeBuffs):
            def __iter__(self):
                yield FakeBuff(111, "Happy", 2)
                yield FakeBuff(112, "Happy", 1)
                raise RuntimeError("iteration broke")
        sim = FakeSimInfo(FakeTracker([FakeCommodity(16656, 60, 1)]), Breaking())
        senses = self.observers.read_senses(sim, 10, None)
        self.assertEqual(len(senses["sim_signals"]), 2)
        self.assertEqual(senses["faults"], {"sim_signals": "partial:iteration stopped"})

    def test_n3_senses_missingness_never_overwrites_an_existing_entry(self):
        existing = {"motives": {"status": "MISSING", "detail": "written by someone else"}}
        merged = self.observers.merge_senses_missingness(existing, {"motives": "no_tracker", "sim_signals": "buffs_error"})
        self.assertEqual(merged["motives"], {"status": "MISSING", "detail": "written by someone else"})
        self.assertEqual(merged["sim_signals"]["detail"], "senses unavailable: buffs_error")

    def test_the_probe_version_is_2_41_4(self):
        self.assertEqual(self.probe.schema.PROBE_VERSION, "2.41.6")


if __name__ == "__main__":
    unittest.main()
