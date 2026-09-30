# Project Ashley — Embodiment E1 Exact-Target Binding Closure

Date: `2026-09-29`

This is a read-only target-binding audit. It does not modify Ashley source,
build output, installed packages, Sims saves, or the Sims runtime. The report
records the current 1.0.6 source and the exact PC 1.128.90.1030 bytecode.

## 1. Candidate and boundary

| item | observed value |
| --- | --- |
| repository | `C:\Users\Xharv\Projects\Ashley` |
| branch | `main` |
| HEAD | `d678f098057bc1a590d4501c13e85f59830db2ac` |
| HEAD tree | `92d9ee964ea03d6ac15d9f743a4a9f62d7222f53` |
| `origin/main` | `d678f098057bc1a590d4501c13e85f59830db2ac` |
| tracked tree | clean; pre-existing untracked Owner material was preserved |
| internal probe | `1.0.6` |
| product-facing name | `Embodiment 1.0.0` |
| target | Sims 4 PC `1.128.90.1030` |
| local artifact | `sims-e1/build/ashley_e1_1.0.6.ts4script` |
| artifact SHA256 | `A1DD1B724B3F935ACB532CB9773E86412C709C8A33698B0AEFF50491CF273A1A` |
| artifact form | 6 pyc-only members, 23752 bytes |
| Sims process at audit | `SIMS_RUNNING=False` |

No Sims command, acceptance action, installation action, source edit, build,
power action, E1-A/B/G action, or E2 action was performed.

## 2. Exact target evidence

The exact CPython interpreter was:

`C:\Users\Xharv\AppData\Local\Programs\Python\Python370-AshleyE1\python.exe`

It reports CPython `3.7.0`. Target pyc magic is `420d0d0a` (decimal `3394`).

| archive | bytes | SHA256 |
| --- | ---: | --- |
| `core.zip` | 332162 | `641E9233C44763B0103517ED40DA37186FCD10DF76143896D6BF3C497A38690B` |
| `base.zip` | 1830057 | `5E53E2A5622FA8806F92D8B75A5639AD4B83D49DBAAD4ADD602A411421D02594` |
| `simulation.zip` | 10130550 | `B97D71BB8C92116B4320ED640F5D3F06C3E4F1E3FB2F7DFD5FEA5F924D0324EC` |

Relevant exact member identities reused or extracted for this closure pass:

| member | bytes | SHA256 |
| --- | ---: | --- |
| `alarms.pyc` | 7859 | `8C019CC9696AD12FA7FD1AEB0D07090FE1D8ECB956687E2A9BE489FDF0362C58` |
| `clock.pyc` | 21483 | `985C5BCF22D80C2BB9931BB7F508EEC51F6916B2E80BF441DBF5C5B47FDCBA3D` |
| `date_and_time.pyc` | 13281 | `67D05343F8688A22F280702F9E7ED8DA611FB16A6F0ABCC531FA12F1B0220F43` |
| `time_service.pyc` | 6843 | `E3AC54F11622D4664F1FFE2FCF9A34D1B9C08A094C82D88CED5404916B579675` |
| `services/__init__.pyc` | 41749 | `1BDC0B7A9AFC8E94BE6F65EA95CE2FF7151011AAFFE0493B43A987079D45AF95` |
| `services/persistence_service.pyc` | 28040 | `96D4FFD7C4696232306D7AFF7AE977C5D9EEAA5599425B71A4DF984DCECC58D1` |
| `objects/__init__.pyc` | 11277 | `CF3C0F90BB68C8F03F1113C2E939ED8DEBBC2D876D9A2C43793073A0EC0FD08D` |
| `objects/game_object.pyc` | 46095 | `2ADD3326CDF1BDEFDB1846549C16248E5D765C70EC5EC11C508CF59ACABDC62F` |
| `sims/sim_info.pyc` | 136141 | `139BB6D2F488953C54457416A1F0F68FC42769880D386FA0F18FC4E844FC388E` |
| `sims/sim.pyc` | 113638 | `B6315AC22027FD3C74BCE56A1E61C23A7401D054E55756582A9456CA2594EC4C` |
| `indexed_manager.pyc` | 7513 | `86AEF71A80CC12D47474AF978F9BDF1A1B5CC4BFE352CD6427139EFC692FA731` |
| `server/clientmanager.pyc` | 1656 | `0A14600073724BEA5174530EB14A81F4B845F0F16C276905F2FC228D30D18907` |
| `interactions/interaction_queue.pyc` | 34352 | `40DFD601E2990E6831877520FB286ABFA53CEFB61361C29467B9E30AD15F9F37` |
| `interactions/si_state.pyc` | 28976 | `5084A13972782D6A1229DF7ACCE59A93BE210E92FBF39B6F44AE4D85F4F2EBF1` |
| `interactions/base/interaction.pyc` | 212148 | `F5C00F2FDB62EBF03CD5A30E41E35DEAA65D471494403B58BE4A33D1BD67FEE0` |
| `interactions/context.pyc` | 8029 | `A69397B3722B7B333C9E96613EEBCFCF330CBC4946BF8D91D9C6B0F76DB05280` |
| `sims/sim_info_base_wrapper.pyc` | 29135 | `B7D4D59E3434023D690C707155F47616195446CED8F8F8F86E39F527AE07C7ED` |

