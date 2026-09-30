"""Pure E2 handle registry: claim ladder over plain-data presence rows.

No game imports and no I/O (plan E2 §8.3). Claims are separate facts and are
never collapsed; anything not proven stays OUTCOME_UNKNOWN. Polling absence
never becomes FINISHED; only the game's finishing callback sets FINISHED.
"""

from . import e2_admission

WINDOW_SECONDS = 60.0
MAINTAIN_SECONDS = 10.0
SIGNATURE_WINDOW_SECONDS = 30.0
CONTINUATION_WINDOW_SECONDS = 30.0
RUNNING_MEMBERSHIPS = ("RUNNING", "QUEUED_AND_RUNNING")
CLAIM_ORDER = ("REQUEST_ACCEPTED", "ENQUEUED", "STARTED", "EFFECT_OBSERVED",
               "ATTRIBUTED", "MAINTAINED_10S", "FINISHED")

PASS = "PASS"
OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


def _entries(row):
    return (row.get("interactions") or {}).get("observed") or []


def _posture(row):
    return ((row.get("body") or {}).get("posture")) or {}


class Experiment:
    def __init__(self, experiment_id, token, object_id, sim_id, interaction_id,
                 pushed_mono_ns, signature, baseline_ids, continuation=()):
        self.experiment_id = experiment_id
        self.token = token
        self.object_id = object_id
        self.sim_id = sim_id
        self.interaction_id = interaction_id
        self.pushed_mono_ns = pushed_mono_ns
        self.signature = signature
        self.continuation = frozenset(continuation)
        self.known_ids = set(i for i in baseline_ids if i is not None)
        self.claims = dict((key, False) for key in CLAIM_ORDER)
        self.claims["REQUEST_ACCEPTED"] = True
        self.foreign_roots = []
        self.continuation_entries = []
        self.incomplete_rows = 0
        self.started_ns = None
        self.effect_since_ns = None
        self.attributed_ns = None
        self.maintenance_broken = False
        self.finishing_type = None
        self.closed = False
        self.verdict = None

    def observe(self, row):
        """Advance claims from one presence row; returns newly set claim names."""
        if self.closed:
            return []
        before = dict(self.claims)
        mono = row.get("monotonic_ns")
        if row.get("observation_complete") is not True:
            self.incomplete_rows += 1
        posture = _posture(row)
        seated = (posture.get("target_id") == self.object_id and
                  self.signature is not None and
                  posture.get("posture_name") == self.signature)
        ours = None
        for entry in _entries(row):
            iid = entry.get("interaction_id")
            if iid is not None and iid == self.interaction_id:
                ours = entry
                continue
            source = entry.get("source_raw")
            membership = entry.get("membership")
            if iid is not None and iid in self.continuation_entries:
                if membership in RUNNING_MEMBERSHIPS:
                    self.continuation_entries.remove(iid)
                    if iid not in self.foreign_roots:
                        self.foreign_roots.append(iid)
                continue
            autonomy_on_object = (
                source == "InteractionSource.AUTONOMY" and
                entry.get("target_id") == self.object_id)
            if autonomy_on_object and iid is not None:
                is_continuation = (
                    iid not in self.known_ids and
                    iid not in self.foreign_roots and
                    entry.get("affordance_id") in self.continuation and
                    seated and
                    membership == "QUEUED")
                if is_continuation:
                    self.continuation_entries.append(iid)
                    self.known_ids.add(iid)
                    continue
                if iid not in self.foreign_roots:
                    self.foreign_roots.append(iid)
                self.known_ids.add(iid)
                continue
            if iid is None or iid in self.known_ids:
                continue
            self.known_ids.add(iid)
            if source in e2_admission.BUSY_SOURCES:
                self.foreign_roots.append(iid)
        if ours is not None:
            self.claims["ENQUEUED"] = True
            if ours.get("membership") in RUNNING_MEMBERSHIPS and self.started_ns is None:
                self.started_ns = mono
                self.claims["STARTED"] = True
        if seated:
            self.claims["EFFECT_OBSERVED"] = True
            if self.effect_since_ns is None:
                self.effect_since_ns = mono
        else:
            self.effect_since_ns = None
            if self.claims["ATTRIBUTED"] and not self.claims["MAINTAINED_10S"]:
                # Maintenance must be continuous from attribution; a later
                # re-seat is a new, unattributed effect.
                self.maintenance_broken = True
        if (seated and self.claims["STARTED"] and not self.claims["ATTRIBUTED"] and
                not self.foreign_roots and self.incomplete_rows == 0 and
                self.started_ns is not None and self.started_ns <= mono):
            self.claims["ATTRIBUTED"] = True
            self.attributed_ns = mono
        if (self.claims["ATTRIBUTED"] and seated and not self.foreign_roots and
                not self.maintenance_broken and
                self.effect_since_ns is not None and
                mono - max(self.effect_since_ns, self.attributed_ns) >=
                MAINTAIN_SECONDS * 1e9):
            self.claims["MAINTAINED_10S"] = True
        if mono - self.pushed_mono_ns >= WINDOW_SECONDS * 1e9:
            self.close()
        return [key for key in CLAIM_ORDER if self.claims[key] and not before[key]]

    def finish(self, finishing_type):
        if self.finishing_type is None:
            self.finishing_type = finishing_type
        self.claims["FINISHED"] = True

    def close(self):
        if self.closed:
            return self.verdict
        self.closed = True
        if self.claims["ATTRIBUTED"] and self.claims["MAINTAINED_10S"]:
            self.verdict = PASS
        else:
            self.verdict = OUTCOME_UNKNOWN
        return self.verdict


