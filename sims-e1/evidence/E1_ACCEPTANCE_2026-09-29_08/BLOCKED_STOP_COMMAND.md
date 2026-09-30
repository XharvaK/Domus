# E1 Acceptance 2026-09-29_08 — Blocked

## Exact finite blocker

`STOP_COMMAND_NO_EFFECT_AFTER_TWO_SUBMITTED_ATTEMPTS`

The Owner confirmed two exact submissions of:

```text
ashley_e1.stop
```

with the live gameplay window focused. Telemetry continued to append
`presence_snapshot` rows in `SAMPLING` after both submissions. No
`session_close` row was emitted because `disarm` was not entered after the
failed stop boundary.

No further Ashley command was entered. Sims was then fully quit normally.

## Candidate and artifact

- repository: `C:\Users\Xharv\Projects\Ashley`
- branch: `main`
- HEAD: `48a4d7421293553fbacc054541ded69b478df369`
- tree: `43eb0ffc11f62d27b7a2225dd2c8cbd4ed6bee70`
- origin/main: `48a4d7421293553fbacc054541ded69b478df369`
- product-facing release: `Embodiment 1.0.0`
- internal probe: `1.0.8`
- artifact: `ashley_e1_1.0.8.ts4script`
- artifact SHA256: `E0E1CB043EBC21EA12F0975BF8A8620FCD44BB65F502E210EA212FC673709240`
- source changed during acceptance: `NO`
- artifact rebuilt during acceptance: `NO`
- install/reinstall during acceptance: `NO`

## Bootstrap witness

- file: `ashley_e1_bootstrap_40127887-e082-497e-8d4e-63cc2dfe7932.jsonl`
- copied evidence file: `ashley_e1_bootstrap_40127887-e082-497e-8d4e-63cc2dfe7932.jsonl`
- bytes: `1019`
- SHA256: `D41DD111235AC6DD96EDF9A2D4CAA451E5A9BD24E6C562DE736EEE93C1BE1892`
- `probe_version`: `1.0.8`
- `sims_build`: `1.128.90.1030`
- embedded Python: `3.7.0`
- `perf_counter`: `true`
- `armed_name`: `UNARMED`
- exact required-import summary: `19/19 true`
- event: `load_disabled`

## Session witness

- telemetry session UUID: `0cfeefbe-6c57-4b21-a152-6acdc6aed25a`
- raw evidence file: `ashley_e1_0cfeefbe-6c57-4b21-a152-6acdc6aed25a.jsonl`
- bytes: `840186`
- SHA256: `C8282A64B3E969C85D95AE89B81703C8F894B9BEC418D46806EC855B5E5139D0`
- physical rows: `416`
- final `written_sequence`: `415`
- event counts: `session_open=1`, `presence_snapshot=406`, `session_checkpoint=9`
- `session_close`: absent
- first successful poll wall timestamp: `1790671187842`
- final wall timestamp: `1790671602234`
- sampling interval represented: `414.392` seconds
- paused samples: `8` (`clock=PAUSED`, stable ticks)
- first 60-second window: `59` presence callbacks over `59.372` seconds
- final counters: `dropped_queue=0`, `dropped_overrun=0`, `dropped_serialize=0`, `redundant_starts=0`
- final writer state: `OK`

The session therefore demonstrates successful bootstrap, arm, start,
complete first-poll identity, cadence, pause continuity, sustained buffered
sampling, and zero observed writer drops. It does not demonstrate the
required stop/disarm/close boundary because the canonical stop command had no
observable effect.

## Save comparison

The 12-file saves inventory retained the baseline sizes and timestamps.
Hashes for the ten non-active files matched the fresh baseline. The two
active `.save` files remained inaccessible to `Get-FileHash` after Sims quit;
their sizes and timestamps matched the baseline. No unexplained save change
was detected, but a complete post-close hash comparison for those two files
was not available.

## Boundary

- E1-A: `NOT STARTED`
- E1-B: `NOT STARTED`
- E1-G: `NOT STARTED`
- E2: `NOT STARTED`
- synthetic input: `NO`
- source repair in this run: `NO`
- power action: `NO`

## Verdict

`SIMS4_E1_FIRST_LOAD_ACCEPTANCE: BLOCKED`

Finite blocker: `STOP_COMMAND_NO_EFFECT_AFTER_TWO_SUBMITTED_ATTEMPTS`.

No same-session repair, rebuild, reinstall, or further Ashley command was
performed.
