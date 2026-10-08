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
                       now_ticks=None, situations=None):
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
            "relationship": relationship,
            "situations": None if situations is None else situations.get(entry_id, [])}


def read_situations():
    """2.15.2: Sim id -> the game situations that Sim is in (a visit, a party, a
    greeting) and its role there, from the zone situation manager. Plain reads:
    each situation's `_situation_sims` (Sim -> SituationSim) and the SituationSim's
    `current_role_state_type` (bytecode situations/base_situation; the game's own
    get_situations_sim_is_in only iterates and compares). None when unreadable."""
    try:
        situations = list(services.get_zone_situation_manager().values())
    except Exception:
        return None
    found = {}
    for situation in situations:
        name = _bounded_name(_tuning_name(situation), "situation")
        if name is None:
            continue
        try:
            members = list(situation._situation_sims.items())
        except Exception:
            continue
        for sim, member in members:
            try:
                sim_id = str(sim.id)
            except Exception:
                continue
            try:
                role = _bounded_name(_type_name(member.current_role_state_type), "role")
            except Exception:
                role = None
            entries = found.setdefault(sim_id, [])
            if len(entries) < schema.MAX_SITUATIONS:
                entries.append({"situation": name, "role": role})
    return found


def read_place(sim_info):
    """2.15.2: whose lot she is on (the zone lot's `zone_owner_household_id`, as the
    game's own owning_household_id_of_active_lot reads it), whether that is her home,
    and the venue (the zone venue service's `_active_venue`, its class name).
    Live 2026-10-05: cooking on a host's stove drew reaction_Inappropriate; she had no
    way to know she was a visitor in someone else's home."""
    try:
        zone = services.current_zone()
    except Exception:
        return None
    if zone is None:
        return None
    try:
        owner = zone.lot.zone_owner_household_id
    except Exception:
        owner = None
    owner = owner if type(owner) is int and owner > 0 else None
    try:
        own = sim_info.household_id
    except Exception:
        own = None
    her_home = None if type(own) is not int else (owner is not None and owner == own)
    try:
        venue = _bounded_name(_tuning_name(zone.venue_service._active_venue), "venue")
    except Exception:
        venue = None
    return {"owner_household_id": None if owner is None else str(owner),
            "her_home": her_home, "venue": venue}


# 2.15.2: the game's dialog answers (ButtonType, bytecode ui/ui_dialog).
DIALOG_RESPONSES = {-1: "closed", 10000: "no_response", 10001: "ok", 10002: "cancel",
                    10003: "ok_alt", 10004: "custom_1", 10005: "custom_2", 10006: "custom_3"}
RESPONSE_IDS = {name: number for number, name in DIALOG_RESPONSES.items()}
_DIALOGS_OPEN = {}
# 2.23.0: speed before each dialog. The sample that first lists a dialog is already
# inside the pause that dialog made, so the stored speed is the previous sample's
# clock_speed (the same read as _game_snapshot). A session's first sample uses the
# current read. Closed dialogs are dropped.
_DIALOG_SPEED = {}
_SPEED_SEEN = None


def _remember_dialog_speeds(open_ids):
    global _SPEED_SEEN
    current = None
    try:
        current = _game_snapshot().get("clock_speed")
    except Exception:
        current = None
    if not isinstance(current, str):
        current = None
    prior = _SPEED_SEEN if _SPEED_SEEN is not None else current
    for key in open_ids:
        if key not in _DIALOG_SPEED:
            _DIALOG_SPEED[key] = prior
    for key in list(_DIALOG_SPEED):
        if key not in open_ids:
            del _DIALOG_SPEED[key]
    if current is not None:
        _SPEED_SEEN = current


def dialog_prior_speed(dialog_id):
    """The speed recorded when this dialog was first seen, else the last sample's."""
    key = str(dialog_id)
    if key in _DIALOG_SPEED:
        return _DIALOG_SPEED[key]
    return _SPEED_SEEN


def _response_name(value):
    """A known answer by name, another by its id; None past 16 characters (the schema
    bound), so one odd id never costs the whole row."""
    try:
        number = int(value)
    except Exception:
        return None
    name = DIALOG_RESPONSES.get(number, str(number))
    return name if len(name) <= 16 else None


