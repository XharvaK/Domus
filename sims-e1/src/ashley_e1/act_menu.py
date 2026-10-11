"""8f (2.16.0): what Ashley can do in her home, as the game offers it. No game imports.

The probe lists the objects of the lot she is on (her room first), and for each the
user-directed affordances the trial guard does not exclude. This builder asks the game,
a few at a time within a small budget per sampling tick, whether it would refuse each
one now (the same test a player's click runs, no push). What passes is the menu.

2.34.0 (N8, F4): the menu covers every object on the lot that offers her something, not
the nearest few. Each object keeps its room. The build is stepped across sampling ticks,
reading the offers of one object at a time, and the menu is written in parts small
enough for one record.
"""
import time

from . import schema

REBUILD_S = 20.0
CANDIDATE_ACTS = 16
# Lights, candles, doors and windows come last within their room: ordering only; nothing is hidden.
FIXTURE_PARTS = ("light", "candle", "door", "window", "gate")
# 2.34.0 (N8, F4): the menu's objects per written part (a part is one act_menu record, under 48 KiB).
MENU_PART_OBJECTS = 16
# 2.35.0 (D3): a spot's id is one number from 1, kept for the probe's session for one (room, level, kind); at most 999.
SPOT_IDS_MAX = 999


def fixture(item):
    klass = (item.get("class") or "").lower()
    return any(part in klass for part in FIXTURE_PARTS)


class SpotIds(object):
    """2.35.0 (D3): the spot ids of one probe session. The first time a (room, level, kind) is seen it gets the next
    id from 1 and keeps it for the session, so an id never names another spot. None once 999 keys have ids."""

    def __init__(self):
        self._ids = {}

    def id_for(self, room, level, kind):
        key = (room, level, kind)
        if key not in self._ids:
            if len(self._ids) >= SPOT_IDS_MAX:
                return None
            self._ids[key] = len(self._ids) + 1
        return self._ids[key]


def ordered(objects):
    """2.16.2 (live 2026-10-05: on the sidewalk the nearest 24 objects were the street, and
    21 of them offered nothing): her room, then the rest of the lot she is on, then what is
    off the lot, each nearest first. Items carry distance_m, same_room and on_lot; an
    object with no position and not on the lot is left out."""
    def tier(item):
        if item.get("same_room") is True:
            return 0
        return 1 if item.get("on_lot") is True else 2

    def order(item):
        distance = item.get("distance_m")
        return (tier(item), distance is None, distance or 0.0, item.get("object_id") or "")
    kept = [item for item in objects
            if item.get("distance_m") is not None or item.get("same_room") is True or item.get("on_lot") is True]
    return sorted(kept, key=order)


def _room_key(item):
    if item.get("phone") is True:
        return "phone"
    if item.get("person") is True:
        return "people"
    if item.get("same_room") is True:
        return "here"
    if item.get("on_lot") is not True:
        return "off"
    return item.get("room")


def _within_room(item):
    """Within a room: objects first, fixtures last among them, and a spot (2.35.0, D3: her way there) after the
    room's objects, so the helper can keep a spot until its room's objects are gone."""
    return (item.get("spot") is not None, fixture(item))


def iter_pick(items, offers):
    """(item, acts) for every item that offers her something, one item at a time (offers(item) is read
    only when the caller asks for the next pair, so a build can be stepped across ticks). Her room first,
    then her phone (2.29.0: one entry, never folded), then the people she can reach, then each other room
    nearest first, then what is off the lot. Within a room, fixtures come last. 2.34.0 (F4): no cap on
    the number of objects and no folding of identical choices: every object with acts is listed."""
    groups = []
    by_key = {}
    for item in items:
        key = _room_key(item)
        if key not in by_key:
            by_key[key] = []
            groups.append(key)
        by_key[key].append(item)
    for key in groups:
        by_key[key].sort(key=_within_room)  # stable: nearest first within each kind
    rooms = [key for key in groups if key not in ("here", "off", "people", "phone")]
    sequence = [key for key in ("here", "phone", "people") if key in by_key] + rooms + \
        [key for key in ("off",) if key in by_key]
    for key in sequence:
        for item in by_key[key]:
            acts = offers(item)
            if acts:
                yield item, acts


def pick(items, offers):
    """The list form of iter_pick (tests and small menus)."""
    return list(iter_pick(items, offers))


