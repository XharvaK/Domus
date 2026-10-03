"""Pure decide(). The caller supplies now_ms. No clock, no I/O."""

import math

from domus_helper.thalamus.parameters import validate
from domus_helper.thalamus.types import Decision, KeyState, ThalamusState, Trace

_PENDING_CAP = 32


def recover(h, dt_ms, tau_ms):
    if dt_ms <= 0:
        return h
    return h + (1.0 - h) * (1.0 - math.exp(-dt_ms / tau_ms))


def habituate(h, alpha):
    return h * (1.0 - alpha)


def leak(v, dt_ms, tau_ms):
    if dt_ms <= 0:
        return v
    return v * math.exp(-dt_ms / tau_ms)


def novelty(count, beta):
    return beta / math.sqrt(1.0 + count)


def theta(params, context):
    return params.theta0 * context.theta_scale


def boredom_pressure(idle_ms, params, context):
    rise = params.boredom_rise_ms
    if context.resting:
        rise *= params.resting_rise_multiplier
    return theta(params, context) * min(1.0, idle_ms / rise)


def alpha_for(percept, params):
    if percept.urgency == "always_through":
        return params.alpha_always_through
    if percept.kind == "social":
        return params.alpha_social
    return params.alpha_ambient


def _cap(pending):
    if len(pending) <= _PENDING_CAP:
        return tuple(pending)
    ranked = sorted(enumerate(pending), key=lambda item: (-item[1][1], item[0]))
    chosen = sorted(ranked[:_PENDING_CAP], key=lambda item: item[0])
    return tuple(item[1] for item in chosen)


def _dedup(pending):
    best = {}
    order = []
    for percept, salience in pending:
        key = percept.key
        if key not in best:
            order.append(key)
            best[key] = (percept, salience)
        elif salience > best[key][1]:
            best[key] = (percept, salience)
    return tuple(best[key] for key in order)


def decide(state, percepts, now_ms, params, context):
    validate(params)
    now = now_ms
    if state.last_now_ms is not None and state.last_now_ms > now:
        now = state.last_now_ms
    previous = now if state.last_now_ms is None else state.last_now_ms
    arousal = leak(state.arousal, now - previous, params.arousal_tau_ms)
    idle_since = now if state.idle_since_ms is None else state.idle_since_ms
    keys = dict(state.keys)
    counts = dict(state.novelty_counts)
    pending = list(state.pending)
    deadline = state.pending_deadline_ms
    pending_reason = state.pending_reason
    refractory_until = state.refractory_until_ms
    last_fire = state.last_fire_ms
    th = theta(params, context)
    traces = []

    for percept in percepts:
        ks = keys.get(percept.key, KeyState())
        if ks.last_ms is None:
            h_before = ks.h
        else:
            h_before = recover(ks.h, now - ks.last_ms, params.recovery_tau_ms)
        count_key = (percept.lineage, percept.key)
        if percept.undone:
            seen = 0.0
        else:
            seen = novelty(counts.get(count_key, 0), params.novelty_beta)
            counts[count_key] = counts.get(count_key, 0) + 1
        capped = percept.surprise if percept.surprise < params.surprise_cap else params.surprise_cap
        raw = params.w_kind[percept.kind] * capped / params.surprise_cap + seen
        if percept.urgency == "wake":
            raw += params.wake_boost
        if percept.pressure == "action_end":
            raw += params.action_end_boost
        salience = h_before * raw
        arousal += salience
        h_after = habituate(h_before, alpha_for(percept, params))
        keys[percept.key] = KeyState(h_after, now)
        if raw >= th or percept.urgency != "normal":
            for other, other_state in list(keys.items()):
                if other == percept.key:
                    continue
                if other_state.last_ms is None:
                    restored = other_state.h
                else:
                    restored = recover(
                        other_state.h, now - other_state.last_ms, params.recovery_tau_ms)
                restored = restored + (1.0 - restored) * params.dishabituation_fraction
                keys[other] = KeyState(restored, now)
        traces.append(Trace(percept.key, raw, h_before, h_after, salience, seen))
        pending.append((percept, salience))

    fired = False
    reason = None
    delivered = ()
    through = any(percept.urgency == "always_through" for percept in percepts)
    if through:
        fired = True
        reason = "always_through"
    elif deadline is not None and now >= deadline:
        fired = True
        reason = pending_reason
    elif refractory_until is not None and now < refractory_until:
        pass
    elif deadline is not None:
        pass
    elif arousal >= th:
        deadline = now + params.debounce_ms
        pending_reason = "threshold"
    else:
        origin = idle_since if last_fire is None else last_fire
        if boredom_pressure(now - origin, params, context) >= th:
            deadline = now + params.debounce_ms
            pending_reason = "boredom"

    if fired:
        delivered = _cap(_dedup(pending))
        arousal *= params.arousal_reset_fraction
        refractory_until = now + params.refractory_ms
        last_fire = now
        idle_since = now
        pending = []
        deadline = None
        pending_reason = None
    else:
        pending = list(_cap(pending))

    new_state = ThalamusState(
        last_now_ms=now,
        arousal=arousal,
        keys=keys,
        novelty_counts=counts,
        pending=tuple(pending),
        pending_deadline_ms=deadline,
        pending_reason=pending_reason,
        refractory_until_ms=refractory_until,
        last_fire_ms=last_fire,
        idle_since_ms=idle_since,
    )
    decision = Decision(fired, reason, delivered, arousal, th, tuple(traces))
    return new_state, decision
