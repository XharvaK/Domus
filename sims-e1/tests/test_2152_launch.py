"""2.15.2 (schema 9), from the 2026-10-05 sessions: sampling that carries over to the
next launch of the same save (D47), a warning before the telemetry folder fills (D48),
whose lot she is on, the situations Sims are in, and the game's pop-ups. Game-shaped
fakes, built from the 1.128 bytecode."""
import json
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
from test_binding import FakeWriter, load_probe
from test_ds3_senses import _Wrapper


def _row(probe, guid="guid", slot="slot"):
    return probe.schema.make_record(
        "presence_snapshot", telemetry_session_id=probe.get_status()["telemetry_session_id"],
        wall_timestamp_ms=10, monotonic_ns=20, observation_complete=True,
        attestation=probe.schema.attestation("LAB_E1_FORK"),
        save={"save_slot_guid": guid, "slot_id": slot},
        body={"sim_id": "77", "instantiated": True, "is_selectable": True,
              "is_selected": None, "posture": None},
        interactions={"observed": [], "queue_truncated": False,
                      "running_truncated": False, "observation_complete": True})


def _save(services, guid, slot):
    services.get_persistence_service = lambda: types.SimpleNamespace(
        get_save_slot_proto_guid=lambda: guid,
        get_save_slot_proto_buff=lambda: types.SimpleNamespace(slot_id=slot))


class LaunchTests(unittest.TestCase):
    """D47 (live 2026-10-05): after a relaunch nothing was recorded until the probe was
    armed by hand; the User's cleanup and the book put back were lost."""

    def setUp(self):
        _, self.probe, _ = load_probe()
        self.root = self.probe._TELEMETRY_ROOT
        self.zone = object()
        sys.modules["services"].current_zone = lambda: self.zone
        self.assertTrue(self.probe._cmd_arm("LAB_E1_FORK"))
        self.assertTrue(self.probe._dispatch_start())
        self.probe.observers.poll_once = lambda session, name: _row(self.probe)
        self.probe._poll_tick()  # session_open: the save this sampling belongs to

    def path(self):
        return os.path.join(self.root, "autosample.json")

    def relaunch(self, guid="guid", slot="slot"):
        _, probe, _ = load_probe()
        probe._TELEMETRY_ROOT = self.root
        services = sys.modules["services"]
        zone = object()
        services.current_zone = lambda: zone
        _save(services, guid, slot)
        return probe

    def test_the_start_is_remembered_for_its_save(self):
        with open(self.path(), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), {"armed_name": "LAB_E1_FORK",
                                                 "save_slot_guid": "guid",
                                                 "slot_id": "slot", "sim_id": "77"})

    def test_the_same_save_starts_by_itself_on_the_next_launch(self):
        probe = self.relaunch()
        self.assertTrue(probe._supervise_sampling())
        self.assertEqual(probe._STATE, "SAMPLING")
        self.assertTrue(probe._RESUME_SAMPLING)
        rows = FakeWriter.instances[-1].rows
        self.assertEqual([row.get("checkpoint_reason") for row in rows], ["AUTOSTARTED"])
        probe.schema.validate_record(rows[0])

    def test_another_save_is_never_sampled(self):
        probe = self.relaunch(guid="other")
        self.assertFalse(probe._supervise_sampling())
        self.assertEqual(probe._STATE, "UNARMED")

    def test_a_save_not_yet_readable_is_tried_again(self):
        probe = self.relaunch(guid=None)
        self.assertFalse(probe._supervise_sampling())
        _save(sys.modules["services"], "guid", "slot")
        self.assertTrue(probe._supervise_sampling())

    def test_the_users_stop_forgets_it(self):
        self.assertTrue(self.probe._dispatch_stop())
        self.assertFalse(os.path.exists(self.path()))
        probe = self.relaunch()
        self.assertFalse(probe._supervise_sampling())
        self.assertEqual(probe._STATE, "UNARMED")

    def test_the_users_disarm_forgets_it(self):
        self.assertTrue(self.probe._dispatch_disarm())
        self.assertFalse(os.path.exists(self.path()))


