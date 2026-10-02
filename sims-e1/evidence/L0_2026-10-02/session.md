# LAB L0 live session: probe 2.3.0 on LAB_E1, 2026-10-02

Run by CommandCode (Muse) with the Owner at the game. First live session of
2.3.0 senses + DS2 detected-build gate.

## Checklist (roadmap Part 6 L0 / R_F3 §"L0")

Common reads first, then steps. Steps needing Owner hands are marked OWNER.

1. OWNER: prepared LAB save open, read-only instrumentation authorized
   (2.3.0 already installed). MET — Owner in LAB_E1, sampling started by agent.
2. Loaded class/offered scan (≤20). NOT RUN — no `atlas_dump`/`offered_scan`
   probe command exists yet (Phase 5 work). Marked unavailable per the
   session rule; no tool invented.
3. Needs/mood/buff reads. PARTIAL — moodlets + mood live (below); motives
   empty (live root cause found, probe fix pending, needs 2.3.1 install).
   Career/scheduler/wants reads: no delegated adapter exists yet — marked
   unavailable (L0 step 4 scope, not this session).
4. Wants/scheduler reads. NOT RUN — no adapter (see step 3).
5. 60× 1 s repeat + purity audit. PARTIAL — ~28 min continuous sampling
   (1665 snapshots, zero drops) instead of a 60 s burst; statistic-count
   comparison not available (no count reader exists). Purity holds by
   construction: the poll path uses getters/iteration only (DS1 tripwire).
6. OWNER toggles (Wants/Fears UI, save/reload, CAS). NOT RUN — Owner time
   not spent on toggles this session; CAS/reload cycles deferred.
7. DS2 live confirmation. MET — detected `1.128.90.1030` (EXE +
   `Default.ini` agree), declared `1.128.90.1030` (schema `SIMS_BUILD`),
   no mismatch, actuation stayed enabled. Fingerprint snapshot in DS2
   report. Two DS2 bugs fixed from this session's data (EXE string table,
   UTF-16 `GameVersion.txt`).
8. OWNER second scene (larger S/N) + cost report. PARTIAL — single scene
   (solo sim); snapshot bytes measured: min 3468, p50 ~4130, p95/max 4442
   (well under the 8 KiB budget). No second scene prepared.

## Session facts

- Armed LAB_E1 (`arm lab_e1` → OK) then `start` → OK; `status` SAMPLING,
  lineage `CONTINUES_LAST_SAVE`, designated sim `118245043779534861`,
  slot 2, guid 2773024768 (same body/save as S1).
- Telemetry session `ashley_e1_97129da5-…jsonl`: 1665 presence_snapshot,
  1 session_open, 2 lineage_event, 12 command_event, 29
  session_checkpoint, 1 session_close. Zero `dropped_summary`,
  `guard_exhausted`, `cap_reached`, `writer_failed`. All snapshots
  `observation_complete = True`. `inbox_errors` 0 throughout, clean
  `stop` → `disarm` → UNARMED at close.
- Ticks advanced ~6970457 → ~8670005 at NORMAL, unpaused. Sim behavior
  observed in rows: dish-collect/wash queue at sink, then `stand`,
  autonomy `stand_Passive`, then reading (Owner: sitting at sofa).
- Mood steady: type `14643` intensity 1 all session. Moodlets live:
  16 signals at arm, 14 mid-session, 16 at close (two expired, two
  arrived). `observation_complete = True` throughout.

## Owner panel vs probe (motive root cause)

Owner-reported panel (sim alone, reading on sofa; screenshot in report
message): Bladder green ~4/5 rising, Hunger green ~4/5, Energy green ~3/5,
Hygiene green ~4/5, Fun orange low ~1/4 falling, Social red nearly empty.
Low fun + near-empty social consistent with solo reading.

Probe 2.3.0 reported `motives: []` on all 1665 rows. Live root cause
(verified against TARGET_BYTECODE `simulation.zip` on 1.128.90.1030):

- DS1 guessed `entry._cached_value` / `entry._last_update_ticks`. Neither
  string exists in the statistics bytecode (`_cached_value` occurs only in
  `retail/retail_component.pyc`). Every motive row raised internally and
  was skipped by the per-row guard — hence silent empties.
- Actual 1.128 chain: `Statistic.get_value` reads `inst._modified_value`
  (!= None) else `cls.default_value` (disassembled); `ContinuousStatistic`
  (commodities' class) has NO `get_value` override — but its `get_value`
  calls `inst._update_value()` first (disassembled), which advances decay
  state. So Domus must never call `get_value`/`_update_value`; the pure
  replay is: read `inst._modified_value`, fall back to
  `inst.default_value` when None. Age: `inst._last_update` (ticks, stamped
  by `_update_value` from `sim_now` — the only tick-stamp attr in
  `continuous_statistic.pyc`).
- `get_all_commodities()` confirmed pure: returns non-None `_statistics`
  values only (disassembled; no create path).
- Fix applied in tree (uncommitted): `observers._read_cached_motive`
  reads `_modified_value` → `default_value` fallback, `_last_update`;
  `read_presence` passes `include_spawn_point=False` explicitly (method
  takes `(self, allow_hidden_flags, include_spawn_point)` — verified by
  disassembly; defaults unknown, so both args are now explicit).
  `test_ds1_senses.py` fakes updated + a `default_value`-fallback case.
  Full 3.7.0 suite 251 OK, guards exit 0.

## Presence/social verdict

`presence: []`, `social: []` on all rows — CORRECT: Owner confirms the
sim is alone on the lot. Social-sense verification needs a second sim on
the lot (future session with a visitor/guest scene).

## Owner decisions recorded

- None new. Prior stands: single checkout, no worktrees; merge on Owner
  call; E0 deferred; spending cap deferred.

## Next

1. Gate + commit the 2.3.1 motive fix (build/verify), push on
   `domus-next`.
2. Install 2.3.1 with the game closed (Owner closes when ready).
3. Short live re-check: arm/start, confirm `motives` non-empty vs panel,
   stop/disarm. Then DA1 (atlas dump design).
