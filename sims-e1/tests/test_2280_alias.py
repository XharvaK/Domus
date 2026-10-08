"""2.28.0: an act tracks the interaction the game actually queued. A picker's push returns one
interaction while her queue gains another; both are the act, so the picker is held, the ending
is seen, and the act finishes once, naming the interaction that finished."""
import copy
import sys
import types
import unittest

import test_2160_act as acts
import test_2180_answer as answers
import test_e2
from test_e2 import CHAIR, PIE


class Queued(test_e2._Interaction):
    """An interaction her queue holds, shaped as the game's entries are read."""

    def __init__(self, iid):
        super(Queued, self).__init__(iid)
        self.guid64 = 4242
        self.affordance = "cook"
        self.target = types.SimpleNamespace(id=int(CHAIR))
        self.context = types.SimpleNamespace(source=PIE)


def picker_push(base, queued_ids=(703,), returned_id=704):
    """The push returns `returned_id` while her queue gains one entry per queued id."""
    queued = [Queued(iid) for iid in queued_ids]
    returned = test_e2._Interaction(returned_id)

    def push(affordance, target, context):
        base.pushes.append((affordance.guid64, target.id, context))
        base.sim.queue = list(base.sim.queue) + queued
        return test_e2._EnqueueResult(True, returned)

    base.sim.push_super_affordance = push
    return queued, returned


