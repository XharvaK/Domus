"""Caller-facing values. A Percept is a fact about the body or the world; nothing here judges it."""

from dataclasses import dataclass

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


def percept_to_dict(percept):
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
