"""2.18.0: a game dialog is hers to answer: a picker row or a button, the way the client does."""
import types
import unittest

import test_2160_act as acts

HER = 118245043779534861
ANSWER = "b" * 32


class _Text(object):
    def __init__(self, key):
        self.hash = key


class _Row(object):
    def __init__(self, option_id, name, enabled=True, price=None):
        self.option_id, self.name, self.is_enable = option_id, _Text(name), enabled
        if price is not None:
            self.price = price


class _Picker(object):
    def __init__(self, owner_id, rows):
        self._owner = lambda: None if owner_id is None else types.SimpleNamespace(id=owner_id)
        self.title, self.text = _Text(0x5001), None
        self.text_ok, self.text_cancel = _Text(0x6001), _Text(0x6002)
        self.picker_rows = rows
        self.response = None


class _Service(object):
    def __init__(self):
        self._active_dialogs = {}
        self._auto_respond_alarm_handles = {}
        self.calls = []

    def dialog_pick_result(self, dialog_id, picked_results):
        self.calls.append(("pick", dialog_id, list(picked_results)))

    def dialog_respond(self, dialog_id, response, client=None):
        self.calls.append(("respond", dialog_id, response))


class AnswerTests(unittest.TestCase):
    def setUp(self):
        self.case = acts.ActCommandTests()
        self.case.setUp()
        self.probe = self.case.probe
        self.service = _Service()
        self.case.base.services.ui_dialog_service = lambda: self.service
        self.recipes = _Picker(HER, [_Row(11, 0x7001, price=5), _Row(12, 0x7002, enabled=False), _Row(13, 0x7003)])
        self.service._active_dialogs[555] = self.recipes

    def tearDown(self):
        self.case.tearDown()

    def answer(self, pick, dialog_id="555", act_id=ANSWER):
        connection = self.probe._InboxReply("helper")
        ok = self.probe._inbox_dispatch(
            {"command": "answer", "args": {"act_id": act_id, "dialog_id": dialog_id, "pick": pick}}, connection)
        return ok, connection

    def test_a_row_is_picked_then_ok_like_the_client(self):
        self.case.ready()
        ok, connection = self.answer("13")
        self.assertTrue(ok, connection.lines)
        self.assertEqual(self.service.calls, [("pick", 555, [13]), ("respond", 555, 10001)])
        phases = [(e["phase"], e["object_id"], e["guid64"], e["finishing_type"]) for e in self.case.events()]
        self.assertEqual(phases, [("ACCEPTED", "555", "13", None), ("FINISHED", "555", "13", "ANSWERED")])
        for row in self.case.base.rows("act_event"):
            self.probe.schema.validate_record(row)

    def test_a_button_answer_and_every_refusal(self):
        self.case.ready()
        ok, _ = self.answer("cancel")
        self.assertTrue(ok)
        self.assertEqual(self.service.calls, [("respond", 555, 10002)])
        cases = [("12", "555", "ROW_DISABLED"), ("99", "555", "NO_ROW"), ("13", "556", "NO_DIALOG"),
                 ("custom_3", "555", "NO_RESPONSE")]
        for index, (pick, dialog_id, code) in enumerate(cases):
            ok, connection = self.answer(pick, dialog_id, act_id="%032x" % (index + 1))
            self.assertFalse(ok, code)
            self.assertEqual(connection.lines[-1], "ACT_REJECT %s" % code)
        self.service._active_dialogs[557] = _Picker(42, [_Row(11, 0x7001)])
        ok, connection = self.answer("11", "557", act_id="%032x" % 9)
        self.assertEqual(connection.lines[-1], "ACT_REJECT NOT_HERS")
        self.assertEqual(len(self.service.calls), 1)

    def test_once_per_act_id_and_never_outside_sampling(self):
        ok, connection = self.answer("13")
        self.assertEqual(connection.lines[-1], "ACT_REJECT NOT_SAMPLING")
        ok, connection = self.answer("13")
        self.assertEqual(connection.lines[-1], "ACT_REJECT DUPLICATE")
        self.assertEqual(self.service.calls, [])

    def test_the_rows_are_sensed_enabled_first_with_price(self):
        rows = self.probe.observers._dialog_rows(self.recipes)
        self.assertEqual(rows, [
            {"option_id": "11", "name_key": str(0x7001), "enabled": True, "price": 5},
            {"option_id": "13", "name_key": str(0x7003), "enabled": True, "price": None},
            {"option_id": "12", "name_key": str(0x7002), "enabled": False, "price": None}])
        self.assertEqual(self.probe.observers._dialog_rows(types.SimpleNamespace()), [])

    def test_cmdbox_answer_shapes(self):
        from ashley_e1 import cmdbox
        import json
        base = {"v": 1, "id": "c" * 32, "issued_at_ms": 1000, "expires_at_ms": 2000, "issuer": "helper",
                "command": "answer"}

        def check(args):
            return cmdbox.parse(json.dumps(dict(base, args=args)).encode("utf-8"), 1500, set())[1]
        self.assertIsNone(check({"act_id": ANSWER, "dialog_id": "555", "pick": "13"}))
        self.assertIsNone(check({"act_id": ANSWER, "dialog_id": "555", "pick": "cancel"}))
        for bad in ({"act_id": ANSWER, "dialog_id": "x", "pick": "13"},
                    {"act_id": ANSWER, "dialog_id": "555", "pick": "Cancel!"},
                    {"act_id": ANSWER, "dialog_id": "555"}):
            self.assertEqual(check(bad), "BAD_ARGS", bad)


if __name__ == "__main__":
    unittest.main()
