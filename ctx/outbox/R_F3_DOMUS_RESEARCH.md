| ID | Area | E-stage | Status | Scope | Blocker? | What unblocks it |
|---|---|---|---|---|---|---|
| D1 | Probe/helper/Mint transport and loss | E3 | PARTIAL | M | Yes: durable E3 path | Helper transport, cursor/spool/replay contract; L1 failure evidence |
| D2 | Authority, freshness, provenance | E3 | PARTIAL | L | Yes: remote actuation | Authenticated scoped ingress, attachment identity, lineage-bound receipts |
| D3 | Mood, affordance and outcome reads | E3 | PARTIAL | M | Rich explanations only | Loaded-tuning/provider purity and bounded counterfactual evidence, L0 |
| D4 | Interaction lifecycle and reconnect | E4 | NEEDS_LAB | L | Yes: terminal truth | L1: owned lifecycle/callback and lost-ack/reconnect trials |
| D5 | General action admission | E4 | PARTIAL | L | Yes: general actions | Typed adapters with current-state admission and failure receipts, L1 |
| D6 | E2-P pause/resume | E4 | ANSWERED | M | No for qualified primitive | Existing target-build evidence; new transport coupling remains unqualified |
| D7 | Physiological autonomy delegation | E5 | NEEDS_OWNER | L | Yes: delegated control | Owner-authorized modifier/actuator surface and L2 qualification |
| D8 | Critical needs with autonomy off | E5 | NEEDS_LAB | M | Yes: exception semantics | L2: target tuning, thresholds, sources and outcomes |
| D9 | Wants/fears and toggle/load/CAS | E5 | NEEDS_LAB | M | Conditional: those signals | L0: existing-slot reads across Owner UI toggle, load and CAS |
| D10 | Clock ratios, speeds and dilation | E5 | PARTIAL | M | Dilation only | Read loaded scale; L1 speed/latency measurement |
| D11 | Guest control, RQ01 | E6 | NEEDS_OWNER | L | Yes: arrangement B | Explicit guard decision for selectable-list mutation; L3 |
| D12 | Owner-avatar absence/stasis | E6 | NEEDS_LAB | L | Yes: promised stasis | L3: filter coverage, offscreen systems and identity-preserving return |
| D13 | UI control and engine selectability | E6 | NEEDS_LAB | L | If narrow UI lock is required | L3: per-interaction qualification and an authorized narrow input hook |
| D14 | Single zone and travel | E6 | NEEDS_LAB | M | Travel only | L3: rebind/currentness/outcome trials through teardown and arrival |
| D15 | Owner/native/authored attribution | E6 | PARTIAL | M | Human attribution only | Dual-body provenance plus owned-action map; L1/L3 |
| D16 | Save safety and safe points | E7 | NEEDS_OWNER | L | Scripted save only | Guard authorization; L4 state/lock/modal/completion qualification |
| D17 | Unfocused/minimized operation | E7 | NEEDS_LAB | L | Solo unattended claims | L4: target-client window-mode/focus matrix |
| D18 | HOME_OBJECT_EDIT transactions | E7 | NEEDS_OWNER | L | Automated edits only | Typed authorized edit surface; L4 funds/placement/refund/persistence |
| D19 | HOME, guest and funds authority | E7 | PARTIAL | M | Topology-dependent actions | Explicit HOME/household authority contract and L3 ownership reads |
| D20 | Patch detection and qualification | Cross-cutting | PARTIAL | M | Reliable patch gating | Actual installed-build/tuning/mod fingerprints, L0 |
| D21 | MCCC and mod coexistence | Cross-cutting | NEEDS_LAB | M | Full-mod-set claims | L5: exact-version/settings census and comparative trials |
| D22 | Polling and alarm performance | Cross-cutting | NEEDS_LAB | M | Production polling budget | L0/L5: main-thread duration and volume distributions |
| D23 | Peripheral thalamus Part B | Cross-cutting | PARTIAL | M | Unsupported signal families | Bounded lineage-aware deltas, qualified channels and log budget |
| DC1 | Guest B versus roommate A | Consultation | CONSULTATION | L | Decision remains conditional | D11–D13 authority and runtime evidence |
| DC2 | Pause versus dilation | Consultation | CONSULTATION | M | No for recommendation | Qualified pause primitive; failure-lease evidence for unattended use |
| DC3 | Technical dependencies | Consultation | CONSULTATION | M | Per capability only | Facts and reasons below; no ordering implied |

# R-F3-D — Domus / Sims uncertainty research

Research date: 2026-10-01. Read-only source snapshots: domus 0605205 (D11 head), ashley 2ea3ef7 (origin main); neither is evidence that a new D11 helper/probe is deployed. Packet: papers/R_F3_BROAD_RESEARCH.md, sections R-F3-D, Format and Rules. Research coverage: D1–D23 and DC1–DC3. This document supplies facts, limitations and consultation answers; “Plan consequence” states a capability implication, not a roadmap.

**1.128 source availability:** successful installed-archive staging, not mirror-only. game-1128/MANIFEST.txt reports build 1.128.90.1030, code version 1.200.000.718. The three archive SHA-256 values were independently checked against the manifest. base/core/simulation were unpacked inside game-1128/unpacked/ (440/137/2,965 entries). Selected modules were decompiled/disassembled only inside game-1128/dec/. No game code was executed and no third-party code is reproduced here.

**Evidence labels:** VERIFIED-1.128 means a fact visible in the supplied target-build bytecode; it does not establish live tuning, native DLL behavior or UI behavior. VERIFIED-mirror means the earlier mirror only. SOURCE-CONFIRMED means first-party repository code or a supplied recorded observation, distinguished explicitly below. COMMUNITY means creator/community evidence with a URL, not target qualification. PROPOSED means an unimplemented contract or research recommendation. UNKNOWN identifies an unanswered factual question. Status describes the item as a whole; a section can contain verified subclaims and unresolved runtime questions.

**Citation conventions:** game citations are module:class/function with original bytecode first/source lines where available. The corresponding target files are under game-1128/unpacked/ and game-1128/dec/. uncompyle6 produced some partial parser failures; selected xdis/pydisasm function output, rather than a partial decompile, is the authority for those findings. Domus “src/” citations below expand to domus/sims-e1/src/ashley_e1/. Helper citations expand to domus/helper/domus_helper/. Runtime evidence predates this read-only sweep; no fresh game trial is claimed.

## Target-build re-check: NEEDS_LAB → VERIFIED-1.128 subclaims

These are static subclaim upgrades from reports/R_F1_FUTURE_RESEARCH.md F3–F7/F15 and reports/R_M1_RESULTS.md. They do not promote an entire unresolved live item.

| Prior uncertainty | Target-build fact now verified | Remaining boundary |
|---|---|---|
| F3: tuning-manager enumeration and lookup | sims4/tuning/instance_manager:InstanceManager.types (487) returns loaded tuned classes; get (849) resolves a resource key and can register a tuning dependency | Installed tuning counts, full readiness and pack/mod contents are still L0 |
| F3: super/social classification | interactions/base/interaction:Interaction.is_super (4615), is_social (6006); super_interaction:SuperInteraction.is_super; social_super_interaction:SocialSuperInteraction.is_social (1710) distinguish base/super/social classes | Classification does not prove a legal target, parameters or successful tests |
| F4: offer discovery and provider boundary | objects/script_object:ScriptObject.super_affordances (1819) includes component/dynamic providers; potential_interactions (1897) reaches AOP tests and forwarding | Provider purity and installed offer sets are still L0; testing is not a routine pure read |
| F5: context source shape | interactions/context:InteractionSource (19) includes PIE_MENU, AUTONOMY, SCRIPT and SCRIPT_WITH_USER_INTENT; Interaction.source (5358), sim (5353), target (5432) are available | Source alone does not authenticate the human or distinguish all native/mod producers |
| F6: push boundary | sims/sim:Sim.push_super_affordance (4252) constructs an AOP and reaches test_and_execute (4271); no direct selectability check occurs in this body | Downstream tests, picker parameters and actual pushability remain L1/L3 |
| F7: current need drift | statistics/continuous_statistic:ContinuousStatistic.get_change_rate (617) returns non-decay change when present, otherwise decay; get_decay_rate (501) and base_decay_rate (648) expose the decay calculation | Units, critical tuning and causal attribution remain L0/L2; net drift is not a complete consequence model |
| F15: work/time fields | careers/career_base:CareerBase.current_level (389), _get_work_scheduler (683), start_time (686), current_work_duration (690), get_next_work_time (1132) exist; next-work lookup returns delay/start/end with scheduling exceptions | Delegated scheduler purity, calendar boundaries and live units remain L0 |
| F15: interaction timing limits | Interaction.start_time (6022) is stored timing; approximate_duration (4781) returns time_overhead | No universal predicted action end has been verified |
| R-M1: buff/mood iteration | objects/components/buff_component:BuffComponent.__iter__ (216), get_mood (904), get_mood_intensity (921); sims/sim_info:SimInfo.Buffs (2055) | Timeout and arbitrary component reads require their own purity check |
| R-M1: existing need instances | statistics/commodity_tracker:CommodityTracker.get_all_commodities (282) snapshots existing non-None values; base_statistic_tracker:BaseStatisticTracker.__iter__ (91) skips recovery placeholders; statistic:Statistic.get_value (263) has a base read path; ContinuousStatistic.get_value (315) updates an existing instance | Generic tracker lookup can create recovered statistics; continuous-statistic value getters can update values and notify deltas |
| R-M1: presence/body identity | sims/sim_info_manager:SimInfoManager.instanced_sims_gen (684), instanced_sims_on_active_lot_gen (691); SimInfo.get_sim_instance (2216), is_instanced (2230), is_selectable (815), is_selected (826) | Broad manager scans and hidden/LOD handling still need bounded live checks |
| R-M1: interaction containers | interactions/si_state:SIState.__iter__ (358), sis_actor_gen (361), all_si_gen (413); interactions/interaction_queue:InteractionQueue.__iter__ (515), queued_super_interactions_gen (1736) | A poll cannot recover terminal events that disappeared between samples |
| R-M1: need metadata | statistics/commodity:Commodity.min_value (2192), max_value (2185), best_value (2201), UI visibility metadata (2336) | Not every statistic is a physiological need; loaded tuning/pack categorization remains necessary |

