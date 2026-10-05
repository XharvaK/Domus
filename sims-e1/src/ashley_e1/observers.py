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


def stat_trackers(owner):
    """D42 (bytecode objects/components/statistic_component): the `statistic_tracker`
    and `commodity_tracker` properties call _get_or_add_statistic_component, which adds
    a component to an object that has none (add_dynamic_component), and the getters
    create a tracker. Only the existing component's fields are read here:
    (statistic tracker or None, commodity tracker or None)."""
    try:
        from objects.components.types import STATISTIC_COMPONENT
        component = owner.get_component(STATISTIC_COMPONENT)
    except Exception:
        return None, None
    if component is None:
        return None, None
    found = []
    for read in (lambda: component._statistic_tracker,
                 lambda: component._commodity_tracker):
        try:
            found.append(read())
        except Exception:
            found.append(None)
    return found[0], found[1]


def _commodity_tracker(sim_info):
    """D42: her commodity tracker without the creating property."""
    return stat_trackers(sim_info)[1]


def _moodlet_minutes_left(entry, sim_info, now_ticks):
    """S5: game minutes until a timed moodlet ends. Bytecode (buffs/buff): a timed buff
    has `_temporary_commodity_info` and keeps `_owning_commodity`; the `commodity`
    property can create one (a store), so the instance is read from the Sim's own
    commodity tracker (D42: through the pure route). Minutes come from the D25-checked decay calls. None otherwise."""
    try:
        if entry._temporary_commodity_info is None:
            return None
        owning = entry._owning_commodity
        if owning is None or sim_info is None:
            return None
        tracker = _commodity_tracker(sim_info)
        if tracker is None:
            return None
        instance = tracker._statistics.get(owning)
    except Exception:
        return None
    if instance is None:
        return None
    try:
        until = instance._calculate_minutes_until_value_is_reached_through_decay(
            float(instance.convergence_value))
        updated = instance._last_update
    except Exception:
        return None
    if until is None or isinstance(until, bool) or not isinstance(until, (int, float)):
        return None
    age = 0.0
    if type(updated) is int and type(now_ticks) is int and now_ticks >= updated:
        age = (now_ticks - updated) / TICKS_PER_SIM_MINUTE
    return round(max(float(until) - age, 0.0), 1)


def _describe_buff(entry, sim_info=None, now_ticks=None):
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
    try:
        reason_key = _string_key(entry.buff_reason)
    except Exception:
        reason_key = None
    return {"kind": "MOODLET", "tuning_id": tuning_id, "tuning_name": name,
            "game_text": None, "magnitude": magnitude, "consequences": None,
            "native_override": None, "text_key": text_key,
            "mood_type": _bounded_name(mood_name, "signal.mood_type"),
            "visible": visible if type(visible) is bool else None,
            "reason_key": reason_key,
            "minutes_left": _moodlet_minutes_left(entry, sim_info, now_ticks)}


def _signal_order(signal):
    """Visible moodlets first, heavier first, then by id: truncation drops hidden ones."""
    weight = 0
    try:
        weight = int(signal["magnitude"][2:])
    except Exception:
        pass
    return (0 if signal.get("visible") is True else 1, -abs(weight), signal["tuning_id"])


def read_moodlets(sim_info, now_ticks=None):
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
            row = _describe_buff(entry, sim_info, now_ticks)
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
            "sim_signals": read_moodlets(sim_info, now_ticks),
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


def _type_name(value):
    """value.__name__ as a plain attribute read (no reflection), or None."""
    try:
        name = value.__name__
    except Exception:
        return None
    return name if isinstance(name, str) else None


def _trait_entry(trait):
    name = _bounded_name(_type_name(trait), "trait")
    if name is None:
        return None
    try:
        text_key = _string_key(trait.display_name)
    except Exception:
        text_key = None
    return {"trait": name, "text_key": text_key}


