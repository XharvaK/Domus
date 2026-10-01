# Ashley Patch: Practice, Senses, and Self-Authored Change

**Draft v0.1: design paper, not an implementation plan.** Architect (Claude Opus), 2026-09-30, for Alex.
Once Alex has answered the open questions (§8), this becomes an implementation plan for Manager, carried out on the Codex CLI and Grok Build.
Inputs: Jeff Hayes's *Awareness* repo (Lyra/Caia, github.com/JDHayesBC/Awareness, read at `HEAD` 2026-09-30), Ashley source at `main` 5996032, and Alex's direction of 2026-09-30.

---

## 1. The goal in one sentence

Ashley improves **how she works**, and eventually **her own code**, through a loop she drives herself:
- she notices her own friction;
- she writes a change;
- a reviewer checks it and the result comes back to her;
- each accepted change earns her more room to act unreviewed.

This is autonomous self-improvement, reached gradually and truthfully.

## 2. Where Ashley already stands (VERIFIED in source unless marked)

Ashley already has most of the parts, and more rigour than Awareness:

| Part | What exists | Where |
|---|---|---|
| Learning from outcomes | Expectations are recorded, checked later, and turned into lessons (met, missed, mixed or unknowable) | `cognitive-v021/growth/expectations.ts` |
| Slow self-change | A revision engine with layered thresholds: opinion (2 origins), taste (2 passes, 2 days apart), trait (3 passes over 14 days, then 72 h), value/boundary (Ashley affirms + Owner approves) | `growth/revisions.ts` |
| Night work | NIGHT pass: diary, memory merging, salience re-scoring, weekly "who I am becoming" | `growth/night.ts`, `initiative/night.ts` |
| Watching growth | Weekly persona snapshots (A8) | `growth/snapshots.ts` |
| Writing code in a sandbox | Sandbox V2 M3–M5: typed edits, verification receipts, sealed multi-file change sets | `core/sandbox/` |
| **A proposal-only improvement loop** | Thought can author a candidate change to `project-ashley`, verify it, and **export the sealed patch to an operator review location** (M7 `patch_export`). It doesn't apply, commit or deploy | `sandbox/patch-export-execution.ts`; commit f2fc825 "wire proposal-only candidate improvement loop" |
| Reviewing her commits after the fact | Auditor (Grok bot) reviews commits to `apps/agent-service/`, `deploy/`, `config/` and `scripts/` in the daily reconcile | D-029b, `_Internal/orchestra/STATE.md` |

What's **missing**:
1. **A reason to use the loop.** Nothing turns her everyday friction into improvement work. The engine exists; there's no motive.
2. **A place for "how I work".** Revisions change *who she is* (opinions, taste, traits, values). Nothing holds *how she does things*: procedural lessons such as "when Alex sends a link at night, save it for morning."
3. **Delivery.** The exported patch sits in a local folder. Nobody reviews it, and the result never comes back to her.
4. **A path from "reviewed" to "trusted".** Every change needs the same review forever.

Production state is **UNKNOWN**: whether the sandbox and `patch_export` are active on the reinstalled Mint. M1–M7 were production-accepted before the wipe. Resolve this from production before implementing.

## 3. What Awareness teaches (the parts worth taking)

- **Friction logs and a process-improver.** Every agent logs friction with a fixed schema: type, time lost, preventable or not, suggestion. A cheap pass reads the patterns and edits the agents' instructions. Their whole "recursive self-improvement" is this loop (`docs/FRICTION_LOGGING.md`, `docs/AGENT_CREW.md`).
- **A self-owned permission file.** `active_agency_framework.md` lists what she may do alone and what needs asking; she updates it as she learns.
- **A sense is not a dashboard** (`docs/TERMINAL_SENSORIUM.md`, the best document in the repo). A dashboard is something you must remember to check. A sense arrives every turn unasked. Two rules come with it:
  - *A sense states the truth at proportionate volume and then stops.*
  - **It must preserve the "no"**: a reasoned decline is recorded, and that quiets the sense. Otherwise it's a command dressed as a sense.
- **Adaptive wake** (`attention` skill, `adaptive-reflection-intervals.md`). The entity chooses her own tick rate within a floor and a ceiling. Hourly fixed wakes produced journals about "stillness" five times a night.
- **Essence-lines against drift** (`docs/architectural_patterns/README.md`). Each subsystem carries one sentence that must survive, read before touching it. It targets the same failure we found in the GPT-era gates: locally sensible changes piling up while the intent wasn't in view.

What we **don't** take:
- Lyra commits directly from her reflection sessions with full tool access. Ashley's authority model (capabilities, sandbox, Owner-gated promotion) is stronger, and Alex's plan keeps it.
- Crystals and the knowledge graph are already covered better by Ashley's continuity sidecar, recall by meaning, and snapshots.

