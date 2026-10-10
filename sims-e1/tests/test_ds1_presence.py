"""DS1-3 red-first: presence and social reads."""
import os
import sys
import types
import unittest


SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)
if "ashley_e1" not in sys.modules:
    package = types.ModuleType("ashley_e1")
    package.__path__ = [os.path.join(SRC, "ashley_e1")]
    sys.modules["ashley_e1"] = package

from test_binding import load_probe
from test_ds1_senses import FakeSimInfo, FakeTracker, FakeBuffs


class FakeSim(object):
    """A game Sim object (what instanced_sims_on_active_lot_gen yields). It carries
    sim_info and has no get_sim_instance (D37: the old reader called it)."""

    def __init__(self, sim_id, household_id=None, level=None, selectable=True,
                 si_state=None, queue=None, on_lot=True, at=None):
        self._sim_id = sim_id
        self.id = sim_id
        self._household_id = household_id
        self._level = level
        self._selectable = selectable
        self.si_state = si_state
        self.queue = queue
        self._on_lot = on_lot
        self.sim_info = None
        self.zone_id = 7
        self.posture = None
        x, z = at if at is not None else (0.0, 0.0)
        self.position = types.SimpleNamespace(x=x, y=0.0, z=z)

    def get_sim_instance(self, *args, **kwargs):
        raise AttributeError("a Sim has no get_sim_instance")

    @property
    def level(self):
        return self._level

    def is_on_active_lot(self, include_spawn_point=None):
        del include_spawn_point
        return self._on_lot


class FakeSimInfoEntry(object):
    def __init__(self, sim_id, sim=None, household=None, household_id=None,
                 selectable=True, first_name=None, last_name=None):
        self.id = sim_id
        self._sim = sim
        self.household = household
        self.household_id = household_id
        self._selectable = selectable
        self.first_name = first_name
        self.last_name = last_name
        if sim is not None:
            sim.sim_info = self

    def get_sim_instance(self, allow_hidden_flags=None):
        del allow_hidden_flags
        return self._sim

    @property
    def is_selectable(self):
        return self._selectable


class FakeEntry(object):
    def __init__(self, entry_id, affordance, target, source="InteractionSource.AUTONOMY"):
        self.id = entry_id
        self.guid64 = affordance
        self.affordance = affordance
        self.target = target
        self.context = types.SimpleNamespace(source=source)


class LabSim(object):
    def __init__(self, sim_id):
        self.id = sim_id


class Manager(object):
    def __init__(self, entries):
        self._entries = entries

    def get_all(self):
        return list(self._entries)

    def instanced_sims_on_active_lot_gen(self, allow_hidden_flags=None,
                                         include_spawn_point=None):
        """Like the game (SimInfoManager, bytecode 1.128): instanced Sim objects."""
        del allow_hidden_flags, include_spawn_point
        for entry in self._entries:
            if entry._sim is not None:
                yield entry._sim


def presence_row(sim_id, active_household=False, level=None, is_body=False,
                 household_id=None, name=None, position=None, room=None,
                 posture=None, doing=None, doing_target=None, distance_m=None,
                 relationship=None, on_lot=True, situations=None):
    return {"id": sim_id, "on_lot": on_lot, "active_household": active_household,
            "level": level,
            "is_body": is_body, "household_id": household_id, "name": name,
            "position": position, "room": room, "posture": posture, "doing": doing,
            "doing_target": doing_target, "distance_m": distance_m,
            "relationship": relationship, "situations": situations,
            # 2.32.0 (PR13): a Sim the fake does not describe as a pet, with no species or occult type read.
            "is_pet": None, "species": None, "occult_kinds": None}


