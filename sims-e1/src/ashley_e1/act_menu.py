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
import json
import time

from . import schema

REBUILD_S = 20.0
CANDIDATE_ACTS = 16
# 2.37.0 (W10 P3): her phone's candidates have their own cap (its scan is probe-side: e2_actuator.PHONE_SCAN_LIMIT).
PHONE_CANDIDATES = 96
# 2.37.0 (W10 P2): a far candidate's test outcome is kept this long (seconds), then tested again; cleared on a zone change.
FAR_CACHE_S = 120.0
# 2.37.1 (live 2026-10-12: outside her rooms the near part was her phone alone, and the house came only with the
# whole first build, minutes later): the first build in a zone writes the menu it has so far every FIRST_PARTIAL_S
# seconds, and steps with FIRST_BUDGET_MS a tick instead of the usual 8.
FIRST_PARTIAL_S = 15.0
FIRST_BUDGET_MS = 20.0
# Lights, candles, doors and windows come last within their room: ordering only; nothing is hidden.
FIXTURE_PARTS = ("light", "candle", "door", "window", "gate")
# 2.34.0 (N8, F4): the menu's objects per written part (a part is one act_menu record, under 48 KiB).
MENU_PART_OBJECTS = 16
# 2.35.0 (D3): a spot's id is one number from 1, kept for the probe's session for one (room, level, kind); at most 999.
SPOT_IDS_MAX = 999
# 2.39.0 (W12 C1): a near object is one within NEAR_M metres of her (the helper's NEAR_M, acts.py), or in her room,
# on her phone, or a Sim on her lot. The near part is written on every build, on her move into another room, and on a
# look (menu_near). Its distances are read when it is written.
NEAR_M = 4.0
# 2.39.0 (W12 C4): the game's refusals kept per object (at most this many; the near ones are shown).
REFUSALS_PER_OBJECT = 8


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


def is_near(job):
    """2.39.0 (W12 C1): a candidate near her: her phone, her room, a Sim on her lot, or within NEAR_M metres."""
    if job.get("phone") is True or job.get("same_room") is True:
        return True
    if job.get("person") is True and job.get("on_lot") is True:
        return True
    distance = job.get("distance_m")
    return distance is not None and distance <= NEAR_M


def fold_key(job):
    """2.39.0 (W12 C12): acts with the same words are one choice. The text key the game shows is the fold; the name
    stands in when there is no text key, and the guid (with its variant) when there is neither."""
    if job.get("text_key") is not None:
        return ("text", job.get("text_key"))
    name = job.get("name") or ""
    if name:
        return ("name", name)
    return ("guid", job.get("guid64"), job.get("variant"))


def is_far(job):
    """2.37.0 (W10 P2): a candidate the far cache may hold: not in her room, not her phone and not a Sim."""
    return job.get("same_room") is not True and job.get("phone") is not True and job.get("person") is not True


class FarCache(object):
    """2.37.0 (W10 P2): the test outcomes of far candidates, by (object id, guid64). An outcome is kept for FAR_CACHE_S
    seconds on the clock given, and is never a near candidate's (see is_far). clear() when the zone changes.
    2.38.0 (W11 P3): also kept by (definition id, guid64) when the candidate has a definition, so identical far objects
    share one test per act. The fields kept are the test's own (refused, reason_key); reach is asked per object.
    2.39.0 (W12 C3): a refusal is kept by the object only; a pass is shared by definition too. One occupied object
    never hides its identical kin."""

    def __init__(self, clock=time.monotonic, ttl_s=FAR_CACHE_S):
        self._clock = clock
        self._ttl_s = ttl_s
        self._entries = {}

    @staticmethod
    def _keys(job, ok=True):
        keys = [("object", job.get("object_id"), job.get("guid64"))]
        if ok and job.get("definition_id") is not None:
            keys.append(("definition", job.get("definition_id"), job.get("guid64")))
        return keys

    def get(self, job):
        """The stored outcome {ok, fields} of this candidate under either key, or None when it has none or it is too old."""
        for key in self._keys(job):
            entry = self._entries.get(key)
            if entry is None:
                continue
            stamp, outcome = entry
            if self._clock() - stamp >= self._ttl_s:
                self._entries.pop(key, None)
                continue
            return outcome
        return None

    def put(self, job, ok):
        """Keeps what the test said of this candidate: whether it passed, and the fields the test set on it."""
        fields = dict((name, job[name]) for name in ("refused", "reason_key") if name in job)
        entry = (self._clock(), {"ok": ok, "fields": fields})
        for key in self._keys(job, ok=ok):
            self._entries[key] = entry

    def clear(self):
        self._entries = {}


