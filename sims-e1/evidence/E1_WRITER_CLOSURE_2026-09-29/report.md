# Project Ashley — Embodiment E1 Writer / Backpressure Closure

Date: `2026-09-29` (Europe/Istanbul)

Scope: read-only source/evidence audit. No source edit, test edit, build,
package mutation, install/uninstall, Sims command, E1-A/B/G, E2, or power
action was performed by this campaign.

## Baseline and evidence boundary

| Item | Value |
|---|---|
| repository | `C:\\Users\\Xharv\\Projects\\Ashley` |
| branch | `main` |
| HEAD | `2398e327000eac19abee2e31ff855eca1d141129` |
| `origin/main` | `2398e327000eac19abee2e31ff855eca1d141129` |
| starting tree | `bd8545bc0a4c407dd5e3b1e94bd5a3e9e848508d` |
| internal probe | `1.0.7` |
| product-facing name | `Embodiment 1.0.0` |
| installed artifact SHA256 | `33E75CAFAEE28E63EAEC7887E29A59F520708E08D1360C83C1034229CA2EA736` |

The preserved blocker record is
[`BLOCKED_DROP_DISCIPLINE.md`](../E1_ACCEPTANCE_2026-09-29_07/BLOCKED_DROP_DISCIPLINE.md).
It was not rewritten.

The acceptance session file was closed before this audit. The live source
was copied into this new evidence directory as
[`session_e08c49af-f0d4-4cd0-86f6-cfc45bd84aa8.jsonl`](session_e08c49af-f0d4-4cd0-86f6-cfc45bd84aa8.jsonl).
The source file and this copy are both 791,424 bytes and both have SHA256
`770B450728552FABF86E76B51C0513B1B5CE078642F29669793D3CCDD506E8A7`.

Source path:

```text
C:\Users\Xharv\OneDrive\Belgeler\Electronic Arts\The Sims 4\AshleyE1Telemetry\ashley_e1_e08c49af-f0d4-4cd0-86f6-cfc45bd84aa8.jsonl
```

The session UUID is `e08c49af-f0d4-4cd0-86f6-cfc45bd84aa8`.

## 1. Runtime reconstruction

The final JSONL has 391 physical records. `written_sequence` is contiguous
from 0 through 390. There are no sequence gaps, corrupt lines, or dropped
summary rows.

| Metric | Observed value |
|---|---:|
| physical records | 391 |
| sequence minimum / maximum | 0 / 390 |
| sequence gaps | 0 |
| first wall timestamp | 1790666844803 |
| last wall timestamp | 1790667398423 |
| `session_open` position | 0 |
| `session_close` position | 390 |
| `observation_complete=true` | 381 |
| `observation_complete=false` | 0 |
| `observation_complete=null` | 10 non-observation rows |
| writer states | 391 `OK` |
| dropped summaries | 0 |
| close reason | `DISARM_CLEAN` |

Event histogram:

| Event kind | Count |
|---|---:|
| `session_open` | 1 |
| `presence_snapshot` | 381 |
| `session_checkpoint` | 8 |
| `session_close` | 1 |

The `session_open` attestation is complete:

```text
snapshot_guid = "2773024768"
snapshot_slot = "2"
snapshot_sim  = "118245043779534861"
armed_name    = "LAB_E1"
```

Checkpoint rows:

| Sequence | Reason | Wall timestamp | `dropped_queue` | Writer state |
|---:|---|---:|---:|---|
| 24 | `PERIODIC_60S` | 1790666873869 | 0 | `OK` |
| 70 | `PERIODIC_60S` | 1790666936827 | 0 | `OK` |
| 110 | `PERIODIC_60S` | 1790666999117 | 0 | `OK` |
| 144 | `PERIODIC_60S` | 1790667061126 | 0 | `OK` |
| 181 | `PERIODIC_60S` | 1790667122234 | 0 | `OK` |
| 240 | `PERIODIC_60S` | 1790667183542 | 0 | `OK` |
| 288 | `PERIODIC_60S` | 1790667244657 | 0 | `OK` |
| 389 | `PRE_DISARM` | 1790667397763 | 51 | `OK` |