def _closure_key(text):
    """2.19.0 (live 2026-10-06, a work event at her culinary job: buttons 0 and 1 with no
    text): AdventureMoment._get_dialog (bytecode interactions/utils/adventure) gives each
    button `text=lambda *_, **__: display_name`, the LocalizedString it built from the
    tuned choice. The key is read from the lambda's closure cells, fixed attribute reads
    (`__closure__`, `cell_contents`), nothing called; the first cell holding a string key."""
    try:
        cells = tuple(text.__closure__ or ())
    except Exception:
        return None
    for cell in cells[:4]:
        try:
            key = _string_key(cell.cell_contents)
        except Exception:
            key = None
        if key is not None:
            return key
    return None


def _dialog_responses(dialog):
    """The choices the game offers: ok/cancel texts on an ok-cancel dialog, else the
    tuned and added UiDialogResponse entries. The `responses` property is not used
    (it builds new response objects)."""
    found = []
    try:
        ok = dialog.text_ok
    except Exception:
        ok = None
    if ok is not None:
        found.append({"response": "ok", "text_key": _string_key(ok)})
        try:
            cancel = dialog.text_cancel
        except Exception:
            cancel = None
        if cancel is not None:
            found.append({"response": "cancel", "text_key": _string_key(cancel)})
        return found
    items = []
    for read in (lambda: dialog.ui_responses, lambda: dialog._additional_responses):
        try:
            items.extend(read() or ())
        except Exception:
            continue
    for item in items[:schema.MAX_DIALOG_RESPONSES]:
        try:
            name = _response_name(item.dialog_response_id)
        except Exception:
            name = None
        if name is None:
            continue
        try:
            text_key = _string_key(item.text)
        except Exception:
            text_key = None
        if text_key is None:
            text_key = _closure_key(item.text)
        found.append({"response": name, "text_key": text_key})
    return found


# 2.31.0 (DOMUS_DEEP_DESIGN §11): how each window was attributed and sent, by dialog id key:
# {"held", "cause", "text_inputs"}. e2_control writes it through note_window / forget_window (it imports
# observers, never the reverse); read_dialogs only reads it, and drops the entries of dialogs that are gone.
WINDOWS_KEPT = 32
_WINDOWS = {}


def note_window(key, **facts):
    """2.31.0: facts about one window for the next sample. Bounded: the oldest entry goes first."""
    entry = _WINDOWS.get(key)
    if entry is None:
        if len(_WINDOWS) >= WINDOWS_KEPT:
            del _WINDOWS[next(iter(_WINDOWS))]
        entry = _WINDOWS[key] = {}
    entry.update(facts)


def forget_window(key):
    _WINDOWS.pop(key, None)


def _value(read):
    """2.31.0: one plain attribute read (a lambda, so no name-based lookup) that never raises; None when it
    cannot be read."""
    try:
        return read()
    except Exception:
        return None


def _clamp(value, high):
    """2.31.0: a count the schema can carry (0 .. high); 0 keeps the game's no-limit meaning."""
    return min(max(value, 0), high)


def _optional_int(message, name, read):
    """2.31.0: a set integer field of a protobuf message, else None. HasField(name) says whether it is set;
    read is the plain attribute read of the same field."""
    try:
        if not message.HasField(name):
            return None
    except Exception:
        # A field the message cannot say is set or not: a value above zero counts as set.
        value = _value(read)
        return value if type(value) is int and value > 0 else None
    value = _value(read)
    return value if type(value) is int else None


def read_text_inputs(message):
    """2.31.0 (DOMUS_DEEP_DESIGN §4.4, §11): the text fields of a held dialog message, one per field the
    game built (UiDialogMessage.text_input; bytecode ui/ui_text_input.UiTextInput.build_msg): the field
    name, its length and value limits, whether the game checks profanity, whether a restricted-character
    set exists, and the string key of the default text. Numbers and flags only, never the text. None when
    the message has no text field, a field name is one the probe cannot name, or there are more fields than
    the schema carries (a partial report would let her answer leave a field empty)."""
    try:
        fields = list(message.text_input)
    except Exception:
        return None
    if not fields or len(fields) > schema.MAX_TEXT_INPUTS:
        return None
    found = []
    for field in fields:
        name = _value(lambda: field.text_input_name)
        if type(name) is not str or not 1 <= len(name) <= 32 or not set(name) <= schema.FIELD_NAME_CHARS:
            return None
        min_value = _optional_int(field, "min_value", lambda: field.min_value)
        max_value = _optional_int(field, "max_value", lambda: field.max_value)
        min_length = _optional_int(field, "min_length", lambda: field.min_length)
        found.append({
            "name": name, "min_length": 0 if min_length is None else min_length,
            "max_length": _optional_int(field, "max_length", lambda: field.max_length),
            "numeric": min_value is not None or max_value is not None,
            "min_value": min_value, "max_value": max_value,
            "profanity_checked": _value(lambda: field.check_profanity) is True,
            "restricted": _string_key(_value(lambda: field.restricted_characters)) is not None,
            "default_key": _string_key(_value(lambda: field.default_text))})
    return found


