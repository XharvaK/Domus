"""2.40.0 (W13 P2, probe: home): the things list, the catalogue, her save, and her home edits (buy, place, move, sell).

Game thread only. Every game read and effect goes through e2_actuator, the only module that calls the game's effects
(tools/check_guards.py). The removal of a household object is in two places only: a sale, and the removal of an object
a purchase made when the purchase failed. Either is paid or refunded only once the game has finished the removal (the
tick). This module holds the shapes and bounds, the save floor, the things and catalogue rows, the placement facts and
the command flow. Her home is her call: a purchase or move that cuts a route is reported in the result, never refused.
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
# A removal the game has queued (a sale, or an object made for a purchase that failed) is confirmed gone within this
# many real seconds; after that it is UNKNOWN, and its money is not moved (HOME-9, S6).
GONE_CONFIRM_S = 30
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
STATE_TEXT_MAX = 64
TAGS_MAX = 8
# S3 (the game's build_buy flags, read from its bytecode): the buy categories a store item may be in, by bit. UNUSED (1),
# UNUSED_2 (16) and DEFAULT (2^31) are not categories, and are ignored.
BUY_CATEGORY_BITS = (("APPLIANCES", 2), ("ELECTRONICS", 4), ("ENTERTAINMENT", 8), ("LIGHTING", 32),
                     ("PLUMBING", 64), ("DECOR", 128), ("KIDS", 256), ("STORAGE", 512), ("COMFORT", 2048),
                     ("SURFACE", 4096), ("VEHICLE", 8192))
CATEGORY_MAX = len(BUY_CATEGORY_BITS)
# S3: a placement is one word. A wall flag (CENTER_ON_WALL, EDGE_AGAINST_WALL, ADJUST_HEIGHT_ON_WALL,
# GROUNDED_AGAINST_WALL, ON_WALL_TOP) makes it a wall item; REQUIRES_SLOT makes it a surface item; else a floor item.
WALL_FLAG_BITS = (1, 2, 4, 8388608, 268435456)
SLOT_FLAG_BIT = 1024
PLACEMENT_FLAGS = ("floor", "wall", "surface")
# Build items (structure), never furniture or decor, by the last word of the class name (CamelCase words).
BUILD_LAST_WORDS = ("wall", "floor", "roof", "stair", "stairs", "door", "window", "gate", "archway", "fence",
                    "portal", "terrain")
HIDDEN_TAG_WORDS = ("cheat", "debug", "hidden")


class HomeState(object):
    """What the home commands remember for one controller: the time of her last save, the save still waiting for its
    result, the objects she vacated (for `instead`), the removals waiting for the game to finish them (object id ->
    what to do then), and whether the save-complete callback is subscribed."""

    def __init__(self):
        self.saved_at = None
        self.pending_save = None
        self.vacated = {}
        self.pending_gone = {}
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


def buy_category_names(mask):
    """S3: the names of the buy categories whose bit is set in a definition's buy-category flags, in BUY_CATEGORY_BITS
    order (an empty list when none is set); None when the flags are unreadable."""
    if type(mask) is not int or mask < 0:
        return None
    return [name for name, bit in BUY_CATEGORY_BITS if mask & bit]


def placement_word(mask):
    """S3: the one placement word of a definition's placement flags: wall, surface or floor; None when unreadable."""
    if type(mask) is not int or mask < 0:
        return None
    if any(mask & bit for bit in WALL_FLAG_BITS):
        return "wall"
    if mask & SLOT_FLAG_BIT:
        return "surface"
    return "floor"


