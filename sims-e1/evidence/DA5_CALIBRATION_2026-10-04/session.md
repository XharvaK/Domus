# DA5 calibration session, 2026-10-04

- Save: LAB_E1_FORK (LAB_E1 untouched). Aging off, full native autonomy, speed 3. One Sim alone on the lot (L0 chamber: walkbys suppressed, no visitors, so no social data).
- Probe 2.7.0 (BUILD_SHA256 AE63EDC7...2F8B), armed `lab_e1_fork`, `start`, `calibrate` (observe only; actuation refused). Lineage class FOREIGN_OR_UNKNOWN. 6 motives matched.
- Helper bridge `--interval 5` with transport disabled (`DOMUS_ASHLEY_URL=""`): thalamus decisions logged, nothing sent to Mint. `thalamus_decisions.jsonl` = this session's rows only (wall_ms >= 1791105000000), 1160 rows.
- Owner notes: one short accidental pause; the Owner directed the Sim to repair the sink and the fridge (pie menu, not autonomy: autonomy never repaired anything); after sleep the game drops from SPEED3 to normal on its own (native behaviour), the Owner set speed 3 again by hand.
- Ended after ~40 min of play (diminishing returns): `stop`, `disarm`.
- Analyzer (`domus_helper.calibration.analyze`, full file): 268 AUTONOMY spans, 97 affordances, 2 gaps; ticks by speed NORMAL 426,720 / PAUSED 721 / SPEED3 9,804,818 / SUPER_SPEED3 4,789,363; wall ms NORMAL 398,334 / PAUSED 5,128 / SPEED3 1,385,939 / SUPER_SPEED3 136,693. Full output: `calibration_report.json`.
- Research on it: R-AUT (`_Internal/work/RAUT_REPORT.md`, analysis script `raut/analyze.py`).
