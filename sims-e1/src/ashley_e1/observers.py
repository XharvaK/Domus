"""Read-only game observation surface for the E1 probe."""

import services  # PRIOR_ART|RUNTIME_UNVERIFIED: vanilla service getters.
import time

from objects import ALL_HIDDEN_REASONS  # PRIOR_ART|RUNTIME_UNVERIFIED: approved hidden-flag constant.

try:
    # DS3: the game's own room lookup (objects_in_target_room_gen uses it the same way).
    # The guard allows this one name from build_buy and nothing else.
    from build_buy import get_room_id
except Exception:
    get_room_id = None

from . import schema
from . import snapshot


class SelectabilityReadFailure(RuntimeError):
    pass


class LabIdentityAmbiguous(RuntimeError):
    def __init__(self, eligible_count):
        super().__init__("LAB_IDENTITY_AMBIGUOUS:%s" % eligible_count)
        self.eligible_count = eligible_count


def select_lab_body(candidates, hidden_flags):
    eligible = []
    for si in candidates:
        if si is None:
            continue
        try:
            sim = si.get_sim_instance(allow_hidden_flags=hidden_flags)
        except Exception:
            continue
        if sim is None:
            continue
        try:
            selectable = si.is_selectable
        except Exception as error:
            raise SelectabilityReadFailure("SELECTABILITY_READ_FAILURE") from error
        if type(selectable) is not bool:
            raise SelectabilityReadFailure("SELECTABILITY_READ_FAILURE")
        if selectable is True:
            eligible.append((si, sim))
    if len(eligible) != 1:
        raise LabIdentityAmbiguous(len(eligible))
    return eligible[0]


def _monotonic_ns():
    return time.perf_counter_ns()


def _save_snapshot():
    persistence = services.get_persistence_service()
    guid = persistence.get_save_slot_proto_guid()
    buff = persistence.get_save_slot_proto_buff()
    raw_slot_id = None if buff is None else buff.slot_id
    return {"save_slot_guid": None if guid is None else str(guid),
            "slot_id": None if raw_slot_id is None else str(raw_slot_id)}


def _saved_world_ticks():
    """Ticks stored in the loaded/last-saved slot proto (GameClock.save writes
    sim_now ticks to gameplay_data.world_game_time; GameClock.setup reads it on
    load — TARGET_BYTECODE 1.128). None when absent. Read only."""
    buff = services.get_persistence_service().get_save_slot_proto_buff()
    if buff is None:
        return None
    try:
        value = buff.gameplay_data.world_game_time
    except AttributeError:
        return None
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _game_snapshot():
    time_service = services.time_service()
    sim_now = time_service.sim_now
    ticks = sim_now.absolute_ticks()
    clock = services.game_clock_service()
    speed = clock.clock_speed
    try:
        speed = speed.name
    except AttributeError:
        pass
    return {"ticks": int(ticks), "calendar": str(sim_now),
            "clock_speed": str(speed), "paused": speed == "PAUSED"}


def _posture_snapshot(sim):
    """Posture name and target id as plain strings; None-safe, never raises."""
    try:
        posture = sim.posture
    except Exception:
        return None
    if posture is None:
        return None
    name = None
    target_id = None
    try:
        name = str(posture.name)[:schema.MAX_DISPLAY_TEXT_LENGTH]
    except Exception:
        name = None
    try:
        target = posture.target
        target_id = None if target is None else str(target.id)
    except Exception:
        target_id = None
    return {"posture_name": name, "target_id": target_id}


def _describe_interaction(entry):
    row = snapshot.minimal_interaction(entry)
    try:
        row["interaction_id"] = str(entry.id)
    except Exception:
        pass
    try:
        row["affordance_id"] = str(entry.guid64)
    except Exception:
        pass
    try:
        row["affordance_text"] = str(entry.affordance)
    except Exception:
        pass
    try:
        row["target_id"] = str(entry.target.id)
    except Exception:
        pass
    try:
        row["source_raw"] = str(entry.context.source)
    except Exception:
        pass
    return row


# Community-sourced motive tuning ids (s4cl motives enum), LAB-unverified.
# Name match is preferred where available; guid64 is the fallback key.
MOTIVE_GUIDS = {
    16656: "hunger",
    16654: "energy",
    16652: "bladder",
    16657: "hygiene",
    16655: "fun",
    16658: "social",
}


