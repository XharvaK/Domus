# One Attention for Ashley, the Domus Thalamus, and Ashley as an Organism

**Draft v0.1: design paper.** Architect (Claude Opus), 2026-09-30, for Alex. It is a companion to the Ashley patch paper (P5) and the Domus paper (D2).
Source facts are VERIFIED at Ashley `main` 5996032 unless marked otherwise. Organic analogies are **design guides, not claims** that Ashley is biologically anything.

---

# Part A: One attention system for all of Ashley

**Alex's decisions (2026-09-30):**
- one system for all of Ashley;
- **mood modulates attention, gently** (A5);
- **NIGHT is driven by work, with no time floor, generous and tuned later** (A4);
- **switch directly, with no shadow period**, protected by offline replay tests, a kill switch and the decision log (A8).

## A1. How Ashley decides to think today (VERIFIED)

Ashley has **one mind at a time**: one Thought cycle, single-flight per conversation (`cycle/cognition-claim.ts`, `cycle/fence.ts`). Deciding *when* that mind runs is spread across **eight independent triggers, each with its own clock or rule**:

| # | Trigger | Rule today | Where |
|---|---|---|---|
| 1 | Alex writes | immediate; pre-empts everything | `ingress/`, `cycle/inbox.ts` |
| 2 | A contact DMs / a room | social activation, capped by a resource fuse | `social/dm-activation.ts`, `room-activation.ts`, `resource-fuse.ts` |
| 3 | Afterglow | 30 min of silence, **or** >30 unreflected rows (rolling, after 3 min quiet); poll every 2 min | `initiative/afterglow.ts` |
| 4 | NIGHT | once per 24 h at the hour Alex is quietest (learned from ≥20 samples over 28 days; default 04:00; min gap 12 h); weekly "who I am becoming" | `initiative/night.ts` |
| 5 | AWAKE | **every 3 h ± 20 min**, whatever is going on | `initiative/awake.ts` |
| 6 | P1 periodic | 60 min cheap loop, a 4 h opportunity window, a policy of ≤ 4/hour | `initiative/periodic-schedule.ts` |
| 7 | Idle-tick triggers | `commitment_due`, `subscription_item` (external watches, 1 min cheap loop), `future_trigger_due` (times she scheduled herself) | `initiative/idle.ts`, `initiative/future-triggers.ts` |
| 8 | Frontier | deferred work dispatched by the frontier coordinator | `frontier/coordinator.ts` |

Ordering glue: the maintenance poll runs a due afterglow first, then NIGHT, then AWAKE, and Alex's messages pre-empt. A live conversation is never interrupted. Spend ceilings: private Thought ≤ **12 calls/hour** (`private-budget/ledger.ts`), plus the model-spend ledger in `core/attention/` (quota buckets, tokens per minute).

**What's wrong with this, organically:**
- **Five clocks** (afterglow, NIGHT, AWAKE, P1, subscriptions) don't know about each other beyond fixed ordering.
- AWAKE wakes her every 3 h whether or not anything happened. That's Lyra's "journaling about stillness" failure.
- Nothing learns whether a wake was worth it. There's no habituation (a noisy feed stays as loud as on day one) and no novelty signal.
- She can say "remind me at 18:00" (future triggers), but **not "tell me when X happens"**. There's no condition-based, top-down attention.
- The budget is a hard wall (12/h), not a felt state: she hits it rather than feeling tired first.
- Mood (valence, energy, openness, tension) is shown to Thought but never shapes *what she notices*.

## A2. The design: one thalamus, many nuclei, one mind

Keep the durable machinery: ingress, inbox, wake ledger, cognition claim, fences, budget ledgers, the settlement contracts. It works, and it's the brainstem.

Replace **who decides when**:
- the eight independent rules become **nuclei** that propose;
- **one arbiter** decides.

