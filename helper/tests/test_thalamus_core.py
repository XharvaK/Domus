"""Pure peripheral thalamus. Numbers below are closed-form, not core dumps."""

import math

import pytest

from domus_helper.thalamus.core import (
    alpha_for, boredom_pressure, decide, habituate, leak, novelty, recover, theta,
)
from domus_helper.thalamus.parameters import (
    PARAMETER_REVISION, Parameters, bounds, validate,
)
from domus_helper.thalamus.types import (
    Context, KeyState, Percept, ThalamusState,
)


def test_closed_forms():
    # recover: h + (1-h)*(1-e^(-dt/tau)); dt <= 0 leaves h.
    assert recover(0.7, 0, 600_000) == 0.7
    assert recover(0.7, -5, 600_000) == 0.7
    assert recover(0.7, 600_000, 600_000) == pytest.approx(
        0.7 + 0.3 * (1 - math.exp(-1)))
    assert habituate(1.0, 0.3) == pytest.approx(0.7)
    assert leak(1.0, 0, 60_000) == 1.0
    assert leak(1.0, -1, 60_000) == 1.0
    assert leak(1.0, 60_000, 60_000) == pytest.approx(math.exp(-1))
    # n = beta/sqrt(1+count)
    assert novelty(0, 0.6) == pytest.approx(0.6)
    assert novelty(1, 0.6) == pytest.approx(0.6 / math.sqrt(2))
    p = Parameters()
    assert theta(p, Context()) == 1.0
    assert theta(p, Context(theta_scale=2.0)) == 2.0
    # rise 900_000; pressure = theta * min(1, idle/rise); resting doubles rise.
    assert boredom_pressure(900_000, p, Context()) == pytest.approx(1.0)
    assert boredom_pressure(450_000, p, Context()) == pytest.approx(0.5)
    assert boredom_pressure(900_000, p, Context(resting=True)) == pytest.approx(0.5)
    assert boredom_pressure(1_800_000, p, Context(resting=True)) == pytest.approx(1.0)


def test_parameter_and_percept_validation():
    assert PARAMETER_REVISION == "dt2.v1"
    validate(Parameters())
    assert bounds["alpha_always_through"] == (0.0, 0.0)
    assert bounds["recovery_tau_ms"] == (600_000, 600_000)
    with pytest.raises(ValueError):
        validate(Parameters(alpha_ambient=0.29))
    with pytest.raises(ValueError):
        validate(Parameters(theta0=3.1))
    with pytest.raises(ValueError):
        validate(Parameters(w_kind={"need": 1.0}))
    with pytest.raises(ValueError):
        validate(Parameters(w_kind={k: 1.0 for k in bounds if False} | {
            "need": 0.1, "interaction": 1, "posture": 1, "presence": 1,
            "social": 1, "moodlet": 1, "env": 1, "lineage": 1, "gap": 1}))
    with pytest.raises(ValueError):
        Percept("nope", "s", "o", "b")
    with pytest.raises(ValueError):
        Percept("need", "s", "o", "b", urgency="soon")
    with pytest.raises(ValueError):
        Percept("need", "s", "o", "b", pressure="start")
    with pytest.raises(ValueError):
        Percept("need", "s", "o", "b", surprise=-0.1)
    with pytest.raises(ValueError):
        Context(theta_scale=0.49)
    p = Percept("interaction", "sim", "14244", "running", facts=(("phase", "running"),))
    assert p.key == "interaction:sim:14244:running"
    assert alpha_for(p, Parameters()) == 0.3
    social = Percept("social", "a", "b", "c", urgency="always_through")
    assert alpha_for(social, Parameters()) == 0.0
    assert alpha_for(Percept("social", "a", "b", "c"), Parameters()) == 0.1


def test_decide_does_not_mutate_input_and_empty_call_leaks():
    # Deadline due at t=1000. Leak first: V' = 1*e^(-1000/60000), then fire resets V.
    held = KeyState(0.4, 0)
    counts = {("L", "need:s:o:b"): 2}
    pending = (Percept("need", "s", "o", "b", surprise=3.0, undone=True), 1.0)
    state = ThalamusState(
        last_now_ms=0, arousal=1.0, keys={"need:s:o:b": held},
        novelty_counts=counts, pending=(pending,),
        pending_deadline_ms=1000, pending_reason="threshold", idle_since_ms=0)
    new, decision = decide(state, [], 1000, Parameters(), Context())
    assert state.arousal == 1.0
    assert state.keys["need:s:o:b"] is held and held.h == 0.4
    assert state.novelty_counts == counts
    assert state.pending[0][0].subject == "s"
    assert state.last_now_ms == 0
    assert decision.fired is True
    assert decision.reason == "threshold"
    assert decision.arousal == 0.0
    assert decision.percepts[0][0].key == "need:s:o:b"
    assert new.pending == ()
    assert new.refractory_until_ms == 1000 + 20_000
    assert new.idle_since_ms == 1000
    assert new.last_now_ms == 1000
    # A later empty call only leaks (reset fraction 0 leaves arousal 0) and does not fire.
    later, quiet = decide(new, [], 1000 + 20_000, Parameters(), Context())
    assert quiet.fired is False
    assert quiet.reason is None
    assert quiet.trace == ()
    assert later.arousal == 0.0