def _motive_band(value):
    if value <= 20:
        return "distress"
    if value <= 50:
        return "low"
    return "ok"


# Live-verified on 1.128.90.1030 (TARGET_BYTECODE). Commodity defines no
# get_value. An instance resolves ContinuousStatistic.get_value
# (continuous_statistic.py offset 10: inst._update_value(), then offset 36:
# super(ContinuousStatistic, inst).get_value()). ContinuousStatistic's base is
# BaseStatistic, not Statistic. BaseStatistic.get_value offset 10 returns
# inst._value when inst is not None; default_value at offset 16 runs only when
# inst is None. _value is always stored in BaseStatistic.__init__ offset 10.
# _modified_value is stored only by Statistic._update_modified_value offset 64.
# Statistic subclasses BaseStatistic and is not on the Commodity chain
# (Commodity's first base is TunedContinuousStatistic; ContinuousStatistic's
# base is BaseStatistic). Domus does not call _update_value or get_value. It
# reads inst._value. Age comes from inst._last_update
# (ContinuousStatistic.__init__ offset 72).
_MOTIVE_DIAG = {"stage": "ok", "seen_guids": [], "matched": 0}


def motive_diag():
    """Copy of the last motive-read outcome. Never raises."""
    try:
        return {
            "stage": _MOTIVE_DIAG["stage"],
            "seen_guids": list(_MOTIVE_DIAG["seen_guids"]),
            "matched": _MOTIVE_DIAG["matched"],
        }
    except Exception:
        return {"stage": "ok", "seen_guids": [], "matched": 0}


def _store_motive_diag(stage, seen, matched):
    global _MOTIVE_DIAG
    try:
        row = schema.validate_motive_diag(
            {"stage": stage, "seen_guids": list(seen), "matched": matched})
    except Exception:
        return
    _MOTIVE_DIAG = row


def _motive_guid(entry):
    try:
        value = entry.guid64
    except Exception:
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_field(entry, field):
    if field == "_value":
        return entry._value
    if field == "_last_update":
        return entry._last_update
    if field == "min_value":
        return entry.min_value
    if field == "max_value":
        return entry.max_value
    raise AttributeError(field)


# Bytecode date_and_time: REAL_MILLISECONDS_PER_SIM_SECOND = 25, so a sim minute is
# 1500 ticks.
TICKS_PER_SIM_MINUTE = 1500.0


def _current_value(entry, value, age):
    """D25 (live: at speed 3 the cache of every need she was not refilling was up to
    47554 ticks old). The game's own ContinuousStatistic._update_value, without its
    write (bytecode statistics/continuous_statistic): change rate, or decay toward
    convergence. Every call here was checked for stores across the game's statistic
    classes; get_value and _update_value are never called. None if unreadable."""
    try:
        tracker = entry._tracker
        if tracker is not None and tracker.should_suppress_calculations() is True:
            return value
        if age <= 0:
            return value
        minutes = age / TICKS_PER_SIM_MINUTE
        change = float(entry._get_change_rate_without_decay())
        decay = float(entry.get_decay_rate())
        new = None
        if change == 0 and decay != 0:
            target = float(entry.convergence_value)
            until = entry._calculate_minutes_until_value_is_reached_through_decay(target)
            if until is not None and minutes > float(until):
                new = target
            rate = decay
        else:
            rate = change
        if new is None:
            new = value + minutes * rate
        return float(new)
    except Exception:
        return None


def _read_cached_motive(entry, now_ticks):
    """Return (row or None, fault or None). Fault is set only for a known motive."""
    guid = _motive_guid(entry)
    if guid is None or guid not in MOTIVE_GUIDS:
        return None, None
    try:
        raw = _load_field(entry, "_value")
    except Exception:
        return None, "row_error:_value"
    source = "_value"
    loaded = {}
    for field in ("_last_update", "min_value", "max_value"):
        try:
            loaded[field] = _load_field(entry, field)
        except Exception:
            return None, "row_error:" + field
    if isinstance(raw, bool):
        return None, "row_error:" + source
    if isinstance(loaded["_last_update"], bool):
        return None, "row_error:_last_update"
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None, "row_error:" + source
    try:
        low = float(loaded["min_value"])
    except (TypeError, ValueError):
        return None, "row_error:min_value"
    try:
        high = float(loaded["max_value"])
    except (TypeError, ValueError):
        return None, "row_error:max_value"
    try:
        stamp = int(loaded["_last_update"])
        now = int(now_ticks)
        age = now - stamp
    except (TypeError, ValueError):
        return None, "row_error:_last_update"
    if age < 0:
        age = 0
    current = _current_value(entry, value, age)
    if current is not None:
        # age_ticks is the age of the reading: 0 when this is the game's current value.
        value = max(low, min(high, current))
        age = 0
    if high == low:
        normalized = None
    else:
        normalized = round((value - low) / (high - low) * 100)
        normalized = max(0, min(100, normalized))
    band = None if normalized is None else _motive_band(normalized)
    try:
        motive_id = schema.string_id(MOTIVE_GUIDS[guid], "motive.id")
        if motive_id is None:
            raise ValueError("motive.id")
        motive_id = str(motive_id)
    except Exception:
        return None, "string_id_error"
    return {"id": motive_id, "value": normalized, "band": band, "age_ticks": age}, None


