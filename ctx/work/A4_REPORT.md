STATUS: STOPPED — Owner requested stop after committing corrections.

# A4 implementation report — 2026-10-01

## Candidate and authority
Root: C:\Users\Xharv\Projects\Ashley.
Branch: a4-c4-port. HEAD: bc7003ed6057816e739b10b1fc37b6eeecf7386a.
Verified preflight base: bd566cb7b40cc9aea4709d286077630e758c5bc8; tree d8f2fb89340dd70c2b58d4fe06e87f65bba3ca3e. Tracked checkout clean after final commit.
Scope: A4_PHASE4_C4_GRADUATION_PORT.md, amended by A4a_TEST_PORT_RULING.md and the next-free-version roadmap ruling. A5 and later phases were not implemented.
A4a resolves the original preflight STOP: observations never adjudicate; the generic explicit typed comparison API remains; exactly two automatic recorders make observation and explicit deterministic_compare calls in one transaction.
This report establishes source implementation and the checks below. It does not establish completed qualification, production activation, promotion, or Owner acceptance.

## Implemented roadmap
1. Prediction metadata: expectations and Thought output accept optional bounded judgmentClass, observable, horizonHours and check. Legacy string expectations remain valid. Sidecar migration 49→50.
2. Observations: separate append-only records; receipt/exact binding validation; no adjudication on observation receipt. Exactly two automatic recorders, owner_reply and delivered, use three servicing sites including existing horizon reconciliation. Atomic writes, idempotency, failure isolation and no copied message text.
3. Adjudications: explicit deterministic_compare, ashley_thought_reflection and owner_confirmed authorities. General typed comparison retained. Corrections and supersession retained. Calibration selects latest adjudication by time, then rowid.
4. Calibration: four-adjudication minimum, 30-day window, contradicted/(confirmed+contradicted), increase threshold0.5 and decrease threshold0.15. Partial/unresolved excluded. One open proposal per class; stale basis demoted before replacement. Thought admits/declines at most3 positions in a later pass; at most5 eligible calibration lines. Rollback preserves history.
5. Mode: observe default; observe and dark_apply expose no graduation input and ignore positions with a code. dark_apply reports would-show diagnostics. Owner-gated apply control records actor/time; no apply flip performed.
6. Owner controls: GET /growth/graduation; POST /growth/graduation/mode; POST /growth/graduation/adjudicate; POST /growth/calibration/rollback. Legacy GET /nuclear/cognitive-graduation points to sidecar diagnostics. Guards, transport authorization and route manifest updated.
7. Retirement: old cognitive-graduation module removed. Nuclear migration54→55 drops six C4 tables only when empty; c4_rows_present:<table>:<n> refuses before continuity writes or drop DDL. Historic DDL/fixtures retained and c4 contract marker kept. Current schema/fingerprint pins updated. Existing C3 eligibility assertions retained.

## Commits
- 7095113: prediction metadata and durable sidecar layers.
- efdcc91: explicit observations and Thought adjudications.
- 2f0a01d: later-pass Thought calibration admission.
- 6fb1587: receipt-backed automatic recorders.
- b23d8f7: Owner controls and diagnostics.
- d02c8fc: fail-closed nuclear v55 retirement.
- bc7003e: stale proposal demotion and regression corrections.

## Verification and limitations
Build passed at final candidate. Affected focused checks passed, including final21 tests in3 files. Discord:168 passed,0 failed.
All seven parent-source replays failed by assertion, with5/6/7/7/4/8/2 failures respectively and no collection errors. This meets the per-commit red-first requirement.
First full agent run:3261 passed,4 failed,2 skipped across459 files. The four failures concerned Windows backup path assertions, a future schema pin, a senses rewind fixture and the chat prefix budget. Corrections and affected checks subsequently passed. Production backup code and the8600 prefix budget were unchanged.
First current-release run failed during current-product checks:2931 passed,3 failed,2 skipped. Stale-proposal and prefix failures were subsequently corrected.
Final full agent and current-release reruns were interrupted at the Owner's stop instruction. Neither has a final passing aggregate. Full/release qualification remains incomplete.
Deployment baseline and tip checks both exited1 with the same21 distinct failure names; exact set equality verified. No new failure name was introduced in that completed comparison.
Root npm ci attempted once and failed EUSAGE because the root has no package-lock.json or shrinkwrap. No dependency or lockfile change was made.
Logs: %TEMP%\ashley-a4-final-build.txt, ashley-a4-closure-last.txt, ashley-a4-discord.txt, ashley-a4-agent-full.txt, ashley-a4-current-release.txt, ashley-a4-agent-final.txt, ashley-a4-current-release-final.txt, ashley-a4-deployment-base.txt, ashley-a4-deployment-tip.txt, and ashley-a4-parent-<commit>.txt.

