"""8f (2.16.0): what Ashley can do near her body, as the game offers it. No game imports.

The probe lists the objects near her (her room, or within NEAR_M), and for each the
user-directed affordances the trial guard does not exclude. This builder asks the game,
a few at a time within a small budget per sampling tick, whether it would refuse each
one now (the same test a player's click runs, no push). What passes is the menu.
"""
import time

from . import schema

NEAR_M = 8.0
REBUILD_S = 20.0
CANDIDATE_OBJECTS = 24
CANDIDATE_ACTS = 16


def near(objects, limit=CANDIDATE_OBJECTS):
    """Objects in her room or within NEAR_M first, then (2.16.1) the nearest of the rest, so
    standing outside she still sees her house, not only the mailbox (live 2026-10-05). Items
    carry distance_m and same_room; an object with no position comes last."""
    def order(item):
        return (item.get("distance_m") is None, item.get("distance_m") or 0.0, item.get("object_id") or "")
    close = [item for item in objects
             if item.get("same_room") is True or
             (item.get("distance_m") is not None and item["distance_m"] <= NEAR_M)]
    rest = [item for item in objects if item not in close and item.get("distance_m") is not None]
    close.sort(key=order)
    rest.sort(key=order)
    return (close + rest)[:limit]


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
