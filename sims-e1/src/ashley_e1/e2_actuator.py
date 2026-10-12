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
from . import reach
from . import tuned

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
# 2.40.0 (W13 P1): her trip, a planned event, and the situation's guest list. Each name is optional: a missing one
# turns its verb off and nothing else (RUNTIME_UNVERIFIED until the discovery record is read in a live session).
try:
    from world.travel_service import travel_sim_to_zone
except ImportError:
    travel_sim_to_zone = None
try:
    from situations.situation_guest_list import SituationGuestInfo, SituationGuestList, SituationInvitationPurpose
except ImportError:
    SituationGuestInfo = SituationGuestList = SituationInvitationPurpose = None
try:
    from sims4.resources import Types as ResourceTypes
except ImportError:
    ResourceTypes = None
try:
    from date_and_time import create_date_and_time
except ImportError:
    create_date_and_time = None

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
    # 2.40.0 (W13 P1): a phone act that asks for a Sim (needs_sim) is listed, and the Sim is picked by her.
    if "piemenu" in name.lower().replace("_", "") and not needs_sim(affordance):
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


def push_affordance_ex(sim, obj, affordance, context, parameters=None):
    """push_affordance plus the refusal tooltip's string key, or None.

    The tooltip is never called. Callers that only need the triple use push_affordance.
    2.40.0 (W13 P1): parameters are the interaction parameters of a Sim picker (picked_item_ids, included_override),
    passed as the push's keyword arguments, as the game's own picker is pushed. None for every other act.
    """
    if parameters:
        result = sim.push_super_affordance(affordance, obj, context, **parameters)
    else:
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


def preflight_test(sim, obj, affordance, context, parameters=None):
    """Read: would push_super_affordance's test refuse this pair (A28).

    Same arguments as the push. The game method calls AffordanceObjectPair.test
    and does not execute. Returns (ok, reason, reason_key). reason_key is the
    tooltip's string key when the test refuses, else None. The tooltip is never called.
    2.40.0 (W13 P1): parameters as push_affordance_ex takes them (a Sim picker's picked Sim).
    """
    if parameters:
        result = sim.test_super_affordance(affordance, obj, context, **parameters)
    else:
        result = sim.test_super_affordance(affordance, obj, context)
    if not result:
        return False, _bounded(str(result)), refusal_key(result)
    return True, None, None


# 2.40.0 (W13 P1): her reach. A phone act that asks for a Sim (a call, a text, an invite) is a picker: the Sim she
# names is the picker's own parameter (picked_item_ids, included_override), so the game's picker takes her choice.
# Her trip and her planned event are the game's own travel and situation calls. Every function here is a read,
# except travel, create_event and charge, which are the actuator's own effect calls.
SIM_PICKER_CLASSES = ("SimPickerInteraction", "SimPickerMixin")


def needs_sim(affordance):
    """Read: True when the affordance opens a Sim picker (its class, read down the MRO, is a Sim picker)."""
    return any(_class_name(cls) in SIM_PICKER_CLASSES for cls in _mro(affordance))


def picker_parameters(sim_info, sim_id):
    """2.40.0: the interaction parameters that make a Sim picker choose this Sim (picked_item_ids, included_override,
    as the game's picker reads them), or None when the Sim cannot be named."""
    if sim_info is None:
        return None
    try:
        return {"picked_item_ids": frozenset((int(sim_id),)), "included_override": [sim_info]}
    except (TypeError, ValueError):
        return None


def picker_offers(affordance, target, context):
    """Read: whether the picker has any Sim it could choose now (its has_valid_choice). True or False; None when unread."""
    try:
        return bool(affordance.has_valid_choice(target, context))
    except Exception:
        return None


def sim_info_for(sim_id):
    """Read: the sim info with this id, or None."""
    try:
        return services.sim_info_manager().get(int(sim_id))
    except Exception:
        return None


def travel(sim_id, zone_id):
    """Act: her trip, asked of the game's travel service (the game's own travel call, which asks the client to travel).
    True when the call went through, False when it raised, None when the game's call is not there."""
    if travel_sim_to_zone is None:
        return None
    try:
        travel_sim_to_zone(int(sim_id), int(zone_id))
    except Exception:
        return False
    return True


def situation_type(guid64):
    """Read: the situation type with this guid64 (its tuning), or None."""
    if ResourceTypes is None:
        return None
    try:
        return services.get_instance_manager(ResourceTypes.SITUATION).get(int(guid64))
    except Exception:
        return None


def default_job(situation):
    """Read: the job a guest of this situation type takes (its default job), or None."""
    try:
        return situation.default_job()
    except Exception:
        return None


def event_guest_list(host_sim_id, guest_ids, job_type):
    """Read: a guest list with her as host and the guests invited (SituationGuestInfo.construct_from_purpose), or None
    when the game's names are missing or the list cannot be made."""
    if None in (SituationGuestList, SituationGuestInfo, SituationInvitationPurpose) or job_type is None:
        return None
    try:
        guest_list = SituationGuestList(True, int(host_sim_id), None)
        for sim_id in [host_sim_id] + list(guest_ids):
            guest_list.add_guest_info(SituationGuestInfo.construct_from_purpose(
                int(sim_id), job_type, SituationInvitationPurpose.INVITED))
    except Exception:
        return None
    return guest_list


