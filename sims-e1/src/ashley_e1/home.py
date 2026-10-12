"""2.40.0 (W13 P2, probe: home): the things list, the catalogue, her save, and her home edits (buy, place, move, sell).

Game thread only. Every game read and effect goes through e2_actuator, the only module that calls the game's effects
(tools/check_guards.py). The removal of a household object is in two places only: sell, and the removal of the object
this command just created after a failed placement (the money is refunded first). This module holds the shapes and
bounds, the save floor, the things and catalogue rows, the placement facts and the command flow. Her home is her call:
a purchase or move that cuts a route is reported in the result, never refused.
"""

import json
import time

from . import e2_lineage
from . import schema

try:
    from . import e2_actuator
except ImportError:
    e2_actuator = None
try:
    from . import observers
except ImportError:
    observers = None
try:
    import services  # TARGET_BYTECODE: sim_info_manager, as e2_control reads it.
except ImportError:
    services = None

COMMANDS = ("save", "buy", "place", "move", "sell", "catalog_dump")
# 2.40.0: the save floor (15 real minutes between her saves, the User's ruling of 2026-10-12).
SAVE_FLOOR_S = 15 * 60
SAVE_CONFIRM_S = 120
THINGS_MAX = 600
# The catalogue parts: at most this many items, and about this many bytes of JSON (a record is 48 KiB). The things
# list is written by the probe's lists tick (reach.ListWriter), not here.
CATALOG_PART_ITEMS = 256
CATALOG_PART_BYTES = 40 * 1024
NEAR_M = 1.5
NEAR_LIMIT = 4
WALL_LIMIT = 2
ROUTE_KINDS = ("door", "bed", "toilet", "fridge")
THING_WHERE = ("room", "inventory", "outside")
STATES_MAX = 4
TAGS_MAX = 8
CATEGORY_MAX = 4
PLACEMENT_FLAGS = ("floor", "wall", "surface")
# Build items (structure), never furniture or decor, by the last word of the class name (CamelCase words).
BUILD_LAST_WORDS = ("wall", "floor", "roof", "stair", "stairs", "door", "window", "gate", "archway", "fence",
                    "portal", "terrain")
HIDDEN_TAG_WORDS = ("cheat", "debug", "hidden")


class HomeState(object):
    """What the home commands remember for one controller: the time of her last save, the save still waiting for its
    result, the objects she vacated (for `instead`), and whether the save-complete callback is subscribed."""

    def __init__(self):
        self.saved_at = None
        self.pending_save = None
        self.vacated = {}
        self.subscribed = False
        self.callback = None


def state_of(control):
    """The home state of this controller, kept on it (created on first use), so a re-arm keeps the save floor."""
    try:
        return control._home_state
    except AttributeError:
        state = HomeState()
        control._home_state = state
        return state


# ----------------------------------------------------------------------------------------------- shapes and bounds

def _digits(value):
    """A game id as its decimal string when it is a positive int (or digits), else None."""
    if type(value) is bool:
        return None
    if type(value) is int and value > 0:
        return str(value)
    if type(value) is str and value.isdigit() and 0 < len(value) <= 20:
        return value
    return None


def _int_or_none(value):
    return value if type(value) is int and not isinstance(value, bool) else None


def _bool_or_none(value):
    return value if type(value) is bool else None


def _words(name):
    """The CamelCase words of a class name, lower case (no regular expressions: the guards allow no re import)."""
    words, current = [], ""
    for ch in str(name):
        if ch.isupper() and current:
            words.append(current.lower())
            current = ""
        if ch.isalnum():
            current += ch
    if current:
        words.append(current.lower())
    return words


def is_build_class(name):
    """True for a build item (a wall, floor, roof, stair, door, window, terrain ...) by its class name's last word."""
    words = _words(name)
    return bool(words) and words[-1] in BUILD_LAST_WORDS