def purchasable(price, tag_names, categories):
    """2.40.0, S3: a catalogue item she may buy: a price (a store price may be zero), a buy category (the store lists it),
    and no tag that says cheat, debug or hidden. Only such items are offered and bought."""
    if type(price) is not int or isinstance(price, bool) or price < 0:
        return False
    if not categories:
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
    """A thing's state as {state, value} (a name and a plain value; a text is cut to STATE_TEXT_MAX characters, HOME-30);
    None when the name or the value is unreadable."""
    if type(raw) is not dict:
        return None
    name = raw.get("state")
    value = raw.get("value")
    if type(name) is not str or not name:
        return None
    if type(value) is bool or type(value) not in (int, float, str, type(None)):
        return None
    if type(value) is str:
        value = value[:STATE_TEXT_MAX]
    return {"state": name[:STATE_TEXT_MAX], "value": value}


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
        "placement": placement_word(raw.get("placement_flags")),
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
    """2.40.0, S3: one catalogue item from a raw read: its id, price, buy categories, one placement word and tags. None
    unless it is purchasable (a store item with a price, no hidden tag): no id, no price, a Sim, a build item, and a
    thing the store does not list are all left out."""
    if type(raw) is not dict:
        return None
    definition_id = _digits(raw.get("definition_id"))
    price = _int_or_none(raw.get("price"))
    if definition_id is None or price is None or raw.get("sim") is True:
        return None
    if is_build_class(raw.get("class_name") or ""):
        return None
    tags = [str(tag)[:64] for tag in (raw.get("tags") or ())[:TAGS_MAX]]
    categories = buy_category_names(raw.get("buy_flags"))
    if not purchasable(price, tags, categories):
        return None
    word = placement_word(raw.get("placement_flags"))
    return {"definition_id": definition_id, "price": price, "buy_category": categories,
            "placement": None if word is None else [word], "tags": tags, "purchasable": True}


def catalog_items(raw_rows):
    """The catalogue rows: the purchasable store items (build items, Sims and anything not for sale are left out)."""
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
    for the placed object. wall (it backs on a wall, HOME-24) names wall_has: the doors and windows on its wall, and
    wall_kinds says for each whether it is a door or a window (S2). beside: the nearest other objects within NEAR_M.
    Nothing here is text."""
    near = sorted((item for item in (near or ()) if item.get("distance") is not None and
                   item["distance"] <= NEAR_M and item.get("object_id")),
                  key=lambda item: item["distance"])
    wall_has, wall_kinds = [], []
    if wall is True:
        on_wall = [item for item in near if item.get("portal") or item.get("window")][:WALL_LIMIT]
        wall_has = [item["object_id"] for item in on_wall]
        wall_kinds = ["door" if item.get("portal") else "window" for item in on_wall]
    beside = [item["object_id"] for item in near if item["object_id"] not in wall_has][:NEAR_LIMIT]
    return {"room_id": _digits(room_id), "wall": _bool_or_none(wall), "wall_has": wall_has,
            "wall_kinds": wall_kinds, "beside": beside, "facing_id": _digits(facing_id),
            "routes_lost": list(lost), "price": _int_or_none(price), "funds": _int_or_none(funds)}


def sell_facts(value, funds):
    """2.40.0: the result of a sale: what she was paid and her funds now."""
    return {"value": _int_or_none(value), "funds": _int_or_none(funds)}


# ----------------------------------------------------------------------------------------------- the list writers

def write_catalog(control, raw_rows, rev=None):
    """2.40.0: the catalogue record in parts (catalog_dump). rev is the game's version string. Returns (items, parts
    written, parts): a part the probe did not write is not counted (HOME-19)."""
    items = catalog_items(raw_rows)
    payloads = catalog_parts(rev or schema.SIMS_BUILD, items)
    written = 0
    for payload in payloads:
        if control._event("catalog", payload):
            written += 1
    return len(items), written, len(payloads)


# ------------------------------------------------------------------------------------------------- the commands

def _row(control, act_id, phase, **payload):
    """One act row (CORE-9). A row the schema refuses is replaced by an UNKNOWN row without the result (ROW_INVALID),
    so the act is never left open for want of a row the probe could not write."""
    if control._act_event(act_id, phase, **payload) is False:
        control._act_event(act_id, "UNKNOWN", code="ROW_INVALID", object_id=None, guid64=None)
        return False
    return True


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
        _row(control, act_id, "REJECTED", code="E2_UNAVAILABLE")
        _say(control, connection, "ACT_REJECT E2_UNAVAILABLE")
        return False
    return True


def _reject(control, act_id, connection, code, detail=None, reason_key=None, phase="REJECTED", **base):
    _row(control, act_id, phase, code=code, detail=None if detail is None else str(detail)[:128],
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


def _guarded(read, default):
    """A read for a result fact: its value, or the default when it cannot be read (HOME-13: a fact that fails leaves
    the fact out; the act still finishes)."""
    try:
        return read()
    except Exception:
        return default


def _facts(obj, sim, before, price=None, funds=None, facing_id=None):
    """The result facts of a placed object: room, wall (against a wall of its room), what is near, the facing it was
    given, and the routes cut since `before`. Each read is guarded (HOME-13)."""
    lost = _guarded(lambda: routes_lost(before, _route_reach(sim)), [])
    near = _guarded(lambda: e2_actuator.near_objects(obj, NEAR_M), [])
    room = _guarded(lambda: e2_actuator.room_of(obj), None)
    wall = _guarded(lambda: e2_actuator.against_wall(obj), None)
    return placement_facts(room, wall, near, facing_id=facing_id, lost=lost, price=price, funds=funds)


def _vacate(control, obj):
    """Remember where an object was before it is sold or moved, so `instead` can name that spot later."""
    state = state_of(control)
    spot = e2_actuator.spot_of(obj)
    if spot is not None:
        state.vacated[str(obj.id)] = spot


def _wall_item(flags):
    """True when a thing is a wall item by its placement flags (S3): it is placed against a wall."""
    return placement_word(flags) == "wall"


def _spot(control, obj, sim, place, wall_item=False):
    """(spot, refusal). `instead` names the spot its target vacated, and is refused NOT_FREE while the target still
    stands there; the other relations are the game's own search for a spot."""
    if place["rel"] == "instead":
        target = str(place["target_id"])
        vacated = state_of(control).vacated.get(target)
        target_obj = e2_actuator.find_object(target)
        if target_obj is not None:
            # The target still stands: its spot is free only when she moved it away first (A6-19).
            if vacated is None or e2_actuator.spot_key(e2_actuator.spot_of(target_obj)) == \
                    e2_actuator.spot_key(vacated):
                return None, "NOT_FREE"
            return vacated, None
        if vacated is None:
            return None, "NO_SPOT"
        return vacated, None
    return e2_actuator.find_spot(obj, sim, place, wall_item=wall_item), None


