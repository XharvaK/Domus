"""H0.5: she is woken at decision points (idle, a visitor, the game asking, a need band, a mood
change, a refused act); drift and walk-bys fold into the next wake; while busy only a slow
check looks in. Plans live in Ashley; between their steps her idle is held back."""

import json

from domus_helper.acts import ActCourier
from domus_helper.spool import Spool
from domus_helper.thalamus.core import decide
from domus_helper.thalamus.parameters import Parameters
from domus_helper.thalamus.percepts import Extractor
from domus_helper.thalamus.types import Context, Percept, ThalamusState

P = Parameters()
POSTURE = "InteractionSource.POSTURE_GRAPH"
STAND = "InteractionSource.BODY_CANCEL_AOP"
MINE = "InteractionSource.SCRIPT_WITH_USER_INTENT"


def _drift(i):
    return Percept("need", "fun", "", "ok", surprise=3.0, lineage="L", facts=(("i", str(i)),))


def _wake():
    return Percept("presence", "200", "", "on_lot", urgency="wake", lineage="L")


def _run(state, steps, context):
    fires = []
    for now, percepts in steps:
        state, decision = decide(state, percepts, now, P, context)
        if decision.fired:
            fires.append((now, decision.reason, [p.key for p, _ in decision.percepts]))
    return state, fires


def test_drift_alone_never_wakes_her_at_decision_points_but_does_in_dt2_v1():
    steps = [(i * 2_000, [_drift(i)]) for i in range(30)]
    _, legacy = _run(ThalamusState(), steps, Context())
    assert legacy, "dt2.v1 fires on arousal"
    _, points = _run(ThalamusState(), steps, Context(busy=True))
    assert points == []


def test_a_wake_fires_after_the_debounce_and_carries_the_drift_that_folded_in():
    steps = [(0, [_drift(0)]), (1_000, [_wake()]), (2_000, []), (3_000, [])]
    _, fires = _run(ThalamusState(), steps, Context(busy=True))
    assert len(fires) == 1
    at, reason, keys = fires[0]
    assert (at, reason) == (3_000, "wake")
    assert "need:fun::ok" in keys and "presence:200::on_lot" in keys


def test_a_wake_inside_the_refractory_period_waits_for_its_end():
    steps = [(0, [_wake()]), (2_000, []), (5_000, [Percept("env", "dialog", "9", "asked", urgency="wake")]),
             (10_000, []), (21_000, []), (23_000, [])]
    _, fires = _run(ThalamusState(), steps, Context(busy=False))
    assert [(at, reason) for at, reason, _ in fires] == [(2_000, "wake"), (23_000, "wake")]


def test_busy_gets_a_slow_check_with_a_percept_that_says_so():
    state, fires = _run(ThalamusState(), [(0, [_wake()]), (2_000, [])], Context(busy=True))
    assert len(fires) == 1
    _, fires = _run(state, [(2_000 + P.slow_check_ms - 1, []), (2_000 + P.slow_check_ms, []),
                            (2_000 + P.slow_check_ms + P.debounce_ms, [])], Context(busy=True))
    assert fires == [(2_000 + P.slow_check_ms + P.debounce_ms, "check", ["env:check:check:busy"])]


def test_idle_falls_back_to_boredom_not_the_slow_check():
    state, _ = _run(ThalamusState(), [(0, [_wake()]), (2_000, [])], Context(busy=False))
    _, fires = _run(state, [(2_000 + P.slow_check_ms + 10_000, []), (2_000 + P.slow_check_ms + 12_000, [])], Context(busy=False))
    assert fires == []
    _, fires = _run(state, [(2_000 + P.boredom_rise_ms, []), (2_000 + P.boredom_rise_ms + P.debounce_ms, [])], Context(busy=False))
    assert fires == [(2_000 + P.boredom_rise_ms + P.debounce_ms, "boredom", ["env:check:check:idle"])]


def _row(seq, observed=(), mood=None):
    row = {"event_kind": "presence_snapshot", "written_sequence": seq, "telemetry_session_id": "s",
           "wall_timestamp_ms": 1_000 + seq, "game": {"ticks": 100 * seq, "paused": False},
           "body": {"sim_id": "ASH", "posture": {"posture_name": "stand"}},
           "interactions": {"observed": list(observed)}, "motives": [], "zone": {"zone_id": 1, "lot_id": 9}}
    if mood is not None:
        row["mood"] = {"name": mood}
    return row


def _si(iid, source, membership="RUNNING"):
    return {"interaction_id": iid, "affordance_id": iid, "affordance_text": "x", "source_raw": source, "membership": membership}


def test_she_becomes_idle_when_only_her_posture_is_left_running():
    ext = Extractor()
    assert ext.busy is None
    ext.step(_row(1, [_si(1, POSTURE), _si(2, STAND)]))
    assert ext.busy is False
    ext.step(_row(2, [_si(1, POSTURE), _si(3, MINE, "QUEUED")]))
    assert ext.busy is True
    running = ext.step(_row(3, [_si(1, POSTURE), _si(3, MINE)]))
    assert [p for p in running if p.bucket == "idle"] == []
    done = ext.step(_row(4, [_si(1, POSTURE)]))
    assert [(p.kind, p.bucket, p.urgency) for p in done if p.bucket == "idle"] == [("interaction", "idle", "wake")]
    assert ext.busy is False
    again = ext.step(_row(5, [_si(1, POSTURE)]))
    assert [p for p in again if p.bucket == "idle"] == []
    # It survives a restart of the helper.
    assert Extractor.from_dict(json.loads(json.dumps(ext.to_dict()))).busy is False


def test_a_mood_change_wakes_her_once():
    ext = Extractor()
    assert [p for p in ext.step(_row(1, mood="Fine")) if p.kind == "moodlet"] == []
    changed = [p for p in ext.step(_row(2, mood="Happy")) if p.kind == "moodlet"]
    assert [(p.object, p.bucket, p.urgency) for p in changed] == [("Fine", "Happy", "wake")]
    assert [p for p in ext.step(_row(3, mood="Happy")) if p.kind == "moodlet"] == []


class _Sync:
    def __init__(self, planned):
        self.planned = planned

    def sync_acts(self, body):
        return {"status": "ok", "applied": 0, "acts": [], **({} if self.planned is None else {"planned": self.planned})}


def test_the_courier_remembers_how_many_plan_steps_ashley_still_holds(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    courier = ActCourier(spool, lambda command, args: None)
    assert courier.planned == 0
    courier.tick(_Sync(2), "h", 1_000, True)
    assert courier.planned == 2
    assert ActCourier(spool, lambda command, args: None).planned == 2
    courier.tick(_Sync(None), "h", 2_000, True)  # an Ashley without plans
    assert courier.planned == 0
    courier.tick(_Sync("x"), "h", 3_000, True)
    assert courier.planned == 0