## Legacy test ledger
Ported cases keep their meaning; fixture/schema identities adapt to sidecar ownership. Retired cases below are not claimed as unchanged ports. New sidecar regressions cover their applicable new contracts separately.

- `c3-interface.test.ts`: “consumes a qualified C3 binding through current C1 evidence and stops after C1 correction” — Dropped: nuclear working-view/C3 integration retired; current C1 correction and C3 demotion remain covered in learned-autonomy/eligibility.test.ts.

- `c3-interface.test.ts`: “does not keep a C4 working view current after C3 demotion” — Dropped: nuclear working-view/C3 integration retired; current C1 correction and C3 demotion remain covered in learned-autonomy/eligibility.test.ts.

- `outcome.test.ts`: “requires a later actual value or evidence binding, and does not adjudicate on receipt” — Ported unchanged in meaning to cognitive-v021/graduation/outcome.test.ts.

- `outcome.test.ts`: “allows missing and OUTCOME_UNKNOWN without treating either as a failed retry” — Ported unchanged in meaning to cognitive-v021/graduation/outcome.test.ts.

- `outcome.test.ts`: “uses deterministic comparison only for typed comparable values and keeps later adjudications append-only” — Ported unchanged in meaning to cognitive-v021/graduation/outcome.test.ts.

- `outcome.test.ts`: “rejects proposed reflection authority, invalid host admission, and semantic claims over unknown outcomes” — Ported unchanged in meaning to cognitive-v021/graduation/outcome.test.ts.

- `outcome.test.ts`: “supports exact evidence plus content binding when a typed value is not copied” — Ported unchanged in meaning to cognitive-v021/graduation/outcome.test.ts.

- `prediction-gap.test.ts`: “keeps the selected prediction pair separate from existing decision telemetry” — Ported unchanged in meaning to cognitive-v021/graduation/prediction-gap.test.ts.

- `prediction-gap.test.ts`: “does not treat the existing initiative-learning surface as Q8 calibration” — Ported unchanged in meaning to cognitive-v021/graduation/prediction-gap.test.ts.

- `schema.test.ts`: “creates append-only prediction, outcome, link, and calibration tables” — Dropped: asserts the six nuclear tables intentionally retired by v55. Historical DDL ladder and new sidecar/migration regressions cover the replacement.

- `select.test.ts`: “stores a bounded prediction with two current C1 references and a working-view link” — Dropped: Nuclear two-C1-reference and working-view-link selector retired; not required by the new expectation contract.

- `select.test.ts`: “does not infer a prediction from decision outcome text or initiative learning” — Dropped: Old nuclear selector retired; decision telemetry/initiative-learning separation is retained in ported prediction-gap cases.

- `select.test.ts`: “refuses missing bounded fields, CoT markers, stale C1 evidence, and secret evidence” — Dropped: Nuclear bounded/C1 selection fixtures retired; new metadata and privacy regressions cover the new contract separately.

- `select.test.ts`: “fails closed when a persisted C4 contract is newer than this candidate” — Dropped: Nuclear C4 selection API retired; sidecar contract-version fail-closed validation is a new contract, not an unchanged port.

- `settlement.test.ts`: “closes the additive chain without promotion or authority widening” — Dropped: nuclear Decision/link/calibration or six-table inventory fixtures have no sidecar equivalent; new sidecar lifecycle and authority regressions cover the replacement.

- `settlement.test.ts`: “classifies all C4 durable records outside the live behavioral projection” — Dropped: nuclear Decision/link/calibration or six-table inventory fixtures have no sidecar equivalent; new sidecar lifecycle and authority regressions cover the replacement.

- `c4-future-only.test.ts`: “records a bounded future adjustment without mutating the admitting Decision” — Dropped: nuclear Decision/effect_value/capability-mode provenance fixtures retired. New later-pass, mode and rollback regressions cover the sidecar contract; these are not unchanged ports.

- `c4-future-only.test.ts`: “keeps observe calibration shadow-only and rejects current-turn or unbounded influence” — Dropped: nuclear Decision/effect_value/capability-mode provenance fixtures retired. New later-pass, mode and rollback regressions cover the sidecar contract; these are not unchanged ports.

- `c4-future-only.test.ts`: “stops influence after rollback and keeps semantic calibration history” — Dropped: nuclear Decision/effect_value/capability-mode provenance fixtures retired. New later-pass, mode and rollback regressions cover the sidecar contract; these are not unchanged ports.

- `c4-future-only.test.ts`: “cannot time-shift a shadow prediction into live future influence” — Dropped: nuclear Decision/effect_value/capability-mode provenance fixtures retired. New later-pass, mode and rollback regressions cover the sidecar contract; these are not unchanged ports.

## Stop boundary
All corrections committed. No push, merge, deployment, Mint operation, credentials access or subagent delegation occurred. No further implementation or verification will run under this request. A4 is source-implemented; its final full/release qualification is incomplete.
