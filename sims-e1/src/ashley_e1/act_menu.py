"""8f (2.16.0): what Ashley can do in her home, as the game offers it. No game imports.

The probe lists the objects of the lot she is on (her room first), and for each the
user-directed affordances the trial guard does not exclude. This builder asks the game,
a few at a time within a small budget per sampling tick, whether it would refuse each
one now (the same test a player's click runs, no push). What passes is the menu.
"""
import time

from . import schema

REBUILD_S = 20.0
CANDIDATE_OBJECTS = 30
CANDIDATE_ACTS = 16
# 2.16.3 (live 2026-10-06: tired and hungry, her 12-object menu was the piano room and the
# bathroom; the bed and the kitchen never made the list): her room keeps a few slots, then
# every other room gets one object before any room gets a second. Choosing a thing in
# another room is how she moves around the house.
HER_ROOM_OBJECTS = 4
ROOM_OBJECTS = 3
# 2.17.0: the people she can reach (on this lot, or within PEOPLE_NEAR_M) come right after
# her room, nearest first: greeting the neighbours at the door, inviting them in.
PEOPLE_OBJECTS = 3
PEOPLE_NEAR_M = 15.0
# Objects whose offers are read for one build: bounds the work of a single sampling tick.
SCAN_OBJECTS = 120
# Lights, candles, doors and windows come last within their room: they have offers in every
# room and would take the one slot a room gets. Ordering only; nothing is hidden.
FIXTURE_PARTS = ("light", "candle", "door", "window", "gate")


def fixture(item):
    klass = (item.get("class") or "").lower()
    return any(part in klass for part in FIXTURE_PARTS)


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
    if item.get("person") is True:
        return "people"
    if item.get("same_room") is True:
        return "here"
    if item.get("on_lot") is not True:
        return "off"
    return item.get("room")


def _choice(acts):
    """The set of act ids an object offers, None when the acts carry none."""
    guids = [act.get("guid64") if isinstance(act, dict) else None for act in acts]
    return None if None in guids else frozenset(guids)


def pick(items, offers, limit=CANDIDATE_OBJECTS, scan=SCAN_OBJECTS):
    """[(item, acts)] for a build. items come from ordered(). offers(item) lists the item's
    candidate acts. Her room first (at most HER_ROOM_OBJECTS); then rounds over the other
    rooms of the lot, nearest room first, one object per room per round (at most
    ROOM_OBJECTS each); what is off the lot comes last. Within a room, fixtures come last.
    An object that offers nothing is passed over before it counts toward limit; one object
    per definition (four dining chairs are one choice), one per set of acts. At most scan objects have their
    offers read."""
    groups = []
    by_key = {}
    for item in items:
        key = _room_key(item)
        if key not in by_key:
            by_key[key] = []
            groups.append(key)
        by_key[key].append(item)
    for key in groups:
        by_key[key].sort(key=fixture)  # stable: nearest first within each kind
    rooms = [key for key in groups if key not in ("here", "off", "people")]
    picked = []
    definitions = set()
    choices = set()
    state = {"scanned": 0}
    cursor = {key: 0 for key in groups}

    def take(key):
        """The next object of this room with offers, or None when the room is spent."""
        queue = by_key[key]
        while cursor[key] < len(queue) and state["scanned"] < scan:
            item = queue[cursor[key]]
            cursor[key] += 1
            definition = item.get("definition_id")
            if definition is not None and definition in definitions:
                continue
            state["scanned"] += 1
            acts = offers(item)
            if not acts:
                continue
            # 2.19.0 (live 2026-10-06: three mirrors with the same five acts, and the
            # kitchen never listed): an object offering exactly the acts of one already
            # picked is the same choice again. People are never folded.
            same = None if item.get("person") is True else _choice(acts)
            if same is not None and same in choices:
                continue
            if definition is not None:
                definitions.add(definition)
            if same is not None:
                choices.add(same)
            return item, acts
        return None

    def full():
        return len(picked) >= limit or state["scanned"] >= scan

    if "here" in by_key:
        for _ in range(HER_ROOM_OBJECTS):
            if full():
                break
            found = take("here")
            if found is None:
                break
            picked.append(found)
    if "people" in by_key:
        for _ in range(PEOPLE_OBJECTS):
            if full():
                break
            found = take("people")
            if found is None:
                break
            picked.append(found)
    for _round in range(ROOM_OBJECTS):
        for key in rooms:
            if full():
                return picked
            found = take(key)
            if found is not None:
                picked.append(found)
    if "off" in by_key:
        for _ in range(ROOM_OBJECTS):
            if full():
                break
            found = take("off")
            if found is None:
                break
            picked.append(found)
    return picked


class MenuBuild(object):
    def __init__(self, jobs, runner, budget_ms=8.0, max_per_chunk=80, clock=time.perf_counter):
        self._jobs = list(jobs)
        self._runner = runner
        self.budget_ms = budget_ms
        self.max_per_chunk = max_per_chunk
        self.clock = clock
        self._index = 0
        self._kept = []
        self.tested = 0
        self.refused = 0
        self.build_ms = 0.0
        self.done = not self._jobs

    def step(self):
        if self.done:
            return
        start = self.clock()
        processed = 0
        while self._index < len(self._jobs) and processed < self.max_per_chunk:
            if (self.clock() - start) * 1000.0 >= self.budget_ms:
                break
            job = self._jobs[self._index]
            self._index += 1
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
        self.build_ms += (self.clock() - start) * 1000.0
        if self._index >= len(self._jobs):
            self.done = True

    def payload(self, menu_rev, room):
        """The act_menu payload: nearest objects first, at most MENU_MAX_OBJECTS with
        at most MENU_MAX_ACTS acts each, acts in the order the game listed them."""
        by_object = {}
        order = []
        for job in self._kept:
            key = job["object_id"]
            if key not in by_object:
                by_object[key] = {
                    "object_id": job["object_id"], "definition_id": job.get("definition_id"),
                    "class": (job.get("class") or "")[:96], "distance_m": job.get("distance_m"),
                    "same_room": job.get("same_room"), "acts": []}
                order.append(key)
            acts = by_object[key]["acts"]
            if len(acts) < schema.MENU_MAX_ACTS and all(a["guid64"] != job["guid64"] for a in acts):
                acts.append({"guid64": job["guid64"], "name": (job.get("name") or "")[:128],
                             "text_key": job.get("text_key")})
        objects = [by_object[key] for key in order][:schema.MENU_MAX_OBJECTS]
        return {"menu_rev": menu_rev, "room": room, "objects": objects,
                "tested": self.tested, "refused": self.refused,
                "build_ms": round(self.build_ms, 2)}


def same_menu(left, right):
    """Two payloads offer the same choices (revision and timings aside)."""
    if left is None or right is None:
        return False
    def shape(payload):
        return [(item["object_id"], tuple(act["guid64"] for act in item["acts"]))
                for item in payload["objects"]]
    return shape(left) == shape(right) and left.get("room") == right.get("room")
