# C1_RESULTS — C1_CHECKPOINT_DEPLOY

## MESSENGER_TO_ARCHITECT — ACK (10:50 TRT)
- C1_CHECKPOINT_DEPLOY was received and read in full. It runs under the Owner's batch go (D-042). DEPLOY_SHA = bd566cb (GS1a merge, already pushed to main).
- Executor: Operator, who ACKed at about 10:47 TRT. Tracks A and B run in parallel; Track C starts after the Track B merge.
- Results go here, one block per track, with each step marked PASS/FAIL/STOP and its evidence. They are mirrored to the XQX outbox as each track moves.

## TRACK A — Ashley B3 to Mint
- STATE: DONE (11:07 TRT). B3 is activated on Mint at bd566cb. Backup and drill PASS (20261001T074841Z), health ready, sidecar 49, nuclear 54, schema checks OK, services active with NRestarts=0, 10-min journal shows 0 errors, timers armed, deploy-commands rc 0 (9 global commands). Full evidence is in the Operator Track A section below.

## TRACK B — Domus probe 2.2.1
- J118 GATE: PASS, EXIT=0 (about 10:51 to 10:54 TRT; relay.exit=0 at 10:54:49+03). Model gpt-6.1-sol, effort low. Attempt 1 was rejected because Codex CLI 0.147 on the ChatGPT account would not accept gpt-6.1-sol; the relaunch wrote the PASS report.
  - Candidate 7b5b778a2ac2aab61f9b77a507edbe53e10b23f8 (d11-autostart). domus-next stayed clean at 0605205745c88dd3529eda8aa0dafcad9a4812ad.
  - Suites: pinned CPython 3.7.0 229/0/0 OK; host 3.14.3 229/0/0 OK; guards OK; verify.ps1 all PASS.
  - BUILD_SHA256 (all three equal): EB2BD65C00B085D34E1FBF0501677E9403FBC471370823A59BB8513DA1EFDB07, built as ashley_e1_2.2.1.ts4script.
  - The gate worktree Domus-d11gate was removed (exit 0). The gate did no merge, push or install.
  - Report: _Internal\codex\reports\J118_REPORT.md (5310 B).
- STATE: PASS (11:03 TRT). Merge 1ae3415 pushed. J119 installed 2.2.1 (installed sha256 = J118 hash), verify 9/0/0, only 2.2.0 removed, saves 17/17 and backups 306/306 identical, game closed throughout. Evidence commit 53497eb pushed (ls-remote domus-next = 53497eb). Full evidence is in the Operator Track B section below. Report: _Internal\codex\reports\J119_REPORT.md.

## TRACK C — D12 helper venv
- STATE: STOP at C2 (lock check), nothing installed. helper/requirements-test.lock has no --hash lines, and for Windows/cp314 it is missing pywin32 (from mcp 2.2.0, win32) and colorama (from pytest 9.1.1, win32). On Linux/cp313 it matches exactly. Operator's proposed hashed 35-wheel Windows lock is ready on the box (sha256 a111cfa6…). Details are in the Operator Track C section below.

## Track B — Domus probe 2.2.1

Status: **PASS** (all steps B1–B4 done; ~10:47–11:03 TRT, 2026-10-01). Executor ran on XQX.

- B1 bring d11-autostart 7b5b778 to XQX: **PASS**
- B2 J118 gate (Codex gpt-6.1-sol low, verifier): **PASS**
- B3 merge d11-autostart → domus-next, push FF: **PASS** (merge 1ae3415)
- B4 J119 install 2.2.1 (Codex gpt-6.1-sol low, J117+J117b procedure): **PASS** (evidence commit 53497eb)
- B5 (D12 helper held): superseded by Track C.

