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
GROUP = 5150
ACT_ID = "a" * 32
# 2.37.0 (W10 P1): the game's interaction sources that make a window on her Sim hers (every source but the two the User drives).
HER_SOURCES = ("AUTONOMY", "SCRIPT", "REACTION", "SOCIAL_ADJUSTMENT", "POSTURE_GRAPH", "GET_COMFORTABLE",
               "BODY_CANCEL_AOP", "CARRY_CANCEL_AOP", "VEHCILE_CANCEL_AOP", "UNIT_TEST")
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

    def her_interaction(self, interaction_id, source="InteractionSource.AUTONOMY", sim=HER, group=None):
        return types.SimpleNamespace(id=interaction_id, sim=types.SimpleNamespace(id=sim), group_id=group,
                                     context=types.SimpleNamespace(source=source))

    def push_with_group(self, group, interaction_id=777):
        """2.38.0 (W11 P1): her act (cmd_act) pushed; the game's interaction for it carries group_id `group`."""
        original = self.base.sim.push_super_affordance

        def push(affordance, target, context):
            result = original(affordance, target, context)
            result.execute_result.interaction.group_id = group
            return result

        self.base.sim.push_super_affordance = push
        ok, connection = self.case.act(act_id=ACT_ID)
        self.assertTrue(ok, connection.lines)
        return interaction_id

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
        self.assertEqual((self.act_rows()[-1]["phase"], self.act_rows()[-1]["code"]), ("NOTED", "SCREEN_WITHHELD"))
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

    # 2.37.0 (W10 P1): the first interaction's source decides a window on her Sim. The game's own script,
    # reflex and cancel acts are hers; a pie menu or a hand at the controls (SCRIPT_WITH_USER_INTENT) is the User's.
    def test_a_window_from_any_game_source_on_her_sim_is_hers_and_held(self):
        for number, source in enumerate(HER_SOURCES):
            dialog_id = 700 + number
            window = self.window(dialog_id=dialog_id, interaction=self.her_interaction(
                780 + number, source="InteractionSource." + source))
            window.distribute_dialog("T", "m")
            self.assertEqual(window.sent, [], source)
            self.assertIsNone(self.control.held[str(dialog_id)]["act_id"], source)

    def test_a_pie_menu_or_hand_on_the_controls_on_her_sim_is_the_users(self):
        for number, source in enumerate(("PIE_MENU", "SCRIPT_WITH_USER_INTENT")):
            window = self.window(dialog_id=720 + number, interaction=self.her_interaction(
                790 + number, source="InteractionSource." + source))
            window.distribute_dialog("T", "m")
            self.assertEqual(window.sent, [("T", "m", False)], source)
        self.assertEqual(self.control.held, {})

    def test_a_script_act_on_another_sim_is_the_users(self):
        window = self.window(dialog_id=730, interaction=self.her_interaction(
            795, sim=OTHER, source="InteractionSource.SCRIPT"), owner=OTHER)
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [("T", "m", False)])
        self.assertEqual(self.control.held, {})

    def test_a_window_from_an_unknown_source_on_her_sim_is_the_users(self):
        window = self.window(dialog_id=731, interaction=self.her_interaction(
            796, source="InteractionSource.NOT_A_SOURCE"))
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [("T", "m", False)])
        self.assertEqual(self.control.held, {})

    # shapes (§3.2, §4.2)
    def test_a_colour_picker_of_hers_is_shown_at_once(self):
        self.push()
        window = self.window(interaction=types.SimpleNamespace(id=OPENER), cls=UiDialogObjectColorPicker)
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [("T", "m")])
        self.assertEqual(self.last_speed(), ("DIALOG_SHOWN", "NOT_ANSWERABLE:UiDialogObjectColorPicker",
                                             "dialog 601 act %s" % ACT_ID))
        # 2.39.0 (W12 A4): shown at once is the User's, so its cause says so.
        self.assertEqual(self.module.observers._WINDOWS["601"]["cause"], "user")

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
        self.assertEqual((self.act_rows()[-1]["phase"], self.act_rows()[-1]["code"]), ("NOTED", "SCREEN_WITHHELD"))

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

    # 2.31.0 (W4 review fixes): held windows only, the cause before the live check, zone change, vanished windows
    def test_a_window_shown_at_once_is_recorded_and_its_late_answer_is_refused_as_shown(self):
        self.push()
        window = self.window(interaction=types.SimpleNamespace(id=OPENER), cls=UiDialogObjectColorPicker)
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [("T", "m")])
        self.assertIn("601", self.control.shown_to_user)
        ok, connection = self.answer.answer("ok", dialog_id="601")
        self.assertFalse(ok)
        self.assertIn("ACT_REJECT SHOWN_TO_USER", connection.lines)

    def test_a_window_that_was_never_held_is_refused_not_held(self):
        self.push()
        self.window(dialog_id=603, interaction=types.SimpleNamespace(id=OPENER))
        ok, connection = self.answer.answer("ok", dialog_id="603")
        self.assertFalse(ok)
        self.assertIn("ACT_REJECT NOT_HELD", connection.lines)

    def test_the_cause_of_a_window_is_noted_before_the_live_check(self):
        self.push()
        window = self.window(interaction=types.SimpleNamespace(id=OPENER))
        self.control._live = lambda: False
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [("T", "m", False)])
        self.assertEqual(self.control.held, {})
        self.assertEqual(self.module.observers._WINDOWS["601"]["cause"], "user")  # 2.39.0 (A4): passed through

    def test_a_zone_change_drops_held_windows_unsent(self):
        self.push()
        window = self.window(interaction=types.SimpleNamespace(id=OPENER))
        window.distribute_dialog("T", "m")
        self.control.on_stop("ZONE_CHANGE")
        self.assertEqual(window.sent, [])
        self.assertEqual(self.control.held, {})
        self.assertEqual(self.last_speed(), ("DIALOG_DROPPED", "ZONE_CHANGE", "dialog 601 act %s" % ACT_ID))

    def test_a_stop_still_sends_held_windows_to_the_user(self):
        self.push()
        window = self.window(interaction=types.SimpleNamespace(id=OPENER))
        window.distribute_dialog("T", "m")
        self.control.on_stop("STOP")
        self.assertEqual(window.sent, [("T", "m", False)])
        self.assertEqual(self.last_speed(), ("DIALOG_SHOWN", "STOP", "dialog 601 act %s" % ACT_ID))
        # 2.39.0 (W12 A4): a window handed to the User reads cause user, never hers.
        self.assertEqual(self.module.observers._WINDOWS["601"]["cause"], "user")

    def test_a_users_window_passes_through_with_its_cause_and_a_pass_through_event(self):
        # 2.39.0 (W12 A10): a pass-through is recorded, so the window's end is never silent.
        window = self.window(dialog_id=601, interaction=None, owner=OTHER)
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [("T", "m", False)])
        self.assertEqual(self.module.observers._WINDOWS["601"]["cause"], "user")
        self.assertEqual(self.last_speed(), ("DIALOG_SHOWN", "PASS_THROUGH", "dialog 601"))

    def test_a_held_window_that_vanishes_is_dropped_with_an_event_and_never_sent(self):
        self.push()
        window = self.window(interaction=types.SimpleNamespace(id=OPENER))
        window.distribute_dialog("T", "m")
        del self.service._active_dialogs[601]
        self.control._drop_closed()
        self.assertEqual(window.sent, [])
        self.assertEqual(self.control.held, {})
        self.assertEqual(self.last_speed(), ("DIALOG_DROPPED", "VANISHED", "dialog 601 act %s" % ACT_ID))

    def test_a_release_skips_a_window_dropped_by_an_earlier_send(self):
        self.push()
        first = self.window(dialog_id=601, interaction=types.SimpleNamespace(id=OPENER))
        second = self.window(dialog_id=602, interaction=types.SimpleNamespace(id=OPENER))
        first.distribute_dialog("T", "one")
        second.distribute_dialog("T", "two")
        original, args, kwargs = self.control.held["601"]["send"]

        def send_and_drop(*call_args, **call_kwargs):
            self.control.held.pop("602", None)
            return original(*args, **kwargs)
        self.control.held["601"]["send"] = (send_and_drop, (), {})
        self.control._release_held(everything=True, code="STOP")
        self.assertEqual(len(first.sent), 1)
        self.assertEqual(second.sent, [])
        self.assertEqual(self.control.held, {})

    def test_the_shown_record_keeps_the_newest_64_windows(self):
        self.control.shown_to_user = []
        limit = self.module.SHOWN_TO_USER_LIMIT
        self.assertEqual(limit, 64)
        for index in range(limit + 2):
            self.control._remember_shown(str(900 + index))
        self.assertEqual(len(self.control.shown_to_user), limit)
        self.assertEqual(self.control.shown_to_user[0], "902")
        self.assertEqual(self.control.shown_to_user[-1], str(900 + limit + 1))
        self.window(dialog_id=901, interaction=types.SimpleNamespace(id=OPENER))
        ok, connection = self.answer.answer("ok", dialog_id="901")
        self.assertFalse(ok)
        self.assertIn("ACT_REJECT NOT_HELD", connection.lines)

    # 2.34.0 (F1): windows and screens that arrive while her act is being pushed, before it is recorded.
    def push_then(self, during, raises=False):
        """Her act (cmd_act) whose push runs `during` before the game's own push: the window or screen
        is created inside push_super_affordance, as the game does."""
        original = self.base.sim.push_super_affordance

        def push(affordance, target, context):
            during()
            if raises:
                raise RuntimeError("game")
            return original(affordance, target, context)

        self.base.sim.push_super_affordance = push
        return self.case.act(act_id=ACT_ID)

    def test_a_picker_opened_during_her_push_is_hers_and_held(self):
        window = {}

        def open_picker():
            window["dialog"] = self.window(dialog_id=603, interaction=self.her_interaction(
                OPENER, source="InteractionSource.SCRIPT_WITH_USER_INTENT"))
            window["dialog"].distribute_dialog("T", "m")

        ok, connection = self.push_then(open_picker)
        self.assertTrue(ok, connection.lines)
        self.assertEqual(window["dialog"].sent, [])
        self.assertEqual(self.control.held["603"]["act_id"], ACT_ID)
        self.assertEqual(self.last_speed(), ("DIALOG_HELD", None, "dialog 603 act %s" % ACT_ID))

    def test_a_window_owned_by_her_during_her_push_is_hers(self):
        window = {}

        def open_window():
            window["dialog"] = self.window(dialog_id=604, interaction=None, owner=HER)
            window["dialog"].distribute_dialog("T", "m")

        self.push_then(open_window)
        self.assertEqual(window["dialog"].sent, [])
        self.assertEqual(self.control.held["604"]["act_id"], ACT_ID)

    def test_a_window_about_another_sim_during_her_push_is_the_users(self):
        window = {}

        def open_window():
            window["dialog"] = self.window(dialog_id=605, interaction=self.her_interaction(
                OPENER, sim=OTHER, source="InteractionSource.SCRIPT_WITH_USER_INTENT"), owner=OTHER)
            window["dialog"].distribute_dialog("T", "m")

        self.push_then(open_window)
        self.assertEqual(window["dialog"].sent, [("T", "m", False)])
        self.assertEqual(self.control.held, {})

    def test_her_screen_during_her_push_is_withheld_and_her_act_says_so(self):
        self.push_then(lambda: self.dist.add_event(SCREEN, "m"))
        self.assertEqual(self.dist.sent, [])
        withheld = [row for row in self.act_rows() if str(row.get("code", "")).startswith("SCREEN_WITHHELD")]
        self.assertEqual([(row["phase"], row["code"]) for row in withheld], [("NOTED", "SCREEN_WITHHELD")])
        self.assertEqual(withheld[0]["act_id"], ACT_ID)
        self.assertEqual(self.last_speed(), ("SCREEN_WITHHELD", "MSG_SITUATION_PREPARE", "screen act %s" % ACT_ID))

    def test_an_identity_window_during_her_push_stays_the_users(self):
        window = {}

        def rename():
            window["dialog"] = self.window(dialog_id=606, interaction=None, cls=SimPersonalityAssignmentDialog)
            window["dialog"]._assignment_sim_info = types.SimpleNamespace(id=HER)
            window["dialog"].distribute_dialog("T", "m")

        self.push_then(rename)
        self.assertEqual(window["dialog"].sent, [("T", "m")])
        self.assertEqual(self.last_speed()[:2], ("DIALOG_SHOWN", "IDENTITY_USER"))
        self.assertEqual(self.control.held, {})

    def test_the_mark_is_cleared_after_the_push_so_a_later_unlinked_window_is_the_users(self):
        ok, connection = self.push_then(lambda: None)
        self.assertTrue(ok, connection.lines)
        self.assertIsNone(self.control.pushing)
        self.now[0] += 121  # 2.38.0 (W11 P1): past the 120 s source window of her last push
        window = self.window(dialog_id=607, interaction=self.her_interaction(
            999, source="InteractionSource.SCRIPT_WITH_USER_INTENT"))
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [("T", "m", False)])
        self.assertEqual(self.control.held, {})

    def test_the_mark_is_cleared_when_the_push_raises(self):
        ok, connection = self.push_then(lambda: None, raises=True)
        self.assertFalse(ok)
        self.assertIsNone(self.control.pushing)
        window = self.window(dialog_id=608, interaction=self.her_interaction(
            998, source="InteractionSource.SCRIPT_WITH_USER_INTENT"))
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [("T", "m", False)])


    # 2.38.0 (W11 P1): her errand's windows. A window whose resolver interaction continues her pushed act (the same
    # group_id, kept 10 minutes) is hers with that act; a SCRIPT_WITH_USER_INTENT window on her Sim is hers for 120 s
    # after her last push; a pie menu on her Sim stays the User's.
    def test_a_window_continuing_her_pushed_act_by_group_is_hers_with_that_act(self):
        self.push_with_group(GROUP)
        self.now[0] += 1
        window = self.window(dialog_id=610, interaction=self.her_interaction(
            991, source="InteractionSource.SCRIPT_WITH_USER_INTENT", group=GROUP))
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [])
        self.assertEqual(self.control.held["610"]["act_id"], ACT_ID)
        self.assertEqual(self.last_speed(), ("DIALOG_HELD", None, "dialog 610 act %s" % ACT_ID))

    def test_a_group_match_is_kept_ten_minutes_after_the_push_and_no_longer(self):
        self.push_with_group(GROUP)
        self.now[0] += 599
        window = self.window(dialog_id=611, interaction=self.her_interaction(
            992, source="InteractionSource.SCRIPT_WITH_USER_INTENT", group=GROUP))
        window.distribute_dialog("T", "m")
        self.assertEqual(self.control.held["611"]["act_id"], ACT_ID)
        self.now[0] += 2  # 601 s after the push: the group has expired, and the source window closed long ago
        late = self.window(dialog_id=612, interaction=self.her_interaction(
            993, source="InteractionSource.SCRIPT_WITH_USER_INTENT", group=GROUP))
        late.distribute_dialog("T", "m")
        self.assertEqual(late.sent, [("T", "m", False)])
        self.assertNotIn("612", self.control.held)

    def test_a_group_is_not_matched_by_another_group_or_by_no_group(self):
        self.push_with_group(GROUP)
        other = self.window(dialog_id=613, interaction=self.her_interaction(
            994, source="InteractionSource.PIE_MENU", group=GROUP + 1))
        other.distribute_dialog("T", "m")
        self.assertEqual(other.sent, [("T", "m", False)])
        none = self.window(dialog_id=614, interaction=self.her_interaction(
            995, source="InteractionSource.PIE_MENU", group=None))
        none.distribute_dialog("T", "m")
        self.assertEqual(none.sent, [("T", "m", False)])
        self.assertEqual(self.control.held, {})

    def test_a_script_with_user_intent_window_on_her_sim_is_hers_for_120_seconds_after_her_push(self):
        self.push_with_group(GROUP)
        self.now[0] += 119
        window = self.window(dialog_id=615, interaction=self.her_interaction(
            996, source="InteractionSource.SCRIPT_WITH_USER_INTENT"))
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [])
        self.assertIsNone(self.control.held["615"]["act_id"])

    def test_a_script_with_user_intent_window_after_120_seconds_is_the_users(self):
        self.push_with_group(GROUP)
        self.now[0] += 121
        window = self.window(dialog_id=616, interaction=self.her_interaction(
            997, source="InteractionSource.SCRIPT_WITH_USER_INTENT"))
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [("T", "m", False)])
        self.assertEqual(self.control.held, {})

    def test_a_pie_menu_window_on_her_sim_during_her_errand_stays_the_users(self):
        self.push_with_group(GROUP)
        window = self.window(dialog_id=617, interaction=self.her_interaction(
            998, source="InteractionSource.PIE_MENU"))
        window.distribute_dialog("T", "m")
        self.assertEqual(window.sent, [("T", "m", False)])
        self.assertEqual(self.control.held, {})

    def test_a_group_the_probe_cannot_read_never_raises_and_is_not_hers_by_group(self):
        self.push_with_group(GROUP)

        class Unreadable(object):
            @property
            def group_id(self):
                raise RuntimeError("game")

        self.assertIsNone(self.control._group_pushed_for(Unreadable()))
        self.assertIsNone(self.control._group_pushed_for(None))

    def test_watch_act_keeps_the_group_of_the_act_and_of_each_alias(self):
        act = types.SimpleNamespace(id=OPENER, group_id=GROUP)
        alias = types.SimpleNamespace(id=888, group_id=GROUP + 2)
        base = {"object_id": CHAIR, "guid64": "4242"}
        self.control._watch_act(ACT_ID, base, str(OPENER), "plan", act, {"888": alias})
        window = self.window(dialog_id=618, interaction=self.her_interaction(
            999, source="InteractionSource.PIE_MENU", group=GROUP + 2))
        self.assertEqual(self.control._decide_window(window), ("hers", self.control.pushed["888"]))


if __name__ == "__main__":
    unittest.main()
