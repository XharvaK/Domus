# Peripheral thalamus (dt2.v2)

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
| `DECISION_LOG_QUOTA_BYTES` | 52428800 | Owner-adjustable retention for `data_dir/thalamus/decisions-*.jsonl`. Not a `decide` input. |

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

## Decision points (dt2.v2, H0.5, 2026-10-06)

`Context.busy` switches the mode. `None` (replays, the scorer, the dt2.v1 vectors) keeps the order above exactly. The live bridge passes `True` or `False` from `Extractor.busy`: her body is busy when anything runs or waits in her queue other than what holds her in place (`POSTURE_GRAPH`, the `BODY_CANCEL_AOP` stand).

In this mode, after steps 1–2, a `wake` percept opens a window at `max(now + debounce_ms, refractory_until_ms)` (reason `wake`); nothing else does. Drift, walk-bys and posture fold into the next window. While busy, `slow_check_ms` (180 s) after the last fire opens a `check` window; while idle, boredom does as before. A `check` or `boredom` fire adds the percept `env:check:check:busy|idle`, so it always says what it is.

New wake percepts: `interaction::idle` when she goes from busy to idle (an act ended and nothing follows), and `moodlet:mood:<from>:<to>` when her mood changes. Her plans live in Ashley (`domusAct.then`); while Ashley still holds a plan step (`planned` in the act sync answer), the bridge turns her `idle` into an ordinary percept, because Ashley sends the next step in the same round trip.

Replay of three 2026-10-06 sessions (11–14 min each): 25→14, 11→7, 28→15 fires.

## Open

θ₀ against "≤ 1 wake per 3–5 real minutes" is still open after the DT2B replays below. Defaults were not changed. `w_kind` learning (`wake_worth`) is not in v1. `DECISION_LOG_QUOTA_BYTES` is the Owner-adjustable decision-log cap (50 MiB).

## Extraction

`Extractor.step` reads one row. `telemetry.raw_rows` replays old evidence without schema checks. `file_rows` still validates. Her body is `body.sim_id`. Activity for a need rate is the sorted tuple of RUNNING `affordance_id`s on the previous snapshot (`()` when idle). A lineage id is `slot_id:guid` and is stamped on later percepts. Gap and lineage reset both forward models.

| Percept | When | Bucket | Urgency |
|---|---|---|---|
| `gap` | `written_sequence` jumps by more than 1 in the session, or `session_open` after any row | `gap` | `wake` |
| `lineage` | `lineage_event` (`subject` slot, `object` guid) | `lineage_class` | `wake` |
| `need` | Her motive band changes. Otherwise only when the need model's `z >= 2` | new band | ok→low `wake`; any→distress `always_through`; recovery `normal`; surprise `normal` |
| `interaction` | RUNNING membership gained, or a RUNNING entry gone | `started` / `ended` | `normal`. `ended` sets `pressure=action_end` for `SCRIPT_WITH_USER_INTENT`, and `surprise=3` for `BODY_CANCEL_AOP` |
| `posture` | `posture_name` differs from the previous snapshot | new name | `normal` |
| `env` | `zone_id` or `lot_id` changes, both sides non-null or null→value | `lot_id` | `wake` |
| `presence` | Only if the row has `presence`. A sim id appears or disappears | `arrived` / `left` | `normal` |
| `social` | Only if the row has `social`. An entry whose `target_id` is her body | `addressed` | `always_through` when `source_sim == owner_sim_id` |

Facts are at most `ticks`, need `value`/`band`, and interaction `affordance_text` cut to 120 characters. `NeedModel` learns `rate` and `sigma` with gain 0.2 on consecutive unpaused pairs (`z = 0` until a rate exists). `DurationModel` keeps 50 unambiguous completed durations; surprise is 0 with fewer than 3 samples, else 3 when the duration is outside `[p25/2, p75×2]` (nearest rank, same helper as calibration).

## Replay (dt2.v1 defaults, 2026-10-03)

| Run | Result |
|---|---|
| Sit `E2_T1_T3` `863ffab5` | Affordance `14244` is QUEUED on 419 rows and RUNNING on 0. No interaction percept, so no `h` series. |
| N5 `E2_N5_BOOTSTRAP_02` `863ffab5` | Max 2 non-`always_through` fires in any 60 s wall window (6 such fires). `wakes_per_real_minute` 0.520. Counts: interaction 27, lineage 5, posture 5. |
| Nap `E2_N_P_L_OWNER` `863ffab5` | During `SUPER_SPEED3`, max 1 fire per 60 s (3 fires). Whole file max 3 per 60 s. `wakes_per_real_minute` 0.425 (above the 0.20–0.33 target). Counts: interaction 199, lineage 7, posture 36. |
| L3 `0d15935a` then `1437e3d1` | Every `zone_id` and `lot_id` is null, so no `env` percept. Six `lineage` percepts; each resets the models. A key seen before a lineage boundary has novelty 0.6 on its next sighting. Counts: interaction 3, lineage 6, gap 1. |
| Fixture `DT2B_FIXTURE` | Need band changes, distress as `always_through`. Rates learned for every motive. Raw bands: bladder ok→low; energy distress→low→ok; fun low; hunger low→distress; hygiene distress; social distress. Counts: gap 1, interaction 8, lineage 2, need 6, posture 2. |
| Determinism | Two replays of the fixture match. |
