"""E2 session control: commands, lineage, experiments, pause (plan E2 §6–§8).

Game thread only. All world actions go through e2_actuator; all reads through
observers/e2_actuator read helpers; all file I/O through the writer queue.
The host supplies emit/state callables so this module never imports probe.
"""

import sys
import time

from . import act_menu
from . import e2_admission
from . import e2_cards
from . import e2_lineage
from . import e2_registry
from . import e2_trial
from . import reach
from . import schema
from . import snapshot

try:
    from . import e2_actuator  # TARGET_BYTECODE 1.128 bindings; RUNTIME first-load gate.
except ImportError:
    e2_actuator = None
try:
    from . import observers
except ImportError:
    observers = None
try:
    import services  # PRIOR_ART|TARGET_BYTECODE: sim_info_manager read surface.
except ImportError:
    services = None
try:
    # TARGET_BYTECODE: Distributor.add_event(immediate=True) is append + process_events().
    from distributor.system import Distributor
except ImportError:
    Distributor = None
try:
    # TARGET_BYTECODE: camera.focus_on_sim(sim, follow, client) / focus_on_object(object, follow)
    # send FocusCamera(id, follow_mode) to the client; they move only the view.
    from camera import focus_on_sim, focus_on_object
except ImportError:
    focus_on_sim = focus_on_object = None
try:
    # 2.26.0: the game's own notification, for one line of plain text on the User's screen.
    from ui.ui_dialog_notification import UiDialogNotification
    from sims4.localization import LocalizationHelperTuning
except ImportError:
    UiDialogNotification = LocalizationHelperTuning = None
try:
    # 2.31.0: the base of every dialog window: ui/ui_dialog.UiDialogBase.distribute_dialog sends it.
    from ui.ui_dialog import UiDialogBase
except ImportError:
    UiDialogBase = None
try:
    # 2.31.0: the game's own overriders of distribute_dialog (bytecode scan, DOMUS_DEEP_DESIGN §3.2):
    # a colour picker, her personality dialog, the map and apartment pickers. UiDialogNotification is
    # never held: 2.36.0 (D6, P2) observes its distribution only (_notice_hook), for the notices about her.
    from objects.color.object_color_dialog import UiDialogObjectColorPicker
except ImportError:
    UiDialogObjectColorPicker = None
try:
    from sims.sim_dialogs import SimPersonalityAssignmentDialog
except ImportError:
    SimPersonalityAssignmentDialog = None
try:
    from ui.ui_dialog_picker import UiMapViewPicker, UiApartmentPicker
except ImportError:
    UiMapViewPicker = UiApartmentPicker = None
try:
    # 2.31.0: the hold's real-time watchdog (alarms.add_alarm_real_time / cancel_alarm, as probe.py uses them)
    # and the probe's own real-time interval (clock.interval_in_real_seconds).
    import alarms
except ImportError:
    alarms = None
try:
    import clock as game_clock
except ImportError:
    game_clock = None
try:
    # 2.31.0 (W3p): the milliseconds per sim second, read once for the clock preflight (CLOCK_RESEARCH §1).
    import date_and_time
except ImportError:
    date_and_time = None
try:
    # 2.23.0: the close message ui/ui_dialog_service._dialog_cancel_internal builds.
    from protocolbuffers import Consts_pb2, Dialog_pb2
except ImportError:
    Consts_pb2 = Dialog_pb2 = None
try:
    # 2.23.0: ClockSpeedMode / GameSpeedChangeSource. The dialog pause is a UI_MODAL request.
    from clock import ClockSpeedMode, GameSpeedChangeSource
except ImportError:
    ClockSpeedMode = GameSpeedChangeSource = None
CAMERA_MIN_GAP_S = 1.5
# 2.26.0: social talk on the User's screen, at most one line each TALK_MIN_GAP_S.
TALK_MIN_GAP_S = 2.0
# 2.31.0 (W3p, DOMUS_DEEP_DESIGN §5a and §5): her pace. Her needs drain through the game's own decay-rate
# modifier on each motive (lever D). The game clock runs at a slower normal speed through one class
# attribute (lever A), only when the preflight finds the clock at the game's own defaults. 1.0 is normal
# pace and changes nothing.
PACE_LOWEST = 0.25
PACE_NORMAL = 1.0
CLOCK_DEFAULT_SPEED = 1
CLOCK_DEFAULT_MS_PER_SIM_SECOND = 25


def _factor(value):
    """2.31.0: a pace factor: a finite number from PACE_LOWEST to PACE_NORMAL (a bool is not one), else None."""
    if type(value) not in (int, float) or not PACE_LOWEST <= value <= PACE_NORMAL:
        return None
    return float(value)


def _measure(value):
    """2.31.0: a reading for the pace block: a number within the schema's bound, else None."""
    if type(value) not in (int, float) or not 0 <= value <= schema.PACE_MEASURE_LIMIT:
        return None
    return float(value)


def _capture_clock():
    """2.31.0: the game clock's normal multiplier, read once at install, and whether the clock is foreign:
    not the game's own defaults. A foreign clock is never touched. 2.31.0 (W4, F12): an unreadable clock is
    foreign too, and reported with its own reason. Returns (base, foreign, unreadable)."""
    try:
        base = game_clock.GameClock.NORMAL_SPEED_MULTIPLIER
        per_second = date_and_time.REAL_MILLISECONDS_PER_SIM_SECOND
        foreign = not (base == CLOCK_DEFAULT_SPEED and per_second == CLOCK_DEFAULT_MS_PER_SIM_SECOND)
    except Exception:
        return None, True, True
    return base, foreign, False
# 2.27.0: a window her own act opened is hers to answer, so it is held back from the User's screen.
# Unanswered after PICKER_HOLD_S, it is shown to the User (the fallback). 2.31.0: the same hold covers
# every window and call she is offered (DOMUS_DEEP_DESIGN §4.2).
PICKER_HOLD_S = 180.0
# 2.31.0: the watchdog wakes this often (real seconds) while a window is held (§4.6).
WATCHDOG_TICK_S = 1.0
# 2.31.0: frames of the call stack read to find her act (§4.1).
STACK_FRAME_LIMIT = 64
# 2.31.0: windows the fallback showed to the User; a late answer to one of them is refused.
SHOWN_TO_USER_LIMIT = 64
# 2.31.0: windows she cannot answer (§3.2): shown at once with DIALOG_SHOWN NOT_ANSWERABLE.
NOT_ANSWERABLE_CLASSES = frozenset(("UiMultiPicker", "UiDialogObjectColorPicker",
                                    "SimPersonalityAssignmentDialog"))
# 2.31.0: client-drawn pickers (§4.2): never sent; the dialog is cancelled instead.
WITHHELD_DIALOG_CLASSES = frozenset(("UiMapViewPicker", "UiApartmentPicker"))
# 2.31.0: interactions that rename or retrait her own Sim: always the User's (User ruling Q3).
# 2.32.0 (PR5, User ruling): the death window on her own Sim (keep, reincarnate, leave) is the User's.
IDENTITY_CLASSES = frozenset(("ChangeSimNameInteraction", "TraitTypePickerSuperInteraction",
                              "TraitPickerSuperInteraction", "MatchmakingTraitPickerSuperInteraction",
                              "DeathSuperInteraction"))
# 2.31.0: the message that rings her phone; dialog_show sends it instead of distribute_dialog (§3.1 R2).
RING_MESSAGE_NAME = "MSG_UI_PHONE_RING"
# 2.31.0: client screens she may not open by message (§4.5, R4), Consts_pb2 names, resolved at install.
SCREEN_MESSAGE_NAMES = (
    "MSG_SITUATION_PREPARE", "MSG_SHOW_FAMILY_TREE_UI", "MSG_SHOW_FAMILY_TREE_FORGERY",
    "MSG_SHOW_SIM_PROFILE", "MSG_MOVE_IN_MOVE_OUT", "MSG_SHOW_DYNASTY_CONFIGURATOR",
    "MSG_SHOW_SMALL_BUSINESS_CONFIGURATOR", "MSG_MANAGE_EMPLOYEES_DIALOG",
    "MSG_MANAGE_SMALL_BUSINESS_EMPLOYEES_DIALOG", "MSG_MANAGE_SMALL_BUSINESS_EMPLOYEE_TASKS_DIALOG",
    "MSG_RETAIL_MANAGE_EMPLOYEES", "OPEN_INVENTORY", "OPEN_INVENTORY_WITH_FILTERS", "SHOW_FAMILY_TREE",
    "SHOW_RENTAL_UNIT_MANAGEMENT", "SHOW_LIFETIME_MILESTONES_PANEL")
# 2.31.0: client screens sent as ops (§3.1 R5, distributor/ops), by class name.
SCREEN_OP_NAMES = frozenset(("ShowBillsPanel", "ShowSocialMediaPanel", "ShowMatchmakingDialog",
                             "ShowClubInfoUI", "ShowHorseCompetitionSelector",
                             "ShowSimCompetitionSelector"))
# 2.31.0 (§11): the answer shapes the probe accepts. Rows per answer. A restricted field takes only letters,
# digits and spaces, because its restricted set is a localized string the probe cannot read (a conservative rule).
ANSWER_ROWS_LIMIT = 16
RESTRICTED_SAFE_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 ")
# controller: the E2Control the hooks report to (None: pass through). saved: the game's originals
# while installed. events: watched message ids; screens: id -> name; ring: the phone ring's id.
_HOLD = {"controller": None, "saved": None, "events": frozenset(), "screens": {}, "ring": None,
         "ops": SCREEN_OP_NAMES}


class _HoldAlarmOwner(object):
    """2.31.0: the owner of the hold's watchdog alarm (alarms keep the owner weakly)."""


def _class_names(obj):
    """2.31.0: the class names along obj's MRO, read only (matched by name, no imports)."""
    try:
        return frozenset(klass.__name__ for klass in type(obj).__mro__)
    except Exception:
        return frozenset()


def _read(read):
    """2.31.0: one read that never raises; None when it cannot be read."""
    try:
        return read()
    except Exception:
        return None


def _note_window(key, **facts):
    """2.31.0 (§11): what the observers report about one window (cause, held, text fields). Never raises."""
    try:
        observers.note_window(key, **facts)
    except Exception:
        pass


def _read_text_fields(message):
    """2.31.0 (§4.4, §11): the text fields of a held message (observers.read_text_inputs), or None. Never raises."""
    try:
        return observers.read_text_inputs(message)
    except Exception:
        return None


def _window_detail(kind, key, act_id):
    """2.31.0: a speed event's detail: the kind, the dialog id when there is one, and "act <id>" only when
    her act opened the window (helper windows.py reads that word pair; never "act None")."""
    words = [kind] + ([key] if key else []) + (["act %s" % act_id] if act_id else [])
    return " ".join(words)[:schema.MAX_DETAIL_LENGTH]


def _held_message(kind, send_args, send_kwargs):
    """2.31.0 (§4.4): the dialog message a held window sends: the dialog_msg of a distribute_dialog send, or
    the dialog of a phone ring. None when it cannot be read."""
    message = (send_args[2] if len(send_args) > 2
               else send_kwargs.get("dialog_msg" if kind == "dialog" else "msg"))
    if kind == "ring":
        message = _read(lambda: message.dialog)
    return message


def _response_number(pick):
    """2.39.0 (W12 A2): the ButtonType number of a numbered answer, from "response_<N>"; None for any other pick."""
    prefix = "response_"
    if type(pick) is not str or not pick.startswith(prefix):
        return None
    digits = pick[len(prefix):]
    if not digits.isdigit() or len(digits) > 9:
        return None
    return int(digits)


def _window_open(service, dialog_id):
    """2.39.0 (W12 A5): whether a dialog with this id is still open on the dialog service. False when unreadable."""
    try:
        return any(int(key) == int(dialog_id) for key in service._active_dialogs)
    except Exception:
        return False


def _open_window(row, held):
    """2.39.0 (W12 A1): the newest window open now, by its dialog id: the sample's own pop-ups, else her held
    window; None when no window is open (or it cannot be told)."""
    dialogs = row.get("dialogs") if isinstance(row, dict) else None
    opened = dialogs.get("open") if isinstance(dialogs, dict) else None
    for entry in reversed(opened or []):
        if isinstance(entry, dict) and entry.get("dialog_id") is not None:
            return str(entry["dialog_id"])
    return str(next(iter(held))) if held else None


def _def_id_of(dialog, option):
    """2.31.0 (§4.3): the definition id of a purchase row (PurchasePickerRow.def_id), found by its option id."""
    for row in _read(lambda: list(dialog.picker_rows or ())) or []:
        if _read(lambda: str(int(row.option_id))) == option:
            return _read(lambda: int(row.def_id))
    return None


def _check_text(fields, text):
    """2.31.0 (§4.4): every field of the held message gets a value (the game's order), each within its limits.
    Returns (refusal, [(name, value)]). Her text never goes into a refusal, only a field name."""
    if sorted(text) != sorted(field["name"] for field in fields):
        return ("TEXT_INVALID", None), None
    pairs = []
    for field in fields:
        name, value = field["name"], text[field["name"]]
        if field["max_length"] is None or (field["numeric"] and (field["min_value"] is None or
                                                                 field["max_value"] is None)):
            return ("NO_LIMIT", name), None
        if not all(ch.isprintable() for ch in value) or not field["min_length"] <= len(value) <= field["max_length"]:
            return ("TEXT_INVALID", name), None
        if field["numeric"]:
            digits = value[1:] if value.startswith("-") else value
            if not digits or not set(digits) <= set("0123456789") or not (
                    field["min_value"] <= int(value) <= field["max_value"]):
                return ("TEXT_INVALID", name), None
        if field["restricted"] and not set(value) <= RESTRICTED_SAFE_CHARS:
            return ("TEXT_INVALID", name), None
        pairs.append((name, value))
    return None, pairs


def _same_id(obj, her):
    return her is not None and obj is not None and _read(lambda: str(obj.id)) == her


# 2.37.0 (W10 P1): the game's InteractionSource names. A window whose first interaction is one of the others, on her
# Sim, is hers; a pie menu or a hand at the controls (SCRIPT_WITH_USER_INTENT) keeps it the User's.
HER_INTERACTION_SOURCES = frozenset(("AUTONOMY", "BODY_CANCEL_AOP", "CARRY_CANCEL_AOP", "SCRIPT", "UNIT_TEST",
                                     "POSTURE_GRAPH", "SOCIAL_ADJUSTMENT", "REACTION", "GET_COMFORTABLE",
                                     "VEHCILE_CANCEL_AOP"))
# 2.38.0 (W11 P1): how long an interaction's group_id stays tied to her pushed act, and how long after her last push
# a SCRIPT_WITH_USER_INTENT window on her Sim is hers (the probe's own pushes carry that source).
GROUP_KEEP_S = 600.0
PUSH_SOURCE_S = 120.0


def _interaction_source_name(source):
    """2.37.0 (W10 P1): the enum member's name from str(source) ("InteractionSource.SCRIPT" gives "SCRIPT"), or None."""
    if not isinstance(source, str):
        return None
    return source.rsplit(".", 1)[-1]


def _target_or_actor_is(interaction, her):
    """2.31.0 (§4.1 identity): the interaction's target Sim, or its actor when the target cannot be read."""
    target = _read(lambda: interaction.target)
    if target is None:
        target = _read(lambda: interaction.sim)
    return _same_id(target, her)


def _is_commands_file(path):
    path = str(path).replace("\\", "/")
    return "sims4" in path and path.endswith("commands.py")


def _note_own_notice(notification):
    """2.36.0 (D6, P2): the probe's own line is remembered by its dialog id (observers.note_own_notice). Never raises."""
    if observers is not None:
        observers.note_own_notice(notification)


