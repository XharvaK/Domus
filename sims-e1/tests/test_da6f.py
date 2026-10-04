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
