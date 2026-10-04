"""Pure trial admission and the push-failure storm latch.

No game imports and no I/O. DA6B vendors this module unchanged.
"""

from . import e2_admission
from . import e2_lineage

TRIAL_FORK_ONLY = "TRIAL_FORK_ONLY"
TRIAL_EXCLUDED = "TRIAL_EXCLUDED"
NEED_DISTRESS = "NEED_DISTRESS"
TRIAL_STORM = "TRIAL_STORM"
# Distress that cannot harm the body and that a lone lab Sim cannot relieve (DA6
# first crawl, 2026-10-04: social sat in distress for the whole LAB session).
# A motive without an id still counts, so an unreadable row stays conservative.
NON_BODILY_MOTIVES = ("social", "fun")
# Running entries that mean "standing or carrying, nothing chosen": the game keeps a
# BODY_CANCEL_AOP sim-stand RUNNING on an idle Sim after she wakes (first live crawl).
IDLE_RUNNING_SOURCES = ("InteractionSource.POSTURE_GRAPH",
                        "InteractionSource.BODY_CANCEL_AOP",
                        "InteractionSource.CARRY_CANCEL_AOP")

DENY_NAME_PARTS = (
    "debug", "cheat", "testing", "tutorial", "sell", "delete", "destroy",
    "demolish", "burn", "fire", "kill", "death", "grim", "woohoo", "trybaby",
    "try_for_baby", "propose", "breakup", "divorce", "adopt", "moveout",
    "move_out", "travel", "goto", "go_here", "leave", "career", "job", "quit",
    "retire", "buy", "purchase", "order", "call_", "phone_call", "invite",
    "ask_to", "social",
)

# D8 (live 2026-10-04): with energy in distress the guard refused bed and food too,
# and with autonomy off nothing could help her. A trial that relieves every
# distressed body motive is the cure, not a risk. Hunger is relieved by a food route.
RELIEF_NAME_PARTS = {
    "energy": ("sleep", "nap"),
    "bladder": ("toilet",),
    "hygiene": ("shower", "bath"),
}
LOW_BAND = ("low", "distress")

POSTURE_SOURCE = "InteractionSource.POSTURE_GRAPH"
RUNNING_MEMBERSHIPS = ("RUNNING", "QUEUED_AND_RUNNING")
STORM_LIMIT = 5


def trial_check(view):
    """Return None when a trial may be pushed, else one rejection code.

    `view` is the plain admission view plus `armed_name`, `object_id`,
    `excluded_ids`, `own_open_ids`, motive rows, and `object.excluded`.
    """
    if view.get("sampling") is not True:
        return e2_admission.NOT_SAMPLING
    lineage_class = view.get("lineage_class")
    if lineage_class in (None, e2_lineage.PENDING):
        return e2_admission.LINEAGE_PENDING
    if lineage_class == e2_lineage.BODY_MISMATCH:
        return e2_admission.BODY_MISMATCH
    if not e2_lineage.is_admissible(lineage_class):
        return e2_admission.LINEAGE_NOT_ADMISSIBLE
    designated = view.get("designated_sim_id")
    if designated is not None and designated != view.get("sim_id"):
        return e2_admission.BODY_MISMATCH
    if view.get("sim_id") is None or view.get("body_available") is not True:
        return e2_admission.BODY_UNAVAILABLE
    obj = view.get("object") or {}
    if obj.get("exists") is not True:
        return e2_admission.NO_OBJECT
    excluded_ids = view.get("excluded_ids") or ()
    if view.get("object_id") in excluded_ids:
        return e2_admission.OBJECT_EXCLUDED
    if view.get("armed_name") != "LAB_E1_FORK":
        return TRIAL_FORK_ONLY
    if obj.get("offer_count", 0) < 1:
        return e2_admission.AFFORDANCE_NOT_OFFERED
    if obj.get("excluded"):
        return TRIAL_EXCLUDED
    distressed = []
    for motive in view.get("motives") or ():
        if (isinstance(motive, dict) and motive.get("band") == "distress" and
                motive.get("id") not in NON_BODILY_MOTIVES):
            distressed.append(motive.get("id"))
    if distressed and not all(
            relieves(motive_id, view.get("tuning_name"), view.get("food_route"))
            for motive_id in distressed):
        return NEED_DISTRESS
    own = view.get("own_open_ids") or ()
    for entry in view.get("entries") or ():
        if entry.get("interaction_id") in own:
            return e2_admission.BODY_BUSY
        if entry.get("source_raw") in e2_admission.BUSY_SOURCES:
            return e2_admission.BODY_BUSY
        if (entry.get("membership") in RUNNING_MEMBERSHIPS and
                entry.get("source_raw") not in IDLE_RUNNING_SOURCES):
            return e2_admission.BODY_BUSY
    if view.get("paused") is not False:
        return e2_admission.CLOCK_PAUSED
    return None


def relieves(motive_id, tuning_name, food_route):
    """True when this affordance is the plain cure for one body motive."""
    if motive_id == "hunger":
        return food_route is not None
    parts = RELIEF_NAME_PARTS.get(motive_id)
    if not parts or type(tuning_name) is not str:
        return False
    low = tuning_name.lower()
    return any(part in low for part in parts)


def relief_motives(motives, tuning_name, food_route):
    """Low or distressed body motives this affordance relieves (D13)."""
    found = []
    for motive in motives or ():
        if (isinstance(motive, dict) and motive.get("band") in LOW_BAND and
                motive.get("id") not in NON_BODILY_MOTIVES and
                relieves(motive.get("id"), tuning_name, food_route)):
            found.append(motive.get("id"))
    return found


class StormCounter:
    """Five consecutive push failures latch until reset (the next arm)."""

    def __init__(self):
        self.failures = 0

    def latched(self):
        return self.failures >= STORM_LIMIT

    def fail(self):
        self.failures += 1

    def clear(self):
        self.failures = 0