def route_kind(name, portal):
    """The route a lot object gives her, by its class name: door (a portal), bed, toilet or fridge; None for others."""
    if portal:
        return "door"
    low = str(name).lower()
    if "toilet" in low:
        return "toilet"
    if "fridge" in low or "refrigerator" in low:
        return "fridge"
    if "bed" in _words(name):
        return "bed"
    return None


def purchasable(price, tag_names):
    """2.40.0: a catalogue item she may buy: a price above zero, and no tag that says cheat, debug or hidden."""
    if type(price) is not int or isinstance(price, bool) or price <= 0:
        return False
    for tag in tag_names or ():
        low = str(tag).lower()
        if any(word in low for word in HIDDEN_TAG_WORDS):
            return False
    return True


def _size(item):
    return len(json.dumps(item, separators=(",", ":"), ensure_ascii=True)) + 1


def pack(items, per_part, budget):
    """The items in parts of at most per_part items and about budget bytes each (an empty list is one empty part)."""
    parts, current, used = [], [], 0
    for item in items:
        size = _size(item)
        if current and (len(current) >= per_part or used + size > budget):
            parts.append(current)
            current, used = [], 0
        current.append(item)
        used += size
    if current or not parts:
        parts.append(current)
    return parts


def shape_state(raw):
    """A thing's state as {state, value} (a name and a plain value); None when either is unreadable."""
    if type(raw) is not dict:
        return None
    name = raw.get("state")
    value = raw.get("value")
    if type(name) is not str or not 1 <= len(name) <= 64:
        return None
    if type(value) is bool or type(value) not in (int, float, str, type(None)):
        return None
    return {"state": name, "value": value}


def shape_thing(raw):
    """2.40.0: one row of the `things` list from a raw read (a dict), or None when it has no id or no place."""
    if type(raw) is not dict:
        return None
    object_id = _digits(raw.get("object_id"))
    where = raw.get("where")
    room_id = _digits(raw.get("room_id")) if where == "room" else None
    if object_id is None or where not in THING_WHERE or (where == "room" and room_id is None):
        return None
    states = [shape_state(item) for item in (raw.get("states") or ())[:STATES_MAX]]
    placement = raw.get("placement")
    return {
        "object_id": object_id,
        "definition_id": _digits(raw.get("definition_id")),
        "name_key": _digits(raw.get("name_key")),
        "where": where,
        "room_id": room_id,
        "value": _int_or_none(raw.get("value")),
        "made_by_her": _bool_or_none(raw.get("made_by_her")),
        "states": [state for state in states if state is not None],
        "in_use": _bool_or_none(raw.get("in_use")),
        "count": _int_or_none(raw.get("count")),
        "placement": placement if placement in PLACEMENT_FLAGS else None,
    }


def things_items(raw_rows):
    """The things list: the shaped rows, in the order read, at most THINGS_MAX. Build items (walls, floors, roofs,
    stairs, terrain) are not things; a Sim is never one (the raw rows leave both out already)."""
    items = []
    for raw in raw_rows or ():
        if type(raw) is dict and is_build_class(raw.get("class_name") or ""):
            continue
        item = shape_thing(raw)
        if item is not None:
            items.append(item)
        if len(items) >= THINGS_MAX:
            break
    return items


def shape_catalog(raw):
    """2.40.0: one catalogue item from a raw read, or None (no id, not a price, a Sim, or a build item)."""
    if type(raw) is not dict:
        return None
    definition_id = _digits(raw.get("definition_id"))
    price = _int_or_none(raw.get("price"))
    if definition_id is None or price is None or price < 0 or raw.get("sim") is True:
        return None
    if is_build_class(raw.get("class_name") or ""):
        return None
    tags = [str(tag)[:64] for tag in (raw.get("tags") or ())[:TAGS_MAX]]
    categories = [str(item)[:40] for item in (raw.get("buy_category") or ())[:CATEGORY_MAX]]
    placement = raw.get("placement")
    if placement is not None:
        placement = [flag for flag in placement if flag in PLACEMENT_FLAGS]
    return {"definition_id": definition_id, "price": price, "buy_category": categories,
            "placement": placement, "tags": tags, "purchasable": purchasable(price, tags)}