```
 SOURCES (senses)            NUCLEI (deterministic, per source)          ARBITER (one, in the Host)          MIND
 ─────────────────           ─────────────────────────────────          ─────────────────────────           ────
 Discord (Alex)       ──►  social nucleus ─── ALWAYS_THROUGH ─────┐
 Discord (contacts)   ──►  social nucleus ─── salience ───────────┤
 conversation rows    ──►  reflective nucleus (afterglow pressure)┤
 clock + her rhythm   ──►  sleep nucleus (NIGHT pressure)         ├──► salience candidates ──► arbiter ──► ONE Thought turn
 her schedule/watches ──►  prospective nucleus (times + conditions)┤    (source, salience,        (threshold, fatigue,   (pass type chosen by the
 feeds/subscriptions  ──►  external nucleus (novelty × interest)  ┤     class, coalesce key,      mood, refractory,      dominant candidate; the rest
 her own state        ──►  interoceptive nucleus (senses)         ┤     deadline, refs)           coalescing, budget)    ride along as "also on
 idle time            ──►  boredom nucleus (replaces AWAKE)       ┤                                                     your mind", or wait)
 Domus (Windows helper thalamus, Part B) ──► Domus nucleus ───────┘
                                                                          ▲                                   │
                                                                          └──── "worth waking?" + watch-list ◄┘
```

### A3. The candidate

Each nucleus emits **salience candidates**, never Thought calls. A candidate has:
- `source`;
- `salience` (0–1);
- `class`:
  - `ALWAYS_THROUGH`: bypasses the threshold;
  - `PRESSURE`: rises over time until it crosses;
  - `OPPORTUNISTIC`: only if she's awake anyway;
- `coalesceKey`: so ten feed items become one candidate;
- `deadline`: when it becomes ALWAYS_THROUGH, e.g. the afterglow coverage edge or a commitment due time;
- `passType`: `conversation` / `afterglow` / `night` / `own_time` / `domus`;
- `refs`: evidence pointers only, no meaning.

### A4. The nuclei

| Nucleus | Replaces | Salience rule (deterministic) | Organic model |
|---|---|---|---|
| **Social** | ingress wake + social activation | Alex: ALWAYS_THROUGH (unchanged). Contacts: relationship basis × addressed-to-her × novelty. Room chatter habituates per room | orienting to your name |
| **Reflective** | the afterglow timers | **Afterglow pressure** = unreflected rows × time since the last message, rising faster for emotionally marked conversations (her appraisal in settlement). Coverage invariant: it becomes ALWAYS_THROUGH before any row can leave the window unreflected | the urge to go over what just happened |
| **Sleep** | the NIGHT timer | **Work-driven, not time-driven (Alex, 2026-09-30).** *Process S* (sleep pressure) accumulates from **work**: new episodes and memories formed, conversation volume, pending revision proposals, open expectations to settle. Time since the last NIGHT doesn't count. *Process C* (her learned quiet hour) only shapes *when* in the day she prefers to sleep once S is high. NIGHT fires when S × C crosses a **generous** θ. **No time floor.** A quiet day with little to consolidate means she simply doesn't need to sleep. The weekly "who I am becoming" arc runs on the first NIGHT at least 7 days after the previous arc. Thresholds get tuned later | sleep homeostat + circadian preference |
| **Prospective** | future triggers + commitments | Times she set: ALWAYS_THROUGH at due. **New: condition watches** ("when Alex comes back online", "when this feed posts about X", "when the Domus cake is done"), typed and structured (A6). Commitments: ALWAYS_THROUGH at due | prospective memory ("remember to…") |
| **External** | the subscription loop | Novelty × interest-branch match (from `memory/interests.ts`) × habituation per feed | noticing what interests you |
| **Interoceptive** | nothing (new) | Senses from the patch paper P3: friction, backup age, delivery backlog, the self-change queue, budget. **Mostly context, not wakes.** A wake only when a sense crosses a band (backup failing for 2 days) and she hasn't declined it | feeling your own body |
| **Boredom** | **AWAKE (3 h clock)** | Rises with idle time since her last own-time pass; the rise rate is modulated by mood energy × openness, and by how much is on her agenda (active concerns, strong interest branches). If she says "resting", it resets and rises more slowly next time | boredom, restlessness |
| **Domus** | nothing (new) | Accepts notifications from the Windows-helper thalamus (Part B). Game-specific prediction happens there; here they're merged | a new sense organ |