class AliasTests(unittest.TestCase):
    def setUp(self):
        self.case = acts.ActCommandTests()
        self.case.setUp()
        self.base = self.case.base
        self.probe = self.case.probe
        self.control = self.probe._E2
        self.module = sys.modules[type(self.control).__module__]

    def tearDown(self):
        self.case.tearDown()

    def pushed(self):
        return [row for row in self.case.events() if row["phase"] == "PUSHED"]

    def test_the_queued_alias_is_seen_and_the_act_is_not_left_queue(self):
        self.case.ready()
        picker_push(self.base)
        ok, connection = self.case.act()
        self.assertTrue(ok, connection.lines)
        self.assertEqual(self.pushed()[0]["interaction_id"], "704")
        self.assertEqual(self.pushed()[0]["aliases"], ["703"])
        for _ in range(7):
            self.base.tick()
        self.assertEqual([row["phase"] for row in self.case.events()], ["ACCEPTED", "PUSHED"])
        self.assertTrue(self.control.pushed["703"]["seen"])
        self.assertEqual(set(self.control.pushed), {"703", "704"})

    def test_an_alias_that_leaves_without_a_finish_is_one_left_queue(self):
        self.case.ready()
        picker_push(self.base)
        self.assertTrue(self.case.act()[0])
        self.base.tick()
        self.base.sim.queue = []
        for _ in range(6):
            self.base.tick()
        left = [row for row in self.case.events() if row["phase"] == "UNKNOWN"]
        self.assertEqual(len(left), 1)
        self.assertEqual((left[0]["code"], left[0]["detail"], left[0]["interaction_id"]),
                         ("LEFT_QUEUE", "ran, then left", "704"))
        self.assertEqual(self.control.pushed, {})

    def test_two_aliases_that_leave_together_are_one_left_queue_for_the_act(self):
        self.case.ready()
        picker_push(self.base, queued_ids=(703, 705))
        self.assertTrue(self.case.act()[0])
        self.base.tick()
        self.base.sim.queue = []
        for _ in range(6):
            self.base.tick()
        left = [row for row in self.case.events() if row["phase"] == "UNKNOWN"]
        self.assertEqual([(row["code"], row["detail"], row["interaction_id"]) for row in left],
                         [("LEFT_QUEUE", "ran, then left", "704")])
        self.assertEqual(self.control.pushed, {})

    def test_an_act_that_never_queues_anything_is_still_never_seen(self):
        self.case.ready()
        picker_push(self.base, queued_ids=())
        self.assertTrue(self.case.act()[0])
        for _ in range(6):
            self.base.tick()
        left = [row for row in self.case.events() if row["phase"] == "UNKNOWN"]
        self.assertEqual([(row["code"], row["detail"]) for row in left],
                         [("LEFT_QUEUE", "never seen in her queue")])
        self.assertEqual(self.pushed()[0]["aliases"], None)
        self.assertEqual(self.control.pushed, {})

    def test_the_queued_alias_finishing_writes_one_finished_naming_it(self):
        self.case.ready()
        queued, returned = picker_push(self.base)
        self.assertTrue(self.case.act()[0])
        self.base.tick()
        self.assertEqual(len(queued[0].callbacks), 1)
        queued[0].callbacks[0](queued[0])
        returned.callbacks[0](returned)
        finished = [row for row in self.case.events() if row["phase"] == "FINISHED"]
        self.assertEqual(len(finished), 1)
        self.assertEqual((finished[0]["interaction_id"], finished[0]["finishing_type"],
                          finished[0]["tuning_name"]), ("703", "FinishingType.NATURAL", "ReadBook"))
        self.assertEqual(self.control.pushed, {})
        self.base.tick()
        self.assertEqual(len([row for row in self.case.events() if row["phase"] == "FINISHED"]), 1)

    def test_the_returned_interaction_finishing_first_names_it_and_the_alias_adds_nothing(self):
        self.case.ready()
        queued, returned = picker_push(self.base)
        self.assertTrue(self.case.act()[0])
        returned.callbacks[0](returned)
        queued[0].callbacks[0](queued[0])
        finished = [row for row in self.case.events() if row["phase"] == "FINISHED"]
        self.assertEqual([row["interaction_id"] for row in finished], ["704"])

    def test_a_plain_push_is_exactly_as_before(self):
        self.case.ready()
        self.assertTrue(self.case.act()[0])
        self.assertEqual(list(self.control.pushed), ["777"])
        self.assertIsNone(self.pushed()[0]["aliases"])
        self.assertEqual(self.pushed()[0]["interaction_id"], "777")
        self.assertEqual(len(self.base.pushes), 1)
        self.assertEqual(self.base.sim.queue, [])
        same = test_e2._Interaction(888)

        def push_same(affordance, target, context):
            self.base.sim.queue = list(self.base.sim.queue) + [same]
            return test_e2._EnqueueResult(True, same)

        self.base.sim.push_super_affordance = push_same
        self.assertTrue(self.case.act(act_id="%032x" % 2)[0])
        self.assertIsNone(self.pushed()[-1]["aliases"])
        self.assertEqual(self.pushed()[-1]["interaction_id"], "888")
        self.assertEqual(len(same.callbacks), 1)

    def test_more_than_four_aliases_are_all_tracked_and_four_are_recorded(self):
        self.case.ready()
        picker_push(self.base, queued_ids=(701, 702, 703, 705, 706, 707))
        self.assertTrue(self.case.act()[0])
        self.assertEqual(self.pushed()[0]["aliases"], ["701", "702", "703", "705"])
        self.assertEqual(sorted(self.control.pushed), ["701", "702", "703", "704", "705", "706", "707"])

    def truthy_push(self, running_ids):
        """The push result is truthy, yet carries no interaction object (the game's
        execute_result.interaction is None); her running list gains the given ids."""
        def push(affordance, target, context):
            self.base.pushes.append((affordance.guid64, target.id, context))
            self.base.sim.si_state = list(self.base.sim.si_state) + [Queued(i) for i in running_ids]
            return test_e2._EnqueueResult(True, None)

        self.base.sim.push_super_affordance = push

    def test_a_truthy_push_without_an_interaction_is_the_one_it_queued(self):
        self.case.ready()
        self.truthy_push([2158])
        ok, connection = self.case.act()
        self.assertTrue(ok, connection.lines)
        self.assertEqual(connection.lines[-1], "ACT_PUSHED %s interaction 2158" % acts.ACT)
        self.assertEqual([row["phase"] for row in self.case.events()], ["ACCEPTED", "PUSHED"])
        self.assertEqual((self.pushed()[0]["interaction_id"], self.pushed()[0]["aliases"]), ("2158", None))
        self.assertEqual(list(self.control.pushed), ["2158"])
        running = self.base.sim.si_state[0]
        self.assertEqual(len(running.callbacks), 1)
        running.callbacks[0](running)
        finished = [row for row in self.case.events() if row["phase"] == "FINISHED"]
        self.assertEqual([(row["interaction_id"], row["finishing_type"]) for row in finished],
                         [("2158", "FinishingType.NATURAL")])
        self.assertEqual(self.control.pushed, {})

    def test_the_first_queued_is_the_act_and_the_others_are_its_aliases(self):
        self.case.ready()
        self.truthy_push([2158, 2159])
        self.assertTrue(self.case.act()[0])
        self.assertEqual((self.pushed()[0]["interaction_id"], self.pushed()[0]["aliases"]), ("2158", ["2159"]))
        self.assertEqual(sorted(self.control.pushed), ["2158", "2159"])
        for _ in range(7):
            self.base.tick()
        self.assertEqual([row["phase"] for row in self.case.events()], ["ACCEPTED", "PUSHED"])
        self.assertTrue(self.control.pushed["2158"]["seen"])

    def test_a_truthy_push_that_queues_nothing_is_still_push_failed(self):
        self.case.ready()
        self.truthy_push([])
        ok, connection = self.case.act()
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT PUSH_FAILED")
        self.assertEqual([(row["phase"], row["code"]) for row in self.case.events()],
                         [("ACCEPTED", None), ("REJECTED", "PUSH_FAILED")])
        self.assertEqual(self.control.pushed, {})

    def test_the_scan_is_bounded_and_never_raises(self):
        many = [test_e2._Interaction(i) for i in range(1, 41)]
        found = self.module._queued_interactions(types.SimpleNamespace(queue=many, si_state=None))
        self.assertEqual(len(found), self.module.ALIAS_SCAN_LIMIT)

        class Broken(object):
            def __iter__(self):
                raise RuntimeError("queue")

        found = self.module._queued_interactions(
            types.SimpleNamespace(queue=Broken(), si_state=[test_e2._Interaction(9)]))
        self.assertEqual(sorted(found), ["9"])
        self.assertEqual(self.module._queued_interactions(types.SimpleNamespace()), {})

    def test_the_rows_validate_and_aliases_are_optional_and_bounded(self):
        self.case.ready()
        picker_push(self.base)
        self.assertTrue(self.case.act()[0])
        self.base.tick()
        schema = self.probe.schema
        rows = [row for row in self.base.rows("act_event") if row["e2"]["phase"] == "PUSHED"]
        for row in self.base.rows("act_event"):
            schema.validate_record(row)
        row = copy.deepcopy(rows[0])
        del row["e2"]["aliases"]
        schema.validate_record(row)
        self.assertIsNone(row["e2"]["aliases"])
        for bad in (["1", "2", "3", "4", "5"], ["x" * 65], [7], "703"):
            row = copy.deepcopy(rows[0])
            row["e2"]["aliases"] = bad
            with self.assertRaises(schema.SchemaError, msg=repr(bad)):
                schema.validate_record(row)


