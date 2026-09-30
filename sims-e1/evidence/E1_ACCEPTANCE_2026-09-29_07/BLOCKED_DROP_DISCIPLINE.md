# E1 Acceptance 2026-09-29_07 — BLOCKED

## Exact finite blocker

`DROP_DISCIPLINE = FAIL`.

The first session closed with a nonzero queue-loss counter:

- `dropped_queue=51`
- `dropped_overrun=0`
- `dropped_serialize=0`
- writer state: `OK`
- close reason: `DISARM_CLEAN`

The two rows carrying the nonzero counter were:

| sequence | event | dropped_queue | wall timestamp |
|---:|---|---:|---:|
| 389 | `session_checkpoint` | 51 | `1790667397763` |
| 390 | `session_close` | 51 | `1790667398423` |

The session contains no `clock_snapshot` or `zone_snapshot` rows. Therefore
the 51 queued losses cannot be qualified as clock-class-only loss. The
acceptance contract requires zero critical-class loss. This is a load-bearing
runtime blocker.

## Session identity

- telemetry session UUID: `e08c49af-f0d4-4cd0-86f6-cfc45bd84aa8`
- file: `C:\Users\Xharv\OneDrive\Belgeler\Electronic Arts\The Sims 4\AshleyE1Telemetry\ashley_e1_e08c49af-f0d4-4cd0-86f6-cfc45bd84aa8.jsonl`
- final file bytes: `791424`
- final file SHA256: `770B450728552FABF86E76B51C0513B1B5CE078642F29669793D3CCDD506E8A7`
- final row count: `391`
- final sequence: `390`
- event counts: `session_open=1`, `presence_snapshot=381`,
  `session_checkpoint=8`, `session_close=1`

## Witnesses completed before stop

- fresh 1.0.7 bootstrap: PASS
- complete first-poll identity: PASS
- first 60-second unpaused window: `59` callbacks
- Owner pause continuity: `71` callbacks, zero drops before closure
- repeated `start`: PASS; `redundant_starts=1`
- arm while SAMPLING rejection: PASS
- stop while SAMPLING: PASS
- redundant stop while ARMED: PASS
- disarm/session close: PASS before drop-discipline failure

## Boundary

- source changed: `NO`
- artifact rebuilt: `NO`
- invalid-arm and start-while-UNARMED witnesses: not run after blocker
- E1-A/B/G: `NO`
- E2: `NO`
- synthetic input: `NO`
- power action: `NO`
- Sims remained running; no shutdown, reboot, sleep, or hibernate was used.

Acceptance stopped immediately after preserving this evidence.
