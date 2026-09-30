# Project Ashley — Target-Runtime Scheduler Binding Research

Date: `2026-09-29`

This report is a read-only target-runtime investigation. It does not modify
Ashley source, build output, installed files, Sims saves, or the running game.
Sims was closed before archive inspection and remains closed.

## Boundary and candidate identity

- Repository: `C:\Users\Xharv\Projects\Ashley`
- Branch: `main`
- HEAD: `9df5fa0fb9f04ea1e5ff3d6fa493060c0dfb5be1`
- HEAD tree: `92e93b9ca6e2f0732f4d795d9388c1e17efdae48`
- `origin/main`: `9df5fa0fb9f04ea1e5ff3d6fa493060c0dfb5be1`
- Tracked tree at inspection: clean
- Internal probe inspected: `1.0.5`
- Product-facing name: `Embodiment 1.0.0`
- Target Sims build: `PC 1.128.90.1030`
- Candidate artifact:
  `sims-e1/build/ashley_e1_1.0.5.ts4script`
- Candidate artifact SHA256:
  `6B9E604F26A739782E1EE4FEADDC0D8782CDF676E32513A22ABB73DA72633833`
- Exact inspection interpreter: `C:\Users\Xharv\AppData\Local\Programs\Python\Python370-AshleyE1\python.exe`
- Interpreter version observed: `3.7.0`

No Sims command, source edit, build, install, uninstall, save operation, or
power action was performed.

## Target archives and exact members

The three authorized archives were hashed before member inspection:

| archive | bytes | SHA256 |
| --- | ---: | --- |
| `Data\Simulation\Gameplay\core.zip` | 332162 | `641E9233C44763B0103517ED40DA37186FCD10DF76143896D6BF3C497A38690B` |
| `Data\Simulation\Gameplay\base.zip` | 1830057 | `5E53E2A5622FA8806F92D8B75A5639AD4B83D49DBAAD4ADD602A411421D02594` |
| `Data\Simulation\Gameplay\simulation.zip` | 10130550 | `B97D71BB8C92116B4320ED640F5D3F06C3E4F1E3FB2F7DFD5FEA5F924D0324EC` |

All three target members are root members of `simulation.zip`. They were
extracted read-only to the bounded temporary directory
`C:\Users\Xharv\AppData\Local\Temp\ashley-e1-scheduler-binding-20260929\`.

| member | CRC | uncompressed | compressed | extracted SHA256 | first 16 bytes |
| --- | --- | ---: | ---: | --- | --- |
| `clock.pyc` | `18B97F5C` | 21483 | 8776 | `985C5BCF22D80C2BB9931BB7F508EEC51F6916B2E80BF441DBF5C5B47FDCBA3D` | `420d0d0a00000000f5850e6739920000` |
| `date_and_time.pyc` | `198710CA` | 13281 | 4870 | `67D05343F8688A22F280702F9E7ED8DA611FB16A6F0ABCC531FA12F1B0220F43` | `420d0d0a000000003c742668d94f0000` |
| `alarms.pyc` | `141F554E` | 7859 | 3510 | `8C019CC9696AD12FA7FD1AEB0D07090FE1D8ECB956687E2A9BE489FDF0362C58` | `420d0d0a000000001071dd59ab3c0000` |

The headers are timestamp/size-form CPython 3.7 bytecode headers. The magic
bytes are `420d0d0a`, decimal magic `3394`.

## Target contract reconstruction

### `clock.interval_in_real_seconds`

The exact code object has `co_argcount=1`,
`co_varnames=('seconds',)`, and names
`('TimeSpan', 'date_and_time', 'TICKS_PER_REAL_WORLD_SECOND')`. Its bytecode
is mechanically:

```text
LOAD_GLOBAL  TimeSpan
LOAD_FAST    seconds
LOAD_GLOBAL  date_and_time
LOAD_ATTR    TICKS_PER_REAL_WORLD_SECOND
BINARY_MULTIPLY
CALL_FUNCTION 1
RETURN_VALUE
```

Therefore `clock.interval_in_real_seconds(1)` itself constructs and returns a
`date_and_time.TimeSpan`.

### `date_and_time.TimeSpan`

The exact `TimeSpan.__init__(self, delta)` code calls
`math.ceil(delta)` and stores the result in `self._delta`. The class has no
`__ceil__` implementation. Passing an existing `TimeSpan` therefore reaches
`math.ceil(TimeSpan)` and is not a supported nested construction.

An isolated pure-Python reconstruction executed under the exact CPython 3.7.0
interpreter produced:

```text
span_type=TimeSpan
span_delta=1000
TypeError: must be real number, not TimeSpan
```

This is a reconstruction of the recovered target implementation, not a Sims
runtime mutation or an imported live-game execution.

### `alarms.add_alarm_real_time`

The exact function has six positional parameters and defaults
`(False, True, False)`:

```text
add_alarm_real_time(owner, time_span, callback,
                    repeating=False, use_sleep_time=True,
                    cross_zone=False)
