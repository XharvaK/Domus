"""2.31.0 (DOMUS_DEEP_DESIGN §4.3, §4.4, §11): what the dialog report says about her windows, the schema
that carries it, and her multi-row, counted and text answers, with every refusal code.

Fakes: pickers and text windows built as the game builds them (a resolver, an owner, picker rows, text
fields with proto2-like presence), sent through the window hold of test_2310_windows."""
import json
import types
import unittest

import test_2180_answer as answers
import test_2310_windows as windows

HER = windows.HER
OTHER = windows.OTHER
OPENER = windows.OPENER
DIALOG = 655
PLAIN = 656


class Text(object):
    """A localized string as the game holds it: its string key."""
    def __init__(self, key):
        self.hash = key


class Field(object):
    """A proto2-like message: an unset field is absent, and HasField says whether a set one is set."""
    def __init__(self, **values):
        self.__dict__.update(values)

    def HasField(self, name):
        if name not in self.__dict__:
            raise ValueError(name)
        return self.__dict__[name] is not None


class Row(object):
    def __init__(self, option_id, enabled=True, def_id=None):
        self.option_id, self.name, self.is_enable = option_id, Text(0x7000 + option_id), enabled
        if def_id is not None:
            self.def_id = def_id


class Picker(windows.Base):
    """ui/ui_dialog_picker.UiDialogObjectPicker (min_selectable, max_selectable_num); a purchase picker
    also has max_selectable_in_row and max_selectable_rows."""
    def __init__(self, dialog_id, interaction=None, owner=HER, rows=(), low=1, high=1, in_row=None, max_rows=None):
        windows.Base.__init__(self, dialog_id, interaction=interaction, owner=owner)
        self.picker_rows = list(rows)
        self.min_selectable, self.max_selectable_num = low, high
        if in_row is not None:
            self.max_selectable_in_row, self.max_selectable_rows = in_row, max_rows
        self.text_ok, self.text_cancel = Text(0x6001), Text(0x6002)
        self.title, self.text = Text(0x5001), None


class CountsOnlyPicker(windows.Base):
    """A purchase window with its counts and no min/max attributes (2.31.0 W4): counts alone check it."""
    def __init__(self, dialog_id, interaction=None, owner=HER, rows=(), in_row=5, max_rows=2):
        windows.Base.__init__(self, dialog_id, interaction=interaction, owner=owner)
        self.picker_rows = list(rows)
        self.max_selectable_in_row, self.max_selectable_rows = in_row, max_rows
        self.text_ok, self.text_cancel = Text(0x6001), Text(0x6002)
        self.title, self.text = Text(0x5001), None


class TextWindow(windows.Base):
    """ui/ui_dialog_generic.UiDialogTextInput: no picker rows, no selects; its message carries the fields."""
    def __init__(self, dialog_id, interaction=None, owner=HER):
        windows.Base.__init__(self, dialog_id, interaction=interaction, owner=owner)
        self.text_ok, self.text_cancel = Text(0x6001), Text(0x6002)
        self.title, self.text = Text(0x5001), None


UiMultiPicker = type("UiMultiPicker", (windows.Base,), {})


def text_fields():
    """Invented fields: a name with a profanity check and a restricted set, a numeric amount, and a field
    with no maximum length (refused: NO_LIMIT)."""
    return [
        Field(text_input_name="given_name", min_length=1, max_length=14, check_profanity=True,
              restricted_characters=Text(0x8001), default_text=Text(0x8002)),
        Field(text_input_name="amount", min_length=1, max_length=6, min_value=1, max_value=500000,
              check_profanity=False),
    ]


def message(fields):
    return types.SimpleNamespace(text_input=fields)


def entry(**changes):
    item = {"dialog_id": "655", "kind": "Picker", "owner_id": "1", "title_key": None, "text_key": None,
            "responses": [], "auto_respond": False, "rows": [], "held": True, "cause": "hers",
            "select": {"min": 1, "max": 3}, "counts": None, "text_inputs": None}
    item.update(changes)
    return item


