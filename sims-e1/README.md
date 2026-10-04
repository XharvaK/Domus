# Ashley Sims 4 Embodiment probe

This directory contains the owner-commanded Sims 4 Embodiment probe.

## Current build: 2.9.2 (DA6A trial command)

The source is version `2.9.2` (`src/ashley_e1/__init__.py`,
`src/ashley_e1/schema.py`; observation schema 5, schema 4 rows still validate). It is no longer read-only:
it carries the E2 actuation experiment described by
`docs/Domus/PROJECT_ASHLEY_SIMS4_EMBODIMENT_E2_IMPLEMENTATION_READY_PLAN_V1.md`.
2.9.2 has not yet passed its E2 first-load gate or trials; those run on the
Owner's Windows dev PC. `calibrate` while armed refuses actuation and only observes.
Class cards judge a trial by posture, need, interaction, or social purpose.
`trial` pushes one parameter-free super-affordance on the lab fork and judges it
with an interaction card. Sit and sit_trial are unchanged.

Owner commands (also available through the local command inbox when the zone reaches RUNNING):

| Command | Stage | What it does |
|---|---|---|
| `ashley_e1.arm LAB_E1` / `ashley_e1.arm LAB_E1_FORK` | E1 | Arm an observation session |
| `ashley_e1.start` / `ashley_e1.stop` | E1 | Start and stop observation |
| `ashley_e1.inbox` | E1 | Fallback start for the independent 1 Hz local command inbox |
| `ashley_e1.status` | E1 | Report probe and inbox state |
| `ashley_e1.disarm` | E1 | Disarm the session |
| `ashley_e2.prepare <object_id>` | E2 | Prepare one sit experiment on an object |
| `ashley_e2.sit <token>` | E2 | Admit and push one prepared sit experiment |
| `ashley_e2.pause` | E2 | Push the probe's pause request |
| `ashley_e2.release` | E2 | Remove the probe's pause request |

The inbox starts automatically through the zone manager object-add callback when
a zone reaches RUNNING. `ashley_e1.inbox` is the fallback if automatic start is
unavailable. Automatic start still awaits live qualification.

The inbox uses UTF-8 JSON files in `AshleyE1Telemetry/cmd/inbox`, single-use
32-character lowercase hex ids, and expiry of at most 60 seconds. Replies are
published atomically in `cmd/outbox`; claimed inputs finish in `cmd/done`.
`status` works while unarmed; `sit_trial` calls prepare then sit in one tick,
with the existing admission checks. The inbox survives stop and disarm and
its alarm ends at the zone boundary.

Build and verification (pinned official CPython 3.7.0 x64):

```powershell
powershell -ExecutionPolicy Bypass -File sims-e1/tools/build.ps1 -Version 2.9.2
powershell -ExecutionPolicy Bypass -File sims-e1/tools/verify.ps1 -Version 2.9.2
```

E1 evidence (acceptance, adjudication and repairs) is under
`sims-e1/evidence/`; it moves to the Domus repository when that repository
exists.

## History: E1 read-only builds (1.0.x)

The E1 read-only probe was described by
`PROJECT_ASHLEY_SIMS4_EMBODIMENT_E0_E1_IMPLEMENTATION_READY_PLAN_V1_2a.md`.
Its last internal build was version `1.0.11`. Product-facing branding remains
`Embodiment 1.0.0`; `E1` is an internal engineering and stage identifier.
Version `1.0.11` is a bounded telemetry-truth correction on 1.0.10, which
passed first-load acceptance A-M
(`evidence/E1_ACCEPTANCE_2026-09-29_09/acceptance.md`). Presence rows now carry
the probe-owned armed snapshot in `attestation` (1.0.10 and earlier wrote the
save GUID into `snapshot_slot` and left `snapshot_guid` null); per-session
counters reset on every accepted ARM; and the game thread never lowers a
writer-owned counter. 1.0.11 itself still requires runtime requalification.

The 1.0.10 repair preserves the closed command, scheduler, callback, and
writer contracts while making the alarm owner weak-referenceable, passing the
approved `objects.ALL_HIDDEN_REASONS` constant, handling transient save-slot
and interaction-view absence without fabrication, and fail-closing before
`session_open` until the complete save GUID/slot/Sim identity triple exists.
It adds writer-owned logical cap accounting with bounded reconciliation and
failure-only stop/cancel observability. Product-facing branding remains
`Embodiment 1.0.0`.
Attended-session filesystem setup, inventory, active-file creation, writes,
flushes, reconciliation, rotation, and close are owned by the writer thread;
ARM remains nonblocking and does not treat the post-construction writer state
as a readiness proof; worker startup state is authoritative.

The V1.2a expression `TimeSpan(interval_in_real_seconds(1))` was falsified by
exact Sims 1.128 bytecode: `interval_in_real_seconds(1)` already returns a
`TimeSpan`, and the nested constructor raises `TypeError: must be real number,
not TimeSpan`. The corrected binding passes `interval_in_real_seconds(1)`
directly as the `time_span` argument. Architecture and bootstrap semantics are
unchanged; the `date_and_time.TimeSpan` required-import key remains closed and
is still recorded in the 19-key summary.

The target Sims 1.128 command transport lowercases ordinary string arguments
before the Python callback. Owner command documentation remains
`ashley_e1.arm LAB_E1` and `ashley_e1.arm LAB_E1_FORK`. The adapter accepts
only the closed native tokens `lab_e1` and `lab_e1_fork` and maps them to the
canonical semantic names. It does not apply generic case normalization or
aliases. Mixed-case and lowercase distinctions that the native transport does
not preserve cannot be recovered by the probe.

The 1.0.11 build used the same tooling with `-Version 1.0.11`.

`install.ps1` and `remove.ps1` are mechanical OD-4 tools. They require an
explicit Owner-confirmed Sims user-data root and a closed game. This repair
pass does not perform installation or runtime witnessing.

Raw telemetry and witness material stay outside Git. Historical diagnostic
evidence remains preserved under `sims-e1/evidence`.