class AliasHoldTests(unittest.TestCase):
    def setUp(self):
        self.answer = answers.AnswerTests()
        self.answer.setUp()
        self.case = self.answer.case
        self.base = self.case.base
        self.control = self.case.probe._E2
        self.module = sys.modules[type(self.control).__module__]
        self.shown = []
        test = self

        def original(dialog, dialog_type, dialog_msg, immediate=False):
            test.shown.append(dialog.dialog_id)

        self.module._HOLD.update(controller=self.control, original=original)
        self.picker = self.answer.recipes
        self.picker.dialog_id = 555

    def tearDown(self):
        self.module._HOLD.update(controller=None, original=None)
        self.answer.tearDown()

    def speed(self):
        return [(row["phase"], row["code"], row["detail"]) for row in self.base.e2("speed_event")]

    def test_the_picker_her_alias_opened_is_held_then_answered_unseen(self):
        self.case.ready()
        queued, returned = picker_push(self.base)
        ok, connection = self.case.act()
        self.assertTrue(ok, connection.lines)
        self.picker._resolver = types.SimpleNamespace(_interaction=queued[0], super_interaction=None)
        self.module._held_distribute(self.picker, "MSG_PICKER", "msg", immediate=True)
        self.assertEqual(self.shown, [])
        self.assertIn("555", self.control.held)
        self.assertEqual(self.speed()[-1], ("DIALOG_HELD", None, "dialog 555 act %s" % acts.ACT))
        ok, connection = self.answer.answer("13")
        self.assertTrue(ok, connection.lines)
        finished = self.base.e2("act_event")[-1]
        self.assertEqual((finished["phase"], finished["detail"]), ("FINISHED", "held"))
        self.assertEqual(self.control.held, {})
        self.assertEqual(self.shown, [])

    def test_the_returned_id_of_the_same_act_holds_its_picker_too(self):
        self.case.ready()
        queued, returned = picker_push(self.base)
        self.assertTrue(self.case.act()[0])
        self.picker.dialog_id = 556
        self.picker._resolver = types.SimpleNamespace(_interaction=returned, super_interaction=None)
        self.module._held_distribute(self.picker, "MSG_PICKER", "msg", immediate=True)
        self.assertEqual(self.shown, [])
        self.assertEqual(self.control.held["556"]["act_id"], acts.ACT)

    def test_a_picker_of_another_interaction_is_still_shown(self):
        self.case.ready()
        picker_push(self.base)
        self.assertTrue(self.case.act()[0])
        self.picker._resolver = types.SimpleNamespace(
            _interaction=test_e2._Interaction(999), super_interaction=None)
        self.module._held_distribute(self.picker, "MSG_PICKER", "msg", immediate=True)
        self.assertEqual(self.shown, [555])
        self.assertEqual(self.control.held, {})


if __name__ == "__main__":
    unittest.main()