Every physical row carries the four cumulative counters. The complete
run-length chart covers all 391 sequences:

| Sequence range | `dropped_queue` | `dropped_overrun` | `dropped_serialize` | `redundant_starts` | Rows |
|---|---:|---:|---:|---:|---:|
| 0–277 | 0 | 0 | 0 | 0 | 278 |
| 278–388 | 0 | 0 | 0 | 1 | 111 |
| 389–390 | 51 | 0 | 0 | 1 | 2 |

First non-zero counter observations:

| Counter | First sequence | Event kind | Value |
|---|---:|---|---:|
| `dropped_queue` | 389 | `session_checkpoint` (`PRE_DISARM`) | 51 |
| `dropped_overrun` | none | — | 0 throughout |
| `dropped_serialize` | none | — | 0 throughout |
| `redundant_starts` | 278 | `presence_snapshot` | 1 |

The final close row repeats `dropped_queue=51`, `dropped_overrun=0`,
`dropped_serialize=0`, and `redundant_starts=1`. It reports
`close_reason=DISARM_CLEAN` and `writer.state=OK`.

## 2. Exact drop origin

The current `writer.py` has three `dropped_queue` increment sites:

1. `_evict_preferred()` success at line 187, after a full queue evicts one
   `clock_snapshot` or `zone_snapshot`.
2. All-critical queue-full failure at line 194, which sets
   `capture_stopped=True` and `failure_reason="saturation_critical"`.
3. Shutdown deadline discard at line 424, after `get_nowait()` removes each
   still-queued row.

The session has no `clock_snapshot` or `zone_snapshot` rows. The current
probe's game-thread `_emit()` path can enqueue only `session_open`,
`presence_snapshot`, or `guard_exhausted`; the writer creates checkpoints
directly on its own thread. The observed session contains one physical
`session_open`, no guard rows, and 381 physical presence rows. Thus the
maximum game-thread queue admission for this session was 433 rows, below the
fixed capacity of 1024 even if the writer had processed none of them.

The counter remains zero through sequence 388 and changes to 51 only when
the writer emits `PRE_DISARM` and `session_close`. The current `_run()` code
sets an internal `_pending_drop_reason` to `SHUTDOWN_DEADLINE` at line 425,
but the closed `dropped_summary` schema does not permit that reason and no
summary row is emitted.

Therefore:

```text
DROP_ORIGIN = SHUTDOWN_DRAIN_PROVEN
```

This is not a live queue-saturation event.

## 3. Lost-record classification

The 51 discarded queue items cannot be clock-only records. No clock or zone
record exists in this session, and those are the only preferentially
evictable classes in the canonical contract.

The first `session_open` is already physically present at sequence 0. The
remaining queue entries admitted by the active probe path are presence rows
(or a guard row, which is absent from this session). The current observer
path emits `presence_snapshot` for every successful poll, and the canonical
contract classifies presence observations as critical.

Therefore:

```text
LOST_RECORD_CLASS = PRESENCE_CRITICAL_PROVEN
```

This is a load-bearing instrumentation failure for any witness that needs
zero critical loss. It cannot be reclassified as a clock-class tolerance.

## 4. Writer throughput reconstruction

The 381 physical presence rows have callback timestamp intervals from 916 ms
to 1,132 ms, with a 1,022.35 ms mean. The six complete 60-second buckets
contain 59, 59, 58, 59, 59, and 59 callbacks; the final partial bucket has
28. This is consistent with the approximately 1 Hz sampler.

The physical JSONL sizing and queue budget are:

| Budget item | Observed or contractual value |
|---|---:|
| callback rate | approximately 0.98 rows/s |
| mean physical row including LF | 2,024.10 bytes |
| mean `presence_snapshot` including LF | 2,047.16 bytes |
| maximum physical row including LF | 2,354 bytes |
| written presence throughput at observed rate | approximately 2,006.22 bytes/s |
| queue capacity | 1,024 records |
| schema logical queue payload bound | 1,024 × 8 KiB = 8,388,608 bytes (approximately 8 MiB) |
| shutdown backlog | 51 queued records |