def read_motives(sim_info, now_ticks):
    """Pure tracker route: get_component → get_commodity_tracker(create=False)."""
    stage = "ok"
    seen = []
    matched = 0
    motives = []
    try:
        try:
            from objects.components.types import STATISTIC_COMPONENT
            component = sim_info.get_component(STATISTIC_COMPONENT)
        except Exception:
            stage = "component_error"
            return []
        if component is None:
            stage = "no_component"
            return []
        try:
            tracker = component.get_commodity_tracker(create=False)
        except Exception:
            stage = "no_tracker"
            return []
        if tracker is None:
            stage = "no_tracker"
            return []
        try:
            commodities = tracker.get_all_commodities()
            iterator = iter(commodities)
        except Exception:
            stage = "commodities_error"
            return []
        seen_set = []
        fault = None
        for entry in iterator:
            guid = _motive_guid(entry)
            if guid is not None and guid not in seen_set and len(seen_set) < 40:
                seen_set.append(guid)
            if len(motives) >= schema.MAX_MOTIVES:
                continue
            try:
                row, row_fault = _read_cached_motive(entry, now_ticks)
            except Exception:
                row, row_fault = None, "commodities_error"
            if row_fault is not None and fault is None:
                fault = row_fault
            if row is not None:
                motives.append(row)
        seen = sorted(seen_set)
        matched = len(motives)
        if fault is not None and matched == 0:
            stage = fault
        elif matched:
            stage = "ok"
        else:
            stage = "no_guid_match"
        return motives
    except Exception:
        stage = "commodities_error"
        return []
    finally:
        _store_motive_diag(stage, seen, matched)


def _bounded_name(value, field):
    try:
        if not isinstance(value, str):
            return None
        return schema.bounded_string(value, 128, field, False)
    except Exception:
        return None


def _tuning_name(entry):
    """Class name only. No method calls on the buff."""
    try:
        raw = type(entry).__name__
    except Exception:
        try:
            raw = entry.__class__.__name__
        except Exception:
            return None
    return _bounded_name(raw, "signal.tuning_name")


def _buff_blueprint(entry):
    """DS3 (live: every moodlet read tuning_name "Buff" and weight 0): an active buff
    is a Buff instance; its tuned data sits on its blueprint (Buff.buff_type returns
    tuning_blueprint). Plain attribute reads only."""
    try:
        blueprint = entry.tuning_blueprint
    except Exception:
        blueprint = None
    return entry if blueprint is None else blueprint


def _string_key(value):
    """The game string key of a tuned string factory (_string_id) or a built
    LocalizedString (hash), as a decimal string. The helper resolves the text."""
    if value is None:
        return None
    for read in (lambda: value._string_id, lambda: value.hash):
        try:
            key = read()
        except Exception:
            continue
        if type(key) is int and key > 0:
            return str(key)
    return None


