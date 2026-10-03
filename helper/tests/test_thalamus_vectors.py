"""Golden vectors. Expected floats are closed forms (abs < 1e-9).

sit-habituation: dt 6500, tau 600000, alpha 0.3.
  h starts at 1. Each rep recovers (first rep has no last_ms) then h *= 0.7.
  h after rep 5 = 0.17982859325409065 <= 0.2.
recovery-10min: h_before = 0.7 + 0.3*(1-e^-1), then h *= 0.7.
dishabituation: 0.7*0.7 = 0.49; wake restores 0.49 + 0.51*0.5.
exact-threshold: surprise 3 / cap 3 = 1 with undone novelty 0. Equality opens
  the window; the empty call at +1500 fires, then arousal *= 0.
below-threshold: 2.997/3 = 0.999, no deadline.
debounce-coalesce: deadline stays at 1500 when a second percept arrives at 1000.
refractory: fire at 1500 holds until 21500. The wake at 11500 (raw 1.5) is kept.
  At 21501, V = 1.5*exp(-10001/60000) >= 1, so the window opens and fires at 23001.
always-through: alpha 0, so h stays 1, and the call fires inside refractory.
clock-rollback: max(9000, 10000) = 10000.
novelty: 0.6, then 0.6/sqrt(2), lineage M is 0.6 again, undone is 0,
  next L count is still 2 so 0.6/sqrt(3). Five ambient hits with dt 0: h = 0.7**5.
boredom: pressure = theta at idle 900000; resting rise is 1800000.
pending-cap: equal salience, first-seen order, keep 32 of 40.
"""

import hashlib
import json
from pathlib import Path

import pytest

from domus_helper.thalamus.core import decide
from domus_helper.thalamus.parameters import PARAMETER_REVISION, Parameters
from domus_helper.thalamus.types import Context, Percept, ThalamusState

ROOT = Path(__file__).resolve().parents[1] / "domus_helper" / "thalamus" / "vectors"
CENTRAL = (
    "habituation-recovery.json",
    "dishabituation.json",
    "exact-threshold.json",
    "refractory.json",
    "clock-rollback.json",
    "duplicate-out-of-order.json",
    "coalescing.json",
    "README.md",
)


def _percept(raw):
    fields = dict(raw)
    facts = tuple(tuple(pair) for pair in fields.pop("facts", []) or [])
    fields["pressure"] = fields.get("pressure")
    return Percept(facts=facts, **fields)


def _close(got, want):
    assert abs(got - want) < 1e-9, (got, want)


def _play(doc):
    params = Parameters(**doc["params"])
    context = Context(**doc["context"])
    state = ThalamusState()
    for step in doc["steps"]:
        if step.get("reset"):
            state = ThalamusState()
        if "context" in step:
            context = Context(**step["context"])
        state, decision = decide(
            state, [_percept(raw) for raw in step["percepts"]],
            step["nowMs"], params, context)
        expect = step["expect"]
        assert decision.fired is expect["fired"]
        assert decision.reason == expect["reason"]
        if "arousal" in expect:
            _close(decision.arousal, expect["arousal"])
        if "percepts" in expect:
            assert [percept.key for percept, _ in decision.percepts] == expect["percepts"]
        if "keys" in expect:
            for key, body in expect["keys"].items():
                _close(state.keys[key].h, body["h"])
        if "lastNowMs" in expect:
            assert state.last_now_ms == expect["lastNowMs"]
        if "pendingDeadlineMs" in expect:
            assert state.pending_deadline_ms == expect["pendingDeadlineMs"]
        if "novelty" in expect:
            assert [trace.novelty for trace in decision.trace] == pytest.approx(
                expect["novelty"], abs=1e-9)
        if "hBefore" in expect:
            assert [trace.h_before for trace in decision.trace] == pytest.approx(
                expect["hBefore"], abs=1e-9)
    return state


def test_peripheral_vectors_and_manifest():
    manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
    files = sorted(path.name for path in ROOT.glob("*.json") if path.name != "MANIFEST.json")
    assert sorted(manifest) == files
    for name in files:
        blob = (ROOT / name).read_bytes()
        assert hashlib.sha256(blob).hexdigest() == manifest[name]
        doc = json.loads(blob)
        assert doc["schemaVersion"] == 1
        assert doc["parameterRevision"] == PARAMETER_REVISION
        _play(doc)
    sit = json.loads((ROOT / "sit-habituation.json").read_text(encoding="utf-8"))
    final = sit["steps"][-1]["expect"]["keys"]["interaction:sim:14244:running"]["h"]
    assert final == 0.17982859325409065
    assert final <= 0.2


def test_central_manifest_and_schema():
    folder = ROOT / "central"
    manifest = json.loads((folder / "MANIFEST.json").read_text(encoding="utf-8"))
    assert sorted(manifest) == sorted(CENTRAL)
    for name, digest in manifest.items():
        blob = (folder / name).read_bytes()
        assert hashlib.sha256(blob).hexdigest() == digest
        if name.endswith(".json"):
            assert json.loads(blob)["schemaVersion"] == 1


def test_central_bytes_match_sibling_checkout():
    # helper/tests/<file> -> parents[2] is the worktree; sibling repo is ../Ashley.
    ashley = Path(__file__).resolve().parents[2] / ".." / "Ashley"
    source = ashley / "apps" / "agent-service" / "src" / "core" / "cognitive-v021" / "thalamus" / "vectors"
    if not source.is_dir():
        pytest.skip("sibling Ashley checkout is not present")
    folder = ROOT / "central"
    for name in CENTRAL:
        assert (folder / name).read_bytes() == (source / name).read_bytes()
