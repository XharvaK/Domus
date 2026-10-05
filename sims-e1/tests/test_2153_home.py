"""2.15.3: HOME is Ashley's own save (her household and lot). It is armed, sampled and
remembered across launches like the lab fork; the lab-only tools refuse it."""
import json
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

from test_2152_launch import _row, _save
from test_binding import FakeWriter, load_probe


class HomeTests(unittest.TestCase):

    def setUp(self):
        _, self.probe, _ = load_probe()
        self.root = self.probe._TELEMETRY_ROOT
        zone = object()
        sys.modules["services"].current_zone = lambda: zone
        self.assertTrue(self.probe._dispatch_arm("home"))
        self.assertTrue(self.probe._dispatch_start())
        self.probe.observers.poll_once = lambda session, name: _row(self.probe)
        self.probe._poll_tick()

    def test_home_is_armed_and_its_rows_are_valid(self):
        self.assertEqual(self.probe.get_status()["armed_name"], "HOME")
        rows = FakeWriter.instances[-1].rows
        opened = [row for row in rows if row.get("event_kind") == "session_open"]
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0]["attestation"]["armed_name"], "HOME")
        for row in rows:
            self.probe.schema.validate_record(row)

    def test_home_starts_by_itself_on_the_next_launch(self):
        with open(os.path.join(self.root, "autosample.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["armed_name"], "HOME")
        _, probe, _ = load_probe()
        probe._TELEMETRY_ROOT = self.root
        zone = object()
        sys.modules["services"].current_zone = lambda: zone
        _save(sys.modules["services"], "guid", "slot")
        self.assertTrue(probe._supervise_sampling())
        self.assertEqual((probe._STATE, probe._ARMED_NAME), ("SAMPLING", "HOME"))

    def test_the_lab_only_tools_refuse_home(self):
        for dispatch, code in ((self.probe._dispatch_preflight, "PREFLIGHT_NOT_LAB"),
                               (self.probe._dispatch_food_scan, "FOOD_NOT_LAB"),
                               (self.probe._dispatch_situation_scan, "SITUATION_NOT_LAB")):
            connection = types.SimpleNamespace(code=None)
            self.assertFalse(dispatch(connection))
            self.assertEqual(connection.code, code)

    def test_other_names_are_still_refused(self):
        _, probe, _ = load_probe()
        self.assertFalse(probe._dispatch_arm("my_save"))
        self.assertFalse(probe._cmd_arm("UNARMED"))
        with self.assertRaises(Exception):
            probe.schema.attestation("OTHER")


if __name__ == "__main__":
    unittest.main()
