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
