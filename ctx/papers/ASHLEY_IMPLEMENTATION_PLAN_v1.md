# Ashley Implementation Plan v1: Survival, Growth Machinery, One Attention, Self-Change

**Status:** DRAFT for Alex's review. Once approved, the architect hands it to Manager as packets.
**Architect:** Claude Opus, 2026-10-01.
**Grounded at:** Ashley `main` `5996032`. Every file, function, table, constant and version below was read at that commit. Production facts are marked **UNKNOWN** until Phase 0 resolves them.
**Design sources:**
- `ASHLEY_PATCH_SELF_IMPROVEMENT_v0.1.md` (P1–P8);
- `ASHLEY_ATTENTION_AND_ORGANISM_MAP_v0.1.md` (Parts A and C);
- Alex's decisions of 2026-09-30 and 2026-10-01 (§0.3).

---

## 0. How to read and run this plan

### 0.1 Roles (as set in D-027 and D-029b, and as run in the Domus E2 work)

**Owner update, 2026-10-01 (packet A0):**
- This plan runs on **Codex on Manager's box**, Sol 6.1 light, with the CLI updated first; the box reaches Mint over Tailscale.
- **Grok Build is read/write for bots.** The reviewer is still never the author.
- The Command Code CLI (Muse Spark 1.3, xhigh) is available, and its assignment comes later.

- **Coder:** Grok Build, via Manager's bundle flow. Each packet is self-contained.
- **Reviewer:** a Codex CLI job (headless, the new CLI path), one per packet, in the J106 style:
  - it reviews the diff against the packet;
  - it runs fail-before at the base;
  - it gives `REVIEW_VERDICT`;
  - it never fixes.
- **Adjudication:** the architect decides on every review verdict and may override it with written reasons.
- **Alex:** approves deploys, credentials, capability modes, and every self-authored change set (§P5).
- **Commits:** Ashley's `main` is single-branch (D-029b). Commits go directly to `main`, and Auditor reviews after the fact any commit touching `apps/agent-service/`, `deploy/`, `config/` or `scripts/`. The repo is **public**, so nothing private goes into it: no model IDs in docs (AGENTS §5), no secrets, no Owner material.

### 0.2 Standing rules for every packet

- **Red first.** New tests fail at the base and pass at the tip. When an old version of a file is needed, use `git show HEAD:path > path`, never stash.
- **Migrations.**
  - The sidecar is at `COGNITIVE_SIDECAR_SCHEMA_VERSION = 45` (`core/cognitive-v021/types.ts:32`); schema strings live in `core/cognitive-v021/sidecar/schema.ts` and the step ladder in `core/cognitive-v021/sidecar/db.ts:~839`.
  - Nuclear is at `NUCLEAR_SUPPORTED_VERSION = 53` (`core/db.ts:168–169`); the step ladder is in `core/db.ts` (`ensureNuclearV5xSchema`).
  - **Each packet takes the next free version when it lands**, never a pre-assigned number. Fresh installs and upgrades both go through the ladder, and `core/cognition/schema-contract.ts` is updated in the same packet.
  - A table rebuild (e.g. extending a `CHECK`) uses a `migrate…ToVn(existing)` helper, as with `migrateConcernsToV24`.
- **The Thought schema fingerprint is pinned in at least three tests.** The last one was missed (commit e02a2a8). Any packet that touches `thought/output-contract.ts` must:
  - grep for the pinned constant (`semanticSchemaFingerprint` / `SCHEMA_FINGERPRINT` in `thought/*.test.ts`, `qualification/*.test.ts`, `model-fabric/deepseek-migration.test.ts`);
  - update every pin;
  - say so in its results.
- **Verification per packet:**
  - focused vitest files;
  - `npm run build:agent` (tsc);
  - `npm test --prefix apps/agent-service` (the full vitest suite) at candidate freeze;
  - `npm run test:current-release` for anything on the served path.
  - Docs-only packets: docs checks only (AGENTS §8).
- **Essence lines.** Every new module starts with a one-sentence essence comment (patch §7), and reviewers check the diff against it.
- **Deploys:**
  - Only on Alex's go, through `npm run start:ashley` (AGENTS §6).
  - From Phase 1 on, every deploy is preceded by a verified backup package (B1).
  - A schema migration is one-way, so its packet states the rollback SHA and the backup to restore.

### 0.3 Alex's decisions this plan implements

- **Repo and approval:**
  - Self-authored patches go to a **new private repo `XharvaK/Ashley-self`**, pushed by an operator courier. Ashley never holds Git credentials.
  - **Alex approves every change set.** The architect recommends only.
  - About **one patch a day**, on a separate budget.
- **Friction** counts explicit corrections plus disagreements Ashley notices herself.
- **Attention:**
  - **one attention system for all of Ashley**;
  - **mood modulates attention gently**;
  - **NIGHT is work-driven, with no time floor, generous**;
  - **switch directly, no shadow period**, protected by offline replay tests, a kill switch and a decision log.
