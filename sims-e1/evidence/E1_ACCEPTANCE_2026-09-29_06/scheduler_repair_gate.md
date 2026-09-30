# E1_ACCEPTANCE_2026-09-29_06 — Scheduler Repair Gate

Command entered by Owner:

```text
ashley_e1.start
```

Bounded observation:

- Observation UTC: `2026-09-29T05:49:09.0187955Z`
- Session file: `ashley_e1_cc147cea-263b-48dc-8163-64626d366109.jsonl`
- Session file bytes: `0`
- Session file last write UTC remained: `2026-09-29T05:47:29.5352547Z`
- A further 5-second observation also reported `SESSION_BYTES=0`.
- Session content: empty.
- No `session_open` row.
- No first successful poll.
- No sampling/presence observation.
- No new telemetry file.
- No new exception/error/crash file was observed after the arm/start window.
- The open session prevented an independent shared-read SHA256 at that time;
  the exact observed fact is zero bytes.

Saves remained unchanged against `saves_baseline.json`: zero changed files;
all 12 baseline names, sizes, and SHA256 values matched.

The required early scheduler witness did not appear. No stop, disarm, retry,
or other Sims command was issued after this blocker.

```text
SCHEDULER_TIMESPAN_REPAIR_RUNTIME_CONFIRMATION = FAIL
SIMS4_E1_FIRST_LOAD_ACCEPTANCE = BLOCKED
BLOCKER = fresh 1.0.6 normal session remained 0 bytes after ashley_e1.start;
no session_open or first successful poll appeared during the bounded window
```
