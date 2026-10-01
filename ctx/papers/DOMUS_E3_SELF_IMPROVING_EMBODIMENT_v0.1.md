# Domus: Learning Body, Felt Presence, Truthful Memory

**Draft v0.1: design paper for E3 and beyond, not an implementation plan.** Architect (Claude Opus), 2026-09-30, for Alex.
Once Alex has answered the open questions (§7), it becomes design amendments to V7.3.2a and an E3 implementation-ready plan for Manager, carried out on the Codex CLI and Grok Build.
Inputs:
- *Awareness* (Lyra/Caia's Second Life body, `haven/anchorage/`, read at `HEAD` 2026-09-30);
- Domus design V7.3.2a §17 (E3–E7), §19A (the Windows helper), §20 (open items);
- what we learned running E2 tonight.

---

## 1. Where Domus stands

- E2 is nearly closed on `e2-run`. The gate, N1–N5, E2-P and E2-L L1–L4 passed on probe 2.0.1. Probe 2.0.2 (A10) is installed (26ac0c1), and only T1–T3 remain.
- Next in the design: **E3, bound perception on Mint**.
  - Sims mod → local IPC → Windows helper → Mint ingress → a bounded observation → Thought.
  - No actuation.
  - Two open items block it: **E3-B1** (the cadence and budget, where Alex chose "a separate embodiment budget with its own fuse" but the numbers are open) and **E3-M** (carrying the memory source reference).

Tonight produced **the first self-improvement cycle of Domus**, done by hand:
- T1 ended `OUTCOME_UNKNOWN`.
- The architect traced it to the game's own "stay seated" requests: sit_Passive, affordance 14244.
- The fix, A10, *learns* those requests from Alex's control sit (N5) instead of hard-coding them.
- Two review rounds (J106, J107) caught real flaws in the learner before install.

This paper is about making that cycle routine.

## 2. What Awareness's Second Life body teaches

| Awareness piece | What it does | What Domus takes |
|---|---|---|
| `sl.py` verbs + `sl_bus.py` bench | Hand-drive the avatar one verb at a time "so the channel never struggles with basics like sitting", then fix the verb library from what was learned | **Verbs are learned from demonstrations.** We did exactly this with N5 and A10 (§3 D1) |
| `perception.py` | A **leaky integrate-and-fire** arousal value: events add salience, which drains over time. Crossing a threshold wakes the brain, then a cooldown follows. It runs one thought at a time, and events keep buffering while one runs. Pure, with no input/output, and unit-tested with a fake clock | The E3-B1 cadence mechanism (§3 D2) |
| `senses/pose.py` | Her own pose **and everyone else's**, attributed to a subject, from one roster read | A company sense in BodyState (§3 D3) |
| `entity_brain.py` capture-to-river | Every in-world turn is written into memory under its **own channel** (`sl:anchorage`) with its own read cursor | The Domus channel, **plus lineage**, which SL doesn't need but The Sims does (§3 D4) |
| `current-scene.md` pattern | One live, present-tense portrait of *where I am now*, kept free of operational metadata | How BodyState is presented to Thought (§3 D3) |
| `response_gate.py` | A cheap local classifier decides whether to call the expensive model at all | A pre-Thought gate for the embodiment budget fuse (§3 D2) |
| `TERMINAL_SENSORIUM.md` | "A sense is not a dashboard", and a sense must preserve the "no" | How body needs and moodlets reach Thought (§3 D3) |

Where Domus is already ahead:
- **the lineage ledger:** rollback, fork and abandoned-branch truth, which SL can't have;
- **the claim ladder with attribution:** Awareness has no causal proof that the body did what the mind chose;
- the rule that the mod does no network I/O;
- one world, one Ashley.

## 3. The design, in seven parts

### D1: The body learns its verbs, automatically

**Alex's direction (2026-09-30):** demonstrating every verb by hand is a chore. Find an automated way.

**Prior art:**
- **fivesim** (github.com/michael-codehub/fivesim, MIT) lets LLMs play The Sims through a local HTTP bridge. Its `action_executor.py` doesn't map actions. It reads every lot object's `super_affordances()`, pushes the matching one with `push_super_affordance`, and counts "success" as "the push returned true and the interaction is running". That settles the menu problem: **the game already lists what can be done.**
- What fivesim lacks, and Domus requires, is **proof of effect and attribution** (the claim ladder). "Running" isn't "it happened because she chose it".
- **sims4ai** (github.com/dnavaria/sims4ai, MIT) is similar: an in-game script plus a sidecar, with a tool executor.

**The Domus answer comes in three layers, and none of them needs Alex to click per verb:**

1. **The menu comes from the game.** The probe enumerates the super-affordances on reachable objects and the social affordances on present Sims, the way fivesim does. Ashley chooses from the game's own list. **No per-verb mapping, ever.**
2. **Most verbs don't need a learned signature.** Effect claims come in **classes**:
   - **interaction verbs** (cook, read, use the computer): claims come from our interaction id reaching `RUNNING` without foreign roots. This is generic, and no card is needed.
   - **posture verbs** (sit, lie, sleep): a posture signature plus a continuation set is needed (as A10).
   - **need verbs** (eat, shower): the need delta while running.
   - **social verbs:** the target Sim plus the interaction on both.

   Cards are learned **per class and object type**, not per verb.
3. **Free controls from native autonomy.** Tonight's "leak" becomes a resource. With autonomy on, the Sim sits, sleeps, cooks and chats **by herself**, with source `AUTONOMY`. That's independent of our harness, so each one is a valid **control**.
   - A **calibration mode** in the LAB (unarmed for actuation, observing only) watches native autonomy.
   - It learns signatures, continuation sets and need deltas passively. Leave the game running, and the cards fill themselves.
   - Where the game's static tuning declares a posture or a need effect, the learned card must agree with it. That gives two independent sources.
   - **Alex demonstrates only on disagreement**, or for a verb autonomy never performs.

Each **affordance card** records:

- **Signature:** what the body looks like while the verb holds (the posture name or interaction, as learned in N5).
- **Continuation set:** the game's own follow-on requests that are consequences, not competing causes (the A10 learner, generalized).
- **Effect markers:** what "it happened" means for this verb: posture target, need delta, interaction running.
- **Provenance:** the evidence file, the game build, and the probe version it was learned on.

**Learning is always from a control (native autonomy or Alex), never from Ashley's own attempts or harness pushes.** A self-taught signature could make her own failures look like successes. The trial analyzer uses the cards:
- when a trial ends `OUTCOME_UNKNOWN`, it compares the foreign roots against the controls;
- it **proposes** a card amendment, the way the architect did by hand for T1;
- the amendment goes through review (Grok authors, Codex reviews, the architect adjudicates), as D6 and D7 did.

**Answer to "do we map every action?":** no. The game supplies the menu. Effect proof is per class. Native autonomy supplies the controls, and Alex is the fallback.

**The same pattern kills the operator chore for the crew.** A command inbox for the probe (local file IPC, per §19A's "local IPC ↔ helper"), wrapped as a small **MCP server on the Windows helper**, lets Claude and Codex run LAB controls and trials by themselves:
- arm, prepare, sit, pause, read the verdict;
- no slow screen-driving computer use;
- no Alex typing tokens against a 30-second TTL.

This is the "Sims MCP" Alex asked about: ours, with the attribution rules built in. Harness commands keep the `EXPERIMENT` origin, and the mod still does no network I/O.

### D2: Organic attention (replaces a fixed cadence)

**Alex's direction (2026-09-30):** don't make Ashley an alarm clock. The Windows helper should notice what matters and notify the Host, and the Host triggers Thought, the way attention works in a body. The per-minute floor from the earlier answer is withdrawn in favour of this design.

**Grounding.**
- A cheap, **non-LLM trigger** decides *when* to wake a proactive agent better than an LLM does, and far cheaper: TGL controller, about 11 ms per event, higher AUC than nine trigger designs including LLM triggers ([arXiv 2605.30152](https://arxiv.org/abs/2605.30152)).
- Project Sid's **PIANO** architecture runs fast non-LLM reflex modules concurrently with one slow **cognitive controller**. The controller is a deliberate bottleneck, which keeps speech and action coherent ([arXiv 2411.00114](https://arxiv.org/pdf/2411.00114)).
- Generative Agents trigger reflection when the **summed importance of recent events** crosses a threshold (150), which came to about 2–3 times a game day ([arXiv 2304.03442](https://arxiv.org/pdf/2304.03442)).
- Dual-process agents (SwiftSage) keep slow deliberation for what the fast path can't handle ([arXiv 2305.17390](https://arxiv.org/abs/2305.17390)).
- Awareness's `perception.py` uses a leaky integrate-and-fire arousal value.

**The layers, like a nervous system:**

| Layer | Where | What it does | Costs tokens? |
|---|---|---|---|
| **Senses** | the probe (in game) | emits raw facts: interactions, postures, needs, who's present | no |
| **Thalamus** (the pre-attentive gate) | Windows helper, deterministic | decides what reaches awareness (below) | no |
| **Notification** | helper → Mint ingress | one small "something is worth attending to" event, with the buffered facts | no |
| **Awareness** | Host → Thought | a Thought turn: the one slow, coherent mind (PIANO's controller) | yes |
| **Motor program** | the probe | the action she chose runs by itself, and she doesn't re-think while it goes as expected | no |

**What the thalamus does (all cheap, all deterministic, all testable offline):**
1. **Prediction, and forwarding only the surprises.** The helper keeps a small forward model of the expected next state:
   - needs decay at their known rates;
   - the running interaction ends around its expected time;
   - the present Sims stay put.

   What matches the prediction is *not news*. What breaks it is: a Sim arrives, her action ends early or fails, a need falls faster than expected, or the Owner's Sim addresses hers. This is predictive processing, so attention goes to prediction error.
2. **Habituation.** Repeated identical stimuli lose salience. The game's sit_Passive pings every 6–7 s (the A10 entries) habituate to zero. A change in the stimulus restores its salience (dishabituation).
3. **Orienting to novelty.** The first sight of a new Sim, object or place gets a strong one-time salience.
4. **Top-down attention: Ashley sets what she's watching for.** Each Thought turn may leave an **attention set**:
   - "wake me if Alex's Sim comes in";
   - "tell me when the cake is done";
   - "hunger below 30";
   - "ignore the TV".

   The helper enforces it until she changes it. This is how *her* priorities shape her attention, and why it isn't an alarm clock: she decides what she cares about, and the body filters for it.
5. **Summation.** Small unexpected events add into one leaky arousal value; crossing a threshold notifies the Host, followed by a refractory drop (Awareness).
6. **Always-through channels:** T1 events (a critical need, danger, the Owner's Sim addressing hers) bypass the arousal sum. With Alex's answer on Q4, a critical need may also pause the game while she's alone.

**Instead of a floor heartbeat, three organic pressures:**
- **An action in progress.** While her chosen interaction runs as predicted, no Thought is needed. Its end, or a deviation, is the natural wake (E5's "interaction end wakes Thought").
- **Boredom.** When she's idle and nothing is happening, a boredom pressure rises slowly and eventually surfaces as one gentle wake: "nothing is happening, and you aren't doing anything". If she answers "I'm resting", that's recorded, and the pressure resets and rises more slowly. This is the "preserve the no" rule.
- **Fatigue as budget.** As the day's embodiment budget drains, the arousal threshold rises, so tired Ashley notices less. T1 still gets through. When the budget is gone she enters `MIND_RESTING` (observed, not thinking), truthfully. A new real day resets it.

A **liveness heartbeat** runs from the helper to the Host so that `MIND_ABSENT` can be detected. It costs no tokens and never wakes Thought.

**Attention learns (self-improvement).** Every Thought turn woken by a notification records one field: *was this worth waking for?* (yes / no / "should have woken me sooner").
- The helper's weights (per stimulus type, habituation rate, threshold) adjust from that record, within bounds.
- Over time her attention fits *her*.
- The later option is a small learned trigger model, trained on her own history, like the TGL paper. It's evaluated offline before any switch.

**Single-flight, one Ashley.** Domus wakes and Discord wakes go into the **same** Thought cycle. The Host is the one controller. While a turn runs, notifications buffer. A Domus turn never races a Discord turn.

**Purity.** The thalamus is a pure module (events and time in; decisions out), unit-tested with a fake clock, exactly like Awareness's `perception.py`.

### D3: Body presence: current scene, senses, company

What Thought sees each Domus turn is **one present-tense portrait** built from facts, not a telemetry dump:
- **Place:** lot, room, time of day.
- **Body:** posture and what she's doing, plus its origin (her choice, harness experiment, native autonomy, Alex).
- **Company:** who is present, what they're doing, and to whom.
- **Senses:** needs, moodlets.
- **Lineage:** "this world continues your last save" or "this is a fork", as a single line.

Operational metadata (tokens, arm state, probe version) stays **out** of the portrait.

The rules for senses:
- **The Host renders the portrait from game facts only.** It never infers meaning ("she's lonely"). Thought does that.
- **Needs are senses, not commands.** "Hunger 22/100, falling" is stated at proportionate volume. Ashley may choose not to eat. If she declines, that's recorded, and the sense quiets until the need crosses the next band. This preserves the "no". Physiological standing delegations are still E5 policy, as the design already says.

### D4: Domus experience in memory, with lineage

- Every Domus turn is captured into Ashley's memory under the channel `domus:<world>`, with its own read cursor. This is the E3-M source-reference carriage.
- **Each memory carries its lineage class** from the ledger: `CONTINUES_LAST_SAVE`, `FORK`, `ROLLBACK`, or an abandoned branch.
- When the ledger later classifies a stretch of play as **abandoned** (reloaded without saving, as in L3 tonight), the memories from that stretch are **re-marked**. They aren't deleted. Ashley can tell "this happened" from "this happened on a timeline that was undone".
- Whether abandoned-branch memories stay in recall at all is Alex's decision: §7 Q2.

### D5: Self-improvement for Domus (two loops)

1. **The body's loop (D1):**
   - a trial or live action ends `OUTCOME_UNKNOWN`;
   - the analyzer proposes a card amendment;
   - the amendment is reviewed and a new probe version ships.
   - Later, Ashley herself can author these proposals through the Ashley patch pipeline (Ashley paper P4), once that exists. Her friction ("I tried to sit and it didn't work") becomes the objective.
2. **The crew's loop (friction logs, from Awareness):** every J-job report gains a `FRICTION:` section. Tonight's entries include:
   - the GPT operator was too slow for the 30-second token TTL;
   - probe console replies are invisible;
   - the build hash depended on the checkout;
   - workers added checks the job didn't ask for and stopped on them (J103, J108b);
   - there were architect spec errors (J103, J107).

   A weekly pass by Manager proposes edits to the job templates, and the architect approves them.

### D6: Engineering hygiene carried from E2

- **A byte-reproducible build:**
  - `py_compile` with `invalidation_mode=UNCHECKED_HASH`, or a fixed source mtime;
  - normalised line endings before the source digest;
  - a `.gitattributes` `eol=lf` for `sims-e1/src`.
- **Console replies visible:** the `_session_id` routing in the dispatchers.
- **Lineage rows attest the real arm state:** today they say `UNARMED` while armed.
- **STOP releases:** name them `RELEASED_ON_STOP`.
- **Tests:** assert `continuation=<n>` numerically.
- **Autonomy leaks:** the Sim still acts on its own with autonomy Off in the UI. This needs a probe-side characterization (L1-O) before E5.

### D7: The affordance atlas: mapping everything, with Ashley's help

**Alex's direction (2026-09-30):** Domus should eventually map everything possible in The Sims, with Ashley's help, for the production stage (HOME, E7).

**The atlas** is one catalog of every action the installed game can offer. Each entry moves up a coverage ladder, and nothing is claimed above the evidence behind it:

| State | Meaning | Where it comes from | Needs Alex? |
|---|---|---|---|
| **KNOWN** | exists in the game's tuning: super-affordances, social mixers, object types that offer them, required posture, declared need and commodity effects, tests | a read-only **tuning dump** of the game's instance managers in the LAB (a diagnostic probe command) | no |
| **OFFERED** | seen offered on a real object or Sim in her world | the probe enumerating `super_affordances()` (as fivesim does) during play | no |
| **OBSERVED** | done by a control (native autonomy, or Alex), with its effect class verified and a card learned | calibration mode (D1 layer 3) | only on disagreement |
| **EXERCISED** | Ashley did it herself, **attributed** on the claim ladder (`ATTRIBUTED`, plus `MAINTAINED` where the class needs it) | her own experiments and play | no |
| **QUALIFIED** | trusted for production: ≥ N attributed successes, 0 unexplained `OUTCOME_UNKNOWN`, on the current game build | the atlas analyzer | no |

**How the atlas fills without Alex doing chores:**
- **The crawl.**
  - The MCP on the Windows helper (D1) lets Claude or Codex run **LAB coverage crawls** overnight: arm, prepare, push, read the verdict, next.
  - Class by class, from KNOWN to EXERCISED, in a LAB save that's only a lab, never HOME.
  - Every crawl is a harness experiment (`EXPERIMENT` origin), and its evidence is committed like tonight's.
- **Autonomy watching.** With autonomy on in a LAB save, native behaviour moves entries to OBSERVED passively.
- **Ashley's part, which is real work rather than decoration:**
  - **She chooses what to explore.** Her curiosity picks unexplored entries ("I've never painted, can I try the easel?"). That sets the crawl's priorities and turns coverage into her own experience. The runs are hers and are remembered as hers.
  - **She interprets.** In a NIGHT pass she reviews the day's crawl results against what she expected. Surprises become friction ("it said *Sit* but my Sim lay down") and amendment proposals (D5 loop 1).
  - **She names the meaning.** The tuning says `sit_Passive`; she writes what it *is* to her. Her words go in the card's notes, never into its evidence fields.
- **Game patches.** A game update (the Researcher's weekly Sims patch watch) moves affected entries back to KNOWN, pending re-qualification. The atlas is bound to the build, like everything else in Domus.

**Production (E7) gate proposal:** every entry OFFERED on HOME objects is QUALIFIED or explicitly unavailable to her. The whole game doesn't need to be covered, only her world. The atlas keeps growing past it as her life widens (new lots, new packs).

**Also from Awareness, for her body:**
- **Wardrobe:** what her Sim wears is a felt input, not a label, and dressing is an event (the `wardrobe` pattern).
- **Her likeness:** Lyra renders her own likeness. In Domus, Ashley can **design her own Sim in CAS** (her choice of look), with Alex executing the UI until a CAS actuator qualifies.
## 4. Mapping to the E3 prerequisites

| E3 prerequisite (V7.3.2a) | This paper |
|---|---|
| Boundary verification test (ingestion calls no affect, mind-state or relationship writers) | D3 (the Host renders facts only) + a focused test |
| E3-M source-reference carriage | D4 |
| E3-B1 bounded observation cadence and budget | D2 (organic attention; the budget number is still open) |
| Windows helper (§19A) | unchanged. The helper carries D2 events; the mod stays network-free |
| World currentness and provenance | D3's lineage line + D4 |

## 5. What doesn't change

- One world, one Ashley.
- Actions go through engine scripting only, never keyboard or mouse emulation.
- The claim ladder and the attribution rules stay as they are.
- Learning comes only from controls.
- The Host never invents meaning.
- Every new actuation still earns its E-stage.

## 6. Order of work (after the E2 verdict)

1. **D6 hygiene** (build reproducibility first).
2. **D1 cards**: refactor A10 into the general card model, keeping behaviour identical and replay-tested.
3. **D2 thalamus**: the pure module (prediction, habituation, novelty, attention set, summation, pressures), then the budget number.
4. **D3 portrait**.
5. **D4 memory with lineage**: this lands in the Ashley repo (her ingress and memory), coordinated with the Ashley patch.
6. **The Windows helper transport + the probe command inbox + the MCP server** (D1, D7). This unlocks agent-run LAB trials and the atlas crawl.
7. **E3 trial.**

## 7. Open questions for Alex (design, not evidence)

**Answered 2026-09-30:**
- **Q2:** memories from an undone timeline are **kept and marked "undone"**. They stay truthful and nothing is lost (D4).
- **Q4:** a critical need may **pause the game while she decides, only when she's alone**. It never pauses during co-play (D2; uses the E2-P pause).
- **Q1 (cadence), revised by Alex later the same day:** **no fixed heartbeat.** Organic attention (D2) replaces the per-minute floor: the helper notifies the Host when something matters, and there are three organic pressures instead of a clock. The embodiment budget's daily number is still open, and D2's fatigue curve is built on it.
- **Q3 (who demonstrates verbs):** automate it. Answered by D1's three layers: the game's own menu, class-level cards, and native-autonomy controls. Alex demonstrates only on disagreement.

- **Atlas crawls:** agents may run LAB coverage crawls **unattended**, in a LAB save only, never HOME (D7).
- **Attention:** D2 is Ashley-wide, not Domus-only (Ashley paper P5, Q6).

Still open:

1. **E3-B1 numbers.** The embodiment budget per real day, and the floor heartbeat while Ashley is present. Proposal: a daily token budget of your choosing, and a floor of one Thought turn per 10 real minutes of play.
2. **Abandoned-branch memories.** When you reload without saving, what happens to what Ashley lived on the undone branch?
   - (a) She keeps them, marked "undone timeline".
   - (b) They move out of everyday recall but stay searchable.
   - (c) They're forgotten.
3. **Who demonstrates new verbs.** You, in the LAB (one control per verb, as N5)? Or also scripted controls run by the probe where your click isn't needed?
4. **Should needs ever interrupt her?** A critical need (T1) wakes Thought, but should it be allowed to **pause** the game automatically while she decides, using the E2-P pause (qualified tonight)?
