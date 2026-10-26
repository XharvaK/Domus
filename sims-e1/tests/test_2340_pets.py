"""2.32.0 (PR13): pets and occult forms are read from the game's own Sim info: the pet flag, the species name and
the occult type names of her current form. Anything unreadable is None, and a pet on the lot is a person."""
import types
import unittest

import test_e2
from test_2160_act import _Thing


class PetAndOccultReaderTests(unittest.TestCase):
    def setUp(self):
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.observers = self.base.probe.observers

    def test_the_occult_kinds_are_the_names_of_the_current_types_sorted(self):
        tracker = types.SimpleNamespace(get_current_occult_types=lambda: [
            types.SimpleNamespace(name="WEREWOLF"), types.SimpleNamespace(name="VAMPIRE")])
        info = types.SimpleNamespace(occult_tracker=tracker)
        self.assertEqual(self.observers._occult_kinds(info), ["VAMPIRE", "WEREWOLF"])

    def test_an_ordinary_sim_has_no_occult_kinds_and_an_unreadable_one_is_none(self):
        info = types.SimpleNamespace(occult_tracker=types.SimpleNamespace(get_current_occult_types=lambda: []))
        self.assertEqual(self.observers._occult_kinds(info), [])
        self.assertIsNone(self.observers._occult_kinds(types.SimpleNamespace()))

    def test_the_occult_kinds_are_capped(self):
        many = [types.SimpleNamespace(name="K%d" % index) for index in range(9)]
        info = types.SimpleNamespace(occult_tracker=types.SimpleNamespace(get_current_occult_types=lambda: many))
        self.assertEqual(len(self.observers._occult_kinds(info)), self.base.probe.schema.MAX_OCCULT_KINDS)

    def test_the_species_is_its_name_or_none(self):
        self.assertEqual(self.observers._species_name(types.SimpleNamespace(species=types.SimpleNamespace(name="DOG"))),
                         "DOG")
        self.assertIsNone(self.observers._species_name(types.SimpleNamespace()))

    def test_a_pet_object_is_a_person_and_a_plain_object_is_not(self):
        pet = types.SimpleNamespace(sim_info=types.SimpleNamespace(is_pet=True))
        plain = types.SimpleNamespace(sim_info=types.SimpleNamespace(is_pet=False))
        self.assertTrue(self.observers._is_pet_object(pet))
        self.assertFalse(self.observers._is_pet_object(plain))
        self.assertFalse(self.observers._is_pet_object(types.SimpleNamespace()))


if __name__ == "__main__":
    unittest.main()
