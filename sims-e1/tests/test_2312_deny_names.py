"""2.31.0 (PR9): the act deny list matches whole name words. "debug" is not hidden inside "Debugger", "travel"
not inside "Traveler"; the kept exclusions stay denied.
2.37.1 (User 2026-10-12): only testers' and cheat acts, trips off the lot and acts not meant for a hand stay
out by name. Judgement names (kill, fire, sell, love, family, careers, money, moving) are hers to choose.

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

    def test_the_kept_exclusions_still_deny(self):
        cases = {
            "CheatMoney": "cheat", "CheatSheet": "cheat", "DebugTeleport": "debug", "TestingTools": "testing",
            "TutorialStart": "tutorial", "GoToLot": "go_to", "GoHere": "go_here", "TravelToLot": "travel",
            "LeaveLot": "leave",
        }
        for name, entry in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.trial.denied_name(name), entry)

    def test_a_career_leave_is_not_hidden_and_leaving_the_lot_still_is(self):
        # 2.40.0 (W13 R2, Q-a): the career acts that leave early are hers; leaving the lot stays out by name.
        for name in ("CareerLeaveWorkEarly", "CareerLeaveSchoolEarly", "Career_Leave_Work_Early_Invented"):
            with self.subTest(name=name):
                self.assertIsNone(self.trial.denied_name(name))
        for name in ("Push_Leave_Lot_Invented", "LeaveLotInvented", "Leave_Lot_Sample"):
            with self.subTest(name=name):
                self.assertEqual(self.trial.denied_name(name), "leave")

    def test_whole_words_only_for_the_kept_names(self):
        self.assertIsNone(self.trial.denied_name("Debugger_Panel"))
        self.assertIsNone(self.trial.denied_name("Traveler_Chat"))

    def test_judgement_names_are_hers_to_choose(self):
        # 2.37.1 (User 2026-10-12): she takes responsibility for her life; these are not kept out by name.
        for name in ("KillSim", "Skill_Kill_Target", "StartFire", "Fire_Alarm", "SellObject", "DeleteObject",
                     "Woohoo", "WooHoo", "TryForBaby", "TryBaby", "Propose", "BreakUp", "AdoptPet",
                     "AdoptionSuperInteraction", "MoveOut", "BuyFromCatalog", "PurchaseObject", "OrderFood",
                     "QuitJob", "CareerTalk", "AskToJoinInteraction", "CallSim", "PhoneCall", "InviteOver",
                     "SocialSuperInteraction", "Socialize"):
            with self.subTest(name=name):
                self.assertIsNone(self.trial.denied_name(name))

    def test_acts_on_the_menu_use_the_same_rule(self):
        from ashley_e1 import e2_actuator

        class SkillPracticeCooking(object):
            guid64 = 1
            allow_user_directed = True

        class FireplaceLight(object):
            guid64 = 2
            allow_user_directed = True

        class CheatSim(object):
            guid64 = 3
            allow_user_directed = True

        class KillSim(object):
            guid64 = 4
            allow_user_directed = True

        self.assertIsNone(e2_actuator.act_excluded(SkillPracticeCooking, False))
        self.assertIsNone(e2_actuator.act_excluded(FireplaceLight, False))
        self.assertEqual(e2_actuator.act_excluded(CheatSim, False), "deny_name")
        self.assertIsNone(e2_actuator.act_excluded(KillSim, False))


class SocialAndPhoneWordTests(unittest.TestCase):
    """2.31.0 (W4): the social and phone deny parts match whole words, as DENY_NAME_PARTS does. The kept
    exclusions (cheat, debug, travel, vacation, phone) still deny; Skill and Fireplace acts, and Border, are
    not hidden by them. 2.37.1: the judgement names (kill, move in, try for baby, careers) are hers now."""
    def setUp(self):
        load_probe()
        from ashley_e1 import e2_trial, e2_actuator
        self.trial = e2_trial
        self.actuator = e2_actuator

    def test_social_parts_match_whole_words(self):
        part = self.trial.denied_part
        social = self.trial.SOCIAL_DENY_PARTS
        for name in ("SkillSocialGreet", "SkillBasedChat", "FireplaceChat", "CampfireTalk", "TravelerChat"):
            with self.subTest(name=name):
                self.assertIsNone(part(name, social))
        cases = {"CheatSim": "cheat", "Cheating_Chat": "cheating", "DebugChat": "debug",
                 "TravelingSocial": "traveling", "VacationInvite": "vacation", "PhoneCall": "phone"}
        for name, entry in cases.items():
            with self.subTest(name=name):
                self.assertEqual(part(name, social), entry)
        for name in ("KillSim", "TryBaby", "Move_In_Sim", "CareersTalk", "AdoptionTalk", "BurnSocial"):
            with self.subTest(name=name):
                self.assertIsNone(part(name, social))

    def test_phone_parts_match_whole_words(self):
        part = self.trial.denied_part
        phone = self.actuator.PHONE_DENY_PARTS
        self.assertIsNone(part("Border_Chat", phone))
        self.assertIsNone(part("Recorder_Sample", phone))
        self.assertIsNone(part("Debugger_Chat", phone))
        self.assertEqual(part("Debug_Sample", phone), "debug")
        self.assertEqual(part("Cheating_Phone", phone), "cheating")
        self.assertEqual(part("Autonomous_Call", phone), "autonomous")
        self.assertEqual(part("Phone_NPC_Call", phone), "npc")
        # 2.37.1: the judgement names are hers; a phone act with them is on her menu.
        for name in ("Move_In_Sim", "Try_For_Baby", "Jobs_Board", "Ordering_Food"):
            with self.subTest(name=name):
                self.assertIsNone(part(name, phone))

    def test_the_actuator_uses_the_whole_word_rule_for_socials_and_phone_acts(self):
        def named(name, social=False):
            return type(name, (object,), {"guid64": 1, "allow_user_directed": True, "is_social": social})
        actuator = self.actuator
        self.assertEqual(actuator.act_excluded(named("CheatSocial", True), True), "deny_name")
        self.assertIsNone(actuator.act_excluded(named("KillSocial", True), True))
        self.assertIsNone(actuator.act_excluded(named("SkillSocialGreet", True), True))
        self.assertIsNone(actuator.act_excluded(named("FireplaceChat", True), True))
        self.assertIsNone(actuator.phone_act_excluded(named("phone_Border_Chat")))
        self.assertEqual(actuator.phone_act_excluded(named("phone_Cheat_Sim")), "deny_name")
        self.assertIsNone(actuator.phone_act_excluded(named("phone_Move_In_Sim")))


if __name__ == "__main__":
    unittest.main()
