"""Pure E2 handle registry: claim ladder over plain-data presence rows.

No game imports and no I/O (plan E2 §8.3). Claims are separate facts and are
never collapsed; anything not proven stays OUTCOME_UNKNOWN. Polling absence
never becomes FINISHED; only the game's finishing callback sets FINISHED.
"""

from . import e2_admission
from . import e2_cards

WINDOW_SECONDS = 60.0
# DA6 trials may route across the lot first (first live crawl: start at ~67-70 s).
TRIAL_WINDOW_SECONDS = 180.0
# A cooked meal is eaten after the crafting phases. Hunger, not the 180 s card, judges it.
FOOD_TRIAL_WINDOW_SECONDS = 600.0
# D6 (live 2026-10-04): a 40 s snack held her for the whole 600 s window, about ten
# sim-hours idle. A need trial closes once its effect held, or once its family has
# been gone this long (the card's own grace has passed by then).
NEED_SETTLE_SECONDS = 30.0
MAINTAIN_SECONDS = 10.0
SIGNATURE_WINDOW_SECONDS = 30.0
CONTINUATION_WINDOW_SECONDS = 30.0
RUNNING_MEMBERSHIPS = ("RUNNING", "QUEUED_AND_RUNNING")
CLAIM_ORDER = ("REQUEST_ACCEPTED", "ENQUEUED", "STARTED", "EFFECT_OBSERVED",
               "ATTRIBUTED", "MAINTAINED_10S", "FINISHED")

PASS = "PASS"
OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
INTERRUPTED = "INTERRUPTED"
FAMILY_SOURCES = ("InteractionSource.SCRIPT_WITH_USER_INTENT", "InteractionSource.SCRIPT")
FAMILY_SECONDS = 5.0
OURS_LIVE = ("RUNNING", "QUEUED", "QUEUED_AND_RUNNING")


def _entries(row):
    return (row.get("interactions") or {}).get("observed") or []


def _posture(row):
    return ((row.get("body") or {}).get("posture")) or {}


