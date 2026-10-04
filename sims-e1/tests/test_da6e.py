"""DA6E hardening: replays of what the live 2.11.0 session showed. Fakes only.

Each test is a live trace (2026-10-04 evening, LAB_E1_FORK, real needs) reduced to
the rows the probe saw. They fail on 2.11.0.
"""
import types
import unittest

from test_da6a_trial import _Offer, _running
from test_da6c import Hosted
from test_da6d import fridge_GrabSnackAutonomously
from test_e2 import CHAIR, _load_pure

SCRIPT = "InteractionSource.SCRIPT_WITH_USER_INTENT"
AUTONOMY = "InteractionSource.AUTONOMY"
BODY_CANCEL = "InteractionSource.BODY_CANCEL_AOP"


class bed_sleep(object):
    guid64 = 13094


class tv_WatchNews(object):
    guid64 = 10600


def _band(value):
    if value <= 20:
        return "distress"
    if value <= 50:
        return "low"
    return "ok"


class _Replay(Hosted):
    def _clock(self):
        self._mono = 5_000_000_000

        def now():
            return self._mono

        self.probe.observers._monotonic_ns = now
        self.probe.e2_control.time.perf_counter_ns = now

    def _motives(self, **values):
        rows = [{"id": key, "value": value, "band": _band(value), "age_ticks": 0}
                for key, value in values.items()]
        self.probe.observers.read_motives = lambda *_a, **_k: rows

    def _step(self, seconds=1.0, ticks=1000):
        self._mono += int(seconds * 1e9)
        self.base.ticks += ticks
        self.base.tick()

    def _verdict(self):
        return [row for row in self.e2() if row["phase"] == "VERDICT"][-1]


class LiveSnackReplay(_Replay):
    """dc25fca3-1: push 994 finished before the first poll; child 996
    generic_consume_food queued, then ate (hunger 31 -> 80); the game then ran
    sink_washDish on autonomy and a BODY_CANCEL_AOP sim-stand. 2.11.0 judged
    OUTCOME_UNKNOWN [overlapping_si] after holding her 600 s."""

    def _push_snack(self):
        self.ready()
        self._clock()
        self._motives(hunger=31, energy=60)
        self.base.ticks = 1000
        for _ in range(3):
            self._step()
        self.base.objects[CHAIR] = _Offer(CHAIR, [fridge_GrabSnackAutonomously])
        self.assertTrue(self.trial(guid64="13397")[0])
        experiment = list(self.probe._E2.experiments.values())[-1]
        pushed = experiment.interaction_ref
        # The autonomous start finishes at once and hands off; it is never polled.
        for callback in pushed.callbacks:
            callback(pushed)
        return experiment

    def test_family_meal_passes_closes_early_and_reports_peak(self):
        experiment = self._push_snack()
        child = _running(996, SCRIPT)
        self.base.sim.queue = [child]
        self._step()
        self.base.sim.queue = []
        self.base.sim.si_state = [child]
        for value in (48, 64, 80):
            self._motives(hunger=value, energy=60)
            for _ in range(4):
                self._step()
        self.base.sim.si_state = [_running(1096, AUTONOMY),
                                  _running(1109, BODY_CANCEL)]
        self._motives(hunger=79, energy=60)
        steps = 0
        while not experiment.closed and steps < 120:
            self._step()
            steps += 1
        self.assertTrue(experiment.closed)
        self.assertLess(steps, 60, "D6: closes with its effect, not the 600 s window")
        self.assertEqual(experiment.verdict, "PASS", (experiment.ambiguous, experiment.claims, experiment.children, experiment.foreign_roots, experiment.started_ns, experiment.incomplete_rows, len(experiment.control_rows)))
        self.assertTrue(experiment.claims["ENQUEUED"], "D12")
        verdict = self._verdict()
        self.assertEqual(verdict["ambiguous"], [])
        self.assertIn("hunger=31->80->", verdict["detail"], "D7")

    def test_nothing_eaten_closes_unknown_without_the_full_window(self):
        experiment = self._push_snack()
        child = _running(996, SCRIPT)
        self.base.sim.si_state = [child]
        for _ in range(5):
            self._step()
        self.base.sim.si_state = []
        steps = 0
        while not experiment.closed and steps < 200:
            self._step()
            steps += 1
        self.assertTrue(experiment.closed)
        self.assertLess(steps, 60)
        self.assertEqual(experiment.verdict, "OUTCOME_UNKNOWN")