The 51-row backlog is a record count from the writer counter. Its byte size
is not directly recorded because discarded rows never reach the file.

The final file contains 381 presence rows and the shutdown counter accounts
for 51 additional queue entries. Given the source event path and the absence
of saturation, the session attempted 432 presence observations and wrote 381
of them before shutdown discarded 51.

The evidence proves no capture-side loss before the teardown counter change.
It does not record queue depth or a writer-side completion timestamp for each
row, so a separate steady-state service rate cannot be measured directly.
It does prove that the writer did not keep up through the required clean
close boundary:

```text
DID_WRITER_KEEP_UP = NO
```

The backlog pattern is terminal: counters remain zero during the live rows,
then 51 queued critical records are discarded when the two-second shutdown
deadline expires. This is a writer-drain failure, not queue saturation.

## 5. Flush-policy comparison

V1.2a §12.5 requires flushes on every checkpoint, every `cap_reached` or
`writer_failed`, the disarm signal, and at least every five seconds while
sampling.

The current `_write_physical()` writes one line and calls `flush()` for every
physical row (writer.py line 255). There is no buffered flush timestamp or
five-second cadence. The implementation therefore satisfies the listed
events incidentally through per-row flushing, but it performs substantially
more flushes than the canonical minimum and does not implement the canonical
cadence as a distinct policy.

```text
FLUSH_POLICY = PLAN_MISMATCH_OVERFLUSH
```

The minimal intended seam is to separate `write()` from `flush()`, retain a
writer-owned last-flush timestamp, and invoke flush at the four canonical
triggers plus the bounded sampling cadence. This report does not implement
that seam.

## 6. Shutdown-deadline comparison

`signal_close()` sets the stop event and returns. `_run()` starts a deadline
of exactly `time.time() + 2.0` seconds after observing the stop event, drains
until `unfinished_tasks == 0` or the deadline expires, then removes remaining
queue entries and increments `dropped_queue` for each one. It writes
`PRE_DISARM`, then `session_close`, closes the stream, and marks the writer
idle.

V1.2a requires a bounded writer-side drain but does not pin a numeric
deadline. Therefore:

```text
TWO_SECOND_DEADLINE = NO_IMPLEMENTER_CHOICE
```

The two-second value is a valid bounded implementation choice only after the
writer can meet the expected workload. In the current candidate it is the
direct cause of the observed 51-record teardown loss.

## 7. Loss-accounting comparison

| Loss path | Current counter | Current in-memory reason | Physical evidence | Canonical disposition |
|---|---|---|---|---|
| queue saturation with disposable eviction | `dropped_queue` | `QUEUE_SATURATION` | none in this session | only clock/zone rows may be evicted |
| all-critical queue saturation | `dropped_queue` | `QUEUE_SATURATION`, `saturation_critical` | none in this session | fail closed; critical loss invalidates witness |
| sampler overrun | `dropped_overrun` | `SAMPLER_OVERRUN` | zero | bounded summary permitted |
| validation admission failure | `dropped_serialize` | `SERIALIZE_FAILURE` | zero | bounded summary permitted |
| shutdown deadline discard | `dropped_queue` | `SHUTDOWN_DEADLINE` | 51 at `PRE_DISARM` and close | still-queued rows counted as loss |

The current counter name conflates queue saturation and shutdown discard.
The internal shutdown reason is not serialized. A `DISARM_CLEAN` close row
therefore means that the Owner disarm boundary was cleanly requested; it does
not mean that every admitted row was written.