def _careers_of(sim_info):
    """Career type names from career_tracker._careers (a plain dict read)."""
    try:
        values = list(sim_info.career_tracker._careers.values())
    except Exception:
        return None
    names = []
    for career in values[:4]:
        name = _bounded_name(_type_name(type(career)), "career")
        if name is not None:
            names.append(name)
    return sorted(names)


NOTHING_KNOWN = {"traits": [], "careers": None, "relationship_status": False,
                 "romantic_preference": False, "net_worth": None}


def _knowledge(data, other_info):
    """2.15.0: what she has learned about the other Sim. Bytecode (relationships/
    sim_knowledge, data/unidirectional_relationship_data): her side of the relationship
    keeps `_knowledge`, None until she learns something; SimKnowledge keeps plain
    fields. SimRelationship.get_knowledge was not used: it creates the record
    (initialize_knowledge). None when unreadable."""
    try:
        knowledge = data._knowledge
    except Exception:
        return None
    known = dict(NOTHING_KNOWN)
    if knowledge is None:
        return known
    try:
        traits = list(knowledge._known_traits)
    except Exception:
        traits = []
    entries = [entry for entry in (_trait_entry(trait) for trait in traits) if entry]
    known["traits"] = sorted(entries, key=lambda item: item["trait"])[:schema.MAX_KNOWN_TRAITS]
    for key, read in (("relationship_status", lambda: knowledge._knows_rel_status),
                      ("romantic_preference", lambda: knowledge._knows_romantic_preference)):
        try:
            known[key] = read() is True
        except Exception:
            known[key] = False
    try:
        knows_career = knowledge._knows_career is True
    except Exception:
        knows_career = False
    if knows_career and other_info is not None:
        known["careers"] = _careers_of(other_info)
    try:
        worth = knowledge._known_net_worth
    except Exception:
        worth = None
    if type(worth) is int:
        known["net_worth"] = worth
    return known


def _sentiments(data):
    """2.15.0: her sentiments toward the other Sim (Close, Hurt, ...): the types held in
    her side's `_sentiment_tracker._statistics` (plain read)."""
    try:
        tracker = data._sentiment_tracker
    except Exception:
        return []
    if tracker is None:
        return []
    try:
        types_ = list(tracker._statistics.keys())
    except Exception:
        return []
    found = []
    for track_type in types_:
        name = _bounded_name(_type_name(track_type), "sentiment")
        if name is None:
            continue
        try:
            text_key = _string_key(track_type.display_name)
        except Exception:
            text_key = None
        found.append({"sentiment": name, "text_key": text_key})
    found.sort(key=lambda item: item["sentiment"])
    return found[:schema.MAX_SENTIMENTS]


def _her_side(relationship, body_id):
    """Her uni-directional data (SimRelationship._get_uni_directional_rel_data, read
    without the call): `_sim_a_relationship_data` when she is `_sim_id_a`."""
    try:
        if relationship._sim_id_a == body_id:
            return relationship._sim_a_relationship_data
        return relationship._sim_b_relationship_data
    except Exception:
        return None


