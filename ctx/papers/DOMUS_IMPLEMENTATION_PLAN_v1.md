# Domus Implementation Plan v1: From E2 to Bound Perception (E3), with an Agent-Run LAB

**Status:** DRAFT for Alex's review. Once approved, the architect hands it to Manager as packets.
**Architect:** Claude Opus, 2026-10-01.
**Grounded at:** Domus `e2-run` `26ac0c1` (probe 2.0.2 installed). Every file, function, command and constant below was read at that commit.
**Design sources:**
- `DOMUS_E3_SELF_IMPROVING_EMBODIMENT_v0.1.md` (D1–D7);
- `ASHLEY_ATTENTION_AND_ORGANISM_MAP_v0.1.md` Part B (the peripheral thalamus);
- the Domus design V7.3.2a (§12, §14, §17 E3, §19A, §20);
- Alex's decisions of 2026-09-30.

The Ashley-side half of E3 is in `ASHLEY_IMPLEMENTATION_PLAN_v1.md` Phase 8.

---

## 0. How to read and run this plan

### 0.1 Roles

- **Coder:** Codex Sol 6.1 light on the box (Owner, 2026-10-01; Grok Build before).
- **Reviewer:** Grok Build per packet (Owner, 2026-10-01), in the J106 style, in its own temp worktree: fail-before at the base, the pinned CPython 3.7 suite, then `build.ps1` + `verify.ps1`.
  - **Owner, 2026-10-01:** Codex Sol 6.1 light on Manager's box codes; Grok Build reviews. The Windows-only steps (the exact-3.7.0 build and verify, installs) run on XQX through the relay.
- **Installs:** J104/J108 style jobs. The game must be closed, and save hashes must be identical before and after.
- **Adjudication:** the architect.
- **Alex:** decides the LAB sessions that need them, merges to `main`, and sets the budget numbers.
- **Branch:** `e2-run` is not merged yet (Alex merges). This plan's work goes on a new branch **`domus-next`**, cut from the `e2-run` tip after the E2 verdict commit. Pushing it is authorized; merging waits for Alex.

### 0.2 Standing rules

- **Frozen:**
  - one world, one Ashley;
  - actions go through engine scripting only, never keyboard or mouse emulation;
  - the claim ladder and attribution rules;
  - learning comes only from controls;
  - the mod does no network I/O (§19A);
  - `MOD_INERT_OUTSIDE_BOUND_SAVES`.
- **Probe guards** (`sims-e1/tools/check_guards.py`) stay law:
  - imports only from `APPROVED_STDLIB_IMPORTS` (`hashlib json os pathlib queue struct sys threading time uuid`) and `APPROVED_GAME_ROOTS`;
  - `FORBIDDEN_IMPORT_ROOTS` includes `socket http ssl urllib subprocess importlib`;
  - actuation calls only in `e2_actuator.py`;
  - `PURE_FILES` have no game imports.

  Every new probe module follows these rules, and pure logic goes in a new pure file.
- **Every probe change is a new version and a new plan amendment** (Appendix B: A11, A12…), with byte-exact amendment text in the packet, as A10 was.
- **Tests:**
  - `sims-e1/tests/` (unittest) under the pinned Python `C:\Users\Xharv\AppData\Local\Programs\Python\Python370-AshleyE1\python.exe` (`sys.path.insert`, not `PYTHONPATH`);
  - `tools/check_guards.py`;
  - `verify.ps1`.
  - New tests fail **by assertion** at the base, except declared regression guards.
- **Evidence:** every live session gets a `sims-e1/evidence/<STAGE>_<date>_<nn>/` folder with the raw telemetry, `session.md`, the ledger and the save inventory. The folder is committed as `-text` (`.gitattributes`).

### 0.3 Alex's decisions this plan implements

- **Automate verb learning.** The menu comes from the game, effects are proven per class, native autonomy supplies controls, and Alex demonstrates only on disagreement.
- **Agents run the LAB through an MCP on the Windows helper,** and may crawl unattended in LAB saves only.
- **The affordance atlas** maps everything, with Ashley's help.
- **Organic attention** (the peripheral thalamus). No fixed heartbeat and no shadow period.
- **Memories from undone timelines** are kept, marked "undone".
- **A critical need may pause the game only when Ashley is alone.**

