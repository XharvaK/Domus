"""2.23.0: her answer closes the client's window and lifts only the pause that dialog made."""
import sys
import unittest

import test_2180_answer as answers


class _Msg(object):
    def __init__(self):
        self.dialog_id = None


class ClosePauseTests(unittest.TestCase):
    def setUp(self):
        self.case = answers.AnswerTests()
        self.case.setUp()
        self.probe = self.case.probe
        self.observers = self.probe.observers
        self.observers._DIALOG_SPEED.clear()
        self.observers._SPEED_SEEN = None
        self.observers._DIALOGS_OPEN = {}
        self.module = sys.modules[type(self.probe._E2).__module__]
        self.saved = (self.module.Distributor, self.module.Dialog_pb2, self.module.Consts_pb2)
        self.clock = self.case.case.base.services.game_clock_service()
        self.pop_calls = []
        self.set_calls = []
        self.events = []
        self.pop_result = object()
        self.pop_error = None
        self.close_error = None
        self.module.GameSpeedChangeSource.UI_MODAL = "UI_MODAL"
        self._saved_pop = getattr(self.clock, "pop_speed", None)
        self._saved_set = getattr(self.clock, "set_clock_speed", None)
        test = self

        def pop_speed(speed, source=None, reason="", immediate=False):
            test.pop_calls.append((speed, source, immediate))
            if test.pop_error is not None:
                raise test.pop_error
            return test.pop_result

        def set_clock_speed(speed, source=None, reason="", immediate=False):
            test.set_calls.append((speed, source, immediate))
            return True

        self.clock.pop_speed = pop_speed
        self.clock.set_clock_speed = set_clock_speed
        self._install_close()

    def tearDown(self):
        self.module.Distributor, self.module.Dialog_pb2, self.module.Consts_pb2 = self.saved
        if self._saved_pop is None:
            del self.clock.pop_speed
        else:
            self.clock.pop_speed = self._saved_pop
        if self._saved_set is None:
            del self.clock.set_clock_speed
        else:
            self.clock.set_clock_speed = self._saved_set
        self.observers._DIALOG_SPEED.clear()
        self.observers._SPEED_SEEN = None
        self.observers._DIALOGS_OPEN = {}
        self.case.tearDown()

    def _install_close(self):
        test = self

        class _Dialogs(object):
            def UiDialogCloseRequest(self):
                if test.close_error is not None:
                    raise test.close_error
                return _Msg()

        class _Consts(object):
            MSG_UI_DIALOG_CLOSE = "MSG_UI_DIALOG_CLOSE"

        class _Dist(object):
            def add_event(self, op, message, immediate=False):
                test.events.append((op, getattr(message, "dialog_id", None), immediate))

            def process_events(self):
                test.events.append("process_events")

        self.module.Dialog_pb2 = _Dialogs()
        self.module.Consts_pb2 = _Consts()
        holder = _Dist()
        self.module.Distributor = type("Distributor", (), {"instance": staticmethod(lambda: holder)})
        self.case.recipes.dialog_id = 555

    def speed(self, name):
        self.case.case.base.clock_speed = name

    def see(self, *dialog_ids):
        service = self.case.service
        service._active_dialogs.clear()
        for dialog_id in dialog_ids:
            picker = self.case.recipes if dialog_id == 555 else answers._Picker(answers.HER, [])
            picker.dialog_id = dialog_id
            service._active_dialogs[dialog_id] = picker
        self.observers.read_dialogs()

    def paused_after_normal(self):
        self.speed("NORMAL")
        self.see()
        self.speed("PAUSED")
        self.see(555)
        self.assertEqual(self.observers.dialog_prior_speed("555"), "NORMAL")

    def answer(self, pick="13"):
        self.case.case.ready()
        self.case.hold_recipes()  # 2.31.0 (W4): her picker is a held window
        return self.case.answer(pick)

    def finished(self):
        event = self.case.case.events()[-1]
        self.assertEqual(event["phase"], "FINISHED")
        self.assertEqual(event["finishing_type"], "ANSWERED")
        for row in self.case.case.base.rows("act_event"):
            self.probe.schema.validate_record(row)
        return event

    def closes(self):
        sent = [item for item in self.events if item != "process_events"]
        self.assertEqual(sent, [("MSG_UI_DIALOG_CLOSE", 555, True)])
        self.assertEqual(self.events.count("process_events"), 1)

    def test_an_accepted_answer_closes_once_and_releases_the_dialog_pause(self):
        self.paused_after_normal()
        ok, connection = self.answer()
        self.assertTrue(ok, connection.lines)
        self.closes()
        self.assertEqual(self.pop_calls, [("PAUSED", "UI_MODAL", True)])
        self.assertEqual(self.set_calls, [])
        event = self.finished()
        self.assertEqual(event["closed"], True)
        self.assertEqual(event["resumed"], "released")
        self.see()
        self.assertNotIn("555", self.observers._DIALOG_SPEED)

    def test_a_missing_request_leaves_the_clock_alone_because_the_pause_is_not_hers(self):
        # 2.39.0 (W12 A6): with no UI_MODAL request of hers, the pause in place is the User's (or another
        # mod's); restoring the speed from before the dialog would lift it.
        self.pop_result = None
        self.paused_after_normal()
        ok, connection = self.answer()
        self.assertTrue(ok, connection.lines)
        self.closes()
        self.assertEqual(len(self.pop_calls), 1)
        self.assertEqual(self.set_calls, [])
        event = self.finished()
        self.assertEqual((event["closed"], event["resumed"]), (True, "not_hers"))

    def test_a_pause_already_in_place_is_never_lifted(self):
        self.speed("PAUSED")
        self.see()
        self.see(555)
        self.assertEqual(self.observers.dialog_prior_speed("555"), "PAUSED")
        ok, _ = self.answer()
        self.assertTrue(ok)
        self.closes()
        self.assertEqual(self.pop_calls, [])
        self.assertEqual(self.set_calls, [])
        self.assertEqual(self.finished()["resumed"], "player_paused")

    def test_another_open_dialog_keeps_the_pause(self):
        self.paused_after_normal()
        self.case.service._active_dialogs[556] = answers._Picker(answers.HER, [])
        ok, _ = self.answer()
        self.assertTrue(ok)
        self.assertEqual(self.pop_calls, [])
        self.assertEqual(self.finished()["resumed"], "other_dialog_open")

    def test_a_clock_that_is_not_paused_is_left_alone(self):
        self.paused_after_normal()
        self.speed("NORMAL")
        ok, _ = self.answer()
        self.assertTrue(ok)
        self.assertEqual(self.pop_calls, [])
        self.assertEqual(self.finished()["resumed"], "not_paused")

    def test_a_close_failure_still_finishes_the_answer(self):
        self.close_error = RuntimeError("close")
        self.paused_after_normal()
        ok, connection = self.answer()
        self.assertTrue(ok, connection.lines)
        self.assertEqual(connection.lines[-1].startswith("ACT_ANSWERED "), True)
        self.assertEqual([item for item in self.events if item != "process_events"], [])
        event = self.finished()
        self.assertEqual(event["closed"], False)
        self.assertEqual(event["resumed"], "released")

    def test_a_resume_failure_still_finishes_the_answer(self):
        self.pop_error = RuntimeError("resume")
        self.paused_after_normal()
        ok, connection = self.answer()
        self.assertTrue(ok, connection.lines)
        event = self.finished()
        self.assertEqual(event["closed"], True)
        self.assertEqual(event["resumed"], "failed")

    def test_cancel_closes_the_window_too(self):
        self.paused_after_normal()
        ok, connection = self.answer("cancel")
        self.assertTrue(ok, connection.lines)
        self.assertEqual(self.case.service.calls, [("respond", 555, 10002)])
        self.closes()
        self.assertEqual(self.finished()["closed"], True)

    def test_schema_accepts_the_fields_and_rejects_a_bad_resume(self):
        schema = self.probe.schema
        self.assertEqual(schema.OBSERVATION_SCHEMA_VERSION, 20)

        def row(**extra):
            payload = {
                "act_id": "d" * 32, "phase": "FINISHED", "code": None,
                "object_id": "555", "guid64": "13", "interaction_id": None,
                "tuning_name": "Picker", "finishing_type": "ANSWERED", "detail": None,
                "reason_key": None,
            }
            payload.update(extra)
            record = schema.make_record(
                "act_event", telemetry_session_id="u", wall_timestamp_ms=1,
                monotonic_ns=1, e2=payload)
            schema.validate_record(record)
            return record

        for value in schema.RESUME_RESULTS:
            self.assertEqual(row(closed=True, resumed=value)["e2"]["resumed"], value)
        bare = row()
        self.assertIsNone(bare["e2"]["closed"])
        self.assertIsNone(bare["e2"]["resumed"])
        for bad in ("maybe", 1, True):
            with self.assertRaises(schema.SchemaError):
                row(resumed=bad)
        for bad in (1, "yes"):
            with self.assertRaises(schema.SchemaError):
                row(closed=bad)

    def test_the_new_calls_stay_inside_cmd_answer_and_the_file_is_domus(self):
        import os
        tools = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
        sys.path.insert(0, tools)
        import check_guards
        control = os.path.join(os.path.dirname(tools), "src", "ashley_e1", "e2_control.py")
        with open(control, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertEqual(check_guards.scan_text(source, "e2_control.py"), [])
        outside = "def cmd_cancel(self):\n    clock.pop_speed(1)\n    clock.set_clock_speed(1)\n"
        flagged = check_guards.scan_text(outside, "e2_control.py")
        self.assertEqual(len(flagged), 2)
        elsewhere = "def cmd_answer(self):\n    clock.pop_speed(1)\n"
        self.assertEqual(len(check_guards.scan_text(elsewhere, "probe.py")), 1)
        for name in ("build.ps1", "verify.ps1", "install.ps1"):
            path = os.path.join(tools, name)
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
            self.assertIn('Domus_" + $Version + ".ts4script"', text)
        with open(os.path.join(tools, "remove.ps1"), "r", encoding="utf-8") as handle:
            remove = handle.read()
        self.assertIn("Domus_", remove)
        self.assertIn("ashley_e1_", remove)


if __name__ == "__main__":
    unittest.main()