class DirFillTests(unittest.TestCase):
    """D48 (live 2026-10-05): 121 of 200 MB and no warning before sampling would stop."""

    def test_one_warning_past_three_quarters(self):
        _, probe, _ = load_probe()
        self.assertTrue(probe._cmd_arm("LAB_E1_FORK"))
        self.assertTrue(probe._cmd_start())
        writer = FakeWriter.instances[-1]
        writer.max_dir_bytes = 1000
        writer._logical_directory_bytes = 740
        probe.observers.poll_once = lambda session, name: _row(probe)
        probe._poll_tick()
        self.assertNotIn("TELEMETRY_DIR_75", [r.get("checkpoint_reason") for r in writer.rows])
        writer._logical_directory_bytes = 760
        probe._poll_tick()
        probe._poll_tick()
        reasons = [r.get("checkpoint_reason") for r in writer.rows]
        self.assertEqual(reasons.count("TELEMETRY_DIR_75"), 1)
        self.assertEqual(probe._inbox_status()["telemetry_dir"], {"bytes": 760, "cap": 1000})


class Residential(object):
    pass


class situation_Visit(object):
    def __init__(self, members):
        self._situation_sims = members


class situation_Party(situation_Visit):
    pass


class RoleState_Visitor(object):
    pass


class RoleState_Host(object):
    pass


class _Situations(dict):
    pass


class PlaceAndSituationTests(unittest.TestCase):
    def setUp(self):
        ds3.PollOnceTests.setUp(self)
        services = sys.modules["services"]
        self.zone = types.SimpleNamespace(
            lot=types.SimpleNamespace(zone_owner_household_id=4242),
            venue_service=types.SimpleNamespace(_active_venue=Residential()))
        services.current_zone = lambda: self.zone
        self.lab.household_id = 777

    def row(self):
        return ds3.PollOnceTests.row(self)

    def test_a_guest_in_someone_elses_home(self):
        """Live 2.15.0: cooking on a host's stove drew reaction_Inappropriate."""
        self.assertEqual(self.row()["place"], {"owner_household_id": "4242",
                                               "her_home": False, "venue": "Residential"})

    def test_her_own_home(self):
        self.lab.household_id = 4242
        self.assertTrue(self.row()["place"]["her_home"])

    def test_an_unowned_lot(self):
        self.zone.lot.zone_owner_household_id = 0
        self.assertEqual(self.row()["place"]["owner_household_id"], None)
        self.assertFalse(self.row()["place"]["her_home"])

    def test_situations_and_roles_per_sim(self):
        body, near = self.body, self.near.get_sim_instance()
        visit = situation_Visit({near: types.SimpleNamespace(
            current_role_state_type=RoleState_Visitor)})
        party = situation_Party({body: types.SimpleNamespace(
            current_role_state_type=RoleState_Host),
            near: types.SimpleNamespace(current_role_state_type=RoleState_Visitor)})
        manager = _Situations({1: visit, 2: party})
        sys.modules["services"].get_zone_situation_manager = lambda zone_id=None: manager
        by_id = {item["id"]: item for item in self.row()["presence"]}
        self.assertEqual(by_id["100"]["situations"],
                         [{"situation": "situation_Party", "role": "RoleState_Host"}])
        self.assertEqual(by_id["200"]["situations"], [
            {"situation": "situation_Visit", "role": "RoleState_Visitor"},
            {"situation": "situation_Party", "role": "RoleState_Visitor"}])
        self.assertEqual(by_id["300"]["situations"], [])

    def test_unreadable_situations_are_none_not_empty(self):
        self.assertIsNone(self.row()["presence"][0]["situations"])


class UiDialogOkCancel(object):
    def __init__(self, owner, title, text):
        self._owner = lambda: owner
        self.title, self.text = _Wrapper(title), _Wrapper(text)
        self.text_ok, self.text_cancel = _Wrapper(0x6001), _Wrapper(0x6002)
        self.response = None

    def respond(self, response):
        raise AssertionError("the probe never answers a dialog")


class UiDialogResponse(object):
    def __init__(self, dialog_response_id, text):
        self.dialog_response_id, self.text = dialog_response_id, _Wrapper(text)


