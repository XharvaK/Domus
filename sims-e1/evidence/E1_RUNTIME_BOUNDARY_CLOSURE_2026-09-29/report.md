# Project Ashley — Embodiment E1 Runtime Boundary Closure

Date: 2026-09-29 (Europe/Istanbul)

Scope: read-only runtime-boundary research and evidence closure for internal
probe 1.0.8. No product source, test, verifier, package, or artifact was
changed. No build, install, uninstall, Sims launch, Sims command, save, E1-A,
E1-B, E1-G, E2, or power action was performed by this campaign.

## 1. Baseline and evidence boundary

| Item | Value |
|---|---|
| repository | C:\\Users\\Xharv\\Projects\\Ashley |
| branch | main |
| HEAD | 48a4d7421293553fbacc054541ded69b478df369 |
| starting tree | 43eb0ffc11f62d27b7a2225dd2c8cbd4ed6bee70 |
| origin/main | 48a4d7421293553fbacc054541ded69b478df369 |
| internal probe | 1.0.8 |
| product-facing name | Embodiment 1.0.0 |
| evidence directory | sims-e1/evidence/E1_ACCEPTANCE_2026-09-29_08/ |
| raw session | ashley_e1_0cfeefbe-6c57-4b21-a152-6acdc6aed25a.jsonl |
| raw session SHA256 | C8282A64B3E969C85D95AE89B81703C8F894B9BEC418D46806EC855B5E5139D0 |
| session UUID | 0cfeefbe-6c57-4b21-a152-6acdc6aed25a |
| Sims build | 1.128.90.1030 |

The raw session contains 416 physical rows, with contiguous
written_sequence values 0..415:

| Event kind | Count |
|---|---:|
| session_open | 1 |
| presence_snapshot | 406 |
| session_checkpoint | 9 |
| session_close | 0 |

The final physical row has all counters at zero and writer.state=OK. The
session has no physical session_close. Two exact Owner submissions of
ashley_e1.stop produced no observable disarm/close transition; Sims was then
quit normally. This is an observed boundary fact, not a source-change claim.

## 2. Consolidated classifications

~~~text
WRITER_STEADY_STATE                 = FALLS_BEHIND_PROVEN
CAP_SCAN_FREQUENCY                 = EVERY_PHYSICAL_ROW_TWICE
CAP_SCAN_BOTTLENECK                = NOT_SUPPORTED
CAP_SCAN_REPAIR_SEAM               = REQUIRED_SCALABILITY_SEAM
STOP_CODE_REGRESSION_1_0_8         = NO
CANCEL_BINDING_AFTER_LONG_REPEAT   = TARGET_CLOSED
CANCEL_EXCEPTION_SYMPTOM_MATCH     = PARTIAL
WRITER_LAG_CAUSAL_FOR_STOP         = NOT_SUPPORTED
STOP_ROOT_CAUSE                    = UNRESOLVED_RUNTIME_CAUSE
~~~

CAP_SCAN_BOTTLENECK is NOT_SUPPORTED as the explanation for the observed
approximately 0.57 physical-row/second service rate because the isolated
directory scan is approximately 1.38 ms. The scan is still a real O(n),
twice-per-row defect and remains a deterministic repair seam for scaling and
cap correctness.

## 3. Producer and writer rates

The producer rate is calculated from the wall and monotonic timestamps on
physical presence_snapshot rows. The 406 physical presence rows span
414.392 seconds:

~~~text
producer_rate_wall       = 0.9797486438 presence rows/second
producer_rate_monotonic  = 0.9797488138 presence rows/second
presence_interval_median = 1.024 seconds
presence_interval_p90    = 1.033 seconds
presence_interval_max    = 1.264 seconds
~~~

The writer rate is reconstructed from successive physical checkpoint rows.
The checkpoint rows are written after queued presence work, so their lag from
the preceding physical presence row is a direct backlog-age indicator.

| Checkpoint sequence | Preceding presence sequence | Checkpoint lag |
|---:|---:|---:|
| 10 | 9 | 11.542 s |
| 48 | 47 | 35.375 s |
| 87 | 86 | 59.151 s |
| 120 | 119 | 88.202 s |
| 157 | 156 | 113.897 s |
| 189 | 188 | 143.605 s |
| 223 | 222 | 172.842 s |
| 258 | 257 | 199.803 s |
| 294 | 293 | 226.493 s |