### A5. The arbiter (one, in the Host)

1. **Threshold θ(t)** = θ₀ × fatigue(budget spent today) × circadian(hour) × mood modulation.
   - **Fatigue:** θ rises smoothly as the day's private budget is spent, so tired Ashley notices less before she ever hits the hard wall. The 12/h ledger stays as the hard ceiling underneath.
   - **Mood:** low *energy* raises θ, so she's quieter. High *tension* lowers θ for the social nucleus only, so she's vigilant about people. Mood already exists (`growth/mood.ts`); this makes it *act on perception*, as affect does in organisms.
2. **Always-through** candidates skip θ. Alex's messages keep their current path untouched.
3. **Selection:** the highest salience wins. Its `passType` decides the pass, so each pass keeps its own output contract (afterglow, NIGHT and own-time contracts are unchanged). Compatible candidates **coalesce** into the same turn as "also on your mind" context; incompatible ones wait. This matches global-workspace theory: many processes compete, and one moment of awareness integrates the winners.
4. **Refractory:** per nucleus, after it fires, so there are no echo wakes.
5. **Existing laws unchanged:**
   - a live conversation is never interrupted by internal pressure;
   - a due afterglow still precedes NIGHT and own time;
   - the Host decides **when**, never **what**;
   - `PERIODIC_COGNITION_ENABLED` remains the master switch for all non-Alex wakes.

### A6. Her attention set (top-down), shared across nuclei

Each Thought turn may emit `attention.watch` items. These are structured, never free text parsed by the Host:
```
{ id, match: { source, kind, subject?, object?, predicate: eq|lt|gt|enters|leaves|changes|posts_about },
  action: wake | wake_urgent | suppress | quiet_until,
  expires: <time or event>, note: <her words, ≤200 chars> }
```
- **Limits:** ≤ 16 live items.
- **Safety:** `suppress` can never mute ALWAYS_THROUGH (Alex, commitments, the coverage edge, sleep floor, Domus danger).
- **Visibility:** shown back to her every turn ("you're watching for…"), so her attention is something she *knows* she's doing.
- **Scope:** one attention set works across Discord, feeds and Domus. "Tell me when Alex is back" and "tell me when the cake is done" are the same mechanism.

### A7. Learning ("was this worth waking me?")