def select_of(dialog):
    """2.31.0 (§11): a picker's selectable rows, from its own attributes (bytecode
    ui/ui_dialog_picker.UiDialogObjectPicker.multi_select reads min_selectable and max_selectable_num).
    None for a window that is not a picker. A max of 0 is the no-limit value multi_select tests for."""
    low = _value(lambda: dialog.min_selectable)
    high = _value(lambda: dialog.max_selectable_num)
    if type(low) is not int or type(high) is not int:
        return None
    return {"min": _clamp(low, schema.MAX_DIALOG_ROWS), "max": _clamp(high, schema.MAX_DIALOG_ROWS)}


def counts_of(dialog):
    """2.31.0 (§11): a purchase picker's counted caps (bytecode ui/ui_dialog_picker.UiPurchasePicker.__init__
    stores max_selectable_in_row and max_selectable_rows). None for a window without them."""
    in_row = _value(lambda: dialog.max_selectable_in_row)
    rows = _value(lambda: dialog.max_selectable_rows)
    if type(in_row) is not int or type(rows) is not int:
        return None
    return {"max_in_row": _clamp(in_row, schema.MAX_WINDOW_COUNT),
            "max_rows": _clamp(rows, schema.MAX_WINDOW_COUNT)}


def _describe_dialog(dialog_id, dialog, auto):
    try:
        key = str(schema.string_id(int(dialog_id), "dialog_id"))
    except Exception:
        return None
    kind = _bounded_name(_tuning_name(dialog), "dialog.kind")
    if kind is None:
        return None
    try:
        owner = dialog._owner()  # a weakref to the owner's SimInfo
        owner_id = None if owner is None else str(owner.id)
    except Exception:
        owner_id = None
    entry = {"dialog_id": key, "kind": kind, "owner_id": owner_id,
             "title_key": None, "text_key": None, "auto_respond": bool(auto)}
    for field, read in (("title_key", lambda: dialog.title),
                        ("text_key", lambda: dialog.text)):
        try:
            entry[field] = _string_key(read())
        except Exception:
            entry[field] = None
    entry["responses"] = _dialog_responses(dialog)
    entry["rows"] = _dialog_rows(dialog)
    entry["select"] = select_of(dialog)
    entry["counts"] = counts_of(dialog)
    # 2.31.0 (§11): who holds the window, and its text fields only while she holds it.
    facts = _WINDOWS.get(key, {})
    entry["held"] = facts.get("held") is True
    entry["cause"] = facts.get("cause")
    entry["text_inputs"] = facts.get("text_inputs") if entry["held"] else None
    return entry


def _dialog_rows(dialog):
    """2.18.0: the rows a picker dialog offers (picker_rows, plain list on UiDialogObjectPicker;
    bytecode ui/ui_dialog_picker): option id, name, whether it can be picked, and its price
    (RecipePickerRow.price, ObjectPickerRow.cost). Enabled rows first; none for a plain pop-up."""
    try:
        rows = list(dialog.picker_rows or ())
    except Exception:
        return []
    found = []
    for row in rows:
        try:
            option_id = int(row.option_id)
        except Exception:
            continue
        if option_id < 0:
            continue
        name_key = None
        for read in (lambda: row.name, lambda: row.display_name):
            try:
                name_key = _string_key(read())
            except Exception:
                name_key = None
            if name_key is not None:
                break
        try:
            enabled = row.is_enable is True
        except Exception:
            enabled = False
        price = None
        for read in (lambda: row.price, lambda: row.cost):
            try:
                value = read()
            except Exception:
                continue
            if type(value) is int and value >= 0:
                price = value
                break
        found.append({"option_id": str(option_id), "name_key": name_key, "enabled": enabled, "price": price})
    found.sort(key=lambda item: not item["enabled"])
    return found[:schema.MAX_DIALOG_ROWS]


