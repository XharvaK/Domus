# LAB L0 re-check: probe 2.3.1 live on LAB_E1, 2026-10-02

Second live session (game relaunched by Owner after 2.3.1 install).
Session `6b9066ca-a530-41bd-a1d3-4b637dda3b43`, same body/save
(sim `118245043779534861`, slot 2, guid 2773024768).

## Result: motives STILL empty — the 2.3.1 fix did not take effect live

- Armed LAB_E1 → OK, `start` → OK; `status` SAMPLING, probe 2.3.1,
  schema 4, lineage `CONTINUES_LAST_SAVE`, detected `1.128.90.1030`
  (PID 20716), `inbox_errors` 0.
- Read ~785 presence_snapshot rows: ALL `motives: []`,
  `observation_complete = True` throughout, zero drops.
- Mood live and varying this time (14643 ×740, 27149 ×31, 14646 ×14) —
  moodlets (15–16) and mood track the game. Presence/social empty
  (sim alone — consistent).
- Clean `stop` → `disarm` → UNARMED, `inbox_errors` 0.

## Why the fix didn't land

`sim_info.commodity_tracker` is NOT a live accessor on 1.128: the
`commodity_tracker` name in `sim_info.pyc` occurs only as a STORE_ATTR
target (init writes `self.commodity_tracker.simulation_level`), never as
a property/method. `SimInfo` exposes `get_statistic(stat, add)` (which
routes via an internal `get_tracker` → `tracker.get_statistic`), but no
public `commodity_tracker` attribute/method exists in the class consts.
So `read_motives` raises `AttributeError` on the very first line, returns
`[]` — the `_modified_value`/`_last_update` fix never even executes.

`get_all_commodities()` itself is verified pure (returns non-None
`_statistics` values, no create path), and the value/age replay
(`_modified_value` → `default_value`, `_last_update`) is verified — but
the entry point is wrong. Next step is finding the real live tracker
route (candidate: `get_statistic` per-motive with `add=False`, or the
internal tracker object), verifying its purity on 1.128 bytecode, then
probe 2.3.2.

## Stand note (from prior session, confirmed here)

Posture alternates sit/stand/shower/toilet_sit/cook with activity; the
`stand` rows were dish-washing, `sit` + `seating_Sit` RUNNING at close.
Not a bug — no change.