def catalog_items(raw_rows):
    """The catalogue rows: furniture and decor with a price (build items and Sims are left out)."""
    items = []
    for raw in raw_rows or ():
        item = shape_catalog(raw)
        if item is not None:
            items.append(item)
    return items


def catalog_parts(rev, items):
    """The `catalog` record payloads: parts of CATALOG_PART_ITEMS items, each under CATALOG_PART_BYTES."""
    parts = pack(items, CATALOG_PART_ITEMS, CATALOG_PART_BYTES)
    return [{"catalog_rev": rev, "part": index, "parts": len(parts), "items": part}
            for index, part in enumerate(parts)]


# ----------------------------------------------------------------------------------------------------- the rules

def save_gate(saved_at, now):
    """None when she may save now; else the whole seconds left until she may (saved_at None: never saved)."""
    if saved_at is None:
        return None
    left = SAVE_FLOOR_S - (now - saved_at)
    if left <= 0:
        return None
    return int(left) + 1


def routes_lost(before, after):
    """The routes she could walk before and cannot now, in ROUTE_KINDS order. A route is cut only when the game's own
    check reads False now (a portal reads None, so a door is never reported cut)."""
    before = before or {}
    after = after or {}
    return [kind for kind in ROUTE_KINDS if before.get(kind) is True and after.get(kind) is False]


def placement_facts(room_id, wall, near, facing_id=None, lost=(), price=None, funds=None):
    """2.40.0: the plain facts of a home edit's result. near is a list of {object_id, distance, portal, window}, read
    for the placed object. wall_has (a door or a window on its wall) only when it backs on a wall. beside: the nearest
    other objects within NEAR_M. Nothing here is text."""
    near = sorted((item for item in (near or ()) if item.get("distance") is not None and
                   item["distance"] <= NEAR_M and item.get("object_id")),
                  key=lambda item: item["distance"])
    wall_has = []
    if wall is True:
        wall_has = [item["object_id"] for item in near if item.get("portal") or item.get("window")][:WALL_LIMIT]
    beside = [item["object_id"] for item in near if item["object_id"] not in wall_has][:NEAR_LIMIT]
    return {"room_id": _digits(room_id), "wall": _bool_or_none(wall), "wall_has": wall_has, "beside": beside,
            "facing_id": _digits(facing_id), "routes_lost": list(lost), "price": _int_or_none(price),
            "funds": _int_or_none(funds)}


RESULT_KEYS = ("room_id", "wall", "wall_has", "beside", "facing_id", "routes_lost", "price", "funds", "value")


def sell_facts(value, funds):
    """2.40.0: the result of a sale: what she was paid and her funds now."""
    return {"value": _int_or_none(value), "funds": _int_or_none(funds)}


# ----------------------------------------------------------------------------------------------- the list writers

def write_catalog(control, raw_rows, rev=None):
    """2.40.0: the catalogue record in parts (catalog_dump). rev is the game's version string."""
    items = catalog_items(raw_rows)
    for payload in catalog_parts(rev or schema.SIMS_BUILD, items):
        control._event("catalog", payload)
    return len(items)


# ------------------------------------------------------------------------------------------------- the commands

def _say(control, connection, text):
    try:
        control._say(connection, text)
    except Exception:
        pass


def _start(control, act_id, connection):
    """The common start of a verb: a duplicate is refused, as an act is; False when it may not run."""
    if act_id in control.act_ids:
        _say(control, connection, "ACT_REJECT DUPLICATE")
        return False
    control.act_ids.add(act_id)
    if not control.available():
        control._act_event(act_id, "REJECTED", code="E2_UNAVAILABLE")
        _say(control, connection, "ACT_REJECT E2_UNAVAILABLE")
        return False
    return True


