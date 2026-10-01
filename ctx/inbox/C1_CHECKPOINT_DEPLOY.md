# C1: Owner order. Checkpoint deploy of both systems: Ashley to Mint, Domus probe 2.2.1 to the game.

From: Architect, relaying the **Owner** (~14:15 TRT). To: Manager → Operator. Results: `outbox\C1_RESULTS.md`.

> Owner: "i think we can deploy both at this point - thats a checkpoint."

This is the Owner's batch go (D-042) for Ashley, and the go to install probe 2.2.1. HOLD_NO_NEW_WORK still applies to everything else: A4, D13 and Part C stay held. **The two tracks are independent; one failing doesn't stop the other.**

## Track A: Ashley batch B3 to Mint

**Contents:**
- A3: friction, practice and senses (sidecar v46–v48);
- A3S: the credential-shape guard;
- GS1: `never_public` growth (sidecar v49).

Nuclear stays at v54.

1. **Wait for GS1a:** the GS1 merge is validated and pushed. Record the `origin/main` SHA as `DEPLOY_SHA`. The XQX checkout is on `main` at `DEPLOY_SHA`, since `start:ashley` deploys origin's tip.
2. **Fresh backup, then drill, on Mint:**
   - `systemctl --user start ashley-backup.service`, then wait. Check that `status.json` has a new `last_ok_ms` and that the remote listing shows the new package with `versions nuclear=54 / sidecar=45`;
   - then `systemctl --user start ashley-backup-drill.service`, and check that `drill_ok_ms` is set and `drill_error` is null **against that package**.
   - **If either fails: STOP Track A.** Don't deploy.
3. **Deploy:** from XQX repo root, `npm run start:ashley`. Its pre-step makes one more backup, which is fine.
4. **Post-deploy checks (read-only), each with evidence:**
   - activated SHA = `DEPLOY_SHA`, health ready, boot validation OK;
   - sidecar `schema_version` = **49**, nuclear `user_version` = **54**;
   - the new tables exist: `friction_events`, `sense_declines` (with `data_classification`), and `growth_revisions` accepting `practice`;
   - `ashley-agent` and `ashley-discord` active, with no `error`/`migration` failure lines in `journalctl --user` for 10 minutes (counts and codes only);
   - the backup timers are still listed.
5. **Slash commands:** run `npm run deploy-commands --prefix apps/discord-bot` on Mint (for A3's `/identity` practices view) and report success or failure. **No Discord messages as the Owner.**
6. **STOP conditions:**
   - a migration error;
   - activation that doesn't match `DEPLOY_SHA`;
   - a crashloop.

   Don't retry and don't roll back on your own. Report right away. Rollback (restoring the pre-deploy package with the A1 restore procedure) happens **only on the Owner's or architect's word.**

## Track B: Domus probe 2.2.1 to the game (on XQX)

1. **Bring `d11-autostart` (tip `7b5b778`) to XQX** with the usual bundle flow, fetching into `C:\Users\Xharv\Projects\Domus`.
2. **J118, the XQX gate** (Codex Sol low, verifier only). Use the `J116b` template (`_Internal\codex\queue\J116b_regate_probe_2_2_0.md`) with:
   - candidate `7b5b778` on `d11-autostart`, base `0605205` (`domus-next`), version **2.2.1**;
   - its own gate worktree;
   - the pinned CPython 3.7.0 suite and the host-Python suite, both with 0 failures and 0 errors;
   - `check_guards` OK;
   - `build.ps1 -Version 2.2.1`;
   - `verify.ps1` with REPRODUCIBLE and ZIPIMPORT, and **three equal BUILD_SHA256s**.
   - Report: `_Internal\codex\reports\J118_REPORT.md`.
   - **FAIL means STOP Track B.**
3. **PASS: merge.** Merge `d11-autostart` into `domus-next` with `--no-ff`. Message: `Merge d11-autostart (D11): import-time inbox autostart, tick error isolation, probe 2.2.1`. D11 is a bugfix, so no review. Push `domus-next` with a fast-forward only.
4. **J119, the install** (the `J117` template, `_Internal\codex\queue\J117_install_probe_2_2_0.md`, as amended by `J117b`):
   - **the game must be closed:** if `TS4_x64` is running, STOP and ask the Owner to close it;
   - take the BEFORE save and Mods inventory;
   - remove **2.2.0 only** and install 2.2.1;
   - post-install verify exactly as J117b: `verify.ps1 -Version 2.2.1 -HostPythonPath …` with 9 PASS, and the installed `ashley_e1_2.2.1.ts4script` sha256 must equal J118's hash;
   - the AFTER save inventory must be identical to BEFORE.
   - Evidence goes to `sims-e1\evidence\D11_INSTALL_2_2_1_<date>\`, with an evidence commit on `domus-next` and a fast-forward push.
   - **Never delete a save or a backup. Never launch the game.**
5. **Not in this checkpoint:** the D12 helper install (the `pip install mcp` into `helper/.venv` on XQX). That needs a separate Owner OK, and it stays held.
6. **The first live check happens the next time the Owner plays:** loading LAB_E1 should show `inbox_autostart = ZONE:<source>` in the status reply, with no `ashley_e1.inbox` console command needed. It's recorded when it happens, and it isn't part of C1.

## Report

`C1_RESULTS.md` gets one block per track: each step PASS, FAIL or STOP with its evidence, the SHAs and hashes, and the backup package name. Then stop: no more work under HOLD.

## Track C (added ~14:20, Owner OK): install the D12 helper on XQX

> Owner: "ok ofc, why do you even ask"

This replaces Track B item 5. It runs after Track B's merge, since the helper vendor sync is in D11-3.

1. In `C:\Users\Xharv\Projects\Domus\helper`, create `helper\.venv` from the host Python (≥3.12), the one the D12 report used.
2. `pip install --require-hashes -r <the helper lockfile>` **into that venv only.** It's never a global or user-site install.
   - Check that every package in the lock is a real dependency of `mcp==2.2.0`. Verify `httpx2`/`httpcore2` in particular against the `mcp` package metadata.
   - **If anything doesn't match, STOP.** Don't install, and report the package and the evidence.
3. `helper\.venv\Scripts\python -m pytest -q` must be green (47/47), and `python -m domus_helper.mcp_server --help` (or the module's smoke entry) must start and exit cleanly.
4. **Don't edit** `.mcp.json` or any Claude/Codex config beyond what the repo already ships. Report the venv path, the pip freeze hashes, and the test tallies.
5. **Don't launch the game, and don't call the MCP tools against a running game.** That's for the Owner session.