def _finish(control, act_id, connection, phase, code, result=None, **base):
    _row(control, act_id, phase, code=code, result=result, **base)
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
    _expire_save(control)
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
    busy = e2_actuator.save_busy()
    if busy is None:
        return _reject(control, act_id, connection, "SAVE_FAILED", detail="timeline unreadable", **base)
    if busy or state_of(control).pending_save is not None:
        return _reject(control, act_id, connection, "SAVE_BUSY", **base)
    state = state_of(control)
    left = save_gate(state.saved_at, time.time())
    if left is not None:
        return _reject(control, act_id, connection, "SAVE_TOO_SOON", detail="%d s" % left, **base)
    _row(control, act_id, "ACCEPTED", **base)
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
    """The game's save-complete callback: FINISHED SAVED for the save waiting for it. It never raises into the game:
    a failure is the save's UNKNOWN row (CORE-9)."""
    state = state_of(control)
    pending = state.pending_save
    if pending is None:
        return
    state.pending_save = None
    act_id, _at, connection = pending
    try:
        _finish(control, act_id, connection, "FINISHED", "SAVED", object_id=None, guid64=None)
    except Exception as error:
        try:
            _row(control, act_id, "UNKNOWN", code=("E2_EXCEPTION:%s" % type(error).__name__)[:64],
                 object_id=None, guid64=None)
        except Exception:
            pass


