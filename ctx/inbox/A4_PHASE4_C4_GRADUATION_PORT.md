# A4: Ashley plan Phase 4, part 1. Port C4 (cognitive-graduation) into v021 and retire the old module.

From: Architect. To: Manager → **Operator** (on the harness/model of the moment per H1f: Codex while it has quota, else Muse on cmdc), then **Auditor** (a separate run). Date: 2026-10-01. Results: `outbox\A4_RESULTS.md`.
**Base:** Ashley `main` **after A3 is merged** (the A3 merge SHA). **Don't start before that merge.** **Branch:** `a4-c4-port`. **No deploy** (D-042).
**Design source:** `_Internal\papers\ASHLEY_IMPLEMENTATION_PLAN_v1.md` §Phase 4 C4. **This packet wins where they differ.** C3 (learned-autonomy) is **A5**, a separate packet after A4.

## Standing rules (plan §0.2, plus the lessons from A3)

- **Red-first:** each new test fails by assertion at its commit's parent.
- **Versions:**
  - the sidecar takes the **next free version**, expected 49 after A3;
  - nuclear takes the **next free version**, expected 55 after A2's v54;
  - `core/cognition/schema-contract.ts` is updated in the same commit.
- **The A3d lesson:** a version bump updates **every** current-version pin in **every** form: `toBe(N)`, `toEqual({schema_version:N})`, `toMatchObject`, `user_version`, in all test dirs (sidecar and nuclear).
  - Sweep with `rg -n "\b(45|46|47|48|54)\b" -g '*.test.ts'` plus context. List each pin as changed or kept (a ladder intermediate stays).
- **Thought fingerprint pins:** any commit touching `thought/output-contract.ts` updates every pin and lists them.
- **Essence line** on every new module. **The Host only records facts;** Thought owns meaning.
- **Public repo:** no model IDs or Owner material.
- **Reading discipline (W1):** grep or slice; no whole-file reads over 200 lines.

## VERIFIED anchors at 592669d (re-verify at the base and report any drift)

| Anchor | Location |
|---|---|
| old module (17 files, ~3.0k lines) | `core/cognitive-graduation/` |
| C4 tables | `migration-38.ts` (`cognitive_predictions` :27, `cognitive_outcome_observations` :59, `cognitive_outcome_adjudications` :83, `working_view_links` :117, `lived_experience_links` :124, `thought_calibration_adjustments` :145) |
| calibration API | `calibration.ts` (`recordThoughtCalibrationAdjustment` :181, `listEligibleThoughtCalibration` :271, `rollbackCognitiveGraduation` :303) |
| external importers | `server.ts:85` (diagnostics), `:1241` (`GET /nuclear/cognitive-graduation`); `core/db.ts:110`; `core/cognition/schema-contract.ts:24`; `core/reflection/c4-future-only.test.ts` |
| C4 → C3 imports (gone after the port) | `predictions.ts:4–5`, `view-links.ts:2` (learned-autonomy) |
| v021 light port | `cognitive-v021/growth/expectations.ts` (`EXPECTATION_OUTCOMES` :19, `recordExpectations` :127, `checkExpectations` :155, `listOpenExpectations` :186), table `sidecar/schema.ts:1563` |
| Thought contract | `expectationChecks` `thought/output-contract.ts:363`; the growth guidance string `:778` |
| Mint row counts (G0.1) | **all six C4 tables have 0 rows**, so no row migration is needed |
| removal pattern to follow | A2 `bdde8e7` (historic DDL kept for the ladder, a legacy fixture, a drop migration, every pin bumped) |

## Build (port, don't reinvent: reuse C4's logic and **port its tests**)

**Essence of `cognitive-v021/graduation/`:** *her predictions meet what happened; the Host compares only what a receipt can decide, and calibration is hers to admit.*

1. **Expectations become predictions** (sidecar next version).
   - `expectations` gains nullable `judgment_class` (≤40), `observable` (≤200), `horizon_hours` (1–720) and `check_kind` (`owner_reply` | `delivered` | NULL). Use a `migrate…ToVn` helper if the table must be rebuilt.
   - `growth.expectations[]` in the output contract gains the optional `judgmentClass`, `observable`, `horizonHours` and `check` with the same bounds. Existing expectations stay valid.
   - Add one sentence to the growth guidance: *"for an expectation you can be held to, add judgmentClass (a short class name you reuse), observable, horizonHours, and check owner_reply or delivered when Alex's reply or the delivery of this message decides it."*
2. **Observations:** `graduation_observations` (ported from the C4 observation schema, keyed to `expectation_id`).
   - **Deterministic comparators, exactly two:**
     - **`owner_reply`:** an owner message admitted within `horizon_hours` after the expectation is `receipt_backed` (with the message id as ref, **not the text**); none by the horizon is `missing`.
     - **`delivered`:** the delivery receipt of that cycle's speech within the horizon is `receipt_backed`; a terminal delivery failure, or none by the horizon, is `missing`.
   - Everything else gets nothing from the Host.
   - **One recorder per comparator**, at its terminal choke point. The A3b rule applies: idempotent per `(expectation_id, kind)`, a recorder failure never alters the path, **STOP past 3 recorders**.
3. **Adjudications:** `graduation_adjudications`, ported, with `supersedesAdjudicationId` and correction classes kept.
   - **`deterministic_compare`** from a comparator: `receipt_backed` → `confirmed`, `missing` → `contradicted`.
   - **`ashley_thought_reflection`** from her existing `expectationChecks`: `met` → `confirmed`, `missed` → `contradicted`, `mixed` → `partial_support`, `unknowable` → `unresolved`.
   - **`owner_confirmed`** through the owner endpoint (item 6).
   - If both a comparator and Thought adjudicate one expectation, keep both rows. The later one supersedes for calibration counting. Say which rule you implemented.