def read_dialogs():
    """2.15.2: the game's pop-ups (live 2026-10-05: a question about a new like was
    answered for her and never sensed). Open ones come from the dialog
    service's `_active_dialogs` (dialog id -> dialog; bytecode ui/ui_dialog_service),
    newest last; a dialog gone since the last sample is reported closed with the
    answer the game stored on it (`response`). A dialog waiting on the game's own
    auto-response is marked. Read only: no dialog is answered or cancelled here."""
    global _DIALOGS_OPEN
    try:
        service = services.ui_dialog_service()
        active = list(service._active_dialogs.items())
    except Exception:
        return None
    try:
        auto = set(service._auto_respond_alarm_handles)
    except Exception:
        auto = set()
    current = {}
    for dialog_id, dialog in active:
        entry = _describe_dialog(dialog_id, dialog, dialog_id in auto)
        if entry is not None:
            current[entry["dialog_id"]] = (dialog, entry)
    closed = []
    for key, (dialog, entry) in _DIALOGS_OPEN.items():
        if key in current:
            continue
        try:
            response = _response_name(dialog.response)
        except Exception:
            response = None
        closed.append({"dialog_id": key, "kind": entry["kind"],
                       "title_key": entry["title_key"], "text_key": entry["text_key"],
                       "response": response})
    _DIALOGS_OPEN = current
    for stale in [key for key in _WINDOWS if key not in current]:
        del _WINDOWS[stale]
    _remember_dialog_speeds(set(current))
    opened = [entry for _, entry in current.values()]
    truncated = (len(opened) > schema.MAX_DIALOGS or len(closed) > schema.MAX_DIALOGS)
    return {"open": opened[-schema.MAX_DIALOGS:], "closed": closed[-schema.MAX_DIALOGS:],
            "truncated": truncated}