def _expire_save(control, now=None):
    """A save with no callback after SAVE_CONFIRM_S is UNKNOWN: the game may have saved or not."""
    state = state_of(control)
    pending = state.pending_save
    now = time.time() if now is None else now
    if pending is None or now - pending[1] < SAVE_CONFIRM_S:
        return
    state.pending_save = None
    act_id, _at, old_connection = pending
    _finish(control, act_id, old_connection, "UNKNOWN", "SAVE_UNCONFIRMED", object_id=None, guid64=None)


def tick(control, now=None):
    """2.40.0 (W13 P2, home): the home work of every sampling tick (probe's reach tick): a save with no callback after
    SAVE_CONFIRM_S, and the removals the game has to finish (a sale, an undone purchase). Never raises into sampling."""
    now = time.time() if now is None else now
    _expire_save(control, now)
    _settle_removals(control, now)


def _settle_removals(control, now):
    """Each removal waiting for the game: when the object is gone, its act settles (the sale is paid now; an undone
    purchase is refunded now, if it was charged); after GONE_CONFIRM_S with the object still there, UNKNOWN and no money
    moved (a failed path never refunds while an object may still exist)."""
    state = state_of(control)
    for key, pending in list(state.pending_gone.items()):
        gone = e2_actuator.object_gone(key)
        if gone is True:
            del state.pending_gone[key]
            _settled(control, pending)
        elif now - pending["at"] >= GONE_CONFIRM_S:
            del state.pending_gone[key]
            code = "SELL_UNCONFIRMED" if pending["kind"] == "sale" else "REMOVE_UNCONFIRMED"
            _finish(control, pending["act_id"], pending["connection"], "UNKNOWN", code,
                    **dict(pending["base"], object_id=key))


def _settled(control, pending):
    """A removal the game has finished: the sale is paid (and FINISHED SOLD), or the undone purchase is refunded (its
    REJECTED row says so when the refund fails)."""
    e2_actuator.forget_rooms()
    act_id, connection, base = pending["act_id"], pending["connection"], pending["base"]
    if pending["kind"] == "sale":
        if not e2_actuator.funds_add(pending["funds"], pending["value"], pending["sim"]):
            return _finish(control, act_id, connection, "UNKNOWN", "SELL_FAILED", detail="not paid", **base)
        return _finish(control, act_id, connection, "FINISHED", "SOLD",
                       result=sell_facts(pending["value"], e2_actuator.funds_money(pending["funds"])), **base)
    detail = pending.get("detail")
    refund = pending.get("refund")
    if refund is not None and not e2_actuator.funds_add(refund["funds"], refund["amount"], refund["sim"]):
        detail = "refund failed"
    return _finish(control, act_id, connection, pending.get("phase", "REJECTED"), pending["code"], detail=detail,
                   **base)


def _undo(control, act_id, connection, obj, code, detail=None, refund=None, phase="REJECTED"):
    """A purchase that failed after its object was made: the object is removed, and the act settles only once the game
    has finished the removal (tick). The money is refunded then, never before (a failed path never refunds while the
    object may still exist). A removal the game refuses is UNKNOWN with the object's id, and nothing is refunded.
    phase is the act's end: REJECTED, or UNKNOWN when the money is not known (CHARGE_UNKNOWN)."""
    key = str(obj.id)
    if not e2_actuator.remove_created(obj):
        return _finish(control, act_id, connection, "UNKNOWN", "REMOVE_UNCONFIRMED", object_id=key, guid64=None)
    pending = {"kind": "undo", "act_id": act_id, "connection": connection, "base": {"object_id": None, "guid64": None},
               "at": time.time(), "code": code, "detail": detail, "refund": refund, "phase": phase}
    if e2_actuator.object_gone(key) is True:
        _settled(control, pending)
    else:
        state_of(control).pending_gone[key] = pending
    return False


def charge_made(before, after, price):
    """True when the money fell by exactly the price (both reads known): the charge is made (HOME-10)."""
    return before is not None and after is not None and before - after == price


