"""Crawl-side protocol constants. The deny list is the probe's own (vendored e2_trial.py), so the helper never sends what the probe would refuse."""

from domus_helper.vendor import e2_trial

# The probe's hard floor plus helper-only exclusions reviewed on the first real plan
# (2026-10-04): things that break objects, spend money or call NPCs, change lot rules,
# need another life stage, or take her off the lot. The probe never needs to know these.
HELPER_EXTRA_DENY = (
    "ghost", "possess", "bane", "sabotage", "hire", "replacebroken", "mailman",
    "displaybills", "door_", "utilities_", "deliverbaby", "callover", "telepathy",
    "toddler", "infant", "rabbithole",
)
DENY_SUBSTRINGS = e2_trial.DENY_NAME_PARTS + HELPER_EXTRA_DENY

RETRY_CODES = ("BODY_BUSY", "CLOCK_PAUSED")

OUTCOMES = ("PASS", "OUTCOME_UNKNOWN", "TRIAL_REJECT", "PUSH_FAILED", "TIMEOUT")


def name_blocked(name):
    """Deny-list and picker checks against the atlas tuning name."""
    if not isinstance(name, str) or not name:
        return True
    folded = name.casefold()
    if "picker" in folded:
        return True
    return any(part in folded for part in DENY_SUBSTRINGS)