The existing scheduler, owner, command, and native-dispatch reports remain
the source for their previously captured detailed disassembly. The new
closure facts below were checked against the same exact target identity.

## 3. Production surface inventory

The shipped source contains six production modules:

* `probe.py` and `observers.py` directly import or read Sims APIs.
* `snapshot.py` consumes only objects passed from the game-thread observer and
  uses stdlib operations (`id`, `len`, `iter`, strings, dicts, lists).
* `schema.py` is pure validation/serialization.
* `writer.py` imports only stdlib modules and `.schema`; it has no game import.
* `__init__.py` imports `probe.initialize_probe()` only.

No other production module directly consumes a Sims API.

## 4. Required closure verdicts

### Alarm construction

`clock.interval_in_real_seconds(1)` returns a target `date_and_time.TimeSpan`
with a 1000-tick delta. Target `DateAndTime.__add__` accepts a `TimeSpan`.
`services.time_service()` returns the service-manager time service. Its
`start()` creates `wall_clock_timeline`; `wall_clock_timeline.now` is a
`DateAndTime`. The target `Timeline.schedule` queues an element and returns an
element handle; it does not run the callback synchronously. With
`repeating=True`, `use_sleep_time=False`, and `cross_zone=False`, target
`AlarmHandle` selects `LossyRepeatingAlarmElement`.

The only constructor mismatch is the already-proven owner weak-reference
requirement: `object()` cannot be weak-referenced. After replacing it with a
module-owned ordinary weak-referenceable object, no additional deterministic
constructor/API incompatibility remains.

`ALARM_CONSTRUCTION_AFTER_OWNER_REPAIR = TARGET_CLOSED`

### Repeating callback

The selected repeating element calls the callback with exactly one positional
argument: the `AlarmHandle` looked up from the element handle. It computes the
next due time as `timeline_now(t) + interval` and schedules again unless the
element is canceled. The callback return value is not used to decide whether
to repeat. `use_sleep_time=False` selects the lossy/future timeline calculation;
it does not change callback shape. `cross_zone=False` selects the non-cross-zone
element class; it does not change callback shape or owner handling. The wall
timeline is simulated independently of the game-clock timeline by
`TimeService.update`, so a pause does not mechanically stop this real-time
alarm. Pause continuity and callback count still require the A–M runtime
witness.

Ashley `_poll_tick(alarm_handle=None)` accepts the target callback shape and
its identity guard is correct.

