"""2.29.0: her own phone is on her menu. The phone's acts come from her Sim's own list, target her
Sim, and never take her off the lot; an act on her Sim is offered by her phone and nothing else."""
import types
import unittest

import test_2160_act as acts
import test_2280_alias as alias
from test_2160_act import GUID, ReadBook

SIM_ID = 9001  # invented id for her Sim


class PhoneSampleRing(object):
    guid64 = 5001
    allow_user_directed = True


class PhoneSampleNote(object):
    guid64 = 5002
    allow_user_directed = True


class PhoneSampleUntested(object):
    guid64 = 5003
    allow_user_directed = True


class PhoneSampleCheat(object):
    guid64 = 5004
    allow_user_directed = True
    cheat = True


class PhoneSampleAutonomous(object):
    guid64 = 5005
    allow_user_directed = False


class PhoneSampleTravelHome(object):
    guid64 = 5006
    allow_user_directed = True


class PhoneSampleVisitLot(object):
    guid64 = 5007
    allow_user_directed = True


class PhoneSample_go_to_lot(object):
    guid64 = 5008
    allow_user_directed = True


class TravelSampleBase(object):
    pass


class PhoneSampleFlight(TravelSampleBase):
    guid64 = 5009
    allow_user_directed = True


class PhoneSampleInviteOver(object):
    guid64 = 5010
    allow_user_directed = True


class PhoneSampleMessage(object):
    guid64 = 5011
    allow_user_directed = True


def her_phone(sim):
    sim.id = SIM_ID
    sim._phone_affordances = [PhoneSampleRing, PhoneSampleNote, PhoneSampleUntested, PhoneSampleCheat,
                              PhoneSampleAutonomous, PhoneSampleTravelHome, PhoneSampleVisitLot,
                              PhoneSample_go_to_lot, PhoneSampleFlight, PhoneSampleInviteOver]
    return sim