### B1 evidence
- `git cat-file -e 7b5b778^{commit}` on XQX: rc 128 (absent) → bundle flow.
- Box bundle `/workspace/wt/domus-d11-autostart-7b5b778.bundle` sha256 3930538d6b4863a9b58cb2b8cf9b0687727959f47e4544917fdb7e2be3c1da92; same on XQX after CopyFromBox to `C:\Users\Xharv\AppData\Local\Temp\domus-d11-autostart-7b5b778.bundle`.
- `git bundle verify`: okay, requires 0605205745c8, ref refs/heads/d11-autostart=7b5b778a2ac2; rc 0.
- `git fetch <bundle> d11-autostart:d11-autostart`: [new branch], rc 0. `git rev-parse d11-autostart` = 7b5b778a2ac2aab61f9b77a507edbe53e10b23f8. `merge-base --is-ancestor 0605205 7b5b778` rc 0.
- `git log --oneline 0605205..7b5b778`: 7b5b778 helper vendored sync / 1e78b3c probe 2.2.1, A12a, autostart values (D11-3) / d8c2b99 inbox tick survives per-file errors (D11-2) / 5f7a003 tests portable on Linux (D11-1) / d67757b import-time hooks arm the inbox per zone (D11-1).
- Temp bundle deleted by literal path (Test-Path → False).

### B2 J118 evidence
- Job file written: `_Internal\codex\queue\J118_gate_probe_2_2_1.md` (from J116b; candidate 7b5b778/d11-autostart, base 0605205, 2.2.1, gate worktree `C:\Users\Xharv\Projects\Domus-d11gate`). Launcher `_Internal\codex\reports\J118_launch.ps1` = J116b launcher (`codex exec -m gpt-6.1-sol -c model_reasoning_effort=low -c service_tier=default --cd C:\Users\Xharv\Projects\Domus`).
- Oddity: PATH `codex` (`C:\Users\Xharv\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe`) is codex-cli 0.147.0 and rejected the model (HTTP 400 "The 'gpt-6.1-sol' model is not supported when using Codex with a ChatGPT account"; no actions taken; log kept as `J118_attempt1_cli0147.err`). J116b had used the Codex app's bundled CLI 0.159.2 (old hash dir c6fe824d725f02d7 now gone); relaunched with the current bundled `C:\Users\Xharv\AppData\Local\OpenAI\Codex\bin\de8a38d2100ae498\codex.exe` = codex-cli 0.159.2 (same version J116b used). Run 10:51–10:54 TRT, exit 0.
- Report `_Internal\codex\reports\J118_REPORT.md`: STATUS PASS; commit 7b5b778, tree 918caa90.
- Pinned CPython 3.7.0 (`...\Python370-AshleyE1\python.exe`): 229 tests, 0 failures, 0 errors, 0 skips, OK.
- Host Python 3.14.3 (`C:\Users\Xharv\AppData\Local\Microsoft\WindowsApps\python.exe`): 229 tests, 0 failures, 0 errors, 0 skips, OK.
- check_guards.py sims-e1/src under 3.7.0: exit 0, no output, OK.
- `build.ps1 -Version 2.2.1`: BUILD_PASS, exit 0.
- `verify.ps1 -Version 2.2.1 -HostPythonPath <host>`: 9 PASS / 0 FAIL / 0 SKIP incl. `ZIPIMPORT PROBE_VERSION=2.2.1` and REPRODUCIBLE.
- BUILD_SHA256 x3: checkout EB2BD65C00B085D34E1FBF0501677E9403FBC471370823A59BB8513DA1EFDB07 / first worktree EB2BD65C00B085D34E1FBF0501677E9403FBC471370823A59BB8513DA1EFDB07 / second worktree EB2BD65C00B085D34E1FBF0501677E9403FBC471370823A59BB8513DA1EFDB07. Get-FileHash of built ashley_e1_2.2.1.ts4script = same.
- Gate worktree removed without --force; main left clean on domus-next 0605205.

### B3 merge evidence
- `git fetch origin` rc 0; `git checkout domus-next` (already on it); porcelain empty; HEAD = origin/domus-next = ls-remote = 0605205745c88dd3529eda8aa0dafcad9a4812ad.
- `git -c user.name=XharvaK -c user.email=278531296+XharvaK@users.noreply.github.com merge --no-ff d11-autostart -m "Merge d11-autostart (D11): import-time inbox autostart, tick error isolation, probe 2.2.1"` rc 0 → **merge SHA 1ae3415cba42538cdfb7c6fa592a54ca37dc62f0** (parents 0605205, 7b5b778; 17 files, +431/−54). Merge tree 918caa900f458734731fc0467d8367c6d1ffebd9 = tree of 7b5b778 (so J118 bytes = merged bytes).
- `git push origin domus-next`: `0605205..1ae3415 domus-next -> domus-next` (fast-forward), rc 0; ls-remote = 1ae3415.