`CALLBACK_AND_REPEAT_BINDING = TARGET_CLOSED`

### Start-state ordering

Target `Timeline.schedule` only inserts the element into the heap. The target
timeline invokes `_run` only from a later `Timeline.simulate` pass when the
due time is reached. `interval_in_real_seconds(1)` is positive. Therefore the
callback cannot run inside `add_alarm_real_time` or `schedule` before
`_cmd_start` sets `_STATE = "SAMPLING"`.

`START_STATE_ORDERING = SAFE`

### First-poll failure visibility

`observers.poll_once` exceptions are caught by all three `_poll_tick_body`
handlers: selectability failure, lab-cardinality ambiguity, and ordinary
`Exception`. Each generated guard reason is a bounded string. The guard row
uses integer wall/monotonic values and the fixed schema defaults. The closed
schema accepts these rows, and `TelemetryWriter.try_put` accepts them when the
writer is healthy.

No ordinary Sims API `Exception` from `poll_once` escapes before the guard row
is constructed. A writer that is already `FAILED_STICKY`, saturated, or unable
to open a file can still prevent physical persistence; that is an independent
writer failure, not an unhandled target API exception.

`FIRST_POLL_FAILURE_VISIBILITY = CLOSED`

### First-row writer path

For a schema-valid `session_open` or `presence_snapshot`, the path is closed:
`try_put` validates and enqueues; the writer thread drains the queue;
`_write_row` adds counters/writer state; `_write_direct` serializes, opens an
active file if needed, writes one JSONL line, flushes it, and assigns
`written_sequence`. The existing zero-byte ARM file is therefore not evidence
that the healthy first-row path cannot write.

The schema intentionally rejects a `session_open` whose snapshot GUID, slot,
or Sim ID is `None`. That is a runtime completion-point condition. The save
buffer `None` path is separately listed as a source gap below.

`FIRST_ROW_WRITER_PATH = CLOSED`

### Stop/cancel

Target `alarms.cancel_alarm(handle)` calls `AlarmHandle.cancel()`. The target
cancel path returns immediately if the handle was already torn down; otherwise
it unregisters auto-cleanup, clears/hard-stops the scheduled element, and tears
down the handle. Ashley stores the same returned handle and passes it
positionally. A canceled repeating element does not schedule another repeat.
Repeated stop while `ARMED` is a source state-machine no-op. Disarm signals
the writer, which drains queued rows, writes the optional `PRE_DISARM`
checkpoint, writes `session_close`, and closes the stream. These mechanics use
no additional Sims API.

`STOP_CANCEL_BINDING = TARGET_CLOSED`

## 5. Target-binding closure matrix

Classification meanings are exactly the campaign meanings: `TARGET_CONFIRMED`,
`TARGET_FALSIFIED`, `RUNTIME_VALUE_DEPENDENT`, and
`TARGET_BYTECODE_OPAQUE`.

