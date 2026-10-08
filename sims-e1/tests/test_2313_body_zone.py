"""2.31.0 (PR7, PR8): a switch to another body refuses her acts with BODY_MISMATCH even without a prepare,
and a zone change or a load ends every act still pushed as UNKNOWN (ZONE_CHANGE or LOADED), not later.

Invented ids only. Built on the control-flow fakes of test_e2 and the act fixtures of test_2160."""
import sys
import types
import unittest

import test_e2
from test_2160_act import ACT, GUID, ReadBook, _Offer
from test_e2 import CHAIR

OTHER_SIM_ID = 4242
ACT_TWO = "b" * 32


class _SwitchedBody(object):
    """Another selectable household Sim: the one the User plays after a switch."""
    is_selectable = True
    id = OTHER_SIM_ID

    def __init__(self, sim):
        self._sim = sim

    def get_sim_instance(self, allow_hidden_flags=None):
        return self._sim


class _BodyBase(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.probe = self.base.probe
        self.base.objects[CHAIR] = _Offer(CHAIR, [ReadBook])
        self.tested = []

        def test_super_affordance(affordance, target, context):
            self.tested.append((affordance.guid64, target.id))
            return True

        self.base.sim.test_super_affordance = test_super_affordance

    def tearDown(self):
        writer = self.base.LedgerWriter.instances[-1] if self.base.LedgerWriter.instances else None
        if writer is not None:
            writer.finish()

    def ready(self, name="HOME"):
        self.base.LedgerWriter.records = [self.base.continuing()[0]]
        self.assertTrue(self.probe._cmd_arm(name))
        self.assertTrue(self.probe._cmd_start())
        self.base.tick()

    def act(self, act_id=ACT, object_id=CHAIR, guid64=GUID):
        connection = self.probe._InboxReply("helper")
        ok = self.probe._inbox_dispatch(
            {"command": "act", "args": {"act_id": act_id, "object_id": object_id, "guid64": guid64}},
            connection)
        return ok, connection

    def act_events(self, phase=None):
        return [e for e in self.base.e2("act_event") if phase is None or e["phase"] == phase]

    def switch_to_other_body(self):
        other = _SwitchedBody(self.base.sim)
        self.base.services.sim_info_manager = lambda: types.SimpleNamespace(get_all=lambda: [other])


class BodySwitchTests(_BodyBase):
    def test_a_normal_act_is_unaffected(self):
        self.ready()
        ok, connection = self.act()
        self.assertTrue(ok, connection.lines)
        self.assertEqual(self.probe._E2.lineage_class, "CONTINUES_LAST_SAVE")
        self.assertEqual(self.base.pushes[-1][1], int(CHAIR))

    def test_a_switch_is_recorded_once_and_the_act_is_refused_without_a_prepare(self):
        self.ready()
        self.assertIsNone(self.probe._E2.designated_sim_id)
        self.switch_to_other_body()
        self.base.tick()
        self.assertEqual(self.probe._E2.lineage_class, "BODY_MISMATCH")
        checkpoints = [e for e in self.base.e2("lineage_event")
                       if e.get("record") == "CLASSIFIED" and e.get("lineage_class") == "BODY_MISMATCH"]
        self.assertEqual(len(checkpoints), 1)
        self.assertEqual(checkpoints[0]["sim_id"], str(OTHER_SIM_ID))
        self.base.tick()
        self.base.tick()
        self.assertEqual(len([e for e in self.base.e2("lineage_event")
                              if e.get("lineage_class") == "BODY_MISMATCH"]), 1)
        pushes_before = len(self.base.pushes)
        ok, connection = self.act(act_id=ACT_TWO)
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT BODY_MISMATCH")
        self.assertEqual(len(self.base.pushes), pushes_before)

    def test_a_switch_between_polls_is_still_refused_at_once(self):
        self.ready()
        self.switch_to_other_body()
        ok, connection = self.act()
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT BODY_MISMATCH")
        self.assertEqual(self.base.pushes, [])
        self.assertEqual(self.act_events("REJECTED")[-1]["code"], "BODY_MISMATCH")

    def test_a_switched_body_refuses_camera_and_talk_too(self):
        self.ready()
        self.switch_to_other_body()
        self.base.tick()
        # The camera's view calls and the talk notification exist only in the game; the test stands in for them.
        e2_module = sys.modules["ashley_e1.e2_control"]
        e2_module.focus_on_sim = e2_module.focus_on_object = lambda *args, **kwargs: None
        connection = self.probe._InboxReply("helper")
        self.assertFalse(self.probe._E2.cmd_camera("follow_sim", CHAIR, connection))
        self.assertEqual(connection.lines[-1], "CAMERA_REJECT BODY_MISMATCH")
        e2_module.UiDialogNotification = e2_module.LocalizationHelperTuning = lambda *args, **kwargs: None
        connection = self.probe._InboxReply("helper")
        self.assertFalse(self.probe._E2.cmd_talk("hello", None, connection))
        self.assertEqual(connection.lines[-1], "TALK_REJECT BODY_MISMATCH")


class PushedActEndTests(_BodyBase):
    def pushed_act(self):
        self.ready()
        ok, connection = self.act()
        self.assertTrue(ok, connection.lines)
        self.assertEqual(len(self.probe._E2.pushed), 1)

    def test_a_zone_change_resolves_the_pushed_act_as_unknown_at_once(self):
        self.pushed_act()
        self.probe._E2.on_stop("ZONE_CHANGE")
        unknown = self.act_events("UNKNOWN")
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0]["code"], "ZONE_CHANGE")
        self.assertEqual(self.probe._E2.pushed, {})
        for _ in range(6):
            self.base.tick()
        self.assertEqual([e["code"] for e in self.act_events("UNKNOWN")], ["ZONE_CHANGE"])
        self.assertFalse([e for e in self.act_events() if e.get("code") == "LEFT_QUEUE"])

    def test_a_load_resolves_an_act_left_from_an_earlier_session_as_loaded(self):
        self.pushed_act()
        self.probe._cmd_disarm()
        self.assertEqual(len(self.probe._E2.pushed), 1)
        # The writer is idle once its close is written (the game's writer thread does that).
        self.base.LedgerWriter.instances[-1].finish()
        self.assertTrue(self.probe._cmd_arm("HOME"))
        unknown = self.act_events("UNKNOWN")
        self.assertEqual([e["code"] for e in unknown], ["LOADED"])
        self.assertEqual(self.probe._E2.pushed, {})

    def test_a_stop_for_another_reason_keeps_the_existing_left_queue_rule(self):
        self.pushed_act()
        self.probe._E2.on_stop("STOP")
        self.assertEqual(self.act_events("UNKNOWN"), [])
        self.assertEqual(len(self.probe._E2.pushed), 1)


if __name__ == "__main__":
    unittest.main()