def relationship_between(body_id, other_id, now_ticks=None, other_info=None):
    """S5: what the game holds between her and another Sim, from plain attributes.

    Bytecode (relationships/*): RelationshipService keeps `_relationships` keyed by
    (smaller id, larger id); a Relationship keeps `_bi_directional_relationship_data`
    with `_track_tracker._statistics` (friendship, romance, ...) and `_bits` (labels,
    with `display_name`, `visible`). get_relationship_score was not used: it goes
    through _find_relationship (which can create one) and get_track_score (the value
    getter). Track values are the D25 decay math on `_value`. known=False: no
    relationship exists yet (they have not met)."""
    try:
        a, b = int(body_id), int(other_id)
        key = (a, b) if a < b else (b, a)
        relationship = services.relationship_service()._relationships.get(key)
    except Exception:
        return None
    if relationship is None:
        return {"known": False, "tracks": [], "labels": [],
                "knows": dict(NOTHING_KNOWN), "sentiments": []}
    try:
        data = relationship._bi_directional_relationship_data
    except Exception:
        return None
    tracks = []
    try:
        items = list(data._track_tracker._statistics.items())
    except Exception:
        items = []
    for track_type, instance in items:
        name = _bounded_name(_type_name(track_type), "relationship.track")
        if name is None or instance is None:
            continue
        try:
            value = instance._value
            updated = instance._last_update
        except Exception:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        current = float(value)
        if type(updated) is int and type(now_ticks) is int and now_ticks >= updated:
            computed = _current_value(instance, float(value), now_ticks - updated)
            if computed is not None:
                current = computed
        tracks.append({"track": name, "value": round(current, 1)})
    tracks.sort(key=lambda item: item["track"])
    labels = []
    try:
        bits = list(data._bits.keys())
    except Exception:
        bits = []
    for bit in bits:
        try:
            if bit.visible is not True:
                continue
        except Exception:
            continue
        name = _bounded_name(_type_name(bit), "relationship.label")
        if name is None:
            continue
        try:
            text_key = _string_key(bit.display_name)
        except Exception:
            text_key = None
        labels.append({"label": name, "text_key": text_key})
    labels.sort(key=lambda item: item["label"])
    side = _her_side(relationship, a)  # a is her id (before the key sort)
    return {"known": True, "tracks": tracks[:schema.MAX_REL_TRACKS],
            "labels": labels[:schema.MAX_REL_LABELS],
            "knows": None if side is None else _knowledge(side, other_info),
            "sentiments": [] if side is None else _sentiments(side)}


def _describe_presence(sim_info, sim, household_id, lab_sim_id=None, body_position=None,
                       now_ticks=None):
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
    is_body = lab_sim_id is not None and entry_id == str(lab_sim_id)
    relationship = None
    if not is_body and lab_sim_id is not None:
        try:
            relationship = relationship_between(lab_sim_id, entry_id, now_ticks,
                                                sim_info)
        except Exception:
            relationship = None
    try:
        on_lot = sim.is_on_active_lot()
    except Exception:
        on_lot = None
    return {"id": entry_id,
            "on_lot": on_lot if type(on_lot) is bool else None,
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
            "distance_m": _distance(position, body_position),
            "relationship": relationship}