| ID | Ashley source | Ashley expression / assumed contract | Exact target member and evidence | Classification | Correction if any | Runtime witness still required? |
| --- | --- | --- | --- | --- | --- | --- |
| I-01 | `probe.py:3-14` | Import `alarms`, `clock`, `date_and_time`; bind alarm functions, interval helper, `TimeSpan`. | Exact target modules exist. `clock.interval_in_real_seconds(seconds)` constructs `TimeSpan(seconds * TICKS_PER_REAL_WORLD_SECOND)`. `alarms.add_alarm_real_time` and `cancel_alarm` are present. | `TARGET_CONFIRMED` | None. | Required-import bootstrap and C/D. |
| I-02 | `probe.py:16-38` | Import `interactions.context`, `server.clientmanager`, `services`, `sims.sim.Sim`, `sims.sim_info.SimInfo`, `sims4.commands`; all imports are expected to resolve. | Exact target members are present in the authorized archives. | `TARGET_CONFIRMED` | None. | Required-import bootstrap. |
| C-01 | `probe.py:139-153` | Call `register(name, restrictions, handler, description, usage, CommandType.Live)` six-positionally for exactly four commands. | `sims4.commands.register` has six positional parameters `(name, restrictions, handler, description, usage, command_type)`. `CommandType.Live=5`; `UNRESTRICTED=0`. | `TARGET_CONFIRMED` | None. | Four registrations in bootstrap/runtime. |
| C-02 | `probe.py:109-118` | Arm adapter accepts one string positional argument, `_session_id` keyword, and no ordinary kwargs; lowercase native tokens map to canonical names. | Prior raw native diagnostic observed one positional `str`, no ordinary kwargs, and integer session ID. Native lowercases ordinary string arguments. | `TARGET_CONFIRMED` | Already applied adapter mapping; preserve. | One bounded native command witness remains useful. |
| A-01 | `probe.py:297-299` | Pass `time_span=interval_in_real_seconds(1)` directly. | Exact `clock.interval_in_real_seconds(1)` returns target `TimeSpan`; target alarm examples pass it directly. | `TARGET_CONFIRMED` | Already repaired; do not wrap in `TimeSpan(...)`. | 60-second callback trial. |
| A-02 | `probe.py:87,297` | Use `_PROBE_ALARM_OWNER = object()` as a non-game owner. | `AlarmHandle.__init__` unconditionally calls `weakref.ref(owner, callback)`. Exact CPython 3.7 proof: `object()` raises `TypeError: cannot create weak reference to 'object' object`. | `TARGET_FALSIFIED` | Replace with an inert ordinary weak-referenceable module singleton. | No; exact target proof is sufficient. |
| A-03 | target path from `probe.py:297-299` | `alarms.add_alarm_real_time` should obtain the time service and wall timeline. | `services.time_service()` returns `game_services.service_manager.time_service`; `TimeService.start()` creates `wall_clock_timeline`. | `TARGET_CONFIRMED` | None. | Timeline must be alive at runtime. |
| A-04 | target path from `probe.py:297-299` | Use `wall_clock_timeline.now` as alarm base time. | Target timeline exposes `now` as `DateAndTime`; schedule uses it as due-time base. | `TARGET_CONFIRMED` | None. | Stable live gameplay/time-service state. |
| A-05 | target path from `probe.py:297-299` | Add target `DateAndTime` and target `TimeSpan`. | Exact `DateAndTime.__add__` reads `other._delta` and returns a `DateAndTime`; direct interval result supplies `_delta`. | `TARGET_CONFIRMED` | None. | No additional API witness. |
| A-06 | target path from `probe.py:297-299` | `repeating=True`, `use_sleep_time=False`, `cross_zone=False` select a usable repeating element. | Exact target selects `LossyRepeatingAlarmElement` for these flags. | `TARGET_CONFIRMED` | None. | Callback count and pause trial. |
| A-07 | target path from `probe.py:297-299` | `timeline.schedule(element, due)` returns a handle without running it inline. | Exact `Timeline.schedule` pushes an `ElementHandle`; `_run` occurs from later `Timeline.simulate`. | `TARGET_CONFIRMED` | None. | No race witness beyond A–M start trial. |
| A-08 | target path from `probe.py:297-299` | Returned `AlarmHandle` remains usable for callback identity and cancellation. | Auto-cleanup maps the scheduled element to the same `AlarmHandle`; target callback lookup returns that object. Ashley's `is` guard matches. | `TARGET_CONFIRMED` | Preserve identity guard. | Dead-handle/zone branch is runtime/unit covered. |
| A-09 | `probe.py:385-404` | `_poll_tick(alarm_handle=None)` accepts one handle and repeats without I/O. | Repeating `_run` calls `callback(_lookup_alarm_handle(...))`; callback return is ignored for repeat; next due is `future + interval`. | `TARGET_CONFIRMED` | None. | 60-second count, pause, overrun. |
| O-01 | `observers.py:93-94` | Read `services.sim_info_manager().get_all()` and iterate candidates. | `services.sim_info_manager()` returns the service-manager manager; `IndexedManager.get_all()` returns `_objects.values()`. | `TARGET_CONFIRMED` | None. | Manager population. |
| O-02 | `observers.py:20-41,91-94` | For each candidate, call `si.get_sim_instance(allow_hidden_flags=hidden_flags)`. | `SimInfo.get_sim_instance` has one keyword-only `allow_hidden_flags` parameter and calls `sim.is_hidden(allow_hidden_flags=...)`. | `TARGET_CONFIRMED` for call shape | The value passed is a separate falsification in O-03. | Instantiated Sim availability. |
| O-03 | `observers.py:91,94` | Default `hidden_flags=None` is assumed usable for a live Sim. | Exact `GameObject.is_hidden` executes `int(self._hidden_flags) & ~int(allow_hidden_flags)`; exact CPython proof shows `int(None)` raises `TypeError`. Target `HiddenReasonFlag` values are `NOT_INITIALIZED=1`, `RABBIT_HOLE=2`, `REPLACEMENT=4`; `ALL_HIDDEN_REASONS=7`. | `TARGET_FALSIFIED` | Import/use target `objects.ALL_HIDDEN_REASONS`; do not pass `None`. | One stable LAB poll after repair. |
| O-04 | `observers.py:31-38` | Read `selectable = si.is_selectable`; require exact bool. | Target property calls `services.client_manager().get_client_by_household_id(self._household_id)`; absent client returns `False`, otherwise membership in `client.selectable_sims` returns a Boolean. | `TARGET_CONFIRMED` | None; preserve no coercion. | Candidate property read and singleton result. |
| O-05 | target path of O-04 | Client lookup used by the target property is expected to have household semantics. | `ClientManager.get_client_by_household_id(household_id)` scans client values and returns matching `client.household_id`, else `None`. | `TARGET_CONFIRMED` | None. | Client/household runtime state. |
| O-06 | `observers.py:95` | `sim.queue` is an iterable current queue. | Target `Sim.__init__` sets `queue=None`; later runtime code may replace it with `InteractionQueue`. | `TARGET_CONFIRMED` member; `RUNTIME_VALUE_DEPENDENT` value | Guard `None` before iteration and preserve incomplete/missing semantics. | Empty/stable LAB point. |
| O-07 | `observers.py:96` | `sim.si_state` is an iterable running set. | Target `Sim.si_state` returns `_si_state`; `Sim.__init__` constructs `SIState(self)`. | `TARGET_CONFIRMED` member; `RUNTIME_VALUE_DEPENDENT` contents | Guard any transient `None` or unusable value without claiming complete observation. | Empty/stable LAB point. |
| O-08 | `snapshot.py:21-60` | `len(items)` and `iter(items)` are safe for queue/running views and cap at eight. | `InteractionQueue.__iter__` yields running then bucket items and `__len__` counts unique items. `SIState.__iter__` and `__len__` delegate to its super-interaction set. | `TARGET_CONFIRMED` for initialized views; `TARGET_FALSIFIED` for source `None` path | Normalize `None` before `_bounded_items`; retain conservative completeness. | Queue/running contents and nonblocking cost. |
| O-09 | `observers.py:70-88` | Read `entry.guid64` and stringify it; failures are optional. | Exact `Interaction` Python code does not define a `guid64` accessor in the inspected class code; tuning/metaclass/native value is opaque. | `TARGET_BYTECODE_OPAQUE` | No fallback; keep bounded string/catch behavior. | Concrete interaction values. |
| O-10 | `observers.py:77-79` | Read `entry.affordance` and stringify it. | Exact `Interaction.affordance` property returns the class (`cls`); its display string is runtime/tuning dependent. | `TARGET_CONFIRMED` | None. | Concrete string length/value. |
| O-11 | `observers.py:81-83` | Read `entry.target.id` and stringify it; missing target is optional. | Exact `Interaction.target` property returns `_target`; target object's concrete `id` member/value is dynamic and not required for every entry. | `TARGET_BYTECODE_OPAQUE` | No fallback; keep catch and `None` default. | Concrete target/value exposure. |
| O-12 | `observers.py:84-87` | Read `entry.context.source` verbatim and stringify it. | Exact `Interaction.source` returns `self.context.source`; `InteractionContext` stores the source value. | `TARGET_CONFIRMED` member; `RUNTIME_VALUE_DEPENDENT` value | Keep `source_raw`; keep conservative `source_norm=UNKNOWN` until witness. | E1-A source values. |
| O-13 | `observers.py:48-53` | Read persistence service, GUID, save-slot buffer, and `buff.slot_id`; absent values become `None`. | `get_persistence_service` returns a singleton; `get_save_slot_proto_guid` returns proto GUID or `None`; `get_save_slot_proto_buff` returns save-slot proto or `None`. | `TARGET_CONFIRMED` getters; `RUNTIME_VALUE_DEPENDENT` values | None guard required for the buffer before `.slot_id`. | Stable completion-point IDs. |
| O-14 | `observers.py:51-53` | Dereference `buff.slot_id` without checking `buff`. | Exact target returns `None` when `_save_game_data_proto` is absent. Current code then raises `AttributeError` before returning a save snapshot. | `TARGET_FALSIFIED` | If `buff is None`, return `slot_id=None` and preserve the schema's missingness/completion rule. | Transient save-service state. |
| O-15 | `observers.py:57-67` | Read `services.time_service().sim_now`, `absolute_ticks()`, and `services.game_clock_service().clock_speed`; stringify calendar/speed and derive paused. | Target `time_service()` and `game_clock_service()` return service-manager members. `DateAndTime.absolute_ticks()` returns `int`; `sim_now` returns a zero value when time service is not alive. | `TARGET_CONFIRMED` members; `RUNTIME_VALUE_DEPENDENT` values | None/error guards remain bounded; no API substitution. | Clock/calendar/speed/paused witness. |
| O-16 | `observers.py:104` | Read `sim_info.id`, stringify it as body ID. | `SimInfoBaseWrapper.id` getter returns `self.sim_id`. | `TARGET_CONFIRMED` | None. | Stable ID witness. |
| O-17 | `snapshot.py:4-18,21-38` | Use process-local `hex(id(entry))`, deduplicate same live object, copy all fields to plain data. | No Sims import or target-specific method is used. Target interaction objects are converted to strings/IDs before queueing. | `TARGET_CONFIRMED` boundary; no target API defect | None. | Interaction identity/APPEAR runtime witness. |
| F-01 | `probe.py:407-432` | Convert poll exceptions to bounded `guard_exhausted` rows. | Generated reasons and timestamps satisfy the closed schema; `schema.make_record` does not perform a target read. | `TARGET_CONFIRMED` | None. | Physical row requires healthy writer. |
| W-01 | `writer.py:1-10` | Writer must never import or call game APIs. | Source imports only `json`, `os`, `queue`, `threading`, `time`, `uuid`, and `.schema`. | `TARGET_CONFIRMED` | None. | Static guard already passes. |
| W-02 | `writer.py:96-149,173-199` | Queue a validated row without blocking; writer thread owns file I/O. | Pure stdlib `Queue`, thread, and validation mechanics. | `TARGET_CONFIRMED` | None. | Filesystem permissions and queue/cap state. |
| W-03 | `writer.py:218-339` | Open active JSONL file, serialize, write, flush, rotate under caps. | Pure stdlib path; accepts plain schema data. | `TARGET_CONFIRMED` | None. | Physical disk/AV timing and cap witnesses. |
| S-01 | `probe.py:308-318` | Pass stored `_ALARM_HANDLE` to `alarms.cancel_alarm`; repeated stop is safe. | Exact target `cancel_alarm(handle)` calls `handle.cancel()`; cancel hard-stops/clears scheduled element and tears down handle. | `TARGET_CONFIRMED` | None. | Stop/re-arm and zone dead-handle witness. |
| S-02 | `probe.py:321-338`, `writer.py:201-210,375-433` | Disarm after stop signals close and permits `PRE_DISARM`/`session_close`. | No Sims API is used; writer drains and closes under its bounded deadline. | `TARGET_CONFIRMED` | None. | Close-row and predecessor gate witness. |

