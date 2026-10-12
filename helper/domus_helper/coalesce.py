"""H1 (D2): pending percepts and when they go out as one view. Pure: the caller supplies now_ms.

Every change the Extractor reports is kept here, one per key (the newest), at most the wire's 32. A view goes
when something is pending and either nothing new has come for QUIET_MS, the oldest pending change is OLDEST_MS
old, or a question the game opened for her is pending (at once). Her own setting of what wakes her is not here;
the body sends every change, and the mechanical waits above only keep the views from flooding her turns.
"""

from dataclasses import dataclass

from domus_helper.thalamus.types import percept_from_dict, percept_to_dict

QUIET_MS = 1_500
OLDEST_MS = 8_000
CAP = 32

QUESTION = "question"
QUIET = "quiet"
OLDEST = "oldest"
CHOICES = "choices"  # SEAM3-7: the game's choices came in (the first whole of a session, or a new act list): at once


@dataclass(frozen=True)
class Pending:
    """(percept, at_ms) in arrival order, one entry per key, at most CAP entries."""
    items: tuple = ()


def add(state, percepts, now_ms):
    items = list(state.items)
    for percept in percepts:
        items = [(kept, at) for kept, at in items if kept.key != percept.key]
        items.append((percept, now_ms))
    return Pending(tuple(items[-CAP:]))


def _asked(percept):
    return percept.kind == "env" and percept.bucket == "asked"


def due(state, now_ms, choices=False):
    """The reason a view goes now, or None. choices: the game's choices came in and have not gone out yet."""
    if choices:
        return CHOICES
    if not state.items:
        return None
    if any(_asked(percept) for percept, _ in state.items):
        return QUESTION
    if now_ms - max(at for _, at in state.items) >= QUIET_MS:
        return QUIET
    if now_ms - min(at for _, at in state.items) >= OLDEST_MS:
        return OLDEST
    return None


def take(state):
    """The pending percepts in arrival order, and the empty state."""
    return tuple(percept for percept, _ in state.items), Pending()


def to_list(state):
    return [[percept_to_dict(percept), at] for percept, at in state.items]


def from_list(blob):
    return Pending(tuple((percept_from_dict(item), int(at)) for item, at in blob or []))