Checkpoint-to-checkpoint physical service rates were:

~~~text
10 -> 48:   38 records / 61.684 s = 0.6160 records/s
48 -> 87:   39 records / 62.690 s = 0.6221 records/s
87 -> 120:  33 records / 61.796 s = 0.5340 records/s
120 -> 157: 37 records / 62.423 s = 0.5927 records/s
157 -> 189: 32 records / 61.429 s = 0.5209 records/s
189 -> 223: 34 records / 62.971 s = 0.5399 records/s
223 -> 258: 35 records / 61.960 s = 0.5649 records/s
258 -> 294: 36 records / 62.492 s = 0.5761 records/s
~~~

The sustained writer service rate is therefore approximately 0.57 physical
records/second, below the approximately 0.98 presence rows/second producer
rate. The increasing checkpoint lag proves that the writer falls behind while
sampling. The late checkpoints occur after the producer has stopped, so their
lag is not an exact queue-depth measurement.

Approximate backlog estimates while the producer was active were 11, 34, 57,
86, 111, 140, and 168 rows at checkpoint sequences 10, 48, 87, 120, 157,
189, and 223 respectively. They are estimates from observed lag, not exact
queue depth: rows still in memory are not present in the JSONL and the queue
does not record depth.

## 4. Complete writer path and physical operations

The current sims-e1/src/ashley_e1/writer.py path is:

1. The game thread validates a record and calls queue.put_nowait through
   TelemetryWriter.try_put. Admission never blocks the game thread.
2. A daemon writer thread dequeues records and performs serialization and
   physical writes.
3. The writer opens the active file with open(path, "xb").
4. _write_direct serializes the row, checks capacity, and calls
   _write_physical.
5. _write_physical checks capacity again, writes payload plus newline, updates
   the active byte count, and marks the stream dirty.
6. _flush_if_due flushes on the configured five-second sampling cadence;
   checkpoints and close paths force a flush.
7. Rotation performs bounded active-file and sibling checks, then opens the
   next active file.
8. signal_close sets the stop event. The writer drains until its bounded
   deadline, emits PRE_DISARM and session_close, flushes, closes the handle,
   calls task_done for dequeued work, and marks itself idle.

The cap-related filesystem operations are:

~~~text
os.path.exists(active_path)
os.path.getsize(active_path)
os.listdir(telemetry_root)
os.path.isfile(each_directory_entry)
os.path.getsize(each_directory_entry)
os.makedirs(telemetry_root, exist_ok=True)
open(active_path, "xb")
stream.write(payload + newline)
stream.flush()
stream.close()
~~~

_directory_size(root) performs a full os.listdir plus isfile and getsize
traversal. _can_fit performs that directory scan and _write_direct calls
_can_fit before _write_physical, which calls it again. An ordinary physical row
therefore performs two full directory scans.

Relevant source seams at this baseline are:

~~~text
writer.py:42-51    _directory_size
writer.py:256-306  open, _can_fit, _write_physical
writer.py:336-447  direct row, checkpoint, row and flush paths
writer.py:449-522  close, drain, shutdown discard and writer loop
probe.py:139-142   _dispatch_stop
probe.py:314-324   _cmd_stop
~~~

## 5. Directory and isolated operation timing

The actual telemetry root is:

~~~text
C:\\Users\\Xharv\\OneDrive\\Belgeler\\Electronic Arts\\The Sims 4\\AshleyE1Telemetry
~~~

The root is OneDrive-backed. It contained 17 entries and 1,644,315 total
bytes at inspection time. There were 12 bootstrap files, four non-rotated
session files, and zero rotated siblings. The four session files included the
current 840,186-byte file, the prior 791,424-byte file, and two zero-byte
files. All inspected files had the Archive attribute and no Offline or
ReparsePoint attribute was externally observable.

The isolated harness loaded schema.py and writer.py directly in a synthetic
package namespace so that the Sims package initializer was not imported. It
used the bundled Python 3.12.14 runtime, not the target embedded CPython
3.7.0; therefore these are host-side timing measurements, not an exact target
runtime performance qualification. The representative payload was taken from
a preserved presence_snapshot row.

