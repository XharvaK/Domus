"""2.27.0: a picker her own act opened is hers to answer; its window stays off the User's screen,
and is shown to the User only if she has not answered in time. 2.31.0: the same hold is built per
game send (_dialog_hook), so the fallback replays that send's original with its own arguments."""
import os
import sys
import types
import unittest

import test_2180_answer as answers

ACT = "a" * 32
OPENER = 900
OTHER = 4242


class HoldTests(unittest.TestCase):
    def setUp(self):
        self.case = answers.AnswerTests()
        self.case.setUp()
        self.probe = self.case.probe
        self.control = self.probe._E2
        self.module = sys.modules[type(self.control).__module__]
        self.saved_monotonic = self.module.time.monotonic
        self.now = [100.0]
        self.module.time.monotonic = lambda: self.now[0]
        self.shown = []
        test = self

        self.raise_on_send = False

        def original(dialog, dialog_type, dialog_msg, immediate=False):
            if test.raise_on_send:
                raise RuntimeError("send")
            test.shown.append((dialog.dialog_id, dialog_type, dialog_msg, immediate))

        self.hook = self.module._dialog_hook(original)
        self.module._HOLD.update(controller=self.control)
        self.picker = self.case.recipes
        self.picker.dialog_id = 555
        self.picker._resolver = types.SimpleNamespace(
            _interaction=types.SimpleNamespace(id=OPENER), super_interaction=None)

    def tearDown(self):
        self.module.time.monotonic = self.saved_monotonic
        self.module._HOLD.update(controller=None)
        self.case.tearDown()

    def mine(self):
        self.control.pushed[str(OPENER)] = {"act_id": ACT, "base": {}, "tuning_name": "cook",
                                            "interaction_id": str(OPENER), "seen": True, "misses": 0}

    def distribute(self):
        return self.hook(self.picker, "MSG_PICKER", "msg", immediate=True)

    def speed(self):
        return [(row["phase"], row["code"], row["detail"]) for row in self.case.case.base.e2("speed_event")]

    def test_her_own_picker_is_held_then_answered_unseen(self):
        self.case.case.ready()
        self.mine()
        self.distribute()
        self.assertEqual(self.shown, [])
        self.assertIn("555", self.control.held)
        self.assertEqual(self.speed()[-1], ("DIALOG_HELD", None, "dialog 555 act %s" % ACT))
        ok, connection = self.case.answer("13")
        self.assertTrue(ok, connection.lines)
        finished = self.case.case.events()[-1]
        self.assertEqual((finished["phase"], finished["detail"]), ("FINISHED", "held"))
        self.assertEqual(self.control.held, {})
        self.assertEqual(self.shown, [])

    def test_unanswered_in_time_it_is_shown_to_the_user(self):
        self.case.case.ready()
        self.mine()
        self.distribute()
        self.now[0] += self.module.PICKER_HOLD_S - 1
        self.control._release_held()
        self.assertEqual(self.shown, [])
        self.now[0] += 1
        self.control._release_held()
        self.assertEqual(self.shown, [(555, "MSG_PICKER", "msg", True)])
        self.assertEqual(self.speed()[-1], ("DIALOG_SHOWN", "TIMEOUT", "dialog 555 act %s" % ACT))
        self.assertEqual(self.control.held, {})

    def dialog_entry(self):
        opened = self.probe.observers.read_dialogs()["open"]
        return [item for item in opened if item["dialog_id"] == "555"][0]

    def test_a_held_window_says_how_long_is_left_until_the_fallback(self):
        # 2.39.0 (W12 A9): hold_left_s is the whole seconds until the fallback hands the window to the User.
        self.case.case.ready()
        self.mine()
        self.distribute()
        entry = self.dialog_entry()
        self.assertEqual((entry["held"], entry["cause"], entry["hold_left_s"]), (True, "hers", 180))
        self.now[0] += 30.5
        self.assertEqual(self.dialog_entry()["hold_left_s"], 149)

    def test_a_window_handed_to_the_user_reads_cause_user_and_no_hold(self):
        # 2.39.0 (W12 A4): released, it is the User's; the record never says hers after that.
        self.case.case.ready()
        self.mine()
        self.distribute()
        self.control._release_held(everything=True, code="STOP")
        entry = self.dialog_entry()
        self.assertEqual((entry["held"], entry["cause"], entry["hold_left_s"]), (False, "user", None))

    def test_a_send_that_fails_at_the_fallback_is_recorded_as_failed(self):
        # 2.39.0 (W12 A10): FAILED:<name> is a DIALOG_SHOWN code like the others.
        self.case.case.ready()
        self.mine()
        self.distribute()
        self.raise_on_send = True
        self.control._release_held(everything=True, code="STOP")
        self.assertEqual(self.speed()[-1], ("DIALOG_SHOWN", "FAILED:RuntimeError", "dialog 555 act %s" % ACT))
        self.assertEqual(self.control.held, {})

    def test_gone_dialogs_are_dropped_and_a_stop_shows_the_rest(self):
        self.case.case.ready()
        self.mine()
        self.distribute()
        del self.case.service._active_dialogs[555]
        self.control._release_held(everything=True, code="STOP")
        self.assertEqual(self.shown, [])
        self.case.service._active_dialogs[555] = self.picker
        self.distribute()
        self.control.on_stop("STOP")
        self.assertEqual(len(self.shown), 1)
        self.assertEqual(self.speed()[-1][:2], ("DIALOG_SHOWN", "STOP"))

    def test_other_pickers_show_as_always(self):
        self.case.case.ready()
        self.distribute()
        self.assertEqual(len(self.shown), 1)
        self.mine()
        self.picker._owner = lambda: types.SimpleNamespace(id=OTHER)
        self.picker._resolver = types.SimpleNamespace()
        self.distribute()
        self.assertEqual(len(self.shown), 2)
        self.picker._resolver = types.SimpleNamespace(
            _interaction=None, super_interaction=types.SimpleNamespace(id=OPENER))
        self.distribute()
        self.assertEqual(len(self.shown), 2)
        self.assertEqual(self.control.held["555"]["act_id"], ACT)

    def test_not_sampling_or_a_failing_check_shows_it(self):
        self.mine()
        self.distribute()
        self.assertEqual(len(self.shown), 1)
        self.case.case.ready()
        self.mine()
        self.picker._resolver = None
        self.distribute()
        self.assertEqual(len(self.shown), 2)
        for row in self.case.case.base.rows("speed_event"):
            self.probe.schema.validate_record(row)

    def test_install_replaces_the_game_send_once_and_restores_it(self):
        calls = []

        class _Base(object):
            def distribute_dialog(self, dialog_type, dialog_msg, immediate=False):
                calls.append((dialog_type, dialog_msg, immediate))

        game = _Base.distribute_dialog
        saved = self.module.UiDialogBase
        self.module.UiDialogBase = _Base
        self.module._HOLD.update(controller=None, saved=None)
        try:
            self.assertTrue(self.module._install_holds(self.control))
            self.assertTrue(self.module._install_holds(self.control))
            self.assertIs(self.module._HOLD["saved"]["base"], game)
            self.assertIsNot(_Base.distribute_dialog, game)
            _Base().distribute_dialog("T", "M", immediate=True)
            self.assertEqual(calls, [("T", "M", True)])
            self.module._restore_holds()
            self.assertIs(_Base.distribute_dialog, game)
            self.assertIsNone(self.module._HOLD["saved"])
        finally:
            self.module.UiDialogBase = saved
            self.module._restore_holds()

    def test_the_guard_allows_only_the_reviewed_replacements(self):
        tools = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
        sys.path.insert(0, tools)
        import check_guards
        allowed = ("from ui.ui_dialog import UiDialogBase\n"
                   "UiDialogBase.distribute_dialog = f\n")
        self.assertEqual(check_guards.scan_text(allowed, "e2_control.py"), [])
        self.assertEqual(len(check_guards.scan_text(allowed, "probe.py")), 2)
        for bad in ("import services\nservices.sim_info_manager = f\n",
                    "from sims.sim import Sim\nSim.update = f\n",
                    "from ui.ui_dialog import UiDialogBase\nUiDialogBase.show_dialog = f\n"):
            self.assertEqual(len(check_guards.scan_text(bad, "e2_control.py")), 1, bad)
        self.assertEqual(check_guards.scan_text("self.held = {}\nitem.x = 1\n", "e2_control.py"), [])


if __name__ == "__main__":
    unittest.main()
