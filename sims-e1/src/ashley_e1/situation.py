"""S1: what is on the lot, as the game holds it. Plain attribute reads only.

One fact row per object: class, definition, position, room, every object state by
name (freshness, dish location, dirtiness, ...), statistics and commodities by name
with their current values (servings among them), and, for crafted things, the
recipe, its display-name string keys and the crafter. Sims are left out: presence
rows already carry them. Rows stay partial until the footer, like the other scans.

Bytecode (1.128): StateComponent keeps `_states` (state -> value); statistic
trackers keep `_statistics` (type -> instance); Statistic.get_value returns
`_modified_value`, BaseStatistic `_value`; CraftingComponent keeps
`_crafting_process`; CraftingProcess keeps `_recipe`, `_crafter_sim_id`, `crafter`.
"""
import json
import os
import time

from . import observers
from . import schema
from .writer import append_atlas_line

MAX_STATES = 24
MAX_STATS = 16


def _name(value, limit=96):
    try:
        name = value.__name__
    except Exception:
        return None
    return name[:limit] if isinstance(name, str) and name else None


def _int_id(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return None


def _states(obj):
    try:
        component = obj.state_component
        states = component._states
        items = list(states.items())
    except Exception:
        return None
    found = {}
    for state, value in items:
        key = _name(state)
        if key is None:
            continue
        found[key] = _name(value)
    return {key: found[key] for key in sorted(found)[:MAX_STATES]}


def _stat_value(instance, now_ticks):
    """Current value without calling get_value or _update_value (D25 for commodities)."""
    try:
        modified = instance._modified_value
    except Exception:
        modified = None
    if type(modified) in (int, float):
        return float(modified)
    try:
        value = instance._value
    except Exception:
        return None
    if type(value) not in (int, float):
        return None
    try:
        updated = instance._last_update
    except Exception:
        updated = None
    if type(updated) is int and type(now_ticks) is int and now_ticks >= updated:
        current = observers._current_value(instance, float(value), now_ticks - updated)
        if current is not None:
            return current
    return float(value)


def _stats(obj, now_ticks):
    found = {}
    # D42: the existing trackers only; the properties add a component to the object.
    for tracker in observers.stat_trackers(obj):
        try:
            items = list(tracker._statistics.items())
        except Exception:
            continue
        for stat_type, instance in items:
            name = _name(stat_type)
            if name is None or instance is None or name in found:
                continue
            value = _stat_value(instance, now_ticks)
            if value is not None:
                found[name] = round(value, 2)
    return {key: found[key] for key in sorted(found)[:MAX_STATS]}


def _crafter_name(crafter):
    if crafter is None:
        return None
    return observers._sim_name(crafter)


def _craft(obj):
    try:
        component = obj.crafting_component
        process = None if component is None else component._crafting_process
    except Exception:
        return None
    if process is None:
        return None
    try:
        recipe = process._recipe
    except Exception:
        recipe = None
    row = {"recipe": _name(recipe), "name_key": None, "multi_name_key": None,
           "crafter_id": None, "crafter": None}
    if recipe is not None:
        try:
            row["name_key"] = observers._string_key(recipe.name)
        except Exception:
            pass
        try:
            row["multi_name_key"] = observers._string_key(recipe.multi_serving_name)
        except Exception:
            pass
    try:
        row["crafter_id"] = _int_id(process._crafter_sim_id)
    except Exception:
        pass
    try:
        row["crafter"] = _crafter_name(process.crafter)
    except Exception:
        pass
    return row


def _tags(obj):
    """Catalogue tags (`definition.build_buy_tags`), by name, at most 12."""
    try:
        tags = list(obj.definition.build_buy_tags or ())
    except Exception:
        return None
    names = set()
    for tag in tags:
        try:
            name = tag.name
        except Exception:
            name = None
        if not isinstance(name, str):
            try:
                name = str(int(tag))
            except Exception:
                continue
        names.add(name[:64])
    return sorted(names)[:12]


def _users(obj):
    """Who holds a reservation on it (ReservationMixin `_reservation_handlers`; the
    `in_use` property reads only that), parts included. Sim ids, at most 4."""
    holders = []
    for owner in [obj] + list(_parts(obj)):
        try:
            handlers = list(owner._reservation_handlers or ())
        except Exception:
            continue
        for handler in handlers:
            try:
                holders.append(_int_id(handler.sim.id))
            except Exception:
                holders.append(None)
    return sorted({holder for holder in holders if holder is not None})[:4], bool(holders)


def _parts(obj):
    try:
        return tuple(obj.parts or ())
    except Exception:
        return ()


def _rates(obj, now_ticks):
    """Per game minute, for commodities that move (freshness among them), from the
    D25-checked decay math: the change over the next 60 game minutes."""
    found = {}
    try:
        items = list(observers.stat_trackers(obj)[1]._statistics.items())
    except Exception:
        return found
    for stat_type, instance in items:
        name = _name(stat_type)
        if name is None or instance is None:
            continue
        try:
            value = float(instance._value)
            updated = instance._last_update
        except Exception:
            continue
        age = now_ticks - updated if type(updated) is int and type(now_ticks) is int \
            and now_ticks >= updated else 0
        now = observers._current_value(instance, value, age)
        later = observers._current_value(instance, value, age + 60 * observers.TICKS_PER_SIM_MINUTE)
        if now is None or later is None or later == now:
            continue
        found[name] = round((later - now) / 60.0, 4)
    return {key: found[key] for key in sorted(found)[:8]}


def object_fact(obj, now_ticks):
    """One object's facts, or None for Sims and unreadable objects."""
    try:
        if obj.is_sim is True:
            return None
    except Exception:
        pass
    try:
        object_id = _int_id(obj.id)
    except Exception:
        object_id = None
    if object_id is None:
        return None
    try:
        definition_id = _int_id(obj.definition.id)
    except Exception:
        definition_id = None
    position = observers._position(obj)
    users, in_use = _users(obj)
    return {
        "kind": "object", "object_id": object_id, "definition_id": definition_id,
        "class": _name(type(obj)), "position": position,
        "room": observers._room(obj, position),
        "states": _states(obj), "stats": _stats(obj, now_ticks), "craft": _craft(obj),
        # S1 extras (2.14.0): catalogue tags, who is using it, how its commodities move.
        "tags": _tags(obj), "in_use": in_use, "used_by": users,
        "rates": _rates(obj, now_ticks),
    }


class SituationScan(object):
    def __init__(self, objects, out_path, now_ticks, header=None, budget_ms=5.0,
                 max_per_chunk=50, clock=time.perf_counter):
        self._jobs = list(objects)
        self.out_path = out_path
        self.partial = out_path + ".partial"
        self.now_ticks = now_ticks
        self.budget_ms = budget_ms
        self.max_per_chunk = max_per_chunk
        self.clock = clock
        self.state = "running"
        self._index = 0
        self._count = 0
        self._errors = 0
        self.chunks = 0
        self._chunk_ms = []
        row = {"kind": "situation_header", "probe_version": schema.PROBE_VERSION,
               "sims_build": schema.SIMS_BUILD, "total": len(self._jobs),
               "started_ms": int(time.time() * 1000), "ticks": now_ticks}
        row.update(header or {})
        append_atlas_line(self.partial, _line(row))

    def step(self):
        if self.state != "running":
            return
        start = self.clock()
        processed = 0
        while self._index < len(self._jobs):
            if processed >= self.max_per_chunk:
                break
            if (self.clock() - start) * 1000.0 >= self.budget_ms:
                break
            obj = self._jobs[self._index]
            self._index += 1
            processed += 1
            try:
                row = object_fact(obj, self.now_ticks)
            except Exception as error:
                row = {"kind": "object_error", "error": type(error).__name__[:64]}
                self._errors += 1
            if row is None:
                continue
            self._count += 1
            append_atlas_line(self.partial, _line(row))
        self.chunks += 1
        self._chunk_ms.append((self.clock() - start) * 1000.0)
        if self._index >= len(self._jobs):
            footer = {"kind": "situation_footer", "count": self._count,
                      "errors": self._errors, "chunks": self.chunks,
                      "max_chunk_ms": max(self._chunk_ms) if self._chunk_ms else 0}
            append_atlas_line(self.partial, _line(footer))
            os.replace(self.partial, self.out_path)
            self.state = "done"

    def progress(self):
        return {"state": self.state, "done": self._index, "total": len(self._jobs),
                "chunks": self.chunks,
                "max_chunk_ms": max(self._chunk_ms) if self._chunk_ms else 0,
                "file": self.out_path if self.state == "done" else self.partial}


def _line(row):
    return json.dumps(row, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