def read_presence(lab_sim_id, hidden_flags=ALL_HIDDEN_REASONS, body_position=None,
                  now_ticks=None):
    """Every instanced Sim in the zone, her body first, then nearest first.
    Returns (presence, dropped, skipped); dropped counts the Sims past the cap,
    {"on_lot": n, "other": m}.

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
    situations = read_situations()
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
                                     now_ticks, situations)
        except Exception:
            row = None
        if row is None:
            skipped += 1
            continue
        presence.append(row)
    # D45 (live 2.15.0): passers-by on the street filled the cap by distance and could
    # push a guest out. Her body first, then everyone on the lot, then the nearest.
    presence.sort(key=lambda row: (0 if row["is_body"] else 1,
                                   0 if row["on_lot"] is True else 1,
                                   row["distance_m"] if row["distance_m"] is not None else 1e9,
                                   row["id"]))
    left_out = presence[schema.MAX_PRESENCE:]
    dropped = {"on_lot": sum(1 for row in left_out if row["on_lot"] is True),
               "other": sum(1 for row in left_out if row["on_lot"] is not True)}
    return presence[:schema.MAX_PRESENCE], dropped, skipped


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
    presence, dropped, skipped = ([], {"on_lot": 0, "other": 0}, None)
    social, social_truncated = ([], False)
    zone = zone_snapshot(sim)
    if lab_id is not None:
        try:
            presence, dropped, skipped = read_presence(
                lab_id, body_position=zone["position"], now_ticks=now_ticks)
        except Exception:
            presence, dropped, skipped = ([], {"on_lot": 0, "other": 0}, None)
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
    if social_truncated:
        complete = False
    missingness = {}
    missed = []
    if skipped is None:
        missed.append("unreadable")
    elif skipped > 0:
        missed.append("skipped %d Sims" % skipped)
    if not any(item["is_body"] for item in presence):
        missed.append("body absent")
    if dropped["on_lot"]:
        missed.append("%d on the lot not listed" % dropped["on_lot"])
    if missed:
        # D40: a presence read that missed anyone, her body included, says so.
        complete = False
        missingness["presence"] = {"status": "MISSING", "detail": ", ".join(missed)}
    if dropped["other"]:
        # D45: Sims off the lot past the cap are named as left out; the lot stays whole.
        missingness["presence_nearby"] = {
            "status": "MISSING", "detail": "%d off the lot not listed" % dropped["other"]}
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
        row["place"] = read_place(sim_info)
    except Exception:
        row["place"] = None
    try:
        row["dialogs"] = read_dialogs()
    except Exception:
        row["dialogs"] = None
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


# D46 (live 2.15.0): the game's own settings (gender options, walk style, phone case,
# hidden) took her 12 trait slots. TraitType values, bytecode traits/trait_type:
# WALKSTYLE 2, HIDDEN 4, TAILSTYLE 7, GENDER_OPTIONS 8, SIM_PHONE 9,
# ROBOT_MODULE_LOCKED 19, INFANT_CARRIER 32.
MECHANICAL_TRAIT_TYPES = frozenset((2, 4, 7, 8, 9, 19, 32))


def _mechanical_trait(trait):
    """A trait that is a game setting, not part of who she is (a tuned class
    attribute, plain read). Unreadable counts as not mechanical."""
    try:
        return int(trait.trait_type) in MECHANICAL_TRAIT_TYPES
    except Exception:
        return False


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
        if _mechanical_trait(trait):
            continue
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
            "funds": funds, "careers": _own_careers(sim_info), "wants": _own_wants(sim_info)}


def _own_wants(sim_info):
    """2.30.0 (the User: she should solve her own problems, so she sees the game's wants and fears):
    plain reads (bytecode whims/whims_tracker, situations/situation_goal): sim_info `_whim_tracker`
    (absent below full LOD), its `_whim_slots`, each slot's `whim`, `goal_instance` and `whim_type`
    (CONFRONTATION is a fear), the goal's tuned `display_name` / `display_tooltip`, `_locked`, `_count`,
    `_iterations` and `expiration_time`. Never `goal.score` (runs tests) nor any tracker method."""
    try:
        tracker = sim_info._whim_tracker
    except Exception:
        return None
    if tracker is None:
        return None
    try:
        slots = list(tracker._whim_slots)
    except Exception:
        return None
    wants = []
    for slot in slots:
        try:
            goal, whim = slot.goal_instance, slot.whim
        except Exception:
            continue
        if goal is None or whim is None:
            continue
        name = _bounded_name(_type_name(whim), "want")
        if name is None:
            continue
        try:
            fear = slot.whim_type.name == "CONFRONTATION"
        except Exception:
            fear = False
        keys = []
        for read in (lambda: goal.display_name, lambda: goal.display_tooltip):
            try:
                keys.append(_string_key(read()))
            except Exception:
                keys.append(None)
        try:
            locked = goal._locked is True
        except Exception:
            locked = False
        counts = []
        for read in (lambda: goal._count, lambda: goal._iterations):
            try:
                value = read()
            except Exception:
                value = None
            counts.append(value if type(value) is int else None)
        until = None
        try:
            expiry = goal.expiration_time
            if expiry is not None:
                hour, minute = expiry.hour(), expiry.minute()
                if type(hour) is int and type(minute) is int and 0 <= hour < 24 and 0 <= minute < 60:
                    until = [hour, minute]
        except Exception:
            until = None
        wants.append({"want": name, "text_key": keys[0], "tip_key": keys[1], "fear": fear,
                      "locked": locked, "done": counts[0], "of": counts[1], "until": until})
        if len(wants) >= schema.MAX_SELF_WANTS:
            break
    return sorted(wants, key=lambda item: (not item["fear"], item["want"]))


def _own_careers(sim_info):
    """2.19.0 (live 2026-10-06: the save gave her a culinary job she did not know she had):
    her jobs. Plain reads (bytecode careers/career_base, career_tuning): career_tracker
    `_careers`, each career's `_current_track.career_name` and the title of
    `_current_track.career_levels[_level]` (string factories), `_user_level`, `_at_work`."""
    try:
        values = list(sim_info.career_tracker._careers.values())
    except Exception:
        return None
    careers = []
    for career in values[:schema.MAX_SELF_CAREERS]:
        name = _bounded_name(_type_name(type(career)), "career")
        if name is None:
            continue
        name_key = title_key = None
        try:
            track = career._current_track
            name_key = _string_key(track.career_name)
            title_key = _string_key(track.career_levels[career._level].title)
        except Exception:
            pass
        try:
            level = career._user_level
        except Exception:
            level = None
        try:
            at_work = career._at_work is True
        except Exception:
            at_work = False
        careers.append({"career": name, "text_key": name_key, "title_key": title_key,
                        "level": level if type(level) is int else None, "at_work": at_work})
    return sorted(careers, key=lambda item: item["career"])


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
