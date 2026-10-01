# D13: Domus Phase 4 senses (probe 2.3.0). Read-only motives, moodlets, mood, presence and social.

From: Architect (~09:05 TRT). To: Manager → **Operator** (implementation, model per the rotation D-045/H1h/D-045b), then **Auditor** (a separate run on codex-cc, Muse). Results: `outbox\D13_RESULTS.md`.
**H2a/D-046 applies:** Manager writes one job brief per sub-job below. This packet is the REFERENCE.

## R-M1 ruling

R-M1 is accepted as PARTIAL. Every read chain is VERIFIED read-only in the pre-1.128 mirror. Three things stay UNKNOWN and go to the LAB live check: what the reads do on 1.128, which motive GUIDs are live, and the localized buff names. My rulings, where R-M1 left a choice:

| Point | Ruling |
|---|---|
| Motive discovery | **No `get_statistic` at all.** Enumerate the LAB Sim's live commodities with `commodity_tracker.get_all_commodities()`, and keep those whose `guid64` is in the motive table (next row). Read each kept instance's `get_value()`, `min_value` and `max_value`. This removes the `add=True` risk entirely. |
| Motive table | `{16656: "hunger", 16654: "energy", 16652: "bladder", 16657: "hygiene", 16655: "fun", 16658: "social"}`. It's a module constant with a source comment: "community-sourced (s4cl motives enum), LAB-verified on 1.128 in the Owner session". Comfort (16653) is left out. |
| Motive value and band | `value` = round((v − min) / (max − min) × 100), clamped 0–100; if `max == min`, None. `band`: `"distress"` ≤ 20, `"low"` ≤ 50, else `"ok"`. That's a fixed scale, not tuning-driven. The tuning threshold is a later refinement once LAB shows it. |
| Moodlets | Iterate `sim_info.Buffs` directly. Each entry becomes `MOODLET` with `tuning_id = str(guid64)` and `magnitude = "w:<mood_weight>"`. `game_text` stays **None** (no read-only localized getter is verified), and `consequences`/`native_override` stay None. **No `get_timeout_time`**: its body wasn't read, and it touches `get_commodity_instance`. **The hidden-buff filter is left out for D13:** emit every entry, up to the cap. LAB compares with the panel, and a filter becomes a later bugfix. |
| Mood | Only `Buffs.get_mood()` and `get_mood_intensity()`. Record `{"type": str(guid64) or None, "intensity": number or None}`. No private fields. |
| Presence | `services.sim_info_manager().instanced_sims_on_active_lot_gen(...)` with the probe's existing hidden flags. Per Sim: `{id, active_household (bool), level (int or None)}`. Active household = the Sim's `household_id` equals `services.active_household_id()` or `active_household().id`, whichever the existing probe already uses. If neither is used yet, use `active_household()`. Cap **N = 8**, and set the existing truncation flag beyond that. No room (UNKNOWN). |
| Social | For each present non-LAB Sim, iterate `si_state` and then `queue` (plain iteration, both None-guarded). Keep an entry when its `.target` is the LAB Sim or its SimInfo (compare `.id`). Describe kept entries with the existing `_describe_interaction`. Cap **M = 4**. No `get_participants`, no watchers, no cancel. |
| Attribute probing | No new `getattr`/`hasattr` if the guard bans them. Use `try/except AttributeError` per row. **A row failure skips the row; a sense failure gives its empty default.** A poll never fails because of a sense. |
| Schema | **Next free version.** That's v4, or v5 if D11-3 took v4 for `inbox_autostart`. `presence_snapshot` gains three **required** keys: `presence` (list ≤ 8 of `{id, active_household, level}`), `social` (list ≤ 4 of the existing interaction row shape) and `mood` (`{type, intensity}` or null). Motives and signals are unchanged. Add the constants `MAX_PRESENCE = 8` and `MAX_SOCIAL = 4`. |
| Size | **A writer-side budget, so a record never goes over 8 KiB.** If the serialized record would exceed `MAX_SERIALIZED_RECORD_BYTES`, drop in this order until it fits: social → presence beyond 4 → signals beyond 8 → `game_text` (None today anyway). Set the existing truncation flag, and add a `note` if there's a free field. A worst-case test must serialize ≤ 8 KiB with the **existing** interactions filled too. |

## Base and order

