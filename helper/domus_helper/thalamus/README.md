# Peripheral thalamus (dt2.v1)

Ashley's central thalamus arbitrates across nuclei and the budget. This package decides which game percepts reach Ashley at all. It is a pure function of `(state, percepts, now_ms, params, context)`. The caller owns the clock. Probe parsing and the bridge are outside this package.

Central fixtures in `vectors/central/` are vendored byte for byte from Ashley. `vectors/central/README.md` says those fixtures do not require peripheral sensing to make the same decisions, and they are not a cross-language parity test. This package does not replay them through `decide`.

## Parameters

`PARAMETER_REVISION = "dt2.v1"`. Paper lines are from the organism map Part B, as cited in the DT2 fact map §1.

| Name | Default | Source |
|---|---|---|
| `theta0` | 1.0 | Contract value so raw `1` is the exact-threshold case. Numeric calibration against ≤ 1 wake per 3–5 real minutes is open (`:244`) and happens in DT2B replays. |
| `alpha_ambient` | 0.3 | `:245`, bounds [0.3, 0.8] |
| `alpha_social` | 0.1 | `:245`, bounds [0.0, 0.8] |
| `alpha_always_through` | 0.0 | T1 / always-through α is 0 (`:245`) |
| `recovery_tau_ms` | 600000 | 10 min real, fixed v1 (`:246`) |
| `arousal_tau_ms` | 60000 | 60 s real (`:243`) |
| `refractory_ms` | 20000 | 20 s real, fixed v1 (`:249`) |
| `debounce_ms` | 1500 | 1.5 s fixed (`:248`, `:211`) |
| `novelty_beta` | 0.6 | fixed v1 (`:247`); `n = β/√(1+count)` per lineage (`:201`) |
| `dishabituation_fraction` | 0.5 | Paper left the fraction open (`:191-195`). v1 uses half the lost `h`. |
| `arousal_reset_fraction` | 0.0 | Drop fraction open (`:207`). v1 matches the central default of 0. |
| `surprise_cap` | 3.0 | Caps `w_kind · z` at 1 before novelty and boosts (`:205-206`) |
| `wake_boost` | 0.5 | `wake` top-down term (`:205`). Amount is the v1 contract. |
| `action_end_boost` | 0.5 | `ACTION_END` pressure (`:215-217`). Amount is the v1 contract. |
| `boredom_rise_ms` | 900000 | Idle climbs 0→θ in ~15 real minutes (`:215-217`) |
| `resting_rise_multiplier` | 2.0 | "Slower after resting" (`:215`). v1 doubles the rise. |
| `w_kind` | 1.0 each | Kinds `:159-168`. Learning `wake_worth` is not in v1 (`:234-235`). |

Alpha: `urgency == always_through` uses `alpha_always_through` (including a social percept). Kind `social` otherwise uses `alpha_social`. Everything else uses `alpha_ambient`.

## Decision order

`now` is `max(now_ms, last_now_ms)` when `last_now_ms` is set, so a rollback cannot move time backward. `0` is a real timestamp. `dt` leaks arousal with `arousal_tau_ms`.

For each percept, in order: recover `h` unless the key has no `last_ms`; novelty is 0 when `undone`, and only a done percept increments `(lineage, key)`; `raw = w_kind[kind] · min(surprise, cap)/cap + novelty + wake boost + action-end boost`; `salience = h_before · raw` is added to arousal; then `h` habituates and is stamped at `now`. If `raw >= θ` or urgency is not `normal`, every other key is recovered to `now` and moved toward 1 by `dishabituation_fraction`. The percept joins the pending list.

After the batch:

1. Any `always_through` percept fires immediately and bypasses refractory and debounce. The notification is the pending list, which already includes this call.
2. Else a due `pending_deadline_ms` fires with the reason stored when the window opened (`threshold` or `boredom`).
3. Else, inside refractory (`now < refractory_until_ms`), nothing fires. Pending percepts stay.
4. Else an already-open window is left alone, so a later percept does not extend the 1.5 s.
5. Else `arousal >= θ` opens a threshold window at `now + debounce_ms`.
6. Else boredom pressure at or above `θ` opens a boredom window. Idle time starts at the first `now` seen (`idle_since_ms`) and restarts on each fire (`last_fire_ms`).

On fire: percepts are deduplicated by key (highest salience, first-seen order), arousal is multiplied by `arousal_reset_fraction`, refractory runs `refractory_ms`, and pending is cleared. Pending is capped at 32 by highest salience, ties by first-seen. An empty `decide` only leaks, then checks the deadline and boredom.

## Open

θ₀ against "≤ 1 wake per 3–5 real minutes" is a DT2B replay question. `w_kind` learning (`wake_worth`) is not in v1. The decision-log quota is DT2C.