def _describe_buff(entry):
    try:
        tuning = str(entry.guid64)
    except Exception:
        return None
    blueprint = _buff_blueprint(entry)
    try:
        weight = blueprint.mood_weight
    except Exception:
        try:
            weight = entry.mood_weight
        except Exception:
            return None
    if isinstance(weight, bool):
        return None
    try:
        magnitude = "w:%d" % int(weight)
    except (TypeError, ValueError):
        return None
    try:
        tuning_id = str(schema.string_id(tuning, "signal.tuning_id"))
    except Exception:
        return None
    try:
        name = blueprint.__name__ if blueprint is not entry else None
    except Exception:
        name = None
    name = _bounded_name(name, "signal.tuning_name") or _tuning_name(entry)
    try:
        mood = blueprint.mood_type
        mood_name = None if mood is None else mood.__name__
    except Exception:
        mood_name = None
    try:
        visible = blueprint.visible
    except Exception:
        visible = None
    try:
        text_key = _string_key(blueprint.buff_name)
    except Exception:
        text_key = None
    return {"kind": "MOODLET", "tuning_id": tuning_id, "tuning_name": name,
            "game_text": None, "magnitude": magnitude, "consequences": None,
            "native_override": None, "text_key": text_key,
            "mood_type": _bounded_name(mood_name, "signal.mood_type"),
            "visible": visible if type(visible) is bool else None}


def _signal_order(signal):
    """Visible moodlets first, heavier first, then by id: truncation drops hidden ones."""
    weight = 0
    try:
        weight = int(signal["magnitude"][2:])
    except Exception:
        pass
    return (0 if signal.get("visible") is True else 1, -abs(weight), signal["tuning_id"])


def read_moodlets(sim_info):
    try:
        buffs = sim_info.Buffs
    except Exception:
        return []
    if buffs is None:
        return []
    try:
        iterator = iter(buffs)
    except TypeError:
        return []
    signals = []
    seen = 0
    for entry in iterator:
        # Read a bounded number, then keep the visible and heavy ones (DS3).
        seen += 1
        if seen > schema.MAX_SIGNALS * 4:
            break
        try:
            row = _describe_buff(entry)
        except Exception:
            continue
        if row is not None:
            signals.append(row)
    signals.sort(key=_signal_order)
    return signals[:schema.MAX_SIGNALS]


def read_mood(sim_info):
    try:
        buffs = sim_info.Buffs
    except Exception:
        return None
    if buffs is None:
        return None
    try:
        mood = buffs.get_mood()
    except Exception:
        return None
    if mood is None:
        return None
    try:
        mood_type = str(mood.guid64)
    except Exception:
        return None
    try:
        intensity = buffs.get_mood_intensity()
    except Exception:
        return None
    if intensity is not None and (isinstance(intensity, bool) or
                                  not isinstance(intensity, (int, float))):
        return None
    try:
        mood_id = str(schema.string_id(mood_type, "mood.type"))
    except Exception:
        return None
    try:
        mood_name = mood.__name__
    except Exception:
        mood_name = None
    return {"type": mood_id, "intensity": intensity,
            "name": _bounded_name(mood_name, "mood.name")}


def read_senses(sim_info, now_ticks, game):
    del game
    return {"motives": read_motives(sim_info, now_ticks),
            "sim_signals": read_moodlets(sim_info),
            "mood": read_mood(sim_info)}


def _active_household_id():
    try:
        household = services.active_household()
    except Exception:
        return None
    try:
        return household.id
    except Exception:
        return None


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _position(obj):
    """DS3: {x, y, z, level} rounded to 0.01, or None. ClientObjectMixin.position is
    transform.translation; level is a plain read."""
    try:
        translation = obj.position
        coords = (_number(translation.x), _number(translation.y), _number(translation.z))
    except Exception:
        return None
    if None in coords:
        return None
    try:
        level = obj.level
    except Exception:
        level = None
    if isinstance(level, bool) or not isinstance(level, int):
        level = None
    return {"x": round(float(coords[0]), 2), "y": round(float(coords[1]), 2),
            "z": round(float(coords[2]), 2), "level": level}


def _room(obj, position):
    """DS3: the game's room id for this object, as a string id, or None."""
    if get_room_id is None or position is None or position["level"] is None:
        return None
    try:
        room = get_room_id(obj.zone_id, obj.position, position["level"])
    except Exception:
        return None
    if isinstance(room, bool) or not isinstance(room, int):
        return None
    return str(room)


def _distance(a, b):
    if a is None or b is None:
        return None
    dx = a["x"] - b["x"]
    dz = a["z"] - b["z"]
    return round((dx * dx + dz * dz) ** 0.5, 1)


