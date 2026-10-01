VERDICT: ACCEPT_WITH_NOTES

# GS1R independent review of GS1 (2ea3ef7..af90ce6)

Scope reviewed: exactly `2ea3ef7..af90ce6` (0ef8dd0 Build 1 taint carrier,
f1f3833 Build 2 labels + sidecar v49, af90ce6 Build 3 projection audit).
41 files, +296/-67. Clone root: /workspace/wt/gs1-review, detached at af90ce6.
Brief: `.rr/GS1_BRIEF.md`. Author claims: `.rr/GS1_CODER_REPORT.md`.
Prior unverified material: `.rr/A3g_working.diff` (used only as allowed input).

## 1. Requirements table (brief DO 1-6 + DON'T)

| Req | Verdict | Evidence |
|---|---|---|
| DO1 taint from labels only, essence comment verbatim at computation | MET | `thought/input.ts:157-166` (`thoughtInputContainsSecret` checks only `dataClassification === "secret"` / `secretOmitted === true`, recurses into objects, never touches scalar content); `thought/projection-allocator/allocator.ts:1021-1025` carries the verbatim `// the Host records only that secret evidence was present; it never reads or judges it.` and computes `sawSecret` over included projection + included compact retrieval provenance only. No secret content read/logged/hashed/compared anywhere on this path (rg for content reads beside the label check returns nothing). |
| DO1 carrier reaches recordSettlementAftermath on live AND recovery paths | MET | Non-enumerable `sawSecret` on allocated projection (`allocator.ts:1025`) -> `run.ts:1608` copies to local -> `run.ts:1427` stamps `ThoughtSettlementDraft.sawSecret` -> `settlement/publish.ts:551-556` persists whole draft as `settlements.payload_json` (`json({...settlement...})`) -> `aftermath.ts:75` reads `payload_json` on both `recordSettlementAftermath` (live call) and `recoverSettlementAftermath` loop (`aftermath.ts:135-148`) which delegates to the same function. Validation (`settlement/validate.ts:60-73,326-335`) does not strip `sawSecret` (not in PUBLISHED_ONLY_FIELDS). |
| DO1 legacy payloads fail closed to never_public | MET | `thought/aftermath.ts:89`: `settlement.sawSecret === false ? "ordinary" : "never_public"`. Absent/undefined/malformed flag -> never_public on both publication and recovery (comment at :88 says so). |
| DO2 every Thought-authored growth/night/journal write uses sawSecret ? never_public : ordinary; Host friction unchanged | MET with note | `aftermath.ts:89-119` threads one `dataClassification` into `recordJournalEntry`, `recordSenseDeclines`, `recordGrowth`, `recordNight`. Growth threads it to appraisal/expectations/checks/positions/proposals (`growth.ts:175-196`, `expectations.ts:158-170`, `revisions.ts:440-525`); journal takes max with reads (`journal.ts:156`); night/diary/narrative take it directly (`night.ts:212-245`); senses take it (`senses.ts:87`). Update paths never downgrade `secret` (`expectations.ts:167-170`, `revisions.ts:522-525` CASE WHEN). Host friction unchanged: `friction.ts` has no GS1 diff; `recordHostFriction` still hard-codes never_public note=kind (`friction.ts:14-17`); brief asked Host-recorded friction classification stay as-is. NOTE: Thought-authored `claim.friction` rows now also inherit the taint via `growth.ts:175` (`recordFriction ... dataClassification: input.dataClassification`) — consistent with "every Thought-authored write", but the brief's wording ("Host-recorded friction stays as it is") is ambiguous here; the redacted-a3 friction test asserts the cycle friction row gets the expected label, and no STOP is triggered. |
| DO3 v49 sense_declines.data_classification with right CHECK; every pin updated; fresh+upgrade tests | MET | `sidecar/schema.ts:1730-1735` V49 adds `TEXT NOT NULL DEFAULT 'ordinary' CHECK (... IN ('ordinary','sensitive','never_public','secret'))` matching the other tables' set. Chain: `db.ts:189-195` migrateSidecarToV49 (tolerates retained column), fresh path `:819`, upgrade path `:880`. `types.ts:32` pin 48->49; all `toBe(48)` pins in sidecar __tests__ updated to 49 (v18/v19/v20/v21/v23/v25/v27/v28x2/v30/v31/v32/v34/v35/v36/v38/v39/v40/v43/v44/v45); `schema-contract.ts:1538` adds v49 column requirement. `schema-v49-migration.test.ts` covers fresh + upgrade, defaults, legal labels, rejection, preservation, repeat open. Verified 2/2 pass at tip. |
| DO4 projections: list filters, fix = 'ordinary' feeding owner/Owner, non-owner must exclude never_public | MET | No `= 'ordinary'`-style audience filter found in growth/journal/night/practice/sense reads (rg returns empty). All owner/Thought reads use `!= 'secret'` / `<> 'secret'` so never_public is retained: friction.ts:21, expectations.ts:193/202, revisions.ts:224/684/692/700/787, night.ts:256/265, journal.ts:189, vectors.ts:84, plus practices/opinions/applied lists (revisions.ts:682-700). Only filter change in range: `senses.ts:66` `WHERE sense = ?` -> `WHERE sense = ? AND data_classification != 'secret'` (see byte-identical section). |
| DO5a secret evidence row -> all growth/night/decline never_public; else ordinary | MET | `aftermath.test.ts:96-129` parametrised true/false/undefined x live/recovery asserts all 7 tables get expected label; `run.test.ts:2798-2815` live carrier test persists labels and checks expectations + sense_declines. |
| DO5b secretOmitted also taints | MET | `allocator.test.ts:3342-3355` "omitted secret" case (ordinary + secretOmitted=true -> sawSecret true); `run.test.ts` ("ordinary", omitted=true -> true). |
| DO5c recovery path same label as live | MET | Aftermath test loops `recovery in [false, true]` with identical assertions. |
| DO5d next owner_private pass still sees never_public rows | MET | `input.test.ts:986-1010` re-entry test: never_public expectation + practice visible in owner_private input; senses decline suppresses (expected: decline active so line absent); owner_dm/dm/room get no growth/senses/journal. |
| DO5e non-owner surface excludes them | MET (conditional, matches brief) | No non-owner surface reading these tables found (see audience table). Boundary tests in input.test.ts cover owner_dm/dm/room exclusion. |
| DO5f v49 fresh + upgrade with pins | MET | schema-v49-migration.test.ts 2/2 pass at tip; red at parent confirmed. |
| DO6 commit per green step with prefix | MET | `git log --oneline 2ea3ef7..HEAD` lists exactly 3 commits, all `feat(GS1):` by the specified author. |
| DON'T: no settlement authority / admission / Thought-visible change | MET | Publish/validate/admission untouched (no diff in settlement/, cycle/admission); wire output excludes sawSecret (non-enumerable + `JSON.stringify(projected)` assertion in allocator test); projection outputs for ordinary/never_public unchanged (see byte-identical). |
| DON'T: labels only, never content | MET | See DO1. `detectCredentialShape(rationale)` in senses/friction is pre-existing content-shape redaction, unchanged by GS1 except carried rationale string; no secret-content comparison drives the taint. |
| DON'T: friction Host classification untouched | MET | `git diff ... -- growth/friction.ts` empty. |
| DON'T: no network/installs/push/deploy/other worktrees by candidate | MET | No such changes in range; worktrees used are /tmp read-only parents for red-first only. |
| DON'T: slices <=150 lines | N/A (reviewer-side; this review used rg + slices) | - |