### 0.4 Phase map

| Phase | What | Probe version | Needs Alex at the PC? |
|---|---|---|---|
| **0** | Close E2: T1–T3 on 2.0.2, then the E2 verdict | 2.0.2 | **yes** (~20 min, last time) |
| **1** | Hygiene: byte-reproducible build, console output, attestation, naming | 2.1.0 | install only (game closed) |
| **2** | Command inbox/outbox in the probe | 2.2.0 | install only |
| **3** | Windows helper + Domus MCP + agent trial runner | — (helper) | no |
| **4** | Senses expansion: needs, moodlets, presence, social | 2.3.0 | install only |
| **5** | Atlas + class cards + calibration from native autonomy + crawl | 2.4.0 | no (the crawl runs unattended) |
| **6** | Peripheral thalamus + E3 transport (with Ashley plan Phase 8) → E3 trial | 3.0.0 | E3 trial session |

From Phase 3 on, **every live LAB session is agent-run through the MCP** unless it needs Alex's own hands.

---

## Phase 0: Close E2 (architect + Alex; no code)

1. The game loads LAB_E1 (expect `CLASSIFIED CONTINUES_LAST_SAVE` at S1 = 5331484).
2. `ashley_e1.arm lab_e1`, then `ashley_e1.start`. Check that autonomy is off.
3. **N5 re-learn:** Alex sits the Sim on chair `118245043789434055` by hand. Expect `CONTINUATION_LEARNED` with detail `14244`.
4. **T1–T3:** up to 5 trials for 3 PASS. The clipboard helper (`token_watch.ps1`, which follows the newest session file) copies each token. Each verdict must show `continuation=<n>`, checked numerically by eye (the J107 nit).
5. The evidence commit, then `sims-e1/evidence/E2_VERDICT_<date>.md` (§11). It declares that the gate, N, P and L evidence ran on 2.0.1 and the T evidence on 2.0.2, with the build hashes and the findings list.
6. Cut the `domus-next` branch.

---

## Phase 1: Hygiene (probe 2.1.0, amendment A11)

**H1: A byte-reproducible build.** Root cause, VERIFIED on 2026-09-30: `.pyc` headers carry the source mtime and size, and line endings differ between checkouts.
- `sims-e1/tools/build.ps1`, the compile code at `$compileCode`: `py_compile.compile(src, cfile=dst, dfile=dfile, doraise=True, optimize=0, invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)`. This is available in CPython 3.7; `flags=1` puts the source hash in place of the mtime.
- `.gitattributes`: add `sims-e1/src/** text eol=lf`, then renormalize once (`git add --renormalize sims-e1/src`).
- The `source_content_sha256` in the build metadata is computed over LF-normalized bytes.
- `verify.ps1`: a new check **REPRODUCIBLE**. It builds twice, in two fresh temp worktrees at the same commit, and requires identical `BUILD_SHA256`.
- **Acceptance:** the J106/J107/J108 situation can't recur. Three builds (a checkout and two worktrees) give one hash.

**H2: Probe console replies are visible (diagnose first).**
- **The earlier diagnosis is withdrawn (2026-10-01).** It said "the game passes `_connection`, so `_output(text, 0)` goes nowhere." But the dispatchers are registered with the raw `register`, which the engine calls with `_session_id` (the vanilla `Command` decorator translates that into `_connection`). With an unknown keyword, every command would have returned False, and they worked live.
- The root cause is UNKNOWN.
- **D9 H2:** establish it from prior art, fix only on evidence, and otherwise report UNKNOWN. Phase 2's outbox replies make console replies unnecessary for agents.
- **Root cause found (R-H2, 2026-10-01; vanilla bytecode):**
  - in release builds `sims4.commands.output()` is a no-op (`return None`);
  - only `sims4.commands.cheat_output(s, context)` forwards to the native `_commands.output`;
  - `_session_id` is the correct keyword for raw `register` handlers.

  **Fix in D10 (2.2.0):** `_commands_output = _commands_module.cheat_output`, plus a live A/B check at the first load.

