# HANDOFF: Domus, Ashley's Sims 4 embodiment (single implementer)

**Read this first, then start.** It's written for **one agent working alone**: Codex app (Sol 6.1, light), CommandCode (Muse), or Grok Build CLI. There's no orchestrator, Manager, box or separate reviewer any more. **You implement, test, gate, self-review and report to the Owner (Alex).** The Owner plays the game, decides merges to `main`, and gives every install the go.
**Date:** 2026-10-01.
**Repo:** `C:\Users\Xharv\Projects\Domus` (private GitHub `XharvaK/Domus`). Branches: `main` (E2 merged, `dbc382c`) and `domus-next` (integration).
**Private notes:** `C:\Users\Xharv\Projects\Ashley\_Internal\` (never commit any of it).

---

## 1. Your sources (read in this order, only what the task needs)

1. **This file.**
2. **The roadmap:** `_Internal\papers\DOMUS_ROADMAP_v1.md`. It's also an Owner-facing doc: https://claude.ai/code/artifact/183a3943-c13b-4ddd-a9e4-fcc58a9a6a43.
   - §0.8: Sims law and observer purity.
   - §0.9: the Domus decision ledger DD-1…DD-9.
   - Part 3: every packet.
   - Part 6: the LAB sessions.
   - Part 0's multi-agent parts (Manager, the bus) **no longer apply.** Its engineering rules **still apply.**
3. **The design law:** `docs/PROJECT_ASHLEY_SIMS4_EMBODIMENT_DESIGN_V7_3_2a.md` in the Domus repo. Read only the section your packet names.
4. **The research with the 1.128 facts** (file:line from the installed game's decompiled scripts):
   - `_Internal\orchestra\outbox\R_F3_DOMUS_RESEARCH.md`;
   - `R_M1_RESULTS.md`;
   - `R_F1_FUTURE_RESEARCH.md` (F3–F7, F15).

**Context discipline:**
- grep first, read slices of ≤150 lines, never a whole file over 200 lines;
- run unittest with `| Select-Object -Last 40`;
- keep notes in your report instead of re-reading.

## 2. State right now (verify before you act)

| Fact | Value | Verify |
|---|---|---|
| Stages | E1 accepted, E2 accepted and merged to `main` (`dbc382c`). **E0 unknown:** ask the Owner | `sims-e1/evidence/E1_ADJUDICATION_2026-09-29.md`, `E2_VERDICT_2026-10-01.md` |
| `domus-next` | **`6feb853`**: the helper's hashed Windows lock, on top of `53497eb` (2.2.1 install evidence) and `1ae3415` (D11 merge), on top of 2.1.0 hygiene, the 2.2.0 command inbox and the D12 helper + MCP | `git fetch; git log --oneline -3 origin/domus-next` |
| D11 (probe 2.2.1) | branch `d11-autostart` `7b5b778`. **J118 gate PASS**, BUILD_SHA256 `EB2BD65C00B085D34E1FBF0501677E9403FBC471370823A59BB8513DA1EFDB07` | `_Internal\codex\reports\J118_REPORT.md` |
| Checkpoint C1 | **All done.** Track B: D11 merged, 2.2.1 installed (J119). Track C: helper `.venv` installed by the architect on XQX (Python 3.14.3, `--require-hashes` from `helper/requirements-test-win.lock`, pytest 47 passed) | `_Internal\orchestra\outbox\C1_RESULTS.md` |
| Helper | Ready: `C:\Users\Xharv\Projects\Domus\helper\.venv\Scripts\python.exe -m domus_helper.mcp_server` (stdio MCP; `.mcp.json` at the Domus root) | `helper\README.md` |
| Installed probe | **2.2.1** (J119 PASS, installed hash EB2BD65C…DB07, saves identical) | Mods: `C:\Users\Xharv\OneDrive\Belgeler\Electronic Arts\The Sims 4\Mods` |
| Game | 1.128.90.1030 at `E:\SteamLibrary\steamapps\common\The Sims 4\` | — |
| Telemetry / command inbox | `C:\Users\Xharv\OneDrive\Belgeler\Electronic Arts\The Sims 4\AshleyE1Telemetry\` (`cmd\inbox`, `outbox`, `done`) | — |

**The checkpoint is complete.** Mod 2.2.1 is installed and the helper is ready. Your first task is **S1, the live session with the Owner** (below).

**If the helper's venv ever needs rebuilding:**
1. `py -3.14 -m venv helper\.venv`
2. `helper\.venv\Scripts\python -m pip install --require-hashes -r helper\requirements-test-win.lock`
3. `cd helper; .venv\Scripts\python -m pytest -q` must report 47 passed.

On Windows, always use `requirements-test-win.lock`. The plain `requirements-test.lock` is Linux-only and has no hashes.

## 3. The work queue (in order)

| # | Item | Kind | Roadmap section |
|---|---|---|---|
| 1 | ~~Finish C1~~ **DONE** (2026-10-01) | ops | — |
| 2 | **S1, a live session with the Owner** (he plays; you drive the helper MCP) | live | Part 6 S1 |
| 3 | **DS1: senses, probe 2.3.0.** Amends `_Internal\orchestra\inbox\D13_PHASE4_SENSES.md`: no `get_value`; cached value + age; no timeout read; extended tripwire | feature | Phase 4 → DS1 |
| 4 | **DS2:** detected build + fingerprints (helper) | feature | DS2 |
| 5 | LAB L0 with the Owner | live | Part 6 |
| 6 | **DA1 → DA7:** atlas, cards, calibration, crawl, analyzer (probe 2.4.0) | features | Phase 5 |
| 7 | **E3 path DT1 → DT4, then the E3 trial.** Needs Ashley 8a–8d (see `HANDOFF_ASHLEY.md`) | features | E3 |
| 8 | E4 → E7 per the roadmap (R-E6 research first for co-play) | features | E4–E7 |
| — | DX1 helper IPC fixes, any time | bugfix | Cross-cutting |

**S1 checklist** (only today's MCP tools: `status`, `lineage`, `telemetry`, `verdicts`; nothing invented):
1. The Owner launches the game and loads LAB_E1.
2. `status()` must show probe 2.2.1 and `inbox_autostart = ZONE:<source>`, with **no** `ashley_e1.inbox` console command typed.
3. `inbox_errors` is 0.
4. Run `lineage()`, then `telemetry(n=50)`.
5. Live reads for DS1: the six motive GUIDs (hunger 16656, energy 16654, bladder 16652, hygiene 16657, fun 16655, social 16658), checked against the commodities present, and the moodlet count against the in-game panel.

   This needs a read-only probe field. If 2.2.1 doesn't expose one, note it as an input to DS1.
6. Write `sims-e1/evidence/S1_<date>/session.md` and commit it on `domus-next`.

## 4. How to run one packet alone (the loop)

1. **Brief yourself:** write `_Internal\work\<ID>_BRIEF.md` with GOAL / SCOPE / DO / DON'T / tests / STOP from the roadmap, plus a BUDGET line: commit at each green step. If a packet is much bigger than ~25 tool turns, split it.
2. **Branch** from `origin/domus-next`, for example `ds1-senses`.
3. **Red first:** run the new tests under the **pinned Python 3.7.0** and record the failing assertion. A collection error doesn't count.

   ```powershell
   cd C:\Users\Xharv\Projects\Domus\sims-e1\tests
   & C:\Users\Xharv\AppData\Local\Programs\Python\Python370-AshleyE1\python.exe -m unittest discover 2>&1 | Select-Object -Last 40
   ```

4. **Green.** Then run `python sims-e1\tools\check_guards.py sims-e1\src` with the pinned Python; it must exit 0, and you never edit the guard without an Owner decision (§6). Then commit.
5. **Version:** every probe change is a **new version**:
   - move the version at every site (`rg -n "2\.2\.1"`), and every test that pins the **current** version;
   - historical amendment text stays byte-exact;
   - add a byte-exact amendment row (A13, A14…) in the packet's evidence;
   - list every moved pin in the report.
6. **Self-review** (replaces the separate Auditor):
   - check the diff against the packet's DO, DON'T and review focus;
   - re-run ≥2 new tests per commit at that commit's parent;
   - **every game-facing call in the diff must be a getter or an iteration that passes the purity table (roadmap §0.8)**: list each name with its file:line;
   - write BLOCKING / NONBLOCKING / NOTE, and fix any BLOCKING before reporting.
7. **Gate on XQX** (the old J-gate; you run it):
   - in a fresh worktree (`git worktree add ..\Domus-gate <branch>`), run the pinned 3.7.0 suite and the host-Python suite, both with 0 failures;
   - run `check_guards`;
   - run `sims-e1\tools\build.ps1 -Version <v>`;
   - run `sims-e1\tools\verify.ps1 -Version <v> -HostPythonPath C:\Users\Xharv\AppData\Local\Microsoft\WindowsApps\python.exe`;
   - **every check must PASS, including REPRODUCIBLE and ZIPIMPORT, with three equal BUILD_SHA256s.** Record the hash, then remove the worktree.
8. **Report** to `_Internal\work\<ID>_REPORT.md`. The first line is `STATUS: DONE` or `STATUS: STOPPED`, followed by: items MET or NOT MET with file:line, the red-first runs, the gate output and hash, and the self-review.
9. **Push the branch** and tell the Owner in one message: what's done, the branch, the hash, and "merge into domus-next and install?"
10. **On his OK,** merge into `domus-next` with `--no-ff`, push (fast-forward only), then **install (§5)**. **Merging `domus-next` into `main` is the Owner's call.** Ask when a stage completes.

**On a STOP:** stop, keep everything, write the blocker and the options, and ask the Owner. Never work around it.

## 5. Install procedure (game CLOSED; the old J117 template)

1. If `Get-Process TS4_x64 -ErrorAction SilentlyContinue` returns anything, STOP and ask the Owner to close the game.
2. The tracked tree is clean, on `domus-next` at the gated SHA. `git ls-files --eol sims-e1/src` shows no `w/crlf` for `.py` files.
3. **BEFORE inventory:** every save and backup file, with SHA256, written to `sims-e1\evidence\<ID>_INSTALL_<v>_<date>\`.
4. Build and verify in the checkout. BUILD_SHA256 must equal the gate hash, or STOP before removing anything.
5. Run `remove.ps1 -Version <old>`, which must remove **only** `ashley_e1_<old>.ts4script`. Then run `install.ps1 -Version <v>`.
6. **Post-install verify:** run `verify.ps1 -Version <v> -HostPythonPath …`, which must show 9 PASS. Then `Get-FileHash` the installed `ashley_e1_<v>.ts4script` in Mods, which must equal the gate hash.
7. **AFTER inventory** must be identical to BEFORE, or STOP.
8. Write `install_summary.md` in the evidence folder. Commit **only that folder** on `domus-next` with the message `Domus <v> install evidence (<ID>)`, then push (fast-forward only).

**Never delete a save or a backup. Never launch the game.**

## 6. Sims law and the Owner's decisions (non-negotiable)

**The law:**
- One world, one Ashley.
- Engine scripting only, never keyboard or mouse emulation.
- The mod does no network I/O.
- The mod is inert outside bound saves.
- `check_guards.py` is law.

**Decided by the Owner on 2026-10-01** (roadmap DD-1…DD-3):
- **HOME object edits** (buy, place, move, rotate, sell): approved as a narrow typed adapter with a spending cap. `destroy` stays forbidden.
- **Co-play = "teleport in and out":** the Owner's avatar emerges at HOME when he joins and is **fully frozen** while away (no aging, needs, career or story). Guest control is approved; **there is no roommate fallback.**
- **Scripted saves:** approved, at qualified safe points only.
- Each of these is still a **named, narrow guard amendment** inside its packet, actuator-only, with a test.
- **Native critical-need actions** are rare and are recorded as `NATIVE_OVERRIDE`. Ashley handles her needs before they reach distress.

**Still the Owner's call** (ask; don't decide):
- DD-6, the lazy-update `get_value`. Default: cached value + age only.
- Physiological delegation (OD4).
- The pause failure lease (OD5; 120 s recommended).
- The spending cap.
- The cadence and budget numbers.
- The E0 status.
- The mod set.

**Observer purity (1.128):** these are NOT pure:
- `get_statistic`/`get_value` (they can create statistics);
- `ContinuousStatistic.get_value` (it updates the value and notifies);
- `Buff.get_timeout_time`;
- `get_active_whimset_data`;
- `potential_interactions`.

If your read needs one of them, STOP.

**Time:** at Normal speed, 1 real second ≈ 40 game seconds. Plan in game ticks.

## 7. Cross-repo pacing

The E3 path needs Ashley-side pieces first: ingress 8a, lineage 8b, tripwire 8c, nucleus and budget 8d, co-play lease 8e. E4 needs 8f and Session R. Those are in `HANDOFF_ASHLEY.md`. If one agent does both repos, run Ashley Phase 4 while Domus does DS1–DA7. Then do Ashley 8a–8e before DT1.

## 8. Notes per model

- **Sol 6.1 light:** keep steps small. When you resume, put a STATE block in your brief (done, failing, anchors already mapped). This turned a stalled job into a 16-turn finish here.
- **Muse (CommandCode):** effort **high**, never xhigh.
- **Grok Build CLI:** the same loop, run directly on XQX. The pinned Python and the game files are only on XQX.
- **Any model, when context gets long:** write the report so far, commit, and continue fresh from its STATE.
