"""DA5 observe-only calibrate. Fakes only."""
import os
import sys
import unittest
from unittest import mock

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from test_binding import load_probe
from test_d10 import command
from test_e2 import AUTO, CHAIR, PIE, _entry, _row


class CalibrateTests(unittest.TestCase):
    def setUp(self):
        _, self.p, _ = load_probe()
        self.rows = []
        self.p._E2._emit_row = self.rows.append
        self.p._TELEMETRY_SESSION_ID = "sess"
        self.reply = self.p._InboxReply("agent:coder")

    def test_unarmed_calibrate_refuses_like_start(self):
        self.assertIsNone(self.p._ARMED_NAME)
        self.assertFalse(self.p._cmd_start())
        self.assertFalse(self.p._inbox_dispatch(command("calibrate"), self.reply))
        self.assertFalse(self.p._CALIBRATE)
        self.assertIsNone(self.reply.code)

    def test_armed_sets_flag_and_start_row(self):
        self.p._ARMED_NAME = "LAB_E1"
        with mock.patch.object(self.p, "_current_clock_speed", return_value="SPEED3"):
            self.assertTrue(self.p._inbox_dispatch(command("calibrate"), self.reply))
        self.assertTrue(self.p._CALIBRATE)
        self.assertEqual(self.rows[-1]["e2"]["phase"], "CALIBRATE_START")
        self.assertIn("clock_speed=SPEED3", self.rows[-1]["e2"]["detail"])
        self.assertIn("armed_name=LAB_E1", self.rows[-1]["e2"]["detail"])
        self.assertTrue(self.p._inbox_status()["calibrate"])
        self.assertTrue(self.p.get_status()["calibrate"])

    def test_actuation_refused_without_side_effects(self):
        self.p._ARMED_NAME = "LAB_E1"
        self.p._CALIBRATE = True
        calls = []
        self.p._E2.cmd_prepare = lambda *a, **k: calls.append("prepare") or True
        self.p._E2.cmd_sit = lambda *a, **k: calls.append("sit") or True
        self.p._E2.cmd_pause = lambda *a, **k: calls.append("pause") or True
        self.p._E2.cmd_release = lambda *a, **k: calls.append("release") or True
        shapes = {
            "prepare": {"object_id": "123"},
            "sit": {"token": "a" * 16},
            "sit_trial": {"object_id": "123"},
            "pause": {},
            "release": {},
        }
        for name, args in shapes.items():
            reply = self.p._InboxReply("agent:coder")
            self.assertFalse(self.p._inbox_dispatch(command(name, args), reply), name)
            self.assertEqual(reply.code, "CALIBRATE_OBSERVE_ONLY", name)
        self.assertEqual(calls, [])
        self.assertEqual(self.p._INBOX_VERDICTS[-1]["code"], "CALIBRATE_OBSERVE_ONLY")

    def test_disarm_and_rearm_clear_flag(self):
        self.assertTrue(self.p._cmd_arm("LAB_E1"))
        self.p._CALIBRATE = True
        self.assertTrue(self.p._cmd_disarm())
        self.assertFalse(self.p._CALIBRATE)
        self.assertIsNone(self.p._ARMED_NAME)
        self.p._WRITER.finish()
        self.p._CALIBRATE = True
        self.assertTrue(self.p._cmd_arm("LAB_E1"))
        self.assertFalse(self.p._CALIBRATE)

    def test_speed_change_row(self):
        self.p._CALIBRATE = True
        self.p._CAL_SPEED = "NORMAL"
        self.p._note_calibrate_speed({"event_kind": "presence_snapshot",
                                      "game": {"clock_speed": "NORMAL", "ticks": 1}})
        self.assertEqual(self.rows, [])
        self.p._note_calibrate_speed({"event_kind": "presence_snapshot",
                                      "game": {"clock_speed": "SPEED3", "ticks": 9}})
        self.assertEqual(self.rows[-1]["e2"]["phase"], "CALIBRATE_SPEED")
        self.assertEqual(self.rows[-1]["e2"]["detail"], "from=NORMAL to=SPEED3 ticks=9")
        self.p.schema.validate_record(self.rows[-1])


class AutonomyGuardTests(unittest.TestCase):
    def test_autonomy_does_not_teach_a_signature(self):
        _, probe, _ = load_probe()
        from ashley_e1 import e2_registry
        learner = e2_registry.SignatureLearner()
        auto = _entry("50", AUTO, target=CHAIR, affordance_id="31564")
        self.assertIsNone(learner.observe(_row(1, [auto]), set()))
        self.assertIsNone(learner.observe(_row(3, [], "sitSingle", CHAIR), set()))
        self.assertEqual(learner.signatures, {})
        self.assertFalse(hasattr(learner, "exercised"))
        pie = e2_registry.SignatureLearner()
        click = _entry("50", PIE, target=CHAIR, affordance_id="31564")
        pie.observe(_row(1, [click]), set())
        self.assertEqual(pie.observe(_row(3, [], "sitSingle", CHAIR), set()),
                         (CHAIR, "sitSingle"))


if __name__ == "__main__":
    unittest.main()