- **Base:** `domus-next` **after D11 is merged into it.** Manager merges `d11-autostart` `--no-ff` once D11-3 and J118 are green (D11 is a bugfix, so no review). **Branch:** `d13-senses`. Don't start before that merge. If D11-3 took schema v4, D13 takes v5.
- **Sub-jobs, each ≤ 25 turns and ≤ 25 minutes,** with a commit at each green step, heartbeats, and the D11e stall rule (no commit in 25 minutes means stop and report; continue from state):
  1. **D13-1, schema:**
     - the version bump;
     - the three fields;
     - `MAX_PRESENCE`/`MAX_SOCIAL`;
     - validator tests for good, oversize and wrong-shape records;
     - **then the byte-copy of `schema.py` into `helper/domus_helper/vendor/`**, plus the helper's shape gate and AST drift test.
     - Commit: `schema: v<N> presence, social, mood (D13-1)`.
  2. **D13-2, LAB reads:**
     - motives, moodlets and mood in `observers.py`, with fakes;
     - Commit: `observers: read-only motives, moodlets, mood (D13-2)`.
  3. **D13-3, other Sims and the size budget:**
     - presence, social and the writer size budget;
     - Commit: `observers: presence and social reads, record size budget (D13-3)`.
  4. **D13-4, version:**
     - `PROBE_VERSION` 2.3.0 at every site (`rg -n "2\.2\.1"`);
     - the A12a-style row if D11 established one;
     - helper vendor re-sync if anything moved;
     - Commit: `probe: 2.3.0 senses (D13-4)`.

## Tests (red-first, sims-e1 plus the helper)

- **A tripwire fake:**
  - its game objects raise if any `FORBIDDEN_CALL_NAMES` method is called, or `get_statistic`/`add_statistic`/`set_value`/`add_value`/`get_timeout_time`/`add_watcher`/`get_participants`;
  - one full poll runs against it **with no raise**.
- **Motives:**
  - the six are found by `guid64` and normalized, including the boundaries 0, 20, 50 and 100;
  - `max == min` gives None;
  - an unknown GUID is ignored;
  - a missing tracker gives `[]`.
- **Moodlets:** ≤ 16; the `w:` magnitude; `game_text` None; an entry that raises is skipped.
- **Mood:** present; None.
- **Presence:**
  - LAB present exactly once, with the right flag;
  - the cap of 8 sets truncation;
  - a Sim with no instance is skipped.
- **Social:**
  - an entry targeting LAB is kept, and one targeting another Sim isn't;
  - the queue and si_state are both read;
  - a None `si_state` is fine;
  - cap 4.
- **Size:** the worst case (8 interactions, 6 motives, 16 signals with full game_text, 8 presence, 4 social) is ≤ 8 KiB after the budget, and the drop order is as ruled.
- **`check_guards` passes unchanged.**
- **The helper:** pytest green on 3.13 and 3.14, and the vendored files byte-identical.

## Verification

- **Per commit:** focused tests.
- **At the tip:**
  - full sims-e1 (only the 2 known Linux failures, per D11d);
  - `test_portability`;
  - the helper pytest.
- **Then J118 on XQX:** the pinned 3.7.0 gate, 3 equal hashes, 0 failures. **No install.** 2.3.0 is installed in the combined Owner session, and it supersedes the 2.2.1 install, since it contains D11.

## Auditor (a separate run, codex-cc Muse)

- Review `<domus-next after D11>..d13-senses` against this packet.
- Red-first on ≥ 2 tests per commit, plus the full sims-e1 at the tip.
- **Specifically check:**
  - **every game-facing call in the diff is a getter or iteration.** List each name with file:line, and check it against the R-M1 Q6 list;
  - no `get_statistic`;
  - the tripwire fake really covers the poll path;
  - the size budget order.

## For the Owner session (added to the live-check list)

These are the R-M1 Output 3 checks 1–7, run through the D12 MCP on LAB_E1 with 2.3.0. Add to them:
- confirm the six motive GUIDs live, and record any that don't match;
- record the moodlet count against the visible panel (this sizes the hidden-buff filter bugfix);
- try one read-only localized-name read and report the result verbatim.

## STOP

- Any read that would need a mutating or forbidden call to work.
- A schema shape that can't stay under 8 KiB with the budget.
- Any change to the actuator or the E2 command path.
