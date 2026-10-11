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
from . import observers

# 2.35.0 (D3): going places. The game's Go Here (terrain-gohere) and its standable-spot search. Read from the game's
# own code offline (no install is read here); each name is optional, so a missing one turns spots off and nothing
# else (PRIOR_ART|RUNTIME_UNVERIFIED).
try:
    from objects.terrain import TerrainPoint
except ImportError:
    TerrainPoint = None
try:
    from sims4.math import Location, Transform, Vector3
except ImportError:
    Location = Transform = Vector3 = None
try:
    import placement
except ImportError:
    placement = None
try:
    from build_buy import get_room_id, is_location_pool
except ImportError:
    get_room_id = is_location_pool = None
try:
    from interactions.context import PickInfo, PickType
except ImportError:
    PickInfo = PickType = None

SIT_AFFORDANCE_GUID = 31564
PAUSE_REASON = "ashley_e2_pause"
RELEASE_REASON = "ashley_e2_release"
TRIAL_END_REASON = "ashley_e2_trial_end"
# 2.35.0 (D3): the tuning name of the game's Go Here, its class, and how far in front of the front door a spot starts.
GO_HERE_NAME = "terrain-gohere"
GO_HERE_CLASS = "GoHereSuperInteraction"
FRONT_DOOR_STEP_M = 1.0


def build_context(sim, owner=False, pick=None):
    """2.24.0: an act her Thought marked as asked for by the User goes in at Critical, so a
    reflex at High queues behind it instead of displacing it; every other act stays High.
    2.35.0 (D3): a Go Here act carries the game's pick (pick=PickInfo), as the game's own Go Here does."""
    extra = {} if pick is None else {"pick": pick}
    return InteractionContext(sim, InteractionContext.SOURCE_SCRIPT_WITH_USER_INTENT,
                              Priority.Critical if owner else Priority.High,
                              insert_strategy=QueueInsertStrategy.NEXT, **extra)


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


# 2.29.0: her own phone. The game keeps a Sim's phone acts in her own list (`_phone_affordances`,
# which Sim.potential_phone_interactions reads), and their target is her own Sim. Leaving the lot
# changes zones, so a phone act that travels is not offered in this version.
# 2.37.0 (W10 P3): 256 (was 64), so the menu's own phone cap (act_menu.PHONE_CANDIDATES) is the one that binds.
PHONE_SCAN_LIMIT = 256
PHONE_TRAVEL_PARTS = ("travel", "goto", "visitlot", "mappicker", "inviteto", "askon", "vacation",
                      "lodging")
# 2.29.0: her phone is how she calls, texts and invites people over, so the blanket name bans that
# kept every phone act out (call_, phone_call, invite, social) do not apply to it. What still stays
# out by name: testers' acts, money, jobs, emergencies and the acts that change a life in one click.
# 2.37.1 (User 2026-10-12): only testers' and cheat acts stay out by name, and acts not meant for a player's
# hand (autonomous, npc); money, jobs, family and the rest are hers to choose.
# 2.31.0 (W4): whole words (e2_trial.denied_part), so the plural and -ing forms and the two-word forms
# stay listed where the old substring match caught them.
PHONE_DENY_PARTS = ("debug", "cheat", "cheats", "cheating", "testing", "tutorial", "autonomous", "npc")


def phone_affordances(sim):
    """Read: the phone affordances her Sim carries, at most PHONE_SCAN_LIMIT. Never raises."""
    listed = []
    try:
        for affordance in sim._phone_affordances or ():
            if len(listed) >= PHONE_SCAN_LIMIT:
                break
            listed.append(affordance)
    except Exception:
        pass
    return listed


def phone_offers_for(sim, guid64):
    """Read: her phone affordances whose guid64 equals the request. An act on her own Sim is
    offered by her phone and by nothing else."""
    wanted = int(guid64)
    offers = []
    for affordance in phone_affordances(sim):
        try:
            if int(affordance.guid64) == wanted:
                offers.append(affordance)
        except (TypeError, ValueError, AttributeError):
            continue
    return offers


def phone_act_excluded(affordance):
    """2.29.0: None when a phone act may be on her menu, else a reason. Pickers (who to call,
    text or invite) are hers to answer and socials are what a phone is for; a pie menu, a trip
    off the lot, and the PHONE_DENY_PARTS names stay out."""
    try:
        name = str(affordance.__name__)
    except Exception:
        name = ""
    if "piemenu" in name.lower().replace("_", ""):
        return "pie_picker"
    if e2_trial.denied_part(name, PHONE_DENY_PARTS) is not None:
        return "deny_name"
    return phone_excluded(affordance)