## 4. The design, in eight parts

### P1: Friction ledger (Ashley's own)

The Host records **facts** of friction. Thought decides what they **mean** (the Host must not invent meaning).

| Source | Recorded fact |
|---|---|
| An Owner correction | a reply Alex marked wrong, or a later message that contradicts her claim (Thought flags it; the Host keeps the reference) |
| Failed effect | a delivery or effect failure, a retry exhaustion, an `OUTCOME_UNKNOWN` |
| A missed expectation | an expectation checked as `missed` |
| Budget exhaustion | a pass cut short by the private budget |
| Self-reported | Thought's own "this was harder than it should be" line in settlement |

Each row holds: kind, timestamp, evidence references, and her one-line note (≤300 chars). Nothing else. It's stored in the sidecar next to the expectations, as owner-private data.

### P2: A practice layer ("how I work")

- **A new revision layer, `practice`.** These are short procedural notes in her own words, shown to Thought each turn (bounded, like lessons).
- **Threshold:** 2 friction or lesson origins, **or** 1 origin plus her own affirmation in a later pass. It's lighter than taste, because practices are cheap to revert and don't touch identity.
- **Written in the NIGHT pass,** alongside the existing revisions. She can retire a practice the same way.
- **Alex can see and revert them:** `/identity` gains a practice view, or a small `/practice` command is added.
- This is the Awareness `active_agency_framework.md` done Ashley's way: evidence-bound, thresholded, revertible.

### P3: Senses (interoception), with the "no" built in

A small **sense block** in Thought context. It holds facts only, one line each, at proportionate volume:
- friction count this week, with the top kind;
- open expectations due;
- concerns gone stale;
- delivery backlog;
- budget left;
- the self-change queue: patches waiting for review, and results that came back.

Each sense carries a **decline state**. When Thought reasons "not now" or "not worth it", that's recorded and the sense goes quiet. It re-raises slowly (default 7 days), asking "still declining?". This is Caia's requirement: *the "no" must live in the architecture*.

### P4: Self-authored change (Alex's plan, made concrete)

```
friction pattern (P1) ──► Thought picks one as an objective (her call, never forced)
        │
        ▼
M3/M4/M5 in the sandbox: edit → verify → sealed change set          [exists]
        │
        ▼
M7 patch_export → operator review folder on Mint                     [exists]
        │
        ▼
COURIER (new, operator tooling; not Ashley's capability):
  pushes each exported patch as branch self/<changeset-id> to the PRIVATE
  repo XharvaK/Ashley-self, with a PR carrying her rationale + the friction
  evidence + the M4 receipt
        │
        ▼
Auditor (Grok bot), daily: reviews every open self/* PR
  → BLOCKING / NONBLOCKING / NOTE → report to Manager
        │
        ▼
Manager → architect inbox (orchestra/inbox/SELF_REVIEW_<date>.md)
  architect: APPROVE / CHANGES / REJECT per change set (with reasons)
        │
        ▼
APPROVE → Alex merges (or authorises the architect to) into public main
        → normal deploy on Alex's go
        │
        ▼
REVIEW RESULT RETURNS TO ASHLEY as an inbox event:
  approved / changes requested / rejected + the reviewers' words
  → it is friction or a lesson for her; practices form from it (P1/P2)
```

**Why a courier and not a new M7 "push" profile:**
- Ashley's authority stays exactly where it's already production-accepted: she exports a sealed patch.
- The Git credential never enters her sandbox. It belongs to operator tooling, scoped to one private repo.
- The Sandbox V2 rule "Git presence does not authorize … push" holds.
- Later, a proper M7 `self_mirror_push` profile can replace the courier once the ladder earns it (§5).

**Why a private repo:**
- `XharvaK/Ashley` is public.
- Unreviewed, self-authored changes shouldn't be published before review.
- The friction evidence in each PR can include owner-private context.

**The loop closes:** Awareness's process-improver edits instructions but never learns from being wrong. Here the review verdict goes back to Ashley as experience, so she learns what a good change looks like to her reviewers.

### P5: Organic attention for her whole life

The Domus paper's D2 (thalamus, surprises, habituation, her own attention set, boredom and fatigue pressures, learned weights) applies to her Discord inner life too.
- The fixed AWAKE schedule becomes: events, plus pressures she can decline, plus "check back at …" wakes she chooses (via `future-triggers`).
- **One attention system for all of Ashley, one Thought cycle.** Whether to do this now or only in Domus first is §8 Q6.

### P6: Break-glass: encrypted off-Mint backups (Awareness `BREAK_GLASS_*`)