class PhoneMenuTests(unittest.TestCase):
    def setUp(self):
        self.case = acts.MenuSenseTests()
        self.case.setUp()
        self.probe = self.case.probe
        self.case.things = []
        self.case.allowed = {5001, 5002, 5004, 5005, 5006, 5007, 5008, 5009, 5010, int(GUID)}
        her_phone(self.case.base.sim)

    def tearDown(self):
        self.case.tearDown()

    def _payload(self):
        jobs, room = self.probe._menu_jobs(self.case.row)
        build = self.probe.act_menu.MenuBuild(jobs, self.probe._menu_test, budget_ms=1e9, max_per_chunk=10_000)
        build.step()
        return build.payload(1, room)

    def test_version(self):
        self.assertEqual(self.probe.schema.PROBE_VERSION, "2.37.0")

    def test_the_phone_entry_lists_only_allowed_and_test_passing_phone_acts(self):
        payload = self._payload()
        self.assertEqual(len(payload["objects"]), 1)
        entry = payload["objects"][0]
        self.assertEqual((entry["object_id"], entry["class"], entry["phone"]), (str(SIM_ID), "phone", True))
        self.assertEqual((entry["definition_id"], entry["distance_m"], entry["same_room"], entry["reach"]),
                         (None, None, None, None))
        # Ring, Note and InviteOver pass the game's test and the phone rules; Untested is refused by
        # the game; the rest are a cheat, autonomous-only, a travel act, or travel by MRO.
        self.assertEqual([act["guid64"] for act in entry["acts"]], ["5001", "5002", "5010"])
        self.assertEqual([act["name"] for act in entry["acts"]],
                         ["PhoneSampleRing", "PhoneSampleNote", "PhoneSampleInviteOver"])
        row = self.probe.schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1,
                                            monotonic_ns=1, e2=payload)
        self.probe.schema.validate_record(row)

    def test_a_travel_phone_act_is_left_out_by_name_visit_lot_go_to_and_by_its_class_chain(self):
        excluded = self.probe.e2_actuator.phone_excluded
        self.assertEqual(excluded(PhoneSampleTravelHome), "travel")
        self.assertEqual(excluded(PhoneSampleVisitLot), "travel")
        self.assertEqual(excluded(PhoneSample_go_to_lot), "travel")
        self.assertEqual(excluded(PhoneSampleFlight), "travel")
        self.assertIsNone(excluded(PhoneSampleRing))
        self.assertNotIn("5006", [act["guid64"] for act in self._payload()["objects"][0]["acts"]])
        self.assertNotIn("5009", [act["guid64"] for act in self._payload()["objects"][0]["acts"]])

    def test_inviting_over_is_on_her_phone_though_invite_is_a_deny_name_elsewhere(self):
        actuator = self.probe.e2_actuator
        self.assertEqual(actuator.act_excluded(PhoneSampleInviteOver, False), "deny_name")
        self.assertIsNone(actuator.phone_act_excluded(PhoneSampleInviteOver))
        self.assertIn("5010", [act["guid64"] for act in self._payload()["objects"][0]["acts"]])

    def test_phone_names_keep_out_trips_money_emergencies_and_testers(self):
        actuator = self.probe.e2_actuator
        def named(name):
            return type(name, (object,), {"guid64": 1, "allow_user_directed": True})
        for kept in ("phone_Picker_Chat", "phone_Picker_Text", "phone_Picker_Invite_Over",
                     "phone_Picker_VideoCall", "phone_Picker_PrankCall"):
            self.assertIsNone(actuator.phone_act_excluded(named(kept)), kept)
        for out in ("phone_mapPicker_AskOnDate", "phone_Picker_InviteTo_NEW", "phone_simPicker_AskOnHangout_CAD",
                    "phone_simPicker_InviteToJoinVacation", "phone_CallBackToLodging", "phone_Burglar_CallPolice",
                    "phone_Business_MakeBusinessCalls", "phone_Picker_Chat_Autonomous", "phone_CallOver_EventNPC",
                    "phone_Debug_Sample", "phone_Sample_PieMenu"):
            self.assertIsNotNone(actuator.phone_act_excluded(named(out)), out)

    def test_a_cheat_an_autonomous_only_or_untested_phone_act_is_left_out(self):
        guids = [act["guid64"] for act in self._payload()["objects"][0]["acts"]]
        self.assertNotIn("5003", guids)
        self.assertNotIn("5004", guids)
        self.assertNotIn("5005", guids)

    def test_her_phone_is_at_most_the_phone_act_cap_which_is_past_an_objects_cap(self):
        # 2.37.0 (W10 P3): her phone is one entry for all its acts; call and invite came after the 8th.
        many = [type("PhoneSampleMany%d" % i, (object,), {"guid64": 6000 + i, "allow_user_directed": True})
                for i in range(60)]
        self.case.base.sim._phone_affordances = many
        self.case.allowed = {6000 + i for i in range(60)}
        entry = self._payload()["objects"][0]
        self.assertEqual(len(entry["acts"]), self.probe.schema.MENU_MAX_PHONE_ACTS)
        self.assertGreater(self.probe.schema.MENU_MAX_PHONE_ACTS, self.probe.schema.MENU_MAX_ACTS)

    def test_no_phone_list_means_no_phone_entry(self):
        del self.case.base.sim._phone_affordances
        self.assertEqual(self._payload()["objects"], [])

    def test_her_phone_is_never_a_person_in_the_menu(self):
        payload = self._payload()
        self.assertEqual([item["class"] for item in payload["objects"]], ["phone"])
        self.assertNotIn("sim", [item["class"] for item in payload["objects"]])

    def test_the_phone_entry_sits_after_her_room_and_is_never_folded_with_another_object(self):
        act_menu = self.probe.act_menu
        here = [{"object_id": "h1", "definition_id": "d1", "same_room": True, "on_lot": True,
                 "room": "4", "distance_m": 1.0},
                {"object_id": "h2", "definition_id": "d2", "same_room": True, "on_lot": True,
                 "room": "4", "distance_m": 2.0}]
        far = [{"object_id": "f1", "definition_id": "d3", "same_room": False, "on_lot": True,
                "room": "5", "distance_m": 9.0}]
        phone = {"object_id": str(SIM_ID), "phone": True, "person": False, "same_room": None,
                 "on_lot": None, "distance_m": None, "room": None}
        items = [phone] + act_menu.ordered(here + far)

        guids = {"h1": "7001", "h2": "7002", "f1": "7003"}

        def offers(item):
            # Her phone offers the same act as h1: the object rule would fold it, the phone is kept.
            return [{"guid64": guids.get(item["object_id"], "7001")}]

        picked = [item["object_id"] for item, _acts in act_menu.pick(items, offers)]
        self.assertEqual(picked, ["h1", "h2", str(SIM_ID), "f1"])

    def test_phone_rows_validate_and_the_phone_key_is_optional(self):
        schema = self.probe.schema
        payload = {"menu_rev": 1, "room": None, "tested": 1, "refused": 0, "build_ms": 1.0, "part": 0, "parts": 1,
                   "objects": [
            {"object_id": "1", "definition_id": None, "class": "c", "distance_m": 1.0, "same_room": True,
             "reach": True, "room": None, "acts": [{"guid64": "1", "name": "n", "text_key": None}]}]}
        row = schema.make_record("act_menu", telemetry_session_id="s", wall_timestamp_ms=1, monotonic_ns=1,
                                 e2=payload)
        schema.validate_record(row)
        self.assertIsNone(row["e2"]["objects"][0]["phone"])
        row["e2"]["objects"][0]["phone"] = "yes"
        with self.assertRaises(schema.SchemaError):
            schema.validate_record(row)