def _plain_id(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return str(schema.string_id(value, "id"))
    except Exception:
        return None


def zone_snapshot(sim):
    """DS3 (live rows carried zone, lot, room and position all null): where her body is."""
    try:
        zone_id = services.current_zone_id()
    except Exception:
        zone_id = None
    try:
        lot_id = services.active_lot_id()
    except Exception:
        lot_id = None
    position = _position(sim)
    return {"zone_id": _plain_id(zone_id), "lot_id": _plain_id(lot_id),
            "room": _room(sim, position), "position": position}


def _sim_name(sim_info):
    parts = []
    for read in (lambda: sim_info.first_name, lambda: sim_info.last_name):
        try:
            part = read()
        except Exception:
            part = None
        if isinstance(part, str) and part:
            parts.append(part)
    return _bounded_name(" ".join(parts), "presence.name") if parts else None


def _doing(sim):
    """What a present Sim is doing: its first running super interaction that is not
    posture plumbing, as (affordance text, target id)."""
    try:
        running = list(sim.si_state or ())
    except Exception:
        return None, None
    fallback = (None, None)
    for entry in running[:8]:
        row = _describe_interaction(entry)
        text = row.get("affordance_text")
        if not isinstance(text, str):
            continue
        text = text[:schema.MAX_DISPLAY_TEXT_LENGTH]
        target = _plain_id(row.get("target_id"))
        if "POSTURE_GRAPH" in str(row.get("source_raw")):
            if fallback == (None, None):
                fallback = (text, target)
            continue
        return text, target
    return fallback


def _describe_presence(sim_info, sim, household_id, lab_sim_id=None, body_position=None):
    try:
        raw_id = sim_info.id
    except Exception:
        return None
    if raw_id is None:
        return None
    try:
        own_household = sim_info.household_id
    except Exception:
        own_household = None
    try:
        level = sim.level
    except Exception:
        level = None
    if isinstance(level, bool) or not isinstance(level, int):
        level = None
    try:
        entry_id = str(schema.string_id(raw_id, "presence.id"))
    except Exception:
        return None
    position = _position(sim)
    posture = _posture_snapshot(sim)
    doing, doing_target = _doing(sim)
    return {"id": entry_id,
            "active_household": household_id is not None and own_household == household_id,
            "level": level,
            "is_body": lab_sim_id is not None and entry_id == str(lab_sim_id),
            "household_id": _plain_id(own_household),
            "name": _sim_name(sim_info),
            "position": position,
            "room": _room(sim, position),
            "posture": None if posture is None else posture.get("posture_name"),
            "doing": doing,
            "doing_target": doing_target,
            "distance_m": _distance(position, body_position)}


def read_presence(lab_sim_id, hidden_flags=ALL_HIDDEN_REASONS, body_position=None):
    """Every instanced Sim on the active lot, her body first, then nearest first.

    D37 (live: presence was empty in every row with 8 Sims on the lot):
    instanced_sims_on_active_lot_gen yields Sim objects, not SimInfo. The old reader
    called get_sim_instance on each Sim, which failed and was swallowed, so she never
    saw anyone and social (gated on presence) never ran.
    """
    try:
        manager = services.sim_info_manager()
    except Exception:
        return [], False
    try:
        generator = manager.instanced_sims_on_active_lot_gen(
            hidden_flags, include_spawn_point=False)
    except Exception:
        try:
            generator = manager.instanced_sims_on_active_lot_gen(hidden_flags)
        except Exception:
            return [], False
    try:
        iterator = iter(generator)
    except TypeError:
        return [], False
    household_id = _active_household_id()
    presence = []
    while True:
        try:
            sim = next(iterator)
        except StopIteration:
            break
        except Exception:
            continue
        if sim is None:
            continue
        try:
            sim_info = sim.sim_info
        except Exception:
            continue
        if sim_info is None:
            continue
        try:
            row = _describe_presence(sim_info, sim, household_id, lab_sim_id, body_position)
        except Exception:
            continue
        if row is None:
            continue
        presence.append(row)
        if len(presence) >= schema.MAX_PRESENCE * 4:
            break
    presence.sort(key=lambda row: (0 if row["is_body"] else 1,
                                   row["distance_m"] if row["distance_m"] is not None else 1e9,
                                   row["id"]))
    truncated = len(presence) > schema.MAX_PRESENCE
    return presence[:schema.MAX_PRESENCE], truncated


def _target_matches(entry, lab_sim, lab_sim_id):
    try:
        target = entry.target
    except Exception:
        return False
    if target is None:
        return False
    if target is lab_sim:
        return True
    for candidate in (target, lab_sim):
        try:
            if str(candidate.id) == str(lab_sim_id):
                other = lab_sim if candidate is target else target
                try:
                    if str(other.id) == str(lab_sim_id):
                        return True
                except Exception:
                    pass
        except Exception:
            continue
    return False


def _targeted_entries(container, lab_sim, lab_sim_id):
    found = []
    if container is None:
        return found
    try:
        iterator = iter(container)
    except TypeError:
        return found
    while True:
        try:
            entry = next(iterator)
        except StopIteration:
            break
        except Exception:
            continue
        if entry is None:
            continue
        if _target_matches(entry, lab_sim, lab_sim_id):
            found.append(entry)
    return found


def read_social(lab_sim_id, lab_sim, candidates):
    social = []
    truncated = False
    for candidate in candidates or ():
        if candidate is None:
            continue
        try:
            raw_id = candidate.id
        except Exception:
            continue
        if raw_id is not None and str(raw_id) == str(lab_sim_id):
            continue
        try:
            actor = schema.string_id(raw_id, "social.actor_id")
            actor_id = None if actor is None else str(actor)
        except Exception:
            continue
        if not actor_id:
            continue
        try:
            sim = candidate.get_sim_instance(allow_hidden_flags=ALL_HIDDEN_REASONS)
        except Exception:
            continue
        if sim is None:
            continue
        try:
            queued = _targeted_entries(sim.queue, lab_sim, lab_sim_id)
            running = _targeted_entries(sim.si_state, lab_sim, lab_sim_id)
            merged, queue_truncated, running_truncated = snapshot.merge_interactions(
                queued, running, _describe_interaction)
        except Exception:
            continue
        if queue_truncated or running_truncated:
            truncated = True
        for row in merged:
            row["actor_id"] = actor_id
            if len(social) >= schema.MAX_SOCIAL:
                truncated = True
                continue
            social.append(row)
    return social, truncated


def poll_once(telemetry_session_id, armed_name,
              hidden_flags=ALL_HIDDEN_REASONS):
    """Read one body and return a plain-data presence record."""
    candidates = services.sim_info_manager().get_all()
    sim_info, sim = select_lab_body(candidates, hidden_flags)
    raw_queued = sim.queue
    raw_running = sim.si_state
    capture_complete = raw_queued is not None and raw_running is not None
    queued = () if raw_queued is None else raw_queued
    running = () if raw_running is None else raw_running
    interactions, queue_truncated, running_truncated = snapshot.merge_interactions(
        queued, running, _describe_interaction
    )
    senses = read_senses(sim_info, services.time_service().sim_now.absolute_ticks(), None)
    motives = senses["motives"]
    signals = senses["sim_signals"]
    mood = senses["mood"]
    try:
        raw_lab_id = sim_info.id
        lab_id = None if raw_lab_id is None else str(raw_lab_id)
    except Exception:
        lab_id = None
    presence, presence_truncated = ([], False)
    social, social_truncated = ([], False)
    zone = zone_snapshot(sim)
    if lab_id is not None:
        try:
            presence, presence_truncated = read_presence(
                lab_id, body_position=zone["position"])
        except Exception:
            presence, presence_truncated = ([], False)
        if any(not row["is_body"] for row in presence):
            try:
                candidates = services.sim_info_manager().get_all()
            except Exception:
                candidates = ()
            try:
                social, social_truncated = read_social(lab_id, sim, candidates)
            except Exception:
                social, social_truncated = ([], False)
    save = _save_snapshot()
    game = _game_snapshot()
    wall = int(time.time() * 1000)
    mono = _monotonic_ns()
    raw_sim_id = sim_info.id
    sim_id = None if raw_sim_id is None else str(raw_sim_id)
    body = {"sim_id": sim_id, "instantiated": True, "is_selectable": True,
            "is_selected": None, "posture": _posture_snapshot(sim)}
    complete = snapshot.interactions_complete(
        queue_truncated, running_truncated, capture_complete)
    if presence_truncated or social_truncated:
        complete = False
    row = schema.make_record(
        "presence_snapshot", telemetry_session_id=telemetry_session_id,
        wall_timestamp_ms=wall, monotonic_ns=mono,
        game=game, attestation=schema.attestation(armed_name),
        save=save, zone=zone, body=body,
        interactions={"observed": interactions, "queue_truncated": queue_truncated,
                      "running_truncated": running_truncated,
                      "observation_complete": complete},
        observation_complete=complete,
        motives=motives, sim_signals=signals, mood=mood,
        presence=presence, social=social,
    )
    return snapshot.apply_size_budget(row)