| Operation | Samples | Min ms | Median ms | P90 ms | Max ms |
|---|---:|---:|---:|---:|---:|
| os.listdir(root) | 300 | 0.1213 | 0.1251 | 0.1329 | 0.2990 |
| writer._directory_size(root) | 300 | 1.3236 | 1.3785 | 1.4236 | 1.6044 |
| os.path.getsize(active) | 1000 | 0.0347 | 0.0362 | 0.0385 | 0.1315 |
| writer._can_fit(temp) | 300 | 0.1957 | 0.2034 | 0.2172 | 0.3345 |
| raw buffered write, open/write/close | 200 | 0.1916 | 0.2142 | 0.2401 | 0.3763 |
| normal five-second-style flush | 200 | 0.0030 | 0.0039 | 0.0052 | 0.1219 |
| schema.validate_record | 300 | 0.0830 | 0.0841 | 0.0879 | 0.1562 |
| schema.serialize_record | 300 | 0.0980 | 0.0992 | 0.1012 | 0.1532 |

The measured complete directory scan is approximately 1.38 ms. Two scans per
ordinary row are approximately 2.76 ms under this harness. No isolated
operation measured near one second per row. This supports a real avoidable
filesystem overhead, but does not support attributing the observed 1.75-second
physical-row interval to the scan alone. OneDrive and embedded-Python effects
were not reproduced by this harness, so the result is not a claim that no
environmental latency exists.

~~~text
CAP_SCAN_FREQUENCY  = EVERY_PHYSICAL_ROW_TWICE
CAP_SCAN_BOTTLENECK = NOT_SUPPORTED
~~~

## 6. Deterministic cap-accounting options and proposed repair

The current per-row directory scan is both a performance seam and a source
of timing variability. The bounded alternatives are:

1. Initial directory inventory plus writer-owned logical byte accounting.
2. Initial inventory plus logical accounting, with bounded full-directory
   reconciliation at flush/checkpoint/rotation/close boundaries.
3. Continue scanning on every row. This preserves the current O(n) cost and
   is not a deterministic scaling repair.

The proposed deterministic repair is option 2:

- Inventory the telemetry directory at writer/session start, including
  bootstrap and prior-session files.
- Maintain writer-owned logical totals for the active file and directory.
- Include buffered-but-not-flushed bytes in the logical active-file total.
- Add the payload plus newline to the logical total before admission; commit
  the logical increment only after a successful stream.write.
- Treat a partial or unknown write as sticky writer failure. Do not claim an
  exact byte total after an uncertain write.
- On rotation, retain the completed active file in the directory total and
  start the new active file at zero.
- Reconcile the full directory at the five-second flush boundary, periodic
  checkpoint, rotation, and close. If reconciliation fails or returns
  unknown, fail closed before further physical writes.
- If an external file is added between reconciliations, it is discovered at
  the next bounded reconciliation; no later write is admitted after a
  discovered cap violation.

This keeps the existing 8 MiB active-file cap, four rotated siblings per
session, and 200 MiB directory cap. It removes the twice-per-row scan while
retaining a bounded external-file safety check. This is a proposal only; no
implementation was performed.

## 7. Process-quit loss semantics

The 1.0.8 session ended without a successful stop/disarm boundary. Therefore:

- The game-thread queue could still contain admitted rows.
- The stream could contain dirty buffered bytes that had not been flushed.
- No canonical signal_close, bounded drain, PRE_DISARM, final
  session_close, or final close was observed.
- The physical JSONL contains only rows that reached the operating-system
  write path.
- Final counters of zero describe the last physical row. They do not prove
  that no queued or buffered rows were lost.
- The absent session_close is direct evidence of incomplete close.

An exact lost-row count cannot be reconstructed from this session. It would
be unsafe to infer it from the final counters or the physical row count.

## 8. 1.0.7 stop evidence versus 1.0.8

The prior 1.0.7 session is preserved at the telemetry root:

~~~text
ashley_e1_e08c49af-f0d4-4cd0-86f6-cfc45bd84aa8.jsonl
bytes   = 791424
SHA256  = 770B450728552FABF86E76B51C0513B1B5CE078642F29669793D3CCDD506E8A7
rows    = 391 (session_open 1, presence 381, checkpoints 8, close 1)
~~~

Its final row is a physical session_close with close_reason=DISARM_CLEAN; its
final counters include dropped_queue=51 from shutdown-deadline discard. That is
evidence that the 1.0.7 stop/disarm path reached the writer close path,
although the close was not lossless.