## 6. A–M concrete binding dispositions

| A–M item | disposition |
| --- | --- |
| A build identity | Runtime-only menu/build witness; no production Sims binding. |
| B runtime self-report | Bootstrap/stdlib fact; required import and `perf_counter` witness. |
| C imports | Target-confirmed by exact archives and current bootstrap contract. |
| D scheduler | Target-closed after weak-referenceable owner repair; callback count, pause, save hash, and nonblocking behavior remain runtime witnesses. |
| E poll getters | Mixed: `sim_info_manager`, `get_all`, `is_selectable`, IDs, clock members, and interaction members are target-confirmed/opaque as marked; hidden flags, save-buffer `None`, and queue `None` handling are source corrections required before a new candidate. |
| F monotonicity | Stdlib runtime witness. |
| G GUID/slot/Sim reads | Target getter contracts confirmed; actual presence/stability is runtime completion-point evidence. |
| H persisted save mutation | Runtime saves-directory hash witness only; no target binding defect. |
| I command family | Registration and observed native callback shape target-confirmed; state-machine outcomes remain runtime witness. |
| J state/cancel | Target cancellation closed; state transitions, dead-handle, and predecessor gates remain runtime/unit witnesses. |
| K writer/logging | Pure stdlib mechanics; focused tests cover caps, rotation, serialization, and sticky failure behavior. |
| L drop discipline | Pure writer/runtime workload witness. |
| M bootstrap/root/session ordering | Bootstrap ordering is source-correct; scheduler cannot callback synchronously; root and physical row remain runtime evidence. |