```

The recovered code passes `time_span` directly into the alarm due-time
calculation (`timeline.now + time_span`) and constructs the alarm handle with
the supplied `repeating`, `use_sleep_time`, and `cross_zone` values. The
keyword names used by Ashley are valid target keywords.

### `alarms.cancel_alarm`

The exact function is `cancel_alarm(handle)`. Ashley's positional
`alarms.cancel_alarm(_ALARM_HANDLE)` binding matches it.

### Alarm callback shape

Both the one-shot and repeating target alarm element `_run` methods invoke:

```text
self.callback(_lookup_alarm_handle(element_handle))
```

The target callback receives one positional alarm-handle argument.
Ashley 1.0.5 defines `_poll_tick(alarm_handle=None)`, which accepts that
shape.

## Ordinary target call-site evidence

The exact bytecode scan over all recursively nested code objects in the three
authorized archives found 18 `add_alarm_real_time` name hits in
`simulation.zip`; the useful ordinary call sites include:

1. `zone.pyc`, `start_services`, line 363: passes
   `clock.interval_in_real_seconds(1)` directly as `time_span`, with
   `repeating` and `use_sleep_time` keywords.
2. `broadcasters/broadcaster_service.pyc`, `create_update_alarm`, line 658:
   passes `interval_in_real_seconds(self.INTERVAL)` directly as `time_span`,
   with `repeating` and `use_sleep_time` keywords.
3. `gameplay_scenarios/scenario_tracker.pyc`, `end_scenario`, line 166:
   passes `clock.interval_in_real_seconds(1.0)` directly.
4. `gsi_handlers/performance_handlers.pyc`,
   `enable_performance_logging`, line 62: passes
   `clock.interval_in_real_seconds(SECONDS_BETWEEN_LOGGING)` directly.
5. `objects/game_object.pyc`, `set_build_buy_lockout_state`, line 791:
   computes a `time_span_real_time` from `interval_in_real_seconds` and passes
   that value directly.

These call sites independently corroborate that the target interval helper's
return value is the alarm API's expected `time_span` value.

## Exact 1.0.5 comparison

Current source locations in
`sims-e1/src/ashley_e1/probe.py` are:

- lines 58-60: bind `TimeSpan = date_and_time.TimeSpan`;
- lines 62-64: bind `interval_in_real_seconds`;
- lines 284-304: `_cmd_start`;
- lines 297-298: call
  `alarms.add_alarm_real_time(...,
  time_span=TimeSpan(interval_in_real_seconds(1)),
  callback=_poll_tick, repeating=True, use_sleep_time=False,
  cross_zone=False)`;
- lines 308-317: `_cmd_stop` and positional `alarms.cancel_alarm`;
- lines 385-407: `_poll_tick(alarm_handle=None)`.

The start path's broad `except Exception` converts the nested-constructor
`TypeError` into `False`, clears `_ALARM_HANDLE`, and does not reach
`_STATE = "SAMPLING"` or `_set_writer_sampling(True)`.

## Mechanical classification

| binding | result |
| --- | --- |
| `clock.interval_in_real_seconds(1)` construction | `RETURNS_TIMESPAN` |
| `TimeSpan(interval_in_real_seconds(1))` in 1.0.5 | `MISMATCH_DOUBLE_CONSTRUCTION` |
| nested `TimeSpan` behavior | `REJECTS_TIMESPAN` — `TypeError: must be real number, not TimeSpan` |
| `add_alarm_real_time` argument names/defaults | `MATCH` |
| alarm callback shape | `MATCH` |
| `cancel_alarm` binding | `MATCH` |
| `V1_2A_SCHEDULER_BINDING` | `TARGET_FALSIFIED` |
| `SCHEDULER_ROOT_CAUSE` | `PROVEN` |

The prior 1.0.5 live symptom—`start` accepted by the command surface but no
session-open row, no sampling row, and an empty session file—is consistent
with this source-level failure path. No additional live command was sent in
this research pass.

## Next smallest move (not performed)

The smallest repair candidate is to pass
`interval_in_real_seconds(1)` directly as `time_span` in `_cmd_start`.
`TimeSpan` should be removed from the shipped probe only if a subsequent
source inspection confirms no other use. This report does not apply that
repair, rebuild an artifact, or change the acceptance state.

## Final boundary

- Source edits: `NO`
- Build: `NO`
- Install/uninstall: `NO`
- Sims launch or command: `NO`
- E1-A/B/G: `NO`
- E2: `NO`
- Saves or game files modified: `NO`
- Shutdown/reboot/sleep/hibernate: `NO`

`SIMS4_E1_TARGET_SCHEDULER_BINDING: RESOLVED`
