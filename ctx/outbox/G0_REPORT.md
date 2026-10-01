STATUS: PARTIAL

# G0 ground truth

Observed 2026-10-01. Mint was accessed only through `ssh mint '<command>'`. No production writes, deployments, source edits, commits, pushes, Discord actions, or CI occurred. No secrets, environment values, conversation rows, or message text were printed.

Local source HEAD is `59960324fe514947d0564e201c96074f72e91ed7` (`git rev-parse HEAD`), different from Mint checkout HEAD. Source findings below apply to the local revision; they do not certify Mint's loaded dist artifact. Source references are relative to `apps/agent-service/src/` unless otherwise specified.

## G0.1

### 1. Revision and database versions

- VERIFIED Mint HEAD: `e02a2a847a0e74012486007078bd8ac61a4ed5bf`. Command: `ssh mint 'git -C /home/xarvak/project-ashley rev-parse HEAD'`.
- VERIFIED service WorkingDirectory: `/home/xarvak/project-ashley/apps/agent-service`; ExecStart `/usr/bin/node dist/index.js`; EnvironmentFile `%h/.composer-assistant/.env`. Commands: `ssh mint 'systemctl --user show ashley-agent.service -p WorkingDirectory -p FragmentPath; systemctl --user cat ashley-agent.service | grep -E "^(WorkingDirectory|ExecStart|EnvironmentFile)="'`.
- VERIFIED nuclear user_version=53. Command: `ssh mint 'sqlite3 -readonly /home/xarvak/.composer-assistant/conversations/nuclear.db "PRAGMA user_version;"'`.
- VERIFIED inspected root sidecar schema_version=45, one metadata row. Command: `ssh mint 'sqlite3 -readonly /home/xarvak/.composer-assistant/cognitive-v021.db "SELECT schema_version,COUNT(*) FROM cognitive_sidecar_meta GROUP BY schema_version;"'`.
- UNKNOWN effective process DB selection: the permitted commands do not establish effective data-plane configuration. `/home/xarvak/.composer-assistant/conversations/cognitive-v021.db` also exists, but the same metadata query returned `no such table: cognitive_sidecar_meta`. Do not conflate these files. Source selection uses dataPlane.cognitiveSidecarDbPath (`agent.ts:154`, `core/data-plane.ts:103`).
- VERIFIED service active, ActiveEnterTimestamp `Wed 2026-09-30 07:28:53 +03`. Command: `ssh mint 'systemctl --user show ashley-agent.service -p ActiveState -p ActiveEnterTimestamp'`. Checkout HEAD is not independent proof of loaded artifact identity.

### 2. Sandbox and self-change

- VERIFIED capability release state counts in the inspected nuclear DB:

| Capability | State | Rows |
|---|---|---:|
| project_inspection | active | 1 |
| project_experimentation | active | 1 |
| bounded_operation | observe | 1 |
| candidate_authorship | observe | 1 |
| candidate_verification | observe | 1 |
| patch_export | observe | 1 |

Command: `ssh mint 'sqlite3 -readonly /home/xarvak/.composer-assistant/conversations/nuclear.db "SELECT capability,state,COUNT(*) FROM capability_releases GROUP BY capability,state;"'`. These are release rows, not proof that all execution gates allow the capability. Schema was inspected using `SELECT name,sql FROM sqlite_master WHERE name IN ("capability_releases","cognitive_maturation_contract_state")` on this read-only DB.

- VERIFIED unprivileged Bubblewrap probe as xarvak: exit 0. Command: `ssh mint 'bwrap --ro-bind / / --unshare-all true; printf "BWRAP_EXIT=%s\n" "$?"'`. This qualifies only the specified substrate probe.
- UNKNOWN project-ashley registry entry and exportDestinationCanonicalRoot: production registry/configuration content reads are outside the packet's allowed operation list. Local loader uses an operator-selected path and fails closed (`core/sandbox/project-registry.ts:36-47`); a checkout path cannot substitute for registry authority.
- UNKNOWN export folder existence and contents because its canonical root is unknown. No guessed folder substituted.

