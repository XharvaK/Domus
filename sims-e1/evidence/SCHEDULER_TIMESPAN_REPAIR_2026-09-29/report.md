# Project Ashley — Scheduler TimeSpan Binding Repair 1.0.5 -> 1.0.6

Date: `2026-09-29`

## Authority and boundary

This pass implemented only the target-proven scheduler binding correction.
The architecture, command registration, native arm mapping, bootstrap
contract, writer, observer, schema, and E2 boundary were not redesigned.

- Sims launch: `NO`
- Sims command: `NO`
- Install/uninstall: `NO`
- OD-4 retry: `NO`
- E1-A/B/G: `NO`
- E2: `NO`
- Shutdown/reboot/sleep/hibernate: `NO`
- Sims process after verification: `CLOSED`

Historical acceptance and research evidence remain unchanged.

## Git identity

- Start HEAD: `9df5fa0fb9f04ea1e5ff3d6fa493060c0dfb5be1`
- Start tree: `92e93b9ca6e2f0732f4d795d9388c1e17efdae48`
- Final commit: `d678f098057bc1a590d4501c13e85f59830db2ac`
- Final tree: `92d9ee964ea03d6ac15d9f743a4a9f62d7222f53`
- `origin/main`: `d678f098057bc1a590d4501c13e85f59830db2ac`
- Remote `origin/main`: `d678f098057bc1a590d4501c13e85f59830db2ac`
- Push: normal fast-forward push succeeded

The commit contains only the intended scheduler repair, focused tests,
1.0.6 version updates, tooling defaults, and scoped README documentation.
Unrelated Owner-untracked files were not staged.

## Repair

`_cmd_start` now passes the target-produced interval directly:

```python
time_span=interval_in_real_seconds(1)
```

The required binding remains present and unchanged:

```python
TimeSpan = date_and_time.TimeSpan
```

The closed 19-key required-import summary remains unchanged, including
`date_and_time.TimeSpan`.

Internal probe version is `1.0.6`. Product-facing branding remains
`Embodiment 1.0.0`.

## Changed tracked files

- `sims-e1/src/ashley_e1/probe.py`
- `sims-e1/src/ashley_e1/__init__.py`
- `sims-e1/src/ashley_e1/schema.py`
- `sims-e1/tests/test_binding.py`
- `sims-e1/tests/test_bootstrap.py`
- `sims-e1/tests/test_root.py`
- `sims-e1/tools/build.ps1`
- `sims-e1/tools/verify.ps1`
- `sims-e1/tools/install.ps1`
- `sims-e1/tools/remove.ps1`
- `sims-e1/README.md`

## Focused verification

| check | result |
| --- | --- |
| Scheduler red tests against 1.0.5 | 2 expected failures in 14 binding tests |
| Focused suite, system Python 3.14.3 | `69/69 PASS` |
| Focused suite, exact CPython 3.7.0 x64 | `69/69 PASS` |
| `check_guards.py` AST guards | `PASS` |
| PowerShell parsing | `PASS`, 4 scripts |
| `verify.ps1 -Version 1.0.6` | `PASS` |
| pyc magic | `3394` / `420d0d0a` |
| production package | `6` pyc-only members |

The focused scheduler tests prove direct interval identity, prohibit nested
`TimeSpan` construction, preserve exact alarm arguments, preserve sampling and
repeated-start behavior, and retain fail-closed alarm-construction semantics.

## Artifact

- Filename: `ashley_e1_1.0.6.ts4script`
- SHA256: `A1DD1B724B3F935ACB532CB9773E86412C709C8A33698B0AEFF50491CF273A1A`
- Bytes: `23752`
- Members:
  - `ashley_e1/__init__.pyc`
  - `ashley_e1/observers.pyc`
  - `ashley_e1/probe.pyc`
  - `ashley_e1/schema.pyc`
  - `ashley_e1/snapshot.pyc`
  - `ashley_e1/writer.pyc`

## Result

`SIMS4_E1_SCHEDULER_TIMESPAN_REPAIR: COMPLETE`
`READY_FOR_1_0_6_OD4_RETRY: YES`