def _reject(control, act_id, connection, code, detail=None, reason_key=None, phase="REJECTED", **base):
    control._act_event(act_id, phase, code=code, detail=None if detail is None else str(detail)[:128],
                       reason_key=reason_key, **base)
    _say(control, connection, "ACT_%s %s" % (phase, code))
    return False


def _body(control):
    """The refusal code for her body (as an act checks it), else (None, sim_info, sim)."""
    if control._state() != "SAMPLING":
        return "NOT_SAMPLING", None, None
    if control.lineage_class == e2_lineage.BODY_MISMATCH:
        return "BODY_MISMATCH", None, None
    if observers is None or services is None:
        return "BODY_UNAVAILABLE", None, None
    sim_info, sim = observers.select_lab_body(services.sim_info_manager().get_all(),
                                              observers.ALL_HIDDEN_REASONS)
    if sim is None:
        return "BODY_UNAVAILABLE", None, None
    if control.designated_sim_id is not None and str(sim_info.id) != control.designated_sim_id:
        return "BODY_MISMATCH", None, None
    armed = (control._armed_snapshot() or {}).get("sim_id")
    if armed is not None and str(sim_info.id) != str(armed):
        return "BODY_MISMATCH", None, None
    active = observers.active_sim_id()
    if active is not None and active != str(sim_info.id):
        return "BODY_MISMATCH", None, None
    return None, sim_info, sim


def _home_gate(control):
    """(refusal code or None, sim_info, sim) for a home edit: her body, her home lot, and not build mode."""
    code, sim_info, sim = _body(control)
    if code is not None:
        return code, None, None
    if not e2_actuator.at_home(sim_info.household_id):
        return "NOT_HOME", None, None
    if e2_actuator.build_mode() is True:
        return "BUILD_MODE", None, None
    return None, sim_info, sim


def _route_reach(sim):
    """Per route (door, bed, toilet, fridge): True when one lot object of the kind is reachable (the game's own check,
    reachable), False when the check reads False for the ones it can read, else None. Read only."""
    reach = {}
    if e2_actuator is None:
        return reach
    for obj in e2_actuator.lot_objects():
        kind = route_kind(e2_actuator.class_name(obj), e2_actuator.is_portal(obj))
        if kind is None:
            continue
        value = e2_actuator.reachable(sim, obj)
        previous = reach.get(kind)
        if value is True or previous is True:
            reach[kind] = True
        elif value is False or previous is False:
            reach[kind] = False
        else:
            reach[kind] = None
    return reach


def movable(obj):
    """2.40.0: an object she may move: not a Sim, a door, or a build item (a wall, floor, roof, stair, window)."""
    return (e2_actuator.is_sim(obj) is not True and not e2_actuator.is_portal(obj) and
            not is_build_class(e2_actuator.class_name(obj)))


def sellable(obj):
    """2.40.0: an object she may sell: the same as movable (a Sim, door, window, wall or stair is never sold)."""
    return movable(obj)


def _facts(obj, sim, before, price=None, funds=None):
    """The result facts of a placed object: room, wall, what is near, and the routes cut since `before`."""
    after = _route_reach(sim)
    near = e2_actuator.near_objects(obj, NEAR_M)
    return placement_facts(e2_actuator.room_of(obj), e2_actuator.is_wall_placed(obj), near,
                           lost=routes_lost(before, after), price=price, funds=funds)


def _vacate(control, obj):
    """Remember where an object was before it is sold or moved, so `instead` can name that spot later."""
    state = state_of(control)
    spot = e2_actuator.spot_of(obj)
    if spot is not None:
        state.vacated[str(obj.id)] = spot