- **Backups:** encrypted, **one push a day to Google Drive**.
- **Growth dimensions:** she names them, and Alex seeds a starting list.
- **Older modules (2026-10-01):**
  - **cognitive-graduation (C4): revive and port** into v021;
  - **learned-autonomy (C3): port** into v021 (reuse, don't reinvent);
  - **context-allocation: remove**;
  - **learning/revisions: remove**.

### 0.4 Phase map and order

| Phase | What | Depends on | Deploy? |
|---|---|---|---|
| **0** | Ground truth on Mint + source audits (read-only) | — | no |
| **1** | Break-glass backups (wire the existing `continuity/backup-package.ts`) | 0 | yes |
| **2** | Remove learning/revisions and context-allocation | 0, 1 | yes |
| **3** | Friction ledger, practice layer, senses | 1 | yes |
| **4** | Port C4 (graduation) and C3 (learned influences) into v021 | 0, 3 | yes |
| **5** | The thalamus: one attention system | 3 (senses), 4 (influences feed curiosity salience) | yes |
| **6** | Self-change pipeline (courier, Ashley-self, review loop, ladder) | 0, 3 | yes |
| **7** | Gap analysis (growth direction) | 3 | yes |
| **8** | Domus nucleus + Domus observation ingress + lineage-marked memory | 5, Domus plan Phase 6 | yes |
| later | Lifeboat model (P8) | — | — |

Phases 2, 3 and 6 can overlap once Phase 1 is live. Phase 5 is the largest.

---

## Phase 0: Ground truth (read-only; Codex on Mint via Manager's SSH route)

**G0.1 Production facts.** A report only; nothing is changed.
1. Mint HEAD, `nuclear.db` `user_version`, and sidecar `schema_version`.
2. **Sandbox and self-change:**
   - `capability_releases` rows and states for the sandbox and engineering capabilities, including `patch_export`;
   - whether Bubblewrap runs unprivileged on the reinstalled Mint;
   - the project-registry entry for `project-ashley` and its `exportDestinationCanonicalRoot` (read by `sandbox/patch-export-execution.ts:109`);
   - whether that folder exists and what's in it.
3. **Row counts** (counts only, never content) for:
   - C3 tables (from `core/learned-autonomy/migration-37.ts`);
   - C4 tables (`core/cognitive-graduation/migration-38.ts`);
   - `context_budget_policies`, `context_allocation_receipts`, `context_summary_projections`;
   - the legacy revision tables used by `core/learning/revisions.ts`;
   - `cognitive_maturation_contract_state` rows by `wave`.
4. **Served path:**
   - is `core/runtime.ts` (which imports `reflection/initiative.ts` and `change-proposal/store.ts`) reachable from `serve.ts` at runtime?
   - which endpoints of `server.ts` use `core/memory/episodes.ts` (`retrieveEpisodes`)?
5. **Inner-life settings:**
   - the effective `PERIODIC_COGNITION_ENABLED`, `ASHLEY_AFTERGLOW_ENABLED` and `PROACTIVE_CHECK_INTERVAL_MIN` (classified, not printed);
   - the last 7 days of afterglow, NIGHT and AWAKE runs from the `[cognitive-v021]` journal lines;
   - the bot's `[discord-bot] cognitive idle` lines.
6. **Backups:** whether `~/.composer-assistant/backups` exists on Mint, and the newest snapshot's age.

**G0.2 Source audits** (from the Awareness patterns; a report with file:line, no fixes):
- (a) **Coverage contract:** does any read of a conversation or evidence span (recall, `evidence/conversation-log.ts`, the afterglow row window, `memory/episodes.ts`) silently cap or drop rows *inside* the requested span? List every `LIMIT` on a span read and whether a continuation exists.
- (b) **One context path:** do the per-turn Thought input (`thought/input.ts`) and the inner-pass input (`initiative/agenda.ts`, `growth/night.ts`) assemble shared blocks through the same functions, or through divergent copies?

**Acceptance:** `G0_REPORT.md` with every item answered VERIFIED or UNKNOWN (with the reason). The architect turns the counts into the removal and port decisions in Phases 2 and 4.

---

## Phase 1: Break-glass backups (P6)

**What exists (VERIFIED):**
- `core/continuity/backup-package.ts` is an authenticated **three-store package** (nuclear, continuity, sidecar), AES-256-GCM with a scrypt-derived key.
- It takes snapshots in order and exposes `createDualBackupPackage` (:323), `verifyBackupPackage` (:450), `restoreVerifyPackage` (:466) and `restoreDualBackupPackage` (:760).
- `scripts/backup-memory.ps1` makes Windows-local `VACUUM INTO` snapshots and names `ASHLEY_BACKUP_TRANSFER_KEY`.
- **No production code calls the package.** It's a dormant organ, and this phase wires it up.

**Threat-model note:** Awareness uses public-key `age` so that the upload host can't decrypt. Mint *holds the live databases*, so a compromised Mint already exposes everything, and public-key encryption adds nothing there. What matters is that **Drive (off-site) only ever sees ciphertext** and that **the key survives Mint's loss**. The existing symmetric package does both, as long as the key is also kept off Mint. We reuse it; no new crypto.

**B1: The daily package job.**
- **New:** `apps/agent-service/src/scripts/backup-daily.ts`, compiled with the agent. It:
  1. opens the three stores read-only;
  2. calls `createDualBackupPackage` into `~/.composer-assistant/backups/pkg/<UTC stamp>.ashleybak`;
  3. **immediately** runs `verifyBackupPackage`;
  4. writes `~/.composer-assistant/backups/status.json` (`last_ok_ms`, `last_error`, `bytes`, `package_sha256`);
  5. keeps the last 7 local packages.
- It never raw-copies a live WAL database; the package does snapshots, per Lyra's WAL corruption finding.
- **New:** `deploy/linux-mint/systemd/ashley-backup.service` and `.timer` (daily, at a randomized minute).
- Upload: `rclone copy` of the newest package to the Drive remote `ashley-drive:AshleyBackups/`, then `rclone check`. `status.json` gains `last_upload_ok_ms`.
- **Retention on Drive:** 30 dailies + 12 monthlies, pruned by the job. It never deletes the only copy.
- **Owner-gated:**
  - Alex runs `rclone config` on Mint (a Google OAuth sign-in; agents never touch credentials);
  - Alex puts `ASHLEY_BACKUP_TRANSFER_KEY` (64 hex) into `~/.composer-assistant/.env`;
  - Alex stores a copy of the key in their password manager, plus a cold printed copy.
- **Tests:** vitest for the job's prune and status logic with a fake clock and a temp directory; the existing `backup-package` tests stay green.

**B2: The weekly restore drill.**
- **New:** `backup-drill.ts` plus a weekly timer.
- It downloads the newest Drive package into a temp directory, runs `restoreVerifyPackage`, and opens all three restored databases read-only.
- It checks `user_version`, the sidecar meta, and row counts of 5 core tables against the live databases (a tolerance for the day's growth).
- It writes `drill_ok_ms` into `status.json`, then deletes the temp directory.

**B3: Wiring into deploy.** `scripts/mint/remote-update.ps1` (the `start:ashley` path) runs `backup-daily` and refuses to migrate if the backup fails. It replaces the ad-hoc `~/ashley-backup-*` copies.

**Acceptance:**
- One real package is on Drive.
- A drill passes on Mint.
- `status.json` is fresh.
- The Phase 3 senses read `status.json` (the backup-age sense).

---

## Phase 2: Remove the two stale organs (Alex, 2026-10-01)

### R1: Remove `core/learning/revisions.ts`

**Live callers (VERIFIED):**
- `core/memory/episodes.ts:4` and `core/memory/forget.ts:14` import `reconcileUnsupportedRevisions`;
- tests in `core/memory/episodes.test.ts` and `core/relationship/c5-settlement.test.ts`.
- `server.ts:10` uses `core/memory/episodes.ts` (`retrieveEpisodes`), so this sits on the served path.
- The v021 revision engine (`cognitive-v021/growth/revisions.ts`) already handles forgetting itself: status `'forgotten'` at :737–754.

**Steps:**
1. **If G0.1 shows the legacy revision tables are empty:**
   - delete the two calls, `learning/revisions.ts` and its tests;
   - adapt `c5-settlement.test.ts`'s use of `listIdentityReviews` / `proposeRevision` to the v021 foundational-review API (`growth/revisions.ts` `FoundationalReview`), or delete that test if it only covered the legacy path.
2. **If they're not empty:** STOP and report. The architect decides whether to migrate the rows into `growth_revisions` or freeze them.
3. A new nuclear migration drops the legacy revision tables **only** after step 1, with `schema-contract.ts` updated.

**Acceptance:** `grep -r "learning/revisions"` returns nothing; build and the full suite are green.

### R2: Remove `core/context-allocation/`

**Facts (VERIFIED):**
- `migration-36.ts` creates `context_budget_policies`, `context_allocation_receipts` and `context_summary_projections`, **and** `cognitive_maturation_contract_state`. That last table is still read by C3/C4 `contract-state.ts` and by `core/cognition/schema-contract.ts:1016–1057`.
- The only other importer is the type `ContextBudgetMode` in `mistral-client.ts:137,160`.
- The `context_allocation_*_overflow` strings in `cognitive-v021/failure/`, `speech/infrastructure-notice.ts` and `thought/diagnostics.ts` are **failure vocabulary for context overflow**, not this module. **Keep them.**

**Steps:**
1. Move the `migration-36` step function into `core/cognition/` (migration history is immutable, so the step must still run on old databases).
2. Delete the rest of the module and its `schema.test.ts`.
3. Remove the `contextBudgetMode` field and its type from `mistral-client.ts`. If anything reads it, replace it with a local literal type; that reach is shown by grep.
4. A new nuclear migration drops the **three** context tables, if G0.1 shows them empty or unused. `cognitive_maturation_contract_state` **stays** until Phase 4 finishes the C3/C4 ports.
5. Update `schema-contract.ts`.

**Acceptance:** no import of `context-allocation`; build and the full suite are green; the schema-contract tests are updated and green.

---

## Phase 3: Friction, practice, senses (P1–P3)

### F1: The friction ledger

**Essence:** *the Host records that friction happened; only Thought says what it means.*

**Storage.** Sidecar, next version, `friction_events`:
```
friction_id TEXT PK, kind TEXT CHECK (kind IN ('owner_correction','effect_failed','outcome_unknown',
  'expectation_missed','budget_refused','delivery_failed','self_reported')),
occurred_at_ms INTEGER, evidence_refs_json TEXT, note TEXT (≤300), cycle_id TEXT, data_classification TEXT
```
Index on `(kind, occurred_at_ms)`.

**Recorders.** Host facts only. Each is a small call next to existing terminal truth:

| Kind | Where it's recorded |
|---|---|
| `delivery_failed` | the terminal failure in the speech outbox / delivery pump (`speech/outbox.ts`, `core/delivery/`) |
| `outcome_unknown` | `effect/in-flight.ts` reconciliation to `outcome_unknown` (types.ts:757) |
| `effect_failed` | the dispatch terminal `failed` (types.ts:744) |
| `expectation_missed` | `growth/expectations.ts`, when a check with outcome `missed` is recorded |
| `budget_refused` | `private-budget/ledger.ts` `reservePrivateThought`, on refusal `capacity_exhausted` (types.ts:250) |
| `owner_correction` / `self_reported` | from Thought only (below) |

**Thought output.** `growthSchema` in `thought/output-contract.ts:351` gains `friction: [{kind: 'owner_correction'|'self_reported', note, refs}]`, at most 2 per settlement.
- Guidance text, added to the growth guidance at :778: *"when Alex corrected you, or you notice you disagreed or it went worse than it should have, note it; your reading, in your words."* This is Alex's decision that friction includes her own reading.
- Applied in `thought/aftermath.ts` next to `recordGrowth` (:96).

**Thought input.** `growthForThought` (`growth/growth.ts:81`) gains `friction: {last7d: {kind: count}, recent: [≤5 {kind, note, atMs}]}`.

**Tests:** each recorder writes exactly one row on its terminal path and none on success; secret-classified text never enters `note`; the schema fingerprint pins are updated.

### F2: The practice layer ("how I work")

**Essence:** *practices are her own procedural notes, earned from evidence, cheap to revert.*

**Changes to `growth/revisions.ts`:**
- `REVISION_LAYERS` (:40) adds `'practice'`.
- `REVISION_THRESHOLDS` (:55) gains `practice: { evidence: 2, passes: 1, spanMs: 0, delayMs: 0 }`, **plus** a rule that one origin plus Ashley's `affirm` in a later pass also applies (reusing `recordRevisionPositions`, :376).
- Practices are **not** foundational: no Owner approval, and Alex can revert them.
- Evidence refs may cite `friction:<id>` and checked expectations. Friction counts by origin, like any other evidence.
- A new `listCurrentPractices(db, limit=12)`, like `listCurrentOpinions` (:667).

**Migration.** Sidecar, next version. **Rebuild `growth_revisions`** (the `CHECK` at `sidecar/schema.ts:1507` must include `'practice'`) with a `migrateGrowthRevisionsToVn` helper: copy, swap, re-index.

**Thought.**
- `ThoughtGrowth` gains `practices: [{revisionId, text, heldSinceMs}]`.
- The guidance line says: *"growth.practices are how you've learned to work; follow them unless you have a reason; propose practice revisions from friction and lessons."*

**Alex's view.**
- Owner-only endpoints: `GET /growth/practices` and `POST /growth/practices/:id/revert` (status `reverted`), in `server.ts` next to the existing owner growth routes (`/growth/snapshots` from A8).
- The Discord `/identity` command (`apps/discord-bot/src/commands/identity.ts`) gains a "practices" view with a revert button. Afterwards, run `npm run deploy-commands --prefix apps/discord-bot` on Mint.

### F3: Senses, with the "no"

**Essence:** *a sense states the truth at proportionate volume and then stops; a reasoned no quiets it.*

**New:** `cognitive-v021/senses/senses.ts`. It computes a bounded block (≤8 lines) from Host facts:

| Sense | From |
|---|---|
| friction (7 days, top kind) | F1 |
| open expectations due | `growth/expectations.ts` |
| stale concerns | `concerns/occupancy.ts` |
| delivery backlog | the speech outbox |
| budget left this hour | `private-budget/ledger.ts` `getPrivateBudgetProjection` |
| backup age | `~/.composer-assistant/backups/status.json` (Phase 1) |
| self-change queue | Phase 6 |

**Declines.**
- Settlement gains `senses.decline: [{sense, rationale, untilMs?}]`, stored in the sidecar table `sense_declines`.
- A declined sense is hidden until its value crosses the next band **or** 7 days pass. Then it re-raises once: "still declining?".
- Shown in `ThoughtInput` as `senses` (Owner-private passes only, like `growth`).

**Tests:** band crossings; a decline hides the sense, and it re-raises after the band or 7 days; no sense line ever contains message text.

**Phase 3 acceptance:**
- The full suite is green.
- The pins are updated.
- After deploy, Alex sees practices in `/identity`, and a real friction row appears within a day of normal use.

---

## Phase 4: Port the older learning organs into v021 (Alex, 2026-10-01)

Both are **ports that reuse the existing logic**, re-homed into the sidecar and wired into v021 Thought. The old `core/` modules are deleted at the end of each port. Row data moves only if G0.1 shows rows, and the architect decides that per the counts.

### C4: cognitive-graduation, revived and ported

**What it is (VERIFIED, `core/cognitive-graduation/`):**
- predictions (`judgmentText`, `judgmentClass`, `expectedObservableOutcome`, `expectedHorizon`, evidence refs, strength);
- outcome observations (`receipt_backed` / `missing` / `outcome_unknown`);
- adjudications (disposition `confirmed` / `contradicted` / `partial_support` / `unresolved`, authority `deterministic_compare` / `ashley_thought_reflection` / `owner_confirmed`, correction classes);
- **calibration adjustments**: `increase_caution` / `decrease_caution` / `narrow_scope` / `request_more_evidence` / `hold_for_review`, with the lifecycle `proposed → admitted → eligible_for_future_thought → demoted/expired/contradicted/rolled_back`;
- modes `observe` / `dark_apply` / `apply`.

v021's `growth/expectations.ts` is explicitly *"a light port of c4"*. The port completes it.

**The port (`cognitive-v021/graduation/`):**
1. **Expectations become full predictions.**
   - `growth.expectations[]` in the output contract gains optional `judgmentClass` (≤40), `observable` (≤200) and `horizonHours` (1–720).
   - The existing `expectations` table gains the matching columns (sidecar migration).
   - Existing expectations stay valid, with the new fields null.
2. **Observations.**
   - A new sidecar `graduation_observations`, ported from the C4 observation schema in `migration-38.ts`, keyed to `expectation_id`.
   - The Host records **receipt-backed** observations where a deterministic comparator exists:
     - a delivery receipt, for "Alex will see it";
     - an owner reply within the horizon (a fact, not a judgment);
     - later, Domus claim-ladder verdicts.
   - Otherwise `missing` at the horizon.
3. **Adjudications.**
   - A new `graduation_adjudications`, ported.
   - Authority is `deterministic_compare` when a comparator decides, `ashley_thought_reflection` when her existing `expectationChecks` decides, or `owner_confirmed`.
   - `supersedesAdjudicationId` and correction classes are kept.
4. **Calibration.**
   - A new `graduation_calibration`, with the C4 `calibration.ts` lifecycle ported (`recordThoughtCalibrationAdjustment`, `listEligibleThoughtCalibration`, `rollbackCognitiveGraduation`).
   - The Host **proposes** an adjustment per `judgmentClass` when the admitted adjudications cross a bound. Proposed rule: ≥4 adjudications in 30 days, with contradicted/(confirmed+contradicted) ≥ 0.5 → `increase_caution`, or ≤ 0.15 → `decrease_caution`. The numbers are declared constants, reviewable.
   - **Thought admits or declines** each proposal in a later pass (a new `growth.calibrationPositions`). Admitted ones reach `ThoughtGrowth.calibration` as eligible lines ("in *<class>* you've been wrong often; hold these more loosely").
   - Owner rollback goes through an endpoint.
5. **Mode.**
   - The capability starts at `observe`: everything is recorded, and nothing is shown to Thought.
   - Alex flips it to `apply` after reading a week of data. That's an Owner decision, recorded in the sidecar (the ported `contract-state`).
6. **Retire the old module.**
   - Re-point the `server.ts` diagnostics (`getCognitiveGraduationDiagnostics`, :85, :1241) to the port.
   - Delete `core/cognitive-graduation/`.
   - The nuclear tables are dropped in a later migration after the architect confirms the rows were migrated or were empty.

### C3: learned-autonomy, ported

**What it is (VERIFIED, `core/learned-autonomy/`):**
- **Learned influences** (kind `interest`), each with:
  - subject facet, semantic owner, lineage kind (`explicit_seed` / `owner_designated` / `observed_overlap` / `ashley_native`);
  - influence class I0–I3;
  - evidence (assertions);
  - a lifecycle: `proposed → admitted_to_review → accepted/declined`, contradiction and demotion states, adjudicator `thought` or `natural_owner`;
  - modes `observe` / `dark_apply` / `apply`;
  - **choice receipts** recording each time an influence changed a `curiosity_rank`, `motivation_admission` or `thought_selection` decision.
- Live callers: `core/curiosity/reads.ts:8–10` and `core/relationship/projections.ts:9` (the latter is reached from v021 through `thought/domain-pointers.ts:7`).

**The port (`cognitive-v021/influences/`):**
1. **Sidecar tables** ported from `migration-37.ts`: `learned_influences`, `learned_influence_evidence`, `learned_choice_receipts`.
2. **The v021 source of candidates is the interest graph.** When a branch in `memory/interests.ts` has grown from ≥3 lived origins, the Host proposes a learned influence (lineage `ashley_native`). Thought accepts or declines it in a pass (`growth.influencePositions`). Owner-designated influences are available through an endpoint.
3. **Where influences act (and receipts are written):**
   - (a) **the thalamus** external nucleus and boredom nucleus, as a salience gain on matching feed items and agenda items (Phase 5; `curiosity_rank`);
   - (b) own-time agenda ordering in `initiative/agenda.ts` (`thought_selection`);
   - (c) the existing callers `core/curiosity/reads.ts` and `relationship/projections.ts`, re-pointed to the port.
4. **Mode:** starts at `observe` (receipts record what *would* have changed). Alex moves it to `dark_apply` or `apply`, as with C4.
5. **Retire the old module:** delete `core/learned-autonomy/`, and re-point the `server.ts` imports (:84, :1174–1220) and `assertC3ContractCompatible`.

**Then retire `cognitive_maturation_contract_state`**, once both ports have their own sidecar contract state, in the nuclear migration that drops the C3/C4 tables.

**Phase 4 acceptance:**
- Ported logic is tested with the **original C3/C4 tests ported**, not rewritten.
- A mode-gate test covers `observe` (nothing shown to Thought).
- The full suite and pins are green.
- G0.1 counts decide row migration.

---

## Phase 5: The thalamus: one attention system (organism paper, Part A)

**Essence:** *nuclei propose, one arbiter decides when; the Host never decides what.*

### T0: What it replaces (VERIFIED: nine clocks, not eight)

1. The afterglow timers (`initiative/afterglow.ts:38–44`).
2. The NIGHT slot (`initiative/night.ts:36–43`).
3. AWAKE, 3 h ± 20 min (`initiative/awake.ts:35–38`).
4. The P1 periodic schedule (`initiative/periodic-schedule.ts`, already disabled: `periodicCognitionEnabled: false` at `agent.ts:204`).
5. The subscription loop (`observation/subscriptions.ts`).
6. Future triggers (`initiative/future-triggers.ts` `fireDueTriggers`, :421).
7. Commitment opportunities (`relationship/commitment-admission.ts`).
8. The frontier coordinator.
9. **The Discord bot's own idle timer.** `apps/discord-bot/src/initiative/scheduler.ts` `startCognitiveIdleScheduler` calls `POST /initiative/idle` (`server.ts:2861`) → `agent.tickCognitiveIdle` → `tickIdleOpportunity` every `PROACTIVE_CHECK_INTERVAL_MIN` (default 60, `config/env.example:98`). **Her reminders, commitments and feeds are driven from another process's clock.**

The integration point is `pollInnerLife` in `serve.ts:~599–631`: afterglow, then NIGHT, then AWAKE, polled every `AFTERGLOW_POLL_MS`.

### T1: Pure core (`cognitive-v021/thalamus/core.ts`)

- **No I/O and no clock:** `(state, candidates[], now, context) → { decision: fire(passType, bundle) | none, state' }`.
- **Candidate:** `{source, salience, class: ALWAYS_THROUGH|PRESSURE|OPPORTUNISTIC, coalesceKey, deadlineMs?, passType, refs[]}`.
- **Threshold:** `θ(t) = θ0 × fatigue(spentFractionToday) × circadian(hour) × mood(energy, tension)`.
  - Mood is **gentle**: within ±15%, per Alex. Tension lowers θ for the social nucleus only.
- **Habituation** per `coalesceKey` (α, τ_rec), a novelty bonus, a per-nucleus refractory, coalescing by `passType` compatibility, and bounded per-nucleus gains (0.5×–2×).
- **Tests:** property tests with a fake clock.
  - Alex's messages are always ALWAYS_THROUGH, and the thalamus never delays them: they keep their existing inbox path and never pass through the arbiter.
  - The afterglow coverage deadline fires before any row leaves the 40-row window.
  - Commitments fire at their due time.
  - Nothing fires while a live conversation holds the cognition claim, except ALWAYS_THROUGH.

### T2: The nuclei (`cognitive-v021/thalamus/nuclei/*.ts`)

Each is a deterministic adapter over **existing** state:

| Nucleus | Reads | Salience rule |
|---|---|---|
| reflective | the afterglow watermark (the existing row-range coverage) | unreflected rows × time since the last message × her last appraisal magnitude; ALWAYS_THROUGH at the coverage edge |
| sleep | **work since the last NIGHT**: new episodes, memories formed (`memory/strength.ts` formation), conversation rows, open revisions, expectations to settle | S (work) × C (the learned quiet hour, `night.ts` learning kept); **no time floor**, generous θ |
| prospective | `future-triggers` due rows; commitment opportunities; **condition watches** (T3) | ALWAYS_THROUGH at due; watches per their action |
| external | subscription items (`observation/subscriptions.ts`) | novelty × interest-branch match (`memory/interests.ts`) × learned-influence gain (Phase 4 C3) × habituation per feed |
| boredom | time since the last own-time pass; mood energy × openness; agenda size (`initiative/agenda.ts`) | rises; resets on a pass; rises more slowly after a recorded "resting" |
| interoceptive | senses (Phase 3 F3) with declines | a wake only on a band crossing that wasn't declined |
| social (contacts) | social activation (`social/*`) | kept as is behind its fuse; a salience wrapper only |
| domus | Phase 8 | — |

### T3: Her attention set and "worth it?"

- **Output contract** (`thought/output-contract.ts`): a new top-level optional `attention`:
  ```
  attention: { watch?: [{ source, kind, subject?, predicate: eq|lt|gt|enters|leaves|changes|posts_about,
                          value?, action: wake|wake_urgent|suppress|quiet_until, expiresAtMs?, note }],   // ≤ 4 per settlement, ≤ 16 live
               wakeWorth?: 'yes'|'no'|'sooner'|'later',
               resting?: boolean }
  ```
- Guidance text: the watch-list is shown back every turn, and `suppress` can't mute ALWAYS_THROUGH.
- **Sidecar tables** (next version):
  - `attention_watches`;
  - `thalamus_state` (per-nucleus gain, habituation, boredom and sleep accumulators);
  - `thalamus_decisions`: the decision log, one row per candidate and decision, with a 30-day retention.
- **Input:** `ThoughtInput.attention = { watching: [...], wokeBecause: {source, refs}, alsoOnYourMind: [...] }`.

### T4: Integration and the direct switch (Alex: no shadow)

- `serve.ts` `pollInnerLife` calls `thalamus.tick(now)`. The arbiter picks the pass; the existing `tickCognitiveAfterglow` / `tickCognitiveNight` / `tickCognitiveAwake` bodies run as **pass executors**, with their contracts unchanged. Their own timing checks are bypassed when the arbiter fires them.
- **The idle tick moves into agent-service.**
  - The thalamus calls `tickIdleOpportunity` for prospective and external candidates.
  - `apps/discord-bot` stops calling `startCognitiveIdleScheduler` (`client.ts:18`).
  - `POST /initiative/idle` stays for manual use.
  - `/proactive` status shows the thalamus instead.
- **Kill switch:** `ASHLEY_THALAMUS_ENABLED` (default `true` after release). `false` restores the exact old paths, including re-enabling the bot scheduler through the status endpoint it already polls.
- **Offline replay before release:** `scripts/thalamus/replay.mjs` runs over a copy of the production sidecar (read-only) and the bot and agent journal lines from G0.1. It asserts the T1 invariants over the real last-N-days history and reports the wake-count delta per nucleus. That's a test, not a waiting period.
- **Alex's surface:** `/attention` (bot) or a `/status` section: live watches, gains, the last 20 decisions ("woke for… / held because…").

### T5: Learning

`wakeWorth` gives a bounded EMA update of the nucleus gain and the coalesce-family habituation (§A7 of the organism paper). The gains are shown to her as a sense and to Alex in `/attention`. The TGL-style learned trigger is **later**, and replay-tested before any switch.

**Phase 5 acceptance:**
- Pure-core property tests pass.
- The replay report is reviewed by the architect.
- The full suite, `test:current-release` and pins are green.
- After deploy, the first 48 h of decision log are read by the architect: every Alex message went through, and afterglow coverage is intact.

---

## Phase 6: The self-change pipeline (P4 and the §5 ladder)

**What exists (VERIFIED):**
- The proposal-only improvement loop, commit f2fc825: `sandbox/v2-execution.ts` `executeCandidateAuthorshipV2` / `executeCandidateVerificationV2`, `sandbox/changeset-store.ts`, and `sandbox/patch-export-execution.ts` `executePatchExportV2`. The last one copies a sealed patch to `exportDestinationCanonicalRoot` and doesn't apply, commit or deploy.
- Its production activation state is **UNKNOWN** (G0.1).

**S1: Motive.**
- A friction pattern (F1: the same kind ≥3 times in 7 days) or a practice she proposes can become a **self-change concern**. She opens it; the Host never does.
- She works it through the existing M3/M4/M5 operations in the sandbox.
- **Budget:** a second private-budget policy `ashley.self_change.v1`, a 24 h window with a declared call limit (proposed 20 calls/day, i.e. about one change set). It's separate from `ashley.private_thought.v1` (12/h, `private-budget/ledger.ts:12–13`), so it never starves conversation.

**S2: The courier (operator tooling, not Ashley's capability).**
- **New:** `deploy/linux-mint/self-courier.sh` plus `ashley-self-courier.service`/`.timer` (every 15 min).
- For each new sealed patch in the export root, with a sidecar metadata JSON (change-set id, rationale, friction refs, M4 receipt id):
  1. `git clone --depth 50` of `XharvaK/Ashley-self`, using a **deploy key** scoped to that repo only;
  2. check out the base commit recorded in the change set;
  3. `git apply --check`, then `git apply`;
  4. commit with a structured message (rationale, friction refs, M4 receipt, base SHA);
  5. push branch `self/<changeset-id>`.
- A manifest line is written to `~/.composer-assistant/self-change/courier.jsonl`.
- **No PR creation** (a deploy key can't create PRs). Auditor lists the branches.
- It never touches the public repo.
- **Owner-gated:** Alex creates the private repo `Ashley-self` (initialized as a mirror of `main`) and the deploy key.
- The courier keeps `Ashley-self/main` in sync with public `main` (a fast-forward mirror push), so bases stay current.

**S3: Review loop.**
1. Auditor's daily routine reads the new `self/*` branches and writes `outbox/SELF_REVIEW_<date>.md` (BLOCKING / NONBLOCKING / NOTE per change set).
2. Manager forwards it to the architect's inbox.
3. The architect writes a recommendation (APPROVE / CHANGES / REJECT, with reasons).
4. **Alex decides.**
5. On APPROVE, Alex merges the branch into public `main` by cherry-pick (or asks the architect to, as a one-off). The normal deploy happens on Alex's go.
6. **The result goes back to Ashley.** Manager, via SSH, writes `~/.composer-assistant/self-change/results/<changeset-id>.json` (`{decision, reviewer_notes, alex_note?}`). A new ingress poller in agent-service turns it into an inbox event of new kind `self_change_result`: add it to `triggerKindForInbox` (`cycle/inbox.ts:155`) as its own `CycleTriggerKind`, wake it through the thalamus prospective nucleus, and send it to a private pass.
7. Her reading of the result is growth (a lesson, a practice, a friction row).

**S4: The ladder.**
- Sidecar `self_change_ladder` (level, history).
- The level starts at **L1** and changes only by Alex's command.
- Any revert or BLOCKING drops it one level, recorded.
- It's shown to her as a sense.
- **Auto-merge levels (L2/L3) are never implemented in this plan.** They need Alex to delegate first (per Alex's "approve everything").

**Phase 6 acceptance:**
- One real self-authored change set goes end to end: sandbox → export → courier branch → Auditor → architect → Alex → result event → her pass.
- Evidence is in the orchestra outbox.

---

## Phase 7: Gap analysis (P7)

- NIGHT, on weekly passes (`growth/night.ts` weekly path, `WEEKLY_NARRATIVE_INTERVAL_MS`), gains `night.gaps: { dimensions: [{id?, name, score 0–5, note}], choose?: dimensionId }`.
- Sidecar `growth_dimensions` (add, rename, retire, history) and `growth_gap_scores`.
- **Alex seeds** the starting list via an owner endpoint and `/identity`.
- She may add, rename or retire a dimension, with the change recorded and shown to Alex.
- The chosen gap becomes an agenda item for own time and a possible self-change motive (S1).

---

## Phase 8: Domus in Ashley (after Domus plan Phase 6 is ready)

- **Ingress:** a new authenticated route `POST /domus/observation` in `server.ts`, admitting to the inbox as the new kind `domus_notification` (Domus-helper token, Tailscale only). The payload is the helper's notification (Domus plan §5): percepts, portrait facts, lineage class.
- **Domus nucleus** (Phase 5 T2): ALWAYS_THROUGH and salience come from the helper. The embodiment budget is its **own policy** (`ashley.embodiment.v1`, the number is Alex's; E3-B1), with its own fatigue curve.
- **Portrait:** `ThoughtInput.domus`, a present-tense block rendered from facts only (the D3 rules; no Host meaning).
- **Memory with lineage:**
  - episodes and memories formed in a Domus pass carry `channel = 'domus:<world>'` and `lineage_class`;
  - a sidecar migration adds the columns to episodes and assertions;
  - when the helper later reports that a span was **abandoned** (the ledger reclassifies), the Host marks those rows `lineage_class = 'undone'` (Alex: keep, marked).
  - Recall shows the mark.
- **Boundary test (E3 prerequisite):** Domus ingestion calls no affect, mind-state or relationship writers. It's a test that fails if any of those functions is reachable from the route.

---

## Owner-gated actions (the complete list)

| # | Action | Phase |
|---|---|---|
| 1 | `rclone config` for Google Drive on Mint; store `ASHLEY_BACKUP_TRANSFER_KEY` in `.env`, in your password manager, and in a cold copy | 1 |
| 2 | Every production deploy (`npm run start:ashley`) | 1–8 |
| 3 | Decide on row migration vs drop for legacy tables (from G0.1 counts, on the architect's recommendation) | 2, 4 |
| 4 | Flip the C4 and C3 modes from `observe` to `apply` | 4 |
| 5 | Create the private repo `XharvaK/Ashley-self` + a deploy key; put the key on Mint | 6 |
| 6 | Approve or reject every self-authored change set; merge approved ones | 6 |
| 7 | Seed the growth dimensions | 7 |
| 8 | Set the embodiment budget number (E3-B1) | 8 |
| 9 | `npm run deploy-commands` in the bot after new commands | 3, 5, 7 |

## Packet list for Manager (in order)

| Packet | Content | Coder | Reviewer |
|---|---|---|---|
| A-G0 | Phase 0 report | Codex (read-only, Mint) | architect |
| A-B1/B2/B3 | backups | Grok | Codex |
| A-R1, A-R2 | removals | Grok | Codex |
| A-F1, A-F2, A-F3 | friction, practice, senses | Grok (three packets) | Codex |
| A-C4, A-C3 | ports | Grok (two packets) | Codex |
| A-T1…T5 | thalamus (core → nuclei → contract → integration → learning) | Grok | Codex; the architect reads the replay |
| A-S1…S4 | self-change (S2 courier includes a deploy script review) | Grok | Codex |
| A-G7 | gap analysis | Grok | Codex |
| A-D8 | Domus in Ashley | Grok | Codex |

Each packet file will carry: goal, exact files, tests (red-first), verification commands, STOP conditions, a results format (R1), and the no-go list (no deploy, no Mint mutation, no Discord, no credentials, no model IDs in the repo).