def cmd_buy(control, args, connection):
    """2.40.0: buy a catalogue item and place it. The spot is found first (for the item's footprint the object is made
    unplaced, and removed again if no spot is found or the money is not there); only then the charge, decided by the
    money (it fell by the price); then the move. A failure after the charge is undone and refunded once the game has
    removed the object (_undo). A charge whose money cannot be read is UNKNOWN, and the object is kept."""
    act_id = args["act_id"]
    if not _start(control, act_id, connection):
        return False
    base = {"object_id": None, "guid64": None}
    code, sim_info, sim = _home_gate(control)
    if code is not None:
        return _reject(control, act_id, connection, code, **base)
    definition = e2_actuator.definition(args["definition_id"])
    price = e2_actuator.definition_price(definition)
    categories = buy_category_names(e2_actuator.definition_buy_flags(definition))
    if not purchasable(price, e2_actuator.definition_tags(definition), categories):
        return _reject(control, act_id, connection, "NOT_PURCHASABLE", **base)
    if args.get("max_price") is not None and price > args["max_price"]:
        return _reject(control, act_id, connection, "PRICE_ABOVE", detail="price %d" % price, **base)
    funds = e2_actuator.household_funds(sim_info.household_id)
    if funds is None or not e2_actuator.can_afford(funds, price):
        return _reject(control, act_id, connection, "NO_FUNDS", **base)
    if e2_actuator.funds_money(funds) is None:
        return _reject(control, act_id, connection, "NO_FUNDS", detail="funds unreadable", **base)
    _row(control, act_id, "ACCEPTED", **base)
    before = _route_reach(sim)
    obj = e2_actuator.create_unplaced(definition)
    if obj is None:
        return _finish(control, act_id, connection, "REJECTED", "PLACE_FAILED", **base)
    try:
        spot, refused = _spot(control, obj, sim, args["place"],
                              wall_item=_wall_item(e2_actuator.definition_placement_flags(definition)))
    except Exception as error:
        # 2.40.0 (W13 R2, HOME2-2): a search that raises removes what it made; nothing has been charged.
        return _undo(control, act_id, connection, obj, "SPOT_FAILED", detail=type(error).__name__)
    if refused is not None or spot is None:
        return _undo(control, act_id, connection, obj, refused or "NO_SPOT")
    money_before = e2_actuator.funds_money(funds)
    e2_actuator.funds_try_remove(funds, price, sim)
    money_after = e2_actuator.funds_money(funds)
    if money_after is None:
        # 2.40.0 (W13 R2, SEAM2-5 / T4): the money cannot be read, so whether she paid is not known. The object is
        # removed as a failed purchase is, with no refund, and the act says so.
        return _undo(control, act_id, connection, obj, "CHARGE_UNKNOWN", phase="UNKNOWN",
                     detail="the money could not be read; the object was removed and not refunded")
    if not charge_made(money_before, money_after, price):
        return _undo(control, act_id, connection, obj, "NO_FUNDS")
    refund = {"funds": funds, "amount": price, "sim": sim}
    try:
        e2_actuator.place(obj, spot)
    except Exception as error:
        return _undo(control, act_id, connection, obj, "PLACE_FAILED", detail=type(error).__name__, refund=refund)
    e2_actuator.forget_rooms()
    facts = _facts(obj, sim, before, price=price, funds=e2_actuator.funds_money(funds),
                   facing_id=spot.get("facing_id"))
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
    obj = e2_actuator.find_thing(args["object_id"])
    if obj is None or e2_actuator.in_inventory(obj) is not True:
        return _reject(control, act_id, connection, "NOT_IN_INVENTORY", **base)
    _row(control, act_id, "ACCEPTED", **base)
    before = _route_reach(sim)
    spot, refused = _spot(control, obj, sim, args["place"], wall_item=_wall_item(e2_actuator.object_placement_flags(obj)))
    if refused is not None or spot is None:
        return _finish(control, act_id, connection, "REJECTED", refused or "NO_SPOT", **base)
    try:
        taken = e2_actuator.take_from_inventory(sim, obj)
    except Exception as error:
        return _finish(control, act_id, connection, "UNKNOWN", "PLACE_FAILED", detail=type(error).__name__, **base)
    if taken is not True:
        return _finish(control, act_id, connection, "REJECTED", "PLACE_FAILED", detail="not released", **base)
    try:
        e2_actuator.place(obj, spot)
    except Exception as error:
        if e2_actuator.return_to_inventory(sim, obj) is True:
            return _finish(control, act_id, connection, "REJECTED", "PLACE_FAILED", detail=type(error).__name__,
                           **base)
        return _finish(control, act_id, connection, "UNKNOWN", "PLACE_FAILED", detail="put back failed", **base)
    e2_actuator.forget_rooms()
    facts = _facts(obj, sim, before, facing_id=spot.get("facing_id"))
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
    obj = e2_actuator.find_thing(args["object_id"])
    if obj is None or e2_actuator.owner_of(obj) != str(sim_info.household_id):
        return _reject(control, act_id, connection, "NOT_HERS", **base)
    if e2_actuator.in_use(obj) is True:
        return _reject(control, act_id, connection, "IN_USE", **base)
    if e2_actuator.in_inventory(obj) is True:
        return _reject(control, act_id, connection, "IN_INVENTORY", **base)
    if not movable(obj):
        return _reject(control, act_id, connection, "NOT_MOVABLE", **base)
    _row(control, act_id, "ACCEPTED", **base)
    before = _route_reach(sim)
    _vacate(control, obj)
    spot, refused = _spot(control, obj, sim, args["place"], wall_item=_wall_item(e2_actuator.object_placement_flags(obj)))
    if refused is not None or spot is None:
        return _finish(control, act_id, connection, "REJECTED", refused or "NO_SPOT", **base)
    try:
        e2_actuator.place(obj, spot)
    except Exception as error:
        return _finish(control, act_id, connection, "REJECTED", "MOVE_FAILED", detail=type(error).__name__, **base)
    e2_actuator.forget_rooms()
    facts = _facts(obj, sim, before, facing_id=spot.get("facing_id"))
    return _finish(control, act_id, connection, "FINISHED", "MOVED", result=_result(facts), **base)