class Experiment:
    def __init__(self, experiment_id, token, object_id, sim_id, interaction_id,
                 pushed_mono_ns, signature, baseline_ids, continuation=(),
                 card=None, control_rows=None, window_seconds=WINDOW_SECONDS,
                 food_route=None):
        self.experiment_id = experiment_id
        self.token = token
        self.object_id = object_id
        self.sim_id = sim_id
        self.interaction_id = interaction_id
        self.pushed_mono_ns = pushed_mono_ns
        self.signature = signature
        self.continuation = frozenset(continuation)
        if card is None:
            card = e2_cards.posture_card(object_id, signature)
        else:
            e2_cards.validate_card(card)
        self.card = card
        self.control_rows = list(control_rows or ())
        self.window_seconds = window_seconds
        self.food_route = food_route
        # D13: low body motives this trial relieves; a relief trial is not cut short.
        self.relief = []
        self.ambiguous = []
        self._rows_since = []
        self.known_ids = set(i for i in baseline_ids if i is not None)
        self.claims = dict((key, False) for key in CLAIM_ORDER)
        self.claims["REQUEST_ACCEPTED"] = True
        self.foreign_roots = []
        self.continuation_entries = []
        # A25: QUEUED AUTONOMY mixers on the trial object while our own action
        # runs (TV watch-passive every ~10 s) belong to our action, not a rival.
        self.child_mixers = []
        # A27: a SCRIPT child the game pushes after our own interaction.
        self.children = []
        self.finished_ns = None
        self.child_live_ns = None
        self.family_live_ns = None
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
        ours_running = self.card["card_class"] == "interaction" and any(
            entry.get("interaction_id") == self.interaction_id and
            entry.get("membership") in RUNNING_MEMBERSHIPS for entry in _entries(row))
        family_open = self._family_open(row, mono)
        # D5: once a need trial's family has run and left, new entries are the game's
        # aftermath (collect dish, wash dish, put away), not rivals of the meal.
        # Between crafting phases the family is briefly not live; family_open keeps
        # the A32 handoff grace so the next phase child is still ours.
        aftermath = (self.card.get("card_class") == "need" and self.claims["STARTED"] and
                     not family_open)
        for entry in _entries(row):
            if aftermath:
                iid = entry.get("interaction_id")
                if iid is not None:
                    self.known_ids.add(iid)
                continue
            iid = entry.get("interaction_id")
            if iid is not None and iid == self.interaction_id:
                ours = entry
                continue
            if iid is not None and iid in self.children:
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
            if autonomy_on_object and iid is not None and iid in self.child_mixers:
                if membership in RUNNING_MEMBERSHIPS:
                    self.child_mixers.remove(iid)
                    self.foreign_roots.append(iid)
                continue
            if (autonomy_on_object and iid is not None and ours_running and
                    iid not in self.known_ids and iid not in self.foreign_roots and
                    membership == "QUEUED"):
                self.child_mixers.append(iid)
                self.known_ids.add(iid)
                continue
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
            if (family_open and source in FAMILY_SOURCES and iid is not None and
                    iid not in self.known_ids and iid not in self.foreign_roots):
                self.children.append(iid)
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
        if self._child_running(row) and self.started_ns is None:
            self.started_ns = mono
            self.claims["STARTED"] = True
        if self.children:
            # D12: the push can finish before the first poll; its child proves it queued.
            self.claims["ENQUEUED"] = True
        if type(mono) is int and self._family_live(row):
            self.family_live_ns = mono
        if self.card["card_class"] != "posture":
            self._rows_since.append(row)
        effect_held, reason = e2_cards.evaluate_effect(self.card, {
            "interaction_id": self.interaction_id,
            "children": self.children,
            "foreign_roots": self.foreign_roots,
            "control_rows": self.control_rows,
            "pushed_mono_ns": self.pushed_mono_ns,
            "rows_since_push": self._rows_since,
            "started_ns": self.started_ns,
        }, row)
        if reason is not None and reason not in self.ambiguous:
            self.ambiguous.append(reason)
        if reason is not None:
            effect_held = False
        if effect_held:
            self.claims["EFFECT_OBSERVED"] = True
            if self.effect_since_ns is None:
                self.effect_since_ns = mono
        else:
            self.effect_since_ns = None
            if self.claims["ATTRIBUTED"] and not self.claims["MAINTAINED_10S"]:
                # Maintenance must be continuous from attribution; a later
                # re-seat is a new, unattributed effect.
                self.maintenance_broken = True
        if (effect_held and self.claims["STARTED"] and not self.claims["ATTRIBUTED"] and
                not self.foreign_roots and self.incomplete_rows == 0 and
                self.started_ns is not None and self.started_ns <= mono):
            self.claims["ATTRIBUTED"] = True
            self.attributed_ns = mono
        if (self.claims["ATTRIBUTED"] and effect_held and not self.foreign_roots and
                not self.maintenance_broken and
                self.effect_since_ns is not None and
                mono - max(self.effect_since_ns, self.attributed_ns) >=
                MAINTAIN_SECONDS * 1e9):
            self.claims["MAINTAINED_10S"] = True
        if mono - self.pushed_mono_ns >= self.window_seconds * 1e9:
            self.close()
        elif self._settled(mono):
            self.close()
        return [key for key in CLAIM_ORDER if self.claims[key] and not before[key]]

    def _family_live(self, row):
        for entry in _entries(row):
            iid = entry.get("interaction_id")
            if ((iid == self.interaction_id or iid in self.children) and
                    entry.get("membership") in OURS_LIVE):
                return True
        return False

    def _settled(self, mono):
        """D6: a need trial ends with its effect, not with the window. D26 (live
        sleep: she woke at row 1381, the verdict waited for the 180 s window at 1519):
        an interaction ends 30 s after its finished family was last live. D27 (live
        shower_Clean finished NATURAL 5 s after attribution and waited out the window):
        a finish settles it whether or not it reached MAINTAINED_10S; no claim can be
        earned once its family is gone."""
        if type(mono) is not int:
            return False
        if self.card.get("card_class") == "interaction":
            if not self.claims["FINISHED"]:
                return False
            last = self.family_live_ns
            if type(last) is not int or (type(self.finished_ns) is int and
                                         self.finished_ns > last):
                last = self.finished_ns
            if type(last) is not int:
                return False
            return mono - last >= NEED_SETTLE_SECONDS * 1e9
        if self.card.get("card_class") != "need":
            return False
        if self.claims["MAINTAINED_10S"]:
            return True
        if not self.claims["STARTED"]:
            return mono - self.pushed_mono_ns >= TRIAL_WINDOW_SECONDS * 1e9
        if type(self.family_live_ns) is not int:
            return False
        return mono - self.family_live_ns >= NEED_SETTLE_SECONDS * 1e9

    def finish(self, finishing_type, mono_ns=None):
        if self.finishing_type is None:
            self.finishing_type = finishing_type
            self.finished_ns = mono_ns
        self.claims["FINISHED"] = True

    def _family_open(self, row, mono):
        """A27: our push is live, or it finished naturally within the last 5 s."""
        kind = self.card.get("card_class")
        if kind != "interaction" and not (kind == "need" and self.food_route):
            return False
        for entry in _entries(row):
            if (entry.get("interaction_id") == self.interaction_id and
                    entry.get("membership") in OURS_LIVE):
                return True
        # A crafting chain hands off phase to phase (cook, then serve, then eat)
        # long after our own push ended: a live child keeps the family open too.
        for entry in _entries(row):
            if (entry.get("interaction_id") in self.children and
                    entry.get("membership") in OURS_LIVE):
                if type(mono) is int:
                    self.child_live_ns = mono
                return True
        if (type(self.child_live_ns) is int and type(mono) is int and
                0 <= mono - self.child_live_ns <= FAMILY_SECONDS * 1e9):
            return True
        if self.finishing_type != "FinishingType.NATURAL":
            return False
        if type(self.finished_ns) is not int or type(mono) is not int:
            return False
        return 0 <= mono - self.finished_ns <= FAMILY_SECONDS * 1e9

    def _child_running(self, row):
        for entry in _entries(row):
            if (entry.get("interaction_id") in self.children and
                    entry.get("membership") in RUNNING_MEMBERSHIPS):
                return True
        return False

    def close(self):
        if self.closed:
            return self.verdict
        self.closed = True
        interaction = self.card.get("card_class") == "interaction"
        natural = self.finishing_type == "FinishingType.NATURAL"
        user_cancel = self.finishing_type == "FinishingType.USER_CANCEL"
        interrupted = (interaction and self.finishing_type is not None and
                       not natural and not user_cancel)
        held = (self.claims["ATTRIBUTED"] and
                (self.claims["MAINTAINED_10S"] or (interaction and natural)) and
                not self.foreign_roots and not self.ambiguous)
        if interrupted and not self.claims["ATTRIBUTED"]:
            self.verdict = INTERRUPTED
        elif held:
            self.verdict = PASS
        else:
            self.verdict = OUTCOME_UNKNOWN
        return self.verdict