def note_excluded(kept, name, why):
    """2.37.0 (W10 P3): one phone act the guard excluded before its test, named with why; at most
    schema.MENU_MAX_EXCLUDED_PHONE, the first ones (a diagnostic, shown with the menu)."""
    if len(kept) < schema.MENU_MAX_EXCLUDED_PHONE:
        kept.append({"name": (name or "")[:128], "why": why})


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


def _shape_of(item):
    """What the menu shows of one object, for the same-menu check (distances are not compared here)."""
    refusals = item.get("refusals")
    return (item["object_id"], item.get("room"), item.get("reach"),
            tuple((act["guid64"], act.get("variant")) for act in item["acts"]),
            item.get("on_lot"), item.get("acts_cut"),
            None if refusals is None else tuple((r.get("text_key"), r.get("reason_key")) for r in refusals))


class MenuBuild(object):
    """One menu build: the jobs (one per act of each object) are tested in steps, each step within
    budget_ms and max_per_chunk. jobs may be a generator: its offers are read inside the steps too.
    failed is set when reading the jobs raised; a failed build publishes nothing."""

    def __init__(self, jobs, runner, budget_ms=8.0, max_per_chunk=80, clock=time.perf_counter, spots=None,
                 far=None, excluded_phone=None, on_near=None, reach=None, stages=None):
        self._jobs = iter(jobs)
        self._runner = runner
        # 2.38.0 (W11 P3): asks a job's own reach; run for a far candidate whose outcome the cache gave, since reach is per object.
        self._reach = reach
        self.budget_ms = budget_ms
        self.max_per_chunk = max_per_chunk
        self.clock = clock
        self._kept = []
        # 2.39.0 (W12): per object, in the order the build met it: its first job (its fields), its kept jobs, and the
        # game's refusals of its acts (at most REFUSALS_PER_OBJECT). A refusal-only object can still be near her.
        self._order = []
        self._heads = {}
        self._acts = {}
        self._refusals = {}
        # 2.39.0 (W12 G1): the choices of pie-menu acts this build kept: (object id, guid64, variant) -> the key the
        # push matches the choice by. Published with the menu, so an act names a choice the menu showed.
        self.variants = {}
        # 2.39.0 (W12 C11): how far each spot got (counters; probe._spot_offers counts them), shared with the build.
        self.spot_stages = {} if stages is None else stages
        # 2.35.0 (D3): the spots this build found, by spot id (the table an act names; published when it finishes).
        self.spots = {} if spots is None else spots
        # 2.35.0 (D3): her phone's offers the game refused, {name, reason_key}, at most schema.MENU_MAX_REFUSED_PHONE.
        self.refused_phone = []
        # 2.37.0 (W10 P3): her phone's acts the guard excluded before the test, {name, why} (a list the probe fills).
        self.excluded_phone = [] if excluded_phone is None else excluded_phone
        # 2.37.0 (W10 P2): the far cache (FarCache) and the hand-over of the near part (on_near(build), once).
        self._far = far
        self._on_near = on_near
        self._near_done = False
        self.tested = 0
        self.cached = 0
        self.refused = 0
        self.build_ms = 0.0
        self.done = False
        self.failed = False

    def _outcome(self, job):
        """2.37.0 (W10 P2): whether the job's act is on the menu. A far candidate the cache holds is not tested again;
        only a real test counts as tested. A candidate whose test raised is not kept in the cache."""
        far = self._far is not None and is_far(job)
        if far:
            hit = self._far.get(job)
            if hit is not None:
                self.cached += 1
                job.update(hit["fields"])
                if self._reach is not None:
                    try:
                        self._reach(job)
                    except Exception:
                        pass
                return hit["ok"]
        self.tested += 1
        try:
            ok = self._runner(job)
        except Exception:
            ok = False
            far = False
        if far:
            self._far.put(job, ok)
        return ok

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
            if not self._near_done and is_far(job):
                # 2.37.0 (W10 P2): every near candidate has been tested by now; the near part can be written.
                # 2.39.0 (W12 C1): on every build, not only the first in a zone.
                self._near_done = True
                if self._on_near is not None:
                    self._on_near(self)
            oid = job["object_id"]
            if oid not in self._heads:
                self._order.append(oid)
                self._heads[oid] = job
                self._acts[oid] = []
                self._refusals[oid] = []
            ok = self._outcome(job)
            if ok:
                self._kept.append(job)
                self._acts[oid].append(job)
                if job.get("variant") is not None:
                    self.variants[(str(oid), str(job["guid64"]), job["variant"])] = job.get("variant_key")
            else:
                self.refused += 1
                if job.get("refused") is True and len(self._refusals[oid]) < REFUSALS_PER_OBJECT:
                    self._refusals[oid].append(job)
                if (job.get("phone") is True and job.get("refused") is True
                        and len(self.refused_phone) < schema.MENU_MAX_REFUSED_PHONE):
                    self.refused_phone.append({"name": (job.get("name") or "")[:128],
                                               "reason_key": job.get("reason_key")})
        self.build_ms += (self.clock() - start) * 1000.0

    def payload(self, menu_rev, room, near=False, refresh=None):
        """The whole menu as one payload (near=False), or its near part (near=True: only the near objects, each read
        again through refresh(head), which gives the fields read at write time: distance_m, room, same_room).
        Objects are in the order the build met them, nearest first: her room, the phone, the people, the rooms, what
        is off the lot. At most schema.MENU_MAX_OBJECTS; what the cap leaves out is counted in dropped. An act's texts
        are folded before the per-object cap, and the passing acts the cap leaves out are counted (acts_cut).
        part 0 of 1: parts() cuts it into rows."""
        objects = []
        for oid in self._order:
            head = self._heads[oid]
            view = dict(head)
            if refresh is not None:
                view.update(refresh(head) or {})
            near_now = is_near(view)
            if near and not near_now:
                continue
            acts, cut = self._act_rows(oid, view)
            refusals = None
            # Her phone's refusals are already named in refused_phone (2.35.0), so the phone carries none here.
            if near_now and head.get("phone") is not True:
                refusals = [{"text_key": job.get("text_key"), "reason_key": job.get("reason_key")}
                            for job in self._refusals[oid]]
            if not acts and not refusals:
                continue
            on_lot = view.get("on_lot")
            objects.append({
                "object_id": oid, "definition_id": head.get("definition_id"),
                "class": (head.get("class") or "")[:96], "distance_m": view.get("distance_m"),
                "same_room": view.get("same_room"), "room": _room_text(view.get("room")),
                "reach": head.get("reach"),
                "phone": True if head.get("phone") is True else None,
                "spot": head.get("spot"), "level": head.get("level"), "acts": acts,
                "on_lot": on_lot if on_lot in (True, False) else None,
                "acts_cut": cut, "refusals": refusals})
        kept = objects[:schema.MENU_MAX_OBJECTS]
        dropped_objects = objects[schema.MENU_MAX_OBJECTS:]
        rooms = []
        for item in dropped_objects:
            if item["room"] is not None and item["room"] not in rooms and len(rooms) < schema.MENU_MAX_DROPPED_ROOMS:
                rooms.append(item["room"])
        # 2.37.0 (W10 P2, P3): cached counts the candidates whose outcome the far cache gave (tested counts real tests).
        return {"menu_rev": menu_rev, "room": room, "objects": kept,
                "tested": self.tested, "cached": self.cached, "refused": self.refused,
                "build_ms": round(self.build_ms, 2), "part": 0, "parts": 1,
                "refused_phone": list(self.refused_phone),
                "excluded_phone": list(self.excluded_phone),
                "dropped": {"objects": len(dropped_objects), "rooms": rooms},
                "spot_stages": dict(self.spot_stages) or None}

    def _act_rows(self, oid, view):
        """2.39.0 (W12 C12): the acts of one object: texts folded (the first of each text kept), at most the
        per-object cap, and the passing acts past the cap counted. A pie choice carries its variant."""
        cap = schema.MENU_MAX_PHONE_ACTS if view.get("phone") is True else schema.MENU_MAX_ACTS
        seen = set()
        acts = []
        cut = 0
        for job in self._acts[oid]:
            key = fold_key(job)
            if key in seen:
                continue
            seen.add(key)
            if len(acts) >= cap:
                cut += 1
                continue
            # The variant is always written (None for an act that is not a pie choice), so a part's size is what it is.
            acts.append({"guid64": job["guid64"], "name": (job.get("name") or "")[:128],
                         "text_key": job.get("text_key"), "variant": job.get("variant")})
        return acts, cut