The preserved 1.0.7 acceptance notes and raw session provide the following
control facts:

- the first unpaused witness contained 59 callbacks in approximately 60
  seconds;
- Owner pause continuity produced 71 callbacks, with zero drops before
  closure;
- the last physical presence callback was sequence 388 at wall timestamp
  1790667233296, 388.493 seconds after the first physical presence callback;
- no further presence callback was physically written after sequence 388;
  sequence 389 was PRE_DISARM and sequence 390 was session_close;
- repeated start was rejected/handled as designed and the final
  redundant_starts counter was 1;
- arm while sampling was rejected;
- stop while sampling passed;
- redundant stop while ARMED passed;
- disarm/session close passed before the separate drop-discipline blocker.

This is the exact successful control path that reached a final close under the
same Sims build and target alarm API. The callback stream becoming absent after
sequence 388 is physical evidence that sampling stopped before the close rows.

The current 1.0.8 probe.py is unchanged from the accepted 1.0.7 probe source.
The current Sims build and target runtime are also the same. The observed stop
difference is therefore not a demonstrated 1.0.8 source regression:

~~~text
STOP_CODE_REGRESSION_1_0_8 = NO
~~~

## 9. Native command wrapper and argument shape

The source registers the four commands through the target sims4.commands
registration path. The stop dispatch adapter is:

~~~python
def _dispatch_stop(*args, _session_id=0, **kwargs):
    if args or kwargs:
        return False
    return _cmd_stop(_connection=_session_id)
~~~

The target native wrapper has the extracted signature
invoke_command(*args, _session_id=0, **kw). It injects _connection only when
the semantic function declares _connection; the adapter above instead declares
_session_id and explicitly maps it to _connection. The raw diagnostic for the
arm-shaped call had one positional str ('lab_e1'), zero ordinary keywords, and
an integer session id. That shape is accepted by the 1.0.3 arm adapter and the
later adapters.

For stop, the adapter reaches _cmd_stop only when ordinary args and ordinary
kwargs are both empty. Any extra positional value returns False. Any ordinary
keyword, including _connection, is rejected by the adapter; _session_id is
the private injected parameter and is consumed by the Python signature. The
exact Owner invocation was the no-argument form, so the adapter's argument
guard is compatible with that invocation.

The six-positional registration call matches the extracted target registration
shape. No duplicate registration, overwritten registration, or command-name
collision was found in the inspected source or preserved evidence. The
available evidence does not contain a raw stop-dispatch witness after the long
session, so command availability/lifetime after a long session remains a
runtime-unknown rather than a proven cause.

The target wrapper catches BaseException, writes command error output and a
warning, then re-raises. The current _cmd_stop has no local exception boundary
around alarms.cancel_alarm:

~~~python
if _STATE == "SAMPLING":
    if _ALARM_HANDLE is not None:
        alarms.cancel_alarm(_ALARM_HANDLE)
    _ALARM_HANDLE = None
    _STATE = "ARMED"
    _set_writer_sampling(False)
~~~

Thus an exception from the target cancel call exits before _ALARM_HANDLE is
cleared, before _STATE becomes ARMED, and before writer sampling is stopped.
This is symptom-compatible with the observed command no-effect boundary. It
is not proof that the cancel call raised, because no exception record or target
command error trace was captured.

## 10. Target alarm cancellation and runtime evidence

The preserved target bytecode is:

~~~text
C:\\Users\\Xharv\\AppData\\Local\\Temp\\ashley-e1-scheduler-binding-20260929\\alarms.pyc
bytes   = 7859
SHA256  = 8C019CC9696AD12FA7FD1AEB0D07090FE1D8ECB956687E2A9BE489FDF0362C58
magic   = 420d0d0a
~~~

The target binding is alarms.cancel_alarm(handle). It calls
AlarmHandle.cancel(). A handle already torn down returns immediately;
otherwise cancel unregisters auto-cleanup, clears/stops the scheduled element,
and tears down the handle. The stored handle is passed positionally. There is
The accepted handle is the target AlarmHandle object stored by probe.py. The
same cancellation path applies between repeating callbacks, after many
repeats, and after a pause: it removes the scheduled repeating element rather
than waiting for another callback. If the handle or element is already
torn-down/dead, the target path returns through its already-torn-down case.
Repeated cancellation is idempotent for an already-torn-down handle. The
bytecode review found no additional deterministic exception path for these
normal lifecycle states. Exact target execution under embedded CPython 3.7.0
was not re-run in this read-only pass.