**H3: E2 events carry the real attestation.** `E2Control._event` (`e2_control.py:67–78`) calls `schema.make_record` without `attestation=`, so `schema.attestation()` defaults to `UNARMED` (`schema.py:125, 189/229`). Pass `attestation=schema.attestation(armed_name, …)` from `get_armed_snapshot()`, and test it.

**H4: STOP release naming.**
- `schema.py:56` gains `RELEASED_ON_STOP`.
- `E2Control.on_stop` uses it; `RELEASED_ON_DISARM` stays for disarm (`e2_control.py:404`).

**H5: Tests.** Assert `continuation=<n>` numerically in `test_verdict_detail_contains_continuation_count` (`test_e2.py:760–776`).

**Plus:** version 2.1.0 everywhere, A11 amendment text in the packet, a J106-style review, and a J108-style install.

---

## Phase 2: The command inbox (probe 2.2.0, amendment A12)

**Why:** agents (and later the helper) must drive the LAB without the console and without the 30 s TTL race. The mod still does **no network I/O**: this is local file IPC, which §19A allows.

**P2.1: The pure parser `cmdbox.py`** (added to `PURE_FILES` and `PRODUCTION_MODULES`).
- **Command file schema** (`AshleyE1Telemetry/cmd/inbox/<id>.json`, ≤ 4 KB):
  `{ "v":1, "id":"<uuid>", "issued_at_ms":…, "expires_at_ms":… (≤ 60 s after issue), "issuer":"agent:<name>"|"helper", "command":"arm|start|stop|disarm|prepare|sit|pause|release|status|sit_trial|atlas_dump|offered_scan", "args":{…} }`
- **Validation:**
  - a closed command vocabulary; arm names stay closed (`lab_e1`, `lab_e1_fork`);
  - expiry is checked against wall time;
  - the id is single-use: a replay is rejected, and a used-id set is kept per armed session;
  - the issuer is bounded to 40 characters.
- **Reply file schema** (`cmd/outbox/<id>.json`): `{ "id", "status": "OK|REJECTED|ERROR", "code", "result": {…} }`.

**P2.2: Probe integration.**
- A **1 Hz real-time alarm registered at probe load**, the same API family as the sampling alarm (`alarms.add_alarm_real_time`).
- **Inert unless a command file exists:** it runs one `os.listdir` per second, and does nothing outside bound saves except `status`.
- Each file is renamed to `.taken` before it's executed and to `.done` after. It's executed through the **same functions as the console dispatchers**, so there's one code path.
- A new telemetry `command_event` row (a new `EVENT_KIND` in `schema.py` with its payload keys) holds `{id, issuer, command, status, code}`. Attribution is in telemetry.
- **`sit_trial <object_id>`:** prepare, then sit **inside one call**, the token passed internally. Admission and all its checks are unchanged, only without the human round-trip. The actuation still happens in `e2_actuator.py`.
- **`status`:** state, arm name, signature and continuation sets, lineage class, and the last 5 verdicts, returned in the reply.

**A12 (amendment text to fix in the packet):**
- The command inbox is a harness input path equivalent to the console.
- Actions keep the `EXPERIMENT` origin, and `issuer` is recorded as attribution: "agent on the Owner's behalf".
- Alex's console stays available.
- Nothing in the inbox can do what the console can't.

**Tests:**
- the parser: every rejection code, expiry, replay;
- the probe with fakes: file → dispatch → reply → `command_event` row;
- the inert case: no file means no work and no rows.

---

## Phase 3: The Windows helper, the Domus MCP, and the agent trial runner

**New top-level directory** `helper/` in Domus: the Python package `domus_helper` (host Python ≥ 3.12, **never loaded by the game**), with its own `pyproject.toml`, tests (`pytest`) and a README.

**P3.1: Core.**
- `paths.py`: the Sims user root (from config; default `C:\Users\Xharv\OneDrive\Belgeler\Electronic Arts\The Sims 4`), the telemetry root, `cmd/inbox`, `cmd/outbox`.
- `telemetry.py`: tails the newest `ashley_e1_*.jsonl`, switching on re-arm (as `token_watch.ps1` does), and validates rows against a vendored copy of the closed schema keys.
- `commands.py`: `send(command, args, issuer, timeout=15 s)` writes the inbox file atomically (temp + rename), waits for the outbox reply, and returns it.