def phone_excluded(affordance):
    """2.29.0: None, or "travel" when the phone act would take her off the lot. Its class or
    tuning name, read down the class MRO as food_route reads it, says travel, go to, or visit a
    lot (underscores and spaces ignored, so go_to and GoTo both match)."""
    names = []
    for cls in _mro(affordance):
        try:
            names.append(cls.__name__)
        except Exception:
            continue
    try:
        names.append(affordance.__name__)
    except Exception:
        pass
    for name in names:
        low = str(name).lower().replace("_", "").replace(" ", "")
        if any(part in low for part in PHONE_TRAVEL_PARTS):
            return "travel"
    return None


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
            name = str(affordance.__name__)
        except Exception:
            name = ""
        if e2_trial.denied_part(name, e2_trial.SOCIAL_DENY_PARTS) is not None:
            return "deny_name"
        return "social"
    try:
        name = str(affordance.__name__)
    except Exception:
        name = ""
    # 2.31.0 (PR9): whole name words, not substrings ("kill" is not in "Skill").
    if e2_trial.denied_name(name) is not None:
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
    interaction, detail, kind, _reason_key = push_affordance_ex(sim, obj, affordance, context)
    return interaction, detail, kind


def push_affordance_ex(sim, obj, affordance, context):
    """push_affordance plus the refusal tooltip's string key, or None.

    The tooltip is never called. Callers that only need the triple use push_affordance.
    """
    result = sim.push_super_affordance(affordance, obj, context)
    refusal = _refusal(result)
    if refusal is not None:
        try:
            test_result = result.test_result
        except Exception:
            test_result = None
        return None, refusal, "refused", refusal_key(test_result)
    try:
        execute_result = result.execute_result
    except AttributeError:
        execute_result = None
    if not result or execute_result is None:
        # EnqueueResult.interaction would raise here (TARGET_BYTECODE); never touch it.
        return None, _bounded(repr(result)), "failed", None
    try:
        interaction = execute_result.interaction
    except AttributeError:
        interaction = None
    if interaction is None:
        return None, _bounded(repr(execute_result)), "failed", None
    return interaction, None, None, None


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
    and does not execute. Returns (ok, reason, reason_key). reason_key is the
    tooltip's string key when the test refuses, else None. The tooltip is never called.
    """
    result = sim.test_super_affordance(affordance, obj, context)
    if not result:
        return False, _bounded(str(result)), refusal_key(result)
    return True, None, None


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


def refusal_key(test_result):
    """Decimal string key of a refusal tooltip, or None.

    A tuned factory carries `_string_id`. A lambda that closes over a factory or a
    key is read from its closure cells. The tooltip is never called. Any failure
    is no key.
    """
    try:
        tooltip = test_result.tooltip
    except Exception:
        return None
    if tooltip is None:
        return None
    try:
        key = observers._string_key(tooltip)
        if key is None:
            key = observers._closure_key(tooltip)
    except Exception:
        return None
    return key


def _refusal(result):
    """Bounded test_result text when the game refused the push, else None."""
    try:
        test_result = result.test_result
    except AttributeError:
        return None
    if test_result:
        return None
    return _bounded(str(test_result))


def started(interaction):
    """Read: True when the game began performing the interaction (its start time is set only
    then), False when it ended before it ever started, None when unreadable."""
    try:
        return interaction.start_time is not None
    except Exception:
        return None


# 2.38.0 (W11 P2): a portal's class names (the menu's fixture rule reads "door" and "gate" too).
PORTAL_PARTS = ("door", "gate", "archway")


def is_portal(obj):
    """Read: whether the object is a door, gate or archway, by its class name. False when unreadable."""
    try:
        name = type(obj).__name__.lower()
    except Exception:
        return False
    return any(part in name for part in PORTAL_PARTS)


def reachable(sim, obj):
    """Read: whether the game sees a way from her to the object, by the check its own autonomy
    makes before it picks one (autonomy_request._check_object_connectivity_and_rules calls
    ScriptObject.is_connected). True, False, or None when unreadable.
    2.38.0 (W11 P2, live 2026-10-12: every door read False, the front door and both double doors too, while a chair
    46 m away read True): the check does not give a door a way, so a portal never reads False. True when the game
    says so, else None (unknown). No probe API reads a way to a portal's side, so none is computed."""
    try:
        value = obj.is_connected(sim)
    except Exception:
        return None
    if is_portal(obj):
        return True if value is True else None
    return value if type(value) is bool else None


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


