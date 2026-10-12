"""W13-P1 (probe 2.40.0): her reach. The discovery record's shape, the lists her view counts (people, places, events;
things are written by the same writer on P2's branch), and the small rules the verbs share. Pure: no game imports.
The game's reads are in observers.py (read_people, read_places, read_events, read_discovery); the writes go through
the E2 emitter. Every list and section is optional: an unreadable value is left out, never guessed.

Contract: docs/design/w13-build.md (Natalis repository), "Contract (probe 2.40.0, telemetry schema 21)".
"""
import hashlib
import json
import time

from . import schema

# The list kinds. things belongs to P2 (its own reader); the writer below is shared.
LIST_KINDS = ("people", "places", "things", "events")
# Each list is checked at most once every LIST_CHECK_S real seconds, and written only when its digest changed.
LIST_CHECK_S = 60.0
# Items per part (a record); the packed size is also kept under the record limit.
LIST_PART_ITEMS = 128
PEOPLE_MAX = 200
PLACES_MAX = 120
EVENTS_MAX = 200
PLACE_KINDS = ("home", "household", "venue")
PART_BYTES_MAX = schema.MAX_SERIALIZED_RECORD_BYTES - 4096
# The discovery record: optional sections, kept under this many bytes (the largest sections go first).
DISCOVERY_SECTIONS = ("pickers", "phone_tests", "off_lot", "save", "situations", "career", "population")
DISCOVERY_MAX_BYTES = 40 * 1024
PHONE_KINDS = ("text", "call")
NAME_MAX = 64
LABEL_MAX = 40
LABELS_PER_PERSON = 4
TRACKS_PER_PERSON = 4
COST_MAX = 2 ** 31
START_MINUTES_PER_DAY = 1440
# The verbs (go, event): a trip's zone change is awaited this many real seconds; a planned event has at most this many
# guests; the household funds' reason for an event's charge (the game's own text is not needed for it).
GO_SEEN_S = 300.0
EVENT_GUESTS_MAX = 16
FUNDS_REASON = "ashley_e2_event"


def _text(value, limit):
    """Plain text, control characters removed, at most limit characters; None when empty or not text."""
    if not isinstance(value, str):
        return None
    cleaned = "".join(ch for ch in value if ch >= " " and ch != "\x7f").strip()
    return cleaned[:limit] or None


def _id(value):
    """A game id as digits (at most 20); None for anything else. A bool is never an id."""
    if isinstance(value, bool) or value is None:
        return None
    text = str(value) if type(value) is int else value
    if type(text) is str and text.isdigit() and 1 <= len(text) <= 20:
        return text
    return None


def _int(value):
    return value if type(value) is int and -COST_MAX <= value <= COST_MAX else None


def _flag(value):
    return value if type(value) is bool else None