class CardLearner:
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
        for entry in _entries(row):
            iid = entry.get("interaction_id")
            if iid is not None and iid not in self._seen_first:
                self._seen_first[iid] = mono
        if row.get("observation_complete") is not True:
            posture = _posture(row)
            self._observe_continuation(
                row, open_harness_ids, posture.get("target_id"), mono, False)
            return None
        for entry in _entries(row):
            # AUTONOMY never teaches a signature and never marks an entry
            # exercised. There is no exercised set; only a pie-menu sit opens
            # a signature window.
            if entry.get("source_raw") == "InteractionSource.AUTONOMY":
                continue
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
        self._observe_continuation(row, open_harness_ids, target, mono, True)
        return learned

    def _close_continuation(self, object_id):
        learned = self.continuation.setdefault(object_id, set())
        detail = ",".join(sorted(learned))
        self.continuation_events.append((object_id, detail))
        self._cont_closed.add(object_id)
        self._cont_since.pop(object_id, None)

    def _observe_continuation(self, row, open_harness_ids, target, mono, complete):
        for object_id, m0 in list(self._cont_since.items()):
            if object_id in self._cont_closed:
                continue
            if mono - m0 > CONTINUATION_WINDOW_SECONDS * 1e9:
                self._close_continuation(object_id)
                continue
            seated_here = target == object_id
            for entry in _entries(row):
                self._consider_continuation_entry(
                    object_id, entry, open_harness_ids, m0,
                    complete and seated_here)
            if target != object_id and (complete or target is not None):
                self._close_continuation(object_id)

    def _consider_continuation_entry(self, object_id, entry, open_harness_ids, m0,
                                     allow_add):
        if entry.get("source_raw") != "InteractionSource.AUTONOMY":
            return
        if entry.get("target_id") != object_id:
            return
        iid = entry.get("interaction_id")
        if iid is None or iid in open_harness_ids:
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
        if not allow_add:
            return
        first = self._seen_first.get(iid)
        if first is None or first < m0:
            return
        if entry.get("membership") == "QUEUED" and aff not in excluded:
            learned.add(aff)

    def cards(self):
        """Posture cards for signatures learned from the Owner's own Sit."""
        found = []
        for object_id in sorted(self.signatures):
            found.append(e2_cards.posture_card(object_id, self.signatures[object_id]))
        return found


SignatureLearner = CardLearner