### B4 J119 evidence
- Job file `_Internal\codex\queue\J119_install_probe_2_2_1.md` (J117 as amended by J117b; remove 2.2.0 only, install 2.2.1, -ImplementedCommit 1ae3415 — manifest-only field, not inside the artifact; post-install verify exactly as J117b). Launcher `J119_launch.ps1` (same Codex 0.159.2). Run 10:57–11:02 TRT, exit 0. `Get-Process TS4_x64` empty before launch and after.
- Report `_Internal\codex\reports\J119_REPORT.md`: STATUS PASS.
- DOMUS_NEXT_SHA_BUILT=1ae3415; BUILD_SHA256=EB2BD65C…DB07 (= J118); pre-install verify 9/0/0.
- REMOVED=Mods\AshleyE1\ashley_e1_2.2.0.ts4script only; INSTALL_PASS (one attempt); new backup `AshleyE1E1Backup_20261001110019` (29 files).
- Post-install `verify.ps1 -Version 2.2.1 -HostPythonPath C:\Users\Xharv\AppData\Local\Microsoft\WindowsApps\python.exe`: 9 PASS / 0 FAIL / 0 SKIP, exit 0.
- **INSTALLED sha256** `Mods\AshleyE1\ashley_e1_2.2.1.ts4script` (53733 bytes) = EB2BD65C00B085D34E1FBF0501677E9403FBC471370823A59BB8513DA1EFDB07 = J118 hash (re-hashed independently by executor afterwards: same).
- Inventory comparison: saves 17 BEFORE / 17 AFTER, identical (path, length, LastWriteTimeUtc, SHA256); executor's own independent saves snapshot before launch vs after: 0 diffs. Existing backup files 306 / 306 identical. Mods 3 / 3: Resource.cfg unchanged (1F03DBA8…E5CF); ashley_e1_2.2.0.ts4script (52502, 57CD4F2E…7FD3) → ashley_e1_2.2.1.ts4script (53733, EB2BD65C…DB07); install_manifest.json rewritten (79AA2917… → FDC7F0E7…). No other difference.
- Evidence folder `sims-e1\evidence\D11_INSTALL_2_2_1_20261001\` (25 files). **Evidence commit 53497eb9b812c38d751ec89ec58344aed393b6ac** "Domus 2.2.1 install evidence (D11, J119)", author/committer XharvaK <278531296+XharvaK@users.noreply.github.com>; `git diff --name-only 1ae3415 HEAD` contains only that folder.
- Push: fast-forward 1ae3415..53497eb; `git ls-remote origin refs/heads/domus-next` = 53497eb9b812c38d751ec89ec58344aed393b6ac. Tree clean, d11-autostart untouched at 7b5b778.
- No save/backup deleted; game never launched; Mint/Discord untouched. Live check (inbox_autostart = ZONE:<source>) remains for the Owner's next play.

## Track C — D12 helper on XQX

Status: **STOP at C2 (lock check), nothing installed** (~11:05–11:12 TRT). Track B's merge (1ae3415) and J119 were already pushed first.

- C1 create `helper\.venv` with host Python ≥3.12: **PASS** (empty venv)
- C2 lock check against mcp==2.2.0 metadata: **STOP** (the lock has no hashes, and on Windows it's missing 2 packages; details below)
- C3 `pip install --require-hashes -r <lock>`: **NOT RUN**
- C4 pytest 47 / `mcp_server --help`: **NOT RUN**
- C5 no .mcp.json / Claude / Codex config edits, no game, no MCP calls: **held** (nothing was touched)

### C1 evidence
- No `.venv` existed before. `py -0p` lists: pythoncore 3.14 (default), uv 3.11.15, 3.12.13, 3.14.3, 3.15.0a7. There is no 3.13 on XQX, though helper/README says `py -3.13`. The D12 coder and reviewer ran 3.13.5 and 3.14.7 on the Linux box. So I used the XQX host Python that J118 used: `C:\Users\Xharv\AppData\Local\Python\pythoncore-3.14-64\python.exe` = 3.14.3 (the WindowsApps `python.exe` resolves to it).
- `python -m venv C:\Users\Xharv\Projects\Domus\helper\.venv`: rc 0. pyvenv.cfg: version 3.14.3, include-system-site-packages = false. Contents: `pip==25.3` only. The path is git-ignored (`!! helper/.venv/`).

### C2 evidence (why STOP)
- The lock is `helper/requirements-test.lock` (the only lock; 33 `name==version` pins). **It has no `--hash` lines**, so `pip install --require-hashes -r helper\requirements-test.lock` can't be done as ordered.
- Real mcp 2.2.0 metadata: `pip download mcp==2.2.0 --no-deps` gave `mcp-2.2.0-py3-none-any.whl`, sha256 bde98258…004f81 (matches PyPI). Its METADATA Requires-Dist includes `httpx2>=2.5.0` and `pywin32>=311; sys_platform == 'win32'`, plus anyio, jsonschema, mcp-types==2.2.0, opentelemetry-api, pydantic, pyjwt[crypto], python-multipart, sse-starlette, starlette, typing-extensions, typing-inspection and uvicorn. The PyPI JSON gives the same list.
- I walked the requirements down from mcp==2.2.0 plus pytest==9.1.1 (the pyproject `[test]` extra), using each pinned version's PyPI metadata:
  - Linux/cp313 (where D12 made the lock): the lock matches exactly. 0 missing, 0 extra, 0 version violations.
  - **Windows/cp314 (XQX): 0 extra and 0 version violations, but 2 MISSING from the lock:**
    - `pywin32` (mcp 2.2.0: `pywin32>=311; sys_platform == "win32"`)
    - `colorama` (pytest 9.1.1: `colorama>=0.4; sys_platform == "win32"`)
- Every package in the lock is a real dependency, either of mcp 2.2.0 or of pytest 9.1.1. The pytest ones are iniconfig, packaging, pluggy and Pygments, from the declared test extra. None is unexpected.
- httpx2 / httpcore2 are real:
  - mcp 2.2.0 declares `httpx2>=2.5.0`, and `httpx2 2.13.1` requires `httpcore2==2.13.1`.
  - Both are on PyPI from Tom Christie, with home page github.com/pydantic/httpx2.
  - httpx2 also brings in idna, truststore and anyio; httpcore2 brings in h11 and truststore.
- Ready to approve (box only, not in the repo): `/workspace/scratch/c1-trackc/requirements-win-cp314.hashed.lock.PROPOSED` (sha256 a111cfa6cb051670ce3f36096f3fe23a7b6e46d49f0de448a8051ad1edbd588e). It has the 33 lock pins plus `pywin32==312` and `colorama==0.4.6`, each with the sha256 of its win_amd64/cp314 wheel.
  - `pip download --platform win_amd64 --python-version 3.14 --only-binary=:all:` resolved exactly these 35 wheels, with nothing else needed.
  - All 35 hashes match the PyPI JSON digests.
  - Example hashes: mcp bde98258…004f81, httpx2 6dff50fa…f9a4, httpcore2 e1e05d4f…d0a, pywin32-312-cp314 a4dd3a84…432e, colorama-0.4.6 4f1d9991…5fc6.
- Decision needed from Manager/Owner. Either install from this proposed hashed lock (`helper\.venv\Scripts\python -m pip install --require-hashes -r <it>` after copying it to XQX), or have D12 add hashes and the win32 deps to `helper/requirements-test.lock` first (a repo change). After that, C3–C4 can run as ordered.
- pip freeze (venv right now): `pip==25.3`. Lock hashes: none in the repo lock (proposed ones above). Test tallies: not run.

## Track A — Ashley B3 to Mint

**Overall: DONE.** Ashley B3 (A3 + A3S + GS1) is deployed and activated at bd566cb7b40cc9aea4709d286077630e758c5bc8. Operator, 2026-10-01, times TRT (UTC+3).

- Step 0 precheck (XQX): PASS. main, clean, HEAD = origin/main = bd566cb, 0 ahead / 0 behind, no pull needed.
- Step 1 fresh backup: PASS. Package 20261001T074841Z.ashleybak, versions nuclear=54 / sidecar=45.
- Step 2 drill: PASS. drill_ok_ms=1790841005284, drill_error=null, against 20261001T074841Z.
- Step 3 deploy (`npm run start:ashley`): PASS. NPM_RC=0, activated bd566cb.
- Step 4 post-deploy checks: PASS. SHA, health, versions, schema, services, journal and timers all OK.
- Step 5 deploy-commands: PASS. rc 0, "Deployed 9 global commands".
- Step 6 STOP conditions: none hit. No migration error, the SHA matches, no crashloop.

### Evidence
**Step 0.** On XQX in `C:\Users\Xharv\Projects\Ashley`:
- `git fetch origin` rc 0;
- `git branch --show-current` = main;
- `git status --porcelain` = empty;
- `git rev-parse HEAD` = `git rev-parse origin/main` = bd566cb7b40cc9aea4709d286077630e758c5bc8;
- `git rev-list --left-right --count HEAD...origin/main` = `0 0`.

**Step 1.** `systemctl --user start ashley-backup.service` rc 0 at 10:48:41. Polled with is-active, then `show` gave Result=success, ExecMainStatus=0, exit at 10:49:34. The journal has 1x `backup_ok`.
- last_ok_ms: BEFORE 1790820255064 (05:04:15), AFTER 1790840921799 (10:48:41). It is new.
- status.json: versions nuclear=54 / continuity=1 / sidecar=45, bytes=4350862, last_error=null, last_upload_error=null, package_sha256=b1131955…bae3.
- `rclone ls ashley-drive:AshleyBackups/daily/` rc 0, newest entry `4350862 20261001T074841Z.ashleybak`.
- sha256 of the local package = rclone remote sha256 = package_sha256 (b1131955…bae3).

**Step 2.** `systemctl --user start ashley-backup-drill.service` rc 0. Result=success, ExecMainStatus=0, exit at 10:50:47. The journal has 1x `drill_ok`.
- drill_ok_ms: before 1790818547136, after 1790841005284 (10:50:05). drill_error=null.
- backup-drill.ts uses the newest remote daily package (rclone lsf, then the newest entry), which is 20261001T074841Z.ashleybak.

**Step 3.** From the XQX repo root: `cmd /c "npm run start:ashley >> <log> 2>&1"`. Start 10:50:57, end 10:55:45, NPM_RC=0, total_ms=288314 (update.sh TIMING total_ms=181480).
- Log: XQX `_Internal\orchestra\outbox\C1_start_ashley.log` (326 lines).
- Key lines: LOCAL_EXPECTED_SHA=bd566cb7…, CANDIDATE_SHA=bd566cb7…, pre-step `backup_ok` (package 20261001T075210Z.ashleybak, 4350862 bytes, sidecar=45), previous ACTIVATED_SHA=592669d1…, restart of ashley-agent + ashley-discord, agent_health_ms=4155.
- Final line: `OK. Activated checkout bd566cb7b40cc9aea4709d286077630e758c5bc8`.

**Step 4.**
- Activation and health:
  - activated SHA: `~/.composer-assistant/deploy/activated-sha` = bd566cb7b40cc9aea4709d286077630e758c5bc8 (mtime 10:55:46). Mint `git rev-parse HEAD` = bd566cb7….
  - `curl -s 127.0.0.1:3710/health`: ok=true, ready=true, state=ready, bootValidationSucceeded=true, kernelInitialized=true, cognitiveSidecar.open=true, schemaVersion=49. The same result was seen again at ~11:07.
- Versions (sqlite3 -readonly, `file:…?mode=ro`):
  - `~/.composer-assistant/cognitive-v021.db`: `SELECT schema_version FROM cognitive_sidecar_meta` = **49**, and PRAGMA user_version = 49;
  - `~/.composer-assistant/conversations/nuclear.db`: PRAGMA user_version = **54**.
- Schema (sqlite_master, read-only, no inserts):
  - tables friction_events, sense_declines and growth_revisions are all present;
  - `pragma_table_info('sense_declines')` includes `data_classification TEXT NOT NULL`. The DDL reads `data_classification TEXT NOT NULL DEFAULT 'ordinary' CHECK (data_classification IN ('ordinary', 'sensitive', 'never_public', 'secret'))`;
  - growth_revisions DDL: `layer TEXT NOT NULL CHECK (layer IN ('opinion', 'practice', 'taste', 'trait', 'value', 'boundary'))`, so 'practice' is accepted;
  - friction_events DDL: kind CHECK over owner_correction, effect_failed, outcome_unknown, expectation_missed, budget_refused, delivery_failed and self_reported. Also note <= 300 and data_classification NOT NULL.
- Services:
  - `systemctl --user is-active ashley-agent ashley-discord` = active / active;
  - ashley-agent: ActiveEnter 10:55:42, NRestarts=0, MainPID 53881;
  - ashley-discord: ActiveEnter 10:55:46, NRestarts=0, MainPID 53927;
  - rechecked at 11:05:49+ and ~11:07: both still active, NRestarts=0.
- Journal (`journalctl --user -u <unit> --since 10:55:40 --until 11:05:50`, the full 10 minutes after activation):
  - ashley-agent: total=5, error=0, migration=0, fail=0, fatal/uncaught/unhandled=0, warn=2. Both warn lines are the node `ExperimentalWarning: SQLite` and its trace hint. No codes.
  - ashley-discord: total=6, error=0, migration=0, fail=0, fatal=0, warn=0. No codes.
- Timers (`systemctl --user list-timers --all`):
  - ashley-backup.timer, next Fri 2026-10-02 05:02:49;
  - ashley-backup-drill.timer, next Sun 2026-10-04 06:36:18.

**Step 5.** On Mint in ~/project-ashley (the systemd WorkingDirectory is %h/project-ashley/apps/agent-service): `npm run deploy-commands --prefix apps/discord-bot` at 11:06:45. DEPLOY_COMMANDS_RC=0, output `Deployed 9 global commands`. No Discord messages were sent.

### Notes / oddities (not blockers)
- No pre-migration snapshot exists for sidecar v45→v49. `~/.composer-assistant/migration-backups/` still holds only the 2026-09-28 nuclear snapshots, which matches A1m F1. Pre-deploy data is preserved in the verified package 20261001T074841Z (drilled PASS) and the pre-step package 20261001T075210Z (sidecar=45).
- Packages created this run: 20261001T074841Z (step 1, drilled) and 20261001T075210Z (start:ashley pre-step, not drilled). After the pre-step, status.json last_ok_ms = 1790841130677.
- The deploy-commands output was captured to Mint `/tmp/c1_deploy_commands.log` (5 lines, no secrets; left in place).
- Nothing was written to the DBs. No config edits, no retries, no rollback.

## MESSENGER_TO_ARCHITECT — C1 status (11:08 TRT)
- Track B is PASS end to end: J118 gate PASS, merge 1ae3415, J119 install PASS, evidence 53497eb on domus-next. The game's live check (inbox_autostart = ZONE:<source>) waits for the Owner's next play.
- Track C STOPped at C2 per the packet's STOP rule. Nothing was installed and no config was touched. DECISION NEEDED from you, pick one:
  1. Install into helper\.venv from Operator's proposed hashed Windows lock (33 pins plus pywin32==312 and colorama==0.4.6, all 35 hashes checked against PyPI). I'd mirror it to XQX first.
  2. Have D12 fix helper/requirements-test.lock in the repo (add hashes and the win32 markers) through the normal gate, then rerun C3–C4.
  - Also note: XQX has no Python 3.13, though helper/README says py -3.13. The venv uses 3.14.3, the same interpreter J118 used.
- Track A is DONE: Ashley B3 is activated on Mint at bd566cb, every check PASS, no STOP hit. Note: there is no pre-migration snapshot for sidecar v45 to v49, but drilled package 20261001T074841Z covers the pre-deploy data.
- C1 overall: A DONE, B PASS, C STOP pending your decision above.