class PresenceTests(unittest.TestCase):
    def context(self, entries, active_household="hh1", lab_id="lab"):
        _, probe, _ = load_probe()
        services = sys.modules["services"]
        manager = Manager(entries)
        services.sim_info_manager = lambda: manager
        services.active_household = lambda: types.SimpleNamespace(id=active_household)
        return probe

    def test_lab_present_once_with_flag(self):
        sim = FakeSim("lab")
        entry = FakeSimInfoEntry("lab", sim=sim, household="hh1", household_id="hh1")
        probe = self.context([entry])
        presence, truncated, skipped = probe.observers.read_presence("lab")
        self.assertEqual(skipped, 0)
        self.assertEqual(presence, [presence_row(
            "lab", active_household=True, is_body=True, household_id="hh1",
            position={"x": 0.0, "y": 0.0, "z": 0.0, "level": None})])
        self.assertEqual(truncated, {"on_lot": 0, "other": 0})

    def test_cap_eight_sets_truncation_and_skips_no_instance(self):
        entries = [FakeSimInfoEntry("s%d" % i, sim=FakeSim("s%d" % i),
                                    household="other", household_id="other")
                   for i in range(10)]
        entries.insert(3, FakeSimInfoEntry("ghost", sim=None))
        probe = self.context(entries)
        presence, truncated, _ = probe.observers.read_presence("lab")
        self.assertEqual(len(presence), 8)
        self.assertEqual(truncated, {"on_lot": 2, "other": 0})
        self.assertNotIn("ghost", [row["id"] for row in presence])

    def test_level_and_household_flag(self):
        sim = FakeSim("s1", level=3)
        entry = FakeSimInfoEntry("s1", sim=sim, household="hh9", household_id="hh9")
        probe = self.context([entry], active_household="hh1")
        presence, _, _ = probe.observers.read_presence("lab")
        self.assertEqual(presence, [presence_row(
            "s1", level=3, household_id="hh9",
            position={"x": 0.0, "y": 0.0, "z": 0.0, "level": 3})])

    def test_d40_one_unreadable_sim_hides_no_one_and_is_counted(self):
        """Live 2.14.0: one Sim arriving made the game's lot generator raise and the
        whole row went empty, her body included."""
        class Arriving(FakeSim):
            def is_on_active_lot(self, include_spawn_point=None):
                raise RuntimeError("no location yet")

        class Broken(FakeSimInfoEntry):
            def get_sim_instance(self, allow_hidden_flags=None):
                raise RuntimeError("mid-spawn")

        entries = [Broken("broken", sim=FakeSim("broken")),
                   FakeSimInfoEntry("new", sim=Arriving("new", at=(1.0, 0.0))),
                   FakeSimInfoEntry("lab", sim=FakeSim("lab", on_lot=False)),
                   FakeSimInfoEntry("friend", sim=FakeSim("friend", on_lot=False, at=(2.0, 0.0)))]
        probe = self.context(entries)
        presence, truncated, skipped = probe.observers.read_presence(
            "lab", body_position={"x": 0.0, "y": 0.0, "z": 0.0, "level": None})
        self.assertEqual([row["id"] for row in presence], ["lab", "new", "friend"])
        self.assertEqual([row["on_lot"] for row in presence], [False, None, False])
        self.assertEqual(skipped, 1)
        self.assertEqual(truncated, {"on_lot": 0, "other": 0})

    def test_social_keeps_lab_targeted_drops_others(self):
        lab = LabSim("lab")
        other_target = LabSim("other")
        me = FakeSim("me", si_state=[FakeEntry(1, "aff1", lab),
                                     FakeEntry(2, "aff2", other_target)],
                     queue=[FakeEntry(3, "aff3", lab)])
        entry = FakeSimInfoEntry("me", sim=me)
        probe = self.context([entry])
        social, truncated = probe.observers.read_social("lab", LabSim("lab"), [entry])
        self.assertEqual(len(social), 2)
        self.assertFalse(truncated)
        for row in social:
            self.assertEqual(row["target_id"], "lab")

    def test_social_reads_queue_and_si_state_none_fine_capped(self):
        lab = LabSim("lab")
        queued = [FakeEntry(i, "aff", lab) for i in range(6)]
        me = FakeSim("me", si_state=None, queue=queued)
        entry = FakeSimInfoEntry("me", sim=me)
        probe = self.context([entry])
        social, truncated = probe.observers.read_social("lab", lab, [entry])
        self.assertEqual(len(social), 4)
        self.assertTrue(truncated)


if __name__ == "__main__":
    unittest.main()
