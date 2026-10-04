"""mirror of the probe's e2_trial.py (DA6A); the Architect replaces this with the vendored module at merge"""

DENY_SUBSTRINGS = (
    "debug", "cheat", "testing", "tutorial", "sell", "delete", "destroy",
    "demolish", "burn", "fire", "kill", "death", "grim", "woohoo", "trybaby",
    "try_for_baby", "propose", "breakup", "divorce", "adopt", "moveout",
    "move_out", "travel", "goto", "go_here", "leave", "career", "job", "quit",
    "retire", "buy", "purchase", "order", "call_", "phone_call", "invite",
    "ask_to", "social",
)

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
