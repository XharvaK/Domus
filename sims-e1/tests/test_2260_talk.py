"""2.26.0: one line of social talk shown to the User as the game's own notification. Text only."""
import json
import types
import unittest

import test_2210_camera as camera
from test_2210_camera import HER


class _Factory(object):
    def __init__(self, shown):
        self.shown = shown

    def TunableFactory(self):
        shown = self.shown

        class _Tunable(object):
            def default(self, owner, text=None):
                return types.SimpleNamespace(show_dialog=lambda: shown.append((owner, text())))
        return _Tunable()


class TalkTests(unittest.TestCase):
    def setUp(self):
        self.base = camera.CameraTests()
        self.base.setUp()
        self.case, self.probe, self.control = self.base.case, self.base.probe, self.base.control
        self.shown = []
        self.control.UiDialogNotification = _Factory(self.shown)
        self.control.LocalizationHelperTuning = types.SimpleNamespace(get_raw_text=lambda text: ("raw", text))

    def tearDown(self):
        self.base.tearDown()

    def talk(self, args):
        connection = self.probe._InboxReply("helper")
        ok = self.probe._inbox_dispatch({"command": "talk", "args": args}, connection)
        return ok, connection

    def test_shows_one_line_and_changes_nothing(self):
        self.case.ready()
        ok, connection = self.talk({"text": "Ashley is asking Don about his day.", "sim_id": HER})
        self.assertTrue(ok, connection.lines)
        self.assertEqual(connection.lines[-1], "TALK_OK")
        owner, text = self.shown[0]
        self.assertEqual(int(owner.id), int(HER))
        self.assertEqual(text, ("raw", "Ashley is asking Don about his day."))
        self.assertEqual(self.case.events(), [])

    def test_one_line_per_gap_and_no_owner_without_id(self):
        self.case.ready()
        self.assertTrue(self.talk({"text": "one"})[0])
        self.base.now[0] += 1.0
        ok, connection = self.talk({"text": "two"})
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "TALK_REJECT TOO_SOON")
        self.base.now[0] += 1.5
        self.assertTrue(self.talk({"text": "three"})[0])
        self.assertEqual([item[0] for item in self.shown], [None, None])

    def test_not_sampling_or_unavailable_refuses(self):
        self.case.base.LedgerWriter.records = [self.case.base.continuing()[0]]
        self.assertTrue(self.probe._cmd_arm("HOME"))
        ok, connection = self.talk({"text": "x"})
        self.assertEqual(connection.lines[-1], "TALK_REJECT NOT_SAMPLING")
        self.control.UiDialogNotification = None
        ok, connection = self.talk({"text": "x"})
        self.assertEqual(connection.lines[-1], "TALK_REJECT UNAVAILABLE")
        self.assertEqual(self.shown, [])

    def test_cmdbox_shape(self):
        from ashley_e1 import cmdbox
        base = {"v": 1, "id": "e" * 32, "issued_at_ms": 1000, "expires_at_ms": 2000,
                "issuer": "helper", "command": "talk"}

        def check(args):
            return cmdbox.parse(json.dumps(dict(base, args=args)).encode("utf-8"), 1500, set())[1]

        self.assertIsNone(check({"text": "Ashley waves at Bob."}))
        self.assertIsNone(check({"text": "Ayşe greets Ashley.", "sim_id": "123"}))
        for bad in ({"text": ""}, {"text": " padded"}, {"text": "x" * 241}, {"text": "line\nbreak"},
                    {"text": "ok", "sim_id": "12x"}, {"text": "ok", "extra": "1"}, {"sim_id": "1"}):
            self.assertEqual(check(bad), "BAD_ARGS", bad)


if __name__ == "__main__":
    unittest.main()