def _dialog_hook(original):
    """2.31.0: stands in for one distribute_dialog (UiDialogBase and each overrider of §3.2). The
    game's own sends the window; a window that is hers is held or withheld here. Any exception:
    the original runs with the same arguments."""
    def distribute_dialog(dialog, *args, **kwargs):
        controller = _HOLD["controller"]
        if controller is not None:
            try:
                if controller.hold_dialog(original, dialog, args, kwargs):
                    return None
            except Exception:
                pass
        return original(dialog, *args, **kwargs)
    return distribute_dialog


def _notice_hook(original):
    """2.36.0 (D6, P2): stands in for UiDialogNotification.distribute_dialog. A notification is never held,
    withheld or changed here: the observer reads it (observers.notice_shown), and the game's own original sends
    it with the same arguments, whatever the observer does. It never consults the hold controller."""
    def distribute_dialog(dialog, *args, **kwargs):
        try:
            observers.notice_shown(dialog)
        except Exception:
            pass
        return original(dialog, *args, **kwargs)
    return distribute_dialog


def _event_hook(original):
    """2.31.0: stands in for Distributor.add_event. The first check is a membership test on the
    message id, because add_event runs constantly; every other message passes straight through."""
    def add_event(distributor, *args, **kwargs):
        controller = _HOLD["controller"]
        if controller is None:
            return original(distributor, *args, **kwargs)
        msg_id = args[0] if args else kwargs.get("msg_id")
        try:
            watched = msg_id in _HOLD["events"]
        except Exception:
            watched = False
        if watched:
            try:
                if controller.hold_event(original, distributor, msg_id, args, kwargs):
                    return None
            except Exception:
                pass
        else:
            controller.pass_by()
        return original(distributor, *args, **kwargs)
    return add_event


def _op_hook(original):
    """2.31.0: stands in for Distributor.add_op and add_op_with_no_owner (the op is the last argument)."""
    def add_op(distributor, *args, **kwargs):
        controller = _HOLD["controller"]
        if controller is None:
            return original(distributor, *args, **kwargs)
        op = args[-1] if args else kwargs.get("op")
        name = type(op).__name__
        if name == "PhoneNotificationOp":
            # 2.40.0 (W13 P1): a text for her is observed (never held); the op itself passes through below.
            controller.note_phone(op)
        if name in _HOLD["ops"]:
            try:
                if controller.withhold_op(name):
                    return None
            except Exception:
                pass
        else:
            controller.pass_by()
        return original(distributor, *args, **kwargs)
    return add_op


def _message_ids():
    """2.31.0: Consts_pb2 ids by catalogue name; a name the build does not have is skipped."""
    found = {}
    if Consts_pb2 is None:
        return found
    for name in (RING_MESSAGE_NAME,) + SCREEN_MESSAGE_NAMES:
        value = Consts_pb2.__dict__.get(name)
        if value is not None:
            found[name] = value
    return found


def _install_holds(controller):
    """2.31.0, once per game process: the holds and withholds of §4.2 and §4.5, each with the game's
    original kept for _restore_holds. Returns False when nothing could be installed."""
    _HOLD["controller"] = controller
    if _HOLD["saved"]:
        return True
    found = _message_ids()
    _HOLD["ring"] = found.pop(RING_MESSAGE_NAME, None)
    _HOLD["screens"] = dict((value, name) for name, value in found.items())
    _HOLD["events"] = frozenset(found.values()) | (frozenset() if _HOLD["ring"] is None
                                                  else frozenset((_HOLD["ring"],)))
    saved = {}
    _HOLD["saved"] = saved
    try:
        if UiDialogBase is not None:
            saved["base"] = UiDialogBase.distribute_dialog
            UiDialogBase.distribute_dialog = _dialog_hook(saved["base"])
        if UiDialogObjectColorPicker is not None:
            saved["color"] = UiDialogObjectColorPicker.distribute_dialog
            UiDialogObjectColorPicker.distribute_dialog = _dialog_hook(saved["color"])
        if SimPersonalityAssignmentDialog is not None:
            saved["personality"] = SimPersonalityAssignmentDialog.distribute_dialog
            SimPersonalityAssignmentDialog.distribute_dialog = _dialog_hook(saved["personality"])
        if UiMapViewPicker is not None:
            saved["map"] = UiMapViewPicker.distribute_dialog
            UiMapViewPicker.distribute_dialog = _dialog_hook(saved["map"])
        if UiApartmentPicker is not None:
            saved["apartment"] = UiApartmentPicker.distribute_dialog
            UiApartmentPicker.distribute_dialog = _dialog_hook(saved["apartment"])
        if UiDialogNotification is not None:
            # 2.36.0 (D6, P2): observed, never held. Every notification passes here, with or without responses.
            saved["notification"] = UiDialogNotification.distribute_dialog
            UiDialogNotification.distribute_dialog = _notice_hook(saved["notification"])
        if Distributor is not None:
            saved["add_event"] = Distributor.add_event
            Distributor.add_event = _event_hook(saved["add_event"])
            saved["add_op"] = Distributor.add_op
            Distributor.add_op = _op_hook(saved["add_op"])
            saved["add_op_no_owner"] = Distributor.add_op_with_no_owner
            Distributor.add_op_with_no_owner = _op_hook(saved["add_op_no_owner"])
    except Exception:
        _restore_holds()
        return False
    return True


def _restore_holds():
    """2.31.0: the game's own originals back, and no controller: every hook passes through."""
    saved = _HOLD["saved"]
    _HOLD["controller"] = None
    if saved is None:
        return
    _HOLD["saved"] = None
    if "base" in saved:
        UiDialogBase.distribute_dialog = saved["base"]
    if "color" in saved:
        UiDialogObjectColorPicker.distribute_dialog = saved["color"]
    if "personality" in saved:
        SimPersonalityAssignmentDialog.distribute_dialog = saved["personality"]
    if "map" in saved:
        UiMapViewPicker.distribute_dialog = saved["map"]
    if "apartment" in saved:
        UiApartmentPicker.distribute_dialog = saved["apartment"]
    if "notification" in saved:
        UiDialogNotification.distribute_dialog = saved["notification"]
    if "add_event" in saved:
        Distributor.add_event = saved["add_event"]
    if "add_op" in saved:
        Distributor.add_op = saved["add_op"]
    if "add_op_no_owner" in saved:
        Distributor.add_op_with_no_owner = saved["add_op_no_owner"]


def _send_queued_events():
    """2.20.1 (live 2026-10-06: after her answer the recipe picker stayed on screen and the game
    stayed paused): dialog_respond queues the client's close (MSG_UI_DIALOG_CLOSE) for the next
    distributor pass; send it now, as the game's own add_event(immediate=True) does. Never
    changes the answer's outcome."""
    if Distributor is None:
        return False
    try:
        Distributor.instance().process_events()
        return True
    except Exception:
        return False


# E1 LAB sofa (target of the E1 Owner-sit witness): never an E2 experiment target.
EXCLUDED_OBJECT_IDS = frozenset(("118245043789434044",))
# 2.19.1: samples (about one a second) a pushed act may be missing from her queue before it
# is recorded as gone (UNKNOWN, LEFT_QUEUE).
LEFT_QUEUE_SAMPLES = 5
# 2.28.0: at most this many entries of her queue and her running list are compared around a push.
ALIAS_SCAN_LIMIT = 32


def _now():
    return time.perf_counter()


def _hunger_span(experiment):
    return _motive_span(experiment, "hunger")


def _motive_span(experiment, motive_id):
    """D7: start, peak and end. The end of a long window hides a meal (31->80->40)."""
    before = None
    after = None
    peak = None
    for row in experiment._rows_since:
        item = None
        for motive in row.get("motives") or []:
            if isinstance(motive, dict) and motive.get("id") == motive_id:
                item = motive
                break
        if item is None:
            continue
        value = item.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if before is None:
            before = value
        after = value
        if peak is None or value > peak:
            peak = value
    return _num(before), _num(peak), _num(after)


RISE_AT = 5


def _risen(experiment, skip):
    """D28 (live shower_TakeShower PASS, hygiene 82->100, detail silent): the needs
    that rose by RISE_AT or more during a trial, largest rise first."""
    spans = {}
    for row in experiment._rows_since:
        for motive in row.get("motives") or []:
            if not isinstance(motive, dict):
                continue
            motive_id = motive.get("id")
            value = motive.get("value")
            if (not isinstance(motive_id, str) or motive_id in skip or
                    isinstance(value, bool) or not isinstance(value, (int, float))):
                continue
            span = spans.get(motive_id)
            if span is None:
                spans[motive_id] = [value, value, value]
                continue
            span[2] = value
            if value > span[1]:
                span[1] = value
    risen = [(span[1] - span[0], motive_id, span) for motive_id, span in spans.items()
             if span[1] - span[0] >= RISE_AT]
    risen.sort(key=lambda item: (-item[0], item[1]))
    return [(motive_id, span) for _rise, motive_id, span in risen]


def _num(value):
    if value is None:
        return "?"
    return format(value, "g")


def _food_hold(experiment):
    """A31/D11: a running food or relief family is never cancelled. Hunger does not
    rise while she cooks, so "still rising" would cancel a cook halfway (R-PICK §5).
    D13: a sleep pushed for low energy is the cure; cutting it at 180 s defeats it."""
    rows = list(experiment._rows_since)
    if not rows:
        return False
    ids = set(experiment.children)
    ids.add(experiment.interaction_id)
    for entry in (rows[-1].get("interactions") or {}).get("observed") or []:
        if (entry.get("interaction_id") in ids and
                entry.get("membership") in e2_registry.RUNNING_MEMBERSHIPS):
            return True
    return False


def _queued_never_started(experiment):
    """The push itself is still only queued. A running child does not count."""
    for entry in (experiment._rows_since[-1].get("interactions") or {}).get("observed") or []:
        if (entry.get("interaction_id") == experiment.interaction_id and
                entry.get("membership") == "QUEUED"):
            return True
    return False


def _tuning_name(affordance):
    target = affordance if isinstance(affordance, type) else type(affordance)
    try:
        name = target.__name__
    except Exception:
        name = ""
    return str(name)[:128]


def _queued_interactions(sim):
    """2.28.0: her Sim's queued and running interactions by id, {id: interaction}: the two
    collections observers.poll_once reads. At most ALIAS_SCAN_LIMIT of each. Never raises."""
    found = {}
    for read in (lambda: sim.queue, lambda: sim.si_state):
        try:
            items = read()
            if items is None:
                continue
            for index, entry in enumerate(items):
                if index >= ALIAS_SCAN_LIMIT:
                    break
                try:
                    if entry.id is not None:
                        found.setdefault(str(entry.id), entry)
                except Exception:
                    continue
        except Exception:
            continue
    return found


