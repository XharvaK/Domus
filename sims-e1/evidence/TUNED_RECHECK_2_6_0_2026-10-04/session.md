# tuned_scan re-check, probe 2.6.0, 2026-10-04

Owner launched the game and loaded the household lot (UNARMED, inbox autostart `ZONE:manager`, `inbox_errors` 0).
`tuned_scan` sent once by the Architect through the helper (`agent:mcp`); no arm, no actuation.

| Measure | 2.5.0 (2026-10-03) | 2.6.0 (this run) |
|---|---|---|
| `tuned_on_class` rows | 319 | 319 |
| Rows with a non-empty `affordance_guid64s` | 0 | 319 |
| Errors (footer) | 0 | 0 |
| Chunks / max chunk | n/a | 27 / 7.07 ms (p50 5.22 ms) |

- 4,879 guids in total, 577 unique, 58 classes, 9 Sims; 11 rows truncated at the 64-guid cap (Sims, fridges).
- All 577 unique guids are present in the helper atlas for build 1.128.90.1030 (8,256 affordances). All 577 are super-affordances; 212 allow autonomy.
- `definition_id` is null on every row.

Verdict: A18 (DA2B, guid64 read along the class `__mro__`) holds live. DA2B closed.
Rows are class tuning on the object, not an offered or runnable set.
