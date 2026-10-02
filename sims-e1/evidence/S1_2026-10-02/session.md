# S1 live session: probe 2.2.1 on LAB_E1, 2026-10-02

Run by CommandCode (Muse) with the Owner at the game. First live session after C1.

## Checklist (roadmap Part 6 S1 / handoff §3)

1. Owner launched the game and loaded LAB_E1. MET — lineage `LOAD_OBSERVED`
   session `b19ac483-b8af-4506-bbec-1a4a64446c33`, slot 2, guid 2773024768.
2. `status()` shows probe 2.2.1 and `inbox_autostart = ZONE:manager`, with no
   `ashley_e1.inbox` console command typed. MET — Owner confirmed nothing was
   typed; first `status` reply (id `86cde00f…`) already showed
   `inbox_autostart: "ZONE:manager"` while UNARMED. D11 autostart live-verified
   (contrast D10 live check, where the C3b import-time start FAILED and the
   Owner had to type the console command).
3. `inbox_errors` is 0. MET — 0 in every `status` reply (UNARMED, ARMED, SAMPLING).
4. `lineage()` then telemetry tail. MET — lineage 11 rows total; telemetry
   session `ashley_e1_b19ac483-…jsonl`, schema 3, probe 2.2.1,
   build 1.128.90.1030, ~1 presence_snapshot/sec at NORMAL, unpaused,
   `observation_complete = True` throughout.
5. Live reads for DS1. PARTIAL (expected) — see below.
6. This file. MET.

## Session facts

- Armed LAB_E1 (`arm lab_e1` → OK) then `start` → OK; `status` SAMPLING,
  `lineage_class: CONTINUES_LAST_SAVE`, designated sim `118245043779534861`.
- Live snapshots: posture `bed_Sleep` on target `118245043789434027`, 3
  autonomy/POSTURE_GRAPH sleep interactions (sleep_Passive 96864, bed_sleep
  13094, generic_Bed_Sleep 151428), ticks advancing (~6140081 → ~6564757).
- Helper `verdicts` / `status.verdicts`: [] (no experiments run — correct).

## Owner panel vs probe (DS1 inputs)

Owner-reported panel while sim asleep in bed:
- Needs bars (screenshot in report message): Bladder low orange (~1/4),
  Fun low orange (~1/4), Hunger green ~3/5 with decay arrow, Social full red
  bar, Energy green ~3/5, Hygiene green ~4/5.
- Moodlets (4 visible): Asleep +10000; Desolate Sad +3; Has to pee
  Uncomfortable +1; Tense +1 (needs amusement).

Probe 2.2.1 exposes presence only (`observers.py`: queue/si_state iteration,
no motive or buff reads). So: panel shows 6 motive bars + 4 moodlets, probe
shows 0 of either. Confirmed need for DS1 sense fields. The six COMMUNITY
fallback GUIDs (bladder 16652, energy 16654, fun 16655, hunger 16656, hygiene
16657, social 16658) remain LAB-unverified against real `guid64`s — DS1 must
confirm name-match first, GUID fallback second.

## Owner decisions recorded

- Single checkout on `domus-next`, no worktrees; merge to `main` is Owner's
  call at stage completion.
- E0 deferred. Spending cap (OD6) deferred to DE7a.

## Next

DS1 senses, probe 2.3.0 (amends D13 per roadmap §DS1). Sampling left running;
Owner closes the game when done.