class E2Control:
    def __init__(self, emit, get_state, get_session_id, get_armed_snapshot,
                 get_writer, output, get_armed_name=None, get_zone=None):
        self._emit_row = emit
        self._state = get_state
        self._session_id = get_session_id
        self._armed_snapshot = get_armed_snapshot
        self._writer = get_writer
        self._output = output
        self._armed_name = get_armed_name or (lambda: None)
        # 2.35.0 (D3): the zone she is in now, to tell whether the spots of a menu are still hers to name.
        self._get_zone = get_zone or (lambda: None)
        self._camera_at = None
        self._talk_at = None
        # 2.27.0: windows held back, by dialog id: {act_id, at, kind, send}. 2.31.0: the same record for
        # every window she is offered; send = (original function, args, kwargs) for the fallback.
        self.held = {}
        self._watchdog = None
        self._alarm_owner = _HoldAlarmOwner()
        # 2.31.0 (W3p): her pace as the helper last sent it (kept for the session, saved nowhere); the motives
        # the probe has slowed, by identity: {id: (commodity, the value it got)}; and the game clock as read at install.
        self._pace = {"need_drain": PACE_NORMAL, "slow_time": PACE_NORMAL}
        self._drained = {}
        self._clock_base, self._clock_foreign, self._clock_unreadable = _capture_clock()
        self._clock_applied = False
        self._reset_state()

    # ------------------------------------------------------------------ state
    def _reset_state(self):
        self.last_prepared_token = None
        self.tokens = e2_admission.TokenBook()
        self.learner = e2_registry.CardLearner()
        self.experiments = {}
        self.open_ids = set()
        self.lineage_class = None
        self.load_ticks = None
        self.live_slot = None
        self.designated_sim_id = None
        self.save_subscribed = False
        self.pause_request = None
        self.experiment_counter = 0
        self.storm = e2_trial.StormCounter()
        self.presence = []
        self.act_ids = set()
        # 2.19.1: her pushed acts not yet finished, by interaction id: {act_id, base,
        # tuning_name, interaction_id, seen, misses}. 2.28.0: an act's returned id and each
        # alias it gained map to one shared record.
        self.pushed = {}
        # 2.35.0 (D3): the spot ids of this session (act_menu.SpotIds), and the spots of the newest finished menu
        # build with the zone they were found in: {spot id: spot record}. An act names a spot by its id.
        self.spot_ids = act_menu.SpotIds()
        self.spots = {}
        self.spots_zone = None
        # 2.39.0 (W12 G1): the pie choices the newest menu of this zone showed: {(object id, guid64, variant): the key
        # the choice is matched by}. An act's variant is looked up here, then the choice is found again by its key.
        self.variants = {}
        self.variants_zone = None
        # 2.34.0 (F1): {"act": her act's record or None} while her act is being pushed, else None. A window or
        # screen that arrives meanwhile about her Sim is hers, before _watch_act has recorded the act.
        self.pushing = None
        # 2.38.0 (W11 P1): {group_id: {"item": her act's record, "at": monotonic push time}} for each interaction the
        # probe pushed for her (kept GROUP_KEEP_S), and the monotonic time of her last push (None before one).
        self.pushed_groups = {}
        self.last_push_at = None
        # 2.31.0: the UI_MODAL pause requests seen so far (catch-all), and the windows the fallback showed.
        self._modal_seen = []
        self.shown_to_user = []

    def available(self):
        return (e2_actuator is not None and observers is not None and
                services is not None)

    # --------------------------------------------------------------- emitting
    def _event(self, kind, payload):
        keys = schema.E2_PAYLOAD_KEYS[kind]
        body = dict((key, None) for key in keys)
        body.update(payload)
        try:
            row = schema.make_record(
                kind, telemetry_session_id=self._session_id(),
                wall_timestamp_ms=int(time.time() * 1000),
                monotonic_ns=time.perf_counter_ns(), e2=body)
        except schema.SchemaError:
            return False
        return self._emit_row(row)

    def _experiment_event(self, phase, **payload):
        payload["phase"] = phase
        return self._event("experiment_event", payload)

    def _speed_event(self, phase, code=None, detail=None):
        return self._event("speed_event", {"phase": phase, "code": code, "detail": detail})

    def _lineage_event(self, record, **payload):
        payload["record"] = record
        payload["session_uuid"] = self._session_id()
        return self._event("lineage_event", payload)

    def body_gone(self, reason, sim_id):
        """2.32.0 (PR5): her body is gone (her Sim died). One BODY_GONE lineage record, with the reason."""
        armed = self._armed_snapshot() or {}
        return self._lineage_event("BODY_GONE", guid=armed.get("guid"), slot_id=armed.get("slot_id"),
                                   sim_id=sim_id, ticks=None, lineage_class="BODY_GONE", reason=reason)

    def _say(self, connection, text):
        try:
            self._output(text, connection)
        except Exception:
            pass

    # ------------------------------------------------------------- lifecycle
    def on_arm(self):
        self._release_held(everything=True, code="ARM")
        # 2.31.0 (PR8): the load path. Arming reads the world as it is loaded; an act an earlier
        # session left pushed is resolved as LOADED here, not dropped silently by the reset.
        self._resolve_pushed("LOADED")
        self._pace_release()
        self._reset_state()
        if not self.available():
            return
        try:
            _install_holds(self)
        except Exception:
            pass
        try:
            e2_actuator.subscribe_saves(self.on_manual_save)
            self.save_subscribed = True
        except Exception:
            self.save_subscribed = False

    def on_stop(self, reason):
        """Called after a successful STOP (and by DISARM). Fail-safe cleanup."""
        if reason == "ZONE_CHANGE":
            # 2.31.0 (W4, F8): refines design §4.6. Travel takes the dialog with it, so a held window is dropped
            # here, not sent to the User. Only STOP and DISARM send held windows to the User.
            for key in list(self.held):
                self._drop_held(key, "ZONE_CHANGE")
        else:
            self._release_held(everything=True, code="STOP")
        self._cancel_watchdog()
        self._release_pause(reason)
        # 2.31.0 (PR8): a zone change ends every act still pushed now, as UNKNOWN, not as a LEFT_QUEUE later.
        if reason == "ZONE_CHANGE":
            self._resolve_pushed("ZONE_CHANGE")
        # 2.31.0 (W3p): her motives drain at their own pace again, and the clock is the game's, until she samples.
        self._pace_release()
        for experiment in list(self.experiments.values()):
            if not experiment.closed:
                self._close_experiment(experiment)
        self.tokens.clear()

    def on_disarm(self):
        self.on_stop("DISARM")
        # 2.31.0: the game's own methods back on disarm. The probe has no start hook, so a stop alone
        # keeps the hooks, which act only while she is sampling (every hook passes through otherwise).
        _restore_holds()
        if self.save_subscribed and e2_actuator is not None:
            try:
                e2_actuator.unsubscribe_saves(self.on_manual_save)
            except Exception:
                pass
        self.save_subscribed = False

    # --------------------------------------------------------------- lineage
    def on_poll_row(self, row):
        """Feed every emitted presence row (game thread, after emit)."""
        if row.get("event_kind") == "presence_snapshot":
            self.presence.append(row)
            if len(self.presence) > 120:
                del self.presence[:-120]
            self._reconcile_pushed(row)
            self._release_held()
            self._check_modal()
        if self.lineage_class is None:
            self._try_classify(row)
        if row.get("event_kind") == "presence_snapshot":
            self._body_switch(row)
        learned = self.learner.observe(row, self.open_ids)
        if learned is not None:
            self._experiment_event("SIGNATURE_LEARNED", object_id=learned[0],
                                   detail=learned[1][:schema.MAX_DETAIL_LENGTH])
        for object_id, detail in self.learner.continuation_events:
            self._experiment_event("CONTINUATION_LEARNED", object_id=object_id,
                                   detail=detail[:schema.MAX_DETAIL_LENGTH])
        for experiment in list(self.experiments.values()):
            if experiment.closed:
                continue
            for claim in experiment.observe(row):
                self._experiment_event("CLAIM", experiment_id=experiment.experiment_id,
                                       object_id=experiment.object_id,
                                       interaction_id=experiment.interaction_id,
                                       code=claim, claims=dict(experiment.claims))
            if experiment.closed:
                self._emit_verdict(experiment)

    def _body_switch(self, row):
        """2.31.0 (PR7, live 2026-10-08: the User played another household Sim and her acts could land on
        it): every presence row names the body it saw. A body other than the armed Sim's is a switch.
        The lineage becomes BODY_MISMATCH (sticky until the session is armed again, as a classified
        mismatch is) and a CLASSIFIED lineage record says so once. Her acts, answers, camera and talk
        refuse from then on, with or without a prepare."""
        if self.lineage_class is None or self.lineage_class == e2_lineage.BODY_MISMATCH:
            return
        armed = (self._armed_snapshot() or {}).get("sim_id")
        body = (row.get("body") or {}).get("sim_id")
        if armed is None or body is None or str(body) == str(armed):
            return
        self.lineage_class = e2_lineage.BODY_MISMATCH
        save = row.get("save") or {}
        game = row.get("game") or {}
        ticks = game.get("ticks")
        self._lineage_event("CLASSIFIED", guid=save.get("save_slot_guid"), slot_id=save.get("slot_id"),
                            sim_id=str(body), ticks=ticks if type(ticks) is int else None,
                            lineage_class=e2_lineage.BODY_MISMATCH)

    def _try_classify(self, row):
        writer = self._writer()
        if writer is None:
            return
        try:
            state, records = writer.ledger_snapshot()
        except AttributeError:
            return
        if state == "PENDING":
            return
        save = row.get("save") or {}
        body = row.get("body") or {}
        try:
            ticks = observers._saved_world_ticks()
        except Exception:
            ticks = None
        guid, slot, sim_id = save.get("save_slot_guid"), save.get("slot_id"), body.get("sim_id")
        if state != "OK":
            lineage_class = e2_lineage.FOREIGN_OR_UNKNOWN
        else:
            lineage_class = e2_lineage.classify(records, guid, slot, sim_id, ticks)
            designated = e2_lineage.designated_body(records, guid)
            self.designated_sim_id = None if designated is None else designated.get("sim_id")
        self.lineage_class = lineage_class
        self.load_ticks = ticks
        self.live_slot = slot
        self._lineage_event("LOAD_OBSERVED", guid=guid, slot_id=slot, sim_id=sim_id, ticks=ticks)
        self._lineage_event("CLASSIFIED", guid=guid, slot_id=slot, sim_id=sim_id, ticks=ticks,
                            lineage_class=lineage_class)

    def on_manual_save(self, *args, **kwargs):
        """Persistence-service callback (no arguments on 1.128). Armed only."""
        if self._state() not in ("ARMED", "SAMPLING") or observers is None:
            return
        try:
            save = observers._save_snapshot()
            saved_ticks = observers._saved_world_ticks()
        except Exception as error:
            self._lineage_event("SAVE_OBSERVED", lineage_class="READ_FAILURE:%s" %
                                type(error).__name__)
            return
        snap = self._armed_snapshot() or {}
        self._lineage_event("SAVE_OBSERVED", guid=save.get("save_slot_guid"),
                            slot_id=save.get("slot_id"), sim_id=snap.get("sim_id"),
                            ticks=saved_ticks, loaded_from_slot_id=self.live_slot)
        self.live_slot = save.get("slot_id")
        if self.lineage_class is not None:
            self.lineage_class = e2_lineage.reclassify_after_save(self.lineage_class)
            self._lineage_event("CLASSIFIED", guid=save.get("save_slot_guid"),
                                slot_id=save.get("slot_id"), sim_id=snap.get("sim_id"),
                                ticks=saved_ticks, lineage_class=self.lineage_class)

    # ------------------------------------------------------------- admission
    def _view(self, object_id):
        """Fresh plain-data admission view (game-thread reads only)."""
        view = {"sampling": self._state() == "SAMPLING",
                "lineage_class": self.lineage_class,
                "designated_sim_id": self.designated_sim_id}
        sim_info, sim = observers.select_lab_body(
            services.sim_info_manager().get_all(), observers.ALL_HIDDEN_REASONS)
        save = observers._save_snapshot()
        game = observers._game_snapshot()
        queued = () if sim.queue is None else sim.queue
        running = () if sim.si_state is None else sim.si_state
        entries, _, _ = snapshot.merge_interactions(
            queued, running, observers._describe_interaction)
        posture = observers._posture_snapshot(sim) or {}
        obj = e2_actuator.find_object(object_id)
        offers = []
        context = e2_actuator.build_context(sim)
        if obj is not None:
            offers = e2_actuator.sit_offers(obj, context)
        view.update({
            "guid": save.get("save_slot_guid"), "slot_id": save.get("slot_id"),
            "sim_id": None if sim_info.id is None else str(sim_info.id),
            "body_available": sim is not None, "ticks": game.get("ticks"),
            "paused": game.get("paused"), "posture_target_id": posture.get("target_id"),
            "entries": entries,
            "object": {"exists": obj is not None, "sit_offer_count": len(offers)},
        })
        return view, sim, obj, offers, context

    def cmd_prepare(self, object_id, connection):
        if not self.available():
            self._say(connection, "E2_UNAVAILABLE")
            return False
        try:
            view, _, _, _, _ = self._view(object_id)
            code = e2_admission.check(view, object_id, EXCLUDED_OBJECT_IDS,
                                      self.learner.signatures, self.open_ids)
            if code is not None:
                self._experiment_event("PREPARE_REJECT", object_id=object_id, code=code)
                self._say(connection, "PREPARE_REJECT %s" % code)
                return False
            token, code = self.tokens.issue(object_id, view, _now())
            if token is None:
                self._experiment_event("PREPARE_REJECT", object_id=object_id, code=code)
                self._say(connection, "PREPARE_REJECT %s" % code)
                return False
            if self.designated_sim_id is None:
                self.designated_sim_id = view["sim_id"]
                self._lineage_event("DESIGNATED_BODY", guid=view["guid"], slot_id=view["slot_id"],
                                    sim_id=view["sim_id"], ticks=view["ticks"],
                                    lineage_class=self.lineage_class)
            self._experiment_event("PREPARE_OK", object_id=object_id, token=token)
            self.last_prepared_token = token
            self._say(connection, "PREPARE_OK token %s (30 s)" % token)
            return True
        except observers.LabIdentityAmbiguous:
            code = e2_admission.BODY_UNAVAILABLE
            self._experiment_event("PREPARE_REJECT", object_id=object_id, code=code)
            self._say(connection, "PREPARE_REJECT %s" % code)
            return False
        except Exception as error:
            code = "E2_EXCEPTION:%s" % type(error).__name__
            self._experiment_event("PREPARE_REJECT", object_id=object_id, code=code[:64])
            self._say(connection, "PREPARE_REJECT %s" % code)
            return False

    def cmd_sit(self, token, connection):
        if not self.available():
            self._say(connection, "E2_UNAVAILABLE")
            return False
        try:
            bound, code = self.tokens.consume(token, _now())
            if bound is None:
                self._experiment_event("ADMIT_REJECT", token=token, code=code)
                self._say(connection, "ADMIT_REJECT %s" % code)
                return False
            object_id = bound["object_id"]
            view, sim, obj, offers, context = self._view(object_id)
            code = e2_admission.admit(bound, view, object_id, EXCLUDED_OBJECT_IDS,
                                      self.learner.signatures, self.open_ids)
            if code is not None:
                extra = {}
                if code == e2_admission.STALE_SNAPSHOT:
                    underlying = e2_admission.check(
                        view, object_id, EXCLUDED_OBJECT_IDS,
                        self.learner.signatures, self.open_ids)
                    if underlying is not None:
                        extra["detail"] = underlying[:schema.MAX_DETAIL_LENGTH]
                self._experiment_event("ADMIT_REJECT", token=token, object_id=object_id,
                                       code=code, **extra)
                self._say(connection, "ADMIT_REJECT %s" % code)
                return False
            self.experiment_counter += 1
            experiment_id = "%s-%d" % (self._session_id()[:8], self.experiment_counter)
            pushed_ns = time.perf_counter_ns()
            self._push_mark(None)
            try:
                interaction, detail = e2_actuator.push_sit(sim, obj, offers[0], context)
            finally:
                self.pushing = None
            if interaction is None:
                self._experiment_event("PUSH_FAILED", experiment_id=experiment_id,
                                       token=token, object_id=object_id,
                                       detail=(detail or "")[:schema.MAX_DETAIL_LENGTH])
                self._say(connection, "PUSH_FAILED")
                return False
            interaction_id = str(interaction.id)
            experiment = e2_registry.Experiment(
                experiment_id, token, object_id, view["sim_id"], interaction_id, pushed_ns,
                self.learner.signatures.get(object_id),
                [entry.get("interaction_id") for entry in view["entries"]],
                continuation=frozenset(self.learner.continuation.get(object_id, ())))
            self.experiments[experiment_id] = experiment
            self.open_ids.add(interaction_id)

            self._watch_finish(experiment, interaction)
            self._experiment_event("PUSHED", experiment_id=experiment_id, token=token,
                                   object_id=object_id, interaction_id=interaction_id,
                                   claims=dict(experiment.claims))
            self._say(connection, "PUSHED %s interaction %s" % (experiment_id, interaction_id))
            return True
        except Exception as error:
            code = "E2_EXCEPTION:%s" % type(error).__name__
            self._experiment_event("ADMIT_REJECT", token=token, code=code[:64])
            self._say(connection, "ADMIT_REJECT %s" % code)
            return False

    def cmd_trial(self, object_id, guid64, connection):
        """Push one parameter-free affordance and judge it with an interaction card."""
        if not self.available():
            self._say(connection, "E2_UNAVAILABLE")
            return False
        if self.storm.latched():
            self._experiment_event("TRIAL_REJECT", object_id=object_id, guid64=guid64,
                                   code=e2_trial.TRIAL_STORM)
            self._say(connection, "TRIAL_REJECT %s" % e2_trial.TRIAL_STORM)
            return False
        try:
            view, sim, obj, offers, context = self._trial_view(object_id, guid64)
            code = e2_trial.trial_check(view)
            if code is not None:
                self._experiment_event("TRIAL_REJECT", object_id=object_id, guid64=guid64,
                                       code=code)
                self._say(connection, "TRIAL_REJECT %s" % code)
                return False
            self.experiment_counter += 1
            experiment_id = "%s-%d" % (self._session_id()[:8], self.experiment_counter)
            pushed_ns = time.perf_counter_ns()
            self._push_mark(None)
            try:
                interaction, detail, kind = e2_actuator.push_affordance(
                    sim, obj, offers[0], context)
            finally:
                self.pushing = None
            if interaction is None and kind == "refused":
                reason = (detail or "")[:schema.MAX_DETAIL_LENGTH]
                self._experiment_event("PUSH_REFUSED", experiment_id=experiment_id,
                                       object_id=object_id, guid64=guid64, detail=reason)
                self._say(connection, "PUSH_REFUSED %s" % reason)
                return False
            if interaction is None:
                self.storm.fail()
                self._experiment_event("PUSH_FAILED", experiment_id=experiment_id,
                                       object_id=object_id, guid64=guid64,
                                       detail=(detail or "")[:schema.MAX_DETAIL_LENGTH])
                self._say(connection, "PUSH_FAILED")
                return False
            self.storm.clear()
            interaction_id = str(interaction.id)
            tuning_name = _tuning_name(offers[0])
            route = e2_actuator.food_route(offers[0])
            if route is not None:
                card = e2_cards.need_card(object_id, guid64, motive="hunger", direction=1)
                control_rows = self._food_control(pushed_ns)
                window = e2_registry.FOOD_TRIAL_WINDOW_SECONDS
            else:
                card = e2_cards.interaction_card(object_id, guid64)
                control_rows = None
                window = e2_registry.TRIAL_WINDOW_SECONDS
            experiment = e2_registry.Experiment(
                experiment_id, None, object_id, view["sim_id"], interaction_id, pushed_ns,
                None, [entry.get("interaction_id") for entry in view["entries"]],
                continuation=(), card=card, control_rows=control_rows,
                window_seconds=window, food_route=route)
            experiment.tuning_name = tuning_name
            experiment.relief = e2_trial.relief_motives(view["motives"], tuning_name, route)
            experiment.interaction_ref = interaction
            self.experiments[experiment_id] = experiment
            self.open_ids.add(interaction_id)

            experiment.sim_ref = sim
            self._watch_finish(experiment, interaction)
            self._experiment_event("PUSHED", experiment_id=experiment_id,
                                   object_id=object_id, interaction_id=interaction_id,
                                   detail=("relief=%s" % ",".join(experiment.relief)
                                           if experiment.relief else None),
                                   guid64=guid64, card_class=card["card_class"],
                                   tuning_name=tuning_name, claims=dict(experiment.claims))
            self._say(connection, "TRIAL_PUSHED %s interaction %s" %
                      (experiment_id, interaction_id))
            return True
        except observers.LabIdentityAmbiguous:
            code = e2_admission.BODY_UNAVAILABLE
            self._experiment_event("TRIAL_REJECT", object_id=object_id, guid64=guid64, code=code)
            self._say(connection, "TRIAL_REJECT %s" % code)
            return False
        except Exception as error:
            code = "E2_EXCEPTION:%s" % type(error).__name__
            self._experiment_event("TRIAL_REJECT", object_id=object_id, guid64=guid64,
                                   code=code[:64])
            self._say(connection, "TRIAL_REJECT %s" % code)
            return False

    # ------------------------------------------------------------ acts (8f)
    def _act_event(self, act_id, phase, **payload):
        payload["act_id"] = act_id
        payload["phase"] = phase
        return self._event("act_event", payload)

    def _act_check(self, object_id, guid64, owner=False, variant=None, sim_id=None):
        """None when her chosen action may be pushed now, else (code, detail).

        Unlike a trial there is no lab-only gate, no busy gate (it queues like a
        player's click) and no distress gate (her body's reflexes still act): she
        chose it. Lineage refuses only a different body."""
        if self._state() != "SAMPLING":
            return ("NOT_SAMPLING", None), None
        if self.lineage_class == e2_lineage.BODY_MISMATCH:
            return ("BODY_MISMATCH", None), None
        sim_info, sim = observers.select_lab_body(
            services.sim_info_manager().get_all(), observers.ALL_HIDDEN_REASONS)
        if sim is None:
            return ("BODY_UNAVAILABLE", None), None
        if self.designated_sim_id is not None and str(sim_info.id) != self.designated_sim_id:
            return ("BODY_MISMATCH", None), None
        # 2.31.0 (PR7): the body an act would use must be the armed Sim, with or without a prepare.
        armed = (self._armed_snapshot() or {}).get("sim_id")
        if armed is not None and str(sim_info.id) != str(armed):
            return ("BODY_MISMATCH", None), None
        # 2.32.0 (PR6, User ruling): the User plays another household Sim; her acts are refused, never
        # the User's Sim's. Not sticky: the refusal ends when the client plays her Sim again.
        active = observers.active_sim_id()
        if active is not None and active != str(sim_info.id):
            return ("BODY_MISMATCH", "NOT_ACTIVE"), None
        if object_id in EXCLUDED_OBJECT_IDS:
            return (e2_admission.OBJECT_EXCLUDED, None), None
        spot = self._spot_of(object_id)
        if spot is not None:
            # 2.35.0 (D3): a spot is Go Here at its point, with the game's pick; the terrain offers Go Here there.
            obj, context = e2_actuator.spot_target(sim, spot, owner=owner)
            if obj is None:
                return ("NO_OBJECT", None), None
            own_phone = False
            offers = e2_actuator.spot_offers_for(e2_actuator.terrain_object(), context, guid64)
        else:
            obj = e2_actuator.find_object(object_id)
            if obj is None:
                return ("NO_OBJECT", None), None
            context = e2_actuator.build_context(sim, owner=owner)
            # 2.29.0: an act whose target is her own Sim is one of her phone's acts, offered by her
            # phone's list and by nothing else; the push still targets her Sim (push_affordance_ex).
            own_phone = obj is sim
            if own_phone:
                offers = e2_actuator.phone_offers_for(sim, guid64)
            else:
                offers = e2_actuator.offers_for(obj, context, guid64)
        if not offers:
            return ("NOT_OFFERED", None), None
        affordance = offers[0]
        if variant is not None:
            return self._variant_check(sim, obj, affordance, context, object_id, guid64, variant,
                                       spot=spot is not None or own_phone)
        try:
            person = obj.is_sim is True and obj is not sim
        except Exception:
            person = False
        if own_phone:
            excluded = e2_actuator.phone_act_excluded(affordance)
        else:
            excluded = e2_actuator.act_excluded(affordance, person)
        if excluded is not None:
            return ("EXCLUDED", excluded), None
        if not e2_actuator.user_directed(affordance):
            return ("NOT_USER_DIRECTED", None), None
        # 2.40.0 (W13 P1): a Sim picker takes the Sim she named (its picked_item_ids and included_override); the Sim is
        # named only to a picker. The picker is tested and pushed with her choice.
        parameters = None
        if e2_actuator.needs_sim(affordance):
            if sim_id is None:
                return ("SIM_NEEDED", None), None
            parameters, step = self._picked_sim(sim, sim_id)
            if parameters is None:
                return ("SIM_NOT_CHOOSABLE", "step %s" % step), None
        elif sim_id is not None:
            return ("NOT_A_SIM_ACT", None), None
        if parameters is None:
            ok, reason, reason_key = e2_actuator.preflight_test(sim, obj, affordance, context)
        else:
            ok, reason, reason_key = e2_actuator.preflight_test(sim, obj, affordance, context, parameters)
        if not ok:
            if parameters is not None:
                return ("SIM_NOT_CHOOSABLE", "step picker", reason_key), None
            # 2.32.0 (PR10, PR11): a refusal during a fire, or in build mode, is named as such.
            if observers.fire_active() is True:
                return ("FIRE_REFUSED", reason, reason_key), None
            if observers.build_mode() is True:
                return ("BUILD_MODE_REFUSED", reason, reason_key), None
            return ("GAME_REFUSED", reason, reason_key), None
        return None, (sim, obj, affordance, context, False, parameters)

    def _picked_sim(self, sim, sim_id):
        """2.40.0 (W13 P1): the picker's parameters for the Sim she named, and the step of the picker's own generator
        that Sim passes ("ok") or fails (observers.read_picker_steps). No parameters unless the step is ok."""
        sim_info = e2_actuator.sim_info_for(sim_id)
        if sim_info is None:
            return None, "unknown"
        step = observers.read_picker_steps(observers.her_sim_info(), [sim_info]).get(str(sim_id), "unknown")
        if step != "ok":
            return None, step
        return e2_actuator.picker_parameters(sim_info, sim_id), step

    def _variant_check(self, sim, obj, pie, context, object_id, guid64, variant, spot=False):
        """2.39.0 (W12 G1): the check of a pie choice. The pie is enumerated again now and the choice whose match key the
        menu gave this variant is found by that key; none (or no menu entry for the variant) is VARIANT_GONE. The choice
        is then checked as its own pair, the way the menu checked it. A spot or her own phone has no pie choices."""
        if spot or not e2_actuator.is_pie(pie):
            return ("VARIANT_GONE", None), None
        key = self.variant_key(object_id, guid64, variant)
        choice = None if key is None else e2_actuator.variant_choice(pie, obj, context, key)
        if choice is None:
            return ("VARIANT_GONE", None), None
        excluded = e2_actuator.choice_excluded(choice)
        if excluded is not None:
            return ("EXCLUDED", excluded), None
        ok, reason, reason_key = e2_actuator.choice_test(choice, context)
        if not ok:
            if observers.fire_active() is True:
                return ("FIRE_REFUSED", reason, reason_key), None
            if observers.build_mode() is True:
                return ("BUILD_MODE_REFUSED", reason, reason_key), None
            return ("GAME_REFUSED", reason, reason_key), None
        return None, (sim, obj, choice, context, True)

    def cmd_act(self, act_id, object_id, guid64, connection, owner=False, variant=None, sim_id=None):
        """8f: push exactly the game action Ashley chose; never another, never twice.

        ACCEPTED is written before the push, so a failure in between leaves
        dispatched-but-unknown evidence (UNKNOWN), never nothing."""
        if act_id in self.act_ids:
            self._say(connection, "ACT_REJECT DUPLICATE")
            return False
        self.act_ids.add(act_id)
        base = {"object_id": object_id, "guid64": guid64}
        # 2.39.0 (W12 G1): a variant is a menu index (an int from 0 to MENU_MAX_VARIANT), never a bool or a string.
        if variant is not None and (type(variant) is not int or not 0 <= variant <= schema.MENU_MAX_VARIANT):
            self._act_event(act_id, "REJECTED", code="BAD_VARIANT", **base)
            self._say(connection, "ACT_REJECT BAD_VARIANT")
            return False
        if not self.available():
            self._act_event(act_id, "REJECTED", code="E2_UNAVAILABLE", **base)
            self._say(connection, "ACT_REJECT E2_UNAVAILABLE")
            return False
        accepted = False
        try:
            refusal, bound = self._act_check(object_id, guid64, owner=owner, variant=variant, sim_id=sim_id)
            if refusal is not None:
                code, detail = refusal[0], refusal[1]
                reason_key = refusal[2] if len(refusal) > 2 else None
                self._act_event(act_id, "REJECTED", code=code,
                                detail=None if detail is None else str(detail)[:schema.MAX_DETAIL_LENGTH],
                                reason_key=reason_key, **base)
                self._say(connection, "ACT_REJECT %s" % code)
                return False
            sim, obj, affordance, context, is_choice = bound[:5]
            # 2.40.0 (W13 P1): a Sim picker's parameters (her picked Sim), None for every other act.
            parameters = bound[5] if len(bound) > 5 else None
            # 2.39.0 (W12 G1): a pie choice is named by its own affordance; it runs as its own pair (push_choice).
            tuning_name = _tuning_name(affordance.affordance if is_choice else affordance)
            self._act_event(act_id, "ACCEPTED", tuning_name=tuning_name, owner=owner is True, **base)
            accepted = True
            queued_before = _queued_interactions(sim)
            self._push_mark({"act_id": act_id, "interaction_id": None, "tuning_name": tuning_name, "base": base})
            try:
                if is_choice:
                    interaction, detail, kind, reason_key = e2_actuator.push_choice(affordance, context)
                else:
                    if parameters is None:
                        interaction, detail, kind, reason_key = e2_actuator.push_affordance_ex(
                            sim, obj, affordance, context)
                    else:
                        interaction, detail, kind, reason_key = e2_actuator.push_affordance_ex(
                            sim, obj, affordance, context, parameters)
            finally:
                self.pushing = None
            # 2.28.0 (live 2026-10-08: a picker's push returned 704 while her queue gained 703, and
            # 704 never appeared): whatever the push put in her queue or running list is this act too.
            born = {}
            if kind != "refused":
                queued_after = _queued_interactions(sim)
                born = dict((key, entry) for key, entry in queued_after.items()
                            if key not in queued_before)
            if interaction is None and not born:
                code = "PUSH_REFUSED" if kind == "refused" else "PUSH_FAILED"
                self._act_event(act_id, "REJECTED", code=code, tuning_name=tuning_name,
                                detail=(detail or "")[:schema.MAX_DETAIL_LENGTH] or None,
                                reason_key=reason_key if kind == "refused" else None, **base)
                self._say(connection, "ACT_REJECT %s" % code)
                return False
            if interaction is None:
                # 2.28.0 (live 2026-10-08: a push returned a truthy result with no interaction object,
                # while interaction 2158 ran): the first interaction the push queued is the act.
                interaction_id = next(iter(born))
                interaction = born.pop(interaction_id)
            else:
                interaction_id = str(interaction.id)
                born.pop(interaction_id, None)
            aliases = list(born)[:schema.ACT_MAX_ALIASES]
            self._act_event(act_id, "PUSHED", interaction_id=interaction_id,
                            tuning_name=tuning_name, aliases=aliases or None, **base)
            self._watch_act(act_id, base, interaction_id, tuning_name, interaction, born)
            self._say(connection, "ACT_PUSHED %s interaction %s" % (act_id, interaction_id))
            return True
        except observers.LabIdentityAmbiguous:
            phase, code = ("UNKNOWN", "BODY_UNAVAILABLE") if accepted else ("REJECTED", "BODY_UNAVAILABLE")
            self._act_event(act_id, phase, code=code, **base)
            self._say(connection, "ACT_%s %s" % (phase, code))
            return False
        except Exception as error:
            code = ("E2_EXCEPTION:%s" % type(error).__name__)[:64]
            phase = "UNKNOWN" if accepted else "REJECTED"
            self._act_event(act_id, phase, code=code, **base)
            self._say(connection, "ACT_%s %s" % (phase, code))
            return False

    # ------------------------------------------------------------ 2.40.0 (W13 P1): her reach (verbs)
    # go and event hold the one-act slot like an act; their rows are act_event rows for their act id, and their facts
    # are the row's result. The host reports and checks the game's own calls; it never judges her choice.
    _go = None

    def _reject(self, act_id, base, connection, code, detail=None):
        """2.40.0: a verb refused: its REJECTED row and the reply. Always False."""
        self._act_event(act_id, "REJECTED", code=code,
                        detail=None if detail is None else str(detail)[:schema.MAX_DETAIL_LENGTH], **base)
        self._say(connection, "ACT_REJECT %s" % code)
        return False

    def _verb_body(self, act_id, base, connection):
        """2.40.0: the checks every verb shares before its own: the act id is new, E2 is available, and her body may act
        (sampling, the same body as her acts, the User's Sim not the one playing). (sim_info, sim), or None when refused."""
        if act_id in self.act_ids:
            self._say(connection, "ACT_REJECT DUPLICATE")
            return None
        self.act_ids.add(act_id)
        if not self.available():
            self._reject(act_id, base, connection, "E2_UNAVAILABLE")
            return None
        if self._state() != "SAMPLING":
            self._reject(act_id, base, connection, "NOT_SAMPLING")
            return None
        if self.lineage_class == e2_lineage.BODY_MISMATCH:
            self._reject(act_id, base, connection, "BODY_MISMATCH")
            return None
        sim_info, sim = observers.select_lab_body(services.sim_info_manager().get_all(), observers.ALL_HIDDEN_REASONS)
        if sim is None:
            self._reject(act_id, base, connection, "BODY_UNAVAILABLE")
            return None
        armed = (self._armed_snapshot() or {}).get("sim_id")
        if (self.designated_sim_id is not None and str(sim_info.id) != self.designated_sim_id) or (
                armed is not None and str(sim_info.id) != str(armed)):
            self._reject(act_id, base, connection, "BODY_MISMATCH")
            return None
        active = observers.active_sim_id()
        if active is not None and active != str(sim_info.id):
            self._reject(act_id, base, connection, "BODY_MISMATCH", "NOT_ACTIVE")
            return None
        return sim_info, sim

    def cmd_go(self, act_id, zone_id, connection, known_zones):
        """2.40.0 (W13 P1): her trip to a place she knows (the game's travel service, which asks the client to travel).
        ACCEPTED, then PUSHED (the trip is asked). FINISHED ARRIVED comes from tick_verbs, once her Sim is in that zone;
        UNKNOWN TRAVEL_UNSEEN when no zone change comes within reach.GO_SEEN_S real seconds. Whether she should go is her
        word (she asks the User first); the host records it and never gates it on its own."""
        base = {"object_id": None, "guid64": None}
        accepted = False
        try:
            body = self._verb_body(act_id, base, connection)
            if body is None:
                return False
            sim_info, _sim = body
            code = self._go_refusal(sim_info, zone_id, known_zones)
            if code is not None:
                return self._reject(act_id, base, connection, code)
            self._act_event(act_id, "ACCEPTED", tuning_name="travel", **base)
            accepted = True
            if e2_actuator.travel(sim_info.id, zone_id) is not True:
                self._act_event(act_id, "REJECTED", code="PUSH_FAILED", **base)
                self._say(connection, "ACT_REJECT PUSH_FAILED")
                return False
            self._act_event(act_id, "PUSHED", tuning_name="travel", **base)
            self._go = {"act_id": act_id, "zone_id": str(zone_id), "at": time.monotonic()}
            self._say(connection, "ACT_PUSHED %s travel" % act_id)
            return True
        except Exception as error:
            code = ("E2_EXCEPTION:%s" % type(error).__name__)[:64]
            self._act_event(act_id, "UNKNOWN" if accepted else "REJECTED", code=code, **base)
            self._say(connection, "ACT_%s %s" % ("UNKNOWN" if accepted else "REJECTED", code))
            return False

    def _go_refusal(self, sim_info, zone_id, known_zones):
        """2.40.0: the code that refuses a trip now, or None: CARRYING_BABY, SAME_ZONE, NO_ZONE (not a place of the newest
        places list), SAVE_LOCKED (the game's own save lock). A trip the game refuses otherwise shows as TRAVEL_UNSEEN."""
        if observers.is_carrying_baby(sim_info) is True:
            return "CARRYING_BABY"
        if str(_read(lambda: services.current_zone_id())) == str(zone_id):
            return "SAME_ZONE"
        if str(zone_id) not in known_zones:
            return "NO_ZONE"
        if observers.save_locked():
            return "SAVE_LOCKED"
        return None

    def tick_verbs(self):
        """2.40.0 (W13 P1): the pending trip, each sampling tick: FINISHED ARRIVED once her Sim is in the zone it asked for,
        UNKNOWN TRAVEL_UNSEEN when no zone change came within reach.GO_SEEN_S real seconds. Never raises."""
        pending = self._go
        if pending is None:
            return
        try:
            if str(_read(lambda: services.current_zone_id())) == pending["zone_id"]:
                self._go = None
                self._act_event(pending["act_id"], "FINISHED", code="ARRIVED", object_id=None, guid64=None,
                                result={"zone_id": pending["zone_id"]})
            elif time.monotonic() - pending["at"] >= reach.GO_SEEN_S:
                self._go = None
                self._act_event(pending["act_id"], "UNKNOWN", code="TRAVEL_UNSEEN", object_id=None, guid64=None)
        except Exception:
            self._go = None

    def cmd_event(self, act_id, situation_id, guests, start, connection):
        """2.40.0 (W13 P1): a planned event (a situation the game makes user-facing): her as host, the guests invited, now
        or at a time today or tomorrow. The cost comes from her household's funds first (the game's own try_remove); a
        failed creation gives the money back. ACCEPTED, then FINISHED CREATED with its cost, her funds and the start."""
        base = {"object_id": None, "guid64": None}
        accepted = False
        charged = None
        try:
            body = self._verb_body(act_id, base, connection)
            if body is None:
                return False
            sim_info, sim = body
            situation = e2_actuator.situation_type(situation_id)
            if situation is None:
                return self._reject(act_id, base, connection, "CREATE_FAILED", "no situation type")
            now = e2_actuator.now_absolute_minutes()
            if now is None:
                return self._reject(act_id, base, connection, "CREATE_FAILED", "clock")
            start_min, scheduled, code = self._event_start(start, now)
            if code is not None:
                return self._reject(act_id, base, connection, code)
            cost = e2_actuator.situation_cost(situation) or 0
            household = _read(lambda: sim_info.household)
            money = observers.household_money(sim_info)
            if cost > 0 and (money is None or money < cost):
                return self._reject(act_id, base, connection, "NO_FUNDS")
            guest_ids = reach.sim_ids(list(guests), reach.EVENT_GUESTS_MAX)
            if guest_ids is None:
                return self._reject(act_id, base, connection, "CREATE_FAILED", "guests")
            guest_list = e2_actuator.event_guest_list(sim_info.id, guest_ids, e2_actuator.default_job(situation))
            if guest_list is None:
                return self._reject(act_id, base, connection, "CREATE_FAILED", "guest list")
            self._act_event(act_id, "ACCEPTED", tuning_name="event", **base)
            accepted = True
            if cost > 0:
                charged = e2_actuator.charge(household, cost, sim, reach.FUNDS_REASON)
                if charged is None:
                    return self._reject(act_id, base, connection, "CREATE_FAILED", "funds unread")
                if charged is False:
                    return self._reject(act_id, base, connection, "NO_FUNDS")
            created = e2_actuator.create_event(_read(lambda: services.current_zone_id()), situation, guest_list,
                                               scheduled)
            if created is None:
                if charged:
                    e2_actuator.refund(household, cost, sim, reach.FUNDS_REASON)
                return self._reject(act_id, base, connection, "CREATE_FAILED", "create")
            funds = observers.household_money(sim_info)
            self._act_event(act_id, "FINISHED", code="CREATED", result={"cost": cost, "funds": funds,
                                                                        "start_min": start_min}, **base)
            self._say(connection, "ACT_FINISHED %s CREATED" % act_id)
            return True
        except Exception as error:
            code = ("E2_EXCEPTION:%s" % type(error).__name__)[:64]
            self._act_event(act_id, "UNKNOWN" if accepted else "REJECTED", code=code, **base)
            self._say(connection, "ACT_%s %s" % ("UNKNOWN" if accepted else "REJECTED", code))
            return False

    def _event_start(self, start, now):
        """2.40.0: (absolute game minute, scheduled time or None, refusal code or None) for a start: "now", or a day offset
        (0 today, 1 tomorrow) with an hour and minute. START_PAST when it is before the clock; CREATE_FAILED when the game
        cannot make the time."""
        if start == "now":
            return now, None, None
        start_min = reach.start_minute(start["day_offset"], start["hour"], start["minute"],
                                       now % reach.START_MINUTES_PER_DAY, now // reach.START_MINUTES_PER_DAY)
        if start_min is None:
            return None, None, "START_PAST"
        scheduled = e2_actuator.scheduled_at(start_min)
        return (start_min, scheduled, None) if scheduled is not None else (None, None, "CREATE_FAILED")

    def note_phone(self, op):
        """2.40.0 (W13 P1): a text for her (PhoneNotificationOp): one phone row, with the sender's sim id when the
        notification names a Sim other than her own. Written while sampling only. Never raises."""
        try:
            if self._state() != "SAMPLING":
                return
            her = observers.her_sim_info()
            sender = _read(lambda: op.sim_id)
            sender_id = None if sender is None or _read(lambda: sender == her.id) else str(sender)
            row = reach.phone_event("text", sender_id, None)
            if row is not None:
                self._event("phone", row)
        except Exception:
            pass

    def _ring_for_her(self, dialog):
        """2.40.0 (W13 P1): her phone's ring is hers when its caller is a Sim other than the User's active Sim: the
        dialog's target sim id is the caller. False when either id is unread."""
        caller = _read(lambda: dialog.target_sim_id)
        active = observers.active_sim_id()
        if caller is None or active is None:
            return False
        return str(caller) != active

    def _answer_check(self, dialog_id, pick, rows=None, text=None):
        """None when her answer may be given now, else (code, detail). The dialog must be open
        and hers (or the game's own, with no owner); a row must be one it offers, enabled.
        2.31.0 (§4.3, §4.4): rows, counts and text are checked by _answer_plan; the bound plan
        says what cmd_answer sends (rows, counts, text fields), None for a button."""
        if self._state() != "SAMPLING":
            return ("NOT_SAMPLING", None), None
        if self.lineage_class == e2_lineage.BODY_MISMATCH:
            return ("BODY_MISMATCH", None), None
        sim_info, sim = observers.select_lab_body(
            services.sim_info_manager().get_all(), observers.ALL_HIDDEN_REASONS)
        if sim is None:
            return ("BODY_UNAVAILABLE", None), None
        service = services.ui_dialog_service()
        dialog = service._active_dialogs.get(int(dialog_id))
        if dialog is None:
            return ("NO_DIALOG", None), None
        try:
            owner = dialog._owner()
        except Exception:
            owner = None
        if owner is not None and owner.id != sim_info.id:
            return ("NOT_HERS", None), None
        # 2.31.0 (§4.2): a window the fallback showed is the User's now; her renaming or retraiting
        # windows are the User's always (Q3).
        if str(int(dialog_id)) in self.shown_to_user:
            return ("SHOWN_TO_USER", None), None
        try:
            interactions = self._resolver_interactions(dialog)
        except Exception:
            interactions = []
        if self._identity_window(dialog, str(sim_info.id), interactions, []):
            return ("IDENTITY_USER", None), None
        # 2.31.0 (W4, F1): only a window held for her is answerable; one the game or the User was shown is not.
        if str(int(dialog_id)) not in self.held:
            return ("NOT_HELD", None), None
        if rows is not None or text is not None:
            refusal, plan = self._answer_plan(dialog, dialog_id, pick, rows, text)
            if refusal is not None:
                return refusal, None
            return None, (service, dialog, plan, observers.RESPONSE_IDS["ok"])
        if pick.isdigit():
            offered_rows = [row for row in observers._dialog_rows(dialog) if row["option_id"] == pick]
            if not offered_rows:
                return ("NO_ROW", None), None
            if not offered_rows[0]["enabled"]:
                return ("ROW_DISABLED", None), None
            # 2.31.0 (W4, F2): a picker that needs more than one row is never answered with a single row.
            # 2.39.0 (W12 A3): nor is a purchase picker with counts: its one row is checked and sent with its count.
            select = observers.select_of(dialog)
            if observers.counts_of(dialog) is not None or (select is not None and select["min"] > 1):
                refusal, found = self._check_rows(dialog, [{"option_id": pick, "count": 1}])
                if refusal is not None:
                    return refusal, None
                plan = {"rows": None, "counts": None, "text": None}
                plan.update(found)
                return None, (service, dialog, plan, observers.RESPONSE_IDS["ok"])
            return None, (service, dialog, {"rows": [int(pick)], "counts": None, "text": None},
                          observers.RESPONSE_IDS["ok"])
        # 2.39.0 (W12 A2): a numbered button is answered by its number, named response_<N>.
        response = observers.RESPONSE_IDS.get(pick)
        if response is None:
            response = _response_number(pick)
        offered = [item["response"] for item in observers._dialog_responses(dialog)]
        if response is None or (pick not in offered and pick not in ("ok", "cancel")):
            return ("NO_RESPONSE", pick), None
        return None, (service, dialog, None, response)

    def _answer_plan(self, dialog, dialog_id, pick, rows, text):
        """2.31.0 (§4.3, §4.4, §11): her rows, counts and text, checked against the live dialog and, for
        text, the held message. Returns (refusal, plan); plan has "rows", "counts" and "text" (None each
        when absent)."""
        if pick != "ok":
            return ("NO_RESPONSE", pick), None
        plan = {"rows": None, "counts": None, "text": None}
        if rows is not None:
            refusal, found = self._check_rows(dialog, rows)
            if refusal is not None:
                return refusal, None
            plan.update(found)
        if text is not None:
            item = self.held.get(str(int(dialog_id)))
            fields = None
            if item is not None:
                fields = _read_text_fields(_held_message(item["kind"], item["send"][1], item["send"][2]))
            if not fields:
                return ("TEXT_NOT_HELD", None), None
            refusal, pairs = _check_text(fields, text)
            if refusal is not None:
                return refusal, None
            plan["text"] = pairs
        return None, plan

    def _check_rows(self, dialog, rows):
        """2.31.0 (§4.3): each row is one the dialog offers and enables, the count is within its select, and
        for a purchase picker each count is within its caps (a count of 1 is the only count elsewhere).
        Returns (refusal, {"rows": [ids]} or {"counts": (def ids, object ids, counts)})."""
        select = observers.select_of(dialog)
        counts = observers.counts_of(dialog)
        # 2.31.0 (W4, F11): a purchase picker may carry counts and no select attributes, so the select bounds
        # apply only when the window has them. A window with neither is not one she can answer by rows.
        if select is None and counts is None:
            return ("NO_ROW", None), None
        offered = dict((item["option_id"], item) for item in observers._dialog_rows(dialog))
        options = [row["option_id"] for row in rows]
        if len(set(options)) != len(options) or any(option not in offered for option in options):
            return ("NO_ROW", None), None
        if any(not offered[option]["enabled"] for option in options):
            return ("ROW_DISABLED", None), None
        low, high = 1, ANSWER_ROWS_LIMIT
        if select is not None:
            # 2.31.0 (W4, F2): a max of 0 is no limit (the game's own meaning); the row limit alone applies.
            low, high = max(select["min"], 1), (select["max"] or ANSWER_ROWS_LIMIT)
        if not low <= len(rows) <= min(high, ANSWER_ROWS_LIMIT):
            return ("ROW_COUNT", None), None
        if counts is None:
            if any(row["count"] != 1 for row in rows):
                return ("COUNT_INVALID", None), None
            return None, {"rows": [int(option) for option in options]}
        if counts["max_rows"] and len(rows) > counts["max_rows"]:
            return ("COUNT_INVALID", None), None
        if any(counts["max_in_row"] and row["count"] > counts["max_in_row"] for row in rows):
            return ("COUNT_INVALID", None), None
        def_ids = [_def_id_of(dialog, option) for option in options]
        if any(def_id is None for def_id in def_ids):
            return ("NO_ROW", None), None
        # ASSUMPTION (not read from bytecode, confirm live): a purchase row has no object yet, so its
        # object id is sent as 0; pick_definitions_ids_and_counts only checks the three lists' lengths.
        return None, {"counts": (def_ids, [0] * len(rows), [row["count"] for row in rows])}

    def cmd_answer(self, act_id, dialog_id, pick, connection, rows=None, text=None):
        """2.18.0: answer a game dialog as she chose, the way the client does: pick the row
        (dialog_pick_result), then respond (dialog_respond). Once per act id.
        2.31.0 (§4.3, §4.4): rows (several, or counted for a purchase picker) and text fields are sent
        first, in the client's order (every text field, the rows, then dialog_respond). Her text is never
        logged: the act records only how many rows and fields she answered."""
        if act_id in self.act_ids:
            self._say(connection, "ACT_REJECT DUPLICATE")
            return False
        self.act_ids.add(act_id)
        base = {"object_id": dialog_id, "guid64": pick if pick.isdigit() else None}
        if not self.available():
            self._act_event(act_id, "REJECTED", code="E2_UNAVAILABLE", **base)
            self._say(connection, "ACT_REJECT E2_UNAVAILABLE")
            return False
        accepted = False
        try:
            refusal, bound = self._answer_check(dialog_id, pick, rows, text)
            if refusal is not None:
                code, detail = refusal
                self._act_event(act_id, "REJECTED", code=code,
                                detail=None if detail is None else str(detail)[:schema.MAX_DETAIL_LENGTH], **base)
                self._say(connection, "ACT_REJECT %s" % code)
                return False
            service, dialog, plan, response = bound
            kind = _tuning_name(dialog)
            key = str(int(dialog_id))
            # 2.39.0 (W12 A5): the hold leaves only once the answer is sent (below), never before.
            held = key in self.held
            self._act_event(act_id, "ACCEPTED", tuning_name=kind, **base)
            accepted = True
            if plan is not None:
                # 2.31.0 (§3.3): every text field, then the rows, then the response (the client's order).
                for name, value in plan["text"] or []:
                    service.dialog_text_input(int(dialog_id), name, value)
                if plan["counts"] is not None:
                    def_ids, object_ids, counts = plan["counts"]
                    service.dialog_pick_result_def_ids_and_counts(
                        int(dialog_id), def_ids, object_ids, counts, False)
                elif plan["rows"]:
                    service.dialog_pick_result(int(dialog_id), plan["rows"])
            service.dialog_respond(int(dialog_id), response)
            # 2.27.0: a held window was never on the User's screen; it is hers alone, and it leaves the hold now the
            # answer went (2.39.0, W12 A5: a failed send keeps it held for the fallback).
            self.held.pop(key, None)
            _note_window(key, held=False)
            # 2.23.0: dialog_respond already accepted. Closing the window and lifting the
            # pause are separate; a failure of either never turns the answer into a rejection.
            # Reviewed path: ui/ui_dialog_service._dialog_cancel_internal builds
            # Dialog_pb2.UiDialogCloseRequest and Distributor.add_event(
            # Consts_pb2.MSG_UI_DIALOG_CLOSE). immediate=True is add_event's own send.
            closed = False
            try:
                if Dialog_pb2 is not None and Consts_pb2 is not None and Distributor is not None:
                    message = Dialog_pb2.UiDialogCloseRequest()
                    message.dialog_id = dialog.dialog_id
                    distributor = Distributor.instance()
                    distributor.add_event(Consts_pb2.MSG_UI_DIALOG_CLOSE, message, immediate=True)
                    closed = True
            except Exception:
                closed = False
            resumed = "failed"
            try:
                prior = observers.dialog_prior_speed(dialog_id)
                others = [key for key in service._active_dialogs if int(key) != int(dialog_id)]
                current = observers._game_snapshot().get("clock_speed")
                if prior == "PAUSED":
                    resumed = "player_paused"
                elif others:
                    resumed = "other_dialog_open"
                elif current != "PAUSED":
                    resumed = "not_paused"
                elif ClockSpeedMode is None or GameSpeedChangeSource is None:
                    resumed = "failed"
                else:
                    # server_commands/clock_commands.unrequest_pause: pop the newest
                    # PAUSED request on UI_MODAL. A player pause is a different source.
                    clock = services.game_clock_service()
                    request = clock.pop_speed(
                        ClockSpeedMode.PAUSED, source=GameSpeedChangeSource.UI_MODAL, immediate=True)
                    if request is not None:
                        resumed = "released"
                    else:
                        # 2.39.0 (W12 A6): no UI_MODAL request is hers, so the pause in place is not her dialog's
                        # (the User's, or another mod's). The clock is left as it is; restoring the speed from before
                        # the dialog would lift the User's pause.
                        resumed = "not_hers"
            except Exception:
                resumed = "failed"
            _send_queued_events()
            # 2.39.0 (W12 A5): ANSWERED only when the window has closed. One still open is the User's now.
            still_open = _window_open(service, dialog_id)
            if still_open:
                _note_window(key, cause="user")
            answered = "ANSWER_SENT_OPEN" if still_open else "ANSWERED"
            # 2.31.0: an answer in the new shapes says how many rows and text fields she gave (counts only, never
            # her text). A single row or a button keeps the detail it always had.
            tokens = ["held"] if held else []
            if rows is not None or text is not None:
                shape = plan or {}
                tokens += (["counts %d" % len(shape["counts"][0])] if shape.get("counts") is not None else
                           (["rows %d" % len(shape["rows"])] if shape.get("rows") else []))
                tokens += ["text %d" % len(shape["text"])] if shape.get("text") else []
            self._act_event(act_id, "FINISHED", tuning_name=kind, finishing_type="ANSWERED", code=answered,
                            closed=closed, resumed=resumed,
                            detail=" ".join(tokens)[:schema.MAX_DETAIL_LENGTH] or None, **base)
            self._say(connection, "ACT_ANSWERED %s" % act_id)
            return True
        except Exception as error:
            code = ("E2_EXCEPTION:%s" % type(error).__name__)[:64]
            phase = "UNKNOWN" if accepted else "REJECTED"
            self._act_event(act_id, phase, code=code, **base)
            self._say(connection, "ACT_%s %s" % (phase, code))
            return False

    def cmd_cancel(self, act_id, interaction_id, connection):
        """2.20.0 (live 2026-10-06: her meal waited behind an open-ended piano song she had no
        way to stop): she stops one of her own actions, running or queued, the way the client's
        X does (interactions.cancel_si: find it on her Sim, or its continuation, then
        cancel_user). The game may refuse. Once per act id."""
        if act_id in self.act_ids:
            self._say(connection, "ACT_REJECT DUPLICATE")
            return False
        self.act_ids.add(act_id)
        base = {"object_id": interaction_id, "guid64": None}
        if not self.available():
            self._act_event(act_id, "REJECTED", code="E2_UNAVAILABLE", **base)
            self._say(connection, "ACT_REJECT E2_UNAVAILABLE")
            return False
        accepted = False
        try:
            refusal = None
            sim = None
            if self._state() != "SAMPLING":
                refusal = "NOT_SAMPLING"
            elif self.lineage_class == e2_lineage.BODY_MISMATCH:
                refusal = "BODY_MISMATCH"
            else:
                _sim_info, sim = observers.select_lab_body(
                    services.sim_info_manager().get_all(), observers.ALL_HIDDEN_REASONS)
                if sim is None:
                    refusal = "BODY_UNAVAILABLE"
            interaction = None
            if refusal is None:
                interaction = sim.find_interaction_by_id(int(interaction_id))
                if interaction is None:
                    interaction = sim.find_continuation_by_id(int(interaction_id))
                if interaction is None:
                    refusal = "NO_INTERACTION"
            if refusal is not None:
                self._act_event(act_id, "REJECTED", code=refusal, **base)
                self._say(connection, "ACT_REJECT %s" % refusal)
                return False
            tuning_name = _tuning_name(interaction)
            self._act_event(act_id, "ACCEPTED", tuning_name=tuning_name, **base)
            accepted = True
            if not interaction.cancel_user(cancel_reason_msg="Ashley stopped it."):
                self._act_event(act_id, "REJECTED", code="GAME_REFUSED", tuning_name=tuning_name, **base)
                self._say(connection, "ACT_REJECT GAME_REFUSED")
                return False
            self._act_event(act_id, "FINISHED", tuning_name=tuning_name, finishing_type="STOPPED", **base)
            self._say(connection, "ACT_STOPPED %s" % act_id)
            return True
        except Exception as error:
            code = ("E2_EXCEPTION:%s" % type(error).__name__)[:64]
            phase = "UNKNOWN" if accepted else "REJECTED"
            self._act_event(act_id, phase, code=code, **base)
            self._say(connection, "ACT_%s %s" % (phase, code))
            return False

    def cmd_camera(self, op, target_id, connection):
        """2.21.0 (E5): the overlay's camera director looks at her Sim (following) or at one
        object. It moves only the view: no act id, no act_event, nothing in her ledger. Refused
        unless sampling her own body, and at most one op per CAMERA_MIN_GAP_S."""
        if not self.available() or focus_on_sim is None or focus_on_object is None:
            self._say(connection, "CAMERA_REJECT UNAVAILABLE")
            return False
        if self._state() != "SAMPLING":
            self._say(connection, "CAMERA_REJECT NOT_SAMPLING")
            return False
        if self.lineage_class == e2_lineage.BODY_MISMATCH:
            self._say(connection, "CAMERA_REJECT BODY_MISMATCH")
            return False
        now = time.monotonic()
        if self._camera_at is not None and now - self._camera_at < CAMERA_MIN_GAP_S:
            self._say(connection, "CAMERA_REJECT TOO_SOON")
            return False
        try:
            if op in ("follow_sim", "unfollow"):
                sim_info = services.sim_info_manager().get(int(target_id))
                sim = sim_info.get_sim_instance() if sim_info is not None else None
                if sim is None:
                    self._say(connection, "CAMERA_REJECT NO_TARGET")
                    return False
                # 2.32.0 (HE14): unfollow looks at her Sim without following it (follow=False, the same call).
                focus_on_sim(sim=sim, follow=op == "follow_sim")
            else:
                obj = services.object_manager().get(int(target_id))
                if obj is None:
                    self._say(connection, "CAMERA_REJECT NO_TARGET")
                    return False
                focus_on_object(object=obj, follow=False)
            _send_queued_events()
            self._camera_at = now
            self._say(connection, "CAMERA_OK %s %s" % (op, target_id))
            return True
        except Exception as error:
            self._say(connection, ("CAMERA_REJECT E2_EXCEPTION:%s" % type(error).__name__)[:64])
            return False

    def cmd_talk(self, text, sim_id, connection):
        """2.26.0: one line of social talk, the plain sentence the helper made from the phrase data,
        shown to the User as the game's own notification (owner: the Sim it is about, when known).
        It only shows text: no act id, no act_event, nothing in her ledger. Refused unless sampling
        her own body, and at most one line each TALK_MIN_GAP_S."""
        if not self.available() or UiDialogNotification is None or LocalizationHelperTuning is None:
            self._say(connection, "TALK_REJECT UNAVAILABLE")
            return False
        if self._state() != "SAMPLING":
            self._say(connection, "TALK_REJECT NOT_SAMPLING")
            return False
        if self.lineage_class == e2_lineage.BODY_MISMATCH:
            self._say(connection, "TALK_REJECT BODY_MISMATCH")
            return False
        now = time.monotonic()
        if self._talk_at is not None and now - self._talk_at < TALK_MIN_GAP_S:
            self._say(connection, "TALK_REJECT TOO_SOON")
            return False
        try:
            owner = services.sim_info_manager().get(int(sim_id)) if sim_id is not None else None
            line = LocalizationHelperTuning.get_raw_text(text)
            notification = UiDialogNotification.TunableFactory().default(owner, text=lambda *_, **__: line)
            _note_own_notice(notification)  # 2.36.0 (D6, P2): marked before it is shown: never a notice about her
            notification.show_dialog()
            self._talk_at = now
            self._say(connection, "TALK_OK")
            return True
        except Exception as error:
            self._say(connection, ("TALK_REJECT E2_EXCEPTION:%s" % type(error).__name__)[:64])
            return False

    # ------------------------------------------------------------ windows (2.31.0)
    # ------------------------------------------------------------------ pace (2.31.0, W3p)
    def cmd_pace(self, need_drain, slow_time, connection):
        """2.31.0 (W3p): the helper's pace, two fractions of normal pace (1.0 is off). The probe keeps the last
        values for the session and applies them while she is sampling. Only the helper may send it."""
        try:
            issuer = connection.issuer
        except AttributeError:
            issuer = None
        if issuer != "helper":
            connection.code = "BAD_ISSUER"
            self._say(connection, "PACE_REJECT BAD_ISSUER")
            return False
        need, slow = _factor(need_drain), _factor(slow_time)
        if need is None or slow is None:
            connection.code = "BAD_ARGS"
            self._say(connection, "PACE_REJECT BAD_ARGS")
            return False
        self._pace = {"need_drain": need, "slow_time": slow}
        self._pace_apply()
        if (self._clock_foreign or self._clock_unreadable) and slow < PACE_NORMAL:
            # 2.31.0 (W4, F12): the clock is refused, not the drain: need_drain is applied, and the reply says so.
            reason = "CLOCK_UNREADABLE" if self._clock_unreadable else "CLOCK_FOREIGN"
            detail = ("the game clock could not be read" if self._clock_unreadable else
                      "another mod sets the game clock") + "; the probe leaves it alone"
            connection.code = reason
            self._speed_event(reason, detail=detail)
            self._say(connection, "PACE_REFUSED %s slow_time; need_drain %g applied" % (reason, need))
            return False
        self._say(connection, "PACE_OK need_drain %g slow_time %g" % (need, slow))
        return True

    def pace_row(self, row):
        """2.31.0 (W3p): called for each observation row before it is written. Checks her body (PR7), applies her
        pace for this moment, and returns the pace block the row carries: what the probe applied."""
        self._body_switch(row)
        self._pace_apply()
        return self.pace_block()

    def pace_block(self):
        """2.31.0 (W3p): the pace block of an observation row (schema PACE_KEYS). `drain_measured` is one
        motive's effective factor, get_decay_rate() over get_decay_rate(False), when its decay is running."""
        measured = None
        for item, _ in list(self._drained.values())[:1]:
            try:
                plain = item.get_decay_rate(False)
                if plain:
                    measured = _measure(item.get_decay_rate() / plain)
            except Exception:
                measured = None
        return {"need_drain": self._pace["need_drain"],
                "motives_modified": min(len(self._drained), schema.MAX_MOTIVES),
                "drain_measured": measured, "slow_time": self._pace["slow_time"],
                "clock_scale": self._clock_scale(), "clock_foreign": bool(self._clock_foreign),
                "clock_unreadable": bool(self._clock_unreadable)}

    def _pace_apply(self):
        """Her pace now: applied while she is live (sampling, not a body switch, the zone running), else undone."""
        live = self._live() and self._zone_running()
        self._pace_drain(live)
        self._pace_clock(live)

    def _pace_release(self):
        """Undo everything the probe changed for her pace: the modifiers and the clock (stop, disarm, arm)."""
        self._pace_drain(False)
        self._pace_clock(False)

    def _pace_drain(self, live):
        """Her motives drain at the wanted factor while live, each motive once (recorded by identity, so a second
        tick never stacks). The modifier comes off each recorded motive when the factor changes or she is not live;
        an entry whose motive left her tracker (travel or load rebuilt it) is dropped, and its new motive gets it."""
        if not live:
            self._undo_drain()
            return
        want = self._pace["need_drain"]
        motives = self._motives()
        if motives is None:
            self._undo_drain()
            return
        present = set(id(item) for item in motives)
        for key in [key for key in self._drained if key not in present]:
            del self._drained[key]
        if any(value != want for _, value in self._drained.values()):
            self._undo_drain()
        if want >= PACE_NORMAL:
            return
        for item in motives:
            if id(item) in self._drained:
                continue
            try:
                item.add_decay_rate_modifier(want)
            except Exception:
                continue
            self._drained[id(item)] = (item, want)
            try:
                item.send_commodity_progress_msg()
            except Exception:
                pass

    def _undo_drain(self):
        """Take the modifier off each recorded motive (the value it got), send its progress, empty the record."""
        for item, value in list(self._drained.values()):
            try:
                item.remove_decay_rate_modifier(value)
            except Exception:
                pass
            try:
                item.send_commodity_progress_msg()
            except Exception:
                pass
        self._drained.clear()

    def _motives(self):
        """Her motive commodities (the guids in observers.MOTIVE_GUIDS), from her body's commodity tracker.
        None when they cannot be read now."""
        try:
            sim_info, _ = observers.select_lab_body(
                services.sim_info_manager().get_all(), observers.ALL_HIDDEN_REASONS)
            commodities = list(sim_info.commodity_tracker.get_all_commodities())
        except Exception:
            return None
        return [item for item in commodities if observers._motive_guid(item) in observers.MOTIVE_GUIDS]

    def _pace_clock(self, live):
        """The game clock runs at the wanted scale while she is live: the class attribute is asserted on every tick,
        and the client is told when the value changes. Otherwise the value read at install comes back. A clock
        another mod owns, or one that cannot be read, is never touched."""
        if self._clock_foreign or game_clock is None:
            return
        want = self._pace["slow_time"]
        if live and want < PACE_NORMAL:
            self._set_clock(want)
            self._clock_applied = True
        elif self._clock_applied:
            self._set_clock(self._clock_base)
            self._clock_applied = False

    def _set_clock(self, value):
        try:
            before = game_clock.GameClock.NORMAL_SPEED_MULTIPLIER
            game_clock.GameClock.NORMAL_SPEED_MULTIPLIER = value
            if before != value:
                services.game_clock_service()._sync_clock_and_broadcast_gameclock()
        except Exception:
            pass

    def _clock_scale(self):
        try:
            return _measure(services.game_clock_service().current_clock_speed_scale())
        except Exception:
            return None

    def _zone_running(self):
        try:
            zone = services.current_zone()
            return zone is not None and bool(zone.is_zone_running)
        except Exception:
            return False

    def pass_by(self):
        """Every pass through a wrapper (a hook inside the distributor's own work) only drops held
        windows whose dialog is gone. It never sends: a window due for the User is shown from the probe
        tick or the real-time watchdog, at the top of the game loop (2.31.0 review fix). Never raises."""
        if self.held:
            try:
                self._drop_closed()
            except Exception:
                pass

    def _live(self):
        return self._state() == "SAMPLING" and self.lineage_class != e2_lineage.BODY_MISMATCH

    def hold_dialog(self, original, dialog, args, kwargs):
        """Route R1 (distribute_dialog, 2.27.0 for pickers, 2.31.0 for every window): True when the
        window is taken here, held for her or withheld. False: the original sends it, untouched."""
        self.pass_by()
        who = self._note_cause(dialog)
        if not self._live():
            # 2.39.0 (W12 A4): not sampling, so the window goes through to the User untouched; its cause says so.
            if who == "hers":
                _note_window(str(int(dialog.dialog_id)), cause="user", held=False)
            return False
        return self._window(original, dialog, (dialog,) + tuple(args), kwargs, "dialog")

    def hold_event(self, original, distributor, msg_id, args, kwargs):
        """Route R2 (her phone ring, held like a window) or R4 (a client screen by message)."""
        self.pass_by()
        if msg_id == _HOLD["ring"]:
            self._note_ring_cause(args, kwargs)
        if not self._live():
            return False
        if msg_id == _HOLD["ring"]:
            msg = args[1] if len(args) > 1 else kwargs.get("msg")
            dialog = services.ui_dialog_service()._active_dialogs.get(int(msg.dialog.dialog_id))
            if dialog is None:
                return False
            return self._window(original, dialog, (distributor,) + tuple(args), kwargs, "ring")
        return self._withhold_screen(_HOLD["screens"].get(msg_id))

    def withhold_op(self, name):
        """Route R5 (a client screen sent as an op, §3.1)."""
        self.pass_by()
        return self._live() and self._withhold_screen(name)

    def _note_cause(self, dialog):
        """2.31.0 (W4, F5): a window's cause is noted before the live check, so every window the hook sees has
        one, held or not. Never raises."""
        try:
            who, _act = self._window_owner(dialog)
            _note_window(str(int(dialog.dialog_id)), cause=who, held=False)
            return who
        except Exception:
            return None

    def _note_ring_cause(self, args, kwargs):
        """2.31.0 (W4, F5): the cause of her phone ring, noted before the live check. Never raises."""
        try:
            msg = args[1] if len(args) > 1 else kwargs.get("msg")
            self._note_cause(services.ui_dialog_service()._active_dialogs.get(int(msg.dialog.dialog_id)))
        except Exception:
            pass

    def _window(self, original, dialog, send_args, send_kwargs, kind):
        """The one decision for a dialog window or her phone ring (§4.1, §4.2, §4.3)."""
        who, act = self._window_owner(dialog)
        # 2.40.0 (W13 P1): an incoming call is held for her by its caller's sim id, not by the resolver's Sim.
        if kind == "ring" and who == "user" and self._ring_for_her(dialog):
            who, act = "hers", None
        name = type(dialog).__name__
        key = str(int(dialog.dialog_id))
        if who == "identity_user":
            _note_window(key, cause="identity_user", held=False)
            self._speed_event("DIALOG_SHOWN", code="IDENTITY_USER", detail=_window_detail(kind, key, None))
            return False
        if who != "hers":
            # 2.39.0 (W12 A10): a window that passes through to the User is recorded too.
            _note_window(key, cause="user", held=False)
            self._speed_event("DIALOG_SHOWN", code="PASS_THROUGH", detail=_window_detail(kind, key, None))
            return False
        names = _class_names(dialog)
        if names & WITHHELD_DIALOG_CLASSES:
            services.ui_dialog_service().dialog_cancel(int(dialog.dialog_id))
            self._withheld(act, name, kind)
            return True
        act_id = None if act is None else act["act_id"]
        if names & NOT_ANSWERABLE_CLASSES:
            _note_window(key, cause="user", held=False)
            # 2.31.0 (W4, F1): shown to the User at once, so a late answer to it is refused as shown.
            self._remember_shown(key)
            self._speed_event("DIALOG_SHOWN", code=("NOT_ANSWERABLE:%s" % name)[:schema.MAX_DETAIL_LENGTH],
                              detail=_window_detail(kind, key, act_id))
            return False
        self.held[key] = {"act_id": act_id, "at": time.monotonic(), "kind": kind,
                          "send": (original, send_args, send_kwargs)}
        # 2.31.0 (§11): the held message's text fields are read now, while the message is in hand.
        # 2.39.0 (W12 A9): held_until is when the fallback hands the window to the User (hold_left_s counts to it).
        _note_window(key, cause="hers", held=True, held_until=self.held[key]["at"] + PICKER_HOLD_S,
                     text_inputs=_read_text_fields(_held_message(kind, send_args, send_kwargs)))
        self._speed_event("DIALOG_HELD", detail=_window_detail(kind, key, act_id))
        self._arm_watchdog()
        return True

    def _withhold_screen(self, name):
        """R4/R5 (§4.5): a client screen her own act opened is not sent. Only her act's frame on the
        call stack makes it hers (§4.1 rule 1); anything else is the game's or the User's.
        2.34.0 (F1): while her act is being pushed (the mark), a screen is hers too, as a window is."""
        if name is None:
            return False
        if self.pushing is not None:
            self._withheld(self.pushing["act"], name, "screen")
            return True
        item = self._pushed_on_stack()
        if item is None:
            return False
        self._withheld(item, name, "screen")
        return True

    def _withheld(self, act, name, kind):
        """Her act records the window it opened and was not shown (UNKNOWN: the act's own finish
        still reports from the game's finish watch); a speed event names it."""
        if act is not None:
            # 2.39.0 (W12 B6): NOTED, not UNKNOWN: the act is not over (a screen cancelled, the act goes on). The
            # screen's name goes in the detail.
            self._act_event(act["act_id"], "NOTED", code="SCREEN_WITHHELD",
                            detail=("screen %s" % name)[:schema.MAX_DETAIL_LENGTH],
                            interaction_id=act["interaction_id"], tuning_name=act["tuning_name"],
                            **act["base"])
        act_id = None if act is None else act["act_id"]
        self._speed_event("SCREEN_WITHHELD", code=name[:schema.MAX_DETAIL_LENGTH],
                          detail=_window_detail(kind, "", act_id))

    def _window_owner(self, dialog):
        """§4.1 and Q3: (who, act), who "hers", "user" or "identity_user"; act is her pushed act's
        record or None. Any exception: ("user", None)."""
        try:
            return self._decide_window(dialog)
        except Exception:
            return "user", None

    def _decide_window(self, dialog):
        her = self._her_sim_id()
        pairs, commanded = self._stack_read()
        interactions = self._resolver_interactions(dialog)
        if self._identity_window(dialog, her, interactions, pairs):
            return "identity_user", None
        if pairs:
            return "hers", pairs[0][1]
        for interaction in interactions:
            item = self._pushed_for(interaction)
            if item is None:
                # 2.38.0 (W11 P1): a window whose interaction continues her pushed act (same group_id) is hers, with it.
                item = self._group_pushed_for(interaction)
            if item is not None:
                return "hers", item
        if self._pushing_window(dialog, her, interactions):
            return "hers", self.pushing["act"]
        if interactions:
            # 2.37.0 (W10 P1): the first interaction's source decides. On her Sim, every game source but a pie
            # menu or a hand at the controls is hers (her own script, reflex or cancel act); another Sim's is the User's.
            # 2.38.0 (W11 P1): a hand's SCRIPT_WITH_USER_INTENT on her Sim is hers within PUSH_SOURCE_S of her last push.
            first = interactions[0]
            source = _read(lambda: str(first.context.source))
            name = _interaction_source_name(source)
            if _same_id(_read(lambda: first.sim), her):
                if name in HER_INTERACTION_SOURCES:
                    return "hers", None
                if name == "SCRIPT_WITH_USER_INTENT" and self._pushed_recently():
                    return "hers", None
            return "user", None
        if commanded:
            return "user", None
        if _same_id(_read(lambda: dialog._owner()), her):
            return "hers", None
        return "user", None

    def _group_pushed_for(self, interaction):
        """2.38.0 (W11 P1): the record of her pushed act this interaction continues, by group_id, while the group is
        kept (GROUP_KEEP_S after her push); None otherwise. Never raises: a window that cannot be read is not hers by this."""
        try:
            if interaction is None or not self.pushed_groups:
                return None
            group = _read(lambda: interaction.group_id)
            entry = None if group is None else self.pushed_groups.get(str(group))
            if entry is None or time.monotonic() - entry["at"] > GROUP_KEEP_S:
                return None
            return entry["item"]
        except Exception:
            return None

    def _pushed_recently(self):
        """2.38.0 (W11 P1): an act was pushed for her less than PUSH_SOURCE_S ago. Never raises."""
        try:
            return self.last_push_at is not None and time.monotonic() - self.last_push_at < PUSH_SOURCE_S
        except Exception:
            return False

    def _keep_groups(self, item, interactions):
        """2.38.0 (W11 P1): the group_id of each interaction the push gave her (the act and its aliases) is kept with
        her act's record for GROUP_KEEP_S; entries past that are dropped. An interaction with no group is not kept.
        Never raises."""
        try:
            now = time.monotonic()
            for key in [key for key, entry in self.pushed_groups.items() if now - entry["at"] >= GROUP_KEEP_S]:
                self.pushed_groups.pop(key, None)
            for interaction in interactions:
                group = _read(lambda: interaction.group_id)
                if group is not None:
                    self.pushed_groups[str(group)] = {"item": item, "at": now}
        except Exception:
            pass

    def _pushing_window(self, dialog, her, interactions):
        """2.34.0 (F1): True while her act is being pushed and the window is about her Sim: its owner, its
        resolver's Sim, or an interaction's Sim is her. Identity is checked before this. Reads only."""
        if self.pushing is None or her is None:
            return False
        if _same_id(_read(lambda: dialog._owner()), her):
            return True
        resolver = dialog._resolver
        if _same_id(_read(lambda: resolver.sim_info), her) or _same_id(_read(lambda: resolver.sim), her):
            return True
        return any(_same_id(_read(lambda: interaction.sim), her) for interaction in interactions)

    def _identity_window(self, dialog, her, interactions, pairs):
        """§4.1 identity, checked before the rest: her own Sim renamed, retraited or re-personalised
        is always the User's (Q3). Naming a pet, a painting or a song is not identity."""
        if her is None:
            return False
        if ("SimPersonalityAssignmentDialog" in _class_names(dialog) and
                _same_id(_read(lambda: dialog._assignment_sim_info), her)):
            return True
        for candidate in list(interactions) + [obj for obj, _item in pairs]:
            if _class_names(candidate) & IDENTITY_CLASSES and _target_or_actor_is(candidate, her):
                return True
        return False

    def _resolver_interactions(self, dialog):
        """The dialog's resolver interaction and super interaction (event_testing/resolver), the
        present ones only. A dialog with no resolver raises, so it is not hers (the caller's "user")."""
        resolver = dialog._resolver
        if resolver is None:
            raise ValueError("no resolver")
        found = []
        for read in (lambda: resolver._interaction, lambda: resolver.super_interaction):
            value = _read(read)
            if value is not None:
                found.append(value)
        return found

    def _her_sim_id(self):
        sim_info, _sim = observers.select_lab_body(services.sim_info_manager().get_all(),
                                                   observers.ALL_HIDDEN_REASONS)
        return None if sim_info is None else str(sim_info.id)

    def _stack_read(self):
        """One read-only walk of the call stack, at most STACK_FRAME_LIMIT frames. Returns
        ([(obj, act record)] for each frame whose self is one of her pushed acts, and whether a
        sims4.commands handler is on the stack)."""
        pairs = []
        commanded = False
        frame = sys._getframe(1)
        for _count in range(STACK_FRAME_LIMIT):
            if frame is None:
                break
            try:
                code = frame.f_code
                if code.co_name == "invoke_command" and _is_commands_file(code.co_filename):
                    commanded = True
                if self.pushed:
                    obj = frame.f_locals.get("self")
                    item = self._pushed_for(obj)
                    if item is not None:
                        pairs.append((obj, item))
            except Exception:
                pass
            frame = frame.f_back
        return pairs, commanded

    def _pushed_on_stack(self):
        if not self.pushed:
            return None
        pairs, _commanded = self._stack_read()
        return pairs[0][1] if pairs else None

    def _pushed_for(self, obj):
        if obj is None or not self.pushed:
            return None
        key = _read(lambda: str(obj.id))
        return None if key is None else self.pushed.get(key)

    def _remember_shown(self, key):
        self.shown_to_user.append(key)
        if len(self.shown_to_user) > SHOWN_TO_USER_LIMIT:
            del self.shown_to_user[0]

    def _drop_closed(self):
        """A held window whose dialog is gone (answered, cancelled) is dropped. Nothing is sent here,
        so it is safe inside a hook (pass_by)."""
        if not self.held:
            return
        try:
            active = services.ui_dialog_service()._active_dialogs
        except Exception:
            return
        for key in list(self.held):
            if int(key) not in active:
                self._drop_held(key, "VANISHED")
        if not self.held:
            self._cancel_watchdog()

    def _drop_held(self, key, code):
        """2.31.0 (W4, F14): a held window leaves her hands unsent (it vanished, or the zone changed). Its speed
        event names the dialog and the act by id only, never its text. Never raises."""
        item = self.held.pop(key, None)
        if item is None:
            return
        _note_window(key, held=False)
        self._speed_event("DIALOG_DROPPED", code=code, detail=_window_detail(item["kind"], key, item["act_id"]))

    def _release_held(self, everything=False, code="TIMEOUT"):
        """2.27.0: a held window whose dialog is gone (answered, cancelled) is dropped; one still
        open after PICKER_HOLD_S, or at a stop, is shown to the User through its original send.
        2.31.0: the same for her phone ring; a window shown here is the User's from then on.
        Sends only from the probe tick (on_poll_row), the watchdog and arm/stop, never from a hook."""
        self._drop_closed()
        if self.held:
            now = time.monotonic()
            for key in list(self.held):
                # 2.31.0 (W4, F13): a window dropped meanwhile is skipped, never a KeyError.
                item = self.held.get(key)
                if item is None:
                    continue
                if not everything and now - item["at"] < PICKER_HOLD_S:
                    continue
                del self.held[key]
                # 2.39.0 (W12 A4): a window handed to the User is the User's: its cause says so.
                _note_window(key, held=False, cause="user")
                function, args, kwargs = item["send"]
                try:
                    function(*args, **kwargs)
                    shown = code
                    self._remember_shown(key)
                except Exception as error:
                    shown = ("FAILED:%s" % type(error).__name__)[:64]
                self._speed_event("DIALOG_SHOWN", code=shown,
                                  detail=_window_detail(item["kind"], key, item["act_id"]))
        if not self.held:
            self._cancel_watchdog()

    def _arm_watchdog(self):
        """2.31.0 (§4.6): one repeating real-time alarm while a window is held; it releases what is due."""
        if self._watchdog is not None or alarms is None or game_clock is None:
            return
        try:
            self._watchdog = alarms.add_alarm_real_time(
                owner=self._alarm_owner, time_span=game_clock.interval_in_real_seconds(WATCHDOG_TICK_S),
                callback=self._watchdog_tick, repeating=True, use_sleep_time=False, cross_zone=False)
        except Exception:
            self._watchdog = None

    def _watchdog_tick(self, _alarm_handle=None):
        """2.31.0 (§4.6): the real-time alarm may show a due window (the top of the game loop)."""
        try:
            self._release_held()
        except Exception:
            pass

    def _cancel_watchdog(self):
        handle, self._watchdog = self._watchdog, None
        if handle is None or alarms is None:
            return
        try:
            alarms.cancel_alarm(handle)
        except Exception:
            pass

    def _ui_modal_pauses(self):
        """UI_MODAL paused speed requests, read only: clock.GameClock.speed_controllers is a defaultdict
        of list-like _SpeedController by source, and .get never creates one."""
        controller = services.game_clock_service().speed_controllers.get(GameSpeedChangeSource.UI_MODAL)
        if controller is None:
            return []
        return [item for item in list(controller) if item.speed == ClockSpeedMode.PAUSED]

    def _check_modal(self):
        """Catch-all (§4.5, P28): a NEW UI_MODAL pause while her act runs, with no dialog open, is a
        screen nobody catalogued. Speed event UNKNOWN_SCREEN with the act's tuning name; nothing is closed."""
        try:
            requests = self._ui_modal_pauses()
            new = [item for item in requests if not any(item is seen for seen in self._modal_seen)]
            self._modal_seen = requests
            if not new or not self.pushed or not self._live():
                return
            if services.ui_dialog_service()._active_dialogs:
                return
            act = self._pushed_records()[-1]
            self._speed_event("UNKNOWN_SCREEN", code=str(act["tuning_name"])[:schema.MAX_DETAIL_LENGTH],
                              detail=("act %s" % act["act_id"])[:schema.MAX_DETAIL_LENGTH])
        except Exception:
            pass

    def _reconcile_pushed(self, row):
        """2.19.1 (live 2026-10-06: a quick meal pushed while she was in the bath never
        appeared in her queue and never finished, so she believed it was still waiting):
        a pushed act whose interaction is missing from her queue for LEFT_QUEUE_SAMPLES
        samples in a row, with no finish from the game, is UNKNOWN (LEFT_QUEUE): it is gone
        and nobody can tell how it ended. 2.28.0: an act is present when any of its ids is in
        her queue, so an alias that stays keeps the act; it is gone when none of them is."""
        if not self.pushed:
            return
        interactions = row.get("interactions") or {}
        observed = interactions.get("observed") or []
        present = set(str(entry.get("interaction_id")) for entry in observed if isinstance(entry, dict))
        # 2.32.0 (PR17): a truncated or incomplete queue read cannot show an act gone; it counts no miss.
        whole = interactions.get("queue_truncated") is not True and interactions.get("observation_complete") is not False
        for item in self._pushed_records():
            keys = self._pushed_keys(item)
            if any(key in present for key in keys):
                item["seen"], item["misses"], item["waiting"] = True, 0, False
                continue
            if not whole:
                continue
            # 2.39.0 (W12 A1): the game keeps a pushed act out of her queue while a window is open. Its record stays
            # (so its finish is kept), no miss is counted, and WAITING is written once for the wait.
            window = _open_window(row, self.held)
            if window is not None:
                item["misses"] = 0
                if not item.get("waiting"):
                    item["waiting"] = True
                    self._act_event(item["act_id"], "WAITING", code="WINDOW_OPEN",
                                    detail=("dialog %s" % window)[:schema.MAX_DETAIL_LENGTH],
                                    interaction_id=item["interaction_id"], tuning_name=item["tuning_name"],
                                    **item["base"])
                continue
            item["waiting"] = False
            item["misses"] += 1
            if item["misses"] < LEFT_QUEUE_SAMPLES:
                continue
            for key in keys:
                self.pushed.pop(key, None)
            self._act_event(item["act_id"], "UNKNOWN", code="LEFT_QUEUE",
                            interaction_id=item["interaction_id"],
                            tuning_name=item["tuning_name"],
                            detail="ran, then left" if item["seen"] else "never seen in her queue",
                            **item["base"])

    def _resolve_pushed(self, code):
        """2.31.0 (PR8, live 2026-10-08: pushed acts outlived a zone change and ended as LEFT_QUEUE): every
        act still pushed is UNKNOWN now, with code ZONE_CHANGE or LOADED, and nothing is left to sample."""
        for item in self._pushed_records():
            for key in self._pushed_keys(item):
                self.pushed.pop(key, None)
            detail = "the zone changed while it ran" if code == "ZONE_CHANGE" else "the save was loaded while it ran"
            self._act_event(item["act_id"], "UNKNOWN", code=code,
                            interaction_id=item["interaction_id"],
                            tuning_name=item["tuning_name"],
                            detail=detail[:schema.MAX_DETAIL_LENGTH], **item["base"])

    def _pushed_records(self):
        """2.28.0: each pushed act once, however many of its ids are tracked."""
        records = {}
        for item in self.pushed.values():
            records.setdefault(id(item), item)
        return list(records.values())

    def _pushed_keys(self, item):
        return [key for key, value in self.pushed.items() if value is item]

    def _push_mark(self, act):
        """2.34.0 (F1): the mark for one push of her act, set just before the push. act is her act's record (None
        for a sit or a trial). The caller clears it in a finally, so a push that raises leaves nothing marked."""
        self.pushing = {"act": act}

    def publish_spots(self, zone, spots):
        """2.35.0 (D3): the spots of a menu build that finished in this zone are the ones an act may name now."""
        self.spots, self.spots_zone = dict(spots), zone

    def publish_variants(self, zone, variants):
        """2.39.0 (W12 G1): the pie choices of the menu just written in this zone are the ones an act may name now."""
        self.variants, self.variants_zone = dict(variants), zone

    def variant_key(self, object_id, guid64, variant):
        """2.39.0 (W12 G1): the match key of a pie choice the menu of this zone showed, or None (VARIANT_GONE)."""
        if self.variants_zone is None or self._get_zone() is not self.variants_zone:
            return None
        return self.variants.get((str(object_id), str(guid64), variant))

    def _spot_of(self, object_id):
        """2.35.0 (D3): the spot the newest finished menu build gave this id, while she is in the zone it was found
        in; None otherwise (an id no build holds is an object id, which the game may not know either)."""
        if self.spots_zone is None or self._get_zone() is not self.spots_zone:
            return None
        return self.spots.get(str(object_id))

    def _watch_act(self, act_id, base, interaction_id, tuning_name, interaction, aliases=None):
        """2.28.0: the act is tracked under its returned interaction and under each alias (the
        interactions the push put in her queue, {id: interaction}). They share one record, so the
        first finish of any of them is the act's FINISHED, and it names the one that finished."""
        item = {"act_id": act_id, "base": base, "tuning_name": tuning_name,
                "interaction_id": interaction_id, "seen": False, "misses": 0, "waiting": False}
        self.pushed[interaction_id] = item
        watched = [(interaction_id, interaction)]
        for alias_id, alias in (aliases or {}).items():
            self.pushed[alias_id] = item
            watched.append((alias_id, alias))
        # 2.38.0 (W11 P1): her push is noted for the source rule, and each interaction it gave her keeps its group.
        self.last_push_at = time.monotonic()
        self._keep_groups(item, [watched_interaction for _id, watched_interaction in watched])
        for watched_id, watched_interaction in watched:
            self._watch_act_finish(item, watched_id, watched_interaction)

    def _watch_act_finish(self, item, watched_id, interaction):
        def _finished(finished_interaction):
            if self.pushed.get(watched_id) is not item:
                return  # already recorded as finished, or gone
            for key in self._pushed_keys(item):
                self.pushed.pop(key, None)
            try:
                finishing = str(finished_interaction.finishing_type)
            except Exception:
                finishing = "UNREADABLE"
            self._act_event(item["act_id"], "FINISHED", interaction_id=watched_id,
                            tuning_name=item["tuning_name"],
                            finishing_type=finishing[:schema.MAX_DISPLAY_TEXT_LENGTH],
                            started=e2_actuator.started(finished_interaction), **item["base"])

        try:
            e2_actuator.watch_finish(interaction, _finished)
        except Exception:
            return

    def _trial_view(self, object_id, guid64):
        view, sim, obj, _sit_offers, context = self._view(object_id)
        offers = []
        if obj is not None:
            offers = e2_actuator.offers_for(obj, context, guid64)
        excluded = bool(offers) and e2_actuator.excluded(offers[0]) is not None
        motives = []
        try:
            sim_info, _sim = observers.select_lab_body(
                services.sim_info_manager().get_all(), observers.ALL_HIDDEN_REASONS)
            motives = observers.read_motives(sim_info, view.get("ticks") or 0) or []
        except Exception:
            motives = []
        view["armed_name"] = self._armed_name()
        view["object_id"] = object_id
        view["excluded_ids"] = EXCLUDED_OBJECT_IDS
        view["own_open_ids"] = self.open_ids
        view["motives"] = motives
        view["tuning_name"] = _tuning_name(offers[0]) if offers else None
        view["food_route"] = e2_actuator.food_route(offers[0]) if offers else None
        view["object"] = {"exists": obj is not None, "offer_count": len(offers),
                          "excluded": excluded, "sit_offer_count": view["object"]["sit_offer_count"]}
        return view, sim, obj, offers, context

    def _food_control(self, pushed_ns):
        """Presence rows from the last 60 s before this push."""
        window = int(60 * 1e9)
        found = []
        for row in self.presence:
            mono = row.get("monotonic_ns")
            if type(mono) is int and 0 <= pushed_ns - mono <= window:
                found.append(row)
        return found

    def _watch_finish(self, experiment, interaction):
        def _finished(finished_interaction, _experiment=experiment):
            try:
                finishing = str(finished_interaction.finishing_type)
            except Exception:
                finishing = "UNREADABLE"
            mono = None
            if observers is not None:
                try:
                    mono = observers._monotonic_ns()
                except Exception:
                    mono = None
            _experiment.finish(finishing[:schema.MAX_DISPLAY_TEXT_LENGTH], mono)
            self._experiment_event("FINISHED_CALLBACK",
                                   experiment_id=_experiment.experiment_id,
                                   interaction_id=_experiment.interaction_id,
                                   finishing_type=_experiment.finishing_type,
                                   claims=dict(_experiment.claims))

        try:
            e2_actuator.watch_finish(interaction, _finished)
        except Exception:
            return

    def _close_experiment(self, experiment):
        experiment.close()
        self._emit_verdict(experiment)

    def _end_trial_action(self, experiment):
        """A25: a trial's own action does not outlive its verdict.

        A TV watch keeps running with autonomy off, so the next trial would be
        BODY_BUSY forever. Only the interaction this probe pushed is cancelled.
        """
        try:
            interaction = experiment.interaction_ref
        except AttributeError:
            interaction = None
        experiment.interaction_ref = None
        try:
            children = list(experiment.children)
        except AttributeError:
            children = []
        try:
            sim = experiment.sim_ref
        except AttributeError:
            sim = None
        if interaction is None and not children:
            return
        if (experiment.food_route or experiment.relief) and _food_hold(experiment):
            if _queued_never_started(experiment) and interaction is not None:
                try:
                    e2_actuator.cancel_own(interaction)
                except Exception:
                    pass
            self._experiment_event("TRIAL_CLEANUP", experiment_id=experiment.experiment_id,
                                   object_id=experiment.object_id,
                                   interaction_id=experiment.interaction_id,
                                   detail=("food_left_running" if experiment.food_route
                                           else "relief_left_running"))
            return
        if experiment.claims["FINISHED"] or interaction is None:
            result = "ALREADY_FINISHED" if interaction is None or experiment.claims["FINISHED"] else "CANCELLED"
        else:
            try:
                e2_actuator.cancel_own(interaction)
                result = "CANCELLED"
            except Exception as error:
                result = ("CANCEL_FAILED:%s" % type(error).__name__)[:schema.MAX_DETAIL_LENGTH]
        if interaction is None:
            result = "ALREADY_FINISHED"
        try:
            cancelled = e2_actuator.cancel_ids(sim, children)
        except Exception:
            cancelled = 0
        if cancelled:
            result = ("%s children=%d" % (result, cancelled))[:schema.MAX_DETAIL_LENGTH]
        self._experiment_event("TRIAL_CLEANUP", experiment_id=experiment.experiment_id,
                               object_id=experiment.object_id,
                               interaction_id=experiment.interaction_id, detail=result)

    def _emit_verdict(self, experiment):
        self.open_ids.discard(experiment.interaction_id)
        detail = ""
        if experiment.food_route:
            before, peak, after = _hunger_span(experiment)
            detail = "route=%s hunger=%s->%s->%s " % (
                experiment.food_route, before, peak, after)
        for motive_id in experiment.relief:
            # D26 (live sleep PASS said nothing about energy): a relief trial reports
            # what the cure did to the need it relieves.
            if motive_id == "hunger" and experiment.food_route:
                continue
            before, peak, after = _motive_span(experiment, motive_id)
            detail += "relief=%s %s=%s->%s->%s " % (motive_id, motive_id, before, peak, after)
        detail += "foreign_roots=%d incomplete_rows=%d continuation=%d mixers=%d family=%d" % (
            len(experiment.foreign_roots), experiment.incomplete_rows,
            len(experiment.continuation_entries), len(experiment.child_mixers),
            len(experiment.children))
        skip = set(experiment.relief)
        if experiment.food_route:
            skip.add("hunger")
        for motive_id, span in _risen(experiment, skip):
            # After the counts: if the detail is too long, these are cut first.
            detail += " rose=%s %s->%s->%s" % (
                motive_id, _num(span[0]), _num(span[1]), _num(span[2]))
        finishing = experiment.finishing_type
        natural = finishing == "FinishingType.NATURAL"
        user_cancel = finishing == "FinishingType.USER_CANCEL"
        if finishing is not None and not natural and not user_cancel:
            detail += " interrupted=%s" % finishing
        if (experiment.verdict == e2_registry.OUTCOME_UNKNOWN and
                not experiment.claims["STARTED"]):
            detail += " never_started=1"
        detail = detail[:schema.MAX_DETAIL_LENGTH]
        extra = {}
        card = experiment.card
        if card.get("card_class") in ("interaction", "need"):
            guid = card.get("affordance_guid64")
            extra["guid64"] = None if guid is None else str(guid)
            extra["card_class"] = card.get("card_class")
            try:
                tuning_name = experiment.tuning_name
            except AttributeError:
                tuning_name = None
            extra["tuning_name"] = tuning_name
            extra["ambiguous"] = list(experiment.ambiguous)[:16]
        self._experiment_event("VERDICT", experiment_id=experiment.experiment_id,
                               object_id=experiment.object_id,
                               interaction_id=experiment.interaction_id,
                               code=experiment.verdict, claims=dict(experiment.claims),
                               finishing_type=experiment.finishing_type, detail=detail,
                               **extra)
        self._end_trial_action(experiment)

    # ----------------------------------------------------------------- speed
    def cmd_pause(self, connection):
        if not self.available():
            self._say(connection, "E2_UNAVAILABLE")
            return False
        if self._state() != "SAMPLING":
            self._speed_event("REJECT", code="NOT_SAMPLING")
            self._say(connection, "PAUSE_REJECT NOT_SAMPLING")
            return False
        if self.pause_request is not None:
            self._speed_event("REJECT", code="ALREADY_REQUESTED")
            self._say(connection, "PAUSE_REJECT ALREADY_REQUESTED")
            return False
        try:
            self.pause_request = e2_actuator.push_pause()
        except Exception as error:
            self.pause_request = None
            self._speed_event("REJECT", code="E2_EXCEPTION:%s" % type(error).__name__)
            self._say(connection, "PAUSE_REJECT EXCEPTION")
            return False
        self._speed_event("REQUEST_PUSHED")
        self._say(connection, "PAUSE_REQUESTED")
        return True

    def cmd_release(self, connection):
        if self.pause_request is None:
            self._speed_event("REJECT", code="NO_REQUEST")
            self._say(connection, "RELEASE_REJECT NO_REQUEST")
            return False
        if not self._remove_request():
            self._speed_event("RELEASE_FAILED", code="REMOVE_FAILED")
            self._say(connection, "RELEASE_FAILED")
            return False
        self._speed_event("REQUEST_REMOVED")
        self._say(connection, "RELEASED")
        return True

    def _remove_request(self):
        try:
            e2_actuator.remove_pause(self.pause_request)
        except Exception:
            return False
        self.pause_request = None
        return True

    def _release_pause(self, reason):
        if self.pause_request is None:
            return
        if self._remove_request():
            self._speed_event("RELEASED_ON_DISARM" if reason == "DISARM" else
                              "RELEASED_ON_STOP", detail=reason)
        else:
            self._speed_event("RELEASE_FAILED", code="REMOVE_FAILED", detail=reason)
