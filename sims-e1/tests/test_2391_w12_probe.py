"""2.39.0 (W12 probe, windows and people): an act that waits behind a window reads WAITING and finishes; a
numbered answer is named response_<N> and answered by its number; a purchase picker answered by one row is
sent as a count; an answer is ANSWERED only when its window closed, and the hold leaves only after the send;
the command vocabulary carries answer, cancel and menu_near; the people fields validate; every drop has a
detail.

Fakes only: the harness of test_2180 (her picker, the dialog service) and test_2160 (her act, pushed into a
fake queue). No game, no live services."""
import json
import shutil
import tempfile
import types
import unittest

import test_2180_answer as answers
import test_bounds as bounds
import test_ds3_senses as ds3

ACT_ONE = "c" * 32
ACT_TWO = "d" * 32


class _Purchase(answers._Picker):
    """A purchase picker: counted caps and no select attributes (the game's UiPurchasePicker)."""
    def __init__(self, owner_id, rows):
        answers._Picker.__init__(self, owner_id, rows)
        self.max_selectable_in_row = 5
        self.max_selectable_rows = 0


class _PurchaseRow(answers._Row):
    def __init__(self, option_id, name, def_id):
        answers._Row.__init__(self, option_id, name)
        self.def_id = def_id


class _Custom(object):
    """A dialog with numbered responses and no ok or cancel: the game's custom buttons."""
    def __init__(self, owner_id, numbers):
        self._owner = lambda: types.SimpleNamespace(id=owner_id)
        self.title, self.text = answers._Text(0x5001), answers._Text(0x5002)
        self.text_ok, self.text_cancel = None, None
        self.ui_responses = [types.SimpleNamespace(dialog_response_id=number, text=answers._Text(0x9000 + number))
                             for number in numbers]
        self.picker_rows = []
        self.response = None