## 7. Summaries

### ALREADY_PROVEN_FIXES

1. Native ordinary string command arguments are lowercased; the closed
   `lab_e1`/`lab_e1_fork` adapter mapping is present and correct.
2. `clock.interval_in_real_seconds(1)` already returns `TimeSpan`; current
   source passes it directly.
3. The target callback handle is the same `AlarmHandle` returned by creation;
   the identity guard is correct.
4. The direct six-positional `register` boundary and four command names match
   the target Python command surface.
5. `initialize_probe()` registers commands before deriving the root and
   emitting bootstrap; an actual registration exception is not swallowed by
   this initialization path.

The weak-referenceable owner requirement is also proven, but the current 1.0.6
source still contains `_PROBE_ALARM_OWNER = object()`. It is therefore a
pending correction, not an applied 1.0.6 fix.

### NEW_TARGET_FALSIFICATIONS

1. `observers.poll_once` passes `hidden_flags=None` to a target path that calls
   `int(allow_hidden_flags)`. This causes every instantiated Sim candidate to
   be skipped and can produce `LAB_IDENTITY_AMBIGUOUS:0` before a substantive
   first poll.
2. `get_save_slot_proto_buff()` is target-defined to return `None` when the
   persistence proto is absent; `_save_snapshot` dereferences `buff.slot_id`
   without a guard.
