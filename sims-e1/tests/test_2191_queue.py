"""2.19.1: an act that leaves her queue unseen is recorded as gone; a pie-menu picker is not
an act she can complete."""
import unittest

import test_2160_act as acts
from test_2160_act import ACT, CHAIR, GUID


class GrabSnackPieMenu(object):
    __name__ = "fridge_GrabSnack_PieMenu"
    guid64 = 77672
    allow_user_directed = True


def _row(interaction_ids):
    return {"event_kind": "presence_snapshot",
            "interactions": {"observed": [{"interaction_id": i} for i in interaction_ids]}}


class LeftQueueTests(unittest.TestCase):
    setUp = acts.ActCommandTests.setUp
    tearDown = acts.ActCommandTests.tearDown
    ready = acts.ActCommandTests.ready
    act = acts.ActCommandTests.act
    events = acts.ActCommandTests.events

    def control(self):
        return self.probe._E2

    def test_never_seen_in_her_queue_is_unknown_left_queue(self):
        self.ready()
        self.assertTrue(self.act()[0])
        control = self.control()
        for _ in range(4):
            control.on_poll_row(_row(["1"]))
        self.assertEqual(self.events()[-1]["phase"], "PUSHED")
        control.on_poll_row(_row(["1"]))
        last = self.events()[-1]
        self.assertEqual((last["phase"], last["code"], last["interaction_id"], last["detail"]),
                         ("UNKNOWN", "LEFT_QUEUE", "777", "never seen in her queue"))
        for row in self.base.rows("act_event"):
            self.probe.schema.validate_record(row)
        control.on_poll_row(_row([]))
        self.assertEqual(len([e for e in self.events() if e["phase"] == "UNKNOWN"]), 1)

    def test_seen_then_finished_by_the_game_is_finished_once(self):
        self.ready()
        captured = []
        original = self.base.sim.push_super_affordance

        def capture(affordance, target, context):
            result = original(affordance, target, context)
            captured.append(result.execute_result.interaction)
            return result

        self.base.sim.push_super_affordance = capture
        self.assertTrue(self.act()[0])
        control = self.control()
        control.on_poll_row(_row(["777"]))
        interaction = captured[-1]
        interaction.callbacks[0](interaction)
        for _ in range(6):
            control.on_poll_row(_row([]))
        self.assertEqual([e["phase"] for e in self.events()], ["ACCEPTED", "PUSHED", "FINISHED"])

    def test_a_pie_menu_picker_is_not_hers_to_push(self):
        self.ready()
        self.assertEqual(self.probe.e2_actuator.act_excluded(GrabSnackPieMenu, False), "pie_picker")
        self.assertIsNone(self.probe.e2_actuator.act_excluded(acts.ReadBook, False))


if __name__ == "__main__":
    unittest.main()
