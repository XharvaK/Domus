"""The only E2 module allowed to act on the game (plan E2 §4, §5).

Game thread only. Closed call allowlist enforced by tools/check_guards.py:
push_super_affordance, push_speed, remove_request,
register_on_finishing_callback, add_manual_save_complete_callback,
remove_manual_save_complete_callback, cancel (our own trial interaction only,
A25). Everything else here is a read.
"""

import services  # TARGET_BYTECODE 1.128: object_manager, game_clock_service, get_persistence_service.

from clock import ClockSpeedMode, GameSpeedChangeSource  # TARGET_BYTECODE 1.128.
from interactions.context import InteractionContext, QueueInsertStrategy  # TARGET_BYTECODE 1.128.
from interactions.interaction_finisher import FinishingType  # TARGET_BYTECODE 1.128.
from interactions.priority import Priority  # TARGET_BYTECODE 1.128.

from . import e2_trial

SIT_AFFORDANCE_GUID = 31564
PAUSE_REASON = "ashley_e2_pause"
RELEASE_REASON = "ashley_e2_release"
TRIAL_END_REASON = "ashley_e2_trial_end"


def build_context(sim):
    return InteractionContext(sim, InteractionContext.SOURCE_SCRIPT_WITH_USER_INTENT,
                              Priority.High, insert_strategy=QueueInsertStrategy.NEXT)


def find_object(object_id):
    """Read: the live object for an id, or None."""
    try:
        numeric = int(object_id)
    except (TypeError, ValueError):
        return None
    manager = services.object_manager()
    if manager is None:
        return None
    return manager.get(numeric)


def offered(obj, context, cap=64):
    """Read: what the object offers now, as a trial sees it (class-tuned and
    component-given, such as a served plate's eat). At most cap."""
    found = []
    for affordance in obj.super_affordances(context):
        if len(found) >= cap:
            break
        found.append(affordance)
    return found


def sit_offers(obj, context):
    """Read: sit affordances (guid64 31564) the object itself offers."""
    return offers_for(obj, context, SIT_AFFORDANCE_GUID)


def offers_for(obj, context, guid64):
    """Read: affordances the object offers whose guid64 equals the request."""
    wanted = int(guid64)
    offers = []
    for affordance in obj.super_affordances(context):
        try:
            if int(affordance.guid64) == wanted:
                offers.append(affordance)
        except (TypeError, ValueError, AttributeError):
            continue
    return offers


def food_route(affordance):
    """Dialog-free food push, or None. Order and catering stay excluded (A30)."""
    names = []
    for cls in _mro(affordance):
        try:
            names.append(cls.__name__)
        except Exception:
            continue
    if ("StartCraftingAutonomouslySuperInteraction" in names and
            "StartCraftingOrderAutonomouslySuperInteraction" not in names):
        return "auto_craft"
    try:
        low = str(affordance.__name__).lower()
    except Exception:
        low = ""
    if "AutonomousObjectPickerInteraction" in names:
        return "auto_pick"
    if "ObjectPickerInteraction" in names and ("leftover" in low or "snack" in low):
        return "auto_pick"
    return None


def excluded(affordance):
    """None when a parameter-free trial may push this affordance, else a reason.

    A30: a food route is still a picker class, but the push does not open a dialog.
    Social and deny-name checks still apply. Every other picker stays excluded.
    """
    if food_route(affordance) is None:
        for cls in _mro(affordance):
            try:
                if "Picker" in cls.__name__:
                    return "picker"
            except Exception:
                continue
    try:
        social = affordance.is_social
    except Exception:
        social = False
    if social is True:
        try:
            low = str(affordance.__name__).lower()
        except Exception:
            low = ""
        for part in e2_trial.SOCIAL_DENY_PARTS:
            if part in low:
                return "deny_name"
        return "social"
    try:
        low = str(affordance.__name__).lower()
    except Exception:
        low = ""
    for part in e2_trial.DENY_NAME_PARTS:
        if part in low:
            return "deny_name"
    return None