class ActWindowTests(unittest.TestCase):
    def setUp(self):
        self.case = answers.AnswerTests()
        self.case.setUp()
        self.base = self.case.case.base
        self.probe = self.case.probe
        self.control = self.probe._E2
        self.observers = self.probe.observers
        self.service = self.case.service
        self.counts = []
        self.service.dialog_pick_result_def_ids_and_counts = (
            lambda dialog_id, def_ids, object_ids, counts, flag: self.counts.append((dialog_id, def_ids, counts)))

    def tearDown(self):
        self.case.tearDown()

    # helpers
    def push_act(self, act_id=ACT_ONE):
        captured = []
        original = self.base.sim.push_super_affordance

        def capture(affordance, target, context):
            result = original(affordance, target, context)
            captured.append(result.execute_result.interaction)
            return result

        self.base.sim.push_super_affordance = capture
        ok, connection = self.case.case.act(act_id=act_id)
        self.assertTrue(ok, connection.lines)
        return captured[-1]

    def row(self, ids, open_dialogs=()):
        return {"event_kind": "presence_snapshot",
                "interactions": {"observed": [{"interaction_id": i} for i in ids]},
                "dialogs": {"open": [{"dialog_id": d} for d in open_dialogs], "closed": [], "truncated": False}}

    def events(self):
        return self.case.case.events()

    def phases(self):
        return [event["phase"] for event in self.events()]

    def hold(self, key, act_id=ACT_ONE):
        self.control.held[key] = {"act_id": act_id, "at": 0.0, "kind": "dialog",
                                  "send": (lambda *args, **kwargs: None, (), {})}

    # A1: a pushed act that waits behind an open window
    def test_an_act_missing_while_a_window_is_open_waits_once_and_its_finish_is_kept(self):
        self.case.case.ready()
        interaction = self.push_act()
        for _ in range(7):
            self.control.on_poll_row(self.row([], ["601"]))
        self.assertEqual(self.phases(), ["ACCEPTED", "PUSHED", "WAITING"])
        waiting = self.events()[-1]
        self.assertEqual((waiting["code"], waiting["detail"]), ("WINDOW_OPEN", "dialog 601"))
        for row in self.base.rows("act_event"):
            self.probe.schema.validate_record(row)
        interaction.callbacks[0](interaction)
        self.assertEqual(self.phases(), ["ACCEPTED", "PUSHED", "WAITING", "FINISHED"])

    def test_the_window_closing_restarts_the_count_and_an_unseen_act_is_left_queue_after_five(self):
        self.case.case.ready()
        self.push_act()
        for _ in range(7):
            self.control.on_poll_row(self.row([], ["601"]))
        for _ in range(4):
            self.control.on_poll_row(self.row([]))
        self.assertNotIn("UNKNOWN", self.phases())
        self.control.on_poll_row(self.row([]))
        last = self.events()[-1]
        self.assertEqual((last["phase"], last["code"], last["detail"]),
                         ("UNKNOWN", "LEFT_QUEUE", "never seen in her queue"))

    # A2: a numbered answer is named response_<N> and answered by its number
    def test_a_numbered_button_is_named_by_its_number_and_answered_by_it(self):
        self.assertEqual(self.observers._response_name(7), "response_7")
        self.assertEqual(self.observers._response_name(10001), "ok")
        self.assertIsNone(self.observers._response_name(-5))
        self.assertIsNone(self.observers._response_name(10 ** 12))
        self.case.case.ready()
        self.service._active_dialogs[556] = _Custom(answers.HER, [7, 8])
        names = [item["response"] for item in self.observers._dialog_responses(self.service._active_dialogs[556])]
        self.assertEqual(names, ["response_7", "response_8"])
        self.hold("556", ACT_ONE)
        ok, connection = self.case.answer("response_7", dialog_id="556", act_id=ACT_ONE)
        self.assertTrue(ok, connection.lines)
        self.assertEqual(self.service.calls, [("respond", 556, 7)])

    def test_a_numbered_button_the_dialog_does_not_offer_is_refused(self):
        self.case.case.ready()
        self.service._active_dialogs[556] = _Custom(answers.HER, [7])
        self.hold("556", ACT_ONE)
        ok, connection = self.case.answer("response_9", dialog_id="556", act_id=ACT_TWO)
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT NO_RESPONSE")
        self.assertEqual(self.service.calls, [])

    # A3: one row answering a purchase picker is sent with its count
    def test_one_row_answering_a_purchase_picker_is_sent_as_a_count(self):
        self.case.case.ready()
        picker = _Purchase(answers.HER, [_PurchaseRow(13, 0x7003, 9013), _PurchaseRow(11, 0x7001, 9011)])
        self.service._active_dialogs[556] = picker
        self.hold("556", ACT_ONE)
        ok, connection = self.case.answer("13", dialog_id="556", act_id=ACT_ONE)
        self.assertTrue(ok, connection.lines)
        self.assertEqual(self.counts, [(556, [9013], [1])])
        self.assertEqual(self.service.calls, [("respond", 556, 10001)])

    # A5: the hold leaves only after the answer is sent; the answer says whether its window closed
    def test_a_failed_send_keeps_the_window_held_and_the_act_unknown(self):
        self.case.case.ready()
        self.case.hold_recipes()

        def refuse(dialog_id, response, client=None):
            raise RuntimeError("send")

        self.service.dialog_respond = refuse
        ok, _connection = self.case.answer("13", act_id=ACT_ONE)
        self.assertFalse(ok)
        self.assertIn("555", self.control.held)
        last = self.events()[-1]
        self.assertEqual((last["phase"], last["code"]), ("UNKNOWN", "E2_EXCEPTION:RuntimeError"))

    def test_a_sent_answer_leaves_the_hold_and_a_window_that_closes_is_answered(self):
        self.case.case.ready()
        self.case.hold_recipes()
        respond = self.service.dialog_respond

        def respond_and_close(dialog_id, response, client=None):
            respond(dialog_id, response, client)
            self.service._active_dialogs.pop(dialog_id, None)

        self.service.dialog_respond = respond_and_close
        ok, _connection = self.case.answer("13", act_id=ACT_ONE)
        self.assertTrue(ok)
        self.assertNotIn("555", self.control.held)
        last = self.events()[-1]
        self.assertEqual((last["phase"], last["finishing_type"], last["code"]), ("FINISHED", "ANSWERED", "ANSWERED"))

    def test_an_answer_whose_window_stays_open_is_sent_open_and_the_user_has_it(self):
        self.case.case.ready()
        self.case.hold_recipes()
        ok, _connection = self.case.answer("13", act_id=ACT_ONE)
        self.assertTrue(ok)
        last = self.events()[-1]
        self.assertEqual((last["phase"], last["finishing_type"], last["code"]),
                         ("FINISHED", "ANSWERED", "ANSWER_SENT_OPEN"))
        self.assertEqual(self.observers._WINDOWS["555"]["cause"], "user")
        self.assertNotIn("555", self.control.held)