class ShapeTests(unittest.TestCase):
    tearDown = windows.WindowTests.tearDown
    push = windows.WindowTests.push
    speed = windows.WindowTests.speed
    last_speed = windows.WindowTests.last_speed

    def setUp(self):
        windows.WindowTests.setUp(self)
        self.observers = self.probe.observers
        self.observers._WINDOWS.clear()
        self.schema = self.probe.schema
        self.service.dialog_text_input = lambda dialog_id, name, value: self.service.calls.append(
            ("text", dialog_id, name, value))
        self.service.dialog_pick_result_def_ids_and_counts = lambda dialog_id, def_ids, object_ids, counts, check: (
            self.service.calls.append(("counts", dialog_id, def_ids, object_ids, counts, check)))
        self.act_no = [0]

    def place(self, dialog):
        self.service._active_dialogs[int(dialog.dialog_id)] = dialog
        return dialog

    def hold(self, dialog, dialog_msg=None):
        """Her window: the game's distribute_dialog send, which the hold takes."""
        if dialog_msg is None:
            dialog.distribute_dialog("T", "m")
        else:
            dialog.distribute_dialog("T", dialog_msg)
        return dialog

    def send(self, pick="ok", dialog_id="655", **extra):
        self.act_no[0] += 1
        connection = self.probe._InboxReply("helper")
        args = {"act_id": "%032x" % (0xA00 + self.act_no[0]), "dialog_id": dialog_id, "pick": pick}
        args.update(extra)
        ok = self.probe._inbox_dispatch({"command": "answer", "args": args}, connection)
        return ok, connection

    def report(self, dialog_id="655"):
        for item in self.observers.read_dialogs()["open"]:
            if item["dialog_id"] == dialog_id:
                return item
        return None

    def telemetry(self):
        return json.dumps(self.base.rows(), sort_keys=True, default=str)

    # ------------------------------------------------------------- the report (§11)
    def test_a_held_picker_reports_its_select_and_that_she_holds_it(self):
        self.push()
        self.place(self.hold(Picker(DIALOG, interaction=types.SimpleNamespace(id=OPENER),
                                    rows=[Row(11), Row(13)], low=1, high=3)))
        item = self.report()
        self.assertTrue(item["held"])
        self.assertEqual(item["cause"], "hers")
        self.assertEqual(item["select"], {"min": 1, "max": 3})
        self.assertIsNone(item["counts"])
        self.assertIsNone(item["text_inputs"])
        self.assertEqual([row["option_id"] for row in item["rows"]], ["11", "13"])

    def test_a_purchase_picker_reports_its_counts(self):
        self.push()
        self.place(self.hold(Picker(DIALOG, interaction=types.SimpleNamespace(id=OPENER), rows=[Row(11, def_id=0x4001)],
                                    low=0, high=0, in_row=5, max_rows=3)))
        item = self.report()
        self.assertEqual(item["counts"], {"max_in_row": 5, "max_rows": 3})
        self.assertEqual(item["select"], {"min": 0, "max": 0})

    def test_a_button_window_reports_no_select_and_no_counts(self):
        self.push()
        self.place(self.hold(windows.Base(DIALOG, interaction=types.SimpleNamespace(id=OPENER))))
        item = self.report()
        self.assertIsNone(item["select"])
        self.assertIsNone(item["counts"])
        self.assertTrue(item["held"])

    def test_a_text_window_reports_its_fields_while_held_and_not_after(self):
        self.push()
        self.place(self.hold(TextWindow(DIALOG, interaction=types.SimpleNamespace(id=OPENER)),
                             message(text_fields())))
        item = self.report()
        self.assertEqual(item["text_inputs"], [
            {"name": "given_name", "min_length": 1, "max_length": 14, "numeric": False, "min_value": None,
             "max_value": None, "profanity_checked": True, "restricted": True, "default_key": str(0x8002)},
            {"name": "amount", "min_length": 1, "max_length": 6, "numeric": True, "min_value": 1,
             "max_value": 500000, "profanity_checked": False, "restricted": False, "default_key": None}])
        self.control._release_held(everything=True, code="STOP")
        item = self.report()
        self.assertFalse(item["held"])
        self.assertIsNone(item["text_inputs"])

    def test_a_window_of_the_users_is_reported_as_the_users_and_not_held(self):
        window = self.place(self.hold(windows.Base(DIALOG, owner=OTHER)))
        item = self.report()
        self.assertEqual(item["cause"], "user")
        self.assertFalse(item["held"])
        self.assertIsNone(item["text_inputs"])
        self.assertEqual(window.sent, [("T", "m", False)])

    def test_a_window_she_cannot_answer_is_shown_at_once_and_says_so(self):
        self.push()
        window = self.place(self.hold(UiMultiPicker(DIALOG, interaction=types.SimpleNamespace(id=OPENER))))
        item = self.report()
        self.assertEqual(item["cause"], "hers")
        self.assertFalse(item["held"])
        self.assertEqual(len(window.sent), 1)
        self.assertEqual(self.last_speed(), ("DIALOG_SHOWN", "NOT_ANSWERABLE:UiMultiPicker", "dialog 655 act %s" % windows.ACT_ID))

    def test_a_window_with_no_act_never_says_act_none(self):
        self.place(self.hold(UiMultiPicker(PLAIN, owner=HER)))
        self.assertEqual(self.last_speed(), ("DIALOG_SHOWN", "NOT_ANSWERABLE:UiMultiPicker", "dialog 656"))

    # ------------------------------------------------------------- the schema (§11, schema 14)
    def validate(self, *items):
        row = {"event_kind": "presence_snapshot", "schema_version": 14,
               "dialogs": {"open": list(items), "closed": [], "truncated": False}}
        self.schema._validate_dialogs(row)

    def test_the_schema_accepts_the_window_shapes(self):
        self.validate(entry())
        self.validate(entry(held=False, cause=None, select=None, counts={"max_in_row": 5, "max_rows": 0}))
        self.validate(entry(cause="user", held=False))
        self.validate(entry(text_inputs=[{"name": "given_name", "min_length": 0, "max_length": None,
                                          "numeric": False, "min_value": None, "max_value": None,
                                          "profanity_checked": False, "restricted": False, "default_key": None}]))

    def test_the_schema_refuses_bad_window_shapes(self):
        field = {"name": "amount", "min_length": 1, "max_length": 6, "numeric": True, "min_value": 1,
                 "max_value": 9, "profanity_checked": False, "restricted": False, "default_key": None}
        bad = [entry(held="yes"), entry(cause="robot"), entry(select={"min": 1}),
               entry(select={"min": 1, "max": 99}), entry(counts={"max_in_row": 1000, "max_rows": 1}),
               entry(held=False, text_inputs=[field]), entry(text_inputs=[]),
               entry(text_inputs=[dict(field, name="a b")]), entry(text_inputs=[dict(field, name="x" * 33)]),
               entry(text_inputs=[dict(field, min_value=1.5)]), entry(text_inputs=[dict(field, numeric=1)]),
               entry(text_inputs=[dict(field, default_key=32770)]),
               entry(text_inputs=[dict(field, extra=True)]),
               entry(text_inputs=[field] * 9)]
        for item in bad:
            with self.assertRaises(self.schema.SchemaError):
                self.validate(item)

    def test_a_schema_14_row_must_carry_the_window_keys_and_a_13_row_need_not(self):
        item = entry()
        for key in ("held", "cause", "select", "counts", "text_inputs"):
            short = dict((name, value) for name, value in item.items() if name != key)
            with self.assertRaises(self.schema.SchemaError):
                self.validate(short)
        old = dict((name, value) for name, value in item.items()
                   if name not in ("held", "cause", "select", "counts", "text_inputs"))
        row = {"event_kind": "presence_snapshot", "schema_version": 13,
               "dialogs": {"open": [old], "closed": [], "truncated": False}}
        self.schema._validate_dialogs(row)

    # ------------------------------------------------------------- multi-row (§4.3, 2)
    def test_several_rows_are_picked_together_then_ok(self):
        self.push()
        self.place(self.hold(Picker(DIALOG, interaction=types.SimpleNamespace(id=OPENER),
                                    rows=[Row(11), Row(13)], low=1, high=3)))
        ok, connection = self.send("ok", rows=[{"option_id": "11", "count": 1}, {"option_id": "13", "count": 1}])
        self.assertTrue(ok, connection.lines)
        self.assertEqual(self.service.calls, [("pick", 655, [11, 13]), ("respond", 655, 10001)])

    def test_a_row_count_inside_the_select_is_the_only_count_on_a_plain_picker(self):
        self.push()
        self.place(self.hold(Picker(DIALOG, interaction=types.SimpleNamespace(id=OPENER),
                                    rows=[Row(11), Row(13)], low=2, high=2)))
        ok, connection = self.send("ok", rows=[{"option_id": "11", "count": 1}])
        self.assertEqual(connection.lines[-1], "ACT_REJECT ROW_COUNT")
        ok, connection = self.send("ok", rows=[{"option_id": "11", "count": 2}, {"option_id": "13", "count": 1}])
        self.assertEqual(connection.lines[-1], "ACT_REJECT COUNT_INVALID")
        self.assertEqual(self.service.calls, [])

    def test_a_multi_row_refusal_names_the_rule_and_keeps_the_window_held(self):
        self.push()
        self.place(self.hold(Picker(DIALOG, interaction=types.SimpleNamespace(id=OPENER),
                                    rows=[Row(11), Row(12, enabled=False), Row(13), Row(14)], low=1, high=2)))
        cases = [([{"option_id": "11", "count": 1}, {"option_id": "13", "count": 1},
                   {"option_id": "14", "count": 1}], "ROW_COUNT"),
                 ([{"option_id": "11", "count": 1}, {"option_id": "11", "count": 1}], "NO_ROW"),
                 ([{"option_id": "99", "count": 1}], "NO_ROW"),
                 ([{"option_id": "12", "count": 1}], "ROW_DISABLED"),
                 ([{"option_id": "11", "count": 1}, {"option_id": "13", "count": 1}], None)]
        for rows, code in cases:
            ok, connection = self.send("ok", rows=rows)
            if code is None:
                self.assertTrue(ok, connection.lines)
            else:
                self.assertFalse(ok)
                self.assertEqual(connection.lines[-1], "ACT_REJECT %s" % code)
        self.assertEqual(self.service.calls, [("pick", 655, [11, 13]), ("respond", 655, 10001)])

    def test_a_select_of_zero_is_no_limit_so_any_number_of_rows_is_answered(self):
        self.push()
        self.place(self.hold(Picker(DIALOG, interaction=types.SimpleNamespace(id=OPENER),
                                    rows=[Row(11), Row(13), Row(14)], low=1, high=0)))
        ok, connection = self.send("ok", rows=[{"option_id": "11", "count": 1}, {"option_id": "13", "count": 1},
                                               {"option_id": "14", "count": 1}])
        self.assertTrue(ok, connection.lines)
        self.assertEqual(self.service.calls, [("pick", 655, [11, 13, 14]), ("respond", 655, 10001)])
        self.assertEqual(self.report()["select"], {"min": 1, "max": 0})

    def test_a_single_row_pick_on_a_picker_that_needs_two_goes_through_the_row_check(self):
        self.push()
        self.place(self.hold(Picker(DIALOG, interaction=types.SimpleNamespace(id=OPENER),
                                    rows=[Row(11), Row(13)], low=2, high=0)))
        ok, connection = self.send("11")
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT ROW_COUNT")
        self.assertEqual(self.service.calls, [])

    def test_a_purchase_window_without_select_attributes_is_answered_by_its_counts(self):
        self.push()
        self.place(self.hold(CountsOnlyPicker(DIALOG, interaction=types.SimpleNamespace(id=OPENER),
                                              rows=[Row(11, def_id=0x4001), Row(13, def_id=0x4002)])))
        ok, connection = self.send("ok", rows=[{"option_id": "11", "count": 2}, {"option_id": "13", "count": 1}])
        self.assertTrue(ok, connection.lines)
        self.assertEqual(self.service.calls, [("counts", 655, [0x4001, 0x4002], [0, 0], [2, 1], False),
                                              ("respond", 655, 10001)])

    def test_rows_on_a_window_without_a_select_are_refused(self):
        self.push()
        self.place(self.hold(windows.Base(DIALOG, interaction=types.SimpleNamespace(id=OPENER))))
        ok, connection = self.send("ok", rows=[{"option_id": "11", "count": 1}])
        self.assertEqual(connection.lines[-1], "ACT_REJECT NO_ROW")

    def test_rows_and_text_need_the_ok_pick(self):
        self.push()
        self.place(self.hold(Picker(DIALOG, interaction=types.SimpleNamespace(id=OPENER), rows=[Row(11)])))
        ok, connection = self.send("11", rows=[{"option_id": "11", "count": 1}])
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT NO_RESPONSE")

    # ------------------------------------------------------------- counts (§4.3, 3)
    def test_a_purchase_is_answered_with_its_definitions_and_counts(self):
        self.push()
        self.place(self.hold(Picker(DIALOG, interaction=types.SimpleNamespace(id=OPENER),
                                    rows=[Row(11, def_id=0x4001), Row(13, def_id=0x4002)],
                                    low=1, high=2, in_row=5, max_rows=2)))
        ok, connection = self.send("ok", rows=[{"option_id": "11", "count": 2}, {"option_id": "13", "count": 5}])
        self.assertTrue(ok, connection.lines)
        self.assertEqual(self.service.calls, [("counts", 655, [0x4001, 0x4002], [0, 0], [2, 5], False),
                                              ("respond", 655, 10001)])

    def test_a_purchase_refuses_counts_over_its_caps(self):
        self.push()
        self.place(self.hold(Picker(DIALOG, interaction=types.SimpleNamespace(id=OPENER),
                                    rows=[Row(11, def_id=0x4001), Row(13, def_id=0x4002)],
                                    low=1, high=2, in_row=5, max_rows=1)))
        ok, connection = self.send("ok", rows=[{"option_id": "11", "count": 6}])
        self.assertEqual(connection.lines[-1], "ACT_REJECT COUNT_INVALID")
        ok, connection = self.send("ok", rows=[{"option_id": "11", "count": 2}, {"option_id": "13", "count": 1}])
        self.assertEqual(connection.lines[-1], "ACT_REJECT COUNT_INVALID")
        self.assertEqual(self.service.calls, [])

    # ------------------------------------------------------------- text (§4.4, 4)
    def test_a_text_answer_writes_every_field_in_order_then_ok(self):
        self.push()
        self.place(self.hold(TextWindow(DIALOG, interaction=types.SimpleNamespace(id=OPENER)),
                             message(text_fields())))
        ok, connection = self.send("ok", text={"amount": "13579", "given_name": "Vesperine"})
        self.assertTrue(ok, connection.lines)
        self.assertEqual(self.service.calls, [("text", 655, "given_name", "Vesperine"),
                                              ("text", 655, "amount", "13579"), ("respond", 655, 10001)])

    def test_a_text_answer_is_refused_unless_the_window_is_held(self):
        self.place(TextWindow(DIALOG, owner=HER))  # in the dialog service, never sent: not held
        ok, connection = self.send("ok", text={"given_name": "Vesperine", "amount": "1"})
        self.assertEqual(connection.lines[-1], "ACT_REJECT NOT_HELD")
        self.assertEqual(self.service.calls, [])

    def test_a_text_answer_is_checked_against_the_limits_of_the_held_message(self):
        self.push()
        fields = text_fields() + [Field(text_input_name="nick", min_length=0, max_length=8)]
        self.place(self.hold(TextWindow(DIALOG, interaction=types.SimpleNamespace(id=OPENER)), message(fields)))
        good = {"given_name": "Ana", "amount": "250", "nick": "a"}
        refusals = [
            ({"given_name": "Ana", "amount": "250"}, "TEXT_INVALID"),
            ({"given_name": "Ana", "amount": "250", "nick": "a", "extra": "x"}, "TEXT_INVALID"),
            (dict(good, given_name=""), "TEXT_INVALID"),
            (dict(good, given_name="x" * 15), "TEXT_INVALID"),
            (dict(good, given_name="bad\x07name"), "TEXT_INVALID"),
            (dict(good, given_name="a-b"), "TEXT_INVALID"),
            (dict(good, amount="abc"), "TEXT_INVALID"),
            (dict(good, amount="-"), "TEXT_INVALID"),
            (dict(good, amount="600000"), "TEXT_INVALID"),
            (dict(good, amount="0"), "TEXT_INVALID"),
            (dict(good, amount="1" * 7), "TEXT_INVALID"),
            (good, None),
        ]
        for text, code in refusals:
            ok, connection = self.send("ok", text=text)
            if code is None:
                self.assertTrue(ok, connection.lines)
            else:
                self.assertFalse(ok)
                self.assertEqual(connection.lines[-1], "ACT_REJECT %s" % code, text)

    def test_a_field_with_no_maximum_is_refused_as_no_limit(self):
        self.push()
        fields = [Field(text_input_name="nick", min_length=0)]
        self.place(self.hold(TextWindow(DIALOG, interaction=types.SimpleNamespace(id=OPENER)), message(fields)))
        ok, connection = self.send("ok", text={"nick": "a"})
        self.assertEqual(connection.lines[-1], "ACT_REJECT NO_LIMIT")

    def test_a_text_window_with_more_fields_than_the_schema_carries_has_no_text_rules(self):
        self.push()
        fields = [Field(text_input_name="f%d" % number, min_length=0, max_length=4) for number in range(9)]
        self.place(self.hold(TextWindow(DIALOG, interaction=types.SimpleNamespace(id=OPENER)), message(fields)))
        self.assertIsNone(self.report()["text_inputs"])
        ok, connection = self.send("ok", text=dict(("f%d" % number, "a") for number in range(9)))
        self.assertEqual(connection.lines[-1], "ACT_REJECT TEXT_NOT_HELD")
        self.assertEqual(self.service.calls, [])

    def test_a_numeric_field_without_both_bounds_is_refused_as_no_limit(self):
        self.push()
        fields = [Field(text_input_name="amount", min_length=1, max_length=6, max_value=500000)]
        self.place(self.hold(TextWindow(DIALOG, interaction=types.SimpleNamespace(id=OPENER)), message(fields)))
        ok, connection = self.send("ok", text={"amount": "5"})
        self.assertEqual(connection.lines[-1], "ACT_REJECT NO_LIMIT")

    def test_her_text_is_never_in_any_telemetry_row(self):
        self.push()
        self.place(self.hold(TextWindow(DIALOG, interaction=types.SimpleNamespace(id=OPENER)),
                             message(text_fields())))
        ok, connection = self.send("ok", text={"given_name": "Vesperine", "amount": "13579"})
        self.assertTrue(ok, connection.lines)
        blob = self.telemetry()
        self.assertNotIn("Vesperine", blob)
        self.assertNotIn("13579", blob)
        finished = [row["e2"] for row in self.base.rows("act_event") if row["e2"].get("phase") == "FINISHED"]
        self.assertEqual(finished[-1]["detail"], "held text 2")

    # ------------------------------------------------------------- the speed detail and the window's facts
    def test_a_held_window_detail_names_the_act_only_when_there_is_one(self):
        self.push()
        self.place(self.hold(Picker(DIALOG, interaction=types.SimpleNamespace(id=OPENER), rows=[Row(11)])))
        self.assertEqual(self.last_speed(), ("DIALOG_HELD", None, "dialog 655 act %s" % windows.ACT_ID))
        self.place(self.hold(Picker(PLAIN, owner=HER, rows=[Row(11)])))
        self.assertEqual(self.speed()[-1], ("DIALOG_HELD", None, "dialog 656"))