def act_excluded(affordance, person):
    """2.17.0: excluded() for her own acts. Toward another Sim (person), a social is how she
    greets, invites in or talks; pickers and deny names stay excluded. Toward an object,
    exactly excluded()."""
    try:
        low = str(affordance.__name__).lower()
    except Exception:
        low = ""
    if "piemenu" in low:
        # 2.19.1 (live 2026-10-06: fridge_GrabSnack_PieMenu was pushed and silently vanished):
        # a pie-menu picker lists its choices as pie entries the client sends back; a push
        # carries no choice and no dialog opens, so it is not an act she can complete.
        return "pie_picker"
    reason = excluded(affordance)
    if person and reason == "social":
        return None
    if reason == "picker":
        # 2.18.0: a picker opens a dialog; the dialog is hers to answer (cmd answer).
        return None
    return reason


def push_affordance(sim, obj, affordance, context):
    """Act: push exactly one affordance.

    Returns (interaction_or_None, detail, kind). kind is "refused" when the
    game's test_result failed (A28); that is not a broken push. A passed test
    with no interaction, or a result that has no test_result, stays a failure.
    """
    result = sim.push_super_affordance(affordance, obj, context)
    refusal = _refusal(result)
    if refusal is not None:
        return None, refusal, "refused"
    try:
        execute_result = result.execute_result
    except AttributeError:
        execute_result = None
    if not result or execute_result is None:
        # EnqueueResult.interaction would raise here (TARGET_BYTECODE); never touch it.
        return None, _bounded(repr(result)), "failed"
    try:
        interaction = execute_result.interaction
    except AttributeError:
        interaction = None
    if interaction is None:
        return None, _bounded(repr(execute_result)), "failed"
    return interaction, None, None


def user_directed(affordance):
    """Read: a player could choose this affordance (8f: her menu and her acts)."""
    try:
        value = affordance.allow_user_directed
    except AttributeError:
        return False
    return value is True


def push_sit(sim, obj, affordance, context):
    """Act: push exactly one admitted sit. Returns (interaction_or_None, detail)."""
    interaction, detail, _kind = push_affordance(sim, obj, affordance, context)
    return interaction, detail


def preflight_test(sim, obj, affordance, context):
    """Read: would push_super_affordance's test refuse this pair (A28).

    Same arguments as the push. The game method calls AffordanceObjectPair.test
    and does not execute. Returns (ok, reason).
    """
    result = sim.test_super_affordance(affordance, obj, context)
    if not result:
        return False, _bounded(str(result))
    return True, None


def cancel_own(interaction):
    """Act: end the trial interaction this probe pushed, after its verdict (A25).

    Callers pass only the interaction returned by our own push; never any other.
    """
    interaction.cancel(FinishingType.USER_CANCEL, cancel_reason_msg=TRIAL_END_REASON)


def cancel_ids(sim, interaction_ids):
    """Act: end child interactions of our trial that are still on the Sim (A27).

    Callers pass only ids this probe classified as children of its own push.
    """
    if sim is None or not interaction_ids:
        return 0
    wanted = set(str(item) for item in interaction_ids)
    pools = []
    try:
        pools.extend(sim.queue or ())
    except Exception:
        pass
    try:
        pools.extend(sim.si_state or ())
    except Exception:
        pass
    seen = set()
    count = 0
    for entry in pools:
        try:
            iid = str(entry.id)
        except Exception:
            continue
        if iid not in wanted or iid in seen:
            continue
        seen.add(iid)
        entry.cancel(FinishingType.USER_CANCEL, cancel_reason_msg=TRIAL_END_REASON)
        count += 1
    return count


def _refusal(result):
    """Bounded test_result text when the game refused the push, else None."""
    try:
        test_result = result.test_result
    except AttributeError:
        return None
    if test_result:
        return None
    return _bounded(str(test_result))


def watch_finish(interaction, callback):
    """Act (callback registration on our own interaction only)."""
    interaction.register_on_finishing_callback(callback)


def push_pause():
    clock = services.game_clock_service()
    return clock.push_speed(ClockSpeedMode.PAUSED, source=GameSpeedChangeSource.GAMEPLAY,
                            reason=PAUSE_REASON)


def remove_pause(request):
    clock = services.game_clock_service()
    clock.remove_request(request, source=GameSpeedChangeSource.GAMEPLAY,
                         reason=RELEASE_REASON)


def subscribe_saves(callback):
    services.get_persistence_service().add_manual_save_complete_callback(callback)


def unsubscribe_saves(callback):
    services.get_persistence_service().remove_manual_save_complete_callback(callback)


def _bounded(text):
    return str(text)[:128]


def _mro(affordance):
    target = affordance if isinstance(affordance, type) else type(affordance)
    try:
        return target.mro()
    except Exception:
        return ()