def _room_text(room):
    return None if room is None else str(room)[:64]


def parts(payload):
    """2.34.0 (F4): the menu as rows, each row a whole menu's part (part of parts, with the same menu_rev). A row holds
    at most MENU_PART_OBJECTS objects and stays under PART_BYTES_MAX (2.39.0, W12 C8: packed by bytes too, since an
    object with its refusals is larger). An empty menu is one empty part. dropped and spot_stages go on part 0 only."""
    objects = payload["objects"]
    envelope = dict(payload, objects=[], refused_phone=None, excluded_phone=None)
    base = _part_bytes(envelope)
    chunks = []
    current = []
    size = base
    for item in objects:
        item_bytes = _part_bytes(item) + 1
        if current and (len(current) >= MENU_PART_OBJECTS or size + item_bytes > PART_BYTES_MAX):
            chunks.append(current)
            current = []
            size = base
        current.append(item)
        size += item_bytes
    if current or not chunks:
        chunks.append(current)
    count = len(chunks)
    # 2.35.0 (D3): the phone's refusals are written once, on part 0. 2.37.0 (P3): so are the phone's exclusions.
    rows = [dict(payload, objects=chunk, part=index, parts=count,
                 refused_phone=payload.get("refused_phone") if index == 0 else None,
                 excluded_phone=payload.get("excluded_phone") if index == 0 else None,
                 dropped=payload.get("dropped") if index == 0 else None,
                 spot_stages=payload.get("spot_stages") if index == 0 else None)
            for index, chunk in enumerate(chunks)]
    # 2.37.0 (W10 P3): part 0 carries the phone's diagnostics; when they would push it past the record limit, the
    # last exclusions go first, then the last refusals (a diagnostic is shortened; the menu is never lost).
    first = rows[0]
    for key in ("excluded_phone", "refused_phone"):
        while first.get(key) and _part_bytes(first) > PART_BYTES_MAX:
            first[key] = first[key][:-1]
    return rows


# 2.37.0 (W10 P3): a part's payload stays this far under the record limit (the record's envelope needs the rest).
PART_BYTES_MAX = schema.MAX_SERIALIZED_RECORD_BYTES - 4096


def _part_bytes(row):
    return len(json.dumps(row, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def near_signature(payload):
    """2.39.0 (W12 C1): what a near part shows, distances included (for a test that a write changed something)."""
    return (payload.get("menu_rev"), payload.get("room"),
            tuple((item["object_id"], item.get("room"), item.get("same_room"), item.get("distance_m"),
                   tuple((act["guid64"], act.get("variant")) for act in item["acts"]))
                  for item in payload["objects"]))


def same_menu(left, right):
    """Two payloads offer the same choices (revision and timings aside)."""
    if left is None or right is None:
        return False

    def shape(payload):
        return [_shape_of(item) for item in payload["objects"]]
    return (shape(left) == shape(right) and left.get("room") == right.get("room")
            and left.get("refused_phone") == right.get("refused_phone")
            and left.get("excluded_phone") == right.get("excluded_phone")
            and left.get("dropped") == right.get("dropped"))
