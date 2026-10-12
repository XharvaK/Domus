"""W13 (H): the probe's lists, discovery and result facts, in words for her and for Natalis.

- A `lists` row is one list (people, places, things or events) written in parts. ListParts keeps the parts of each
  kind until the whole list has come. list_words turns the probe's items into the words Natalis gets: refs, names
  (tokens cleaned), and nothing the probe did not list. digest() is the SHA-256 of what is sent, so Natalis can say
  which list it holds.
- A `discovery` row is the probe's read-only facts about the game. write_discovery keeps the newest one per telemetry
  session as a file in the helper's data folder: it is evidence for the lead, never part of her view.
- result_words says a verb act's result facts in plain words, at most RESULT_WORDS_MAX characters. It never carries
  the probe's ids: the caller gives the names.

Nothing here chooses or ranks for her. A list is sent whole (cut only at the body limit, from its end).
"""
import hashlib
import json
import os
import re

from .acts import RESULT_WORDS_MAX, clean_text, humanize

KINDS = ("people", "places", "things", "events")
# The probe writes at most this many items per part, and at most this many parts (a list of 600 is 5 parts).
PART_ITEMS = 128
PARTS_LIMIT = 64
# Natalis takes a list body of 128 KiB; a list that would be larger is cut from its end (the digest is of what is sent).
LIST_BYTES = 120 * 1024
THINGS_STATES = 4
# The one-letter prefix of each kind's refs (RefBook): people p, places h, things t, events e.
# Natalis's shape for each kind (its contract): at most this many items, and these many characters at most.
LIMITS = {"people": 200, "places": 120, "things": 600, "events": 200}
NAME_LIMIT = 64
WHAT_LIMIT = 40
WHERE_LIMIT = 64
STATE_LIMIT = 40
PLACEMENT_LIMIT = 16
ROUTES = {"door": "door", "bed": "bed", "toilet": "toilet", "fridge": "fridge"}
SESSION_NAME = re.compile(r"[0-9A-Za-z_-]{1,64}")
_DIGITS = re.compile(r"[0-9]{1,32}")