The smallest evidence-preserving repair is not a new event kind or a new
`dropped_summary` enum. Keep the existing three `dropped_summary` reasons for
capture-side failures. Preserve the shutdown-discard provenance in memory
and write `reason="SHUTDOWN_DEADLINE"` on the existing `session_close` common
reason field when the deadline discards rows, while retaining
`close_reason="DISARM_CLEAN"` for the Owner command boundary. Add a focused
schema fixture for this existing field usage. If the contract owner rejects
that optional common field, the alternative is to leave the schema unchanged
and treat a non-zero final counter after disarm as an explicit invalid
teardown; it must not be labelled `QUEUE_SATURATION`.

## 8. Flush-failure contract

V1.2a §12.7 requires: three consecutive flush failures stop capture, set
sticky `FAILED_STICKY`, emit a best-effort `writer_failed` row, and remain
silent for the session; a successful flush resets the consecutive-failure
count.

The current writer has no flush-failure counter, no consecutive-failure
state, and no reset-on-success path. An exception from either `write()` or
`flush()` propagates to `_write_row()`, which immediately calls
`_mark_failure("FAILED_STICKY", "write_failure")`. Thus one failure is
terminal, write and flush failures are not distinguished, and the
`writer_failed` attempt is guarded only by `_diagnostic_attempted`.

```text
FLUSH_FAILURE_CONTRACT = MISMATCH
```

## 9. Close and disarm ordering

| Stage | Canonical requirement | Current source | Disposition |
|---|---|---|---|
| game-thread stop | cancel the alarm and leave sampling | `_cmd_stop()` does this | pass |
| game-thread disarm | clear probe state, signal only, return without I/O/join | `_cmd_disarm()` does this | pass |
| disarm flush | flush on the signal | no explicit signal flush; current row flush masks it | mismatch under buffered repair |
| writer drain | bounded writer-side drain | two-second deadline | structurally pass; value unpinned |
| shutdown discard | count still-queued rows | line 424 increments `dropped_queue` | pass, but provenance hidden |
| pre-disarm checkpoint | writer-side checkpoint before close | `_write_close()` writes `PRE_DISARM` | pass |
| session close | best-effort close row with final counters | `_write_close()` writes it | pass structurally |
| final flush and close | flush then close handle | every-row flush, then `_close_stream()` | pass structurally; overflush |
| idle | set writer idle after close | `_run()` closes stream then sets idle/callback | pass |
| truthful loss status | do not imply lossless close | `DISARM_CLEAN` has no shutdown-loss reason | mismatch |

The ordering itself is not the root defect. The load-bearing defect is that
the bounded drain is allowed to discard critical presence rows, while the
physical close record exposes only the Owner boundary and not the discard
provenance.

## 10. Writer-only synthetic reproduction

The current pure-Python writer was loaded without the game package using the
bundled Python 3.12.14 runtime. No Sims module, process, save, or source file
was touched. One hundred valid presence rows were admitted. `_write_physical`
was wrapped only in memory to add a 50 ms delay per physical write, then the
existing `signal_close()` path was used.

Observed harness result:

```text
accepted = 100
idle = True
physical rows = 41
event histogram = presence_snapshot:39, session_checkpoint:1, session_close:1
counters = dropped_queue:61, dropped_overrun:0, dropped_serialize:0,
           redundant_starts:0
close_reason = DISARM_CLEAN
```

This reproduces the exact current-source failure mode: the queue is far below
capacity, the writer reaches its two-second deadline, and the remaining
critical rows are counted as `dropped_queue` while the close remains
`DISARM_CLEAN`.

An in-memory service-rate model also shows why buffered cadence is the
smallest performance seam. With one row per second, 50 ms row work, and a
1.20 s flush cost, per-row flush completes 48/60 rows and leaves a 12-row
backlog; a five-second flush cadence completes 60/60 and leaves no backlog.
These are model parameters, not measured Sims timings. The real session's
1 Hz callback evidence and 51-row terminal loss are the measured facts.

## 11. Complete writer-contract matrix

