"""2.32.0 (PR5, PR12): her life state is read (age stage, pregnant, sick, dead, ghost, npc), and a death ends
sampling with one BODY_GONE lineage record that names the reason. A living Sim who is only not selectable (a load)
is still waited for, and no BODY_GONE is written.

Invented ids and names only. Built on the body fixtures of test_2313."""
import types
import unittest

import test_e2
from test_2313_body_zone import _BodyBase
from test_e2 import CHAIR


class _Flags(object):
    def __init__(self, **flags):
        self.age = types.SimpleNamespace(name="ADULT")
        self.is_pregnant = flags.get("pregnant", False)
        self.is_sick = flags.get("sick", False)
        self.is_dead = flags.get("dead", False)
        self.is_ghost = flags.get("ghost", False)
        self.is_npc = flags.get("npc", False)


class LifeReaderTests(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.probe = self.base.probe

    def test_each_flag_is_read_and_the_age_stage_is_the_enum_name(self):
        life = self.probe.observers.read_life(_Flags(pregnant=True, dead=True))
        self.assertEqual(life, {"age": "ADULT", "pregnant": True, "sick": False, "dead": True,
                                "ghost": False, "npc": False})

    def test_an_unreadable_value_is_none_never_an_error(self):
        class Broken(object):
            @property
            def is_dead(self):
                raise RuntimeError("unreadable")

            is_sick = "yes"  # not a bool: unknown, not false

        life = self.probe.observers.read_life(Broken())
        self.assertIsNone(life["age"])
        self.assertIsNone(life["dead"])
        self.assertIsNone(life["sick"])
        self.assertIsNone(life["npc"])

    def test_body_life_finds_her_sim_info_by_id_and_is_none_otherwise(self):
        dead = _Flags(dead=True)
        dead.id = 77
        self.base.services.sim_info_manager = lambda: types.SimpleNamespace(get_all=lambda: [dead])
        self.assertIs(self.probe.observers.body_life("77")["dead"], True)
        self.assertIsNone(self.probe.observers.body_life("78"))


class DeathEndsSamplingTests(_BodyBase):
    def info(self):
        return self.base.services.sim_info_manager().get_all()[0]

    def test_a_death_writes_one_body_gone_record_with_the_reason_and_stops(self):
        self.ready()
        info = self.info()
        for name, value in (("is_dead", True), ("is_ghost", False), ("is_selectable", False)):
            setattr(info, name, value)
        self.base.tick()
        self.base.tick()
        gone = [e for e in self.base.e2("lineage_event") if e.get("record") == "BODY_GONE"]
        self.assertEqual(len(gone), 1)
        self.assertEqual(gone[0]["reason"], "DEAD")
        self.assertEqual(gone[0]["lineage_class"], "BODY_GONE")
        self.assertEqual(gone[0]["sim_id"], str(info.id))
        checkpoints = [r for r in self.base.rows("session_checkpoint") if r.get("checkpoint_reason") == "BODY_GONE"]
        self.assertEqual(len(checkpoints), 1)
        self.assertNotEqual(self.probe._STATE, "SAMPLING")
        self.assertEqual(self.base.rows("guard_exhausted"), [])

    def test_a_ghost_is_named_as_a_ghost(self):
        self.ready()
        info = self.info()
        info.is_dead = True
        info.is_ghost = True
        info.is_selectable = False
        self.base.tick()
        gone = [e for e in self.base.e2("lineage_event") if e.get("record") == "BODY_GONE"]
        self.assertEqual(gone[0]["reason"], "GHOST")

    def test_a_living_sim_that_is_not_selectable_is_waited_for_not_stopped(self):
        self.ready()
        info = self.info()
        info.is_dead = False
        info.is_selectable = False
        self.probe._RESUME_SAMPLING = True  # a resumed sampling waits out a load (D41)
        self.base.tick()
        self.base.tick()
        self.assertEqual([e for e in self.base.e2("lineage_event") if e.get("record") == "BODY_GONE"], [])
        self.assertEqual(self.probe._STATE, "SAMPLING")

    def test_her_self_block_carries_the_life_state_in_the_row(self):
        self.info().is_dead = False
        self.ready()
        row = self.base.rows("presence_snapshot")[-1]
        self.assertEqual(set(row["self"]["life"]), {"age", "pregnant", "sick", "dead", "ghost", "npc"})
        self.assertIs(row["self"]["life"]["dead"], False)


if __name__ == "__main__":
    unittest.main()