4. **Calibration:** `graduation_calibration`, with the C4 `calibration.ts` lifecycle ported (`proposed → admitted → eligible_for_future_thought → demoted/expired/contradicted/rolled_back`).
   - **Host proposal rule:**
     - **constants:** `CALIBRATION_MIN_ADJUDICATIONS = 4`, `CALIBRATION_WINDOW_DAYS = 30`, `CALIBRATION_INCREASE_AT = 0.5`, `CALIBRATION_DECREASE_AT = 0.15`, declared and exported;
     - per `judgment_class`, `contradicted / (confirmed + contradicted)`, counting `partial_support`/`unresolved` in neither;
     - **one open proposal per class.**
   - **Thought decides:**
     - `growth.calibrationPositions: [{calibrationId, position: admit|decline, rationale ≤200}]`, at most 3 per settlement, valid only in a pass **after** the one that proposed it;
     - admitted proposals reach `ThoughtGrowth.calibration` as `{class, adjustment, sinceMs}` lines (≤5).
   - **Owner rollback:** `POST /growth/calibration/rollback` (owner-only, the `/growth/snapshots` guard), reusing the ported `rollbackCognitiveGraduation` semantics.
5. **Mode (sidecar `graduation_contract_state`, ported from contract-state):**
   - `observe` is the default: everything is recorded and proposals are created, but **nothing graduation-related reaches ThoughtInput**. That means no proposals to position, no calibration lines, and `calibrationPositions` is ignored with a code.
   - `apply`: proposals and eligible lines are shown.
   - `dark_apply` stays in the enum for compatibility and behaves as `observe`, plus a diagnostic counter of what would have been shown.
   - **Owner-only `POST /growth/graduation/mode`** records the change with `actor` and `at`. **The flip to `apply` is the Owner's later decision. Nothing in A4 sets it.**
6. **Owner view and diagnostics:**
   - `GET /growth/graduation` (owner-only): per-class counts, open proposals, admitted lines, and mode.
   - **Re-point** `GET /nuclear/cognitive-graduation` (`server.ts:1241`) to the port's diagnostics, keeping the route and its owner guard; update `route-surface.json` if its shape changes.
   - `POST /growth/graduation/adjudicate` (owner-only) for `owner_confirmed`.
7. **Retire the old module:**
   - delete `core/cognitive-graduation/`;
   - **nuclear next version:** drop the six C4 tables using the A2 pattern (historic DDL kept for the ladder under `core/cognition/`, a legacy fixture). **The drop migration is fail-closed:** if any of the six tables has rows, it throws with `c4_rows_present:<table>:<n>` and changes nothing. G0.1 says 0, and the pre-deploy backup is the net;
   - `cognitive_maturation_contract_state`'s `c4` row is **kept** until A5 retires the table;
   - port or retire `core/reflection/c4-future-only.test.ts` (say which, with the reason);
   - `c3-interface.test.ts` goes with the module. Confirm that its C3 assertions are still covered by `core/learned-autonomy/` tests, or move them there.

## Tests (red-first)

- **The original C4 tests are ported** (outcome, prediction-gap, select, settlement, schema): same cases, new paths and sidecar. List each one: ported, or dropped with a reason.
- **The comparators:**
  - owner reply within/after the horizon gives confirmed/contradicted;
  - delivered vs failed vs none;
  - idempotency;
  - a throwing recorder doesn't alter the path.
- **The proposal rule at the boundaries:** 3 adjudications give no proposal; ratios of 0.5 and 0.15 exactly; the 30-day window edge.
- **calibrationPositions:**
  - rejected in the proposing pass;
  - at most 3;
  - admit puts it in `ThoughtGrowth.calibration`, and decline doesn't;
  - an owner rollback removes it.
- **The mode gate:** `observe` (and `dark_apply`) gives **no** graduation fields in ThoughtInput, and `apply` shows them. Only the owner can change the mode.
- **Migrations:**
  - sidecar fresh and upgrade from the previous version;
  - nuclear drop: empty tables pass, a seeded row throws `c4_rows_present` and leaves the DB unchanged;
  - legacy fixture upgrade.
- **Pins:** every fingerprint pin and every version pin (the A3d lesson).
- Owner routes reject non-owners.

## Verification and report

- **Per commit:** focused vitest plus `npm run build:agent`.
- **At the tip:** the full agent suite (**0 failures**), Discord, `test:current-release`, and `test:current-deployment` (the same 21 names as at 592669d).
- **`A4_CODER_REPORT.md`:**
  - each item MET or NOT MET;
  - red-first assertions;
  - the versions chosen;
  - every pin site;
  - the ported-test list;
  - the comparator recorder sites (file:line);
  - the supersede rule;
  - any STOP.

## STOP conditions

- a comparator needs more than 3 recorders, or one with no choke point;
- any change to admission, settlement authority, delivery semantics or foundational rules;
- the nuclear drop can't be made fail-closed;
- a C4 test can't be ported without changing its meaning;
- anything that needs a deploy, Mint or credentials.

## Auditor (a separate run)

- Review `<A3-merge>..a4-c4-port` J106-style against this packet.
- Re-run red-first on ≥2 tests per commit, plus the full suite at the tip.
- **Specifically check:**
  - no message or content text in observations, adjudications or calibration rows;
  - the mode gate;
  - the fail-closed drop.