class CmdboxAnswerTests(unittest.TestCase):
    """2.31.0 (§11, 3): the wire shapes of rows and text, checked before the probe sees them."""
    def setUp(self):
        # The probe package needs the game's fakes, which the answer fixture installs.
        self.fixture = answers.AnswerTests()
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()

    def parse(self, args):
        from ashley_e1 import cmdbox
        raw = json.dumps({"v": 1, "id": "c" * 32, "issued_at_ms": 1000, "expires_at_ms": 2000,
                          "issuer": "helper", "command": "answer",
                          "args": dict({"act_id": "a" * 32, "dialog_id": "655", "pick": "ok"}, **args)}).encode("utf-8")
        return cmdbox.parse(raw, 1500, set())[1]

    def test_rows_and_text_are_accepted_with_the_ok_pick(self):
        self.assertIsNone(self.parse({"rows": [{"option_id": "11", "count": 1}]}))
        self.assertIsNone(self.parse({"rows": [{"option_id": str(n), "count": 99} for n in range(1, 17)]}))
        self.assertIsNone(self.parse({"text": {"given_name": "x" * 256, "amount-2.b_c": ""}}))
        self.assertIsNone(self.parse({"rows": [{"option_id": "11", "count": 2}], "text": {"a": "b"}}))

    def test_bad_rows_and_text_are_bad_args(self):
        bad = [{"rows": []}, {"rows": [{"option_id": "11", "count": 0}]}, {"rows": [{"option_id": "11", "count": 100}]},
               {"rows": [{"option_id": "11", "count": True}]}, {"rows": [{"option_id": "1x", "count": 1}]},
               {"rows": [{"option_id": "11"}]}, {"rows": [{"option_id": "11", "count": 1, "x": 1}]},
               {"rows": [{"option_id": str(n), "count": 1} for n in range(1, 18)]},
               {"rows": "11"}, {"text": {}}, {"text": {"a b": "x"}}, {"text": {"": "x"}},
               {"text": {"x" * 33: "x"}}, {"text": {"a": "x" * 257}}, {"text": {"a": 5}},
               {"text": dict(("f%d" % n, "x") for n in range(9))}, {"text": ["a"]}]
        for args in bad:
            self.assertEqual(self.parse(args), "BAD_ARGS", args)
        self.assertEqual(self.parse({"rows": [{"option_id": "11", "count": 1}], "pick": "13"}), "BAD_ARGS")
        self.assertEqual(self.parse({"text": {"a": "x"}, "pick": "11"}), "BAD_ARGS")


if __name__ == "__main__":
    unittest.main()