**P3.2: The MCP server (`domus_helper/mcp_server.py`, stdio, the official Python MCP SDK).**
- **Tools:** `status`, `arm(save: 'lab_e1'|'lab_e1_fork')`, `start`, `stop`, `disarm`, `prepare(object_id)`, `sit(token)`, `sit_trial(object_id)`, `pause`, `release`, `verdicts(n)`, `telemetry(kinds[], n)`, `lineage()`, `atlas_query(filter)` (Phase 5).
- **Safety in the tools:**
  - they refuse if the game isn't running (`TS4_x64` process check) or the probe `status` isn't answering;
  - every actuating tool requires the armed name to be a LAB name, the closed vocabulary.
- **Registration:** `.mcp.json` at the Domus root (Claude Code) and a Codex config snippet in the README. The Owner's own Claude and Codex sessions get the tools.

**P3.3: The agent trial runner (`domus_helper/runs/trial.py`).** It runs a full E2-style session unattended:
1. arm and start;
2. `sit_trial` × N, waiting for each verdict;
3. stop and disarm;
4. write the evidence folder: the telemetry copy, the ledger, the save inventory, and `session.md` generated from telemetry only.

It never commits; the architect commits the evidence.

**Acceptance:** an agent-run replay of T1–T3 in the LAB on 2.2.0 gives the same verdict classes as Phase 0 with no human in the loop. This is **the moment the chore disappears.**

---

## Phase 4: Senses expansion (probe 2.3.0, amendment A13)

**Why:** the schema already reserves `motives` and `sim_signals` (`schema.py:94, 194–195`, with `MAX_MOTIVES` and `MAX_SIGNALS`), but `observers.poll_once` (`observers.py:139–171`) fills neither. The design §12 requires body and psychology signals from E3 day one, and the thalamus has nothing to predict without them.

All of these are **read-only** reads in `observers.py`, and none is in `FORBIDDEN_CALL_NAMES`:

