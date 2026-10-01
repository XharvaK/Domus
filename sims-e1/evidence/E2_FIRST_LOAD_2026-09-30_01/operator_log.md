2026-09-30T17:25:06.0607292+03:00 operator agent on the Owner's behalf: Steam screenshot capture denied twice; no in-game action.
2026-09-30T18:04:00.9187480+03:00 operator agent on the Owner's behalf: access approved; dismissed Mods dialog (ashley_e1_2.0.1 listed); opened Home; observed Version 1.128.90.1030 DX11. Owner launched game earlier.
## Command transcript (TRT; approximate entries reconstructed)
| Time | Command/action | Observed |
|---|---|---|
| before 18:11 interruption | ashley_e1.start UNARMED | submitted, no visible response; no session file |
| before 18:11 interruption | ashley_e1.arm badname | submitted, no visible response; not repeated |
| ~18:17:10 | ashley_e1.arm lab_e1 | empty session file created |
| ~18:17:40 | ashley_e1.start | first poll, session_open, expected triple, FOREIGN_OR_UNKNOWN |
| ~18:18 | ashley_e1.start | redundant_starts later 1; single session |
| ~18:18 | ashley_e1.arm lab_e1 while sampling | no second session; response not visible |
| after >=90s first poll | pause control | 45 pause rows; ticks 1629169 |
| after real 15s wait plus tool overhead | normal-speed control | ticks resumed; actual pause ~45s, exceeds ~15s instruction |
| 18:21:12.459 | ashley_e1.stop | zero presence until restart |
| 18:22:18.598 | ashley_e1.start | restart after >=20s; >=60s hands off |
| 18:24:25.264 | ashley_e1.stop | zero later presence |
| 18:24:54.862 | ashley_e1.disarm | DISARM_CLEAN at 18:24:58.828 |
| closeout | Exit Game then Exit Game, not Save and Exit | process absent afterward |

Every input above was operator agent on the Owner's behalf. Native autonomy moved Sim and camera; no operator-directed movement or object click. Seated fixture differs from job's initial-standing assumption; standing later observed naturally. Server-capacity interruption delayed checks. A final Enter was rejected on user-input detection; pending command reobserved before submission. Stale screenshotId error likewise reobserved before retry.

Save comparison: steam_autocloud.vdf LastWriteTime before 2026-09-29T14:49:02.5169704+03:00; after 2026-09-30T17:25:52.6634649+03:00. Both length 51, SHA256 3D3A5E9A1D3E79C91E971CE506B0FA88F0FF909B6F33DB67EA7ED4F4A8B5267D. Delta predates LAB load; causation not proven. No persisted content delta observed, but exact job comparison fails.

344 rows: session_open 1, lineage_event 2, presence_snapshot 332, checkpoint 8, close 1. Zero experiment/guard/exception rows. Raw capture and analysis.json retained. Ledger contains LOAD_OBSERVED, classification telemetry FOREIGN_OR_UNKNOWN. No repair or trial attempted after exact-comparison failure.