def create_event(zone_id, situation, guest_list, scheduled_time=None):
    """Act: the zone's situation manager makes the event she planned, user-facing, at scheduled_time (None: now).
    Returns the new situation's id (digits), or None when the game made none."""
    try:
        manager = services.get_zone_situation_manager(int(zone_id))
        created = manager.create_situation(situation, guest_list, user_facing=True, zone_id=int(zone_id),
                                           scheduled_time=scheduled_time)
        found = created.id
    except Exception:
        return None
    return None if found is None else str(found)


def funds_of(household):
    """Read: the household's funds object, or None."""
    try:
        return household.funds
    except Exception:
        return None


def charge(household, amount, sim, reason):
    """Act: the household's funds pay amount, all of it or nothing (the game's own try_remove). True when paid, False
    when the funds cannot pay, None when the call itself failed (the funds are unread, so nothing is known)."""
    try:
        paid = funds_of(household).try_remove(amount, reason, sim, require_full_amount=True)
    except Exception:
        return None
    return bool(paid)


def situation_cost(situation):
    """Read: a situation type's cost (its tuned cost, an int), or None when unread."""
    cost = tuned._class_plain(situation, "cost")
    return cost if type(cost) is int and cost >= 0 else None


def now_absolute_minutes():
    """Read: the game's clock now, in absolute minutes (DateAndTime.absolute_minutes of the time service's sim_now);
    None when unread."""
    try:
        value = services.time_service().sim_now.absolute_minutes()
    except Exception:
        return None
    return value if type(value) is int else None