def cmd_sell(control, args, connection):
    """2.40.0: sell an object of hers. The game queues its removal; she is paid, and FINISHED SOLD, only once the game
    has finished the removal (tick). A removal the game refuses now is REJECTED and nothing is paid."""
    act_id = args["act_id"]
    if not _start(control, act_id, connection):
        return False
    base = {"object_id": args["object_id"], "guid64": None}
    code, sim_info, sim = _home_gate(control)
    if code is not None:
        return _reject(control, act_id, connection, code, **base)
    obj = e2_actuator.find_thing(args["object_id"])
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
    _row(control, act_id, "ACCEPTED", **base)
    _vacate(control, obj)
    try:
        e2_actuator.sell_object(obj)
    except Exception as error:
        return _finish(control, act_id, connection, "REJECTED", "SELL_FAILED", detail=type(error).__name__, **base)
    state_of(control).pending_gone[str(obj.id)] = {
        "kind": "sale", "act_id": act_id, "connection": connection, "base": base, "at": time.time(),
        "value": value, "funds": funds, "sim": sim}
    return True


def _result(facts):
    """The result of a finished home edit, keyed as the contract names it (only the keys a placement has)."""
    return dict((key, facts.get(key)) for key in schema.RESULT_KEYS if key != "value")


def cmd_catalog_dump(control, args, connection):
    """2.40.0: writes the catalogue record in parts (idempotent: the same content each time)."""
    raw = e2_actuator.catalog_rows() if e2_actuator is not None else None
    if raw is None:
        _say(control, connection, "CATALOG_UNREADABLE")
        return False
    items, written, parts = write_catalog(control, raw)
    if written == parts:
        _say(control, connection, "CATALOG_WRITTEN %d" % items)
        return True
    _say(control, connection, "CATALOG_PARTIAL %d/%d" % (written, parts))
    return False


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
            _row(control, act_id, "UNKNOWN", code=code, object_id=None, guid64=None)
        _say(control, connection, "ACT_UNKNOWN %s" % code)
        return False
