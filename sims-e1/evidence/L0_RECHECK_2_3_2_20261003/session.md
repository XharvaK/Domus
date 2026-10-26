# LAB L0 re-check: probe 2.3.2 live on LAB_E1, 2026-10-03

Probe 2.3.2 (DS1F, `74f5ba8`) was installed after the Owner closed the game. The build hash `7EFB0461…4704` equals the DS1F gate. The Owner launched and loaded LAB_E1. Session `26478092-c537-4003-be68-d4d01a51fab6`, same body and save (sim `118245043779534861`, slot 2, guid 2773024768). Commands were sent through the helper (`DomusTools`, issuer `agent:claude`).

## Result: the motive read fails at `_modified_value` (DS1G needed)

- `status` before arming: probe 2.3.2, schema 4, `inbox_autostart` `ZONE:manager`, `inbox_errors` 0, `motive_diag` present (initial `ok`, no read yet).
- Armed `lab_e1` → OK. `start` → OK. State SAMPLING.
- After ~12 s, `motive_diag`:
  - `stage`: `row_error:_modified_value`
  - `matched`: 0
  - `seen_guids`: 10020, 16469, 16575, 16585, 16589, 16590, 16616, 16633, 16640, 16652, 16653, 16654, 16655, 16656, 16657, 16658, 16705, 24998, 25002, 29114, 33350, 33351, 38439, 39470, 76777, 97781, 181210, 182176, 217240, 272961, 277010, 291601, plus one large per-instance ID that changes between reads.
- The pure route works live: the statistic component, `get_commodity_tracker(create=False)` and `get_all_commodities()` give real commodities.
- The motive table GUIDs are present (hunger 16656, energy 16654, and the 16652–16658 block), so the GUID table is right.
- Reading `_modified_value` on a live 1.128 motive commodity raises. So 2.3.1's `[]` was the same field failure, silently swallowed.
- Other senses fine in the same rows: `presence_snapshot` with body/posture (`sit`), interactions (sit_Passive QUEUED, seating_Sit RUNNING), moodlets; `observation_complete` true; `motives: []`.
- Clean `stop` → `disarm` → `status` UNARMED, `inbox_errors` 0.

## Verdict and next step

DS1 not closed. **DS1G (probe 2.3.3):** from 1.128 bytecode, find the attribute that actually holds a live commodity's stored value (the instance layout/`__slots__` along the `Commodity` MRO, and what the `get_value` bound for a `Commodity` reads before its update step). Replace `_modified_value` with that verified pure read, then gate, install and re-check.

## Deviations

- A short session (~1 min of sampling) instead of ~3 minutes: the diagnostic answered the question on the first read, so a longer run would have added nothing.
- The Owner wasn't asked to compare the Needs panel, since there were no values to compare.