## 2. Audience-safety table

Reader/projection functions all use `!= 'secret'` (never_public retained for
owner_private Thought). Non-owner callers: none found for these tables.

| Reader | file:line | Audience | Carries never_public? |
|---|---|---|---|
| growthForThought (opinions/revisions/expectations/lessons/practices/mood/diary/narrative/friction) | growth/growth.ts:86-128 via friction.ts:21, expectations.ts:193/202, revisions.ts:682-700/787, night.ts:254-270, journal path | owner_private Thought only (`run.ts:3333-3334` gates `effectiveThoughtAudience.kind === "owner_private" && !externalCycle`; `input.ts:1148-1149,1207-1209` include growth/senses/journal only for owner_private) | YES (intended; owner_private still gets them back) |
| sensesForThought | senses/senses.ts:63-80 | owner_private Thought only (same run.ts:3334 gate; input assembly omits for owner_dm/external/room) | YES for never_public (intended); NEW: `secret` declines neither suppress nor mutate (filter at senses.ts:66) |
| journalForThought / listRecentJournal | initiative/journal.ts:189/207 | owner_private Thought (`input.ts:1148-1149`); Owner memory view via commands.ts | YES (owner surfaces) |
| listCurrentPractices -> GET /growth/practices | revisions.ts:787; server.ts:2464-2467 | Owner only (`requireOwner`) | YES (Owner surface, allowed) |
| listFoundationalReviews -> GET /growth/identity/reviews | revisions.ts:723ff; server.ts:2453-2460 | Owner only (`requireOwner`) | YES (Owner surface, allowed) |
| listPersonaSnapshots -> GET /growth/snapshots | snapshots.ts:68-78; server.ts:2472ff | Owner only (`requireOwner`) | YES (Owner surface, allowed; snapshot embeds opinions/narrative text) |
| getV021MemorySummary -> GET /memory/summary | commands.ts:282-345; server.ts:2431-2440 | Owner only (`requireOwner`); `include_private` flag governs sensitive, never_public retained in both modes | YES (Owner surface, allowed) |
| Discord memory/identity/practice commands | discord-bot/src/commands/memory.ts:11-57; agent-client.ts:624/764/955-963 | Owner only (`client.ts:84-143` isOwner gate; agent-client always sends `config.ownerId`) | YES via Owner API (allowed) |
| Observer exporter | apps/observer-exporter/src/* | No direct reads of growth/night/journal/sense_declines/mood/expectation/revision tables (rg finds only unrelated "revision" bundle words) | NO |
| Room / external-DM / owner_dm input assembly | thought/input.ts:218-306,1148-1209 | Non-owner audiences get no growth/senses/activityJournal | NO (structurally omitted) |
| HTTP non-owner routes | server.ts (all /memory/summary, /growth/* behind requireOwner) | Non-owner has no route to these tables | NO |

Coder's "no non-owner surface" claim: CONFIRMED by independent rg over
agent-service/src, discord-bot/src, observer-exporter/src and server.ts route
guards. No BLOCKING audience finding.

## 3. Byte-identical assessment (DON'T 1)

- `senses.ts:66`: `WHERE sense = ?` -> `WHERE sense = ? AND data_classification != 'secret'`.
  Reachable stored values after GS1: ordinary / never_public (aftermath writes
  only these two; `recordSenseDeclines` defaults `?? "ordinary"`). No code path
  writes `secret` into sense_declines (only never_public/ordinary from GS1;
  pre-existing rows predate the column -> default ordinary). Hence for all
  reachable data the added predicate is a tautology: ordinary/never_public rows
  behave exactly as before (suppress once, re-raise, mutate `reraised_at_ms`
  identically). The two new red tests assert exactly this boundary for a
  synthetic `secret` row (neither suppress nor mutate), which is unreachable in
  production but harmless. Admission, settlement authority, and Thought-visible
  lines for ordinary/never_public are unchanged.
- No other filter change in range: all other listed reads keep `!= 'secret'` /
  `<> 'secret'` or no predicate; writes only add classification columns/params.
- Wire: `sawSecret` is non-enumerable (`allocator.ts:1025`) and asserted absent
  from `JSON.stringify(projected)`; `thoughtMessagesForProjection` output
  asserted equal pre/post. Settlement JSON gains a host-only boolean consumed
  only by aftermath; no Thought prompt, admission decision, or authority check
  reads it.
- Verdict: byte-identical for all reachable ordinary/never_public data. MET.

## 4. Red-first table (independent re-runs at parents)

Parent worktrees reused: /tmp/gs1p-b1 (2ea3ef7), /tmp/gs1p-b2 (0ef8dd0),
/tmp/gs1p-b3 (f1f3833). Saved logs: /tmp/GS1R_red1.txt, red2a, red2b, red3a,
red3b (prior run 09:52-09:53 TRT; re-verified cheaply where relied upon).

| Commit | Test (file) | Parent result (assertion) | Matches coder HEARTBEAT red? |
|---|---|---|---|
| 0ef8dd0 Build 1 | allocator.test.ts "GS1 delivered input labels" x3 (secret evidence / omitted secret / ordinary) | 3 failed at 2ea3ef7 (`sawSecret` undefined on projection; 84 skipped) — /tmp/GS1R_red1.txt | YES (>=2 red; coder: "three delivered-label cases fail (undefined flag), 82 existing pass" — count delta is scoping of the same file, substance matches) |
| f1f3833 Build 2 | aftermath.test.ts "GS1 aftermath classification" x3 (true/false/undefined) | 3 failed at 0ef8dd0: true->ordinary vs never_public; false->`no such column: data_classification`; undefined->ordinary vs never_public — /tmp/GS1R_red2a.txt | YES (coder: "aftermath labels ... fail before implementation") |
| f1f3833 Build 2 | schema-v49-migration.test.ts x2 (fresh/upgrade) | 2 failed at 0ef8dd0: fresh `expected 48 to be 49`; upgrade `no such column: data_classification` — /tmp/GS1R_red2b.txt | YES (coder: "fresh/upgrade v49 tests fail") |
| af90ce6 Build 3 | senses.test.ts "secret declines neither suppress nor mutate" x2 | 2 failed at f1f3833: `expected [...] to include 'backup: unknown'` (secret row suppressed/mutated pre-filter) — /tmp/GS1R_red3a.txt; 3rd case (never_public honored) passed at parent | PARTIAL: 2 of 3 are genuine red-first; the never_public case passed at parent (it pins pre-existing `!= 'secret'` semantics, not new behavior). Coder claimed "two sense label boundary tests failed; 12 passed" — MATCHES. |
| af90ce6 Build 3 | run.test.ts "GS1 live delivered-input carrier" x3 | PASSED at f1f3833 (3 passed — /tmp/GS1R_red3b.txt), i.e. NOT red-first: the live carrier (Build 1) already persisted the flag, so these pass without Build 3. Coder heartbeat did not claim them as red. | N/A (green-pinning, not red-first) |
| af90ce6 Build 3 | input.test.ts "GS1 private projection re-entry" x1; allocator.test.ts "GS1 structured and compact labels" x2 | Not independently re-run at parent in prior run; at tip they pass. The 2 structured/compact allocator cases exercise Build 1 code (thoughtInputContainsSecret over workingContext/retrieval provenance) that predates Build 3, so they are most likely green-pinning like run.test.ts rather than Build-3 reds. The qualifying Build-3 reds remain the 2 senses boundary cases above. | Each commit still has >=2 genuine red-first tests (B1: 3, B2: 3+2, B3: 2). Requirement MET. |

Build 3 red-first note: strictly, only the 2 senses boundary tests are red-first
for af90ce6's filter change; the run/input/allocator cases added in af90ce6 pin
already-green behavior (carrier from B1, pre-existing `!= 'secret'` reads). The
brief requires >=2 NEW red-first tests per commit, which is satisfied (2), but
the report records the distinction rather than claiming all 9 are reds.

## 5. Suite results vs claims (tip af90ce6, quiet, Node 22)

- Full agent-service: prior-run /tmp/GS1R_full.txt: `Test Files 456 passed
  (456); Tests 3242 passed | 1 skipped (3243)`, Duration ~140s. Matches coder
  claim (456 files, 3242 pass, 1 skip, 0 fail). Delta from base (455/3225)
  explained: +1 file (schema-v49-migration.test.ts), +17 tests (3 delivered
  labels + 3 aftermath + 2 migration + 3 senses + 3 live carrier + 1 re-entry +
  2 structured/retrieval). Re-verified subsets at tip: v49 migration 2/2 pass;
  `npm run build:agent` rc=0 (this run /tmp/GS1R_build2.txt tails `tsc`
  clean; prior /tmp/GS1R_build.txt identical).
- Discord: /tmp/GS1R_discord.txt: 168 pass, 0 fail. Matches claim.
- `npm run test:current-deployment`: coder artifacts /tmp/GS1_deploy.txt (21
  `not ok`), /tmp/GS1_deploy_names.txt diffed against
  /workspace/ops/a3merge/merge_names_2ea3ef7.txt: `diff` rc=0
  (DEPLOY-NAMES-MATCH re-confirmed this run). 21 names, rc=1 expected. Matches.
- Commands run (this review + prior run artifacts reused as labelled):
  `git log --oneline 2ea3ef7..af90ce6`; `git diff --stat/names`;
  `rg -n sawSecret/never reads or judges/thoughtInputContainsSecret/projection readers`;
  `npx vitest run <file> --reporter=dot` at tip and at /tmp/gs1p-b*
  parents (logs /tmp/GS1R_red*.txt, /tmp/GS1R_verify.txt);
  `npm run build:agent` (rc 0); full/discord/deploy suites per coder logs
  re-tailed, not re-run in full (budget).

## 6. STOP check (brief STOP)

- Taint from content needed? NO — labels only, proven above.
- Change to Thought/admission/authority needed? NO — none made, none needed.
- never_public to non-owner unexcludable? NO — no non-owner surface exists.
- Green test expectation changed beyond pins? NO — only `toBe(48)`->`toBe(49)`
  pin updates plus new tests.
- Secret content read anywhere? NO. BLOCKING audience/content finding? NONE.
No STOP condition triggered; none unreported.

## 7. Scope / hygiene

- Only GS1 commits in range: YES (`git log --oneline 2ea3ef7..HEAD` = exactly
  the 3 feat(GS1) commits).
- Deploy/systemd/update.sh/crypto/backup/signing changes: NONE.
  `git diff --stat 2ea3ef7..af90ce6 -- deploy/ systemd/ scripts/update.sh`
  empty; name-only grep for deploy|systemd|update.sh|crypto|backup|sign empty.
- Public-repo hygiene (no secrets, no secret content in Host notes): YES.
  Friction/decline notes use credential-shape redaction (`withheld:secret`
  placeholder, pre-existing); tests use synthetic labels ("a quiet day",
  "considered"); no secret material in diff.
- Empty-diff paths statement: the relevant-path diff stat is empty (no output).

## Findings

- BLOCKING: none.
- NONBLOCKING: (1) Build 3 mixes 2 genuine red-first tests with green-pinning
  tests in the same commit — acceptable (>=2 reds met) but future commits
  should separate pinning from red-first. (2) `materializeSemanticSettlement`
  defaults `sawSecret = true` (run.ts:984) — safe direction (fail closed), but
  worth a comment since every real caller passes explicitly. (3) Brief's
  "Host-recorded friction unchanged" vs Thought-authored `claim.friction`
  inheriting taint (growth.ts:175) — judged consistent with DO2's "every
  Thought-authored write", recorded here for clarity. All outside ruled scope
  for BLOCKING; none violates a ruled requirement.
- NOTE (outside ruled scope): `recordFriction` nulls note when classification
  is secret; GS1 never writes secret (only never_public/ordinary), so no
  behavior change; mentioned only to show it was checked.

## Exact commands run (this session; prior-run logs as labelled)

```
git -C /workspace/wt/gs1-review log --oneline 2ea3ef7..af90ce6
git -C /workspace/wt/gs1-review diff --stat 2ea3ef7..af90ce6
rg -n "sawSecret" apps/agent-service/src/core/cognitive-v021/ --glob '!*.test.ts'
rg -n "never reads or judges" apps/agent-service/src/
sed slices: allocator.ts:1000-1030; aftermath.ts:25-150; input.ts:150-175;
  run.ts:1580-1620/1420-1435/975-995/1815-1835; senses.ts:40-90;
  schema.ts:1710-1740; db.ts:60-80/440-470; server.ts:650-700/2455-2475;
  growth.ts:80-135/160-210; expectations.ts:190-245; revisions.ts:680-710;
  night.ts:250-270; journal.ts:180-195; commands.ts:295-345; friction.ts:1-40;
  snapshots.ts:40-80; publish.ts:540-620; validate.ts:55-112/326-384
rg readers: FROM (mood_events|expectations|growth_revisions|...|sense_declines|...)
rg filters: = 'ordinary'|== 'ordinary' (empty); secret-content reads beside labels (empty)
rg routes/guards: requireOwner|growth|journal|night|practice|sense (server.ts, input.ts, discord-bot, observer-exporter)
tail/head of /tmp/GS1R_full.txt /tmp/GS1R_build.txt /tmp/GS1R_discord.txt /tmp/GS1R_red*.txt
diff /tmp/GS1_deploy_names.txt /workspace/ops/a3merge/merge_names_2ea3ef7.txt (rc 0)
npx vitest run schema-v49-migration.test.ts --reporter=dot (2 passed, tip)
npm run build:agent > /tmp/GS1R_build2.txt (rc 0)
git diff --stat 2ea3ef7..af90ce6 -- deploy/ systemd/ scripts/update.sh (empty)
```

Prior-run evidence reused (re-tailed, cheaply re-verified where relied upon):
/tmp/GS1R_full.txt, /tmp/GS1R_build.txt, /tmp/GS1R_discord.txt,
/tmp/GS1R_red1.txt, /tmp/GS1R_red2a.txt, /tmp/GS1R_red2b.txt,
/tmp/GS1R_red3a.txt, /tmp/GS1R_red3b.txt; parents /tmp/gs1p-b1..b3.
Node: /home/box/.local/opt/node22/bin (v22.23.3). No edits to the tracked tree;
report is the deliverable (untracked file at clone root is expected).

## Wrapper metrics (W1)
METRICS session=rollout-2026-10-01T09-59-54-01a0f643-3295-72b1-b870-6185964d24c8.jsonl turns=61 cost=not-in-rollout
METRICS inputTokens per turn: median=57466 max=82957 total=3265405
METRICS cacheRead hit share: 93.5% (cached 3053165 / input 3265405); from turn 3: min 0.5% median 98.3%
METRICS model-wait total=597s (median 4.2s, max 60s) vs tool time total=15s
METRICS outputTokens per turn: median=186 max=5611 mean=540 total=32926
METRICS harness=codex-cc exit=0