class UiDialog(object):
    def __init__(self, owner):
        self._owner = lambda: owner
        self.title, self.text = None, _Wrapper(0x7001)
        self.ui_responses = (UiDialogResponse(10004, 0x7002),)
        self._additional_responses = (UiDialogResponse(10005, 0x7003),)
        self.response = None

    @property
    def responses(self):
        raise AssertionError("responses builds new response objects")


class DialogTests(unittest.TestCase):
    """Live 2026-10-05: a question about a new like (trait_SimPreference_...) was answered for
    her and never sensed."""

    def setUp(self):
        ds3.PollOnceTests.setUp(self)
        self.service = types.SimpleNamespace(_active_dialogs={},
                                             _auto_respond_alarm_handles={})
        sys.modules["services"].ui_dialog_service = lambda: self.service
        self.fitness = UiDialogOkCancel(self.lab, 0x5001, 0x5002)

    def row(self):
        return ds3.PollOnceTests.row(self)

    def test_an_open_question_with_its_choices(self):
        self.service._active_dialogs[555] = self.fitness
        dialogs = self.row()["dialogs"]
        self.assertEqual(dialogs["open"], [{
            "dialog_id": "555", "kind": "UiDialogOkCancel", "owner_id": "100",
            "title_key": str(0x5001), "text_key": str(0x5002),
            "responses": [{"response": "ok", "text_key": str(0x6001)},
                          {"response": "cancel", "text_key": str(0x6002)}],
            "auto_respond": False, "rows": [], "held": False, "cause": None, "select": None,
            "counts": None, "text_inputs": None}])
        self.assertEqual(dialogs["closed"], [])
        again = self.row()["dialogs"]  # still showing: open, never closed
        self.assertEqual([item["dialog_id"] for item in again["open"]], ["555"])
        self.assertEqual(again["closed"], [])

    def test_an_ok_only_dialog_offers_only_ok(self):
        self.fitness.text_cancel = None
        self.service._active_dialogs[555] = self.fitness
        responses = self.row()["dialogs"]["open"][0]["responses"]
        self.assertEqual([item["response"] for item in responses], ["ok"])

    def test_the_answer_once_it_is_gone(self):
        self.service._active_dialogs[555] = self.fitness
        self.row()
        del self.service._active_dialogs[555]
        self.fitness.response = 10001
        dialogs = self.row()["dialogs"]
        self.assertEqual(dialogs["open"], [])
        self.assertEqual(dialogs["closed"], [{
            "dialog_id": "555", "kind": "UiDialogOkCancel", "title_key": str(0x5001),
            "text_key": str(0x5002), "response": "ok"}])
        self.assertEqual(self.row()["dialogs"]["closed"], [])  # reported once

    def test_tuned_responses_and_the_games_own_answer(self):
        dialog = UiDialog(self.lab)
        self.service._active_dialogs[9] = dialog
        self.service._auto_respond_alarm_handles[9] = object()
        entry = self.row()["dialogs"]["open"][0]
        self.assertEqual(entry["responses"], [
            {"response": "custom_1", "text_key": str(0x7002)},
            {"response": "custom_2", "text_key": str(0x7003)}])
        self.assertTrue(entry["auto_respond"])
        self.assertIsNone(entry["title_key"])

    def test_the_newest_four_and_a_flag(self):
        for index in range(6):
            self.service._active_dialogs[index + 1] = UiDialogOkCancel(self.lab, 1, 2)
        dialogs = self.row()["dialogs"]
        self.assertEqual([item["dialog_id"] for item in dialogs["open"]], ["3", "4", "5", "6"])
        self.assertTrue(dialogs["truncated"])

    def test_an_odd_response_id_never_costs_the_row(self):
        dialog = UiDialog(self.lab)
        dialog.ui_responses = (UiDialogResponse(10 ** 20, 0x7002),)
        self.service._active_dialogs[9] = dialog
        responses = self.row()["dialogs"]["open"][0]["responses"]
        self.assertEqual([item["response"] for item in responses], ["custom_2"])

    def test_no_dialog_service_is_none(self):
        del sys.modules["services"].ui_dialog_service
        self.assertIsNone(self.row()["dialogs"])


if __name__ == "__main__":
    unittest.main()