### 3. Row counts

VERIFIED counts from `/home/xarvak/.composer-assistant/conversations/nuclear.db`:

| Group | Table | Count |
|---|---|---:|
| C3 | motivations | 0 |
| C3 | learned_influences | 0 |
| C3 | learned_influence_evidence | 0 |
| C3 | learned_choice_receipts | 0 |
| C3 | identity_seed_lineage | 0 |
| C4 | cognitive_predictions | 0 |
| C4 | cognitive_outcome_observations | 0 |
| C4 | cognitive_outcome_adjudications | 0 |
| C4 | working_view_links | 0 |
| C4 | lived_experience_links | 0 |
| C4 | thought_calibration_adjustments | 0 |
| context | context_budget_policies | 0 |
| context | context_allocation_receipts | 0 |
| context | context_summary_projections | 0 |
| legacy revisions | learning_revisions | 0 |
| legacy revisions | evidence_links | 0 |
| legacy revisions | identity_reviews | 0 |

Exact executed query batch, passed to `ssh mint 'sqlite3 -readonly /home/xarvak/.composer-assistant/conversations/nuclear.db "<SQL>"'` with shell-escaped string literals:

```sql
SELECT 'motivations',COUNT(*) FROM motivations;
SELECT 'learned_influences',COUNT(*) FROM learned_influences;
SELECT 'learned_influence_evidence',COUNT(*) FROM learned_influence_evidence;
SELECT 'learned_choice_receipts',COUNT(*) FROM learned_choice_receipts;
SELECT 'identity_seed_lineage',COUNT(*) FROM identity_seed_lineage;
SELECT 'cognitive_predictions',COUNT(*) FROM cognitive_predictions;
SELECT 'cognitive_outcome_observations',COUNT(*) FROM cognitive_outcome_observations;
SELECT 'cognitive_outcome_adjudications',COUNT(*) FROM cognitive_outcome_adjudications;
SELECT 'working_view_links',COUNT(*) FROM working_view_links;
SELECT 'lived_experience_links',COUNT(*) FROM lived_experience_links;
SELECT 'thought_calibration_adjustments',COUNT(*) FROM thought_calibration_adjustments;
SELECT 'context_budget_policies',COUNT(*) FROM context_budget_policies;
SELECT 'context_allocation_receipts',COUNT(*) FROM context_allocation_receipts;
SELECT 'context_summary_projections',COUNT(*) FROM context_summary_projections;
SELECT 'learning_revisions',COUNT(*) FROM learning_revisions;
SELECT 'evidence_links',COUNT(*) FROM evidence_links;
SELECT 'identity_reviews',COUNT(*) FROM identity_reviews;
SELECT wave,COUNT(*) FROM cognitive_maturation_contract_state GROUP BY wave;
SELECT capability,state,COUNT(*) FROM capability_releases GROUP BY capability,state;
```

Table owners: `core/learned-autonomy/migration-37.ts:25,60,115,133,159`; `core/cognitive-graduation/migration-38.ts:27,59,83,117,124,145`; revision accesses `core/learning/revisions.ts:154,187,200`.

VERIFIED maturation counts by wave: c2=1, c3=1, c4=1, c5=1; c1 absent from grouped results (zero). Query included above.

### 4. Served path

- VERIFIED local runtime.ts module reachability: `index.ts:3,23` invokes serveAgent; `serve.ts:5` imports server; `agent.ts:4` imports AshleyCore from core/index; `core/index.ts:1` re-exports runtime; `agent.ts:138` constructs AshleyCore. `core/runtime.ts:62` imports reflection/initiative and :84 imports change-proposal/store (also dynamic require :1100). This establishes module loading, not invocation of every legacy function. UNKNOWN deployed compiled path equivalence: production source/artifact content reads are outside the packet's permitted commands.
- VERIFIED only local endpoint using retrieveEpisodes is `GET /nuclear/episodes`, `server.ts:528-539`, imported at :10. It requires owner authentication and passes a bounded limit. Search: `rg -n 'retrieveEpisodes' apps/agent-service/src/server.ts`. UNKNOWN deployed artifact equivalence for the same reason.