def digest(items):
    """SHA-256 hex of the canonical items: the list as Natalis holds it."""
    raw = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def fit(items):
    """The items that fit one list body, in their order: the rest are cut from the end."""
    total, keep = 2, 0
    for index, item in enumerate(items):
        size = len(json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + (1 if index else 0)
        if total + size > LIST_BYTES:
            break
        total += size
        keep = index + 1
    return list(items[:keep])


class ListParts(object):
    """W13 (H): a list in parts (list_rev, part, parts; the catalogue's rev is catalog_rev). take() returns the list's items
    once every part of one rev has come, else None. A newer rev of a kind starts that kind over; a part out of range is
    ignored."""

    def __init__(self):
        self._pieces = {}

    def take(self, kind, e2, rev_key="list_rev"):
        parts, part, rev = e2.get("parts"), e2.get("part"), e2.get(rev_key)
        if type(parts) is not int or not 1 <= parts <= PARTS_LIMIT:
            return None
        if type(part) is not int or not 0 <= part < parts:
            return None
        held = self._pieces.get(kind)
        if held is None or held[0] != rev or held[2] != parts:
            held = self._pieces[kind] = (rev, {}, parts)
        items = e2.get("items")
        held[1][part] = [item for item in (items if isinstance(items, list) else []) if isinstance(item, dict)][:PART_ITEMS]
        if len(held[1]) < parts:
            return None
        del self._pieces[kind]
        return [item for index in range(parts) for item in held[1][index]]


def _ident(value):
    """An id from the probe as digits (an int or a digit string), or None."""
    if type(value) is int and value >= 0:
        return str(value)
    if isinstance(value, str) and _DIGITS.fullmatch(value):
        return value
    return None


def _text(value, limit):
    """A plain text from the probe, tokens cleaned and cut to limit characters, or None."""
    if not isinstance(value, str):
        return None
    text = clean_text(value)
    return text[:limit] if text else None


def _text_key(resolve, key):
    """The game's text for a string key, cut to 64 characters, or None (resolve may be None)."""
    if resolve is None or key is None:
        return None
    try:
        text = resolve(str(key))
    except Exception:
        return None
    return _text(text, 64) if isinstance(text, str) else None


def _join(names):
    """Names in words: "A", "A and B", "A, B and C"."""
    names = [name for name in names if name]
    if len(names) <= 1:
        return "".join(names)
    return "%s and %s" % (", ".join(names[:-1]), names[-1])


def _number(value):
    return str(int(round(value)))


def _how(labels, tracks):
    """Relationship labels and tracks in words (at most 80 characters)."""
    parts = []
    names = [humanize(label) for label in (labels if isinstance(labels, list) else [])[:4] if isinstance(label, str) and label]
    if names:
        parts.append(", ".join(names))
    if isinstance(tracks, dict):
        for track, value in list(tracks.items())[:4]:
            if isinstance(track, str) and track and isinstance(value, (int, float)) and not isinstance(value, bool):
                parts.append("%s %s" % (humanize(track), _number(value)))
    return "; ".join(parts)[:80]


class _Skip(Exception):
    """A probe item the list cannot carry in its shape: it is left out, and the reason is logged (never guessed)."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _name(value, limit=NAME_LIMIT):
    """A name in words, cut to limit characters; a name with nothing left is a skip (Natalis never takes an empty one)."""
    text = _text(value, limit)
    if text is None:
        raise _Skip("name")
    return text


def _person(item, refs, **_):
    sim = _ident(item.get("sim_id"))
    if sim is None:
        raise _Skip("id")
    first = _text(item.get("first_name"), NAME_LIMIT) or ""
    last = _text(item.get("last_name"), NAME_LIMIT) or ""
    name = _name((first + " " + last).strip())
    return {"ref": refs.ref(sim, prefix="p"), "id": sim, "name": name,
            "how": _how(item.get("labels"), item.get("tracks")),
            "home": item.get("has_home") is True, "here": item.get("on_lot") is True,
            "waiting": item.get("waiting") is True}


def _place(item, refs, households=None, **_):
    zone = _ident(item.get("zone_id"))
    kind = item.get("kind")
    if zone is None:
        raise _Skip("id")
    if kind not in ("home", "household", "venue"):
        raise _Skip("kind")
    lot = _text(item.get("lot_name"), NAME_LIMIT)
    if kind == "venue":
        venue = item.get("venue")
        what = humanize(venue)[:WHAT_LIMIT] if isinstance(venue, str) and venue else "a venue"
    elif kind == "household":
        owner = (households or {}).get(_ident(item.get("household_id")))
        what = ("%s's home" % owner if owner else "a household's home")[:WHAT_LIMIT]
    else:
        what = "your home"
    return {"ref": refs.ref(zone, prefix="h"), "id": zone, "name": lot or what, "kind": kind, "what": what}


def _placed(item):
    """W13 (H, S5): a thing's place as the probe writes it: (kind, room id as digits). The kind is inventory, outside,
    room or None (unreadable); the room id is set only for a room."""
    where = item.get("where")
    kind, room = None, _ident(item.get("room_id"))
    if isinstance(where, dict):
        kind = where.get("where") or where.get("kind") or ("room" if where.get("room_id") is not None else None)
        if where.get("room_id") is not None:
            room = _ident(where.get("room_id"))
    elif isinstance(where, str):
        kind = where
    if kind == "room" or (kind is None and room is not None):
        return "room", room
    return kind, None


def _where(item, rooms):
    """Her thing's place in words: its room's label (from the things list, S5), inventory or outside. None when the
    place is unreadable or its room has no label: a room is never "a room"."""
    kind, room = _placed(item)
    if kind in ("inventory", "outside"):
        return kind
    if kind == "room" and room is not None:
        label = (rooms or {}).get(room)
        return label[:WHERE_LIMIT] if isinstance(label, str) and label else None
    return None


def _states(raw):
    """A thing's conditions in words (at most 4, each at most 40 characters): the value's name, else the state's."""
    words = []
    for state in raw if isinstance(raw, list) else []:
        if not isinstance(state, dict):
            continue
        value, name = state.get("value"), state.get("state")
        word = humanize(value) if isinstance(value, str) and value else (humanize(name) if isinstance(name, str) and name else "")
        word = word[:STATE_LIMIT].strip()
        if word and word not in words:
            words.append(word)
        if len(words) >= THINGS_STATES:
            break
    return words


def _thing_name(item, resolve=None, catalog=None):
    """A thing's name in words: its own name key, else its catalogue entry's; None when neither reads."""
    name = _text_key(resolve, item.get("name_key"))
    if name is None and catalog is not None and item.get("definition_id") is not None:
        try:
            entry = catalog(item["definition_id"])
        except Exception:
            entry = None
        name = _text_key(resolve, (entry or {}).get("name_key")) if entry else None
    return name


def room_labels(raw, *, resolve=None, catalog=None):
    """W13 (H, S5): a label for each room of the things list, from the names of the things in it: "the room with the
    Test Bed and the Test Lamp" (three names at most). Equal labels get " (2)", " (3)" in ascending room id order; a room
    with no named thing has no label. A thing's place is its room's label, and a place's room name is matched to these."""
    names = {}
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        kind, room = _placed(item)
        name = _thing_name(item, resolve, catalog) if kind == "room" and room is not None else None
        if name is not None:
            names.setdefault(room, set()).add(name)
    labels, counts = {}, {}
    for room in sorted(names, key=int):
        base = ("the room with the %s" % " and the ".join(sorted(names[room], key=str.casefold)[:3]))[:WHERE_LIMIT]
        counts[base] = counts.get(base, 0) + 1
        labels[room] = base if counts[base] == 1 else "%s (%d)" % (base, counts[base])
    return labels


def _thing(item, refs, rooms=None, resolve=None, catalog=None, **_):
    oid = _ident(item.get("object_id"))
    if oid is None:
        raise _Skip("id")
    where = _where(item, rooms)
    if where is None:
        raise _Skip("where")
    name = _thing_name(item, resolve, catalog)
    if name is None:
        raise _Skip("name")
    made = item.get("made_by_her")
    placement = item.get("placement")
    thing = {"ref": refs.ref(oid, prefix="t"), "id": oid, "name": name, "where": where,
             "made_by_her": made if isinstance(made, bool) else None,
             "states": _states(item.get("states")), "in_use": item.get("in_use") is True,
             "placement": placement if isinstance(placement, str) and 1 <= len(placement) <= PLACEMENT_LIMIT else None}
    if type(item.get("value")) is int:
        thing["value"] = item["value"]  # A4-11: a thing without a readable value is kept; Natalis takes its absence
    if type(item.get("count")) is int and item["count"] >= 0:
        thing["count"] = item["count"]
    return thing


def _event(item, refs, resolve=None, **_):
    sid = _ident(item.get("situation_id"))
    if sid is None:
        raise _Skip("id")
    name = _text_key(resolve, item.get("name_key"))
    if name is None:
        raise _Skip("name")
    cost = item.get("cost")
    return {"ref": refs.ref(sid, prefix="e"), "id": sid, "name": name,
            "cost": cost if type(cost) is int else None}


_MAKERS = {"people": _person, "places": _place, "things": _thing, "events": _event}


def list_words(kind, raw, *, refs, rooms=None, resolve=None, catalog=None, households=None, skipped=None):
    """The probe's items of one kind, in words for Natalis, in Natalis's shape. An item that cannot be given that shape
    (no id, no name, no place, no value) is left out, and its reason is appended to skipped when a list is given. At most
    the kind's limit is kept. refs is the helper's RefBook; rooms maps a room id to its label; resolve is the game's text
    for a key; catalog is the catalogue lookup; households maps a household id to its first name."""
    maker = _MAKERS[kind]
    found = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            _note(skipped, "not_an_item")
            continue
        try:
            found.append(maker(item, refs, rooms=rooms, resolve=resolve, catalog=catalog, households=households))
        except _Skip as skip:
            _note(skipped, skip.reason)
    if kind == "things":
        # A6-17: her inventory comes first, so the size cut takes lot objects before what she carries (stable otherwise).
        found.sort(key=lambda thing: thing["where"] != "inventory")
    if len(found) > LIMITS[kind]:
        _note(skipped, "over_limit")
    return found[:LIMITS[kind]]


def _note(skipped, reason):
    if skipped is not None:
        skipped.append(reason)


def households_of(people_raw):
    """household id -> the first name of a Sim of it she knows (from the people list), for a household's place."""
    names = {}
    for item in people_raw if isinstance(people_raw, list) else []:
        if isinstance(item, dict):
            household = _ident(item.get("household_id"))
            first = _text(item.get("first_name"), 64)
            if household is not None and first and household not in names:
                names[household] = first
    return names


def index(lists):
    """What the helper reads from its stored lists (words, as Natalis holds them): the names of things and places
    and the conditions of things, by id, and the names of people, by sim id."""
    found = {"things": {}, "states": {}, "places": {}, "people": {}}
    for kind, target in (("things", "things"), ("places", "places"), ("people", "people")):
        for item in (lists.get(kind) or {}).get("items") or []:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                found[target][item["id"]] = item.get("name")
                if kind == "things" and item.get("states"):
                    found["states"][item["id"]] = list(item["states"])
    return found


def _names(ids, name_of):
    names = []
    for thing in ids if isinstance(ids, list) else []:
        oid = _ident(thing)
        if oid is not None and len(names) < 4:
            names.append((name_of(oid) if name_of is not None else None) or "something")
    return names


def _start_words(start):
    """W13 (S7): an event's start in words, from the act's own start: "Starts now.", or the game time and today or
    tomorrow (its day offset). Never a day count."""
    if start == "now":
        return "Starts now."
    return "Starts at %02d:%02d %s." % (start["hour"], start["minute"], "tomorrow" if start["day_offset"] == 1 else "today")


def result_words(result, *, name_of=None, room_of=None, place_of=None, start=None):
    """A verb act's result facts in plain words, at most RESULT_WORDS_MAX characters, or None when there are none.
    name_of gives a thing's name by its id; room_of a room's name by its id; place_of a place's name by its zone id;
    start is the act's own start (an event), "now" or {day_offset, hour, minute}.
    The sentences: where it is (room, wall, what it is beside), what it faces, what it cuts off, the money, the start."""
    if not isinstance(result, dict):
        return None
    sentences = []
    where = []
    room = _ident(result.get("room_id"))
    if room is not None and room_of is not None and room_of(room):
        where.append("In %s" % room_of(room))
    if result.get("wall") is True:
        clause = "against a wall"
        on_wall = _names(result.get("wall_has"), name_of)
        if on_wall:
            clause += " with %s" % _join(on_wall)
        where.append(clause)
    elif result.get("wall") is False:
        where.append("away from the walls")
    beside = _names(result.get("beside"), name_of)
    if beside:
        where.append("beside %s" % _join(beside))
    if where:
        sentences.append("%s." % ", ".join(where))
    facing = _ident(result.get("facing_id"))
    if facing is not None:
        sentences.append("Facing %s." % ((name_of(facing) if name_of is not None else None) or "something"))
    routes = result.get("routes_lost") if isinstance(result.get("routes_lost"), list) else []
    lost = [ROUTES[route] for route in routes if isinstance(route, str) and route in ROUTES]
    if lost:
        sentences.append("Cuts off the way to the %s." % _join(lost))
    cost = result.get("price") if type(result.get("price")) is int else result.get("cost")
    value = result.get("value")
    funds = result.get("funds") if type(result.get("funds")) is int else None
    if type(value) is int:
        sentences.append("Worth §%d%s." % (value, "; you have §%d" % funds if funds is not None else ""))
    elif type(cost) is int:
        sentences.append("Costs §%d%s." % (cost, "; you have §%d" % funds if funds is not None else ""))
    elif funds is not None:
        sentences.append("You have §%d." % funds)
    if start is not None:
        sentences.append(_start_words(start))
    zone = _ident(result.get("zone_id"))
    if zone is not None:
        place = place_of(zone) if place_of is not None else None
        sentences.append("Now in %s." % (place or "another place"))
    text = " ".join(sentences)[:RESULT_WORDS_MAX]
    return text or None


def write_discovery(folder, row):
    """W13 (H, P1): the discovery row, as one JSON file per telemetry session, the newest kept. Returns the file's
    name, or None when the row names no usable session. The folder is made when it is missing."""
    session = row.get("telemetry_session_id") if isinstance(row, dict) else None
    if not isinstance(session, str) or SESSION_NAME.fullmatch(session) is None:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / ("%s.json" % session)
    temporary = folder / ("%s.json.tmp" % session)
    raw = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(raw)
    os.replace(temporary, target)
    return target.name
