"""Crawl-side protocol constants. The crawl's deny list is its own floor (CRAWL_FLOOR_PARTS and HELPER_EXTRA_DENY):
the crawl is the helper's unsupervised sweep, not her life, so it does not take the probe's 2.37.1 narrowing."""

# 2.37.1: the probe keeps only testers', cheat and trip acts out by name now (her life is hers to choose). The
# crawl keeps the list the probe had before 2.37.1 (kept here as a literal, not read from the vendored module),
# so the sweep never sends sell, delete, kill, fire, careers, money, love, family, moving or calls by itself.
CRAWL_FLOOR_PARTS = (
    "debug", "cheat", "testing", "tutorial", "sell", "delete", "destroy",
    "demolish", "burn", "fire", "kill", "death", "grim", "woohoo", "woo_hoo",
    "trybaby", "try_baby", "try_for_baby", "propose", "breakup", "break_up", "divorce",
    "adopt", "adoption", "moveout", "move_out", "travel", "goto", "go_to", "go_here",
    "leave", "career", "careers", "job", "jobs", "quit", "retire", "buy", "purchase", "order",
    "call", "phone_call", "invite", "ask_to", "social", "socialize",
)

# The probe's hard floor plus helper-only exclusions reviewed on the first real plan
# (2026-10-04): things that break objects, spend money or call NPCs, change lot rules,
# need another life stage, or take her off the lot. The probe never needs to know these.
HELPER_EXTRA_DENY = (
    "ghost", "possess", "bane", "sabotage", "hire", "replacebroken", "mailman",
    "displaybills", "door_", "utilities_", "deliverbaby", "callover", "telepathy",
    "toddler", "infant", "rabbithole",
)
DENY_SUBSTRINGS = CRAWL_FLOOR_PARTS + HELPER_EXTRA_DENY

RETRY_CODES = ("BODY_BUSY", "CLOCK_PAUSED")

OUTCOMES = ("PASS", "OUTCOME_UNKNOWN", "TRIAL_REJECT", "PUSH_FAILED", "TIMEOUT",
           "INTERRUPTED", "STALE_TARGET", "NEVER_STARTED", "PUSH_REFUSED")
# Chained resume and completed-display affordances are not trials (DA6C).
PROTOCOL_SKIP = ("_Resume", "CompletedDisplay")


def name_blocked(name):
    """Deny-list and picker checks against the atlas tuning name."""
    if not isinstance(name, str) or not name:
        return True
    folded = name.casefold()
    if "picker" in folded:
        return True
    return any(part in folded for part in DENY_SUBSTRINGS)