class PhoneActTests(unittest.TestCase):
    def setUp(self):
        self.case = acts.ActCommandTests()
        self.case.setUp()
        self.base = self.case.base
        self.probe = self.case.probe
        her_phone(self.base.sim)
        self.base.objects[str(SIM_ID)] = self.base.sim

    def tearDown(self):
        self.case.tearDown()

    def pushed(self):
        return [row for row in self.case.events() if row["phase"] == "PUSHED"]

    def test_pushing_a_phone_act_targets_her_sim_and_goes_through_alias_tracking(self):
        self.case.ready()
        alias.picker_push(self.base)
        ok, connection = self.case.act(object_id=str(SIM_ID), guid64="5001")
        self.assertTrue(ok, connection.lines)
        self.assertEqual(self.base.pushes[-1][:2], (5001, SIM_ID))
        self.assertEqual(self.pushed()[0]["interaction_id"], "704")
        self.assertEqual(self.pushed()[0]["aliases"], ["703"])
        self.assertEqual(self.pushed()[0]["tuning_name"], "PhoneSampleRing")

    def test_an_act_on_her_sim_with_a_guid_outside_her_phone_is_not_offered(self):
        self.case.ready()
        ok, connection = self.case.act(object_id=str(SIM_ID), guid64=GUID)
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT NOT_OFFERED")
        self.assertEqual(self.base.pushes, [])

    def test_a_phone_act_the_game_refuses_is_refused_and_nothing_is_pushed(self):
        self.case.ready()
        self.case.allowed = False
        ok, connection = self.case.act(object_id=str(SIM_ID), guid64="5001")
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT GAME_REFUSED")
        self.assertEqual(self.base.pushes, [])

    def test_a_travel_phone_act_is_refused_at_the_act_by_the_travel_rule(self):
        self.case.ready()
        ok, connection = self.case.act(act_id="%032x" % 2, object_id=str(SIM_ID), guid64="5008")
        self.assertFalse(ok)
        self.assertEqual(connection.lines[-1], "ACT_REJECT EXCLUDED")
        rejected = [row for row in self.case.events() if row["phase"] == "REJECTED"]
        self.assertEqual((rejected[-1]["code"], rejected[-1]["detail"]), ("EXCLUDED", "travel"))
        self.assertEqual(self.base.pushes, [])

    def test_inviting_people_over_from_her_phone_is_pushed(self):
        self.case.ready()
        ok, _connection = self.case.act(act_id="%032x" % 4, object_id=str(SIM_ID), guid64="5010")
        self.assertTrue(ok)
        self.assertEqual(len(self.base.pushes), 1)

    def test_a_phone_act_on_another_object_still_uses_its_own_offers(self):
        self.case.ready()
        ok, connection = self.case.act(act_id="%032x" % 3, object_id=acts.CHAIR, guid64=GUID)
        self.assertTrue(ok, connection.lines)
        self.assertEqual(self.base.pushes[-1][:2], (int(GUID), int(acts.CHAIR)))


if __name__ == "__main__":
    unittest.main()