def read_presence(lab_sim_id, hidden_flags=ALL_HIDDEN_REASONS, body_position=None,
                  now_ticks=None):
    """Every instanced Sim in the zone, her body first, then nearest first.
    Returns (presence, truncated, skipped).

    D37 (live: presence was empty in every row with 8 Sims on the lot): the reader
    must not call get_sim_instance on a Sim object.
    D40 (live, 2.14.0): the game's instanced_sims_on_active_lot_gen asks each Sim
    is_on_active_lot() inside the generator. A Sim arriving for a group chat made that
    raise, which ends a generator: for an hour of game time her presence was empty,
    her own body included, and the rows still said complete. The lot test also hid
    Sims on the sidewalk next to her. Now each SimInfo's instance is read on its own
    (get_sim_instance reads `_sim_ref`, bytecode sims/sim_info), on_lot is asked per
    Sim, and a Sim that cannot be read is counted in `skipped`.
    """
    try:
        infos = list(services.sim_info_manager().get_all())
    except Exception:
        return [], False, None
    household_id = _active_household_id()
    presence = []
    skipped = 0
    for sim_info in infos:
        try:
            sim = sim_info.get_sim_instance(allow_hidden_flags=hidden_flags)
        except Exception:
            skipped += 1
            continue
        if sim is None:
            continue
        try:
            row = _describe_presence(sim_info, sim, household_id, lab_sim_id, body_position,
                                     now_ticks)
        except Exception:
            row = None
        if row is None:
            skipped += 1
            continue
        presence.append(row)
    presence.sort(key=lambda row: (0 if row["is_body"] else 1,
                                   row["distance_m"] if row["distance_m"] is not None else 1e9,
                                   row["id"]))
    truncated = len(presence) > schema.MAX_PRESENCE
    return presence[:schema.MAX_PRESENCE], truncated, skipped


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
    now_ticks = services.time_service().sim_now.absolute_ticks()
    senses = read_senses(sim_info, now_ticks, None)
    motives = senses["motives"]
    signals = senses["sim_signals"]
    mood = senses["mood"]
    try:
        raw_lab_id = sim_info.id
        lab_id = None if raw_lab_id is None else str(raw_lab_id)
    except Exception:
        lab_id = None
    presence, presence_truncated, skipped = ([], False, None)
    social, social_truncated = ([], False)
    zone = zone_snapshot(sim)
    if lab_id is not None:
        try:
            presence, presence_truncated, skipped = read_presence(
                lab_id, body_position=zone["position"], now_ticks=now_ticks)
        except Exception:
            presence, presence_truncated, skipped = ([], False, None)
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
    missingness = {}
    if skipped is None or skipped > 0 or not any(item["is_body"] for item in presence):
        # D40: a presence read that missed anyone, her body included, says so.
        complete = False
        missingness["presence"] = {
            "status": "MISSING",
            "detail": ("unreadable" if skipped is None else
                       "skipped %d Sims%s" % (skipped, "" if any(
                           item["is_body"] for item in presence) else ", body absent"))}
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
        presence=presence, social=social, missingness=missingness,
    )
    try:
        row["self"] = read_self(sim_info)
    except Exception:
        row["self"] = None
    try:
        row["objects"] = read_object_events(zone.get("zone_id"), zone.get("position"),
                                            int(time.time() * 1000))
    except Exception:
        row["objects"] = None
    return snapshot.apply_size_budget(row)


def _skill_level(instance):
    """Skill level without Skill.get_user_value, which caches into `_user_value` (a
    store; bytecode statistics/skill): the cached `_user_value`, else the game's own
    convert_to_user_value (reads the level list only) on the stored `_value`."""
    try:
        cached = instance._user_value
    except Exception:
        cached = None
    if type(cached) is int:
        return cached
    try:
        level = instance.convert_to_user_value(instance._value)
    except Exception:
        return None
    return level if type(level) is int else None


def read_self(sim_info):
    """2.15.0: what she is like and has: her traits (personality first), her skills
    (highest first) and her household's money. Plain reads: trait_tracker
    `_equipped_traits` and `_equipped_personality_traits`, the skills in the commodity
    tracker's `_statistics` (D42 route; a Skill has `skill_level_type`), and
    household `_funds._funds` (bytecode traits/trait_tracker, sims/funds)."""
    traits = []
    try:
        equipped = list(sim_info.trait_tracker._equipped_traits)
    except Exception:
        equipped = None
    try:
        personality = set(sim_info.trait_tracker._equipped_personality_traits)
    except Exception:
        personality = set()
    for trait in equipped or []:
        entry = _trait_entry(trait)
        if entry is None or entry["text_key"] is None:
            continue  # hidden gameplay traits carry no name of their own
        entry["personality"] = trait in personality
        traits.append(entry)
    traits.sort(key=lambda item: (not item["personality"], item["trait"]))
    skills = []
    try:
        items = list(_commodity_tracker(sim_info)._statistics.items())
    except Exception:
        items = None
    for stat_type, instance in items or []:
        try:
            stat_type.skill_level_type
        except Exception:
            continue
        name = _bounded_name(_type_name(stat_type), "skill")
        if name is None or instance is None:
            continue
        level = _skill_level(instance)
        if level is None:
            continue
        text_key = None
        for read in (lambda: stat_type.stat_name, lambda: stat_type.display_name):
            try:
                text_key = _string_key(read())
            except Exception:
                text_key = None
            if text_key is not None:
                break
        skills.append({"skill": name, "text_key": text_key, "level": level})
    skills.sort(key=lambda item: (-item["level"], item["skill"]))
    funds = None
    try:
        money = sim_info.household._funds._funds
    except Exception:
        money = None
    if type(money) is int:
        funds = money
    return {"traits": None if equipped is None else traits[:schema.MAX_SELF_TRAITS],
            "skills": None if items is None else skills[:schema.MAX_SELF_SKILLS],
            "funds": funds}