def _spot(control, obj, sim, place):
    """(spot, refusal). `instead` names the spot its target vacated, and is refused NOT_FREE while the target still
    stands there; the other relations are the game's own search for a spot."""
    if place["rel"] == "instead":
        target = str(place["target_id"])
        vacated = state_of(control).vacated.get(target)
        target_obj = e2_actuator.find_object(target)
        if target_obj is not None and vacated is not None and \
                e2_actuator.spot_key(e2_actuator.spot_of(target_obj)) == e2_actuator.spot_key(vacated):
            return None, "NOT_FREE"
        if vacated is None:
            return None, "NO_SPOT"
        return vacated, None
    return e2_actuator.find_spot(obj, sim, place), None


def _finish(control, act_id, connection, phase, code, result=None, **base):
    control._act_event(act_id, phase, code=code, result=result, **base)
    _say(control, connection, "ACT_%s %s" % (phase, code))
    return phase == "FINISHED"


def cmd_save(control, args, connection):
    """2.40.0: her save, to her own slot (the game's save, as its Save button makes it). Finished when the game's
    save-complete callback reports success; refused when no player slot is loaded, when the save lock holds it, and
    within the floor of her last save."""
    act_id = args["act_id"]
    if not _start(control, act_id, connection):
        return False
    base = {"object_id": None, "guid64": None}
    _expire_save(control, connection)
    code, sim_info, _sim = _body(control)
    if code is not None:
        return _reject(control, act_id, connection, code, **base)
    slot_id, slot_name, locked, lock_key = e2_actuator.save_slot()
    if slot_id is None or slot_id <= 1:
        return _reject(control, act_id, connection, "NO_PLAYER_SLOT", **base)
    if locked is None:
        return _reject(control, act_id, connection, "SAVE_FAILED", detail="lock unreadable", **base)
    if locked:
        return _reject(control, act_id, connection, "SAVE_LOCKED", reason_key=lock_key, **base)
    state = state_of(control)
    left = save_gate(state.saved_at, time.time())
    if left is not None:
        return _reject(control, act_id, connection, "SAVE_TOO_SOON", detail="%d s" % left, **base)
    control._act_event(act_id, "ACCEPTED", **base)
    _subscribe_save(control, state)
    state.saved_at = time.time()
    try:
        e2_actuator.save_now(slot_id, slot_name)
    except Exception as error:
        state.saved_at = None
        return _reject(control, act_id, connection, "SAVE_FAILED", detail=type(error).__name__, **base)
    state.pending_save = (act_id, time.time(), connection)
    _say(control, connection, "ACT_ACCEPTED %s" % act_id)
    return True


def _subscribe_save(control, state):
    if state.subscribed:
        return
    state.subscribed = True

    def on_complete(*_args, **_kwargs):
        _save_complete(control)

    state.callback = on_complete
    try:
        e2_actuator.subscribe_saves(on_complete)
    except Exception:
        state.subscribed = False


def _save_complete(control):
    """The game's save-complete callback: FINISHED SAVED for the save waiting for it."""
    state = state_of(control)
    pending = state.pending_save
    if pending is None:
        return
    state.pending_save = None
    act_id, _at, connection = pending
    _finish(control, act_id, connection, "FINISHED", "SAVED", object_id=None, guid64=None)


def _expire_save(control, connection):
    """A save with no callback after SAVE_CONFIRM_S is UNKNOWN: the game may have saved or not."""
    state = state_of(control)
    pending = state.pending_save
    if pending is None or time.time() - pending[1] < SAVE_CONFIRM_S:
        return
    state.pending_save = None
    act_id, _at, old_connection = pending
    _finish(control, act_id, old_connection, "UNKNOWN", "SAVE_UNCONFIRMED", object_id=None, guid64=None)


