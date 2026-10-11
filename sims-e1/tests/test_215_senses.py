"""2.15.0 (schema 8), from the 2026-10-05 live session: presence that cannot go blind
(D40), sampling that survives travel (D41), no creating tracker getters (D42), what she
knows about others and feels toward them, and what she is like and has. Game-shaped
fakes, built from the 1.128 bytecode."""
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

import test_ds3_senses as ds3
import test_s5_senses as s5
from test_binding import FakeWriter, load_probe
from test_ds1_senses import CreatingTrackers, stat_component_of
from test_ds3_senses import _Wrapper


class trait_Cheerful(object):
    display_name = _Wrapper(0x3001)


class trait_Loner(object):
    display_name = _Wrapper(0x3002)


class trait_HiddenGameplay(object):
    display_name = None


class Career_Doctor(object):
    pass


class Sentiment_Close(object):
    display_name = _Wrapper(0x4001)


class statistic_Skill_AdultMajor_Charisma(object):
    skill_level_type = "MAJOR"
    stat_name = _Wrapper(0x5001)


class statistic_Skill_AdultMajor_Cooking(object):
    skill_level_type = "MAJOR"
    stat_name = _Wrapper(0x5002)


class commodity_Motive_Hunger(object):
    pass


class _Skill(object):
    def __init__(self, cached, value, level_of_value):
        self._user_value = cached
        self._value = value
        self._level = level_of_value

    def convert_to_user_value(self, value):
        return self._level if value == self._value else None

    def get_user_value(self):
        raise AssertionError("get_user_value caches into _user_value (a store)")


def _knowledge(**fields):
    base = dict(_known_traits=set(), _knows_career=False, _knows_rel_status=False,
                _knows_romantic_preference=False, _known_net_worth=None)
    base.update(fields)
    return types.SimpleNamespace(**base)


class _Side(object):
    def __init__(self, knowledge, sentiments=None):
        self._knowledge = knowledge
        self._sentiment_tracker = (None if sentiments is None else
                                   types.SimpleNamespace(_statistics=sentiments))

    @property
    def knowledge(self):
        return self._knowledge

    def initialize_knowledge(self):
        raise AssertionError("initialize_knowledge creates the record")


class _SidedRelationship(s5._Relationship):
    def __init__(self, hers, theirs, her_id=100):
        s5._Relationship.__init__(self)
        self._sim_id_a = her_id
        self._sim_a_relationship_data = hers
        self._sim_b_relationship_data = theirs

    def get_knowledge(self, *args, **kwargs):
        raise AssertionError("get_knowledge creates the record")


class RelationshipKnowledgeTests(unittest.TestCase):
    def setUp(self):
        ds3.PollOnceTests.setUp(self)
        self.hers = _Side(_knowledge(_known_traits={trait_Cheerful}, _knows_career=True,
                                     _knows_rel_status=True, _known_net_worth=18000),
                          sentiments={Sentiment_Close: object()})
        theirs = _Side(_knowledge(_known_traits={trait_Loner}, _knows_romantic_preference=True))
        self.service = s5._RelService({(100, 200): _SidedRelationship(self.hers, theirs)})
        sys.modules["services"].relationship_service = lambda: self.service
        self.near.career_tracker = types.SimpleNamespace(_careers={1: Career_Doctor()})

    def row(self):
        return ds3.PollOnceTests.row(self)

    def test_what_she_has_learned_about_them_from_her_side_only(self):
        near = self.row()["presence"][1]
        self.assertEqual(near["relationship"]["knows"], {
            "traits": [{"trait": "trait_Cheerful", "text_key": str(0x3001)}],
            "careers": ["Career_Doctor"], "relationship_status": True,
            "romantic_preference": False, "net_worth": 18000})
        self.assertEqual(near["relationship"]["sentiments"],
                         [{"sentiment": "Sentiment_Close", "text_key": str(0x4001)}])

    def test_her_side_is_b_when_her_id_is_larger(self):
        relationship = self.service._relationships[(100, 200)]
        relationship._sim_id_a = 200
        relationship._sim_a_relationship_data, relationship._sim_b_relationship_data = (
            relationship._sim_b_relationship_data, relationship._sim_a_relationship_data)
        near = self.row()["presence"][1]
        self.assertEqual(near["relationship"]["knows"]["traits"][0]["trait"], "trait_Cheerful")

    def test_nothing_learned_yet_is_empty_not_created(self):
        self.hers._knowledge = None
        self.hers._sentiment_tracker = None
        near = self.row()["presence"][1]
        self.assertEqual(near["relationship"]["knows"], {
            "traits": [], "careers": None, "relationship_status": False,
            "romantic_preference": False, "net_worth": None})
        self.assertEqual(near["relationship"]["sentiments"], [])

    def test_career_unknown_stays_none(self):
        self.hers._knowledge._knows_career = False
        self.assertIsNone(self.row()["presence"][1]["relationship"]["knows"]["careers"])


