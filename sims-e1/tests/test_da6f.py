"""DA6F: the second live session (2.11.1). Fakes only."""
import unittest

from test_e2 import _load_pure


class FoodNameTests(unittest.TestCase):
    def setUp(self):
        _load_pure()
        from ashley_e1 import food
        self.food = food

    def test_word_start_not_substring(self):
        """D21: 401 of 701 live rows were cheats, deaths and create-object."""
        hit = self.food.name_hit
        for name in ("cheat_set_as_head", "death_Hunger", "Knitting_CreateObject_Finished",
                     "splash_Sim_seated", "debugDeathInteraction", "Cheat_AddToFamily"):
            self.assertFalse(hit(name, 1), name)
        for name in ("fridge_GrabSnackAutonomously", "stove_Cook_PieMenu_Dinner_8Servings_Ingredients",
                     "refrigerator_GetLeftovers_Lunch_Picker", "fridge_CookGroupMeal_Autonomously",
                     "sim_DrinkEnergyJuice", "eat_Plate", "fridge_CreateSnackAndConsume_Generic",
                     "BBQMeal"):
            self.assertTrue(hit(name, 1), name)
        self.assertTrue(hit("anything", 13397))

    def test_words(self):
        words = self.food._words
        self.assertEqual(words("stove_Cook_PieMenu_8Servings"),
                         ["stove", "cook", "pie", "menu", "8", "servings"])
        self.assertEqual(words("BBQMeal"), ["bbq", "meal"])
        self.assertEqual(words("toilet-use-sitting"), ["toilet", "use", "sitting"])
        self.assertEqual(words("debugDeathInteraction"), ["debug", "death", "interaction"])
        self.assertEqual(words(""), [])


class ScanProgressTests(unittest.TestCase):
    def setUp(self):
        _load_pure()

    def test_preflight_and_food_report_progress(self):
        """D22: a ten-minute preflight looked stuck; status had no block for it."""
        import tempfile, os
        from ashley_e1 import food, preflight
        folder = tempfile.mkdtemp()
        for module, cls in ((preflight, preflight.PreflightScan), (food, food.FoodScan)):
            scan = cls([{"object_id": "1"}] * 3, os.path.join(folder, module.__name__ + ".jsonl"),
                       lambda job: {"kind": "x"}, max_per_chunk=2)
            self.assertEqual(scan.progress()["state"], "running")
            self.assertEqual(scan.progress()["total"], 3)
            self.assertTrue(scan.progress()["file"].endswith(".partial"))
            scan.step()
            self.assertEqual(scan.progress()["done"], 2)
            scan.step()
            done = scan.progress()
            self.assertEqual((done["state"], done["done"], done["chunks"]), ("done", 3, 2))
            self.assertFalse(done["file"].endswith(".partial"))


from test_da6e import AUTONOMY, BODY_CANCEL, SCRIPT, _Replay, bed_sleep  # noqa: E402
from test_da6a_trial import _Offer, _running  # noqa: E402
from test_e2 import CHAIR  # noqa: E402