| Sense | Read | Prior art |
|---|---|---|
| needs (motives) | `sim_info.commodity_tracker.get_value(stat_cls)` for the six motive GUIDs, normalized 0–100 | fivesim `state_reader.py` + `ids.py` `MOTIVE_GUIDS` (MIT; read and cite, don't vendor) |
| moodlets (`sim_signals`) | the active buffs: type id, mood, intensity, remaining time | runtime-verified in the LAB before trust (the E1-C question) |
| presence | instanced Sims on the active lot: id, household or not, room/level if exposed | fivesim `list_present_sims` |
| social | running interactions of **other** present Sims whose target is her Sim: actor, affordance, source | the same `_describe_interaction` as hers |

- Every new field is `EXPOSED` or `UNKNOWN`, and missingness is recorded, never guessed. That's the E1 discipline.
- **A LAB evidence session** (agent-run via the MCP) proves each read on build 1.128 before the thalamus relies on it.

---

## Phase 5: The atlas, class cards, calibration and the crawl (probe 2.4.0, amendment A14)

**P5.1: Tuning dump** (`atlas_dump` inbox command; probe side is read-only).
- Iterates `services.get_instance_manager(sims4.resources.Types.INTERACTION)`. For each tuning class it writes `{guid, name, is_super, is_social, target_type flags, required posture if exposed, loot/commodity refs if exposed}` to `AshleyE1Telemetry/atlas/tuning_<build>.jsonl`.
- Bounded, and chunked across alarm ticks, so it never blocks the game thread for more than 5 ms per tick.
- **KNOWN** state.

**P5.2: Offered scan** (`offered_scan`). For every object and Sim on the lot, it reads `super_affordances()` (the fivesim pattern) and writes `{object_id, object_def, affordance guid}`. **OFFERED** state.

**P5.3: The atlas store (helper).** `helper/domus_helper/atlas.py` keeps a SQLite `atlas.db` in the Domus data dir (not in the repo):
- tables `affordances`, `offered`, `cards`, `observations`, `exercises`;
- the ladder `KNOWN → OFFERED → OBSERVED → EXERCISED → QUALIFIED` (design D7);
- build-bound: a game patch moves entries back to KNOWN;
- MCP `atlas_query`.

**P5.4: Class cards: generalize the A10 learner.**
- `e2_registry.SignatureLearner` (`e2_registry.py:150–254`) becomes `CardLearner` with four effect classes:
  - **posture:** signature + continuation set, exactly today's behaviour;
  - **need:** a need delta while running;
  - **interaction:** our id RUNNING with no foreign roots;
  - **social:** the target + the interaction on both.
- `Experiment` reads its card's class.
- **Regression law:** the T1 and N5 evidence replays (`test_e2.py:452, 502`) stay green unchanged, since posture cards reproduce A10 byte for byte.

**P5.5: Calibration from native autonomy (A14's core).**
- A new arm option, `calibrate`: observing only, and actuation commands are refused.
- The learner accepts **`InteractionSource.AUTONOMY` entries as controls** (today only the Owner's `PIE_MENU` sit, `e2_registry.py:188–191`), with the same windows and exclusions.
- Autonomy is independent of the harness by source, so its entries are valid controls. Cards learned this way are tagged `control=AUTONOMY`.
- **The Owner demonstrates only when:**
  - an autonomy-learned card disagrees with the tuning (P5.1: posture or commodity), or
  - a verb never occurs natively.

**P5.5b: Autonomy as the guide** (Alex, 2026-10-01). Mapping is **autonomy-first**:
- Calibration sessions run with autonomy **on** in LAB saves: overnight, at high speed, with varied Sims (traits, ages) and objects placed in the LAB.
- The probe watches. Every autonomous interaction becomes an OBSERVED atlas entry with a control-learned card, and also data for the thalamus forward model: how often, how long, and need deltas per activity.
- The tuning dump (P5.1) tells which affordances autonomy can **never** do (not allowed autonomously). Only those, plus classes whose cards disagree with the tuning, go to the harness crawl (P5.6) or to Alex.
- Autonomy never makes an entry EXERCISED: that still needs Ashley's own attributed trials.

**P5.6: The crawl (helper, `runs/crawl.py`)** — Alex: unattended, LAB saves only. It covers what autonomy doesn't (P5.5b).
1. Pick the OFFERED entries without an EXERCISED record, class by class. **Ashley's priorities come first** once Ashley plan Phase 8 exists; until then, lowest effort first.
2. `sit_trial` generalizes to `trial <object_id> <affordance guid>`: prepare, then push through the actuator with the affordance chosen from the offered list. The actuator still does a single `push_super_affordance`.
3. Record the verdict; **QUALIFIED** comes at ≥ 3 attributed PASS with 0 unexplained `OUTCOME_UNKNOWN` on the current build.
4. `OUTCOME_UNKNOWN` goes to the trial analyzer (P5.7).

Runs are bounded: at most N trials per hour, stop on any `PUSH_FAILED` storm, stop on a lineage change. Every run leaves an evidence folder.

**P5.7: The trial analyzer (helper).** For each `OUTCOME_UNKNOWN` it compares foreign roots against that class's controls, and **writes a proposed card amendment** (a data-only JSON). It never auto-applies. Proposals go through the review flow (Grok authors, Codex reviews, the architect adjudicates), as D6 and D7 did.

---

## Phase 6: The peripheral thalamus + E3 (probe 3.0.0, with Ashley plan Phase 8)

**P6.1: The thalamus core (`helper/domus_helper/thalamus/`, pure).** It implements organism paper Part B exactly:
- percepts (B2);
- forward models: need decay per activity by EWMA, action duration from atlas cards, presence expectations from career schedules if exposed, otherwise from learned arrival times (B3);
- habituation with recovery and dishabituation (B4);
- lineage-aware novelty (B5);
- salience + a leaky arousal + a threshold from Mint (fatigue, mood, co-play) (B6);
- pressures: `ACTION_END`, boredom with "resting", the liveness heartbeat (B7);
- two clocks (B8);
- failure modes (B9);
- bounded learning from `wake_worth` (B10);
- the B11 defaults.

**The decision log** is a JSONL of every percept → salience → fired or not, and why.

**P6.2: Replay tests (B12) over the committed evidence:**
- T1: sit_Passive habituates to ~0 within 5 repetitions, and the sit completion gives `ACTION_END`;
- N5;
- P4: the 36× nap gives no wake storm;
- L3: the mid-session zone change resets the world model and orients;
- plus a synthetic suite.

A new thalamus version must pass the full replay corpus. **No shadow period** (Alex): the decision log is the audit trail, and Alex's post-hoc ratings feed B10.

**P6.3: The pause coupling.** A T1 need while Ashley is alone → helper → inbox `pause` (qualified in E2-P), then `release` when her Thought turn decides. Never during co-play: the helper knows the co-play mode from Mint.

**P6.4: E3 transport.**
- The helper posts notifications to Ashley's `POST /domus/observation` (Ashley plan Phase 8) over the Tailscale route, with a helper token. Alex creates the token; agents never handle credentials.
- **Retry with backoff; no fabricated catch-up.** A gap is sent as a `gap` percept.
- Liveness heartbeats go to a separate endpoint and never wake Thought.

**P6.5: Probe 3.0.0 = 2.4.0 + any read-only fields the thalamus needs** (e.g. interaction expected end, if exposed). There are no new actuation paths in E3. **E3 is perception-only** (design §17).

**P6.6: The E3 trial.**
- Prerequisites (design §17 E3):
  - the boundary verification test (Ashley side);
  - E3-M provenance (the lineage-marked memory, Ashley Phase 8);
  - E3-B1: Alex's budget number;
  - the helper running;
  - world currentness.
- **Session:** Alex plays normally in the LAB. Ashley perceives her body live, and she talks about it on Discord truthfully ("I sat down", "I'm getting hungry"). There is no actuation.
- Evidence: the telemetry, the decision log, the Ashley-side wake records, her Discord lines (Owner-private), and `E3_VERDICT_<date>.md`.

---

## Owner-gated actions (the complete list)

| # | Action | Phase |
|---|---|---|
| 1 | The Phase 0 session (N5 sit by hand, T trials with the clipboard helper) | 0 |
| 2 | Merge `e2-run` (and later `domus-next`) to `main` | 0+ |
| 3 | Keep the game closed during installs (the jobs check it) | 1, 2, 4, 5, 6 |
| 4 | Leave The Sims running in a LAB save for unattended crawls | 5 |
| 5 | A demonstration only where calibration disagrees with the tuning | 5 |
| 6 | Create the helper → Ashley token; set the embodiment budget (E3-B1) | 6 |
| 7 | The E3 trial session: play normally | 6 |

## Packet list for Manager (in order)

| Packet | Content | Coder | Reviewer | Live step |
|---|---|---|---|---|
| D-P0 | E2 close | — | architect | Alex's session |
| D-H1…H5 | hygiene → 2.1.0 | Grok | Codex (J106 style) | J108-style install |
| D-C1, C2 | cmdbox + probe inbox → 2.2.0 | Codex (box) | Grok | install |
| D-M1…M3 | helper core, MCP, trial runner | Codex (box) | Grok | agent-run T replay (acceptance) |
| D-S1 | senses → 2.3.0 | Codex (box) | Grok | install + agent-run evidence session |
| D-A1…A7 | atlas, cards, calibration, crawl, analyzer → 2.4.0 | Codex (box) | Grok | install + first unattended crawl |
| D-T1…T6 | thalamus, replays, pause coupling, transport, 3.0.0, E3 trial | Codex (box) | Grok | E3 session |

Each packet file will carry:
- goal, exact files, and the amendment text where the probe changes;
- red-first tests with fail-before rules;
- verification commands (pinned-Python suite, `check_guards.py`, `build.ps1`, `verify.ps1` including the new REPRODUCIBLE check);
- STOP conditions and an R1 results format;
- the no-go list: no Mint mutation, no Discord, no credentials, no The Finals; the game is touched only through install jobs or the MCP in LAB saves.
