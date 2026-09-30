# Project Ashley — Consolidated Exact-Target E1 Repair 1.0.6 -> 1.0.7

Date: 2026-09-29

## Verdict

Implementation and package checks completed. Git publication is blocked by
the repository verifier's required system-Python gate.

~~~text
SIMS4_E1_CONSOLIDATED_TARGET_BINDING_REPAIR: BLOCKED
BLOCKER: verify.ps1 requires system Python 3.14.x, but no system Python is
available on PATH or in the installed Python locations on this host.
~~~

No Sims process was launched. No Sims command, install, uninstall, OD-4,
E1-A/B/G, E2, shutdown, reboot, sleep, or hibernate action was performed.

## Baseline

| Item | Value |
|---|---|
| Repository | XharvaK/Ashley |
| Branch | main |
| Initial HEAD | d678f098057bc1a590d4501c13e85f59830db2ac |
| Initial tree | 92d9ee964ea03d6ac15d9f743a4a9f62d7222f53 |
| origin/main before edits | d678f098057bc1a590d4501c13e85f59830db2ac |
| Internal probe | 1.0.7 in the working tree |
| Product branding | Embodiment 1.0.0 |

## Applied repair set

1. Replaced the non-weak-referenceable object() alarm owner with one inert
   module-owned _ProbeAlarmOwner singleton.
2. Imported and used the approved objects.ALL_HIDDEN_REASONS default for
   production hidden-flag resolution.
3. Made the save-slot buffer read None-safe without fabricating "None".
4. Made queue and running interaction views None-safe while preserving the
   distinction between unavailable and initialized-empty views.
5. Added the pre-session-open complete (save_slot_guid, slot_id, sim_id)
   gate. An incomplete triple emits exactly one bounded guard_exhausted row
   with reason
   OBSERVATION_FAILURE:SESSION_OPEN_IDENTITY_INCOMPLETE, stops sampling, and
   leaves the session unopened.

The closed schema, event vocabulary, 19-key required-import contract,
command mapping, scheduler binding, callback identity, writer boundary,
E1-A/B/G design, and E2 boundary were not changed.

## Regression evidence

The new tests were first run against the unchanged 1.0.6 source and
identified the expected failures:

- built-in object() alarm owner cannot be weak-referenced;
- alarm start fails when the fake performs the target weak-reference;
- default hidden flags are None;
- buff=None raises AttributeError;
- queue=None or running=None reaches iter(None);
- sim_id=None becomes the string "None";
- incomplete session identity emits the wrong first-row path.

After implementation:

| Check | Result |
|---|---|
| Focused suite, exact CPython 3.7.0 x64 | 78/78 PASS |
| Focused suite, available bundled Python 3.12.14 | 78/78 PASS |
| AST guard checker under both interpreters | PASS |
| PowerShell parsing, four scripts | PASS |
| Source/test diff whitespace check | PASS |

The repository's prior expected planning-machine runtime is Python 3.14.3.
This host currently reports no python command through Get-Command. The only
available bundled runtime is:

~~~text
Python 3.12.14
~~~

## Build and package evidence

The exact CPython 3.7.0 build completed:

~~~text
BUILD_PASS artifact=C:\Users\Xharv\Projects\Ashley\sims-e1\build\ashley_e1_1.0.7.ts4script
BUILD_SHA256=33E75CAFAEE28E63EAEC7887E29A59F520708E08D1360C83C1034229CA2EA736
~~~

| Item | Value |
|---|---|
| Artifact | sims-e1/build/ashley_e1_1.0.7.ts4script |
| Bytes | 24023 |
| SHA256 | 33E75CAFAEE28E63EAEC7887E29A59F520708E08D1360C83C1034229CA2EA736 |
| PYC magic | 420d0d0a / 3394 |
| Members | six ashley_e1/*.pyc files only |
| Raw .py members | absent |
| __pycache__ members | absent |
| Manual artifact/manifest/source/P1 validation | PASS |

## Verifier blocker

The authorized verifier was run with the available Python exposed as
python:

~~~text
VERIFY_PASS compiler=3.7.0
VERIFY_FAIL system Python must be 3.14.x: Python 3.12.14
~~~

Because verify.ps1 stops its remaining checks after this failure, the
artifact layout, magic, digest, manifest, and P1 checks were run independently
and passed as recorded above. No verifier result was falsified or bypassed.

## Git boundary

The intended 13 repair files remain working-tree changes. No commit and no
push were performed because the request requires both only after focused
verification, including verify.ps1, passes. origin/main remains at the
initial SHA. Historical closure and acceptance evidence remain unchanged.

SIMS4_E1_CONSOLIDATED_TARGET_BINDING_REPAIR: BLOCKED