# S5: object events. The previous sample's object ids (with class names) and the
# states of the objects near her; a zone change, the first sample or a pause in
# sampling longer than OBJECT_BASELINE_GAP_MS starts a new baseline (no events).
NEAR_STATE_METERS = 4.0
NEAR_STATE_MAX = 16
OBJECT_BASELINE_GAP_MS = 5000
_OBJECTS_PREV = {"zone": None, "wall_ms": None, "classes": None, "near": {}}


def _object_class(obj):
    return _bounded_name(_type_name(type(obj)), "objects.class")


def _object_states(obj):
    try:
        items = list(obj.state_component._states.items())
    except Exception:
        return {}
    found = {}
    for state, value in items[:32]:
        key = _type_name(state)
        if key is not None:
            found[key[:96]] = (_type_name(value) or "")[:96] or None
    return found


def read_object_events(zone_id, body_position, wall_ms):
    """Objects created and destroyed on the lot since the previous sample, and state
    changes of the objects within NEAR_STATE_METERS of her (nearest first). Plain
    attribute reads (object manager `_objects`, `state_component._states`)."""
    try:
        items = list(services.object_manager()._objects.items())
    except Exception:
        return None
    current = {}
    for object_id, obj in items:
        try:
            if obj.is_sim is True:
                continue
        except Exception:
            pass
        plain = _plain_id(object_id)
        if plain is not None:
            current[plain] = obj
    near = []
    for plain, obj in current.items():
        distance = _distance(_position(obj), body_position)
        if distance is not None and distance <= NEAR_STATE_METERS:
            near.append((distance, plain))
    near.sort()
    near_states = {plain: _object_states(current[plain]) for _, plain in near[:NEAR_STATE_MAX]}
    classes = {plain: _object_class(obj) for plain, obj in current.items()}
    previous = _OBJECTS_PREV
    baseline = (previous["classes"] is None or previous["zone"] != zone_id or
                previous["wall_ms"] is None or wall_ms - previous["wall_ms"] > OBJECT_BASELINE_GAP_MS)
    events = {"baseline": baseline, "created": [], "destroyed": [], "changed": [],
              "truncated": False}
    if not baseline:
        created = sorted(set(classes) - set(previous["classes"]))
        destroyed = sorted(set(previous["classes"]) - set(classes))
        for plain in created:
            try:
                definition = _plain_id(current[plain].definition.id)
            except Exception:
                definition = None
            events["created"].append({"object_id": plain, "class": classes[plain],
                                      "definition_id": definition})
        for plain in destroyed:
            events["destroyed"].append({"object_id": plain, "class": previous["classes"][plain]})
        for _, plain in near[:NEAR_STATE_MAX]:
            before = previous["near"].get(plain)
            if before is None:
                continue
            after = near_states[plain]
            for state in sorted(set(before) | set(after)):
                if before.get(state) != after.get(state):
                    events["changed"].append({"object_id": plain, "class": classes[plain],
                                              "state": state, "from": before.get(state),
                                              "to": after.get(state)})
        for key in ("created", "destroyed", "changed"):
            if len(events[key]) > schema.MAX_OBJECT_EVENTS:
                events[key] = events[key][:schema.MAX_OBJECT_EVENTS]
                events["truncated"] = True
    _OBJECTS_PREV.update(zone=zone_id, wall_ms=wall_ms, classes=classes, near=near_states)
    return events