def cmd_buy(control, args, connection):
    """2.40.0: buy a catalogue item and place it. The spot is found first (for the item's footprint the object is made
    unplaced, and removed again if no spot is found or the money is not there); only then the charge; then the move.
    A failure after the charge refunds the money and removes the new object."""
    act_id = args["act_id"]
    if not _start(control, act_id, connection):
        return False
    base = {"object_id": None, "guid64": None}
    code, sim_info, sim = _home_gate(control)
    if code is not None:
        return _reject(control, act_id, connection, code, **base)
    definition = e2_actuator.definition(args["definition_id"])
    price = e2_actuator.definition_price(definition)
    if not purchasable(price, e2_actuator.definition_tags(definition)):
        return _reject(control, act_id, connection, "NOT_PURCHASABLE", **base)
    if args.get("max_price") is not None and price > args["max_price"]:
        return _reject(control, act_id, connection, "PRICE_ABOVE", detail="price %d" % price, **base)
    funds = e2_actuator.household_funds(sim_info.household_id)
    if funds is None or not e2_actuator.can_afford(funds, price):
        return _reject(control, act_id, connection, "NO_FUNDS", **base)
    control._act_event(act_id, "ACCEPTED", **base)
    before = _route_reach(sim)
    obj = e2_actuator.create_unplaced(definition)
    if obj is None:
        return _finish(control, act_id, connection, "REJECTED", "PLACE_FAILED", **base)
    spot, refused = _spot(control, obj, sim, args["place"])
    if refused is not None or spot is None:
        e2_actuator.remove_created(obj)
        return _finish(control, act_id, connection, "REJECTED", refused or "NO_SPOT", **base)
    if not e2_actuator.funds_try_remove(funds, price, sim):
        e2_actuator.remove_created(obj)
        return _finish(control, act_id, connection, "REJECTED", "NO_FUNDS", **base)
    try:
        e2_actuator.place(obj, spot)
    except Exception as error:
        e2_actuator.funds_add(funds, price, sim)
        e2_actuator.remove_created(obj)
        return _finish(control, act_id, connection, "REJECTED", "PLACE_FAILED", detail=type(error).__name__,
                       **base)
    facts = _facts(obj, sim, before, price=price, funds=e2_actuator.funds_money(funds))
    return _finish(control, act_id, connection, "FINISHED", "PLACED", result=_result(facts),
                   object_id=str(obj.id), guid64=None)


def cmd_place(control, args, connection):
    """2.40.0: place an item from her inventory (an item of hers that is not on the lot)."""
    act_id = args["act_id"]
    if not _start(control, act_id, connection):
        return False
    base = {"object_id": args["object_id"], "guid64": None}
    code, sim_info, sim = _home_gate(control)
    if code is not None:
        return _reject(control, act_id, connection, code, **base)
    obj = e2_actuator.find_object(args["object_id"])
    if obj is None or e2_actuator.in_inventory(obj) is not True:
        return _reject(control, act_id, connection, "NOT_IN_INVENTORY", **base)
    control._act_event(act_id, "ACCEPTED", **base)
    before = _route_reach(sim)
    spot, refused = _spot(control, obj, sim, args["place"])
    if refused is not None or spot is None:
        return _finish(control, act_id, connection, "REJECTED", refused or "NO_SPOT", **base)
    try:
        e2_actuator.place(obj, spot)
    except Exception as error:
        return _finish(control, act_id, connection, "REJECTED", "PLACE_FAILED", detail=type(error).__name__, **base)
    facts = _facts(obj, sim, before)
    return _finish(control, act_id, connection, "FINISHED", "PLACED", result=_result(facts), **base)