There is no evidence that the source binding selects the wrong target API or uses an
alternate cancel API:

~~~text
CANCEL_BINDING_AFTER_LONG_REPEAT = TARGET_CLOSED
~~~

The long-repeat runtime witness itself is absent because the 1.0.8 stop attempt
did not produce a close row. The structural target binding is closed; the
runtime failure remains unresolved.

## 11. Stop logs, silent window, and writer-lag causality

Read-only inspection found no LastException, lastUIException, last-crash, or
Ashley stop-error file under the Sims root. Config.log contained build and
options information but no Ashley stop trace or cancel exception. The current
raw session also contains no stop, guard, or close row.

The native wrapper's re-raise behavior creates a possible visible command
error path: it catches BaseException long enough to write command error output
and a warning, then re-raises. That can be visible in command output or the
console, but it is not a guaranteed persistent Sims log. If cancel_alarm
raised, the exception would leave sampling active because the three
state-transition statements would not execute. The available persistent
evidence does not show such an exception. The mechanical result is:

~~~text
CANCEL_EXCEPTION_SYMPTOM_MATCH = PARTIAL
~~~

Writer lag is not a supported cause of native stop command failure:

- game-thread admission uses nonblocking put_nowait;
- the writer runs on a separate daemon thread;
- the callback stream continued at approximately 1 Hz while the physical
  writer fell behind;
- no game-thread join or blocking writer flush is in _cmd_stop;
- no source regression exists between 1.0.7 and 1.0.8.

The writer's filesystem calls can contend for CPU, filesystem, and the Python
GIL, but they do not hold a stop-specific lock or join. The observed continued
callback execution while the writer was behind is direct evidence against an
indefinite native-command blockage. This does not identify the actual stop
cause; it only excludes writer lag as the supported mechanism.

Therefore:

~~~text
WRITER_LAG_CAUSAL_FOR_STOP = NOT_SUPPORTED
~~~

The stop root cause remains an unresolved runtime cause among command
availability/lifetime, target cancel exception, or another target-side dispatch
condition. This report does not select one without evidence.

## 12. Minimal failure-only observability for the next candidate

The next candidate should add only bounded, schema-compliant failure evidence.
It should not add ordinary command chatter, a new schema version, a fallback
command API, or a network/file logging path.

1. In _dispatch_stop, if unexpected positional arguments or ordinary keyword
   arguments are received while active, emit one existing guard_exhausted row
   with a bounded reason such as STOP_DISPATCH_INVALID_SHAPE, then return
   False.
2. In _cmd_stop, catch only Exception around
   alarms.cancel_alarm(_ALARM_HANDLE). Emit one existing guard_exhausted row
   with a bounded cancel-failure reason such as
   STOP_CANCEL_FAILURE:<ExceptionName>. Leave _ALARM_HANDLE and _STATE
   unchanged on cancel failure; do not claim that stop succeeded.
3. On successful cancel, perform the existing state transition and writer
   sampling signal. Do not emit a normal success row solely for observability.

This preserves fail-closed state truth and makes the next runtime attempt
diagnosable without mutating the product contract beyond the existing bounded
failure event.

## 13. Complete next-candidate closure matrix

