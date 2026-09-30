# E1_ACCEPTANCE_2026-09-29_06 — Verdict

Fresh 1.0.6 bootstrap and ARM gates passed. The required early scheduler
repair witness failed: after `ashley_e1.start`, the fresh normal session file
remained empty through the bounded observation window, with no `session_open`,
first poll, or sampling row.

No source change, rebuild, reinstall, additional Sims command, E1-A/B/G, E2,
or power action was performed after the blocker.

```text
ARM_NORMALIZATION_RUNTIME_CONFIRMATION: PASS
SCHEDULER_TIMESPAN_REPAIR_RUNTIME_CONFIRMATION: FAIL
SIMS4_E1_FIRST_LOAD_ACCEPTANCE: BLOCKED
BLOCKER: fresh 1.0.6 normal session remained 0 bytes after ashley_e1.start;
no session_open or first successful poll appeared during the bounded window
```
