"""D1 (Domus perception 1): no act the game returns for a listed object disappears without a named reason.

The fixture object is an invented toilet. Its acts exercise every filter the menu has today (not user directed,
a pie picker, a denied name, a hidden act, a social toward a thing, a folded text, the candidate and per-object
caps, a missing guid and a nameless pie choice), and the acts that advertise a need it relieves (bladder, hunger,
hygiene, energy, fun, social) stay options whatever those filters say. Refusals stay the game's own; the probe
never filters a relief act itself.

Names and ids are invented; no game text or real id appears here."""
import types
import unittest

import test_e2
import test_2160_act as acts
from test_binding import load_probe

GUID = "4242"
TOILET = "81"
OTHER = "82"


def _named(name, guid, **attributes):
    values = {"guid64": guid, "allow_user_directed": True}
    values.update(attributes)
    return type(name, (object,), values)


class ToiletSit(object):
    """The relief act itself: the game's own toilet act is often autonomous or hidden, and it still relieves."""
    guid64 = 5001
    allow_user_directed = False
    cheat = True
    advertised_motives = ("bladder",)


class ReliefHidden(object):
    guid64 = 5002
    allow_user_directed = True
    cheat = True
    advertised_motives = ("hygiene",)


class ReliefSocial(object):
    guid64 = 5003
    allow_user_directed = True
    is_social = True
    advertised_motives = ("social",)


class ReliefDenied(object):
    guid64 = 5004
    allow_user_directed = True
    advertised_motives = ("fun",)


class AutonomousOnly(object):
    guid64 = 5010
    allow_user_directed = False


class HiddenAct(object):
    guid64 = 5011
    allow_user_directed = True
    cheat = True


class SocialOnThing(object):
    guid64 = 5012
    allow_user_directed = True
    is_social = True


class CheatMoney(object):
    guid64 = 5013
    allow_user_directed = True


class NoGuid(object):
    guid64 = "no-guid"
    allow_user_directed = True


class ReadBook(object):
    guid64 = int(GUID)
    allow_user_directed = True
    display_name = types.SimpleNamespace(hash=0x7001)


class DuplicateRead(object):
    guid64 = 5014
    allow_user_directed = True
    display_name = types.SimpleNamespace(hash=0x7001)


def _cap_act(number):
    return _named("CapAct%d" % number, 5100 + number)


class _Choice(object):
    """One AffordanceObjectPair as a pie yields it (invented)."""

    def __init__(self, name, text_key, guid, hidden=False, denied=False):
        values = {"guid64": guid, "allow_user_directed": True}
        if hidden:
            values["cheat"] = True
        if denied:
            values["is_social"] = True
        self.affordance = type(name or "UnnamedChoice", (object,), values)
        self.text_key = text_key

    def name(self, context):
        return None if self.text_key is None else types.SimpleNamespace(hash=self.text_key)


class _NamelessChoice(object):
    affordance = None
    interaction_parameters = None

    def name(self, context):
        return None


class _Pie(object):
    def __init__(self, name, guid, choices):
        self.__name__ = name
        self.guid64 = guid
        self.allow_user_directed = True
        self._choices = choices

    def potential_interactions(self, target, context):
        return iter(list(self._choices))


def _item(obj, object_id, person=False):
    return {"object_id": str(object_id), "obj": obj, "definition_id": None,
            "class": type(obj).__name__, "distance_m": 2.0, "same_room": True, "room": "4",
            "on_lot": True, "person": person}