**Safety corrections, verified on 1.128:** BaseStatisticTracker.get_statistic (468; recovery branch 480–491) can force add=True, update recovery bookkeeping and call add_statistic/on_recovery even when its caller supplied add=False. get_value (525) delegates to that path. Buff.get_timeout_time (1922) delegates through get_commodity_instance (1882; tracker call 1893), so it inherits this issue. This corrects the blanket read-purity assumption; no claim is made that the behavior was introduced by 1.128.

ContinuousStatistic.get_value (315; call at 321) invokes _update_value (677), which can notify_delta (738), store _value (740) and clamp (741). Existing-instance enumeration avoids recovery creation but does not make this polymorphic value getter pure. A strict observer can read cached value plus last-update ticks and expose its age; a fresh native lazy-update read requires an explicit purity-policy decision and qualification.

WhimsTracker.get_active_whimset_data (582) clears active data and unregisters/registers event handlers. It is unsuitable as an observer getter. Existing slots via slots_gen (565), empty-slot flags and already-stored goal/target fields are the narrower read candidate.

**Additional R-H2 target confirmation:** core/sims4/commands:output (174) is the no-op wrapper; cheat_output (186) reaches native output; raw registration (118) and wrapper invocation (383, _session_id keyword) confirm the earlier console-wrapper boundary. No live console invocation was performed.

## D1 — Probe → helper → Mint, buffering and failure

**Status / scope:** PARTIAL / M. **SOURCE-CONFIRMED:** helper README describes a Windows stdio MCP with local-file IPC and no network client/listener. The E3 Mint connection, credentials, upstream acknowledgments and durable outgoing buffer are absent from this helper, not inferred from the existence of MCP tools.

Helper telemetry.py:latest_session (12) chooses by filename/mtime; segments (21) orders numbered rotations; file_rows (34) rejects malformed rows and ignores an unterminated final row. tail (43) retains a bounded result deque but rescans history for every call. n≤10,000 limits returned rows, not bytes scanned or duplicate delivery. A rotation gap is not a delivery acknowledgment.

src/writer.py sets a 1,024-row queue, 8 MiB active file, four rotated siblings, 200 MiB directory cap and five-second flushing (initial constants). Queue exhaustion increments drop counts (282); sequence assignment occurs at write (460); cap/rotation exhaustion stops with CAP_REACHED (518). Probe capture drops mark incomplete evidence, not successful backpressure.

src/probe.py:_start_inbox_pump (229) and polling use real-time alarms, cross_zone=False; shutdown/zone changes require bootstrap/rebind. Helper mcp_server.py:game_running (28) is a tasklist process-name test, not a PID-birth, exit-reason, crash-versus-quit or sleep detector. OS sleep, stopped rendering, failed probe and transport loss cannot be distinguished solely by an absent row. The helper README still describes manual inbox startup while the D11 probe source has zone-triggered startup; source presence does not qualify actual deployment or bootstrap recovery.

**PROPOSED:** preserve attachment/session/segment/sequence identifiers, an independent helper spool and acknowledged cursor, explicit drop/cap/gap records and bounded replay. Report current attachment health separately from historical rows. Probe cannot authoritatively infer Mint sleep, human presence/consent, remote credential revocation or memory ancestry.

**UNKNOWN / LAB:** L1 checks helper disappearance, retained rows and late replies; advanced crash/sleep diagnostics need helper attachment instrumentation. No full end-to-end E3 path exists here to test.

**Plan consequence:** E2 telemetry is useful input evidence; it does not establish durable, backpressured or reconnect-safe Mint ingestion.

## D2 — Authentication, freshness, reconnection and lineage

**Status / scope:** PARTIAL / L. **SOURCE-CONFIRMED:** src/cmdbox.py:closed envelope validation accepts only the fixed command set, 4,096-byte messages, bounded issue/expiry times, issuer syntax and replay identifiers. Helper commands.py:envelope (27) uses a UUID and 30-second TTL; send (39) writes/fsyncs an exclusive temporary file then atomically renames it into the inbox. Reply identity/issuer checks are local correlation, not cryptographic sender authentication.

The helper waits 15 seconds while the game envelope can remain valid for 30 seconds. A caller timeout can therefore precede a later valid execution. src/probe.py inbox handling (311–366) persists done markers, but dispatch occurs before reply/done persistence. A crash in that interval leaves an effect-without-durable-receipt window. The local replay guard does not prove exactly-once world effects.

src/e2_lineage.py:classify (36) compares designated Sim ID, save GUID/slot and loaded ticks with its ledger. It distinguishes continuation, rollback, unobserved save, fork, lineage transfer and foreign/body mismatch cases. External edits, unobserved saves and remote memory rollback are not exhaustively proven by those identifiers.

**PROPOSED boundary:** helper owns authenticated remote ingress, principal/scope, durable receipt/spool, version/attachment binding and transport deadlines; probe owns last-moment game-thread target/lineage/snapshot checks and execution receipts. Include expected attachment, zone generation, designated body, accepted snapshot revision, action ID and expiry. Remote receipt status must distinguish rejected, accepted, pushed, terminal and outcome-unknown.

**UNKNOWN / LAB:** L1 lost-ack/reconnect checks; E3 auth/revocation requires a real ingress contract, not an extra issuer string in the present file envelope.

**Plan consequence:** a remote caller cannot treat helper acknowledgment, a syntactically valid issuer or a recovered old snapshot as current permission to act.

## D3 — Read-only mood gating, outcomes and autonomy biases

**Status / scope:** PARTIAL / M. **VERIFIED-1.128:** sims/sim_info_tests:MoodTest.__call__ (1275) compares a subject’s mood against the configured mood/disallow mode and can mark an Actor result as influenced by active mood. That establishes one concrete gating mechanism, not a universal inverse index of mood-enabled actions.

buffs/buff:Buff.get_success_modifier (1129) returns its tuned scalar divided by 100. autonomy/autonomy_modifier:AutonomyModifier exposes score/static-commodity/affordance/tag modifiers. These are inputs into larger tests, scoring and outcome calculations; one scalar is not the aggregate success probability.

F3/F4 show loaded class metadata and offered affordances can be enumerated, but component providers, AOP tests, participants, picker branches and outcome execution can reach impure or expensive code. A generic “read every test/outcome” operation is not authorized by naming it a getter.

**PROPOSED read product:** expose current mood, whitelisted static gating metadata, known offered class IDs and explicit unknown preconditions. Attach build/tuning/mod provenance. Report limited, evidence-backed bias descriptions rather than complete counterfactual outcomes. Never instantiate buffs, apply modifiers or execute outcome/test pipelines merely to explain them.

**UNKNOWN / LAB:** L0 compares capped installed mood-tagged classes/offers and checks no tracker/event-registration growth during repeated observer reads. Mod-sensitive provider purity and actual legal actions remain unsettled.

**Plan consequence:** basic mood/context explanations are feasible; complete mood-to-action and outcome-probability cards require narrower qualified families.

## D4 — Queued, running, finished, canceled, failed and reconnect

**Status / scope:** NEEDS_LAB / L. **VERIFIED-1.128:** Interaction.queued (5847) identifies QUEUED pipeline state; running (5864) uses the run-element child handle. is_finishing (8499) delegates to the finisher; finishing_type (9255) exposes finishing history. InteractionFinisher.is_finishing (138), is_finishing_naturally (196) and finishing_type (203) expose the first recorded reason.

FinishingType (11) distinguishes NATURAL, USER_CANCEL, FAILED_TESTS, TRANSITION_FAILURE, TARGET_DELETED and other endings. NATURAL does not itself prove the application-level goal succeeded. A disappeared interaction with no retained terminal event is UNKNOWN, not automatically finished or canceled.

