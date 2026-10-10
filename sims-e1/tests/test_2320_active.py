"""2.32.0 (PR6): the User plays another household Sim while she is armed. Sampling goes on (no stop), her body
stays her armed Sim, the row says it is not the Sim the client plays, and her acts are refused with BODY_MISMATCH.
The refusal is not sticky: the next act after the client plays her Sim again is not refused for that reason.

Invented ids only. Built on the body fixtures of test_2313."""
import types
import unittest

from test_2313_body_zone import ACT_TWO, OTHER_SIM_ID, _BodyBase
from test_2160_act import GUID

HER_SIM_ID = 118245043779534861


class _HouseholdSim(object):
    is_selectable = True

    def __init__(self, sim_id, sim):
        self.id = sim_id
        self._sim = sim

    def get_sim_instance(self, allow_hidden_flags=None):
        return self._sim


class ActiveOtherSimTests(_BodyBase):
    def setUp(self):
        super().setUp()
        other_sim = types.SimpleNamespace(queue=[], si_state=[], posture=None)
        self.her = _HouseholdSim(HER_SIM_ID, self.base.sim)
        self.other = _HouseholdSim(OTHER_SIM_ID, other_sim)
        self.active = self.her
        self.base.services.sim_info_manager = lambda: types.SimpleNamespace(get_all=lambda: [self.her, self.other])
        self.base.services.active_sim_info = lambda: self.active

    def tearDown(self):
        super().tearDown()
        self.probe.observers.prefer_body(None)

    def test_two_household_sims_do_not_stop_sampling_and_her_body_is_the_armed_one(self):
        self.ready()
        self.active = self.other
        self.assertEqual(self.probe._STATE, "SAMPLING")
        self.base.tick()
        self.base.tick()
        self.assertEqual(self.probe._STATE, "SAMPLING")
        self.assertEqual(self.base.rows("guard_exhausted"), [])
        rows = [row for row in self.base.rows("presence_snapshot")]
        self.assertTrue(rows)
        self.assertEqual(rows[-1]["body"]["sim_id"], str(HER_SIM_ID))
        self.assertIs(rows[-1]["body"]["is_selected"], False)
        self.assertNotEqual(self.probe._E2.lineage_class, "BODY_MISMATCH")

    def test_her_acts_are_refused_while_the_User_plays_another_sim(self):
        self.ready()
        self.active = self.other
        ok, connection = self.act(guid64=GUID)
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT BODY_MISMATCH")
        self.assertEqual(self.base.pushes, [])
        self.assertEqual(self.act_events("REJECTED")[-1]["detail"], "NOT_ACTIVE")

    def test_the_refusal_ends_when_the_client_plays_her_sim_again(self):
        self.ready()
        self.active = self.other
        self.base.tick()
        self.active = self.her
        self.base.tick()
        self.assertIs(self.base.rows("presence_snapshot")[-1]["body"]["is_selected"], True)
        ok, connection = self.act(act_id=ACT_TWO, guid64=GUID)
        self.assertTrue(ok, connection.lines)


if __name__ == "__main__":
    unittest.main()
