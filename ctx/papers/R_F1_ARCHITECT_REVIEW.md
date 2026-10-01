# R-F1 architect review: plan amendments (in progress)

Source: `orchestra\outbox\R_F1_FUTURE_RESEARCH.md` (Sol medium, 2026-10-01). Archives: Ashley 6ad1aba, Domus 0605205, mirror 40fadf8.
Status: F1–F16 reviewed (the full copy arrived at 44,929 B).

## Ashley A5 (C3 learned-autonomy port): rescoped

The research overturns three plan assumptions (§Phase 4 C3):

1. **"≥3 lived origins" isn't readable today** (F1). `memory/interests.ts` `livedCount` counts touches, not distinct origins.
   - **Ruling:** an origin is a **distinct `cycle_id` in which a branch was touched.**
   - A5 adds a small sidecar receipt table, `interest_touches(branch_key, cycle_id, touched_at_ms)`, written next to the existing interest recording in aftermath. It's idempotent per (branch, cycle).
   - The proposal rule counts distinct cycles in it. There's **no backfill from `settlements.payload_json`**: payloads can be redacted, and a partial backfill would fake history. Counting starts when the table is deployed. The table is Host fact-recording only.
2. **C3 eligibility writes on read** (F1, `eligibility.ts:40–60`).
   - **Ruling:** the port splits it into a pure read plus an explicit state transition.
   - A ported test asserts that the read path makes no writes.
   - Any C3 test that relies on write-on-read is a STOP-and-report, not a silent port.
3. **The three choice-receipt decisions don't exist in v021** (F2).
   - **Ruling:** A5 records receipts only where an influence can act **today**: **own-time agenda ordering** (`initiative/agenda.ts`). In `observe` mode the receipt records the order with and without influence. Nothing changes the order until the Owner flips the mode.
   - `curiosity_rank` arrives with the thalamus external nucleus (Phase 5). That's where its receipts go, and A5 doesn't add it.
   - `motivation_admission` has no v021 counterpart. **Dropped** from the port and listed as retired.
   - The legacy consumers (`core/curiosity/reads.ts`, `core/relationship/projections.ts`) need a reachability answer first. **Follow-up research:** item R-F2.1.
4. **Split A5** into:
   - **A5a:** storage plus `interest_touches` plus the eligibility split;
   - **A5b:** the proposal rule, Thought positions and the agenda receipts;
   - **A5c:** the legacy-consumer rewiring or retirement, plus deleting `core/learned-autonomy/` and dropping the C3 tables (fail-closed, the A4 pattern), plus retiring `cognitive_maturation_contract_state`.

## Ashley Phase 5 (thalamus): T4 amendment

- **F8:** the bot never polls initiative status, so the plan's "kill switch re-enables the bot scheduler through the status endpoint it already polls" is false.
- **Ruling:** T4 adds a **versioned scheduler-handoff contract**. The bot polls a small `GET /initiative/scheduler` (owner/transport-auth) every N minutes. The response says who owns idle ticks (the bot or the thalamus) plus a contract version. The bot starts or stops its scheduler and acknowledges.
- The kill switch flips ownership back. Backup, drill and maintenance timers stay outside arbitration.
- Nine timing mechanisms are confirmed, and A1–A3 added no attention timers.

## Domus Phase 5: amendments

| Item | Plan claim | Amendment |
|---|---|---|
| P5.1 dump (F3) | A dump of all interaction tunings, size implied | **Split.** P5.1a: field whitelist (`is_super`, `is_social`, `target_type`, `allow_autonomous`, `allow_user_directed`, `_require_current_posture`, `posture_preferences`, `_static_commodities`, autonomy-commodity lists). Runs only after tuning completion, with no manager creation (skip if the manager is missing), cursor chunks, ≤5 ms measured per tick. P5.1b: LAB cardinality and latency acceptance. No numeric size promise. |
| P5.2 offered scan (F4) | `super_affordances()` is a pure getter | **Changed.** Explicit bounded scans only, never per poll. Record "offered to actor/context at time T", not "runnable". `potential_interactions` is excluded. Purity is gated by a LAB before/after audit. |
| P5.4 need cards (F7) | A need delta while running | **Changed:** a **net-effect estimate** with control windows. Read `get_change_rate` alongside the value. An ambiguous window (overlapping SIs, a missing observation) can't yield an attributed PASS. |
| P5.5b autonomy (F5) | Calibration runs overnight at high speed | **Owner-gated setup:** the Owner sets Full autonomy in game options, clears the selected-Sim autonomy disable, places Sims/objects, unpauses, and picks high speed in the UI. The probe only observes, logs the options and speed at start, and tracks liveness and gaps. **No setter calls** (`enable_autonomy`, `disable_autonomy` and `set_clock_speed` stay forbidden). |
| P5.6 crawl (F6) | One guid, one push | **Split.** P5.6a covers parameter-free super-affordances only, excluding picker families (`PickerSuperInteraction`, `SimPickerInteraction`, `ObjectPickerInteraction`) and anything that needs extra ids/kwargs or dialogs, rechecking the offer right before the push. P5.6b, explicit choice adapters per family, is later. |

**The LAB live-check list gains** the F3–F7 NEEDS_LAB reads: the tuning count and latency, the offered-scan before/after audit, the autonomy options and speed log, per-candidate class/MRO/AOP parameters, and the need-delta control windows. They're grouped into one agent-run LAB session after D13.

## F9–F16 rulings (after the full copy)

- **T4 replay (F9).** Split into two pieces, and the T4 acceptance no longer requires proof that historical holds satisfied T1:
  - a **partial historical replay** over admitted passes and event order, with a **coverage report** saying what can't be reconstructed;
  - **complete decision recording from the switch on**, in `thalamus_decisions`.

  The replay counts come from R-F2.2 (Mint, read-only).