**SOURCE-CONFIRMED:** src/e2_actuator.py:watch_finish (68) uses register_on_finishing_callback; the guard confines callback installation to this actuator. E2 records owned interaction IDs and callbacks. Polling SI/queue containers is appropriate for observational membership; it cannot guarantee short-lived terminal reasons across sample gaps. Observer code must not install arbitrary callbacks.

**PROPOSED:** correlate an act ID with attachment/zone/body, engine interaction ID, affordance/target, source and start time; persist receipts independently of the in-memory object. SCRIPT_WITH_USER_INTENT and numeric interaction IDs alone are insufficient across reload/process replacement. After lost acknowledgment, query the existing act record and current object before any redispatch; unresolved residual execution stays OUTCOME_UNKNOWN.

**LAB:** L1 observes one qualified sit through queue, run and callback, then disconnects/reconnects the helper without replay; a separate Owner interruption observes the actual finishing reason. General adapter cases remain prerequisites, not existing MCP capabilities.

**Plan consequence:** E4 needs retained owned lifecycle evidence; “missing from queue” cannot supply terminal truth or safe retry.

## D5 — Generalized action/trial admission

**Status / scope:** PARTIAL / L. **SOURCE-CONFIRMED:** src/e2_admission.py:check (40) checks sampled state, lineage, designated body, target presence/offers, learned signature, busy state and non-paused state. fingerprint (83) includes save/body/posture/object/offer-count/busy facts. TokenBook (100) limits tokens to eight, 30-second TTL and single use; admit (141) rechecks fresh state and the fingerprint.

This is a qualified sit adapter, not a general act-by-GUID contract. “Same offer count” cannot prove unchanged full affordance eligibility, hidden target state or parameters. A snapshot without attachment/zone generation can survive a remote reconnect incorrectly.

**VERIFIED-1.128:** Sim.push_super_affordance (4252) reaches AOP.test_and_execute; picker interaction paths have their own candidate and UI logic. A recipe, Sim picker, service, object picker or travel affordance can require parameters that a raw class ID and target cannot supply.

**PROPOSED:** separate discovery from a typed family adapter’s preconditions, parameters, tests and result semantics. Recheck on the simulation thread immediately before pushing. Bind trial/admission to attachment, lineage, body, zone, target identity and snapshot revision; reject mismatch/staleness explicitly. Do not use forbidden cancellation as generic cleanup.

**UNKNOWN / LAB:** L1 distinguishes stale-token rejection before push, target deletion/changed posture rejection, push failure and terminal failure using qualified adapters. A generalized adapter is not present and cannot be exercised via today’s sit command.

**Plan consequence:** general E4 control requires family-specific admission and receipts; existing E2 tokens establish the pattern only for their qualified action.

## D6 — E2-P pause/resume and side effects

**Status / scope:** ANSWERED / M for the E2-P primitive, not unattended E3 coupling. **SOURCE-CONFIRMED target runtime:** domus/sims-e1/evidence/E2_N_P_L_OWNER_2026-09-30_01/session.md:42–47 records frozen game ticks for 36 seconds, release to Normal at approximately 1,000 ticks/second, an Owner 1x UI override, pause during native SUPER_SPEED3 and release back to that native speed, and STOP releasing the request. Save hashes were unchanged.

domus/sims-e1/evidence/E2_VERDICT_2026-10-01.md:1–55 identifies build 1.128 throughout and E2-P MET. The pause/admission/actuator path qualified on probe 2.0.1 was unchanged for 2.0.2. This is not runtime qualification of helper 2.2.0 or a new Mint link. Architect acceptance and pending Owner acceptance are distinct.

**VERIFIED-1.128:** clock:GameClock.push_speed (403) adds a source-specific request; remove_request (421) removes that request. _update_speed (246) reconciles requests, broadcasts UI state and has SUPER_SPEED3 NPC behavior (276). src/e2_actuator.py:push_pause (73)/remove_pause (79) uses this approved pair; no forbidden global speed setter is needed.

TimeService.update (107) advances the simulation timeline from game clock and the wall timeline from server clock. Pause is not an OS/UI/network/realtime freeze. A competing Owner request can change actual speed while the probe’s request remains recorded.

**Remaining limit:** helper death does not itself prove the game removes a live pause request. Unattended use requires observed actual speed, request ownership and a qualified failure/expiry policy, covered by L1.

**Plan consequence:** bounded pause and owned-request release have target evidence; treating pause as universal freeze or a crash-safe remote lease does not.

## D7 — Autonomy control without forbidden setters

**Status / scope:** NEEDS_OWNER / L. **VERIFIED-1.128:** autonomy/autonomy_modifier:AutonomyModifier.apply_modifier (985) delegates to StatisticComponent.add_statistic_modifier; remove_modifier (988) removes it. affordance_suppressed (998) distinguishes autonomous/user-directed filtering and retains an ALWAYS_WHITELISTED_AFFORDANCES exception. Modifier construction can include statistics, scoring, affordance/tag filters, locks and decay effects.

objects/components/statistic_component:StatisticComponent.add_statistic_modifier (497) can create statistics, alter values/convergence/decay, lock statistics and trigger suppression checks; removal (856) is not evidence of complete rollback. Commodity flags and scoring exclusions are narrower than an authority firewall. Role/situation assignments also change the Sim’s state.

autonomy/autonomy_component:AutonomyComponent._get_appropriate_autonomy_setting (1474) considers global, role, tutorial, per-Sim and household settings. A single category mask cannot be assumed to override every native push.

**SOURCE-CONFIRMED authority:** domus/sims-e1/tools/check_guards.py:21–46 forbids disable_autonomy/enable_autonomy and confines six actuator-only calls to e2_actuator.py. Current closed adapters do not authorize arbitrary modifier writes. A modifier is not a read-only loophole around that constraint.

**PROPOSED:** an explicitly Owner-authorized typed physiological delegation capability, with a defined allowlist, revocation/expiry, observable excluded categories and native critical exceptions. Social, aspirations, shopping and general initiative are not included merely because they share autonomy machinery.

**OWNER / LAB:** Owner decides whether a narrow modifier capability is authorized. L2 then measures actual offered/pushed categories, rollback and critical exceptions; no forbidden setter or speculative mutation is invoked by this research.

**Plan consequence:** category-level delegation is plausible in engine structure but cannot be claimed safe or authorized from modifier availability alone.

## D8 — Critical needs despite autonomy off

**Status / scope:** NEEDS_LAB / M. **VERIFIED-1.128:** statistics/commodity:Commodity._enter_distress (1696) creates a high-priority AUTONOMY context; _commodity_fail (1824) uses SCRIPT with Critical priority. Commodity state/threshold listeners (including registration at 1224) can trigger these paths without the ordinary full-autonomy chooser.

Therefore ordinary autonomy-off does not establish “no native actions.” The supplied E2 verdict also records need-driven activity with autonomy off. That observation is not a target-build pass-out/wetting/food/sleep exception matrix.

The failure source is ordinary SCRIPT, not a unique “critical physiological override” tag. Other system or mod authors can use SCRIPT. AUTONOMY likewise includes idle/subbehavior activity. Source must be combined with owned receipts, tuning identity, critical threshold transitions and target/body facts.

**UNKNOWN:** exact installed energy/bladder failure affordances, thresholds, hysteresis, visibility/rabbit-hole branches and whether they trigger in selected, unselected and offscreen states. Script archives do not provide a complete installed .package tuning census.

**LAB:** L2 observes Owner-prepared low-energy and low-bladder LAB states without setters, compares UI autonomy-off/on and records need value/drift, threshold tuning, interaction ID/source/priority and actual outcome. Unknown provenance remains unknown.

**Plan consequence:** physiological delegation needs an explicit native-exception policy; “autonomy off” cannot be its sole safety invariant.

## D9 — Wants/fears, UI toggle, load and CAS

**Status / scope:** NEEDS_LAB / M. **VERIFIED-1.128:** SimInfoManager.are_whims_enabled (1074) reads the stored option. load_options (162) reads show_wants through a setter; save_options (167) writes it. WhimsTracker load (870)/save (980) handle goal/whim/target persistence, including cached NPC data.

WhimsTracker.slots_gen (565) exposes existing slots; WhimSlotData.is_empty (400) checks the stored goal instance. The apparently convenient get_active_whimset_data (582) clears/rebuilds active data and event registrations; it must be excluded from observation. show/hide/set_enabled (526) are mutations.

_try_get_source_fear_from_whimset (1406) searches FEAR traits against a whimset. A negative want or a hidden slot is not automatically an active fear. Stored trait identity, source whimset and existing goal/slot state need separate evidence.

**PROPOSED:** return existing slot/goal/target identifiers with empty/hidden/option/LOD indicators, and independently expose qualified FEAR-trait/goal associations. Missing data is not “no desires.” Do not generate whims, switch their option or register listeners to populate reads.