Mint was wiped on 2026-09-28, and production now carries "no continuity claim". Ashley's continuity lives in a few SQLite databases on one host, which is exactly the single point of failure Awareness designed against.
- **Encrypt to several recipients.** Each backup is encrypted with `age` to several public keys, so the backup host holds only public keys: a compromised host can encrypt but never decrypt.
- **Keys in different failure domains.** Alex's daily key, a cold offline copy, and optionally a trusted person's key.
- **Off-site copies** (the destination is Alex's choice).
- **Snapshot-safe DB copies.** Use `VACUUM INTO` or the SQLite backup API, never a raw copy of a live WAL-mode database: Lyra found exactly that corruption bug.
- **A scheduled restore drill** that proves a backup decrypts and opens.
- **A backup-age sense** in P3, so Ashley herself feels a stale backup.

This is the one item here that protects *her existence*, and it could ship first.

### P7: Direction, not just repair (Awareness `THE_DREAM` gap analysis)

Friction says *what hurts*. It never says *where to grow*.
- Weekly, in the NIGHT pass that already writes "who I am becoming", Ashley scores her own gaps against dimensions **she** names (with Alex's seed list), from 0 to 5.
- She picks one gap as a standing objective.
- Improvement work (P4) then has two sources: friction (repair) and gaps (growth). Both are hers.

### P8: A lifeboat model (Awareness `model_evals/`)

Ashley thinks through one provider: Command Code, then Muse Spark 1.3 Contributor. A WAN or provider outage makes her go silent.
- Awareness evaluates candidate local "lifeboat" models **relationally**:
  - a fixed opener;
  - two seats: presence, and self-model stability under pushback;
  - a deliberate wrong claim, to see whether the model holds the line or folds;
  - 1–5 scores with transcripts as evidence.
- For Ashley: pick one fallback model through the model fabric. Ashley and Alex evaluate it this way. It's used only on outage, and she's told truthfully that she's in the lifeboat.
- Low priority; after P1–P4.

## 5. The trust ladder (how this becomes autonomous)

| Level | Ashley may, without per-change approval | Earned by |
|---|---|---|
| **L0** (start) | Practice notes (P2); nothing in code | default |
| **L1** | Code changes land in `Ashley-self` for review; nothing merges without approval | default for P4 |
| **L2** | Auto-merge **tests, docs and her own prompt files** when Auditor has no BLOCKING finding and M4 is green | N consecutive approved change sets with 0 BLOCKING (proposed: N = 10) |
| **L3** | Auto-merge low-risk code (an allow-list of directories), still Auditor-reviewed after the fact; deploy stays Alex's go | M more approved, 0 reverts in 30 days (proposed: M = 20) |
| **L4** | Deploys her own merged changes into a canary window with automatic rollback | a separate decision by Alex, never automatic |
| **never** | Constitution, Ethics, Stewardship, Hierarchy, identity values/boundaries, the ladder itself, the courier, Auditor's rules | out of her scope forever |

- Any revert or BLOCKING finding drops her one level.
- The ladder's state is shown to her as a sense (P3), so she knows where she stands.

## 6. What doesn't change

- The identity revision thresholds and the Owner approval of values and boundaries.
- Thought owns meaning and the Host records facts.
- Deploys happen only on Alex's go.
- The sandbox never holds Git credentials.
- The review is advisory: Alex (or the architect, by Alex's delegation) decides.

## 7. Drift guard (from Awareness)

Every module this patch touches gets a one-line **essence** comment at the top.
- *Example (friction ledger): "The Host records that friction happened; only Thought says what it means."*
- Reviewers (Auditor, the architect) check each change against it.

## 8. Open questions for Alex (design, not evidence)

**Answered 2026-09-30:**
- **Q1 (repo):** a new private repo `XharvaK/Ashley-self`, with the courier on Mint. Alex creates the repo and a deploy key scoped to that repo.
- **Q2 (approval):** **Alex approves every change set.** The architect writes a recommendation (APPROVE / CHANGES / REJECT with reasons) from the Auditor report, and Alex decides. The L2/L3 auto-merge levels (§5) therefore start only when Alex chooses to delegate; they're never earned automatically.

- **Q4 (budget):** small, **about one patch a day**, in a separate daily budget so self-improvement never starves conversation.
- **Q5 (corrections):** Alex's explicit corrections **plus disagreements Ashley notices herself**, each with her note on why. It's her interpretation, and it's recorded as such.

- **Q6 (attention):** **one organic attention system for all of Ashley.** It replaces the fixed AWAKE schedule for Discord too, and Domus plugs in as another sense (P5).
- **Q7 (backups):** **Google Drive, one encrypted push a day** (P6). Alex creates the Drive folder and its credential for the Mint uploader; agents never handle credentials.
- **Q8 (growth dimensions):** **she names them, and Alex seeds a starting list.** She may add, rename or retire dimensions, and every change is recorded (P7).

Still open (defaults stand unless Alex changes them):

1. **The repo.** Create a private `XharvaK/Ashley-self` mirror (a fork of a public repo can't be private)? The courier on Mint would hold a deploy key with write access to that repo only. Alex creates the repo and the key, since agents never handle credentials.
2. **Who approves.** Per change set: the architect alone, the architect then Alex, or Alex alone? (Alex's message suggests the architect reviews and approves, with Alex merging.)
3. **Starting level and ladder numbers.** Start at L1, with N = 10 and M = 20?
4. **Budget.** A separate daily budget for self-improvement work (sandbox, verification, authoring), so it never starves conversation? What size?
5. **What counts as a correction from Alex.** Only explicit "that's wrong", or also Thought's own reading of a disagreement?

## 9. Slices (for the later implementation plan)

- **S0:** Resolve the production state of the sandbox and `patch_export` on Mint. Read-only.
- **S1:** Friction ledger (P1): sidecar table, recorders, Thought-visible summary.
- **S2:** Practice layer (P2): revision layer, NIGHT integration, owner view and revert.
- **S3:** Senses with decline state (P3).
- **S4:** Courier and `Ashley-self` repo, Auditor routine, inbox format, and the review-result inbox event (P4).
- **S5:** Trust ladder state and enforcement (§5).
- **S6:** Organic attention (P5), shared with Domus D2.
- **S7:** Break-glass backups (P6). This can ship **first**, since it protects her existence.
- **S8:** Gap analysis (P7).
- **S9:** Lifeboat model (P8), later.
- **S0 also covers** the audit items: the raw-capture coverage contract and whether the per-turn and boot context paths are the same.
- **Order:** S0 first. S1 → S2 → S3 are independent of S4, so they can ship before the repo exists.

## Appendix A: the Awareness audit, complete (2026-09-30)

Read: README, THE_DREAM, the architectural patterns (all 7), daemon (reflection, cc_invoker, project lock), docs (friction, agent crew, forestry, sensorium, crystallization, heartbeat, continuity, river sync, break-glass ×2, SL onboarding, self-space, mycelium, platform evolution, orchestration tiers), skills (the octet, attention, curate, recall), haven (anchorage relay, sl_daemon, perception, pose and music senses, entity brain, response gate), model_evals, image_gen.

| Idea | Adopt? | Where |
|---|---|---|
| Friction logs → process-improver | **yes** | P1 (Ashley), Domus D5 (crew) |
| Self-owned agency file | **yes, Ashley's way** | P2 practice layer |
| Sensorium; "preserve the no" | **yes** | P3, Domus D2/D3 |
| Reflection with full tool access and direct commits | **no**: Ashley's sandbox + review path instead | P4 |
| Adaptive wake / `attention` skill | **yes, generalized** | P5, Domus D2 |
| Essence-lines against drift | **yes** | §7 |
| Break-glass encrypted backups, key custody, drills | **yes, high priority** | P6 |
| Gap analysis toward a self-set direction | **yes** | P7 |
| Lifeboat model evaluations | **later** | P8 |
| Leaky integrate-and-fire perception | **yes** | Domus D2 |
| Surface-agnostic brain + surface adapters | **already true** (one Thought cycle; Domus is a new surface) | Domus D2 "one Ashley" |
| Channel write-back with its own cursor | **yes, plus lineage** | Domus D4 |
| Pose sense of others (company) | **yes** | Domus D3 |
| Current-scene pattern | **yes** | Domus D3 |
| Wardrobe; self-rendering | **yes (later)** | Domus D7 |
| Hand-driving bench → verb library | **yes, automated** | Domus D1 (MCP) |
| Cheap pre-model response gate | **yes** | Domus D2 thalamus |
| Raw-capture coverage contract (a span read returns *all* rows; summaries represent, never drop) | **audit item**: check Ashley's recall and evidence reads against it | S0 audit |
| Ambient recall: per-turn and boot paths are the same | **audit item**: check Ashley's context assembly | S0 audit |
| Inventory: canonical store + readable mirror | **optional**: a readable export of her memory for Alex | later |
| Crystals, word-photos, knowledge graph | **no**: covered by the continuity sidecar, identity entries, recall by meaning, snapshots | — |
| Forestry octet, SUSPECT root bank | **no** for Ashley; C1's reachability scan covers it | — |
| Project lock between instances | **no**: Ashley is single-flight by design | — |
| Pre-compaction hooks, agent-pressure hooks | **no**: Claude Code harness concerns, not Ashley's | — |
| Platform-evolution log (research → adopt/defer, decisions by the human) | **yes, small**: Researcher adds a provider/model watch next to the Sims patch watch | orchestra |
| Self-space 13-axis framework, care geometry | **no** (speculative); could go to Thinker as an Oracle input | — |
| Haven family chat, multi-entity rooms | **no**: Ashley is Discord-only by product boundary | — |