class SelfTests(unittest.TestCase):
    def setUp(self):
        _, self.probe, _ = load_probe()

    def _sim_info(self):
        info = CreatingTrackers()
        info.trait_tracker = types.SimpleNamespace(
            _equipped_traits=[trait_Loner, trait_HiddenGameplay, trait_Cheerful],
            _equipped_personality_traits=[trait_Cheerful])
        info.get_component = stat_component_of(commodity={
            statistic_Skill_AdultMajor_Charisma: _Skill(None, 900.0, 3),
            statistic_Skill_AdultMajor_Cooking: _Skill(5, 2500.0, 99),
            commodity_Motive_Hunger: types.SimpleNamespace(_value=40.0)})
        info.household = types.SimpleNamespace(_funds=types.SimpleNamespace(_funds=18750))
        return info

    def test_traits_skills_and_money(self):
        own = self.probe.observers.read_self(self._sim_info())
        self.assertEqual(own["traits"], [
            {"trait": "trait_Cheerful", "text_key": str(0x3001), "personality": True},
            {"trait": "trait_Loner", "text_key": str(0x3002), "personality": False}])
        self.assertEqual(own["skills"], [
            {"skill": "statistic_Skill_AdultMajor_Cooking", "text_key": str(0x5002),
             "level": 5},
            {"skill": "statistic_Skill_AdultMajor_Charisma", "text_key": str(0x5001),
             "level": 3}])
        self.assertEqual(own["funds"], 18750)

    def test_unreadable_parts_are_none(self):
        own = self.probe.observers.read_self(CreatingTrackers())
        self.assertEqual(own, {"traits": None, "skills": None, "funds": None, "careers": None, "wants": None,
                               "life": {"age": None, "pregnant": None, "sick": None, "dead": None,
                                        "ghost": None, "npc": None}})

    def test_poll_row_carries_self_and_validates(self):
        ds3.PollOnceTests.setUp(self)
        lab = self.lab
        lab.trait_tracker = self._sim_info().trait_tracker
        lab.household = types.SimpleNamespace(_funds=types.SimpleNamespace(_funds=500))
        row = ds3.PollOnceTests.row(self)
        self.assertEqual(row["schema_version"], 18)
        self.assertEqual(row["self"]["funds"], 500)
        self.assertEqual(row["self"]["traits"][0]["trait"], "trait_Cheerful")
        self.assertEqual([item["on_lot"] for item in row["presence"]], [True, True, True])