| Seam | Current behavior | V1.2a comparison |
|---|---|---|
| writer imports | stdlib plus local schema; no game imports | PASS |
| queue capacity | `queue.Queue(1024)` | PASS |
| game-thread admission | `put_nowait`, never blocks | PASS |
| schema admission | validates before enqueue | PASS |
| preferred eviction | oldest clock, then zone | PASS |
| all-critical saturation | stop capture, `saturation_critical` | PASS |
| presence criticality | no preferential eviction path | PASS |
| sequence assignment | writer-side contiguous sequence | PASS in session |
| per-row flush | flushes every row | PLAN_MISMATCH_OVERFLUSH |
| checkpoint flush | incidental through per-row flush | trigger exists, policy not explicit |
| cap/failure flush | incidental through per-row flush | policy not explicit |
| disarm flush | no explicit signal flush | MISMATCH under buffering |
| flush failure threshold | one exception becomes sticky | MISMATCH; needs 3 consecutive |
| flush reset | none | MISMATCH |
| write failure | sticky, non-recursive diagnostic attempt | partial pass; conflated with flush |
| writer-side serialization failure | caught as `write_failure` | MISMATCH with bounded serialize accounting |
| capture drop summary | three canonical reasons only | PASS for those reasons |
| shutdown discard | increments `dropped_queue` | PASS count, provenance incomplete |
| shutdown reason | internal only, not serialized | MISMATCH |
| bounded drain | two seconds | bounded, numeric value unpinned |
| `PRE_DISARM` | emitted before close after drain | PASS |
| final close | final counters and `DISARM_CLEAN` | structurally pass; loss truth incomplete |
| handle close / idle | close stream, then idle callback | PASS |
| rotation and caps | bounded siblings and directory accounting | focused tests pass |
| predecessor-session gate | arm requires writer idle | focused session/binding tests cover it |

## 12. Consolidated proposed repair set

This is a proposal only. No item below was implemented in this campaign.

1. **Canonical buffered flush seam.** Keep one writer thread and one handle.
   Write serialized lines without per-row flushing. Flush on every
   checkpoint, `cap_reached`, `writer_failed`, the disarm signal, and at least
   every five seconds while sampling. Flush before final handle close.

2. **Three-failure flush state machine.** Track consecutive flush failures in
   writer memory. Reset the count after a successful flush. On the third
   consecutive failure, stop ordinary capture, set sticky `FAILED_STICKY`,
   attempt one bounded `writer_failed` diagnostic, and remain silent. Keep
   write errors distinct from flush errors while preserving non-recursive
   accounting.

3. **Shutdown-loss provenance.** Keep bounded drain and non-blocking game
   thread behavior. Track shutdown-deadline discards separately from live
   queue saturation. Preserve the existing `dropped_summary` vocabulary;
   do not mislabel teardown loss as `QUEUE_SATURATION`. Surface
   `reason="SHUTDOWN_DEADLINE"` on the existing `session_close` common reason
   field when rows are discarded, or otherwise make the non-zero final
   counter an explicit invalid teardown in the verifier. Do not add a new
   event kind or enum unless the contract owner later requires one.

4. **Serialization fault seam.** A record that fails in-memory validation or
   serialization must be bounded and non-recursively accounted as
   `dropped_serialize`; an unrecoverable physical write/flush failure alone
   transitions the writer to sticky failure. Add no fallback writer or game
   API.

5. **Focused regression coverage.** Add writer-only tests for buffered flush
   cadence, checkpoint/disarm/cap/failure flush triggers, three-failure/reset
   behavior, shutdown discard provenance, and the slow-writer reproduction.
   Retain the existing 7 writer-bound tests, 12 schema tests, no-game-import
   guard, and focused sequence/cap tests. No full Ashley corpus is required
   for this closure.

## Boundary record

```text
source changed: NO
tests changed: NO
artifact built: NO
Sims launched by this campaign: NO
Sims command by this campaign: NO
install/uninstall: NO
E1-A/B/G: NO
E2: NO
power action: NO
```

No power action was requested or performed. A final read-only process check
did not find `TS4_x64`; this campaign neither launched nor terminated Sims.
No shutdown, reboot, sleep, or hibernate was requested or performed.

SIMS4_E1_WRITER_CONTRACT_CLOSURE: COMPLETE