class SignatureLearner:
    """Learn the seated posture name from an Owner pie-menu sit on the object.

    The Host never guesses which posture name means "seated": the name is
    taken from what the game reports after the Owner's own Sit click (N5).
    """

    def __init__(self):
        self.signatures = {}
        self.continuation = {}
        self._pending = {}
        self._seen_first = {}
        self._cont_since = {}
        self._cont_excluded = {}
        self._cont_closed = set()
        self.continuation_events = []

    def observe(self, row, open_harness_ids):
        """Returns (object_id, posture_name) when a signature is learned.

        When a continuation window closes, appends (object_id, detail) to
        ``self.continuation_events`` (emitted once per object).
        """
        self.continuation_events = []
        mono = row.get("monotonic_ns")
        if row.get("observation_complete") is not True:
            return None
        for entry in _entries(row):
            iid = entry.get("interaction_id")
            if iid is not None and iid not in self._seen_first:
                self._seen_first[iid] = mono
        for entry in _entries(row):
            if (entry.get("source_raw") == "InteractionSource.PIE_MENU" and
                    entry.get("affordance_id") == e2_admission.SIT_AFFORDANCE_GUID and
                    entry.get("target_id") is not None and
                    entry.get("interaction_id") not in open_harness_ids):
                self._pending.setdefault(entry["target_id"], mono)
        posture = _posture(row)
        target = posture.get("target_id")
        name = posture.get("posture_name")
        learned = None
        for object_id, since in list(self._pending.items()):
            if mono - since > SIGNATURE_WINDOW_SECONDS * 1e9:
                self._pending.pop(object_id)
                continue
            if target == object_id and name is not None and object_id not in self.signatures:
                self.signatures[object_id] = name
                self._pending.pop(object_id)
                self.continuation.setdefault(object_id, set())
                self._cont_excluded.setdefault(object_id, set())
                self._cont_since[object_id] = mono
                learned = (object_id, name)
        self._observe_continuation(row, open_harness_ids, target, mono)
        return learned

    def _observe_continuation(self, row, open_harness_ids, target, mono):
        for object_id, m0 in list(self._cont_since.items()):
            if object_id in self._cont_closed:
                continue
            seated_here = target == object_id
            timed_out = mono - m0 > CONTINUATION_WINDOW_SECONDS * 1e9
            if seated_here:
                for entry in _entries(row):
                    self._consider_continuation_entry(
                        object_id, entry, open_harness_ids, m0)
            if (not seated_here) or timed_out:
                learned = self.continuation.setdefault(object_id, set())
                detail = ",".join(sorted(learned))
                self.continuation_events.append((object_id, detail))
                self._cont_closed.add(object_id)
                self._cont_since.pop(object_id, None)

    def _consider_continuation_entry(self, object_id, entry, open_harness_ids, m0):
        if entry.get("source_raw") != "InteractionSource.AUTONOMY":
            return
        if entry.get("target_id") != object_id:
            return
        iid = entry.get("interaction_id")
        if iid is None or iid in open_harness_ids:
            return
        first = self._seen_first.get(iid)
        if first is None or first < m0:
            return
        aff = entry.get("affordance_id")
        if aff is None:
            return
        excluded = self._cont_excluded.setdefault(object_id, set())
        learned = self.continuation.setdefault(object_id, set())
        if entry.get("membership") in RUNNING_MEMBERSHIPS:
            excluded.add(aff)
            learned.discard(aff)
            return
        if entry.get("membership") == "QUEUED" and aff not in excluded:
            learned.add(aff)