# 2.35.0 (D3): going places. A spot is a standable point the game's own search finds near a position for her Sim;
# Go Here takes her there, as a player's click does, with the game's own pick. Every function here is a read.

def terrain_object():
    """Read: the lot's terrain object, which offers Go Here, or None."""
    try:
        return services.terrain_service.terrain_object()
    except Exception:
        return None


def front_door():
    """Read: the game's front door object, or None when the lot has none."""
    try:
        return services.get_door_service().get_front_door()
    except Exception:
        return None


def spot_start(obj, kind, side=1.0):
    """Read: where the game's standable search starts for a spot. A room's spot starts at the object's own position
    (the search finds free ground near it); the front door's starts one metre from it, along its forward axis on the
    given side (+1 forward, -1 behind): the caller picks the side that is outdoors, since a door may face either way.
    None when it cannot be read."""
    try:
        position = obj.position
        if kind == "front_door":
            forward = obj.forward
            step = FRONT_DOOR_STEP_M * side
            return Vector3(position.x + forward.x * step, position.y, position.z + forward.z * step)
        return position
    except Exception:
        return None


def standable_spot(sim, start, routing_surface):
    """Read: the game's own standable spot for her Sim near start (placement.find_good_location), as
    (position, orientation); None when the game finds none, or the search cannot be run."""
    if placement is None or start is None:
        return None
    try:
        starting = placement.create_starting_location(position=start, routing_surface=routing_surface)
        context = placement.create_fgl_context_for_sim(starting, sim)
        # The game returns (position, orientation, reason); position is None when nothing was found.
        found = placement.find_good_location(context)
        position, orientation = found[0], found[1]
    except Exception:
        return None
    return None if position is None else (position, orientation)


def room_at(obj, position, level):
    """Read: the room id at a position on a level, by the game's own lookup (build_buy.get_room_id), as a string;
    None when unknown."""
    if get_room_id is None:
        return None
    try:
        room = get_room_id(obj.zone_id, position, level)
    except Exception:
        return None
    if isinstance(room, bool) or not isinstance(room, int):
        return None
    return str(room)


def is_go_here(affordance):
    """Read: whether an affordance is the game's Go Here: tuning name terrain-gohere, or class GoHereSuperInteraction."""
    try:
        name = affordance.__name__
    except Exception:
        name = ""
    if name == GO_HERE_NAME:
        return True
    return any(_class_name(cls) == GO_HERE_CLASS for cls in _mro(affordance))


def _class_name(cls):
    try:
        return cls.__name__
    except Exception:
        return ""


def go_here_offered(terrain, context):
    """Read: the terrain's Go Here affordances that this context offers (a spot's context carries its pick)."""
    return [affordance for affordance in terrain.super_affordances(context) if is_go_here(affordance)]


def spot_offers_for(terrain, context, guid64):
    """Read: the terrain's Go Here affordances with this guid64, as the context offers them (an act's request)."""
    if terrain is None:
        return []
    return [affordance for affordance in offers_for(terrain, context, guid64) if is_go_here(affordance)]


def go_here_target(spot):
    """2.35.0 (D3): the point Go Here targets (a TerrainPoint of a Location at the spot) and the pick the game's own
    Go Here context carries: PICK_TERRAIN, or PICK_POOL_SURFACE when the spot is in a pool. (None, None) when a game
    name is missing or the spot cannot be made into a target."""
    if any(name is None for name in (TerrainPoint, Location, Transform, PickInfo, PickType)):
        return None, None
    try:
        position, level, surface = spot["position"], spot["level"], spot["routing_surface"]
        point = TerrainPoint(Location(Transform(position, spot["orientation"]), surface))
        pool = is_location_pool(position, level) is True
        pick = PickInfo(pick_type=PickType.PICK_POOL_SURFACE if pool else PickType.PICK_TERRAIN,
                        target=point, location=position, routing_surface=surface)
    except Exception:
        return None, None
    return point, pick


def spot_target(sim, spot, owner=False):
    """2.35.0 (D3): the target of Go Here at a spot and the act's context (the normal act context with the spot's
    pick); (None, None) when the spot cannot be made into a target."""
    point, pick = go_here_target(spot)
    if point is None:
        return None, None
    return point, build_context(sim, owner=owner, pick=pick)
