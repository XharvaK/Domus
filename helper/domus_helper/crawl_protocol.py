"""Crawl-side protocol constants. The deny list is the probe's own (vendored e2_trial.py), so the helper never sends what the probe would refuse."""

from domus_helper.vendor import e2_trial

DENY_SUBSTRINGS = e2_trial.DENY_NAME_PARTS

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