class FilterPathTests(unittest.TestCase):
    def setUp(self):
        load_probe()
        self.base = test_e2.ControlFlowTests()
        self.base.setUp()
        self.probe = self.base.probe
        self.context = self.probe.e2_actuator.build_context(self.base.sim)

    def tearDown(self):
        writer = self.base.LedgerWriter.instances[-1] if self.base.LedgerWriter.instances else None
        if writer is not None:
            writer.finish()

    def fixture(self):
        pie = _Pie("toilet_Choices_PieMenu", 5201, [
            _Choice("toilet_Snack", 0x7101, 5210),
            _NamelessChoice(),
            _Choice("toilet_Hidden", 0x7102, 5212, hidden=True),
            _Choice("CheatSnack", 0x7103, 5213, denied=True),
            _Choice("water_PieMenuChoice", 0x7104, 5214),
            _Choice("toilet_Snack", 0x7101, 5210),
        ])
        empty = type("toilet_Empty_PieMenu", (object,), {
            "guid64": 5200, "allow_user_directed": True,
            "potential_interactions": staticmethod(lambda target, context: iter(()))})
        affordances = [
            ToiletSit, ReliefHidden, ReliefSocial, ReliefDenied,
            AutonomousOnly, HiddenAct, SocialOnThing, CheatMoney, NoGuid,
            ReadBook, DuplicateRead, pie, empty,
        ] + [_cap_act(number) for number in range(20)]
        # The game's class-tuned list carries an affordance with no usable guid; that is the path NO_GUID names.
        fixture = type("FixtureToilet", (acts._Thing,), {"_super_affordances": affordances})
        return fixture(int(TOILET), 2.0, affordances)

    def test_every_filter_path_is_named_and_every_relief_act_is_an_option(self):
        obj = self.fixture()
        item = _item(obj, TOILET)
        jobs = self.probe._menu_offers(item, self.base.sim, self.context)
        names = [job["name"] for job in jobs]
        for relief in (ToiletSit, ReliefHidden, ReliefSocial, ReliefDenied):
            self.assertIn(relief.__name__, names)
            job = [candidate for candidate in jobs if candidate["name"] == relief.__name__][0]
            self.assertIs(job.get("need_relief"), True)
        codes = {entry["why"] for entry in item["excluded"]}
        for code in ("NOT_USER_DIRECTED", "MENU_HIDDEN", "SOCIAL", "DENY_NAME", "FOLDED",
                     "CAP", "NO_GUID", "NO_NAME", "PIE_PICKER", "PIE_EMPTY"):
            self.assertIn(code, codes)

    def test_the_payload_names_the_hidden_acts_of_a_listed_object_and_keeps_its_relief_acts(self):
        obj = self.fixture()
        item = _item(obj, TOILET)
        jobs = self.probe._menu_offers(item, self.base.sim, self.context)
        only_excluded = acts._Thing(int(OTHER), 3.0, [HiddenAct, AutonomousOnly])
        other = _item(only_excluded, OTHER)
        self.assertEqual(self.probe._menu_offers(other, self.base.sim, self.context), [])
        build = self.probe.act_menu.MenuBuild(
            jobs, lambda job: True, budget_ms=1e9, max_per_chunk=10000,
            excluded={str(TOILET): item["excluded"], str(OTHER): other["excluded"]},
            heads={str(OTHER): other})
        build.step()
        payload = build.payload(1, "4")
        by_id = {entry["object_id"]: entry for entry in payload["objects"]}
        toilet = by_id[TOILET]
        self.assertTrue(any(act.get("relief") is True for act in toilet["acts"]))
        self.assertIn("NOT_USER_DIRECTED", {entry["why"] for entry in toilet["excluded"]})
        self.assertEqual(by_id[OTHER]["acts"], [])
        self.assertEqual({entry["why"] for entry in by_id[OTHER]["excluded"]},
                         {"NOT_USER_DIRECTED", "MENU_HIDDEN"})
        row = self.probe.schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1,
                                            monotonic_ns=1, e2=payload)
        self.probe.schema.validate_record(row)

    def test_a_phone_that_offers_only_left_out_acts_is_listed_with_their_codes(self):
        self.base.sim.id = 900
        self.base.sim._phone_affordances = [
            _named("PhonePieMenu", 8100),
            _named("PhoneVisitLot", 8101),
            _named("PhoneIdle", 8102, allow_user_directed=False),
            _named("PhoneTidy", 8103, cheat=True),
        ]
        item = {"object_id": "900", "obj": self.base.sim, "phone": True, "person": False,
                "same_room": None, "on_lot": None, "distance_m": None, "room": None,
                "definition_id": None, "class": "phone", "spot": None, "level": None}
        excluded_phone = []
        jobs = self.probe._menu_phone_offers(item, self.base.sim, self.context, excluded_phone)
        self.assertEqual(jobs, [])
        self.assertEqual([entry["why"] for entry in item["excluded"]],
                         ["PIE_PICKER", "TRAVEL", "NOT_USER_DIRECTED", "MENU_HIDDEN"])
        self.assertEqual([entry["why"] for entry in excluded_phone],
                         ["pie_picker", "travel", "not_user_directed", "hidden"])
        build = self.probe.act_menu.MenuBuild(
            [], lambda job: True, excluded={"900": item["excluded"]}, heads={"900": item})
        build.step()
        payload = build.payload(1, None)
        phone = payload["objects"][0]
        self.assertEqual((phone["class"], phone["acts"]), ("phone", []))
        self.assertEqual([entry["why"] for entry in phone["excluded"]],
                         ["PIE_PICKER", "TRAVEL", "NOT_USER_DIRECTED", "MENU_HIDDEN"])
        row = self.probe.schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1,
                                            monotonic_ns=1, e2=payload)
        self.probe.schema.validate_record(row)

    def test_the_toilet_is_offered_and_used_though_the_game_marks_it_autonomous_and_hidden(self):
        self.base.objects[TOILET] = acts._Offer(int(TOILET), [ToiletSit])
        self.base.sim.test_super_affordance = lambda affordance, target, context: True
        item = _item(acts._Offer(int(TOILET), [ToiletSit]), TOILET)
        jobs = self.probe._menu_offers(item, self.base.sim, self.context)
        self.assertEqual([job["name"] for job in jobs], ["ToiletSit"])
        self.base.LedgerWriter.records = [self.base.continuing()[0]]
        self.assertTrue(self.probe._cmd_arm("HOME"))
        self.assertTrue(self.probe._cmd_start())
        self.base.tick()
        connection = self.probe._InboxReply("helper")
        ok = self.probe._inbox_dispatch(
            {"command": "act", "args": {"act_id": "a" * 32, "object_id": TOILET, "guid64": "5001"}},
            connection)
        self.assertTrue(ok, connection.lines)
        self.assertTrue(connection.lines[-1].startswith("ACT_PUSHED " + "a" * 32))
        self.assertIn((5001, int(TOILET)), [(guid, target) for guid, target, _context in self.base.pushes])