class DistressRemedy(unittest.TestCase):
    """dc25fca3: energy 20 refused every trial NEED_DISTRESS, bed included."""

    def setUp(self):
        load = _load_pure()
        self.adm = load[0]
        from ashley_e1 import e2_trial
        self.trial = e2_trial

    def view(self, **overrides):
        view = {
            "sampling": True, "lineage_class": "CONTINUES_LAST_SAVE",
            "designated_sim_id": None, "sim_id": "s", "body_available": True,
            "paused": False, "armed_name": "LAB_E1_FORK", "object_id": CHAIR,
            "excluded_ids": (), "own_open_ids": (), "entries": [],
            "motives": [{"id": "energy", "band": "distress"},
                        {"id": "hunger", "band": "low"}],
            "object": {"exists": True, "offer_count": 1, "excluded": False},
            "tuning_name": None, "food_route": None,
        }
        view.update(overrides)
        return view

    def test_cure_passes_the_guard_and_nothing_else_does(self):
        T = self.trial
        self.assertIsNone(T.trial_check(self.view(tuning_name="bed_sleep")))
        self.assertIsNone(T.trial_check(self.view(tuning_name="sofa_Nap")))
        self.assertEqual(T.trial_check(self.view(tuning_name="tv_WatchNews")),
                         T.NEED_DISTRESS)
        self.assertEqual(T.trial_check(self.view(food_route="auto_craft")),
                         T.NEED_DISTRESS, "food does not cure energy")
        # After sleep: hunger 20, bladder 19, fun 12. One cure at a time.
        woke = [{"id": "hunger", "band": "distress"}, {"id": "bladder", "band": "distress"},
                {"id": "fun", "band": "distress"}]
        self.assertIsNone(T.trial_check(self.view(motives=woke, tuning_name="toilet-use-sitting")))
        self.assertIsNone(T.trial_check(self.view(motives=woke, food_route="auto_craft")))
        self.assertEqual(T.trial_check(self.view(motives=woke, tuning_name="bed_sleep")),
                         T.NEED_DISTRESS)
        self.assertEqual(T.trial_check(self.view(motives=woke, tuning_name="tv_WatchNews")),
                         T.NEED_DISTRESS, "fun is not a body need")
        hunger = [{"id": "hunger", "band": "distress"}]
        self.assertIsNone(T.trial_check(self.view(motives=hunger, food_route="auto_craft")))
        unread = [{"band": "distress"}]
        self.assertEqual(T.trial_check(self.view(motives=unread, tuning_name="bed_sleep")),
                         T.NEED_DISTRESS, "an unreadable motive stays conservative")

    def test_relief_motives(self):
        T = self.trial
        motives = [{"id": "energy", "band": "low"}, {"id": "bladder", "band": "ok"},
                   {"id": "fun", "band": "distress"}]
        self.assertEqual(T.relief_motives(motives, "bed_sleep", None), ["energy"])
        self.assertEqual(T.relief_motives(motives, "toilet-use-sitting", None), [])
        self.assertEqual(T.relief_motives(motives, "tv_WatchNews", None), [])
        low = [{"id": "bladder", "band": "low"}, {"id": "hygiene", "band": "low"}]
        self.assertEqual(T.relief_motives(low, "toilet-use-sitting", None), ["bladder"])
        self.assertEqual(T.relief_motives(low, "toilet_Clean", None), [])
        self.assertEqual(T.relief_motives(low, "shower_TakeShower_Brisk", None), ["hygiene"])
        self.assertEqual(T.relief_motives(low, "shower_Clean", None), [])
        self.assertEqual(T.relief_motives(low, "shower_UpgradeSelfCleaning", None), [])


class ReliefLeftRunning(_Replay):
    """D13: a sleep pushed with low energy must not be cut at the 180 s verdict."""

    def test_sleep_for_low_energy_is_left_running(self):
        self.ready()
        self._clock()
        self._motives(energy=30, hunger=70)
        self.base.ticks = 1000
        self.base.objects[CHAIR] = _Offer(CHAIR, [bed_sleep])
        self.assertTrue(self.trial(guid64="13094")[0])
        experiment = list(self.probe._E2.experiments.values())[-1]
        pushed = experiment.interaction_ref
        self.assertEqual(experiment.relief, ["energy"])
        pushed_row = [row for row in self.e2() if row["phase"] == "PUSHED"][-1]
        self.assertEqual(pushed_row["detail"], "relief=energy")
        self.base.sim.si_state = [types.SimpleNamespace(
            id=pushed.id, guid64=13094, affordance="x",
            target=types.SimpleNamespace(id=int(CHAIR)),
            context=types.SimpleNamespace(source=SCRIPT))]
        while not experiment.closed:
            self._step(seconds=4)
        cleanup = [row for row in self.e2() if row["phase"] == "TRIAL_CLEANUP"][-1]
        self.assertEqual(cleanup["detail"], "relief_left_running")
        self.assertEqual(pushed.cancels, [])

    def test_tv_is_still_cut_at_the_verdict(self):
        self.ready()
        self._clock()
        self._motives(energy=30, hunger=70)
        self.base.ticks = 1000
        self.base.objects[CHAIR] = _Offer(CHAIR, [tv_WatchNews])
        self.assertTrue(self.trial(guid64="10600")[0])
        experiment = list(self.probe._E2.experiments.values())[-1]
        pushed = experiment.interaction_ref
        self.assertEqual(experiment.relief, [])
        self.base.sim.si_state = [types.SimpleNamespace(
            id=pushed.id, guid64=10600, affordance="x",
            target=types.SimpleNamespace(id=int(CHAIR)),
            context=types.SimpleNamespace(source=SCRIPT))]
        while not experiment.closed:
            self._step(seconds=4)
        self.assertTrue(pushed.cancels)


if __name__ == "__main__":
    unittest.main()