class CommandVocabularyTests(unittest.TestCase):
    """B9 (probe side): answer, cancel and menu_near are commands the probe writes telemetry for, and the
    menu_near hook is a no-op until the menu worker fills it in."""
    def setUp(self):
        self.case = answers.AnswerTests()
        self.case.setUp()
        self.probe = self.case.probe
        self.schema = self.probe.schema

    def tearDown(self):
        self.case.tearDown()

    def test_answer_cancel_and_menu_near_are_in_both_vocabularies(self):
        from ashley_e1 import cmdbox
        for name in ("answer", "cancel", "menu_near"):
            self.assertIn(name, cmdbox.COMMANDS)
            self.assertIn(name, self.schema.COMMANDS)

    def test_a_command_event_for_each_of_them_validates(self):
        for name in ("answer", "cancel", "menu_near"):
            row = self.schema.make_record(
                "command_event", telemetry_session_id="s", wall_timestamp_ms=1, monotonic_ns=1,
                e2=dict(id=ACT_ONE, issuer="helper", command=name, status="REJECTED", code="NO_ROW"))
            self.schema.validate_record(row)

    def test_menu_near_takes_no_arguments_and_is_answered_ok(self):
        from ashley_e1 import cmdbox
        base = {"v": 1, "id": "f" * 32, "issued_at_ms": 1000, "expires_at_ms": 2000, "issuer": "helper",
                "command": "menu_near"}
        self.assertIsNone(cmdbox.parse(json.dumps(dict(base, args={})).encode("utf-8"), 1500, set())[1])
        self.assertEqual(cmdbox.parse(json.dumps(dict(base, args={"x": 1})).encode("utf-8"), 1500, set())[1],
                         "BAD_ARGS")
        connection = self.probe._InboxReply("helper")
        self.assertTrue(self.probe._inbox_dispatch({"command": "menu_near", "args": {}}, connection))


class PeopleFieldTests(unittest.TestCase):
    """E4, E5: the game's own gender and name fields reach the probe's rows, bounded and validated."""
    def setUp(self):
        ds3.PollOnceTests.setUp(self)

    def tearDown(self):
        teardown = getattr(ds3.PollOnceTests, "tearDown", None)
        if teardown is not None:
            teardown(self)

    def test_gender_is_f_or_m_from_the_games_enum_and_none_otherwise(self):
        def sim(name):
            return types.SimpleNamespace(gender=types.SimpleNamespace(name=name))
        observers = self.probe.observers
        self.assertEqual(observers._gender_code(sim("FEMALE")), "F")
        self.assertEqual(observers._gender_code(sim("MALE")), "M")
        self.assertIsNone(observers._gender_code(sim("NOT_SET")))
        self.assertIsNone(observers._gender_code(types.SimpleNamespace()))

    def test_a_name_part_is_the_games_own_string_bounded_to_64_or_none(self):
        observers = self.probe.observers
        info = types.SimpleNamespace(first_name="Ada", last_name="Marrow the Third")
        self.assertEqual(observers._name_part(lambda: info.first_name), "Ada")
        self.assertEqual(observers._name_part(lambda: info.last_name), "Marrow the Third")
        self.assertIsNone(observers._name_part(lambda: types.SimpleNamespace(last_name="").last_name))
        self.assertIsNone(observers._name_part(lambda: types.SimpleNamespace(last_name=7).last_name))
        self.assertIsNone(observers._name_part(lambda: types.SimpleNamespace().last_name))
        self.assertEqual(len(observers._name_part(lambda: types.SimpleNamespace(first_name="x" * 90).first_name)), 64)

    def test_the_self_block_and_the_presence_items_carry_the_fields_and_validate(self):
        schema = self.probe.schema
        row = ds3.PollOnceTests.row(self)
        row["presence"] = [dict(item, first_name="Ada", last_name="Marrow") for item in row["presence"]]
        row["self"] = dict(row["self"], gender="F", first_name="Ada", last_name="Marrow")
        schema.validate_record(row)
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(dict(row, self=dict(row["self"], gender="X")))
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(dict(row, presence=[dict(item, last_name="y" * 65) for item in row["presence"]]))


class DropDetailAlwaysTests(unittest.TestCase):
    """B9: every drop the writer counts carries a detail, so a summary is never a bare reason."""
    def test_each_drop_reason_leaves_a_detail(self):
        temp = tempfile.mkdtemp()
        try:
            sink = bounds.memory_writer(temp, None)
            for reason in ("SAMPLER_OVERRUN", "QUEUE_SATURATION"):
                sink._pending_drop_reason = None
                sink._pending_drop_detail = None
                sink.note_drop(reason)
                self.assertTrue(sink._pending_drop_detail, reason)
        finally:
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