**LAB:** L0 reads before/after Owner UI toggle, save/reload and CAS entry/exit with persistent Sim identity. Check both active and cached/uninstantiated behavior and that repeated observer reads do not alter goal registrations.

**Plan consequence:** Wants/fears are feasible signal families but require a safe existing-data adapter and explicit option/LOD semantics.

## D10 — Clock ratios, speed modes and solo dilation

**Status / scope:** PARTIAL / M. **SOURCE-CONFIRMED target runtime:** domus/sims-e1/evidence/E1_ADJUDICATION_2026-09-29.md:24–25 records Normal ≈40 game minutes per real minute, 1,500 ticks/game-minute and ≈1,000 ticks/real-second across six runs within 0.6%. E2-P also observed native SUPER_SPEED3.

**VERIFIED-1.128:** GameClock.current_clock_speed_scale (482), _clock_speed_to_scale (492); TunableClockSpeedMultipliers.__init__ (763) has defaults speed2=3, speed3=7, SUPER_SPEED3=36. Derived default rates are 120, 280 and 1,440 game-minutes/real-minute. These are default-derived values, not four measured target-client rates; loaded tuning and mod overrides can change them.

At advancing Normal, L real seconds consume approximately (2/3)L game minutes; at default SUPER_SPEED3, approximately 24L. A 60-second deliberation can consume 40 game minutes or 24 game hours respectively. No actual Mint latency distribution is assumed.

**UNKNOWN:** loaded multipliers at this installation; selected/unselected autonomy behavior at each mode; future slower-than-Normal scaling. Current guard forbids set_clock_speed. Game-time calibration mods can also alter durations, calendar alarms and existing scheduled events (D21); this is not merely a faster/slower UI label.

**LAB:** L1 uses Owner UI speed changes and reads actual scale/ticks/wall intervals, including sleep-induced speed and pause. Optional dilation needs an expressly qualified mechanism, not an invented MCP setter.

**Plan consequence:** time budgeting must use observed game ticks and actual scale; Normal is already fast enough that remote deliberation materially ages the world.

## D11 — Guest control RQ01, greeting, inventory and Build/Buy

**Status / scope:** NEEDS_OWNER / L. **VERIFIED-1.128:** server/client:Client.add_selectable_sim_info (401), remove_selectable_sim_info (414), SelectableSims.add_selectable_sim_info (1133) update selectable membership and notify UI/skewer. Client.active_sim (128) and household (219) are distinct. SimInfo.is_npc (789), is_player_sim (799), is_played_sim (807), is_selectable (815) are different tests.

Selectable membership does not make a guest a household member. Greeting uses GreetedNPCVisitingPlayerSituation (18; helper 43), jobs and role state, not household migration. Existing NPC/visitor role, departure, career and autonomy behavior can remain relevant even after selection.

objects/components/sim_inventory_component:SimInventoryComponent.can_add (91) checks pet/ownable restrictions and add_to_owner_inventory_only/get_sim_owner_id. Selection does not guarantee every pickup or inventory transfer. Build/Buy funds/ownership likewise are household/lot-sensitive; selectable guest portraits alone do not prove Build/Buy permission.