def scheduled_at(absolute_minutes):
    """Read: the game's date and time for an absolute minute (date_and_time.create_date_and_time from its days, hours and
    minutes); None when the game's call is missing or fails."""
    if create_date_and_time is None or absolute_minutes is None:
        return None
    try:
        return create_date_and_time(absolute_minutes // 1440, (absolute_minutes % 1440) // 60, absolute_minutes % 60)
    except Exception:
        return None


def refund(household, amount, sim, reason):
    """Act: the money a charge took goes back to the household's funds (the game's own add), when a later step failed."""
    try:
        funds_of(household).add(amount, reason, sim)
    except Exception:
        return False
    return True


PHONE_TESTS_MAX = 64
TEST_REASON_MAX = 200


def phone_discovery(sim, affordances, known_sims):
    """2.40.0 (W13 P1): the discovery record's phone sections, read only. pickers: each Sim picker of her phone, with its
    tuned minimum, filter class name, include flags, radius and the step that drops each Sim she knows
    (observers.read_picker_steps). phone_tests: each phone act's own test, asked as the game asks it (no run): its
    reason text (cut to TEST_REASON_MAX) and tooltip key. Returns (pickers, phone_tests); a section that cannot be read
    is None."""
    pickers, tests = [], []
    try:
        context = build_context(sim)
    except Exception:
        return None, None
    steps = observers.read_picker_steps(observers.her_sim_info(), known_sims)
    for affordance in affordances[:PHONE_SCAN_LIMIT]:
        try:
            name = str(affordance.__name__)
        except Exception:
            name = ""
        guid = tuned._class_plain(affordance, "guid64")
        if needs_sim(affordance):
            flags = [flag for flag in observers.PICKER_INCLUDE_FLAGS if tuned._class_plain(affordance, flag) is True]
            sim_filter = tuned._class_plain(affordance, "sim_filter")
            pickers.append(reach.picker_row(name, guid, tuned._class_plain(affordance, "min_selectable"),
                                            observers._type_name(type(sim_filter)), flags,
                                            tuned._class_plain(affordance, "radius"), steps))
        if len(tests) < PHONE_TESTS_MAX:
            ok, reason, reason_key = preflight_test(sim, sim, affordance, context)
            tests.append({"name": reach._text(name, reach.LABEL_MAX), "guid64": reach._id(guid),
                          "reason": None if ok else reach._text(reason, TEST_REASON_MAX),
                          "tooltip_key": reason_key if type(reason_key) is str else None})
    return pickers, tests


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


# 2.39.0 (W12 C6): the game's PlacementFlags bits that put an object on a wall (build_buy.PlacementFlags, read from the
# game's bytecode: CENTER_ON_WALL, EDGE_AGAINST_WALL, ADJUST_HEIGHT_ON_WALL, GROUNDED_AGAINST_WALL, ON_WALL_TOP).
WALL_PLACEMENT_FLAGS = (1, 2, 4, 8388608, 268435456)
# 2.39.0 (W12 G1): a pie choice's list is read at most this far (the game's pie menus are short).
PIE_CHOICES_MAX = 16
PIE_HIDDEN_FLAGS = ("cheat", "debug", "automation")


def is_wall_placed(obj):
    """2.39.0 (W12 C6): whether the object is placed on a wall (a mirror, a wall light): BaseObject._has_placement_flag
    for each wall flag. When the flag cannot be read, the class name says so (the game's wall classes are named
    *_wall). False when unknown."""
    try:
        reader = obj._has_placement_flag
    except Exception:
        reader = None
    if callable(reader):
        try:
            for flag in WALL_PLACEMENT_FLAGS:
                if reader(flag) is True:
                    return True
            return False
        except Exception:
            pass
    try:
        return "wall" in type(obj).__name__.lower()
    except Exception:
        return False


def reachable(sim, obj):
    """Read: whether the game sees a way from her to the object, by the check its own autonomy
    makes before it picks one (autonomy_request._check_object_connectivity_and_rules calls
    ScriptObject.is_connected). True, False, or None when unreadable.
    2.38.0 (W11 P2, live 2026-10-12: every door read False, the front door and both double doors too, while a chair
    46 m away read True): the check does not give a door a way, so a portal never reads False. True when the game
    says so, else None (unknown). No probe API reads a way to a portal's side, so none is computed.
    2.39.0 (W12 C6): the same for a wall-placed object (a mirror, a wall light): its False says nothing about a way."""
    try:
        value = obj.is_connected(sim)
    except Exception:
        return None
    if is_portal(obj) or is_wall_placed(obj):
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


# 2.39.0 (W12 G1): pie-menu choices. A pie act (its name carries "PieMenu") is not an act a push can complete: its
# choices are what the player picks. The game lists them with affordance.potential_interactions(target, context),
# each an affordance-object pair (its affordance, its target, its interaction parameters, and its own test and
# execute). A choice runs as that pair, so its parameters travel with it. Every function here is a read, except
# push_choice, which runs one choice the way a player's pick runs it.

def is_pie(affordance):
    """Read: whether an affordance is a pie-menu act (its name carries PieMenu, as act_excluded reads it)."""
    try:
        low = str(affordance.__name__).lower()
    except Exception:
        return False
    return "piemenu" in low


def pie_choices(affordance, target, context):
    """2.39.0 (W12 G1): the choices a pie-menu act offers for this target and context, as the game enumerates them
    now (at most PIE_CHOICES_MAX). [] when they cannot be read. Never raises."""
    try:
        reader = affordance.potential_interactions(target, context)
    except Exception:
        return []
    choices = []
    try:
        for choice in reader:
            if len(choices) >= PIE_CHOICES_MAX:
                break
            if choice is not None:
                choices.append(choice)
    except Exception:
        pass
    return choices


def choice_names(choice, context):
    """2.39.0 (W12 G1): a pie choice's (text key, match key). The text key is the key of its name as the game builds
    it (choice.name(context), a localized string's hash); the match key is the text key, else the choice's affordance
    name. (None, None) when neither reads. A push finds the choice again by its match key (variant_choice)."""
    try:
        text = observers._string_key(choice.name(context))
    except Exception:
        text = None
    try:
        name = str(choice.affordance.__name__)
    except Exception:
        name = ""
    key = text if text is not None else (name or None)
    return text, key


def variant_choice(affordance, target, context, expected):
    """2.39.0 (W12 G1): the pie's choice whose match key is expected, enumerated again now; None when no choice has
    it (the push refuses VARIANT_GONE)."""
    if expected is None:
        return None
    for choice in pie_choices(affordance, target, context):
        if choice_names(choice, context)[1] == expected:
            return choice
    return None


def choice_excluded(choice):
    """2.39.0 (W12 G1): None when a pie choice may be an act, else why. Its affordance is read by the same rules as an
    object's act (act_excluded: pickers and deny names), and the game's cheat, debug and automation flags stay out."""
    try:
        affordance = choice.affordance
    except Exception:
        affordance = None
    if affordance is None:
        return "not_user_directed"
    reason = act_excluded(affordance, False)
    if reason is not None:
        return reason
    for flag in PIE_HIDDEN_FLAGS:
        if tuned._class_plain(affordance, flag) is True:
            return "hidden"
    return None


def choice_test(choice, context):
    """2.39.0 (W12 G1): whether the game would run this pie choice now, by the choice's own test (no run): (ok, reason,
    reason_key), as preflight_test reads an affordance."""
    try:
        result = choice.test(context)
    except Exception as error:
        return False, _bounded(repr(error)), None
    if result:
        return True, None, None
    return False, _bounded(str(result)), refusal_key(result)


def push_choice(choice, context):
    """2.39.0 (W12 G1): the pie choice run as its own pair (its test, then its execute with its interaction parameters),
    as a player's pick runs it. Returns (interaction_or_None, detail, kind, reason_key) as push_affordance_ex does. The
    sim's push takes no parameters, so pushing the proxy affordance alone would lose the pick (the 2.19.1 vanish)."""
    try:
        outcome = choice.test_and_execute(context)
    except Exception as error:
        return None, _bounded(repr(error)), "failed", None
    if not outcome:
        return None, _bounded(str(outcome)), "refused", refusal_key(outcome)
    try:
        interaction = outcome.interaction
    except Exception:
        interaction = None
    if interaction is None:
        return None, _bounded(repr(outcome)), "failed", None
    return interaction, None, None, None