class PresenceMissTests(unittest.TestCase):
    def setUp(self):
        ds3.PollOnceTests.setUp(self)

    def test_a_skipped_sim_makes_the_row_incomplete_and_says_so(self):
        """D40: rows with no one in presence still claimed observation_complete."""
        class Broken(object):
            id = 999

            def get_sim_instance(self, allow_hidden_flags=None):
                raise RuntimeError("mid-spawn")

        manager = sys.modules["services"].sim_info_manager()
        manager._infos.append(Broken())
        row = ds3.PollOnceTests.row(self)
        self.assertFalse(row["observation_complete"])
        self.assertEqual(row["missingness"]["presence"],
                         {"status": "MISSING", "detail": "skipped 1 Sims"})
        self.assertEqual(len(row["presence"]), 3)

    def test_a_sim_that_cannot_be_described_is_counted_too(self):
        class Unreadable(object):
            is_selectable = False

            @property
            def id(self):
                raise RuntimeError("half built")

            def get_sim_instance(self, allow_hidden_flags=None):
                return types.SimpleNamespace()

        manager = sys.modules["services"].sim_info_manager()
        manager._infos.append(Unreadable())
        row = ds3.PollOnceTests.row(self)
        self.assertFalse(row["observation_complete"])
        self.assertEqual(row["missingness"]["presence"]["detail"], "skipped 1 Sims")

    def test_a_clean_read_stays_complete(self):
        row = ds3.PollOnceTests.row(self)
        self.assertTrue(row["observation_complete"])
        self.assertEqual(row["missingness"], {})


class TravelTests(unittest.TestCase):
    """D41 (live 2026-10-05): each trip to another lot left sampling stopped."""

    def setUp(self):
        _, self.probe, self.calls = load_probe()
        services = sys.modules["services"]
        self.zone = object()
        services.current_zone = lambda: self.zone
        self.assertTrue(self.probe._cmd_arm("LAB_E1_FORK"))
        self.assertTrue(self.probe._dispatch_start())
        self.writer = FakeWriter.instances[-1]

        def loading(*args, **kwargs):
            raise self.probe.observers.LabIdentityAmbiguous(0)

        self.probe.observers.poll_once = loading

    def _travel(self):
        self.zone = object()

    def test_loading_screen_waits_without_rows_then_resumes_in_the_new_zone(self):
        for _ in range(5):
            self.probe._poll_tick()
        self.assertEqual(self.probe._STATE, "SAMPLING")
        self.assertEqual(self.writer.rows, [])
        self._travel()
        self.probe._INBOX_ZONE = self.zone
        self.assertTrue(self.probe._start_inbox_pump("manager"))
        self.assertEqual(self.probe._STATE, "SAMPLING")
        self.assertIs(self.probe._ALARM_ZONE, self.zone)
        reasons = [row.get("checkpoint_reason") for row in self.writer.rows]
        self.assertEqual(reasons, ["ZONE_RESUMED"])
        self.probe.schema.validate_record(self.writer.rows[0])
        sampling_alarms = [entry for entry in self.calls["alarms"]
                           if entry[2]["callback"] is self.probe._poll_tick]
        self.assertEqual(len(sampling_alarms), 2)

    def test_a_long_loading_screen_waits_and_says_so_once(self):
        """2.15.2: a first load after a relaunch can take longer than a minute."""
        for _ in range(3 * self.probe.ZONE_SETTLE_TICKS):
            self.probe._poll_tick()
        self.assertEqual(self.probe._STATE, "SAMPLING")
        self.assertEqual([row.get("checkpoint_reason") for row in self.writer.rows],
                         ["WAITING_FOR_BODY"])
        self.probe.schema.validate_record(self.writer.rows[0])

    def test_the_users_stop_holds_across_travel(self):
        self.assertTrue(self.probe._dispatch_stop())
        self._travel()
        self.assertFalse(self.probe._resume_sampling_in_zone())
        self.assertEqual(self.probe._STATE, "ARMED")

    def test_same_zone_is_left_alone(self):
        before = len(self.calls["alarms"])
        self.assertTrue(self.probe._resume_sampling_in_zone())
        self.assertEqual(len(self.calls["alarms"]), before)
        self.assertEqual(self.writer.rows, [])

    def test_other_guards_still_stop_at_once(self):
        def broken(*args, **kwargs):
            raise self.probe.observers.LabIdentityAmbiguous(2)

        self.probe.observers.poll_once = broken
        self.probe._poll_tick()
        self.assertEqual(self.probe._STATE, "ARMED")


if __name__ == "__main__":
    unittest.main()
