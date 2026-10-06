"""Caller-facing values. State objects are replaced, never updated in place."""

from dataclasses import dataclass, field

from domus_helper.thalamus.parameters import KINDS

_URGENCY = frozenset({"normal", "wake", "always_through"})
_PRESSURE = frozenset({None, "action_end"})


@dataclass(frozen=True)
class Percept:
    kind: str
    subject: str
    object: str
    bucket: str
    surprise: float = 0.0
    urgency: str = "normal"
    pressure: str | None = None
    lineage: str = ""
    undone: bool = False
    facts: tuple = ()

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"unknown kind {self.kind}")
        if self.urgency not in _URGENCY:
            raise ValueError(f"unknown urgency {self.urgency}")
        if self.pressure not in _PRESSURE:
            raise ValueError(f"unknown pressure {self.pressure}")
        if self.surprise < 0:
            raise ValueError("surprise must be >= 0")
        facts = tuple((key, value) for key, value in self.facts)
        for pair in facts:
            hash(pair)
        object.__setattr__(self, "facts", facts)

    @property
    def key(self):
        return f"{self.kind}:{self.subject}:{self.object}:{self.bucket}"


@dataclass(frozen=True)
class KeyState:
    h: float = 1.0
    last_ms: int | None = None

    def to_dict(self):
        return {"h": self.h, "last_ms": self.last_ms}

    @classmethod
    def from_dict(cls, blob):
        return cls(h=blob.get("h", 1.0), last_ms=blob.get("last_ms"))


def _percept_dict(percept):
    return {
        "kind": percept.kind,
        "subject": percept.subject,
        "object": percept.object,
        "bucket": percept.bucket,
        "surprise": percept.surprise,
        "urgency": percept.urgency,
        "pressure": percept.pressure,
        "lineage": percept.lineage,
        "undone": percept.undone,
        "facts": [list(pair) for pair in percept.facts],
    }


def percept_from_dict(blob):
    return Percept(
        blob["kind"], blob.get("subject", ""), blob.get("object", ""), blob.get("bucket", ""),
        surprise=blob.get("surprise", 0.0), urgency=blob.get("urgency", "normal"),
        pressure=blob.get("pressure"), lineage=blob.get("lineage", ""),
        undone=bool(blob.get("undone", False)),
        facts=tuple(tuple(pair) for pair in blob.get("facts") or ()),
    )


@dataclass(frozen=True)
class ThalamusState:
    last_now_ms: int | None = None
    arousal: float = 0.0
    keys: dict = field(default_factory=dict)
    novelty_counts: dict = field(default_factory=dict)
    pending: tuple = ()
    pending_deadline_ms: int | None = None
    pending_reason: str | None = None
    refractory_until_ms: int | None = None
    last_fire_ms: int | None = None
    idle_since_ms: int | None = None

    def to_dict(self):
        return {
            "last_now_ms": self.last_now_ms,
            "arousal": self.arousal,
            "keys": {key: slot.to_dict() for key, slot in self.keys.items()},
            "novelty_counts": [
                [key[0], key[1], count] for key, count in self.novelty_counts.items()
            ],
            "pending": [[_percept_dict(percept), salience] for percept, salience in self.pending],
            "pending_deadline_ms": self.pending_deadline_ms,
            "pending_reason": self.pending_reason,
            "refractory_until_ms": self.refractory_until_ms,
            "last_fire_ms": self.last_fire_ms,
            "idle_since_ms": self.idle_since_ms,
        }

    @classmethod
    def from_dict(cls, blob):
        keys = {key: KeyState.from_dict(slot) for key, slot in (blob.get("keys") or {}).items()}
        counts = {}
        for lineage, key, count in blob.get("novelty_counts") or []:
            counts[(lineage, key)] = count
        pending = tuple(
            (percept_from_dict(percept), salience) for percept, salience in blob.get("pending") or []
        )
        return cls(
            last_now_ms=blob.get("last_now_ms"),
            arousal=blob.get("arousal", 0.0),
            keys=keys,
            novelty_counts=counts,
            pending=pending,
            pending_deadline_ms=blob.get("pending_deadline_ms"),
            pending_reason=blob.get("pending_reason"),
            refractory_until_ms=blob.get("refractory_until_ms"),
            last_fire_ms=blob.get("last_fire_ms"),
            idle_since_ms=blob.get("idle_since_ms"),
        )


@dataclass(frozen=True)
class Trace:
    key: str
    raw: float
    h_before: float
    h_after: float
    salience: float
    novelty: float


@dataclass(frozen=True)
class Decision:
    fired: bool
    reason: str | None
    percepts: tuple
    arousal: float
    theta: float
    trace: tuple


@dataclass(frozen=True)
class Context:
    theta_scale: float = 1.0
    resting: bool = False
    # H0.5 decision points. None keeps the dt2.v1 threshold behaviour (replays, the scorer). True
    # or False: she is woken at decision points (wake percepts), drift and walk-bys fold into the
    # next wake, and while busy only a slow check looks in; while idle, boredom still does.
    busy: bool | None = None

    def __post_init__(self):
        if not 0.5 <= self.theta_scale <= 3.0:
            raise ValueError("theta_scale outside [0.5, 3.0]")