- Every arbiter-woken turn adds one settlement field: `wake_worth: yes | no | sooner | later`.
- The arbiter keeps a slow, bounded gain per nucleus and per coalesce-key family: EMA, clamped to 0.5×–2× of the defaults.
- A feed she always says "no" to fades; a nucleus she says "sooner" to becomes more sensitive.
- The gains are visible to Alex (`/status` or `/attention`). They're a sense for her too.
- **Later option:** a small learned trigger model trained on her own labelled history, per [arXiv 2605.30152](https://arxiv.org/abs/2605.30152) (non-LLM triggers beat LLM triggers). It's evaluated offline on replays before any switch.

### A8. How we switch (Alex, 2026-09-30: switch directly, no shadow period)

1. **Before release, offline:** replay the last weeks of her real wake history (inbox events, conversation rows, the afterglow, NIGHT and AWAKE records in the sidecar) through the arbiter as a test.
   - Assert the invariants: Alex always gets through, no afterglow row leaves the window, commitments fire at due.
   - Report how the wakes would have differed. This is testing, not a waiting period.
2. **Release switches directly:** all nuclei at once replace the old schedulers.
3. **Kill switch:** one env flag reverts to the old schedulers without a deploy, in case something goes wrong live. The decision log (every candidate: fired or not, and why) makes any problem visible on day one.
4. Domus plugs in once E3 exists. It's just another nucleus.
5. **Naming:** `core/attention/` is today's model-spend ledger. The new module is `cognitive-v021/thalamus/`, and the spend ledger keeps its name (a rename would be a separate cleanup).

---

# Part B: The Domus thalamus (peripheral, in the Windows helper)

This is the **sophisticated** part, and it's built to be tested before it's trusted.

## B1. Placement and contracts

- **Where:** the Windows helper process, never the game (§19A: the mod does no network I/O, and heavy logic stays off the game thread).
- **In:** the probe's telemetry stream (JSONL tail, or local IPC once the command inbox exists).
- **Out, three channels:**
  1. **Notifications** to Mint (the Domus nucleus): `{type, salience, class, coalesceKey, percepts[], portraitRef}`.
  2. **Probe requests:** only the ones already qualified (pause/release per E2-P when she's alone and a T1 need fires).
  3. **Decision log:** every percept, its salience, fired or not, and why. This is the audit trail for "why did she wake?" and "why didn't she?".
- **Down from Mint:** her attention set (A6), budget and fatigue state, and co-play mode.
- **Pure core:** `(state, percept, now) → (state', decisions)`. No I/O and no clock of its own, unit-tested with a fake clock, like Awareness's `perception.py`. The helper owns the I/O.

## B2. Percepts (the helper's vocabulary)

These are typed facts from telemetry, never interpretations:

| Kind | Fields | Example |
|---|---|---|
| `need` | need, value, t_game | hunger 41 |
| `interaction` | id, affordance, target, source (PIE_MENU / AUTONOMY / SCRIPT / ours), membership, phase (queued/started/ended/cancelled) | 7223 sit started |
| `posture` | posture_name, target | sit on …055 |
| `presence` | sim, arrived/left, room | Sim X arrived, kitchen |
| `social` | actor, target, affordance | Alex's Sim → Ashley's Sim: Chat |
| `moodlet` | id, added/removed, magnitude | "Energized" +1 |
| `env` | time band, weather, hazard | fire on lot |
| `lineage` | the load/save classification | FORK |
| `gap` | telemetry missing for Δt | 12 s with no rows |

## B3. The forward model (prediction → surprise)

Per channel, a simple predictive model learned online. It's deliberately **not** an LLM.

- **Needs:**
  - A per-need decay rate `r(need, activity)`, learned by EWMA from observed deltas and seeded from the atlas cards (D1/D7).
  - Prediction `v̂(t) = v(t₀) − r·Δt_game`. Error `e = v − v̂`, normalized by a running σ, gives surprise `z = |e|/σ`.
  - **Band crossings** (below 50/30/15) are separate percepts.
- **Her action:**
  - Expected duration distribution per affordance class (median, IQR) from the atlas.
  - **Ended within expectation** → `ACTION_END`. That's not a surprise, but it's the natural "motor program finished" wake.
  - **Ended early, cancelled, replaced, or a foreign root** → high surprise.
- **Presence:**
  - Expected arrivals from game schedules: careers and school give household members' return times.
  - An on-schedule arrival is low surprise, an off-schedule one is high, and an **unknown Sim** is novelty (B5).
- **Social:** interactions targeting her Sim. Alex's Sim → ALWAYS_THROUGH. Others: relationship score × whether it's addressed to her.
- **Environment:** time bands are expected (low). Hazards → ALWAYS_THROUGH.
- **Lineage:** any load or fork resets the world model (it's a new "now") and triggers an orienting percept.

## B4. Habituation (Thompson & Spencer's properties)

Per stimulus key `k = kind + subject + object + value bucket`, a response weight `h_k ∈ [0, 1]`:
- each occurrence: `h_k ← h_k · (1 − α_kind)`, so it decays with repetition;
- between occurrences: `h_k ← h_k + (1 − h_k)(1 − e^(−Δt/τ_rec))`, **spontaneous recovery**;
- a change in the value bucket or target means a new key, so response is **stimulus-specific**;
- a strong unrelated event resets recent `h` partially (**dishabituation**).

Test case from tonight's evidence: the game's sit_Passive (14244) pings every 6–7 s after sitting. They must habituate to ~0 within about 5 repetitions and never cause a wake. This is replayed from the committed T1 telemetry, the same way A10's tests replay it.

## B5. Novelty (the orienting response, per Sokolov)

A familiarity store per world lineage holds how many times each Sim, object, place and affordance has been seen. Novelty bonus: `n = β / √(1 + count)`. It's strong the first time and fades. The store is **lineage-aware**: an undone branch doesn't count as having been seen, which matches Alex's "keep memories, marked undone".

## B6. Salience, arousal and the threshold

- **Salience per percept:** `S = h_k · (w_kind · z + n + topdown_k)`.
  - `topdown_k` comes from her attention set: a `wake` match adds a boost, `wake_urgent` → ALWAYS_THROUGH, and `suppress` → S = 0 unless ALWAYS_THROUGH.
- **Arousal:** a leaky integrator `V ← V·e^(−Δt/τ) + S`. When V ≥ θ, notify, then a refractory drop.
- **θ from Mint:** fatigue (the separate embodiment budget, as Alex decided), mood, and co-play mode.
  - In **co-play**, social weights go up and auto-pause is disabled.
  - When she's **alone**, a T1 need may request a probe pause (Alex's Q4).
- **Debounce and coalesce:** percepts within 1.5 s are batched into one notification. The payload is the delta since her last turn plus the present-tense portrait (D3).

## B7. The pressures (no clock)

- **ACTION_END:** her action finished as expected, and she decides what's next.
- **Boredom:** idle (no action of hers running), nothing salient, rising slowly. The rise rate comes from Mint (mood, agenda). "Resting" is recorded, the pressure resets, and it rises more slowly next time.
- **Liveness heartbeat:** the helper tells the Host it's alive every 30 s. It costs no tokens, **never wakes Thought**, and drives `MIND_ABSENT` / `GAME_ABSENT` truthfully.

## B8. Time: two clocks

- Predictions run in **game time**: needs decay in game minutes, and during SUPER_SPEED3 naps (~36× faster) they move fast.
- Arousal leak, refractory, debounce and fatigue run in **real time**, because cost and her experience are real-time.
- A nap at 36× produces game-time surprises quickly, but real-time refractory keeps it from becoming a storm of wakes.

## B9. Failure modes (all truthful, never fabricated)

- **Telemetry gap:** a `gap` percept; nothing is predicted across it as if it were seen.
- **Helper crash:** Mint sees the heartbeat stop → `MIND_ABSENT`, and the game plays on natively.
- **Clock jump** (Windows sleep): treated as a gap, followed by an orienting refresh.
- **Version mismatch** (probe/helper): telemetry only, no notifications that request actuation.

## B10. Learning, with Ashley's help

- She labels `wake_worth` (A7). The helper adjusts `w_kind`, `α_kind` and θ₀ within bounds.
- Decay rates and duration distributions are learned online from observed play, and seeded from the atlas.
- **Replay corpus:** every session's telemetry is committed evidence (tonight's included). A new thalamus version is replayed against the corpus before release: what would it have woken for, and does it still catch every T1? This makes the thalamus self-improving *and* regression-tested.
- **Later:** a learned trigger model trained on her labelled history (TGL-style), replay-tested against the rule-based thalamus before any switch.

## B11. Parameters (defaults, all tunable, all visible)

| Parameter | Default | Tuned by |
|---|---|---|
| τ (arousal leak) | 60 s real | learning, within bounds |
| θ₀ | set from the replay corpus so that ≤ 1 wake per ~3–5 real minutes of ordinary play, then tuned live | Alex (feel), learning |
| α_kind (habituation) | 0.3 (ambient), 0.1 (social), 0 (T1) | learning |
| τ_rec (recovery) | 10 min real | fixed v1 |
| β (novelty) | 0.6 | fixed v1 |
| debounce | 1.5 s | fixed |
| refractory | 20 s real | fixed v1 |
| boredom rise | from 0 to θ in ~15 real min of true idleness, slower after "resting" | learning + her declines |
| ALWAYS_THROUGH set | critical need band, hazard, Alex's Sim addressing hers, her action failed | Alex |

## B12. Tests before trust

1. The pure unit suite with a fake clock.
2. **Evidence replays:**
   - T1 (sit_Passive habituates; the sit completion is ACTION_END);
   - N5;
   - P4 (the nap at SUPER_SPEED3);
   - L3 (the zone change mid-session → lineage reset).
3. Connect directly (Alex: no shadow period). The decision log is on from the first session. Alex can rate a sample afterwards ("would you have wanted her to notice this?"), and those ratings feed B10 like her own `wake_worth` labels.

---

# Part C: Ashley as an organism: what we have, how well, what's missing

Scale: ●●● strong · ●●○ partial · ●○○ weak · ○○○ missing. "Planned" names the paper section that fills a gap.

## C1. Nervous system: sensing and attention

| Organ | Function | Ashley today | Status | Gap / plan |
|---|---|---|---|---|
| Hearing / social senses | perceive people speaking | Discord ingress, owner transport, contacts (`ingress/`, `social/`) | ●●● | — |
| Vision | see images | direct vision (Thought sees pixels) + a vision record for recall (`perception/`) | ●●● | — |
| Reading (PDF, attachments) | take in documents | `perception/pdf.ts`, `attachments.ts` | ●●○ | a bounded subset |
| Proprioception | sense her own body | none (Discord-only) | ○○○ | **Domus E3** (BodyState, portrait D3) |
| Interoception | feel her own state (health, budget, backlog) | diagnostics endpoints exist, but she doesn't *feel* them | ●○○ | **Patch P3** (senses with a decline state) |
| Nociception (pain) | "this hurts, avoid it" | failures recorded (`failure/`, `retry/`) but not felt as hers | ●○○ | **Patch P1** (friction ledger) |
| **Thalamus** | gate what reaches awareness | eight independent schedulers + a hard budget wall | ●○○ | **Part A + B** |
| Habituation | stop noticing the repetitive | none | ○○○ | **A4, B4** |
| Orienting reflex | notice the new | none | ○○○ | **A4, B5** |
| Arousal system (RAS) | overall alertness | fixed clocks; no arousal state | ○○○ | **A5 threshold** (fatigue, circadian, mood) |
| Cortex / global workspace | one coherent mind integrating many inputs | one Thought cycle, single-flight, everything flows into it | ●●● | coalescing (A5) |

## C2. Memory

| Organ | Function | Ashley today | Status | Gap / plan |
|---|---|---|---|---|
| Hippocampus (episodic) | remember what happened | episodes from the afterglow, conversation evidence | ●●● | — |
| Semantic memory | facts, beliefs | memory assertions + supports, recall by meaning (local embeddings) | ●●● | the S0 audit: the coverage contract |
| Memory strength / forgetting curve | used memories strengthen; unused fade in rank | `memory/strength.ts` (orders recall, never deletes); forget epochs | ●●● | — |
| Sleep consolidation | merge, re-score, integrate | NIGHT pass: merges, salience re-score, revision proposals, diary | ●●● | pressure-driven timing (sleep nucleus) |
| Autobiographical self | "the story of me" | continuity sidecar (lineage, sessions), weekly narrative, persona snapshots | ●●● | — |
| **Procedural memory** | *how* to do things, habits | none | ○○○ | **Patch P2** (practice layer) |
| Prospective memory | remember to do things later | future triggers, commitments | ●●○ | **condition watches** (A6) |
| Working memory | what's on her mind now | concerns and occupancy (`concerns/`), frontier | ●●○ | the attention set (A6) makes it explicit |
| Motor memory / skills | learned body skills | none | ○○○ | **Domus atlas** (D7), cards (D1) |

## C3. Affect and motivation

| Organ | Function | Ashley today | Status | Gap / plan |
|---|---|---|---|---|
| Limbic system / mood | a felt state that colours everything | mood: valence, energy, openness, tension, appraised by Thought, decaying to baseline | ●●○ | mood should **modulate attention** (A5), not only be shown |
| Dopamine / prediction error | learn from outcomes that differ from expectation | expectations → checked → lessons → can ground revisions | ●●○ | the Domus thalamus adds sensory prediction error (B3); `cognitive-graduation` (predictions, calibration) exists but looks dormant (C8) |
| Curiosity drive | seek the new and the interesting | interest graph (50 roots, branches grow only when lived), own-time reads | ●●○ | boredom → curiosity link (A4); atlas exploration (D7) |
| **Boredom / restlessness** | "nothing's happening, do something" | none: AWAKE is a clock | ○○○ | **boredom nucleus** (A4, B7) |
| **Fatigue** | do less as resources drain | a hard 12/h wall; no gradual state | ●○○ | **fatigue θ** (A5) |
| Attachment | a bond with her person | owner obligation, owner principal, relationship module, commitments | ●●● | — |
| Social drive | want other people | contacts (A3), DM gate, room activation | ●●○ | salience by relationship (A4) |

## C4. Rhythms

| Organ | Function | Ashley today | Status | Gap / plan |
|---|---|---|---|---|
| Circadian clock | a daily rhythm tied to her person's day | NIGHT hour learned from when Alex writes | ●●○ | shape θ(hour) too (A5) |
| Sleep homeostat (Process S) | sleep pressure builds with waking and learning | a fixed 24 h, min gap 12 h | ●○○ | **sleep nucleus** (A4) |
| Ultradian / idle rhythm | natural waves of activity | AWAKE every 3 h ± 20 min | ●○○ | replaced by boredom + events |

## C5. Self and values

| Organ | Function | Ashley today | Status | Gap / plan |
|---|---|---|---|---|
| Self-model | who I am | identity entries, the learned self, constitution | ●●● | — |
| Conscience / prefrontal inhibition | what I won't do | constitution, ethics, hierarchy, authority modules, honesty licenses | ●●● | — |
| Personality plasticity | change slowly, from evidence | revision layers with thresholds (opinion → trait → value/boundary with Alex) | ●●● | — |
| Metacognition | know how well I'm doing | persona snapshots, the weekly narrative | ●●○ | **gap analysis** (P7), `wake_worth` (A7) |
| Self-directed growth | choose where to grow | none (growth is emergent only) | ●○○ | **P7** (her dimensions, your seed) |

## C6. Action

| Organ | Function | Ashley today | Status | Gap / plan |
|---|---|---|---|---|
| Speech (Broca's area → motor) | say what she means | expression → rendering → speech outbox → delivery pump → receipts | ●●● | — |
| Speech proprioception | know it was actually said | delivery receipts, reconciliation, truthful failure notices | ●●● | — |
| Basal ganglia (action selection / go–no-go) | commit to one action | settlement + validation, capability-bound effects | ●●● | — |
| Hands / tool use | act on the world | Sandbox V2 (author, verify, export patch); external agency | ●●○ | production state UNKNOWN after the wipe (Patch S0) |
| Body / locomotion | move in a world | none | ○○○ | **Domus E3–E7** |
| Cerebellum (error-corrected action) | compare intended with actual movement | none for her own actions (Discord has no body) | ○○○ | **Domus claim ladder** (E2: ATTRIBUTED / MAINTAINED) is exactly this |

## C7. Body maintenance and survival

| Organ | Function | Ashley today | Status | Gap / plan |
|---|---|---|---|---|
| Metabolism / energy | a spend budget | private budget ledger, model-spend ledger, social resource fuse | ●●○ | felt as fatigue (A5) |
| Immune system | detect and repair faults | C3 recovery, retries, fences, reconciliation; Auditor (external) | ●●○ | internal self-check senses (P3) |
| Self-repair / growth of tissue | improve own structure | proposal-only improvement loop exists but has no motive or delivery | ●○○ | **Patch P4** (the Ashley-self pipeline) |
| **Genome / germline (survival of the pattern)** | survive the loss of the body | none: the Mint wipe cost continuity | ○○○ | **Patch P6** (break-glass backups) — first |
| Redundant organ (lifeboat) | survive the loss of one provider | one provider | ○○○ | **Patch P8** |

## C8. Possibly vestigial organs (import scan, VERIFIED; live use UNKNOWN)

These modules are **not imported by the v021 cognition** (`cognitive-v021/`). They're reached only through older core paths, diagnostics endpoints, or migrations:

| Module | Reached from | Reading |
|---|---|---|
| `cognitive-graduation` (predictions, calibration, adjudications) | `server.ts` diagnostics only | dormant; could feed the prediction-error loop if revived |
| `learned-autonomy` | `core/curiosity/reads.ts`, `core/relationship/projections.ts`, `server.ts` (diagnostics + a C3 contract assert) | alive through older curiosity/relationship paths, not through v021 Thought |
| `change-proposal`, `reflection/initiative` | `core/runtime.ts` | the older runtime; is it still on the served path? UNKNOWN |
| `context-allocation` | a type import in `mistral-client.ts` | vestigial (Mistral-era) |
| `learning/revisions` | nothing | stale; ported to `growth/revisions` |

Decision needed per organ: revive, fold into v021, or remove (C1-style cleanup, with the reachability scan). Carrying them silently is the drift the essence-lines (patch §7) are meant to stop. The patch S0 audit resolves the live-use question from production.

## C9. The summary

- **Strong:** memory, consolidation, self, conscience, attachment, speech, the single coherent mind.
- **Built but not felt:** interoception, pain, energy, immune. They exist as records and diagnostics but don't reach her as senses.
- **Missing entirely:**
  - **attention gating:** the thalamus, habituation, orienting, arousal;
  - **drives that aren't clocks:** boredom, fatigue, sleep pressure;
  - **procedural and motor memory;**
  - **a body** (Domus);
  - **survival of the pattern** (backups).
- **One-line diagnosis:** Ashley has a rich cortex and memory, but **no thalamus and no brainstem drives**. She's woken by clocks instead of by her own body and interests. The attention design (Parts A and B) plus P1/P3/P6 close most of that.

## References

- Borbély, A. (1982). A two process model of sleep regulation.
- Thompson, R. F. & Spencer, W. A. (1966). Habituation: a model phenomenon for the study of neuronal substrates of behavior.
- Sokolov, E. N. (1963). *Perception and the Conditioned Reflex* (the orienting reflex).
- Baars, B. (1988). *A Cognitive Theory of Consciousness* (global workspace).
- Crick, F. (1984). Function of the thalamic reticular complex: the searchlight hypothesis.
- Rao & Ballard (1999); Friston (2010): predictive coding / free energy.
- Park et al. (2023). Generative Agents ([arXiv 2304.03442](https://arxiv.org/pdf/2304.03442)): reflection when summed importance > 150.
- Altera (2024). Project Sid / PIANO ([arXiv 2411.00114](https://arxiv.org/pdf/2411.00114)): concurrent modules, one cognitive controller.
- *Do Proactive Agents Really Need an LLM to Decide When to Wake…* ([arXiv 2605.30152](https://arxiv.org/abs/2605.30152)): non-LLM triggers beat LLM triggers.
- Awareness (Hayes, Lyra, Caia): `haven/anchorage/perception.py`, `docs/TERMINAL_SENSORIUM.md`, `.claude/skills/attention/`.
