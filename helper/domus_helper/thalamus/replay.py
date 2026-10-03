"""Replay committed telemetry through extraction and decide()."""

from dataclasses import dataclass

from domus_helper.thalamus.core import decide
from domus_helper.thalamus.percepts import Extractor
from domus_helper.thalamus.parameters import Parameters
from domus_helper.thalamus.types import Context, ThalamusState


@dataclass(frozen=True)
class StepRecord:
    written_sequence: int | None
    clock_speed: str | None
    wall_timestamp_ms: int | None
    percepts: tuple
    decision: object


@dataclass(frozen=True)
class ReplayResult:
    steps: tuple
    fires: tuple
    h: dict
    percept_counts: dict
    wakes_per_real_minute: float


def replay(rows, params=None, context=None, owner_sim_id=None):
    params = Parameters() if params is None else params
    context = Context() if context is None else context
    extractor = Extractor(owner_sim_id=owner_sim_id)
    state = ThalamusState()
    steps = []
    counts = {}
    first_wall = None
    last_wall = None
    for row in rows:
        percepts = tuple(extractor.step(row))
        for percept in percepts:
            counts[percept.kind] = counts.get(percept.kind, 0) + 1
        mono = row.get("monotonic_ns") or 0
        now_ms = int(mono) // 1_000_000
        state, decision = decide(state, percepts, now_ms, params, context)
        game = row.get("game") or {}
        wall = row.get("wall_timestamp_ms")
        speed = game.get("clock_speed")
        record = StepRecord(
            row.get("written_sequence"), speed if isinstance(speed, str) else None,
            wall if type(wall) is int else None, percepts, decision)
        steps.append(record)
        if type(wall) is int:
            if first_wall is None:
                first_wall = wall
            last_wall = wall
    fires = tuple(step for step in steps if step.decision.fired)
    wakes = sum(1 for step in fires if step.decision.reason != "always_through")
    if first_wall is not None and last_wall is not None and last_wall > first_wall:
        rate = wakes / ((last_wall - first_wall) / 60000.0)
    else:
        rate = 0.0
    habituation = {key: slot.h for key, slot in state.keys.items()}
    return ReplayResult(tuple(steps), fires, habituation, counts, rate)