def cmd_move(control, args, connection):
    """2.40.0: move an object of hers on her lot. Blocked routes are reported in the result, not refused."""
    act_id = args["act_id"]
    if not _start(control, act_id, connection):
        return False
    base = {"object_id": args["object_id"], "guid64": None}
    code, sim_info, sim = _home_gate(control)
    if code is not None:
        return _reject(control, act_id, connection, code, **base)
    obj = e2_actuator.find_object(args["object_id"])
    if obj is None or e2_actuator.owner_of(obj) != str(sim_info.household_id):
        return _reject(control, act_id, connection, "NOT_HERS", **base)
    if e2_actuator.in_use(obj) is True:
        return _reject(control, act_id, connection, "IN_USE", **base)
    if not movable(obj):
        return _reject(control, act_id, connection, "NOT_MOVABLE", **base)
    control._act_event(act_id, "ACCEPTED", **base)
    before = _route_reach(sim)
    _vacate(control, obj)
    spot, refused = _spot(control, obj, sim, args["place"])
    if refused is not None or spot is None:
        return _finish(control, act_id, connection, "REJECTED", refused or "NO_SPOT", **base)
    try:
        e2_actuator.place(obj, spot)
    except Exception as error:
        return _finish(control, act_id, connection, "REJECTED", "MOVE_FAILED", detail=type(error).__name__, **base)
    facts = _facts(obj, sim, before)
    return _finish(control, act_id, connection, "FINISHED", "MOVED", result=_result(facts), **base)


def cmd_sell(control, args, connection):
    """2.40.0: sell an object of hers: she is paid its value, then it is removed (refunded if the removal fails)."""
    act_id = args["act_id"]
    if not _start(control, act_id, connection):
        return False
    base = {"object_id": args["object_id"], "guid64": None}
    code, sim_info, sim = _home_gate(control)
    if code is not None:
        return _reject(control, act_id, connection, code, **base)
    obj = e2_actuator.find_object(args["object_id"])
    if obj is None or e2_actuator.owner_of(obj) != str(sim_info.household_id):
        return _reject(control, act_id, connection, "NOT_HERS", **base)
    if e2_actuator.in_use(obj) is True:
        return _reject(control, act_id, connection, "IN_USE", **base)
    if not sellable(obj):
        return _reject(control, act_id, connection, "NOT_SELLABLE", **base)
    value = e2_actuator.value_of(obj)
    funds = e2_actuator.household_funds(sim_info.household_id)
    if value is None or funds is None:
        return _reject(control, act_id, connection, "NOT_SELLABLE", detail="value unreadable", **base)
    control._act_event(act_id, "ACCEPTED", **base)
    _vacate(control, obj)
    e2_actuator.funds_add(funds, value, sim)
    try:
        e2_actuator.sell_object(obj)
    except Exception as error:
        e2_actuator.funds_try_remove(funds, value, sim)
        return _finish(control, act_id, connection, "REJECTED", "SELL_FAILED", detail=type(error).__name__, **base)
    return _finish(control, act_id, connection, "FINISHED", "SOLD",
                   result=sell_facts(value, e2_actuator.funds_money(funds)), **base)


def _result(facts):
    """The result of a finished home edit, keyed as the contract names it (only the keys a placement has)."""
    return dict((key, facts.get(key)) for key in RESULT_KEYS if key != "value")


def cmd_catalog_dump(control, args, connection):
    """2.40.0: writes the catalogue record in parts (idempotent: the same content each time)."""
    raw = e2_actuator.catalog_rows() if e2_actuator is not None else None
    if raw is None:
        _say(control, connection, "CATALOG_UNREADABLE")
        return False
    count = write_catalog(control, raw)
    _say(control, connection, "CATALOG_WRITTEN %d" % count)
    return True


HANDLERS = {
    "save": cmd_save,
    "buy": cmd_buy,
    "place": cmd_place,
    "move": cmd_move,
    "sell": cmd_sell,
    "catalog_dump": cmd_catalog_dump,
}


def dispatch(control, name, args, connection):
    """Runs one of this module's commands (probe's inbox dispatch). Never raises into the game."""
    try:
        return HANDLERS[name](control, args, connection)
    except Exception as error:
        code = ("E2_EXCEPTION:%s" % type(error).__name__)[:64]
        act_id = args.get("act_id") if type(args) is dict else None
        if act_id is not None:
            control._act_event(act_id, "UNKNOWN", code=code, object_id=None, guid64=None)
        _say(control, connection, "ACT_UNKNOWN %s" % code)
        return False
