"""2.31.0 (DOMUS_DEEP_DESIGN §4, §6): every window her act or her game opens is hers or the User's.

Fakes: a Distributor whose sends are recorded, and dialogs built the way the game builds them (a
resolver, an owner, a dialog id). Her act is an object whose frame is on the stack while it runs."""
import sys
import types
import unittest

import test_2180_answer as answers
import test_e2

HER = "118245043779534861"
OTHER = "4242"
PET = "5555"
OPENER = 900
ACT_ID = "a" * 32
CHAIR = test_e2.CHAIR
RING = 7001
SCREEN = 7002
MAP_MSG = 7003
SWAPPED = ("UiDialogBase", "UiDialogObjectColorPicker", "SimPersonalityAssignmentDialog",
           "UiMapViewPicker", "UiApartmentPicker", "Distributor", "Consts_pb2", "GameSpeedChangeSource")


class FakeDistributor(object):
    def __init__(self):
        self.sent = []

    def add_event(self, msg_id, msg, immediate=False):
        self.sent.append(("event", msg_id, msg))

    def add_op(self, obj, op):
        self.sent.append(("op", obj, op))

    def add_op_with_no_owner(self, op):
        self.sent.append(("op", None, op))


class Base(object):
    """Stands for ui/ui_dialog.UiDialogBase: the send the hold takes over."""
    def __init__(self, dialog_id, interaction=None, owner=None):
        self.dialog_id = dialog_id
        self._resolver = types.SimpleNamespace(_interaction=interaction, super_interaction=None)
        self._owner = lambda: None if owner is None else types.SimpleNamespace(id=int(owner))
        self.sent = []

    def distribute_dialog(self, dialog_type, dialog_msg, immediate=False):
        self.sent.append((dialog_type, dialog_msg, immediate))


class Overrider(Base):
    """A class that overrides distribute_dialog and takes no immediate argument (colour, personality)."""
    def distribute_dialog(self, dialog_type, dialog_msg):
        self.sent.append((dialog_type, dialog_msg))


class UiDialogObjectColorPicker(Overrider):
    pass


class SimPersonalityAssignmentDialog(Overrider):
    pass


class UiMapViewPicker(Base):
    def distribute_dialog(self, _, dialog_msg):
        self.sent.append(dialog_msg)


class UiApartmentPicker(Base):
    def distribute_dialog(self, _, dialog_msg):
        self.sent.append(dialog_msg)


class UiDialogNotification(Base):
    """Overrides distribute_dialog and is never touched by the hold."""
    def distribute_dialog(self, dialog_type, dialog_msg):
        self.sent.append(("notification", dialog_msg))


class HerAct(object):
    """Her pushed interaction: its frame is on the call stack while run() works."""
    def __init__(self, interaction_id=OPENER):
        self.id = interaction_id

    def run(self, action):
        return action()


def command_frame(action):
    """Runs action inside a function named invoke_command, in sims4/commands (the game's console and panels)."""
    namespace = {}
    exec(compile("def invoke_command(action):\n    return action()\n", "sims4/commands.py", "exec"), namespace)
    return namespace["invoke_command"](action)


