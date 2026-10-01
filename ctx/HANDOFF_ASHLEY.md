# HANDOFF: Ashley (single implementer)

**Read this first, then start.** It's written for **one agent working alone**: Codex app (Sol 6.1, light), CommandCode (Muse), or Grok Build CLI. There's no orchestrator, Manager, box or separate reviewer any more. **You implement, test, self-review and report to the Owner (Alex).** The Owner decides merges and deploys.
**Date:** 2026-10-01.
**Repo:** `C:\Users\Xharv\Projects\Ashley` (public GitHub `XharvaK/Ashley`, branch `main`).
**Private notes:** `C:\Users\Xharv\Projects\Ashley\_Internal\` (gitignored, never commit it).

---

## 1. Your sources (read in this order, only what the task needs)

1. **This file.**
2. **The roadmap:** `_Internal\papers\ASHLEY_ROADMAP_v1.md`. It's also an Owner-facing doc: https://claude.ai/code/artifact/33beb2c5-df7d-42af-b13b-fc077c52a3e2.
   - **Part 3** has every packet: GOAL, SCOPE, DO, tests, STOP, review focus.
   - **Part 0** is the operating manual. Its multi-agent parts (Manager, the bus, the harness rotation) **no longer apply.** Its engineering rules (§0.4) and decision ledger (§0.7) **still apply.**
3. **Repo `AGENTS.md`:** the governance and reading routes for the code area you touch.
4. **Packet details, only for the packet you're doing:**
   - `_Internal\orchestra\inbox\A4_PHASE4_C4_GRADUATION_PORT.md` (the full A4 spec), **plus `A4a_TEST_PORT_RULING.md` (it amends A4 Build items 2–3; it wins on conflict)**;
   - `_Internal\papers\R_F1_ARCHITECT_REVIEW.md` (rulings that amended the plan);
   - research in `_Internal\orchestra\outbox\R_F*_RESEARCH.md`.

**Context discipline** (your budget is small, so treat this as a rule):
- grep first, read slices of ≤150 lines, never a whole file over 200 lines;
- quiet tests: `--reporter=dot`, with output to a file and only the summary and failures read back;
- keep notes in your report instead of re-reading.

## 2. State right now (verify before you act)

| Fact | Value | Verify |
|---|---|---|
| `main` | `bd566cb` (A3 + GS1 merged) | `git fetch; git log --oneline -3 origin/main` |
| Mint (production) | **`bd566cb`**: deployed 2026-10-01 by C1 Track A. Backup and drill PASS (package 20261001T074841Z), sidecar v49, nuclear v54, services clean, slash commands updated | `_Internal\orchestra\outbox\C1_RESULTS.md`, "TRACK A" |
| Sidecar schema at main | v49 | `COGNITIVE_SIDECAR_SCHEMA_VERSION` in `apps/agent-service/src/core/cognitive-v021/types.ts` |
| Nuclear schema | v54 | `NUCLEAR_SUPPORTED_VERSION` in `apps/agent-service/src/core/db.ts` |
| Next work | **A4**, the C4 graduation port (Phase 4) | roadmap Part 3 |

C1 Track A is DONE, so there's nothing left to finish on the Ashley side. Mint and `main` are both at `bd566cb`.

## 3. The work queue (in order; one packet at a time)

| # | Packet | Kind | Roadmap section |
|---|---|---|---|
| 1 | **A4:** port C4 (cognitive-graduation) into v021, then retire the old module | feature | Phase 4 → A4 (full spec in `inbox\A4_PHASE4_C4_GRADUATION_PORT.md`) |
| 2 | **A5a:** C3 storage, `interest_touches`, eligibility split | feature | Phase 4 → A5a |
| 3 | **A5b:** proposals, Thought positions, agenda receipts | feature | A5b |
| 4 | **A5c:** retire the legacy C3 hooks and module | feature | A5c |
| 5 | **L1:** per-policy private-budget resolver | feature | Shared prerequisite → L1 |
| 6 | **P7a:** weekly NIGHT arc repair plus gate receipts | bugfix | Phase 7 → P7a |
| 7 | **T0 → T5:** the thalamus | features | Phase 5 |
| 8 | **S0 → S4:** self-change (S2/S3 need the Owner's repo and key) | features | Phase 6 |
| 9 | **8a → 8f:** Domus in Ashley, paced with the Domus handoff | features | Phase 8 |
| — | Maintenance backlog, any time | bugfix | `_Internal\orchestra\BACKLOG_NEXT_BATCH.md` |

**A4 base:** current `main`. **Versions:** sidecar is the next free one (v50), nuclear v55. Re-verify the anchors in the A4 packet at your base and note any drift.

## 4. How to run one packet alone (the loop)

1. **Brief yourself.** Copy the packet's GOAL / SCOPE / DO / DON'T / tests / STOP into `_Internal\work\<ID>_BRIEF.md`. Add a **BUDGET** line: commit at each green step. If it's much bigger than ~25 tool turns, split it into sub-steps, each with its own commit.
2. **Branch:** `git switch -c <id>-<slug> origin/main`, e.g. `a4-c4-port`.
3. **Red first:** write the new tests, run them, and **record the failing assertion message**. A test that fails to compile or collect doesn't count as red.
4. **Green:** implement, run the focused tests plus `npm run build:agent`, and commit. The message is imperative and says what changed. The last lines must be the attribution lines your harness requires, if any.
5. **Pins:** when a schema version bumps, **move every test pinning the current version, in every form** (`toBe(N)`, `toEqual({schema_version:N})`, `user_version`). Historical and ladder values stay. When `thought/output-contract.ts` changes, update **every** fingerprint pin. List all pins in the report.
6. **Full verification at the tip** (Node ≥ 22; XQX has Node 24):

   ```powershell
   npm ci                                    # root, once
   # build the workspace packages if collection fails: sandbox-policy, sandbox-m1, sandbox-tree, sandbox-v2 (npm ci + npm run build in each, in that order)
   npm run build:agent
   cd apps/agent-service; npx vitest run --reporter=dot > $env:TEMP\suite.txt 2>&1; Get-Content $env:TEMP\suite.txt -Tail 40; cd ../..
   npm test --prefix apps/discord-bot > $env:TEMP\discord.txt 2>&1; Get-Content $env:TEMP\discord.txt -Tail 40
   npm run test:current-deployment           # its not-ok names must be identical to the base's (21 known)
   ```

   **Bar:** build clean, 0 failures in the agent suite, Discord 0 failures, and the deployment not-ok list unchanged.
7. **Self-review (replaces the separate Auditor).** Feature packets get an independent review by Owner rule. You can't be independent, so do this instead:
   - re-read the diff (`git diff origin/main...HEAD --stat`, then per file) against the packet's DO, DON'T and review-focus lines;
   - re-run **≥2 new tests per commit at that commit's parent** to confirm they fail by assertion;
   - check public-repo hygiene: no model IDs, secrets, `_Internal` content or Owner material.

   Write the findings as BLOCKING / NONBLOCKING / NOTE. **If you find a BLOCKING item, fix it before reporting.** If the Owner wants a truly independent review, he can start a second session with "review branch X against packet Y".
8. **Report:** `_Internal\work\<ID>_REPORT.md`, with the first line `STATUS: DONE` or `STATUS: STOPPED`. It includes:
   - each DO item marked MET or NOT MET, with file:line;
   - the red-first assertions;
   - versions and pins;
   - the suite tallies;
   - the self-review findings;
   - anything you assumed.
9. **Push the branch** (`git push -u origin <branch>`). Tell the Owner in one short message: what's done, the branch, the report path, and **"ready to merge?"**
10. **Merge, only on the Owner's "merge":** `git switch main; git pull --ff-only; git merge --no-ff <branch> -m "Merge <branch> (<ID>): <one line>"`. Re-run step 6 on the merge, push, and note the merge SHA in the report.
11. **Never deploy.** See §5.

**On a STOP:** stop, keep everything, and write the exact blocker plus options in the report. Ask the Owner. Never work around a STOP.

## 5. Owner gates (you never do these on your own)

- **Mint deploy.** Only on the Owner's go for a batch. The sequence:
  1. A fresh backup: `ssh mint "systemctl --user start ashley-backup.service"`. Check `~/.composer-assistant/backups/status.json` for a new `last_ok_ms`.
  2. A drill: `ssh mint "systemctl --user start ashley-backup-drill.service"`. It must set `drill_ok_ms` and leave `drill_error` null.
  3. `npm run start:ashley` from XQX with `main` checked out.
  4. Read-only post-checks: activated SHA, health, schema versions, services active, no errors for 10 minutes.
  5. `npm run deploy-commands --prefix apps/discord-bot` on Mint if slash commands changed.

  **On any failure:** STOP and report. Rollback only on the Owner's word.
- **Never without his word:**
  - any other Mint mutation;
  - a Discord message as the Owner;
  - deleting a backup;
  - touching credentials, `.env` values or tokens. You never print or copy them; reports say "present".
- **Owner-only steps:**
  - the decisions in roadmap Part 4: mode flips, budget numbers, capability promotions, transport setup, the Ashley-self repo and key;
  - running Session G on Mint.
- **No new policy.** Anything that seems to need a new rule is written `NEW POLICY — PROPOSED` in the report, and stops there.
- **Routine project installs** (npm deps inside the repo) are fine. Global or system changes aren't.

## 6. Rules that bite (from the decision ledger)

- **The Host records facts; Thought owns meaning.** Every new module starts with a one-line essence comment.
- **Growth labels:** growth written by a pass that saw secret evidence is `never_public` (GS1). Thought free text in growth tables gets the credential-shape check (`detectCredentialShape`, the A3h rule).
- **Retired tables:** drop migrations for old tables are **fail-closed**. If a table has rows, the migration throws with `<x>_rows_present:<table>:<n>`.
- **Comparing results:** a mismatch between your test counts and earlier reports is usually the environment (unbuilt workspace dists, Node version). Settle it with the full build in step 6.
- **Sources of truth:** source wins over docs. If they disagree, write `DOCUMENT_SOURCE_DIVERGENCE` in the report.

## 7. Notes per model

- **Sol 6.1 light (Codex app):** fast and cheap. Keep each step small, and write a short STATE block in your brief (what's done, what's failing, the anchors already found) when you resume work.
- **Muse (CommandCode):** use effort **high**, not xhigh. xhigh caused 20–40k-token thinking turns and stalls here. Avoid whole-file reads, since cache misses are expensive.
- **Grok Build CLI:** the same loop. Work in the repo directly on XQX. Don't run it in an environment with GitHub credentials you weren't given.
- **Any model: when your context gets long,** write the report so far, commit, and continue in a fresh session from the report's STATE.

## 8. When you finish a packet

Update roadmap Part 1 (the state table) and tick the packet off in §3 of this file. Then take the next one. **Don't start a new phase** (Phase 5, 6 or 8) without telling the Owner first; a one-line heads-up is enough.