3. Target `Sim.__init__` initializes `queue=None`; `_bounded_items` calls
   `iter(None)` without a guard. The source therefore lacks the required
   transient/empty-point None-safety for that target value.

### TARGET_CONFIRMED_BINDINGS

The exact target confirms the command registration boundary, observed native
callback shape, direct real-time interval, time-service/wall-timeline alarm
construction, selected repeating element, callback/repeat semantics, callback
identity, cancel path, manager enumeration, selectability property contract,
SimInfo ID, clock reads, interaction source property, persistence getter
contracts, and all writer boundaries that receive plain data.

### RUNTIME_ONLY_QUESTIONS

* whether the live time service and wall timeline are available at arm/start;
* callback count, pause continuity, zone cessation, and real-time cadence;
* client/household membership and the exact one-eligible-Sim result;
* save proto presence and completion-point GUID/slot stability;
* queue/running contents and their transient lifecycle state;
* concrete interaction GUID, target, affordance, and source values;
* physical writer permissions, directory caps, queue pressure, and file timing;
* the A–M menu, save-hash, bootstrap, state-machine, and close-row witnesses;
* conservative `source_norm` mapping, which remains `UNKNOWN` until the
  Owner-controlled E1-A observations establish exact target values.

### OPAQUE_REMAINING_BINDINGS