class LiveSleepReplay(_Replay):
    """412d52ea-2: bed_sleep pushed at energy 24 (relief=energy), energy 26 -> 100 at
    speed 3, she woke at row 1381 (FINISHED NATURAL); the interaction card waited for
    the 180 s window (VERDICT at 1519) and the PASS detail had no energy reading."""

    def test_sleep_closes_after_waking_and_reports_energy(self):
        import types
        self.ready()
        self._clock()
        self._motives(energy=24, hunger=60)
        self.base.ticks = 1000
        self.base.objects[CHAIR] = _Offer(CHAIR, [bed_sleep])
        self.assertTrue(self.trial(guid64="13094")[0])
        experiment = list(self.probe._E2.experiments.values())[-1]
        pushed = experiment.interaction_ref
        self.base.sim.si_state = [types.SimpleNamespace(
            id=pushed.id, guid64=13094, affordance="x",
            target=types.SimpleNamespace(id=int(CHAIR)),
            context=types.SimpleNamespace(source=SCRIPT))]
        for _ in range(16):  # live 1331-1346: walking to the bed at energy 24
            self._step()
        for value in range(26, 101, 4):
            self._motives(energy=value, hunger=50)
            self._step(ticks=37000)
        self._motives(energy=100, hunger=48)
        for _ in range(5):
            self._step(ticks=37000)
        # Live 1382-1385: sim-stand BODY_CANCEL_AOP running, idle_Hunger AUTONOMY queued.
        self.base.sim.si_state = [_running(3861, BODY_CANCEL, target=999)]
        self.base.sim.queue = [_running(3863, AUTONOMY, target=999)]
        pushed.finishing_type = "FinishingType.NATURAL"
        pushed.callbacks[0](pushed)
        steps = 0
        while not experiment.closed and steps < 200:
            self._step()
            steps += 1
        self.assertTrue(experiment.closed)
        self.assertLess(steps, 45, "D26: closes after she wakes, not at the window")
        self.assertEqual(experiment.verdict, "PASS", (experiment.ambiguous, experiment.claims,
                         experiment.foreign_roots, experiment.incomplete_rows))
        detail = self._verdict()["detail"]
        self.assertIn("relief=energy energy=24->100->100", detail)


class _RatedCommodity(object):
    """A commodity with the game's pure rate getters (bytecode continuous_statistic)."""

    def __init__(self, guid, value, updated, change=0.0, decay=0.0, convergence=0.0,
                 until=None, suppressed=False):
        self.guid64 = guid
        self._value = value
        self._last_update = updated
        self.min_value = 0
        self.max_value = 100
        self._change = change
        self._decay = decay
        self.convergence_value = convergence
        self._until = until
        self._tracker = type("T", (), {"should_suppress_calculations":
                                        lambda _self: suppressed})()

    def _get_change_rate_without_decay(self):
        return self._change

    def _calculate_minutes_until_value_is_reached_through_decay(self, target):
        return self._until

    def get_decay_rate(self):
        return self._decay

    def get_value(self):
        raise AssertionError("get_value writes the cache")

    def _update_value(self):
        raise AssertionError("_update_value writes the cache")


class CurrentMotiveTests(unittest.TestCase):
    """D25: at speed 3 (sleep, work) rows are ~37000 ticks apart; the cache of a
    need she was not refilling read 47554 ticks old and was stale."""

    def setUp(self):
        _load_pure()
        from ashley_e1 import observers
        self.observers = observers

    def read(self, commodity, now):
        row, fault = self.observers._read_cached_motive(commodity, now)
        self.assertIsNone(fault)
        return row["value"], row["age_ticks"]

    def test_decay_over_a_speed_three_gap(self):
        # hunger 40 at tick 0, -0.5 per sim minute, read 47554 ticks (31.7 min) later.
        hunger = _RatedCommodity(16656, 40.0, 0, change=-0.5)
        self.assertEqual(self.read(hunger, 47554), (24, 0))

    def test_decay_stops_at_convergence(self):
        fun = _RatedCommodity(16655, 60.0, 0, decay=-1.0, convergence=50.0, until=10.0)
        self.assertEqual(self.read(fun, 45000), (50, 0))

    def test_clamped_and_suppressed(self):
        energy = _RatedCommodity(16657, 95.0, 0, change=2.0)
        self.assertEqual(self.read(energy, 30000), (100, 0))
        frozen = _RatedCommodity(16657, 30.0, 0, change=-5.0, suppressed=True)
        self.assertEqual(self.read(frozen, 30000), (30, 0))

    def test_unreadable_rates_keep_the_cache_and_its_age(self):
        class Bare(object):
            guid64 = 16656
            _value = 40.0
            _last_update = 0
            min_value = 0
            max_value = 100
        self.assertEqual(self.read(Bare(), 47554), (40, 47554))