### 5. Inner-life settings and journal

- UNKNOWN effective PERIODIC_COGNITION_ENABLED classification. Reading production env content/effective process environment is not an allowed operation. Local unset default=false; normalized true/1 enables (`core/cognitive-v021/dispatch/live.ts:74-79`). This default is not a production value.
- UNKNOWN effective ASHLEY_AFTERGLOW_ENABLED classification, same restriction. Local unset default=true; normalized false disables (`env.ts:138`).
- UNKNOWN effective PROACTIVE_CHECK_INTERVAL_MIN classification, same restriction. Local default=60 minutes, bounds 1–1440 (`apps/discord-bot/src/config.ts:152-157`). No configured numeric value disclosed.
- VERIFIED seven-day journal event counts: afterglow ran=8, abandoned=1; NIGHT scheduled=1, ran=0 observed; AWAKE scheduled=1, ran=6. Counts describe retained journal events, not successful settlements, unique cycles, or proof of complete seven-day history. Source log categories: `serve.ts:614,621-627`.

Exact safe command executed:

```sh
ssh mint 'journalctl --user -u ashley-agent.service --since "7 days ago" --no-pager -o short-iso | grep -E "\[cognitive-v021\] (afterglow|night|awake) " | awk '\''{for(i=1;i<=NF;i++) if($i=="[cognitive-v021]"){print $1,$(i+1),$(i+2);break}}'\'''
```

All timestamps below are 2026-09-30, +03:00:

| Event | Times |
|---|---|
| afterglow ran | 04:53:08, 04:53:49, 04:58:16, 05:02:08, 08:06:08, 23:06:23, 23:08:30, 23:10:37 |
| afterglow abandoned | 23:10:37 |
| NIGHT scheduled | 07:28:56 |
| AWAKE scheduled | 07:28:56 |
| AWAKE ran | 08:07:56, 11:03:15, 14:14:32, 17:14:02, 20:09:09, 23:11:57 |

- VERIFIED bot cognitive idle lines=96; first `2026-09-28T04:25:40+03:00`, last `2026-10-01T00:29:02+03:00`. Exact command:

```sh
ssh mint 'journalctl --user -u ashley-discord.service --since "7 days ago" --no-pager -o short-iso | grep "\[discord-bot\] cognitive idle" | awk '\''NR==1{first=$1} {last=$1} END{print "idle_lines="NR,"first="first,"last="last}'\'''
```

### 6. Backups

- VERIFIED requested `/home/xarvak/.composer-assistant/backups` directory absent. Command: `ssh mint 'ls -ld /home/xarvak/.composer-assistant/backups'` returned No such file or directory.
- UNKNOWN newest snapshot age: no snapshot exists in the requested directory. Other migration backup DB filenames surfaced during permitted path discovery; they do not establish the requested backup package or restore readiness.

## G0.2

### (a) Coverage contract

VERIFIED capped conversation read without continuation: `core/cognitive-v021/evidence/conversation-log.ts:460-484`, listConversationEvidence, clamps to 1–1000, SQL LIMIT at :477 selects newest rows then reverses them. No cursor or omission metadata is returned. It is a latest-window API rather than an explicit closed-span API; treating it as full conversation coverage silently omits older rows. `thought/input.ts:706` consumes it, so later recency omission accounting cannot describe rows absent from this source read.

VERIFIED LIMIT inventory in the named inspected modules:

| Read | Location | Continuation / span assessment |
|---|---|---|
| conversation evidence list | cognitive-v021/evidence/conversation-log.ts:477 | Max1000, no pagination. |
| duplicate evidence lookup | same file:202 | LIMIT1 identity lookup, not span enumeration. |
| afterglow unreflected rows | cognitive-v021/initiative/afterglow.ts:162 | Oldest-first after reflectedThroughSeq; max60 (:42); durable watermark continuation (:129,403). No latest-window eviction. |
| afterglow owner-since predicate | same file:210 | LIMIT1 existence test, not enumerated coverage. |
| legacy ranked episode search | core/memory/episodes.ts:330 | Default6/max20, no cursor; search, not complete conversation span. |
| legacy episode fallback | same file:346 | Same bound, query fallback max3, no cursor. |
| legacy unconsolidated messages | same file:374 | Oldest-first after last episode/watermark; default24/max100; next read derives last source_end_message_id or liveWatermark (:360-365). No explicit cursor return. |
| legacy assertion lookups | same file:73,103,262 | LIMIT1 keyed identity/existence reads. |
| v021 episode projections | cognitive-v021/memory/episodes.ts:177,201 | Bounded episode projections, no SQL pagination. |

VERIFIED afterglow explicitly skips a failed batch by advancing its watermark with outcome abandoned (`initiative/afterglow.ts:257`). Eligibility filters (:156-160) exclude non-owner/Ashley, empty/redacted rows and undelivered Ashley rows. These are explicit exclusions, not a silent LIMIT drop.

VERIFIED additional bounded context reads: `retrieval/fts.ts:77,237` limit candidate searches; `thought/input.ts:649` limits occupancy. NIGHT caps day/week episode and journal projections (`growth/night.ts:139-142,171`); AWAKE slices episodes/threads/questions (`initiative/agenda.ts:27-40`). These agenda projections expose no continuation.

UNKNOWN exhaustive recall/span guarantee across every operation adapter: the named-module inspection and retrieval searches establish these findings but do not establish a complete source-to-consumer inventory of all recall/evidence-span APIs. This report does not certify that every span read elsewhere is uncapped. No fixes or test execution performed.

### (b) One context path

VERIFIED final Thought input builder is shared: `thought/run.ts:3374` calls buildThoughtInput; its options include AWAKE buildInnerAgenda (:3312), NIGHT buildNightAgenda (:3316), and shared growthForThought (:3320). `thought/input.ts:991` builds shared core profile (:1127), episodes (:1133), journal (:1136), learned self (:1039), and innerPass (:1194).

VERIFIED agenda-specific blocks have separate assembly logic: AWAKE `initiative/agenda.ts:23-55` assembles recent episodes, open threads/questions, branches and reach-out feedback; NIGHT `growth/night.ts:93-173` assembles memories, similar pairs, self evidence, stale questions, day/week episodes, journal and branches. They reuse lower-level listRecentEpisodes/toThoughtEpisode, listLiveMemoryAssertions and listInterestBranches, but apply different filters/caps. The final builder is common; overlapping agenda projections are separate and do not guarantee identical coverage.

## Key lines

```text
MINT_HEAD=e02a2a847a0e74012486007078bd8ac61a4ed5bf
LOCAL_HEAD=59960324fe514947d0564e201c96074f72e91ed7
NUCLEAR_USER_VERSION=53
SIDECAR_SCHEMA_VERSION=45 (inspected root sidecar; effective selection UNKNOWN)
BWRAP_UNPRIVILEGED=true (specified probe exit0)
BACKUPS_DIR=/home/xarvak/.composer-assistant/backups (absent)
NEWEST_BACKUP_AGE=UNKNOWN (no snapshot in requested directory)
PATCH_EXPORT_RELEASE_STATE=observe (1 row)
PROJECT_ASHLEY_EXPORT_ROOT=UNKNOWN
PERIODIC_COGNITION_ENABLED=UNKNOWN
ASHLEY_AFTERGLOW_ENABLED=UNKNOWN
PROACTIVE_CHECK_INTERVAL_MIN=UNKNOWN
LEGACY_REQUESTED_TABLE_COUNTS=all zero in inspected nuclear DB
AFTERGLOW_RAN_LOG_EVENTS_7D=8
NIGHT_RAN_LOG_EVENTS_7D=0 observed; scheduled=1
AWAKE_RAN_LOG_EVENTS_7D=6
BOT_COGNITIVE_IDLE_LOG_LINES_7D=96
```
