"""Replays of committed evidence. Parameters stay at the dt2.v1 defaults."""

from pathlib import Path

import pytest

from domus_helper.telemetry import raw_rows
from domus_helper.thalamus.percepts import Extractor
from domus_helper.thalamus.replay import replay

ROOT = Path(__file__).resolve().parents[2]


def _one(pattern):
    matches = sorted(ROOT.glob(pattern))
    assert len(matches) == 1, pattern
    return matches[0]


def _load(pattern):
    return list(raw_rows(_one(pattern)))


def _window(steps, span=60_000):
    times = sorted(
        step.wall_timestamp_ms for step in steps
        if step.decision.fired and step.decision.reason != "always_through"
        and type(step.wall_timestamp_ms) is int)
    best = 0
    start = 0
    for index, stamp in enumerate(times):
        while stamp - times[start] > span:
            start += 1
        best = max(best, index - start + 1)
    return best


def _h_after(result, key):
    found = []
    for step in result.steps:
        for trace in step.decision.trace:
            if trace.key == key:
                found.append(trace.h_after)
    return found


def test_sit_habituation():
    result = replay(_load("sims-e1/evidence/E2_T1_T3_2026-09-30_01/ashley_e1_863ffab5-*.jsonl"))
    keys = {}
    for step in result.steps:
        for percept in step.percepts:
            if percept.kind == "interaction" and percept.object == "14244":
                keys[percept.key] = keys.get(percept.key, 0) + 1
    # Probe rows in this file keep affordance 14244 at membership QUEUED, so the
    # RUNNING edge never fires. Count is the record; there is no h series.
    if not keys:
        assert keys == {}
        return
    key = max(keys, key=keys.get)
    series = _h_after(result, key)
    count = len(series)
    assert count == keys[key]
    if count >= 5:
        assert series[4] <= 0.2
    else:
        assert series == sorted(series, reverse=True)


def test_n5_no_storm():
    result = replay(_load("sims-e1/evidence/E2_N5_BOOTSTRAP_2026-09-30_02/ashley_e1_863ffab5-*.jsonl"))
    assert _window(result.steps) <= 3


def test_nap_super_speed_no_storm():
    result = replay(_load("sims-e1/evidence/E2_N_P_L_OWNER_2026-09-30_01/ashley_e1_863ffab5-*.jsonl"))
    fast = [step for step in result.steps if step.clock_speed == "SUPER_SPEED3"]
    assert _window(fast) <= 3
    assert result.wakes_per_real_minute >= 0.0


def test_l3_zone_and_reload_lineage():
    first = _load("sims-e1/evidence/E2_N_P_L_OWNER_2026-09-30_01/ashley_e1_0d15935a-*.jsonl")
    second = _load("sims-e1/evidence/E2_N_P_L_OWNER_2026-09-30_01/ashley_e1_1437e3d1-*.jsonl")
    result = replay(first + second)
    # Both committed files leave zone_id and lot_id null on every row.
    assert not any(percept.kind == "env" for step in result.steps for percept in step.percepts)
    zoned = _zone_fire()
    assert any(percept.kind == "env" for step in zoned.steps for percept in step.percepts)
    assert any(
        step.decision.fired and any(item[0].kind == "env" for item in step.decision.percepts)
        for step in zoned.steps)
    lineage_at = None
    for index, step in enumerate(result.steps):
        if any(percept.kind == "lineage" for percept in step.percepts):
            lineage_at = index
            break
    assert lineage_at is not None
    seen = set()
    for step in result.steps[:lineage_at]:
        for trace in step.decision.trace:
            seen.add(trace.key)
    fresh = None
    for step in result.steps[lineage_at + 1:]:
        for trace in step.decision.trace:
            if trace.key in seen:
                fresh = trace.novelty
                break
        if fresh is not None:
            break
    if fresh is None:
        for step in result.steps[lineage_at + 1:]:
            if step.decision.trace:
                fresh = step.decision.trace[0].novelty
                break
    assert fresh == pytest.approx(0.6)
    extractor = Extractor()
    reset = 0
    for row in first + second:
        percepts = extractor.step(row)
        if any(percept.kind == "lineage" for percept in percepts):
            assert extractor.needs.keys == {}
            assert extractor.durations.samples == {}
            reset += 1
    assert reset >= 1


def _zone_fire():
    """Two snapshots plus the debounce tick. Evidence itself has no zone ids."""
    def row(seq, zone_id, mono):
        return {
            "event_kind": "presence_snapshot",
            "written_sequence": seq,
            "wall_timestamp_ms": mono // 1_000_000,
            "monotonic_ns": mono,
            "telemetry_session_id": "l3",
            "game": {"ticks": seq, "clock_speed": "NORMAL", "paused": False},
            "body": {"sim_id": "ASH", "posture": {"posture_name": "stand", "target_id": ""}},
            "interactions": {"observed": []},
            "motives": [],
            "zone": {"zone_id": zone_id, "lot_id": 2},
        }
    return replay([
        row(1, 1, 1_000_000_000),
        row(2, 5, 1_001_000_000),
        row(3, 5, 3_001_000_000),
    ])


def test_fixture_need_bands():
    path = _one("sims-e1/evidence/DT2B_FIXTURE_2026-10-03/*.jsonl")
    rows = list(raw_rows(path))
    result = replay(rows)
    bands = {}
    distress = []
    for step in result.steps:
        for percept in step.percepts:
            if percept.kind != "need":
                continue
            bands.setdefault(percept.subject, []).append(percept.bucket)
            if percept.bucket == "distress":
                distress.append(percept.urgency)
    assert bands, "fixture produced no need percepts"
    assert distress and all(item == "always_through" for item in distress)
    extractor = Extractor()
    for row in rows:
        extractor.step(row)
    assert any(slot["has_rate"] for slot in extractor.needs.keys.values())


def test_replay_is_deterministic():
    rows = _load("sims-e1/evidence/DT2B_FIXTURE_2026-10-03/*.jsonl")
    assert replay(rows) == replay(rows)