def canonical(items):
    """The canonical JSON of a list's items (sorted keys, no spaces): what a digest is taken over."""
    return json.dumps(items, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(items):
    return hashlib.sha256(canonical(items).encode("utf-8")).hexdigest()


def _bytes(value):
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


# ------------------------------------------------------------------ item shapes

def person_item(entry):
    """A person she knows, as the list keeps it. None when the entry has no sim id. Labels (bit names) and tracks
    (name: value) are cut to their limits; a missing flag is None, never a guess."""
    sim_id = _id(entry.get("sim_id"))
    if sim_id is None:
        return None
    labels = [_text(label, LABEL_MAX) for label in (entry.get("labels") or ())[:LABELS_PER_PERSON]]
    tracks = {}
    for name, value in list((entry.get("tracks") or {}).items())[:TRACKS_PER_PERSON]:
        key = _text(name, LABEL_MAX)
        if key is not None:
            tracks[key] = _int(value)
    return {"sim_id": sim_id,
            "first_name": _text(entry.get("first_name"), NAME_MAX),
            "last_name": _text(entry.get("last_name"), NAME_MAX),
            "labels": [label for label in labels if label is not None],
            "tracks": tracks,
            "household_id": _id(entry.get("household_id")),
            "has_home": _flag(entry.get("has_home")),
            "on_lot": _flag(entry.get("on_lot")),
            "waiting": _flag(entry.get("waiting"))}


def place_item(entry):
    """A place she can go: home, a household's home, or a venue by type. None without a zone id or a known kind."""
    zone_id = _id(entry.get("zone_id"))
    kind = entry.get("kind")
    if zone_id is None or kind not in PLACE_KINDS:
        return None
    return {"zone_id": zone_id, "kind": kind,
            "lot_name": _text(entry.get("lot_name"), 64),
            "venue": _text(entry.get("venue"), 64),
            "household_id": _id(entry.get("household_id"))}


def event_item(entry):
    """An event type from the user-facing situation types. None without a situation id."""
    situation_id = _id(entry.get("situation_id"))
    if situation_id is None:
        return None
    return {"situation_id": situation_id,
            "name_key": _text(entry.get("name_key"), 32),
            "cost": _int(entry.get("cost")),
            "schedulable": _flag(entry.get("schedulable"))}


CLEAN = {"people": person_item, "places": place_item, "events": event_item}
CAPS = {"people": PEOPLE_MAX, "places": PLACES_MAX, "events": EVENTS_MAX}


def clean_items(kind, entries):
    """The list's items as the probe writes them: cleaned, unique by their id, in the order given, at most the cap.
    None when entries is not a list."""
    if entries is None:
        return None
    cleaner = CLEAN[kind]
    seen = set()
    items = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        item = cleaner(entry)
        if item is None:
            continue
        key = item.get("sim_id") or item.get("zone_id") or item.get("situation_id")
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
        if len(items) >= CAPS[kind]:
            break
    return items


def split_parts(items):
    """The items cut into parts: at most LIST_PART_ITEMS each and under PART_BYTES_MAX packed. An empty list is one
    empty part, so a list that became empty is written as empty."""
    chunks = []
    current = []
    size = 2
    for item in items:
        item_bytes = _bytes(item) + 1
        if current and (len(current) >= LIST_PART_ITEMS or size + item_bytes > PART_BYTES_MAX):
            chunks.append(current)
            current = []
            size = 2
        current.append(item)
        size += item_bytes
    if current or not chunks:
        chunks.append(current)
    return chunks


class ListWriter(object):
    """2.40.0 (W13 P1): the lists, written in parts when their content changed. A list is read at most once every
    LIST_CHECK_S real seconds (tick), and every list is read now on a zone load or a lists_now command (force). The
    readers are given by kind; a reader that returns None (unreadable) writes nothing and keeps its digest.
    emit(kind, row) -> bool writes one record; a list counts as written only when all its parts were."""

    def __init__(self, emit, clock=time.monotonic, check_s=LIST_CHECK_S):
        self._emit = emit
        self._clock = clock
        self._check_s = check_s
        self._checked = {}
        self._digests = {}
        self._revs = {}

    def new_zone(self):
        """A new zone: the digests stay (an unchanged list is not written again), the check times do not."""
        self._checked = {}

    def due(self, kind, now):
        last = self._checked.get(kind)
        return last is None or now - last >= self._check_s

    def tick(self, readers, force=False, now=None):
        """Reads the lists that are due (all of them when force), and writes those whose digest changed. Returns the
        kinds written. Readers are {kind: callable() -> list of raw entries or None}."""
        now = self._clock() if now is None else now
        written = []
        for kind in LIST_KINDS:
            reader = readers.get(kind)
            if reader is None or not (force or self.due(kind, now)):
                continue
            self._checked[kind] = now
            entries = reader()
            if entries is None:
                continue
            if self.send(kind, entries):
                written.append(kind)
        return written

    def send(self, kind, entries):
        """Writes the list's parts if its digest differs from the one written last. True when it wrote them."""
        items = entries if kind == "things" else clean_items(kind, entries)
        if items is None:
            return False
        content = digest(items)
        if self._digests.get(kind) == content:
            return False
        rev = self._revs.get(kind, 0) + 1
        parts = split_parts(items)
        rows = [{"kind": kind, "list_rev": rev, "part": index, "parts": len(parts), "digest": content,
                 "count": len(items), "items": chunk} for index, chunk in enumerate(parts)]
        if not all(self._emit(kind, row) for row in rows):
            return False
        self._digests[kind] = content
        self._revs[kind] = rev
        return True


# ------------------------------------------------------------------ discovery

def discovery_sections(sections):
    """The discovery record's sections: the known ones that were read (None ones are left out). When the record would
    pass DISCOVERY_MAX_BYTES, the largest sections are left out until it fits, and the names of those left out are
    kept in `dropped`."""
    kept = {}
    for name in DISCOVERY_SECTIONS:
        value = sections.get(name)
        if value is not None:
            kept[name] = value
    dropped = []
    while kept and _bytes(kept) > DISCOVERY_MAX_BYTES:
        largest = max(kept, key=lambda name: _bytes(kept[name]))
        dropped.append(largest)
        del kept[largest]
    if dropped:
        kept["dropped"] = sorted(dropped)
    return kept


def picker_row(name, guid, minimums, filter_name, flags, radius, steps):
    """One phone picker of the discovery record: its guid, tuned minimums, filter class name, include flags, radius,
    and the step that drops each Sim she knows (sim ids only, never names)."""
    return {"name": _text(name, LABEL_MAX), "guid64": _id(guid), "min_required": _int(minimums),
            "filter": _text(filter_name, LABEL_MAX), "flags": sorted(set(_text(flag, 32) for flag in flags or ())
                                                                     - {None})[:8],
            "radius": _int(radius), "steps": [{"sim_id": _id(sim), "step": _text(step, 32)}
                                               for sim, step in list((steps or {}).items())[:32]
                                               if _id(sim) is not None]}


# ------------------------------------------------------------------ phone

def phone_event(kind, from_sim_id, notifies):
    """2.40.0 (W13 P1): a text or an incoming call for her, as the probe writes it. kind is text or call; from_sim_id
    the caller's or sender's sim id (digits); notifies the guid64 of the phone act it notifies, when readable."""
    if kind not in PHONE_KINDS:
        return None
    return {"kind": kind, "from_sim_id": _id(from_sim_id), "notifies": _id(notifies)}


def work_end_minute(end):
    """2.40.0 (W13 P1): the game minute of the day a work session ends, from the game's DateAndTime (hour and minute
    read by the caller). None unless both are whole numbers in range."""
    hour, minute = end
    if type(hour) is not int or type(minute) is not int or not 0 <= hour < 24 or not 0 <= minute < 60:
        return None
    return hour * 60 + minute


def start_minute(day_offset, hour, minute, now_minute, now_day):
    """The game minute of the day a start is asked for, as absolute minutes from day zero. day_offset is 0 or 1 (today
    or tomorrow). None when the hour or minute is out of range or the start is past (before now)."""
    if day_offset not in (0, 1) or type(hour) is not int or type(minute) is not int:
        return None
    if not 0 <= hour < 24 or not 0 <= minute < 60:
        return None
    absolute = (now_day + day_offset) * START_MINUTES_PER_DAY + hour * 60 + minute
    if absolute < now_day * START_MINUTES_PER_DAY + now_minute:
        return None
    return absolute


def sim_ids(value, limit):
    """Guest or picked sim ids: a list of at most limit digit strings. None when the value is not such a list."""
    if type(value) is not list or len(value) > limit:
        return None
    if not all(_id(item) == item and item is not None for item in value):
        return None
    return list(value)