class ReliefReadTests(unittest.TestCase):
    def setUp(self):
        load_probe()
        from ashley_e1 import e2_actuator
        self.actuator = e2_actuator

    def test_a_relief_is_read_from_advertised_motives_the_static_commodities_or_the_autonomy_ads(self):
        explicit = _named("ExplicitRelief", 1, advertised_motives=("bladder",))
        static = _named("StaticRelief", 2, _static_commodities=(
            types.SimpleNamespace(guid64=16656),
            types.SimpleNamespace(static_commodity=types.SimpleNamespace(guid64=16657)),
        ))
        ads = _named("AdsRelief", 3, _autonomy_ads={
            16652: types.SimpleNamespace(
                _stat_type=types.SimpleNamespace(guid64=16652),
                _op_list=[types.SimpleNamespace(_amount=2.0, _advertise=True)]),
            16654: types.SimpleNamespace(
                _stat_type=types.SimpleNamespace(guid64=16654),
                _op_list=[types.SimpleNamespace(_amount=-2.0, _advertise=True)]),
        })
        self.assertEqual(self.actuator.relief_motives(explicit), ("bladder",))
        self.assertEqual(self.actuator.relief_motives(static), ("hunger", "hygiene"))
        self.assertEqual(self.actuator.relief_motives(ads), ("bladder",))
        self.assertFalse(self.actuator.need_relief(_named("Plain", 4)))
        self.assertTrue(self.actuator.need_relief(explicit))

    def test_a_phone_pie_and_a_travelling_act_are_named_for_her_phone(self):
        phone = _named("PhonePieMenu", 1)
        travel = _named("PhoneVisitLot", 2)
        self.assertEqual(self.actuator.phone_act_excluded(phone), "pie_picker")
        self.assertEqual(self.actuator.phone_act_excluded(travel), "travel")


if __name__ == "__main__":
    unittest.main()