def ring(dialog_id):
    return types.SimpleNamespace(dialog=types.SimpleNamespace(dialog_id=dialog_id))


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.answer = answers.AnswerTests()
        self.answer.setUp()
        self.case = self.answer.case
        self.base = self.case.base
        self.probe = self.case.probe
        self.control = self.probe._E2
        self.module = sys.modules[type(self.control).__module__]
        self.service = self.answer.service
        self.service._active_dialogs.clear()
        self.cancelled = []

        def dialog_cancel(dialog_id):
            self.cancelled.append(dialog_id)
            self.service._active_dialogs.pop(dialog_id, None)

        self.service.dialog_cancel = dialog_cancel
        self.saved_monotonic = self.module.time.monotonic
        self.now = [100.0]
        self.module.time.monotonic = lambda: self.now[0]
        self.saved = dict((name, getattr(self.module, name)) for name in SWAPPED)
        self.module.UiDialogBase = Base
        self.module.UiDialogObjectColorPicker = UiDialogObjectColorPicker
        self.module.SimPersonalityAssignmentDialog = SimPersonalityAssignmentDialog
        self.module.UiMapViewPicker = UiMapViewPicker
        self.module.UiApartmentPicker = UiApartmentPicker
        self.module.Distributor = self.distributor_class = FakeDistributor
        self.module.Consts_pb2 = types.SimpleNamespace(
            MSG_UI_PHONE_RING=RING, MSG_SITUATION_PREPARE=SCREEN, MSG_SHOW_MAP_VIEW=MAP_MSG)
        self.module.GameSpeedChangeSource = types.SimpleNamespace(UI_MODAL="UI_MODAL", GAMEPLAY="GAMEPLAY")
        self.module._restore_holds()
        self.case.ready()  # arms, installs the holds with the fakes above, and starts sampling
        self.dist = FakeDistributor()

    def tearDown(self):
        self.module._restore_holds()
        self.module.time.monotonic = self.saved_monotonic
        for name, value in self.saved.items():
            setattr(self.module, name, value)
        self.case.tearDown()

    # helpers
    def push(self, interaction_id=OPENER, act_id=ACT_ID, name="plan"):
        self.control.pushed[str(interaction_id)] = {
            "act_id": act_id, "base": {"object_id": CHAIR, "guid64": "4242"}, "tuning_name": name,
            "interaction_id": str(interaction_id), "seen": True, "misses": 0}

    def her_interaction(self, interaction_id, source="InteractionSource.AUTONOMY", sim=HER):
        return types.SimpleNamespace(id=interaction_id, sim=types.SimpleNamespace(id=sim),
                                     context=types.SimpleNamespace(source=source))

    def window(self, dialog_id=601, interaction=None, owner=HER, cls=Base):
        dialog = cls(dialog_id, interaction=interaction, owner=owner)
        self.service._active_dialogs[dialog_id] = dialog
        return dialog

    def speed(self):
        return [(row["phase"], row["code"], row["detail"]) for row in self.base.e2("speed_event")]

    def last_speed(self):
        return self.speed()[-1]

    def act_rows(self):
        return self.case.events()

    # screens (R4, R5)
    def test_her_act_screen_by_message_is_withheld_and_recorded(self):
        self.push()
        HerAct().run(lambda: self.dist.add_event(SCREEN, "m"))
        self.assertEqual(self.dist.sent, [])
        self.assertEqual(self.act_rows()[-1]["code"], "SCREEN_WITHHELD:MSG_SITUATION_PREPARE")
        self.assertEqual(self.act_rows()[-1]["phase"], "UNKNOWN")
        self.assertEqual(self.last_speed(), ("SCREEN_WITHHELD", "MSG_SITUATION_PREPARE", "screen act %s" % ACT_ID))

    def test_the_users_screen_passes_untouched(self):
        self.push()
        self.dist.add_event(SCREEN, "m")
        self.assertEqual(self.dist.sent, [("event", SCREEN, "m")])
        self.assertEqual(self.speed(), [])

    def test_a_screen_behind_a_command_inside_her_act_is_withheld(self):
        self.push()
        HerAct().run(lambda: command_frame(lambda: self.dist.add_event(SCREEN, "m")))
        self.assertEqual(self.dist.sent, [])
        self.assertEqual(self.last_speed()[0], "SCREEN_WITHHELD")

    def test_a_command_the_user_ran_is_not_hers(self):
        self.push()
        command_frame(lambda: self.dist.add_event(SCREEN, "m"))
        self.assertEqual(len(self.dist.sent), 1)
        window = self.window(owner=HER)
        command_frame(lambda: window.distribute_dialog("T", "m"))
        self.assertEqual(window.sent, [("T", "m", False)])

    def test_bills_ops_are_withheld_for_her_act_and_pass_for_the_user(self):
        op = type("ShowBillsPanel", (), {})()
        self.push()
        HerAct().run(lambda: self.dist.add_op(None, op))
        self.assertEqual(self.dist.sent, [])
        self.assertEqual(self.last_speed(), ("SCREEN_WITHHELD", "ShowBillsPanel", "screen act %s" % ACT_ID))
        self.dist.add_op(None, op)
        self.dist.add_op_with_no_owner(op)
        self.assertEqual(self.dist.sent, [("op", None, op), ("op", None, op)])

    def test_a_screen_is_not_withheld_while_not_sampling(self):
        self.push()
        self.control._state = lambda: "ARMED"
        HerAct().run(lambda: self.dist.add_event(SCREEN, "m"))
        self.assertEqual(self.dist.sent, [("event", SCREEN, "m")])

    # calls (R2)
    def test_her_phone_ring_is_held_and_the_fallback_rings_it(self):
        self.push()
        self.window(interaction=types.SimpleNamespace(id=OPENER))
        msg = ring(601)
        self.dist.add_event(RING, msg)
        self.assertEqual(self.dist.sent, [])
        self.assertEqual(self.control.held["601"]["kind"], "ring")
        self.assertEqual(self.last_speed(), ("DIALOG_HELD", None, "ring 601 act %s" % ACT_ID))
        self.control._release_held(everything=True, code="STOP")
        self.assertEqual(self.dist.sent, [("event", RING, msg)])

    def test_a_call_addressed_to_her_is_hers_by_its_owner(self):
        self.window(interaction=None, owner=HER)
        self.dist.add_event(RING, ring(601))
        self.assertEqual(self.dist.sent, [])
        self.assertEqual(self.control.held["601"]["act_id"], None)

    def test_a_call_to_another_household_sim_passes(self):
        self.window(interaction=None, owner=OTHER)
        self.dist.add_event(RING, ring(601))
        self.assertEqual(len(self.dist.sent), 1)
        self.assertEqual(self.control.held, {})

    def test_a_silenced_phone_sends_her_window_through_distribute_dialog(self):
        # dialog_show with the phone silenced never rings: it calls distribute_dialog with immediate=.
        self.push()
        window = self.window(interaction=types.SimpleNamespace(id=OPENER))
        window.distribute_dialog("T", "m", immediate=False)
        self.assertEqual(window.sent, [])
        self.assertEqual(self.control.held["601"]["kind"], "dialog")

    # attribution (§4.1)
    def test_the_pie_menu_act_on_her_is_the_users(self):
        self.push()
        window = self.window(interaction=self.her_interaction(777, source="InteractionSource.PIE_MENU"))
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [("T", "m", False)])
        self.assertEqual(self.control.held, {})

    def test_a_body_reflex_dialog_is_hers(self):
        window = self.window(interaction=self.her_interaction(778))
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [])
        self.assertIsNone(self.control.held["601"]["act_id"])

    def test_an_autonomy_act_on_another_sim_is_the_users(self):
        window = self.window(interaction=self.her_interaction(779, sim=OTHER))
        window.distribute_dialog("T", "m")
        self.assertEqual(len(window.sent), 1)

    def test_another_households_window_is_never_held(self):
        window = self.window(owner=OTHER, interaction=None)
        window.distribute_dialog("T", "m")
        self.assertEqual(len(window.sent), 1)
        self.assertEqual(self.control.held, {})

    # shapes (§3.2, §4.2)
    def test_a_colour_picker_of_hers_is_shown_at_once(self):
        self.push()
        window = self.window(interaction=types.SimpleNamespace(id=OPENER), cls=UiDialogObjectColorPicker)
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [("T", "m")])
        self.assertEqual(self.last_speed(), ("DIALOG_SHOWN", "NOT_ANSWERABLE:UiDialogObjectColorPicker",
                                             "dialog 601 act %s" % ACT_ID))

    def test_a_composite_picker_of_hers_is_shown_at_once(self):
        self.push()
        cls = type("UiMultiPicker", (Base,), {})
        window = self.window(interaction=types.SimpleNamespace(id=OPENER), cls=cls)
        window.distribute_dialog("T", "m")
        self.assertEqual(len(window.sent), 1)
        self.assertEqual(self.last_speed()[1], "NOT_ANSWERABLE:UiMultiPicker")

    def test_map_and_apartment_pickers_are_cancelled_not_sent(self):
        self.push()
        window = self.window(interaction=types.SimpleNamespace(id=OPENER), cls=UiApartmentPicker)
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [])
        self.assertEqual(self.cancelled, [601])
        self.assertEqual(self.act_rows()[-1]["code"], "SCREEN_WITHHELD:UiApartmentPicker")

    def test_a_notification_is_never_held_or_wrapped(self):
        self.push()
        self.assertEqual(UiDialogNotification.distribute_dialog.__qualname__, "UiDialogNotification.distribute_dialog")
        window = self.window(interaction=types.SimpleNamespace(id=OPENER), cls=UiDialogNotification)
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [("notification", "m")])
        self.assertEqual(self.control.held, {})

    # identity (Q3)
    def test_her_sims_personality_dialog_is_the_users(self):
        self.push()
        window = self.window(interaction=types.SimpleNamespace(id=OPENER), cls=SimPersonalityAssignmentDialog)
        window._assignment_sim_info = types.SimpleNamespace(id=HER)
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [("T", "m")])
        self.assertEqual(self.last_speed()[:2], ("DIALOG_SHOWN", "IDENTITY_USER"))
        ok, connection = self.answer.answer("ok", dialog_id="601")
        self.assertFalse(ok)
        self.assertIn("ACT_REJECT IDENTITY_USER", connection.lines)

    def test_renaming_her_sim_is_the_users_even_in_her_act(self):
        self.push()
        change = type("ChangeSimNameInteraction", (object,), {})()
        change.id = OPENER
        change.target = types.SimpleNamespace(id=HER)
        window = self.window(interaction=change)
        window.distribute_dialog("T", "m")
        self.assertEqual(len(window.sent), 1)
        self.assertEqual(self.last_speed()[:2], ("DIALOG_SHOWN", "IDENTITY_USER"))

    def test_naming_a_pet_is_not_identity(self):
        self.push()
        change = type("ChangeSimNameInteraction", (object,), {})()
        change.id = OPENER
        change.target = types.SimpleNamespace(id=PET)
        window = self.window(interaction=change)
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [])
        self.assertEqual(self.control.held["601"]["act_id"], ACT_ID)

    def test_a_trait_picker_with_an_unreadable_target_uses_her_actor(self):
        self.push()
        def unreadable(_self):
            raise RuntimeError("no target")

        trait_class = type("TraitPickerSuperInteraction", (object,), {"target": property(unreadable)})
        trait = trait_class()
        trait.id = OPENER
        trait.sim = types.SimpleNamespace(id=HER)
        window = self.window(interaction=trait)
        window.distribute_dialog("T", "m")
        self.assertEqual(self.last_speed()[:2], ("DIALOG_SHOWN", "IDENTITY_USER"))

    # holds and the fallback (§4.2, §4.6)
    def test_two_windows_are_answered_by_id_and_the_other_stays_held(self):
        self.push()
        first = self.window(dialog_id=601, interaction=types.SimpleNamespace(id=OPENER))
        second = self.window(dialog_id=602, interaction=types.SimpleNamespace(id=OPENER))
        first.distribute_dialog("T", "one")
        second.distribute_dialog("T", "two")
        self.assertEqual(sorted(self.control.held), ["601", "602"])
        ok, connection = self.answer.answer("ok", dialog_id="601")
        self.assertTrue(ok, connection.lines)
        self.assertEqual(sorted(self.control.held), ["602"])
        self.control._release_held(everything=True, code="STOP")
        self.assertEqual(first.sent, [])
        self.assertEqual(second.sent, [("T", "two", False)])

    def test_a_late_answer_to_a_window_shown_to_the_user_is_refused(self):
        self.push()
        window = self.window(interaction=types.SimpleNamespace(id=OPENER))
        window.distribute_dialog("T", "m")
        self.now[0] += self.module.PICKER_HOLD_S
        self.control._release_held()
        self.assertEqual(len(window.sent), 1)
        ok, connection = self.answer.answer("ok", dialog_id="601")
        self.assertFalse(ok)
        self.assertIn("ACT_REJECT SHOWN_TO_USER", connection.lines)

    def test_the_watchdog_releases_a_held_window_without_a_probe_tick(self):
        self.push()
        window = self.window(interaction=types.SimpleNamespace(id=OPENER))
        window.distribute_dialog("T", "m")
        alarm = [item for item in self.base.calls["alarms"]
                 if item[2].get("callback") == self.control._watchdog_tick][-1]
        self.now[0] += self.module.PICKER_HOLD_S + 1
        alarm[2]["callback"](alarm[0])
        self.assertEqual(len(window.sent), 1)
        self.assertEqual(self.control.held, {})
        self.assertIn(alarm[0], self.base.calls["cancelled"])

    def test_a_hook_pass_with_a_due_window_sends_nothing_and_the_tick_shows_it(self):
        """2.31.0 review fix: a wrapper pass runs inside the distributor's own work, so it only drops
        windows whose dialog is gone. The due window goes out from the tick or the watchdog."""
        self.push()
        window = self.window(interaction=types.SimpleNamespace(id=OPENER))
        window.distribute_dialog("T", "m")
        self.now[0] += self.module.PICKER_HOLD_S + 1
        self.dist.add_event(999, "unwatched")
        self.assertEqual(window.sent, [])
        self.assertEqual(sorted(self.control.held), ["601"])
        self.assertIn(("DIALOG_HELD", None, "dialog 601 act %s" % ACT_ID), self.speed())
        self.control._watchdog_tick()
        self.assertEqual(len(window.sent), 1)
        self.assertEqual(self.control.held, {})
        self.assertEqual(self.last_speed(), ("DIALOG_SHOWN", "TIMEOUT", "dialog 601 act %s" % ACT_ID))

    def test_a_raising_controller_runs_the_original(self):
        self.push()
        self.control.hold_dialog = lambda *args: 1 / 0
        self.control.hold_event = lambda *args: 1 / 0
        window = self.window(interaction=types.SimpleNamespace(id=OPENER))
        window.distribute_dialog("T", "m")
        self.assertEqual(len(window.sent), 1)
        self.dist.add_event(SCREEN, "m")
        self.assertEqual(self.dist.sent, [("event", SCREEN, "m")])
        del self.control.hold_dialog
        del self.control.hold_event

    def test_disarm_puts_the_game_back_and_cancels_the_watchdog(self):
        self.push()
        window = self.window(interaction=types.SimpleNamespace(id=OPENER))
        window.distribute_dialog("T", "m")
        self.control.on_disarm()
        self.assertIsNone(self.module._HOLD["saved"])
        self.assertEqual(Base.distribute_dialog.__qualname__, "Base.distribute_dialog")
        self.assertIsNone(self.control._watchdog)
        self.assertEqual(self.control.held, {})
        self.assertEqual(len(window.sent), 1)

    def test_the_catalogue_skips_names_the_build_does_not_have(self):
        self.module.Consts_pb2 = types.SimpleNamespace(MSG_SITUATION_PREPARE=SCREEN)
        found = self.module._message_ids()
        self.assertEqual(found, {"MSG_SITUATION_PREPARE": SCREEN})

    # catch-all (§4.5, P28)
    def test_a_new_ui_modal_pause_during_her_act_is_an_unknown_screen(self):
        self.push()
        requests = []
        clock = types.SimpleNamespace(speed_controllers={"UI_MODAL": requests})
        self.base.services.game_clock_service = lambda: clock
        self.control._check_modal()
        self.assertEqual(self.speed(), [])
        requests.append(types.SimpleNamespace(speed="PAUSED"))
        self.control._check_modal()
        self.assertEqual(self.last_speed(), ("UNKNOWN_SCREEN", "plan", "act %s" % ACT_ID))
        count = len(self.speed())
        self.control._check_modal()
        self.assertEqual(len(self.speed()), count)

    def test_a_pause_with_an_open_dialog_is_not_unknown(self):
        self.push()
        requests = []
        clock = types.SimpleNamespace(speed_controllers={"UI_MODAL": requests})
        self.base.services.game_clock_service = lambda: clock
        self.control._check_modal()
        self.window(interaction=None, owner=OTHER)
        requests.append(types.SimpleNamespace(speed="PAUSED"))
        self.control._check_modal()
        self.assertEqual(self.speed(), [])


if __name__ == "__main__":
    unittest.main()
