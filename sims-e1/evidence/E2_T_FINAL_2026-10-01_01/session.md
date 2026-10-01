# E2 T trials on probe 2.0.2 (2026-10-01, Owner-operated)

Probe 2.0.2: build `2B8550730465C390BD2438B9893F5027F58BDEAC8B7EA903484FE5A77ADFC415` at `4e69484`, installed by J108b (`26ac0c1`). Game build 1.128.90.1030. Save LAB_E1 (slot 2).
Recorded and adjudicated by the architect (Claude Opus) from the raw telemetry in this folder.

## Who acted

- **The Owner's own hand** throughout: the console commands, the control sit, Go Here between trials.
- The `sit` commands were pasted from the clipboard. An architect-run watcher (`token_watch.ps1`) copied `ashley_e2.sit <token>` when `PREPARE_OK` appeared in telemetry.
- Each sit itself is a **harness push** (origin EXPERIMENT) through `e2_actuator.py`. Every result below is from telemetry.

## Files

| File | What |
|---|---|
| `ashley_e1_0d534d87-57d7-47ac-bec7-d4ea92ef7658.jsonl` | the whole armed session: 1030 rows, closed `DISARM_CLEAN`, counters all 0 dropped, 0 incomplete presence rows |
| `ashley_e2_lineage_ledger.jsonl` | the ledger after the session |
| `saves_after.txt` | the save-folder inventory after the game exited (name, length, SHA-256) |

## Timeline

| Time | Event | Result |
|---|---|---|
| 01:03:36 | load LAB_E1, arm `lab_e1`, start | `LOAD_OBSERVED` slot 2 ticks 5331484 → `CLASSIFIED CONTINUES_LAST_SAVE` (ε = 0 against S1) |
| 01:04:13 | **N5 control**: the Owner's pie-menu Sit on chair `…055` | `SIGNATURE_LEARNED sit` |
| 01:04:44 | the continuation window closes | `CONTINUATION_LEARNED 14244` (sit_Passive), as A10 predicts |
| 01:07:57–01:09:00 | **T1**: prepare → sit (interaction 528) | seated 01:08:06, `ATTRIBUTED` 01:08:07; at 01:08:13 the game ends the sit (`INTERACTION_INCOMPATIBILITY`): the exhausted Sim autonomously goes to bed (AUTONOMY 13094 on bed `…027`, another object). **`OUTCOME_UNKNOWN`**, `foreign_roots=0 incomplete_rows=0 continuation=0`; seated 7 s < 10 s |
| 01:11:39, 01:11:44 | two prepares, no sit submitted (console input didn't reach the game) | tokens expired unused; no trial |
| 01:12:54–01:14:00 | **T2** (interaction 1007) | ENQUEUED 01:13:00, seated 01:13:01, `ATTRIBUTED` 01:13:02, `MAINTAINED_10S` 01:13:12. **`PASS`**, `foreign_roots=0 incomplete_rows=0 continuation=9` |
| 01:15:35 | T2's token pasted again | `ADMIT_REJECT REPLAY_REJECTED` (an unplanned live N4-type check: correct) |
| 01:16:47–01:17:50 | **T3** (interaction 1306) | seated 01:16:51, `ATTRIBUTED` 01:16:52, `MAINTAINED_10S` 01:17:02. **`PASS`**, `continuation=9` |
| 01:18:29–01:19:32 | **T4** (interaction 1502) | `ATTRIBUTED` 01:18:37, `MAINTAINED_10S` 01:18:47. **`PASS`**, `continuation=8` |
| ~01:21 | stop, disarm, quit without saving | `session_close DISARM_CLEAN` |

Each `FINISHED_CALLBACK` (`INTERACTION_INCOMPATIBILITY`) after a PASS is the Owner's Go Here ending the sit after the verdict window, as the protocol specifies.

## Summary

```
T1=OUTCOME_UNKNOWN (recorded foreign cause: need-driven autonomous sleep on another object)
T2=PASS  T3=PASS  T4=PASS
ATTRIBUTED_AND_MAINTAINED_COUNT=3/4
FALSE_ATTRIBUTION=none (every ATTRIBUTED had foreign_roots=0; the continuation entries were all sit_Passive 14244, QUEUED, while seated on the chair)
PUSH_SOURCE_LABEL=InteractionSource.SCRIPT_WITH_USER_INTENT
SAVES=identical to the post-install inventory (E2_INSTALL_2_0_2_2026-09-30/saves_after.txt): 17 files, 0 differences
```

## Findings

1. **A10 works live.** The game's seated-idle requests (14244) appeared 8–9 times per PASS trial. They were recorded as continuation, not treated as competing causes. Under 2.0.1 the same entries made T1 (ae7b80d) `OUTCOME_UNKNOWN`.
2. **Need-driven autonomy still overrides autonomy-off** (tonight: energy → sleep). The probe reported it honestly as `OUTCOME_UNKNOWN`, never as a false PASS.
3. **The console path is fragile for humans:** two prepares without a submitted sit, and one replay. The Domus plan Phase 2 (command inbox, `sit_trial`) removes the round-trip.