| Seam | Observed evidence | Source mechanism | Classification | Repair required? | Runtime witness still required? |
|---|---|---|---|---|---|
| producer rate | 0.9797486 presence rows/s | approximately 1 Hz observer callback | measured | no | no |
| writer service rate | approximately 0.57 physical records/s | daemon writer plus physical filesystem path | FALLS_BEHIND_PROVEN | yes | yes, after repair |
| cap directory scan | two full scans per ordinary row | _write_direct and _write_physical both call _can_fit | EVERY_PHYSICAL_ROW_TWICE | yes | yes, after repair |
| active-file accounting | os.path.getsize plus active byte counter | current plus pending byte calculation | deterministic but scan-coupled | yes | yes, after repair |
| buffered write | dirty stream and nonblocking queue admission | rows can remain queued or buffered at quit | bounded but not lossless on failed close | yes | yes |
| flush cadence | five-second due path, checkpoint/close force paths | _flush_if_due and explicit flush calls | writer lags in observed session | yes | yes |
| checkpoint generation | nine physical checkpoints | writer-side periodic checkpoint after queued work | generated, but increasingly delayed | no source change alone | yes |
| queue backlog | checkpoint lag grew to 226.493 s | producer faster than writer | backlog growth proven | yes | yes |
| process quit | no session_close in 1.0.8 | no canonical signal_close/drain/close | incomplete close; loss possible | yes, truthful provenance | yes |
| command registration | four registrations; six-positional target shape | sims4.commands.register | structurally compatible | no source change alone | yes |
| stop adapter | no-arg call required; exact no-arg shape was submitted | _dispatch_stop validates args/kwargs | compatible for submitted shape | observability only | yes |
| cancel_alarm | target AlarmHandle.cancel path is closed | alarms.cancel_alarm(handle) | TARGET_CLOSED | no alternate API | yes |
| post-cancel transition | state transition follows cancel without local catch | _ALARM_HANDLE=None, ARMED, writer sampling false | exception window exists | yes | yes |
| failure observability | no stop/guard/error row or persistent exception | wrapper may re-raise without durable evidence | insufficient | yes | yes |
| disarm dependency on stop | disarm is a separate writer signal, but stop failed first | _cmd_disarm calls _cmd_stop then close signal | stop boundary unresolved | yes | yes |

The writer cannot currently be shown to sustain 1 Hz indefinitely without
backlog growth. The stop command cannot currently be shown to have executed
correctly or to have failed with bounded attributable evidence. The minimum
next runtime candidate therefore needs both the writer repairs and the
failure-only stop observability above.

## 14. Consolidated proposed 1.0.9 repair set

This is the single proposed repair set. It is not implemented in this
campaign.

1. Deterministic writer byte accounting. Replace per-row full-directory cap
   scans with writer-owned logical byte accounting, plus bounded
   reconciliation at flush, checkpoint, rotation, and close boundaries. Fail
   closed on unknown inventory or uncertain physical writes.
2. Canonical buffered flush policy. Keep one writer thread and one handle.
   Flush on every checkpoint, cap/failure event, disarm signal, and at least
   every five seconds while sampling. Flush before final close.
3. Three-failure flush state machine. Track consecutive flush failures, reset
   after a successful flush, and enter sticky FAILED_STICKY only on the third
   consecutive failure. Attempt one bounded writer_failed diagnostic and
   remain silent thereafter.
4. Truthful shutdown-loss provenance. Preserve bounded drain and nonblocking
   admission. Track shutdown-deadline discards separately from live queue
   saturation and surface SHUTDOWN_DEADLINE through the existing close reason
   field, or make a non-zero final counter an explicit invalid teardown in the
   verifier. Do not label teardown loss QUEUE_SATURATION.
5. Serialization fault accounting. Account in-memory validation or
   serialization failures as bounded dropped_serialize; keep physical write
   and flush failure transitions distinct and non-recursive.
6. Stop dispatch failure evidence. Add the bounded invalid-shape
   guard_exhausted row described above, without changing the native command
   registration path.
7. Stop cancel exception boundary. Catch only cancel-call exceptions, emit
   one bounded failure row, preserve the pre-stop state on failure, and
   transition to ARMED plus writer-stop only after cancel returns.
8. Focused regression coverage. Add writer-only tests for logical cap
   accounting and reconciliation, buffered flush triggers, three-failure and
   reset behavior, shutdown-loss provenance, and the slow-writer
   reproduction. Add stop-dispatch tests for invalid shape, cancel exception
   state truth, successful cancel, repeated stop, and no writer/sampler activity
   during failed stop. Retain the existing schema, import, target-binding, and
   sequence/cap guards.

No item above authorizes a fallback command API, synthetic Sims input, a new
event kind, E1-A/B/G, E2, installation, or runtime acceptance.

## 15. Closure boundary

~~~text
source changed: NO
tests changed: NO
artifact built: NO
Sims launched by this campaign: NO
Sims command by this campaign: NO
install/uninstall: NO
E1-A/B/G: NO
E2: NO
power action: NO
~~~

The successful 1.0.7 close evidence and the incomplete 1.0.8 close evidence
remain preserved. The 1.0.8 raw file hash and all rate/timing conclusions in
this report are bound to the evidence listed above. No source or runtime
mutation was performed.

SIMS4_E1_RUNTIME_BOUNDARY_CLOSURE: COMPLETE
