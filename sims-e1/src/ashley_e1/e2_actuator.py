"""The only E2 module allowed to act on the game (plan E2 §4, §5).

Game thread only. Closed call allowlist enforced by tools/check_guards.py:
push_super_affordance, push_speed, remove_request,
register_on_finishing_callback, add_manual_save_complete_callback,
remove_manual_save_complete_callback. Everything else here is a read.
"""

import services  # TARGET_BYTECODE 1.128: object_manager, game_clock_service, get_persistence_service.

from clock import ClockSpeedMode, GameSpeedChangeSource  # TARGET_BYTECODE 1.128.
from interactions.context import InteractionContext, QueueInsertStrategy  # TARGET_BYTECODE 1.128.
from interactions.priority import Priority  # TARGET_BYTECODE 1.128.

from . import e2_trial

SIT_AFFORDANCE_GUID = 31564
PAUSE_REASON = "ashley_e2_pause"
RELEASE_REASON = "ashley_e2_release"


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


def excluded(affordance):
    """None when a parameter-free trial may push this affordance, else a reason."""
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
        return "social"
    try:
        low = str(affordance.__name__).lower()
    except Exception:
        low = ""
    for part in e2_trial.DENY_NAME_PARTS:
        if part in low:
            return "deny_name"
    return None


def push_affordance(sim, obj, affordance, context):
    """Act: push exactly one affordance. Returns (interaction_or_None, detail)."""
    result = sim.push_super_affordance(affordance, obj, context)
    try:
        execute_result = result.execute_result
    except AttributeError:
        execute_result = None
    if not result or execute_result is None:
        # EnqueueResult.interaction would raise here (TARGET_BYTECODE); never touch it.
        return None, _bounded(repr(result))
    try:
        interaction = execute_result.interaction
    except AttributeError:
        interaction = None
    if interaction is None:
        return None, _bounded(repr(execute_result))
    return interaction, None


def push_sit(sim, obj, affordance, context):
    """Act: push exactly one admitted sit. Returns (interaction_or_None, detail)."""
    return push_affordance(sim, obj, affordance, context)


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
