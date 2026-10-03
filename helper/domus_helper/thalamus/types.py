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

    def __post_init__(self):
        if not 0.5 <= self.theta_scale <= 3.0:
            raise ValueError("theta_scale outside [0.5, 3.0]")