class MenuBuild(object):
    """One menu build: the jobs (one per act of each object) are tested in steps, each step within
    budget_ms and max_per_chunk. jobs may be a generator: its offers are read inside the steps too.
    failed is set when reading the jobs raised; a failed build publishes nothing."""

    def __init__(self, jobs, runner, budget_ms=8.0, max_per_chunk=80, clock=time.perf_counter, spots=None):
        self._jobs = iter(jobs)
        self._runner = runner
        self.budget_ms = budget_ms
        self.max_per_chunk = max_per_chunk
        self.clock = clock
        self._kept = []
        # 2.35.0 (D3): the spots this build found, by spot id (the table an act names; published when it finishes).
        self.spots = {} if spots is None else spots
        # 2.35.0 (D3): her phone's offers the game refused, {name, reason_key}, at most schema.MENU_MAX_REFUSED_PHONE.
        self.refused_phone = []
        self.tested = 0
        self.refused = 0
        self.build_ms = 0.0
        self.done = False
        self.failed = False

    def step(self):
        if self.done:
            return
        start = self.clock()
        processed = 0
        while processed < self.max_per_chunk:
            if (self.clock() - start) * 1000.0 >= self.budget_ms:
                break
            try:
                job = next(self._jobs)
            except StopIteration:
                self.done = True
                break
            except Exception:
                self.failed = self.done = True
                break
            processed += 1
            self.tested += 1
            try:
                ok = self._runner(job)
            except Exception:
                ok = False
            if ok:
                self._kept.append(job)
            else:
                self.refused += 1
                if (job.get("phone") is True and job.get("refused") is True
                        and len(self.refused_phone) < schema.MENU_MAX_REFUSED_PHONE):
                    self.refused_phone.append({"name": (job.get("name") or "")[:128],
                                               "reason_key": job.get("reason_key")})
        self.build_ms += (self.clock() - start) * 1000.0

    def payload(self, menu_rev, room):
        """The whole menu as one payload: nearest objects first (her room, the phone, the people, the rooms,
        what is off the lot), each with its room, at most MENU_MAX_OBJECTS objects with at most MENU_MAX_ACTS
        acts each, acts in the order the game listed them. part 0 of 1: parts() cuts it into rows."""
        by_object = {}
        order = []
        for job in self._kept:
            key = job["object_id"]
            if key not in by_object:
                by_object[key] = {
                    "object_id": job["object_id"], "definition_id": job.get("definition_id"),
                    "class": (job.get("class") or "")[:96], "distance_m": job.get("distance_m"),
                    "same_room": job.get("same_room"), "room": _room_text(job.get("room")),
                    "reach": job.get("reach"),
                    "phone": True if job.get("phone") is True else None,
                    "spot": job.get("spot"), "level": job.get("level"), "acts": []}
                order.append(key)
            acts = by_object[key]["acts"]
            if len(acts) < schema.MENU_MAX_ACTS and all(a["guid64"] != job["guid64"] for a in acts):
                acts.append({"guid64": job["guid64"], "name": (job.get("name") or "")[:128],
                             "text_key": job.get("text_key")})
        objects = [by_object[key] for key in order][:schema.MENU_MAX_OBJECTS]
        return {"menu_rev": menu_rev, "room": room, "objects": objects,
                "tested": self.tested, "refused": self.refused,
                "build_ms": round(self.build_ms, 2), "part": 0, "parts": 1,
                "refused_phone": list(self.refused_phone)}


def _room_text(room):
    return None if room is None else str(room)[:64]


def parts(payload):
    """2.34.0 (F4): the menu as rows of at most MENU_PART_OBJECTS objects, each row a whole menu's part
    (part of parts, with the same menu_rev). An empty menu is one empty part."""
    objects = payload["objects"]
    count = max(1, -(-len(objects) // MENU_PART_OBJECTS))
    # 2.35.0 (D3): the phone's refusals are written once, on part 0.
    return [dict(payload, objects=objects[index * MENU_PART_OBJECTS:(index + 1) * MENU_PART_OBJECTS],
                 part=index, parts=count,
                 refused_phone=payload.get("refused_phone") if index == 0 else None) for index in range(count)]


def same_menu(left, right):
    """Two payloads offer the same choices (revision and timings aside)."""
    if left is None or right is None:
        return False
    def shape(payload):
        return [(item["object_id"], item.get("room"), item.get("reach"), tuple(act["guid64"] for act in item["acts"]))
                for item in payload["objects"]]
    return (shape(left) == shape(right) and left.get("room") == right.get("room")
            and left.get("refused_phone") == right.get("refused_phone"))
