# BACKLOG_NEXT_BATCH (Ashley) — created 2026-10-01 per A1n
Each item becomes a packet line when the architect plans the next Owner-approved batch (D-042). Not now.

1. **migration-backups/ gap (A1m F1):** read-only source question: why does `migration-backups/` stop at v21→v22 (2026-09-28)? Is the pre-migration snapshot conditional, or was it retired?
2. **Drill observability (A1m F2):** log per-table restored/live counts at info level on every drill (NOTEs currently only when restored > live).
3. **rclone shared Google Drive client_id retirement (2026):** an Owner step: create Ashley's own Google OAuth client ID and re-authorize `ashley-drive`. The architect writes the steps when it's time. Before the retirement.
4. **npm audit, 1 high in discord-bot:** identify the package and reachability, read-only; fix only if real.
5. **Refused-deploy dist rebuild (A1m follow-up):** `remote-update.ps1` rebuilds `dist` before `update.sh` can refuse, which leaves a mismatched `dist`. Build into a staging dir or restore on refusal.
6. **GS1 note 2 (`sawSecret` default):** add a comment at `materializeSemanticSettlement` (`thought/run.ts:984`) explaining that `sawSecret` defaults to `true` on purpose, so callers that skip it fail closed. Comment only, no behaviour change.

Batch-deploy notes accumulating:
- A3 (Phase 3): `deploy-commands` on Mint for the `/identity` practices view.