**COMMUNITY feasibility only:** [Sim Control Hub creator page](https://www.curseforge.com/sims4/mods/sim-control-hub) describes cross-household selectable control and limitations for some home/roommate interactions. Its listed v1.5.6 target is 1.126.58, not 1.128 qualification. [Control Any Sim creator page](https://www.curseforge.com/sims4/mods/control-any-sim) is older prior art; [its repository](https://github.com/TitanNano/TS4ControlAnySim) is archived. Neither is a proposed dependency.

**OWNER blocker:** check_guards.py:21–46 explicitly forbids add_selectable_sim_info and remove_selectable_sim_info (also set_active_sim). Guest-selectability implementation would require a deliberate guard/authority decision, not a bypass.

**LAB:** L3, only after that decision: same persistent IDs and external household; greeting, controlled/active distinction, departure timer, inventory cases, HOME funds and Build/Buy access.

**Plan consequence:** arrangement B is technically plausible but its central control mechanism is currently forbidden and its guest semantics remain unqualified.

## D12 — Owner-avatar stasis, NPC filters, needs, aging and story

**Status / scope:** NEEDS_LAB / L. **VERIFIED-1.128:** filters/sim_filter_service:SimFilterService.add_sim_id_to_global_blacklist (870), remove (878), get_global_blacklist (909), dialog blacklist (901); _SimFilterRequest._run_filter_query (281) and matching selection (419) consume blacklist data. This covers filter consumers, not every explicit invitation, phone call, pre-existing situation/job or custom mod selection. Blacklist insertion is a mutation not currently authorized.

sims/aging/aging_mixin:AgingMixin.auto_aging_enabled (193) reads state; set_aging_enabled (664) updates callbacks. AgingService.is_aging_enabled_for_sim_info (101) combines household/LOD/species and played/unplayed policy. A later global refresh can affect per-Sim policy.

SimInfoLOD has multiple levels (1/10/25/50/100/125); CommodityTracker.load (203) can defer active statistics at lower LOD. Uninstantiated is not synonymous with frozen needs, career, age or story. SimStoryProgressionTracker.can_add_arc (301) delegates household eligibility; existing arcs are loaded/saved/cached (195/209/323/377). Disabling new Neighborhood Stories selection alone does not erase existing work.

**PROPOSED invariant:** same Owner Sim ID and household identity on return, with explicit unchanged/preserved age, career/school schedule/state, story arcs, inventory, relationships and whichever need semantics the Owner intends. Cover walkby, visitor, party, call, service and explicit-assignment routes separately. MCCC population/story systems are an additional boundary.

**LAB:** L3 records those facts before absence, after defined game-time intervals, after reload and after return. Owner supplies the intended stasis policy and prepared avatar/save; filters must be checked against both generated and pre-existing situations.

**Plan consequence:** external-household absence needs a composite stasis contract; removing the avatar from the active lot is insufficient evidence.

## D13 — Selectability, active household and narrow UI lock

**Status / scope:** NEEDS_LAB / L. **VERIFIED-1.128:** SimInfo.is_selectable (815) consults household/client selectable membership, while active household and active Sim are separate client facts. Sim.push_super_affordance (4252) has no direct selectable guard in its own body; downstream AOP/interaction tests can still require selection, household or active actor context.

sims/households/household_tests:InSameHouseholdTest.__call__ (84) compares subject/context household identifiers. Therefore neither “nonselectable blocks every script push” nor “all actions work without selection” follows from the engine entry point.

A portrait is a UI representation of control membership, not an ownership or guest-admin permission bit. Removing Ashley’s engine selectability as an all-purpose UI lock risks changing affordance tests, autonomy, active-Sim fallback and other mechanics. Changing all user-directed tuning is also broader than an Owner-input restriction.

**PROPOSED product boundary:** preserve Ashley’s engine identity/control facts needed by qualified adapters; reject only Owner-origin Ashley UI commands through an explicitly authorized, narrow input hook while retaining Owner-avatar control. No such qualified hook is established by this sweep. Owner discipline alone is not a technical lock.

**LAB:** L3 compares the same qualified non-picker interaction with selectable versus nonselectable actor only if authorized, and records context/tests/UI behavior. A UI-lock trial must verify Ashley rejection, Owner control, menus, cancel controls and script receipt behavior without global disabling.

**Plan consequence:** script actuation and narrow Owner UI restrictions require separate qualification; selectability cannot substitute for a proven input boundary.

## D14 — Single-zone limits and Owner travel

**Status / scope:** NEEDS_LAB / M. **VERIFIED-1.128:** zone:Zone.is_zone_loading (272), is_zone_running (286), is_zone_shutting_down (290), register_callback (1148); callback registration can run immediately when a state was already reached, and RUNNING is not proof that every load animation/UI transition has ended.

Zone.on_teardown (791) tears down runtime objects/Sims/services. TimeService.teardown (61) retains only eligible cross-zone simulation work; stop (98) also tears down the wall timeline. cross_zone=True is not a universal bootstrap through menu/loading or service replacement.

world/travel_service:travel_sims_to_zone (23) sends a native travel event and reaches a forbidden clock setter. It is not an approved travel actuator. Current probe alarms use cross_zone=False and need zone/bootstrap recovery.

**SOURCE-CONFIRMED:** reports/R_Z1_RESULTS.md and reports/R_Z2_RESULTS.md document lifecycle limits; E2-L3 recovered bounded observations through zone change. This does not prove both persistent Sims traveled together, Owner-only travel policy, full action continuity or arbitrary return.

**PROPOSED:** invalidate target runtime IDs and pending admissions on zone-generation change; recover persistent designated Sim/household identity and lineage before new current-state claims. If a receipt is lost in teardown, do not infer completion or resubmit. Off-zone Owner and Ashley presence must be explicit.

**LAB:** L3 compares stationary play, Owner-only travel and Owner-plus-Ashley travel, then return/reload; record old/new zone generation, body instances, alarm bootstrap, gaps and outstanding action truth.

**Plan consequence:** stationary co-play does not depend on travel support; travel claims require lifecycle rebind evidence beyond a RUNNING callback.

## D15 — Owner action versus native or authored action

**Status / scope:** PARTIAL / M. **SOURCE-CONFIRMED target runtime:** E1_ADJUDICATION_2026-09-29.md:24 identifies PIE_MENU roots and continuation behavior. AUTONOMY also appears for idle mixers/subbehaviors even with autonomy off; it is not an unambiguous record of an independently chosen native goal.

**VERIFIED-1.128:** Interaction.source (5358), sim (5353), target (5432) support source/actor/target attribution. SocialSuperInteraction.is_social (1710), target_sim (592) and participant machinery distinguish social structure; target_sim delegates to participant lookup and is not certified as the cheapest observer getter.

Actor Sim ID can distinguish an action on the Owner avatar from one on Ashley. PIE_MENU does not identify which human produced the click. SCRIPT can be native critical failure or mod work; SCRIPT_WITH_USER_INTENT can be used by more than the Domus actuator.

**PROPOSED:** retain authenticated human principal at ingress, act ID to engine-ID mapping for authored pushes, and dual-body observations for Owner activity. Separate input origin, actor, target, continuation/parent and social counterpart. Social group membership alone must not assign authorship to both participants.

**UNKNOWN / LAB:** L1/L3 record Owner UI interaction with each body and an Owner-avatar→Ashley social while the approved authored sit adapter runs separately. Require exact root/continuation evidence; keep unmatched producers unknown.

**Plan consequence:** body and context attribution are feasible; authenticated human authorship and complete social causality need additional provenance.

## D16 — Save safety, loading/travel/modal state and completion

**Status / scope:** NEEDS_OWNER / L. **VERIFIED-1.128:** services/persistence_service:PersistenceService.is_save_locked (288) reports write/lock state. save_using (469) creates/wraps a save timeline; save_game_gen (499) is a generator and delegates to _save_game_gen (543), handling lock/cooldown/results/errors and manual completion callbacks. Merely obtaining a generator is not a completed save.

get_save_slot_proto_buff/get_save_slot_proto_guid (862/853) are read surfaces, not permission to save. ui/ui_dialog_service:UiDialogService.has_active_modal_dialogs (63) excludes notifications and phone-ring dialogs; it is not proof of every native Build/Buy/CAS/title/loading UI state. Zone loading/running/shutdown, travel-service state and is_in_build_buy cover distinct conditions.

**SOURCE-CONFIRMED:** the approved actuator registers/removes manual-save completion callbacks (85/89) for observation. It does not host a save command. check_guards.py:21–46 forbids save_game_gen and save_using. Existing Owner UI save observations and E2 lineage evidence are allowed evidence routes.

**PROPOSED safe-point predicate:** qualified actual session/body/lineage, no transition or conflicting write/lock, supported UI state, and an authorized save reason. Completion must be a correlated successful result/callback plus durable save/lineage readback, not elapsed sleep or “save requested.”

**OWNER / LAB:** future scripted save needs explicit guard authority and L4 qualification. Today L4 uses Owner UI save to measure lock/modal/travel rejection boundaries and completion/lineage without invoking forbidden functions.

**Plan consequence:** read-only safe-point evidence and Owner UI saving are distinct from an authorized, durable scripted-save capability.

## D17 — Unfocused and minimized play

**Status / scope:** NEEDS_LAB / L. **UNKNOWN:** native client render/focus behavior is outside the Python script archive. This sweep did not verify a target-build pause-on-focus-loss setting or Options.ini key; none is invented.

**COMMUNITY:** an [EA forum fullscreen-options answer](https://forums.ea.com/discussions/the-sims-4-technical-issues-pc-en/sims-4-how-do-i-change-to-fullscreen-through-the-options-file/11724945) describes fullscreen/windowedfullscreen combinations for exclusive fullscreen, borderless fullscreen and windowed modes. Older [alt-tab reports](https://forums.ea.com/discussions/the-sims-4-gameplay-en/does-your-game-pause-automatically-when-you-tab-out/8611666/replies/8611668) are anecdotal and inconsistent; they do not qualify 1.128, current DX mode or minimization.

Real-time probe alarms run through the game’s update-driven wall timeline (D22). If native updates suspend, the helper can still see a process and serve old files. A process-name check and a recent helper response do not prove advancing simulation.

**LAB:** L4 records build/graphics/window mode and, for each of the three supported window modes, 60 seconds focused, 60 unfocused and 60 minimized. Read game ticks, wall timestamps, actual speed, telemetry gaps and active UI/modal state. Owner operates the window/display settings. Repeat with the intended solo pause policy separately from advancing simulation.

**Plan consequence:** unattended background play must be stated per measured client configuration; process alive is not a focus-independent simulation guarantee.

## D18 — HOME_OBJECT_EDIT, funds, placement, sell and persistence

**Status / scope:** NEEDS_OWNER / L. **VERIFIED-1.128:** objects/system:create_object (113) creates/registers an object from a definition; it does not itself prove purchase funds, Build/Buy legality or a household transaction. sims/funds:_Funds.money (147), add (223), try_remove (234) and amount/reservation paths show distinct funds operations; arbitrary subtraction is not a qualified purchase.

placement:find_good_location (579) delegates to native FGL search (1068). Routing suitability is not equivalent to legal Build/Buy placement, ownership or successful charge/refund. build_buy native aliases, including test_location_for_object, require native implementation evidence; Python fallback no-ops are not verified client behavior.

build_buy:move_object_to_household_inventory (542) changes ownership/unparents and can use destruction/native inventory or serialized fallback. remove_object_from_household_inventory (623) reaches native funds updates. c_api_buildbuy_session_end (1250) handles routing/fence bookkeeping. None establishes a complete atomic buy→place→move→sell transaction with rollback.

**PROPOSED typed edit boundary:** definition/pack authorization, HOME household/lot, spending cap, reservation/commit/refund, bounded placement/rotation, no protected/dependency objects, result receipt and save/reload proof. Research-only feasibility does not authorize object creation, move, funds mutation or destruction.

**OWNER blocker:** destroy is forbidden; current actuator has no object-edit command. Owner must authorize a narrow capability rather than an unrestricted native or Python console.

**LAB:** L4 tests successful purchase, blocked placement/no charge, movement and 90° rotation, sale/refund and manual save/reload. Record before/after money, object identity/definition/owner/transform, routing and persistence; unknown transaction behavior stays unknown.

**Plan consequence:** HOME_OBJECT_EDIT needs a qualified transaction adapter; create_object plus FGL is insufficient.

## D19 — HOME Ashley, Owner guest and administrative authority

**Status / scope:** PARTIAL / M. **VERIFIED-1.128:** sims/household:Household.home_zone_id (554) and funds (604) are household facts; Client.household (219), SimInfo household identity and selectable membership are distinct. A selectable external guest does not acquire the HOME household wallet or lot ownership.

**SOURCE-CONFIRMED product intent:** domus/docs/PROJECT_ASHLEY_SIMS4_EMBODIMENT_DESIGN_V7_3_2a.md:397–425 recommends arrangement B with an external/lotless Owner household and A-roommate fallback; :1428–1457 separates HOME object spending/administration from body control. The Domus implementation plan also separates embodiment and world interaction. No native generic “guest admin” permission bit was verified.

**PROPOSED precise interpretation:** HOME is Ashley’s designated household/residential lot plus explicit authority, not merely whichever zone the Owner is visiting. Body control identifies the persistent Sim; object edits identify the paying/owning HOME household and lot. Human administrative confirmation is an application authority, not inferred from guest portraits.

Owner travel can change active zone without changing either household’s home_zone_id. Inventory-specific ownership can differ from household funds and lot ownership. Off-HOME edits and spending require their own declared authority; joining a household changes the topology underlying these facts.

**UNKNOWN / LAB:** L3 reads both persistent Sim/household IDs, home/current zones, active client household, selectable/active facts, object owners and money before/after authorized UI access. Design authority is application-level; engine citations above independently support the ownership distinctions.

**Plan consequence:** every funds/object/travel operation must name its body, HOME household and lot authority; Owner guest control does not supply those implicitly.

## D20 — Patch detection, tuning fingerprints and changed contracts

**Status / scope:** PARTIAL / M. **SOURCE-CONFIRMED:** src/schema.py:9 hardcodes SIMS_BUILD=1.128.90.1030; probe.py imports it (59) and reports it during bootstrap (466). That field is a declared build, not detection of the installed client. The staged manifest and archive hashes independently identify the research inputs only.

**COMMUNITY / official evidence:** [EA’s September 22, 2026 update](https://www.ea.com/games/the-sims/the-sims-4/news/update-9-22-2026) identifies 1.128.90.1030 and includes autonomy/queue/timer changes; it also addresses crashes involving outdated mods. [The modders’ 1.128.90 reference](https://thesims4moddersreference.org/reference/patches/112890/) documents the patch’s changed mod-facing context. Release notes are not an exhaustive API diff.

**PROPOSED detection facts:** helper reads actual installed executable/file version or approved GameVersion/Default.ini metadata and binds it to the active process; fingerprint scripts, native version, installed packs, tuning resources, mod files and relevant settings separately. Archive hashes exclude native DLL behavior and .package tuning. Record declared, detected and qualified versions as separate fields.

**Per-patch qualification checklist, unordered:** bytecode/import/call signatures; getter recovery/provider purity; loaded class/pack/tuning and adapter parameters; queue/source/terminal callback contracts; pause/request priority and clock scales; bootstrap/travel/lineage; guest/UI/inventory/save/native placement boundaries; combined-mod-set performance. This is a set of evidence conditions, not an execution schedule.

**UNKNOWN / LAB:** L0 validates actual installed metadata against the report and a bounded loaded-tuning manifest. No current helper tool exposes all these values.

**Plan consequence:** patch-specific action cards and purity claims must invalidate on relevant fingerprints; the existing reported build cannot serve as the patch gate.

## D21 — MCCC and common mod coexistence

**Status / scope:** NEEDS_LAB / M. **COMMUNITY creator evidence:** [MCCC downloads](https://deaderpool-mccc.com/downloads.html), opened during this sweep, lists 2026.5.0 with 1.128 compatibility. This establishes the creator’s stated supported build, not combined Domus qualification. [MC Tuner documentation](https://deaderpool-mccc.com/mctuner.html) describes enabling/disabling autonomous eligibility, which can alter the offer/card set.

[MCCC 2026.3 release notes](https://deaderpool-mccc.com/changelogs/mccc2026_3_0.html) include an autonomy restriction breaking a Watch Sky case and relationship-related changes. [Its FAQ](https://deaderpool-mccc.com/faq.html) explains that game-time changes cannot cleanly separate interaction durations and can interact with already-scheduled holidays/events and career alarms. These are concrete reasons to fingerprint settings, not an assumption every mod injects every function.

**Affected classes of mods:** autonomy/needs/story/population; UI/control/selectability; picker/Build/Buy frameworks; CC object tuning/footprints; general script injection frameworks. Such changes can affect providers, eligibility, thresholds, client roles, native behavior or performance. Source=SCRIPT does not authenticate which mod acted.

A read-only observer can still invoke an impure third-party provider through a nominal getter. MCCC and EA story systems require distinct absence/stasis coverage. A creator’s version claim does not prove semantic compatibility with Ashley’s authority boundaries.

**LAB:** L5 records exact files/versions/hashes/settings and compares an Owner-approved isolated minimal LAB configuration with the actual intended mod set, using identical bounded reads and qualified action cases. No live-canon mod installation/removal is requested here.

**Plan consequence:** support must be qualified for a named mod/settings set; unexplained producers or altered cards remain unknown rather than attributed to Domus.

## D22 — Polling/alarm cost and N-Sim scaling

**Status / scope:** NEEDS_LAB / M. **SOURCE-CONFIRMED:** probe.py real-time polling/inbox alarms use a nominal one-second interval, use_sleep_time=False and cross_zone=False. **VERIFIED-1.128:** alarms plus TimeService.update (107) run through the update-driven wall timeline; this is not an independent OS thread or hard 1 Hz guarantee.

Existing-instance commodities, buffs, queue and SI iteration cost at least O(C+B+Q+I) per included Sim. Scanning the SimInfo manager adds O(S), including noninstantiated Sims; S can exceed the on-lot N. Naive all-pair social comparison adds O(N²). Serialization caps do not themselves cap provider traversal or main-thread time.

**SOURCE-CONFIRMED transport cost:** helper telemetry.tail (43) rescans retained history on each call, potentially tens of MiB for one stream. Moving aggregation off the game thread does not fix this helper-side repeated scan. Writer queue/disk caps bound storage but can terminate observation or drop rows.

**PROPOSED measurement/bounds:** separate discovery, existing-instance snapshots, serialization, file enqueue and helper tail costs; report p50/p95/p99 and maximum duration against actual S/N/C/B/Q/I. A 5 ms read-chunk deadline is a proposed budget, not measured capacity. Use bounded cursors, explicit truncation, staggered census and priority for owned terminal/gap evidence.

**LAB:** L0/L5 instrument bounded main-thread timing with approved read adapters, then measure representative small and larger Owner-prepared populations with the intended mod set. Capture probe overhead and simulation responsiveness; do not manufacture extra Sims through code.

**Plan consequence:** polling rate and card breadth require measured whole-path budgets; nominal 1 Hz and row-count limits do not establish safe scaling.

## D23 — Peripheral thalamus Part B signals, rates and logs

**Status / scope:** PARTIAL / M. **SOURCE-CONFIRMED:** plans/ASHLEY_ATTENTION_AND_ORGANISM_MAP_v0.1.md:139–237 defines Part B need, interaction, posture, presence, social, moodlet, environment, lineage and gap percepts. Part B is a peripheral channel into the Mint/Domus nucleus, not a new separate Part-A mind.

**Read feasibility:** existing needs/moods/body/posture/interaction membership and lineage have bounded candidate surfaces (F3–F7/R-M1). Wants/fears (D9), room/weather/hazard and full work forecasts need their own qualified adapters. Polling alone cannot ensure ACTION_END (D4); source/social provenance needs D15. Unsupported fields must be marked unknown, not synthesized.

**Rate evidence, bounded samples only:** four files in E2_N_P_L_OWNER_2026-09-30_01 were sampled to at most 150 rows/file. 0d15935a… had 83 rows/77 presence samples over 77.579 s; 1437e3d1… 80/72 over 72.632 s; 863ffab5… first 150/143 over 145.114 s; f12538bb… 60/54 over 54.153 s. Median sampled gaps were 1.021–1.023 s. Distinct interaction entries were 14/8/22/11, mostly AUTONOMY with BODY_CANCEL/POSTURE_GRAPH exceptions. These are short one-body trace samples, not household event, choice or wake rates.

**PROPOSED thalamus contract:** a lineage-aware pure state→delta transformation; observation game ticks for need prediction, monotonic wall time for debounce/fatigue, stable percept/decision IDs, novelty/habituation state, coalescing and explicit missing intervals. Owner-social “always through” needs authenticated Owner/body provenance. A 30-second heartbeat need not trigger thought; a 1.5-second batching target is a design target, not measured wake cadence.

Log volume = 86,400 × rows/second × mean encoded bytes. Illustratively, 512-byte rows at 1/s consume 42.2 MiB/day; 8/s consume 337.5 MiB/day. Actual event/decision sizes are unmeasured. The probe’s 200 MiB cap is not a thalamus retention policy. Preserve consequential decisions, receipts and gap markers under a separately explicit quota.

**LAB:** L0 measures serialized signal/decision sizes and actual delta/wake rates over the intended scenes; L1 supplies owned terminal evidence. Helper failure must not falsely claim a paused/frozen MIND_ABSENT state without a game-side observed policy.

**Plan consequence:** Part B can use qualified deltas now in principle; full sensory coverage, wake economics and terminal truth cannot be inferred from one-second presence sampling.

## DC1 — Arrangement B guest versus A roommate fallback

**Status:** CONSULTATION. **Fact basis:** D11 separates selectable control from household identity and documents the forbidden selectable-list mutation; D12 identifies unresolved external-avatar stasis; D13 separates UI input restriction from engine selectability. Prior-art creator pages show feasibility, not permission or 1.128 compatibility.

**Recommendation:** retain B as a conditional technical candidate where external Owner household identity is a real requirement. Do not call B implementable under the current guard or claim stasis from NPC absence. Specify and qualify A’s roommate-style topology separately; its name alone does not prove fewer selection changes. It still needs Owner-control, aging, needs, career and story semantics. If A uses shared-household membership, whether that identity change is acceptable is an Owner/design decision.

**Confidence:** Medium. Engine distinctions and the guard prohibition are high-confidence; complete guest, UI and offscreen behavior is not runtime-qualified.

**Alternatives considered:** ordinary nonselectable visitor preserves external identity but cannot promise Owner-avatar control; shared household changes identity/topology; cross-household selectable guest preserves topology but requires authorized mutation and qualification; installing a prior-art mod does not resolve authority or guarantee semantics.

## DC2 — Pause versus dilation for solo deliberation

**Status:** CONSULTATION. **Fact basis:** D6 has target evidence for owned pause/release, UI override and native SUPER_SPEED3 restoration. D10 shows how much game time an ordinary remote deliberation can consume. D21 explains why alternative game-time scaling can affect more than apparent pacing.

**Recommendation:** use the qualified owned pause primitive for bounded Owner-absent deliberation, conditional on continuously observed actual paused ticks and a qualified release/failure-lease policy. A live request is not proof of actual pause, and helper death is not proof of release. Co-play automatic pause requires a separately explicit Owner policy; lack of remote heartbeat alone does not establish Owner absence.

Treat dilation as an optional, separately qualified ambient-play mechanism. It cannot replace current-snapshot admission, terminal receipts or correct time units, and the present forbidden clock setter must not be bypassed. General background play still needs D17.

**Confidence:** High for the existing pause primitive; medium for end-to-end unattended use because watchdog/lease, focus behavior and remote attachment failure are unqualified.

**Alternatives considered:** advancing Normal or native sleep speed consumes substantial game time; permanent pause prevents intended ambient life; changing game-time scale may alter durations/calendars and requires fresh qualification; Owner-controlled UI pacing remains a distinct supported choice.

## DC3 — Technical dependencies: facts and reasons only

**Status:** CONSULTATION. The following are capability dependencies, not a schedule, ordering, critical path or universal stage gate.

| Capability fact | Technical dependency and reason |
|---|---|
| Remote action currentness (D5) | D1/D2 attachment, authority, lineage and snapshot provenance: the game must know which live world and permission the request names |
| Reconnect without duplicate/residual action (D4) | Durable owned act map and D1/D2 attachment receipts: engine IDs and file acknowledgments alone cannot distinguish a lost reply from no effect |
| Mood/outcome cards (D3) | D20 installed tuning/mod identity and D22 provider bounds: the card’s eligibility and purity depend on the actually loaded providers |
| Physiological delegation (D7) | D8 native exceptions plus authorized typed scope: the ordinary autonomy filter does not cover every critical push |
| External Owner-avatar stasis (D12) | D11 household/control topology: NPC, aging, filter and story eligibility use those facts, not merely a absent-body label |
| Narrow Ashley UI lock (D13) | Qualified D11 selectability/context semantics and an authorized input hook: removing engine membership changes more than UI acceptance |
| Travel rebind (D14) | D1 bootstrap and D5 invalidated zone/body snapshots: runtime objects and alarms can be destroyed while persistent identity remains |
| Scripted save (D16) | Transition/UI/lock evidence, D2 lineage and explicit Owner authority: save generator creation is neither safe-point proof nor durable completion |
| HOME object transaction (D18) | D19 paying/owning household and native placement/transaction qualification: object creation does not perform legal purchase or refund |
| Object persistence evidence (D18) | Successful save/reload evidence; this may use Owner UI save and does not inherently require a scripted-save feature |
| Part-B terminal/forecast percepts (D23) | D4 owned terminal receipts, F7/F15 qualified values and D10 units: missing interactions and default overhead cannot predict actual completion |
| Background solo play (D17) | Actual native-client update behavior; D1 gap/health evidence can diagnose symptoms but cannot make a suspended render loop advance |
| Combined mod-set support (D21) | Relevant D3/D7/D11/D13/D16/D18/D22 contracts and D20 fingerprints: mod/provider/settings changes can invalidate their established semantics |

**Recommendation:** describe each capability with only its actual data, authority and runtime-contract dependencies; stationary observation, Owner UI saves and supported narrow actions should not inherit unrelated full-feature requirements.

**Confidence:** High for dependencies visible in target code and existing contracts; medium for native UI/mod interactions awaiting LAB.

**Alternatives considered:** a single mandatory E3→E7 chain, treating all future sensory families as observation prerequisites, and making scripted save a prerequisite for every persistence test. None follows from the technical facts.

# LAB session script

These are exact future reads/trials, not actions performed during this job. D12 here means the **Domus D12 stdio MCP harness**, not research item D12. Current helper mcp_server.py:77–159 exposes status, arm, start, stop, disarm, prepare, sit/sit_trial, pause, release, verdicts, telemetry and lineage. It has no arbitrary game-getter, guest-control, save, travel or object-edit endpoint.

**Prerequisite for every extended read:** Owner-authorized bounded read-only probe instrumentation must expose the named fields below in existing telemetry rows, with observer purity checked first. Otherwise mark that read unavailable; do not substitute eval, console injection or an imaginary MCP tool. Native/forbidden actuation needs a separately authorized typed adapter. Owner hands are marked **OWNER**. The operator only invokes the MCP capabilities actually present/qualified. No credentials, login or submission are needed.

**Common reads, in order:** (1) status(); retain schema/probe/helper versions, actual detected client build if exposed, designated body, phase and health. (2) lineage(); retain current classification and ledger references. (3) telemetry(kinds=["session_open","session_checkpoint","zone_snapshot","clock_snapshot","lineage_event","dropped_summary","guard_exhausted","cap_reached","writer_failed"], n=100); bind rows to their actual session/sequence and mark gaps. (4) Reject interpretation as current if attachment, body, lineage or row freshness cannot be established. Filename mtime is not a current-world proof.

## L0 — Pure sensing, wants/fears, fingerprints and cost

Coverage: D3, D9 (NEEDS_LAB), D20, D22 (NEEDS_LAB), D23; unresolved F3/F4/F7/F15.

1. **OWNER:** open a prepared LAB save and authorize/install only the bounded read instrumentation; no changes to live canon. Run common reads. Baseline existing statistic-instance count/recovery placeholders, event registration counts and body/household/zone IDs.
2. Read loaded InstanceManager.types length and a capped sample (≤20) of class IDs/is_super/is_social/static mood-related metadata. Report full-load state, missing packs and truncation. Read at most 20 offered super-affordance IDs from the qualified provider path, without potential_interactions/AOP tests.
3. Read existing CommodityTracker.get_all_commodities instances (≤12 needs), each cached instance value with last-update ticks/min/max/best and qualified get_change_rate; read BuffComponent current mood/intensity and active IDs (≤16). Do not call generic tracker get_statistic/get_value, polymorphic ContinuousStatistic.get_value or Buff timeout lookup; cached value age must be explicit. Read existing interaction/SI/queue IDs and stored start times; classify approximate_duration as overhead only.
4. Read existing career level/scheduler fields and next-work tuple only after delegated scheduler purity is qualified; record units and missing/uninstantiated state. Read Wants option, existing slots/goal/target IDs, FEAR traits and existing associations; never call get_active_whimset_data/show/hide/set_enabled.
5. Repeat the same reads 60 times at one-second nominal cadence. Through telemetry(n=100) collect per-read timing, encoded bytes, rows emitted, delta count and registration/statistic-count comparisons. Any observer-induced mutation fails the read adapter.
6. **OWNER:** toggle Wants/Fears through UI off then on; after each, repeat the exact option/slot/trait read. Owner UI-save/reload, repeat; Owner enter/exit CAS, repeat. Keep the same persistent Sim ID; distinguish hidden, empty, disabled, cached and unavailable records.
7. Read helper-exposed actual installed version, active process attachment, script/native/tuning/pack/mod/settings fingerprints. Compare the actual version with declared schema build and qualified manifest; absence of the read is a failed detector claim, not a match.
8. **OWNER:** supply a second prepared LAB scene with larger S/N, then repeat steps 3–5. Report p50/p95/p99/max, dropped/truncated rows and game responsiveness. Compare measured signal/decision bytes and wakes with the D23 volume formula. No artificial population creation.

## L1 — Lifecycle, stale admission, pause, speeds and helper loss

Coverage: D1/D2/D4 (NEEDS_LAB)/D5/D6/D10/D15.

1. **OWNER:** load LAB_E1 and place/use the already qualified chair setup. Run common reads; arm(save="lab_e1"); start(). Require the existing learned sit signature and admissible lineage before actuation.
2. prepare(object_id="<observed chair runtime ID>"); retain returned token/act correlation. sit(token="<returned token>") once. Read telemetry(kinds=["experiment_event","command_event","clock_snapshot","presence_snapshot"], n=100) and verdicts(n=5). Extended reads capture owned act ID, interaction ID, queued/running/finisher reason and exact callback, not just disappearance.
3. Repeat the qualified sit with **OWNER** cancel/interruption through UI, keeping its finishing reason and goal outcome separate. Do not invoke a forbidden cancellation API.
4. Repeat preparation, wait beyond its 30-second token validity without pushing, then submit that expired token once: require ADMIT_REJECT and no owned push. **OWNER:** prepare another token, then alter the target/posture via the approved UI; submit once and require fresh mismatch rejection. Unimplemented general-family cases remain unavailable.
5. **OWNER/operator:** during an accepted sit, disconnect only the local helper client while keeping the game/probe alive, then reconnect. Run common reads and verdicts; query retained act/lifecycle records before any new request. Require either correlated terminal evidence or OUTCOME_UNKNOWN. Do not replay the original act automatically.
6. **OWNER/operator:** disconnect the helper during a pending local request and inspect retained inbox/reply/done receipts upon reconnect; observe whether it executes after the 15-second client timeout but before 30-second expiry. Do not infer exactly-once from a done file. A crash-window trial needs a separately approved sacrificial LAB harness; no forced game crash is implied.
7. pause(); read clock_snapshot ticks and actual speed for 15 seconds; release(); read another 15 seconds. **OWNER:** while paused, choose 1x in UI; read actual request resolution. During native sleep SUPER_SPEED3, repeat pause/release and verify restoration rather than forced Normal. Read wall/probe timestamps alongside frozen game ticks.
8. **OWNER:** select each ordinary UI speed for 30 seconds; read actual loaded scale and game-tick/wall ratios. Never call a forbidden speed setter. For helper loss during an owned pause, observe the actual qualified lease/release behavior; absent expiry is an unresolved failure policy.
9. **OWNER:** perform one Owner-avatar action, one permitted Ashley UI action and one avatar→Ashley social. Read actor/target/root/continuation/source/owned-act map for each. Identity must come from retained human authority, not source enum alone.
10. stop(); disarm(); common reads verify no owned pause remains and record final gaps/receipts. Current adapter failures do not authorize cleanup via forbidden setters.

## L2 — Critical physiology and delegated categories

Coverage: D7 (NEEDS_OWNER), D8 (NEEDS_LAB).

1. **OWNER:** provide isolated LAB saves already near low-energy and low-bladder thresholds, without this operator changing needs. Read common binding plus UI autonomy setting, selected actor and existing need/tuning values.
2. start the approved observer; telemetry(kinds=["presence_snapshot","experiment_event","clock_snapshot"], n=100) plus extended existing-need/threshold/source/priority/owned-map fields. **OWNER:** set ordinary autonomy off through UI. Observe until a natural threshold/outcome occurs; retain exact IDs and distinction between distress AUTONOMY and failure SCRIPT.
3. Repeat with Owner UI autonomy on, then selected/unselected body as applicable. Record threshold, resulting pass-out/wetting or alternative outcome and missing branches. An unobserved event is not “impossible.”
4. **OWNER decision required:** only if a narrow modifier adapter is explicitly authorized and implemented, apply its physiological allowlist through that typed capability; observe at least the same critical trials plus opportunities for excluded social/aspiration/shopping behavior. No disable_autonomy/enable_autonomy path is used.
5. Revoke that capability through its approved adapter; compare modifier/lock/decay/eligibility state with the baseline. Record residual effects or inability to restore. Without the adapter, step 4/5 are blocked, not simulated via raw engine calls.

## L3 — Guest, stasis, UI, HOME and travel

Coverage: D11 (NEEDS_OWNER), D12/D13/D14 (NEEDS_LAB), D15/D19.

1. **OWNER decision required:** authorize the specific guest-control/selectability and any narrow UI-lock capability, or leave B trial blocked. Owner provides a prepared HOME Ashley household and distinct Owner household with recorded persistent IDs.
2. Run common reads plus both Sim IDs/household/home/current zone, active client household, selectable/selected/NPC/played flags, funds, object owners, visitor roles/timers, aging/career/story state and existing filter blacklists. Multi-body reads require the bounded observer extension.
3. **OWNER:** arrive/greet the avatar via UI. With only the authorized guest adapter, test Owner control; compare portrait, active actor and unchanged household identity. Try permitted inventory pickup/transfer and Build/Buy entry via UI; record actual denial/success and which wallet/owner applies.
4. With qualified scripted action receipts, test the same narrow non-picker action in the allowed selectability configurations. **OWNER:** attempt Ashley UI input and Owner-avatar input under the narrow lock; require the former rejected and latter functional without disabling qualified authored pushes.
5. **OWNER:** leave/uninstantiate the avatar through UI. Record age, need values/LOD, career/school, existing arcs, inventory and relationship baselines; observe after 24 and 72 game hours, then Owner UI save/reload and return. Require same persistent IDs; compare against the explicitly intended stasis policy.
6. During absence, **OWNER** uses prepared opportunities for walkby, visitor, party and phone involvement. Read requested/selected IDs and existing situations/jobs. Test explicit invitation separately from generated filters; blacklist coverage is not presumed universal.
7. **OWNER:** travel alone to a second zone; run common reads and capture teardown/new zone generation, designated body existence, alarm bootstrap and rejected old admissions. Repeat with Ashley as an explicitly chosen companion, then return/reload.
8. If an owned action spans travel, read the existing act record and outcome, never retry based on disappearance. Compare to a stationary baseline. No MCP travel/set_active_sim command is invented.

## L4 — Background client, saving and HOME edits

Coverage: D16 (NEEDS_OWNER), D17 (NEEDS_LAB), D18 (NEEDS_OWNER).

1. **OWNER:** choose exclusive fullscreen, borderless and windowed in turn. For each mode, record graphics/build configuration and 60 seconds focused → 60 unfocused → 60 minimized. Read clock_snapshot plus wall timestamps/health/gaps and modal/loading/BuildBuy state through the approved extension. Do not infer continued simulation from process alive.
2. Repeat the intended bounded pause policy separately. Record actual ticks, speed/request state and whether probe updates stop under each focus state.
3. **OWNER:** perform a UI save in the isolated LAB; read save lock, transition/UI state, correlated completion, GUID/slot/ticks and lineage before/during/after. Read the authorized helper’s save file inventory/durability evidence if exposed; today’s MCP lacks a general file-inventory tool.
4. **OWNER:** open a supported modal, enter Build/Buy/CAS and travel in separate trials. Record which safe-point predicate fields detect each condition; no scripted save is attempted unless its narrow adapter and guard decision are authorized.
5. **OWNER decision required:** authorize/qualify the typed HOME edit adapter, or leave automated edits blocked. Baseline HOME wallet/lot/object owner and placement state; purchase/place one approved object successfully; attempt the same purchase with blocked placement and require no net charge.
6. Move that object, rotate 90°, then sell through the qualified adapter. For each, retain receipt, money before/after, definition/identity/owner/transform, routing and refund evidence. No raw create/destroy/funds/native console bypass.
7. **OWNER:** UI-save and reload between retained-object and sold-object cases. Read persistence, placement and wallet, requiring the retained object’s state and sold object’s absence. Scripted save availability is not a prerequisite for this evidence.

## L5 — Actual mod set and scaling

Coverage: D21/D22 (NEEDS_LAB), with D3/D7/D11–D18 regression evidence where applicable.

1. **OWNER:** provide an isolated prepared LAB for the minimal supported configuration and the intended full mod set. Retain exact mod versions/hashes/settings, packs and actual client version; no change to live canon.
2. Run common reads and L0’s bounded existing-instance/provider/timing reads in the same scene for both configurations. Compare offer/tuning/source, registration/statistic counts, drops, timing distribution and helper scan/spool cost.
3. Exercise only already authorized L1/L2/L3/L4 cases relevant to the installed mods. Keep the same scenario/IDs where possible; never treat unavailable adapters as passed.
4. Attribute unexplained SCRIPT/selection/story events as unknown until concrete producer evidence exists. Record changes in MC Tuner, game-time, aging/story/population and UI/BuildBuy settings explicitly.
5. Repeat timing with the prepared larger scene. Report capacity only for the observed N/S/mod set and qualified read family; retain errors/truncation rather than a blanket “compatible” result.

# Gaps the plans and design do not mention

These are findings/omissions, not a risk register or implementation sequence.

- Generic tracker reads with add=False and buff timeout reads can recover/create statistics; continuous-statistic value reads can advance values/notify deltas; Wants “active data” lookup can change event registrations. Observer purity needs actual call-path evidence.
- The reported Sims build is hardcoded. Actual client/native/tuning/pack/mod provenance and invalidation are separate from a declared schema version.
- Helper tails rescan history, mtime selects a session, and durable upstream cursors/spools/acknowledgments are absent. Local rotation and queue caps can terminate evidence independently of game health.
- Effect-before-reply/done persistence prevents exactly-once claims; a request can outlive the caller’s timeout. Retained owned receipts and outcome-unknown handling are necessary facts.
- An owned pause request has no proven remote-failure lease here. Frozen game ticks do not freeze wall alarms, UI or helper state; process alive does not establish focus-independent updates.
- Critical need failure uses ordinary SCRIPT; AUTONOMY includes continuations/idle behavior. PIE_MENU identifies an input path, not an authenticated human.
- Guest selectability, active actor, household ownership, inventory permissions and HOME administration are different engine/application facts. Neither a portrait nor uninstantiation establishes stasis or authority.
- NPC filter blacklists cannot cover every explicit/pre-existing situation, call, career, aging or external mod story route; offscreen LOD requires explicit return semantics.
- Native modal/loading/BuildBuy/CAS boundaries and native purchase/placement/refund transactions are not fully represented by Python getters or create_object/FGL.
- Universal action-end/work-duration forecasts are absent; sampled disappearance, time_overhead and net need drift cannot supply a complete predictive model.
- Part-B presence cadence is not decision/wake cadence. Per-family rates, serialized sizes, habituation state, loss semantics and decision-log retention are not established by the existing probe cap.
- Save lineage evidence cannot exhaustively prove external save edits or remote memory rollback. World lineage and cognitive authority/ancestry need distinct provenance.

