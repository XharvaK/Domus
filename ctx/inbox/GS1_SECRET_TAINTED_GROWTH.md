# GS1: Owner decision. Growth written by a pass that saw secret evidence is stored as `never_public`.

From: Architect, relaying the **Owner** (~10:45 TRT). To: Manager → **Operator** (Sol low), then **Auditor** (a separate run, codex-cc Muse high). This is a feature, so it gets a review. Results: `outbox\GS1_RESULTS.md`.
**Base:** Ashley `main` **after the A3 merge** (including the A3h fix). **Branch:** `gs1-tainted-growth`. **No deploy** (D-042). **Order:** GS1 lands **before A4 starts**, and A4's base becomes main after GS1. GS1 is small, and A4 touches the same aftermath and growth paths.

> Owner: they "should be marked", and the label is **`never_public`** (chosen over `secret`). `secret` can never re-enter model context (`core/privacy/classification.ts` `canEnterModelContext`), so she would lose that growth. `never_public` stays private-only and still returns to her owner-private Thought.

## Build

1. **Pass taint, a fact the Host records.**
   - While the Thought input for an `owner_private` pass is assembled (`thought/input.ts`, `filterEvidence` / `filterStructured`), compute `sawSecret = true` when any evidence row or structured value **included** in that input has `dataClassification === "secret"` or `secretOmitted`.
   - Carry it with the settlement so the normal path **and** the recovery path both have it.
   - Use the smallest carrier that already reaches `recordSettlementAftermath`. If none exists, add one nullable column in the next free sidecar version (then the A3d pin lesson applies: every version pin, in every form).
   - **No change to settlement authority, admission or what Thought sees.**
2. **The label.** In `thought/aftermath.ts`, every Thought-authored growth write uses `sawSecret ? "never_public" : "ordinary"` instead of the hard-coded `"ordinary"` (main `:100`, `:109`, plus any journal or growth writer on that path).
   - That covers growth (appraisal, expectations, revisions, friction from Thought) and night.
   - **`sense_declines` gets a `data_classification` column** (the same version step), written the same way.
   - Host-recorded friction stays `never_public`, as now.
3. **Projections keep working.** Grep every growth, journal, night, practice and sense projection read.
   - Any filter of the form `= 'ordinary'` (as opposed to `!= 'secret'`) would hide her own growth. **List each one with file:line and fix it to `!= 'secret'`** where it feeds owner-private Thought or the Owner's views.
   - **Don't widen any non-owner surface.** If a non-owner surface reads growth, it must exclude `never_public`; say whether one exists.
4. **Essence comment at the taint computation:** "the Host records only that secret evidence was present; it never reads or judges it."

## Tests (red-first)

- An owner-private pass whose input includes a secret evidence row writes every growth, night and decline row as `never_public`. Without one, the rows are `ordinary`.
- A `secretOmitted` row also taints the pass.
- The recovery-path aftermath gets the same label as the live path.
- Next owner-private pass: `never_public` growth rows **still appear** in `growthForThought` / practices / senses (she keeps her growth).
- Any non-owner surface found in Build 3 excludes them.
- Migration, fresh and upgrade, if a column was added, with the pins.

## Verification

- Focused tests plus `build:agent` per commit.
- At the tip: the full agent suite (0 failures), Discord, and `test:current-deployment` (the same 21 names).
- Report every changed projection filter.

## STOP

- Computing the taint requires reading secret content, not just the labels.
- A change to what Thought sees, or to settlement authority.
- A projection where `never_public` would reach a non-owner audience and can't be excluded locally.

## Auditor

Review `<A3-merge>..gs1-tainted-growth`, with red-first on ≥2 tests per commit and the full suite at the tip. Specifically check:
- the taint is computed only from labels;
- no projection to a non-owner audience carries `never_public`;
- the recovery path is covered.

## Addendum (after the A3g stop)

The stopped A3g work (`/workspace/ops/recovery/A3g_stopped_A3h/working.diff`, 215 lines, `thoughtInputContainsSecret` plus its input/run/aftermath edits) is close to GS1 Build 1–2. Give it to the GS1 coder as **unverified starting material**. The coder must:
- re-check it against this packet: labels only, `never_public` not `secret`, the recovery path, sense_declines classification;
- red-first every test anyway.

Don't apply the stash on `a3-phase3`; GS1 works on its own branch from the A3 merge.
