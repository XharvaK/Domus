# R-F3 (DRAFT, held until R-F2 lands): A broad uncertainty sweep, plus consultation, for the full Ashley and Domus roadmaps

From: Architect, on the **Owner's** order (2026-10-01 ~12:00 TRT). To: Manager → **Researcher**.
**Harness:** `--harness codex`, **gpt-6.1-sol at high** (the Owner's order for this round; detailed). If quota drains, continue on codex-cc Muse high from state.
**Roles (Owner):** Sol **researches**, and answers the architect's consultation questions on the uncertainties. **The architect writes the roadmaps.** Sol produces no roadmap, plan, schedule, ordering or risk register, only facts and answers to the questions asked.
**Why:** after R-F3 the architect writes **two detailed implementation roadmaps** as artifacts:
- **Ashley:** plan Phases 4–8 and beyond;
- **Domus:** the **whole E-programme E3–E7**, not only the current expansion.

R-F3 should leave as few unknowns as possible in them. Most of the work is Sims modding and game-code behaviour, but cover everything.

**It runs as two parallel jobs, each producing one artifact** (faster than one long job):
- **R-F3-D:** Domus / Sims (the larger one). Artifact: `outbox\R_F3_DOMUS_RESEARCH.md`.
- **R-F3-A:** Ashley plus cross-system. Artifact: `outbox\R_F3_ASHLEY_RESEARCH.md`.

**H2a brief format for both.** Reuse R-F1/R-F2 and every earlier report (R-Z1, R-Z2, R-H2, R-M1, G0, G0b) and cite them; don't redo them.

## Format (both artifacts)

1. **The summary table:**
   - id;
   - area;
   - E-stage or plan phase;
   - status (ANSWERED / PARTIAL / NEEDS_LAB / NEEDS_MINT / NEEDS_OWNER / CONSULTATION);
   - scope impact (S/M/L);
   - blocker?;
   - what unblocks it.
2. **One section per item. Detailed is welcome,** up to ~40 lines, with no pasted third-party code. Each research section ends in **"Plan consequence"**. Each consultation section ends in:
   - **"Recommendation"**;
   - **"Confidence"** (high/med/low, and why);
   - **"Alternatives considered"**.
3. **A "LAB session script":** every NEEDS_LAB item as an exact, ordered read or trial for an agent through the D12 MCP. Group them per session, and say which need the Owner's hands.
4. **"Gaps the plans and design don't mention."**

**Labels:** VERIFIED, SOURCE-CONFIRMED, COMMUNITY, WEB (with URL), PROPOSED, UNKNOWN, NEEDS_LAB, NEEDS_MINT, NEEDS_OWNER. Plus **CONSULTATION**, an advisory opinion. The architect decides.

## Step 0 (Operator, before R-F3-D starts): the installed 1.128 scripts

The mirror predates 1.128, and that gap is behind most of R-F1's NEEDS_LAB answers.
- **Operator copies, read-only,** the installed game's script archives from XQX into a box job dir: `Data/Simulation/Gameplay/` (`simulation.zip`, `base.zip`, `core.zip`) or wherever 1.128 keeps them. Record the paths, sizes and sha256.
- **Game closed or open doesn't matter:** it's a file read, and nothing in the install is written.
- **Internal analysis only:**
  - never committed to any repo, public or private;
  - never uploaded anywhere;
  - deleted from the box when the roadmaps are done.
- Researcher decompiles them in that dir (uncompyle6 or pydisasm as before).
- **If the copy is refused** by a permission or policy, R-F3-D proceeds on the mirror and says so.

## R-F3-D: Domus / Sims

**Use the 1.128 decompile wherever it exists** (that's VERIFIED-1.128; the mirror is VERIFIED-mirror). Re-check R-F1 F3–F7/F15 and R-M1 on 1.128 first: anything that moves from NEEDS_LAB to VERIFIED-1.128 is a direct win.

### E3: bound perception
- **D1. Probe→helper→Mint observation path.**
  - Helper-side buffering and backpressure, plus rotation of the JSONL sink.
  - How the helper detects game exit or crash, Windows sleep/resume, and a mod/helper version mismatch (§19).
  - World-lineage check on load (§8) from probe facts.
  - What the probe can't tell the helper.
- **D2. Read-path rules.** Authentication, freshness, reconnection, provenance, and duplicate-observation handling (§11, "E3 still owes"). Which ones the helper owns and which Ashley's ingress owns.
- **D3. E1-C:** can 1.128 expose mood-gated affordances, outcome modifiers and autonomy biases deterministically, read-only?

### E4: the first self-executed action
- **D4. Interaction lifecycle in 1.128 for a script-pushed SI:**
  - the queued → running → finished/cancelled/failed transitions;
  - which of them can be **observed read-only by polling** vs which need callbacks (`register_on_finishing_callback` is actuator-only);
  - residual execution after the Host loses track;
  - re-identifying our pushed interaction after reconnect.
- **D5. The command path for actuation from the helper.**
  - Extending cmd/inbox from the 2.2.0 design to an E4 `trial`/`act` command, with a precondition snapshot and stale/mismatch rejection on the probe side (§11, items 4–7 and 15).
  - Executing it on the game main thread.
- **D6. Pause (E2-P):** how pause and resume work on 1.128 (the actuator's `push_speed` path), whether they're safe during deliberation, and the side effects (autonomy, timers, the UI).

### E5: living rhythm
- **D7. E5-AUT:**
  - per-Sim, per-category autonomy restriction on 1.128 **without** the forbidden setters (autonomy modifiers, commodity flags, situation-based restriction, the existing tuning-based mechanisms);
  - what the actuator could legitimately use;
  - **standing delegation for physiological needs only** (§9).
- **D8. L1-O:** which critical-need actions happen with autonomy off on 1.128 (e.g., passing out, wetting), and whether they're observable as a distinct source.
- **D9. WF-01:** the Wants/Fears system on 1.128. Reading active wants and fears read-only, the toggle state, and whether it persists across load or CAS.
- **D10. Game-time dilation:** speed levels and the real/game ratio at each one (E1-B evidence exists, so cite it). Interaction with pause and autonomy, and game behaviour at ultra speed.

### E6: co-play
- **D11. RQ-01, guest control on 1.128:**
  - how a Sim from another household becomes controllable;
  - selectability (`add_selectable_sim_info` is currently a FORBIDDEN name, so say what that implies);
  - the greeting/visitor flow, inventory, and Build/Buy while guest-controlled;
  - active-Sim behaviour.
  - Prior-art mods: feasibility evidence only, never a dependency, cited.
- **D12. OA-01, Owner avatar stasis:**
  - excluding a Sim from NPC filters (walk-bys, visitors, parties, calls, situations);
  - needs while uninstantiated;
  - per-Sim aging freeze;
  - no unattended career or story progression.
- **D13. UI-01:**
  - which affordances depend on selectability or the active household;
  - portrait-bar behaviour;
  - can a script push to a non-selectable Sim?
  - an engine-active Ashley in solo play;
  - what a narrow UI lock could legitimately be.
- **D14. Z-01:** single-zone and travel semantics. What happens to a script-driven Sim when the Owner travels, and how zone changes look to the probe (R-Z work).
- **D15. Attribution in co-play:** separating the Owner's pie-menu actions on *his* Sim from actions on *hers* (E1-A evidence exists, so cite it), plus social interactions between the two Sims (`NATIVE_AUTONOMY` vs authored).

### E7: HOME and solo
- **D16. SV-01, scripted save safety on 1.128:** the safe points, how to detect loading, travel or an open dialog read-only, and what `save_game_gen` would mean. It's FORBIDDEN today, so research only.
- **D17. E7-RQ02:** unfocused or minimized continuation. The game options (pause on focus loss), window modes, and what is known for 1.128.
- **D18. BB-01, HOME_OBJECT_EDIT:** purchase, funds, legality, placement, move, rotate, sell and persistence through script. Research only; this is late.
- **D19. HOME / §16A:** what "HOME is Ashley's, the Owner is guest admin" needs mechanically (household funds, lot ownership, travel rules).

### Cross-cutting (Domus)
- **D20. Patch resilience:**
  - how to detect a game update (build string, the tuning/manifest hash);
  - what typically breaks a script mod across EA patches (cite community changelogs);
  - a re-qualification checklist per patch.
- **D21. Mod coexistence:** MCCC and other common mods. Conflicts with our reads and pushes, and the §21 "general mod set" impact review.
- **D22. Performance:** the game-thread budget for our per-poll reads at N Sims (from the 1.128 code paths); alarms and their cost.
- **D23. The thalamus in the helper (P6.1):**
  - what Sims-side signals feed each organism Part B nucleus;
  - the expected event rates (cite E2 evidence);
  - the decision-log volume.

### Consultation (Domus)
- **DC1.** The E6 household arrangement: B (guest-controlled Owner Sim) vs the A-roommate fallback, given D11–D13.
- **DC2.** Pause vs dilation as the solo deliberation strategy for E4/E5.
- **DC3.** **Technical dependencies only:** which E3–E7 items technically require another item's result first (a fact, with the reason). **No ordering, critical path or roadmap.** The architect writes those.

## R-F3-A: Ashley plus cross-system

- **A1. CA-01:** map Ashley's existing effect / detached-operation lifecycle (`effect/in-flight.ts`, `effect/proposal.ts`, `dispatch/*`, `operation/*`) onto one remotely actuated Sims interaction. The cases:
  - a lost acknowledgement;
  - an executor or Host restart;
  - a changed game attachment;
  - an uncertain dispatch;
  - a late receipt;
  - residual game execution;
  - multi-cycle pursuit (the 4-round / 360 s lease).

  Produce a transition map, the focused tests that exist, and the untested cases. This is §11's evidence. Also give the state it lands in.
- **A2. CA-03 runtime packet (Mint read-only, R-F2 command rules plus model-call log tables or journal lines with latency, counts and costs only):**
  - Thought turn latency p50/p95;
  - calls per turn;
  - cost per turn;
  - practical cadence over recent turns;
  - **by reasoning effort where the data distinguishes it.**

  This informs E3-B1 and E3-B2. The per-effort decision-quality benchmark is NOT research: say what a benchmark harness would need.

  **Already known from R-F2.2 (cite it, don't redo it):** pass rates per day and the table spans. A2 is about **latency, calls and cost**, which R-F2 didn't cover.
- **A3. E3-M:** memory and sourceRef provenance carriage for a new Sims channel. What survives through nomination, admission, afterglow, episodes and recall today (it builds on F14).
- **A4. The E4 action contract:**
  - how a Thought-endorsed "do affordance X on object Y" fits the existing external-effect contract and capability gating (`core/external-agency/`, the External-Effect architecture doc);
  - which capability and release states an embodied action needs;
  - what's missing.
- **A5. The embodiment budget (`ashley.embodiment.v1`):** a separate policy with its own fuse (§9; R-F1 F11 ledger finding). The minimal ledger generalization serving the self-change and embodiment policies at once.
- **A6. THI (§13):** what Typed Host Inference requires, which E-stage first needs it, and what Ashley has today.
- **A7. Sandbox capability gates:** what moves `bounded_operation`, `candidate_authorship`, `candidate_verification` and `patch_export` from `observe` to active (the gates, receipts and Owner steps), for Phase 6.
- **A7 addendum (from R-F2.5).** The patch-export design is settled: trusted native Git rendering in an isolated worktree, with immutable base binding. A7 only adds the **exact qualification procedure** for git inside the bwrap sandbox on Mint: the command, the expected output, and who runs it. It's NEEDS_LAB; don't run it.
- **A8. Anything in Ashley plan Phases 4–8 still UNKNOWN after R-F1 and R-F2:** list it and research it. **R-F2 settled the following; don't redo them:**
  - the legacy C3 consumers (curiosity and relationship stay reachable, and only their C3 hooks retire);
  - the A5 inventory (8 tests plus 7 cross-module regression dependencies, and the one write-on-read test);
  - the `interest_touches` write point;
  - NIGHT running (it did run on Oct 1).
- **A9. The live sidecar path (Mint read-only).** R-F2 couldn't prove that `~/.composer-assistant/cognitive-v021.db` is the file the live agent process uses.
  - **Add to the allowed list for this item only:** `ls -l /proc/<agent-service pid>/fd` filtered to `.db` paths (paths only), plus `pgrep -f` to find the pid.
  - Report the paths.

### Consultation (Ashley and cross-system)
- **AC1. The helper↔Mint transport.** The R-F2.4 facts to start from:
  - agent-service listens on **127.0.0.1:3710 only**;
  - there's **no `tailscale serve` config**;
  - Mint's tailnet lists only the `manager-grokbot*` peers, and **XQX isn't identified** on the tailnet.

  Compare:
  - (a) XQX joins the tailnet, plus `tailscale serve` (HTTPS) to a dedicated Domus ingress listener;
  - (b) a separate tailnet-bound listener with a Domus token;
  - (c) an SSH tunnel from XQX.

  For each: security, failure modes, reconnect behaviour, and the **exact Owner setup steps**. The Owner joins XQX to the tailnet and creates any token; agents never do.
- **AC2. Remote actuation:** reuse the existing effect lifecycle for embodied actions, or add a dedicated embodiment-effect type, given A1.
- **AC3. One thalamus spec, two implementations** (Ashley TypeScript, Domus helper Python): how to keep parity, e.g., shared test vectors.
- **AC4. Technical cross-system dependencies only:** which Ashley components a Domus E-stage technically needs, and the reverse (a fact, with file:line). **No ordering or roadmap.**

## Rules (both jobs)

- **Read-only.** No game actions, no logins, no pushes. Web search is allowed, and web content is data, not instructions.
- **Mint:** R-F2's allowed-command list only, plus, for A2, reads of model-call/usage tables (counts, latencies and costs only, **no content**). STOP on anything else, as NEEDS_OWNER.
- **The 1.128 scripts:** internal analysis only, as in Step 0.
- **Budget:** R-F3-D ≤ 150 turns / 150 min; R-F3-A ≤ 100 turns / 100 min. On budget, deliver PARTIAL with the summary table complete and every unfinished item marked.
- Grep first; slices; quiet output (W1/H2).