- **Thalamus constants (F10).** T1 starts with a **parameter contract**: every constant with its units, a default, a learning bound and its source (paper section or "architect default"). Calibration against the R-F2.2 wake rates comes before release.
  - **The five-repetition criterion:** the acceptance becomes "ambient response ≤ 0.2 within 5 repetitions, without recovery". α=0.3 gives 0.168, so the paper's "~0" was loose; α is unchanged.
  - **The "sleep floor" contradiction:** the Owner's "no time floor" wins. "Sleep floor" in the suppress-safety list (organism :115) means that **sleep pressure past a hard ceiling** is ALWAYS_THROUGH. It's renamed "sleep-pressure ceiling", and there's still no time floor.
- **Self-change (F11).** Phase 6 gets a new first packet, **S0**:
  1. the exported patch must be a real unified diff (`git apply --check` passes in a test);
  2. the export writes a base manifest, and an empty or unreachable base commit fails closed;
  3. the private-budget ledger gets per-policy window, cap and clock constants, so `ashley.self_change.v1` really is 24 h.

  S2 (the courier) waits for S0. The courier clones enough history to hold the base, or fetches the base by SHA. Depth 50 isn't a guarantee.
- **Result ingress (F12).** `self_change_result` becomes its own packet, **S3a**: the trigger kind, the origin profile resolving to a private non-Owner profile, an authenticated poller, an idempotent per-changeset receipt, and recovery tests. The repo and deploy key stay Owner-gated, and PRs stay out of scope (a deploy key can't create them).
- **Weekly NIGHT (F13).** Phase 7 first fixes the weekly arc:
  - **7 days** (organism B, the Owner's design) instead of 156 h;
  - the weekly watermark advances **only after the narrative is stored**, so a failed or refused pass doesn't use up the week.

  Why NIGHT didn't run in G0's window is R-F2.3 (Mint, read-only).
- **Domus in Ashley (F14).** Phase 8 is split into three packets:
  - **8a**, a dedicated Domus ingress with its own token. It's not the bot token. The bind address and Tailscale reachability come from R-F2.4. The token is Owner-created.
  - **8b**, the lineage columns on episodes and assertions, plus every formation writer F14 lists. Undone-reclassification follows the derived records.
  - **8c**, a boundary tripwire over the F14 writer lists (affect, mind-state, relationship core and repair, commitment admission, social authority, `memory/fanout.ts`) **and** raw SQL writes to their tables. A perception admitted from the queue stays separate from a later Thought pass that legitimately authors on it.
- **Career and duration reads (F15).** P6.5 reads career schedules read-only. **No expected-end field:** ACTION_END prediction is learned from observed durations. The reads join the LAB check list.
- **Co-play (F16).** A design gap. Before P6.3 there's an explicit **co-play lease**: an Owner-set boolean bound to the helper session and world lineage, with an expiry. If it's missing or stale, the mode is unknown and there's no automatic pause. It's a small packet in Ashley and the helper, and the Owner sets it (e.g., `/domus coplay on`).

## Follow-up research (R-F2, Sol medium)

- **R-F2.1:** are `core/curiosity/reads.ts` and `core/relationship/projections.ts` (via `thought/domain-pointers.ts:7`) reached from v021's live Thought or initiative path? What do they do with C3 influences today (0 rows)? Is the clean move a re-point or a retirement?
- **R-F2.2 (Mint, read-only):** replay inputs and wake rates.
- **R-F2.3 (Mint, read-only):** why NIGHT didn't run.
- **R-F2.4 (Mint, read-only):** the agent bind address and Tailscale serve state.
- **R-F2.5 (source):** the minimal valid patch export (a native `git diff` in the candidate workspace, or a fixed renderer), and whether the bwrap sandbox has git available.
- **R-F2.6 (source):** the fastest `interest_touches` write point, plus the C3 test inventory mapped to the A5a/b/c split.

## R-F2 rulings (`R_F2_RESEARCH.md`, sha256 a7a27fe5…)

- **A5c:** curiosity's acquisition path and relationship's getter/recompute path are **live**. A5c removes only their C3 imports and fields (learned ranking, receipts, learned-ID binding), keeps the services, and adds the curiosity influence seam in Phase 5.
- **A5 inventory:** 8 tests plus 7 cross-module regression dependencies. `c3-interface.test.ts:60–91` (implicit write-on-read) is **redesigned** as an explicit refresh test, not ported as-is. `migration-54.test.ts` gets a new expectation when the C3 tables drop.
- **`interest_touches`:** written right after `thought/aftermath.ts:88`, inside the aftermath transaction, one row per grown branch ID, UNIQUE(branch_key, cycle_id).
- **T1/T4:** calibrate from the R-F2.2 rates (awake ≈ 8/day, afterglow ≈ 2.7/day, night ≈ 0.9/day on the dense span), with the denominator and coverage declared. Replay covers timing and codes only.
- **Phase 7:** NIGHT did run (Oct 1 04:01 TRT), so there's no liveness fix. The weekly 7-day, success-only repair stays, and **gate-code receipts per due evaluation** are added, since the history isn't retained today.
- **8a:** 3710 is loopback-only and there's no Serve config. The transport choice goes to R-F3 AC1. XQX's tailnet identity is NEEDS_OWNER.
- **S0:** use (a), trusted native Git rendering in an isolated worktree bound to an immutable sanitized base, plus an export manifest. Refuse a missing base, and never fall back to live HEAD. Sandbox git qualification is a separate NEEDS_LAB step.

Status: **review complete.** The plans get amended when each phase's packets are written; this file is the amendment list.
