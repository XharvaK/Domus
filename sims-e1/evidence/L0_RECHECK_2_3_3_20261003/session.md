# LAB L0 re-check: probe 2.3.3 live on LAB_E1, 2026-10-03 — DS1 CLOSED

Probe 2.3.3 (DS1G, `55c9b8d`) was installed while the game was closed. The build hash `81ACB76C…94ACFA` equals the DS1G gate. The Owner loaded LAB_E1. Session `b4ad0449-fb70-4af5-9e58-e4fb560cb72e`, same body (sim `118245043779534861`). Commands were sent through the helper (`DomusTools`, issuer `agent:claude`).

## Result: motives read live and track the game

- `status` before arming: 2.3.3, UNARMED, `inbox_autostart` `ZONE:manager`, `inbox_errors` 0.
- Armed `lab_e1` → OK. `start` → OK. After ~12 s: `motive_diag` `stage = ok`, `matched = 6`.
- **Comparison with the Needs panel** (Owner screenshot, game ~14:25 day 2) against the probe at 14:24:

  | Need | Probe | Panel |
  |---|---|---|
  | Bladder | 63 ok | green, about two thirds |
  | Fun | 25 low | orange, about a quarter |
  | Hunger | 27 low | orange, about a quarter |
  | Energy | 13 distress | short orange bar, fast-decay arrows |
  | Social | 0 distress | empty red |
  | Hygiene | 0 distress | empty red |

  All six match. Energy shows orange in the panel at about 13, while our `distress` band is ≤20. The band is our own mapping, not the game's colour.
- **Movement over ~51 snapshots (game 14:13 → 20:24):**
  - the Sim went to bed (`bed_Sleep`), and energy rose 12 → 36 → 59 → 67;
  - bladder fell 65 → 42 and hunger 27 → 22;
  - social and hygiene stayed 0, which is consistent with sleeping alone.
  - `age_ticks` resets whenever the game updates a commodity (e.g. energy's age stays small while sleeping), as designed.
- Clean `stop` → `disarm` → UNARMED, `inbox_errors` 0, `motive_diag` still `ok`/6.

## Verdict

**DS1 (motives) CLOSED** on 1.128.90.1030 with probe 2.3.3. The values are cached (the value at `_last_update` plus age), not decayed to now. OD1 (whether fresher values are needed) stays an Owner decision for later. The cached value plus age is enough for now.

## Deviations

- The Owner sent a Needs panel screenshot instead of describing the bars.
