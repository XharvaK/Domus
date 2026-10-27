"""R6: the two game callback ids the probe registers with are named constants (values unchanged; checked against
the 1.128 and 1.129 gameapi: zone_types.ZoneState.RUNNING == 6, indexed_manager.CallbackTypes.ON_OBJECT_ADD == 0)."""
import pathlib
import re
import unittest

from test_binding import load_probe

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "src" / "ashley_e1" / "probe.py"


class CallbackIdTests(unittest.TestCase):
    def test_values(self):
        _, probe, _ = load_probe()
        self.assertEqual(probe.ZONE_STATE_RUNNING, 6)
        self.assertEqual(probe.CALLBACK_ON_OBJECT_ADD, 0)

    def test_register_calls_use_the_names(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn("register_callback(ZONE_STATE_RUNNING,", text)
        self.assertIn("register_callback(CALLBACK_ON_OBJECT_ADD,", text)
        self.assertIsNone(re.search(r"register_callback\(\s*[0-9]", text))


if __name__ == "__main__":
    unittest.main()