* Native `_commands` implementation internals are not present as Python bytecode.
  The observed raw arm-shaped callback row is nevertheless compatible with the
  current adapter, so this opacity is not a blocker.
* `Interaction.guid64` is supplied by tuning/metaclass/native machinery not
  represented by the inspected Python class code.
* Concrete `entry.target.id` providers and tuned affordance display values are
  runtime/object dependent. Ashley stringifies and catches these optional reads.

No opaque binding currently prevents a bounded consolidated repair. These are
runtime evidence questions, not reasons to invent a fallback API.

## 8. One consolidated repair set for the next candidate (not implemented)

The next internal candidate should apply all four corrections together:

1. Replace `_PROBE_ALARM_OWNER = object()` with a module-owned ordinary
   weak-referenceable singleton.
2. Import the approved target `objects.ALL_HIDDEN_REASONS` constant and pass it
   to `SimInfo.get_sim_instance(allow_hidden_flags=...)`. Keep the existing
   19-key `required_imports` schema unchanged.
3. Make `_save_snapshot` treat a `None` save-slot proto as missing/unknown
   rather than dereferencing it.
4. Make the queue/running snapshot path explicitly None-safe. A missing queue
   or running view must not be presented as a complete observation.

Preserve the already-correct direct interval binding, lowercase command
adapter, callback identity guard, closed schema, no-fallback command API, and
writer/game-thread boundary. Do not redesign any subsystem or add live-game
imports beyond the approved `objects` constant.

## 9. Verification performed

Focused tests were run under the exact CPython 3.7.0 x64 interpreter:

```text
& C:\Users\Xharv\AppData\Local\Programs\Python\Python370-AshleyE1\python.exe -m unittest discover -s sims-e1/tests -p 'test_*.py'
.....................................................................
----------------------------------------------------------------------
Ran 69 tests in 1.367s

OK
```

The same interpreter validated representative guard rows through
`schema.validate_record` and `schema.serialize_record`:

```text
SELECTABILITY_READ_FAILURE VALID 1107
LAB_IDENTITY_AMBIGUOUS:0 VALID 1105
LAB_IDENTITY_AMBIGUOUS:2 VALID 1105
OBSERVATION_FAILURE:TypeError VALID 1110
```

The AST-only shipped-source guard also passed:

```text
AST_GUARDS=PASS
```

The existing test doubles do not exercise the real target `int(None)` hidden
flag path; that is why the exact-bytecode audit records it as a new
falsification. No source or test edits were made during this campaign.

## 10. Boundary and terminal

```text
source changed: NO
artifact built: NO
installed package changed: NO
Sims launched: NO
Sims command: NO
A-M runtime continuation: NO
E1-A/B/G: NO
E2: NO
power action: NO

E1_TARGET_BINDING_CLOSURE = COMPLETE
```

SIMS4_E1_TARGET_BINDING_CLOSURE: COMPLETE
