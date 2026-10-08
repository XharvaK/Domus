"""2.31.0 (PR9): the act deny list matches whole name words. "kill" is not hidden inside a skill act,
"fire" not inside a fireplace or campfire act; the intended exclusions stay denied.

Names are invented or class names the game already uses in the probe's tests; no game text."""
import unittest

from test_binding import load_probe


class NameWordTests(unittest.TestCase):
    def setUp(self):
        load_probe()
        from ashley_e1 import e2_trial
        self.trial = e2_trial

    def test_names_split_on_underscores_spaces_and_camel_edges(self):
        words = self.trial.name_words
        self.assertEqual(words("fridge_GrabSnack_PieMenu"), ["fridge", "grab", "snack", "pie", "menu"])
        self.assertEqual(words("SkillKill"), ["skill", "kill"])
        self.assertEqual(words("PIEMenu"), ["pie", "menu"])
        self.assertEqual(words("GoTo lot-two"), ["go", "to", "lot", "two"])
        self.assertEqual(words("WooHoo"), ["woo", "hoo"])
        self.assertEqual(words(""), [])


class DenyNameTests(unittest.TestCase):
    def setUp(self):
        load_probe()
        from ashley_e1 import e2_trial
        self.trial = e2_trial

    def test_skill_and_fireplace_acts_are_not_hidden(self):
        for name in ("SkillBasedMultiInteraction", "SkillPracticeCooking", "Skill_Practice_Handiness",
                     "SkillTimeRamp", "Fireplace_Light", "Campfire_Roast", "UseFireplace",
                     "Gardening_Water", "TakeShower"):
            with self.subTest(name=name):
                self.assertIsNone(self.trial.denied_name(name))

    def test_the_intended_exclusions_still_deny(self):
        cases = {
            "KillSim": "kill", "Skill_Kill_Target": "kill", "StartFire": "fire", "Fire_Alarm": "fire",
            "SellObject": "sell", "DeleteObject": "delete", "Woohoo": "woohoo", "WooHoo": "woo_hoo",
            "TryForBaby": "try_for_baby", "TryBaby": "try_baby", "Propose": "propose",
            "BreakUp": "break_up", "AdoptPet": "adopt", "AdoptionSuperInteraction": "adoption",
            "MoveOut": "move_out", "GoToLot": "go_to", "GoHere": "go_here", "TravelToLot": "travel",
            "CheatMoney": "cheat", "DebugTeleport": "debug", "BuyFromCatalog": "buy",
            "PurchaseObject": "purchase", "OrderFood": "order", "QuitJob": "job", "CareerTalk": "career",
            "AskToJoinInteraction": "ask_to", "CallSim": "call", "PhoneCall": "call",
            "InviteOver": "invite", "SocialSuperInteraction": "social", "Socialize": "socialize",
        }
        for name, entry in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.trial.denied_name(name), entry)

    def test_acts_on_the_menu_use_the_same_rule(self):
        from ashley_e1 import e2_actuator

        class SkillPracticeCooking(object):
            guid64 = 1
            allow_user_directed = True

        class FireplaceLight(object):
            guid64 = 2
            allow_user_directed = True

        class KillSim(object):
            guid64 = 3
            allow_user_directed = True

        self.assertIsNone(e2_actuator.act_excluded(SkillPracticeCooking, False))
        self.assertIsNone(e2_actuator.act_excluded(FireplaceLight, False))
        self.assertEqual(e2_actuator.act_excluded(KillSim, False), "deny_name")


if __name__ == "__main__":
    unittest.main()
