# Project Ashley — E1 Session-Open Identity Closure Addendum

Date: 2026-09-29

Scope: read-only source and focused-test inspection for the missing save
identity/session-open integration. No source edit, test edit, build, Sims
launch, Sims command, install, uninstall, E1-A/B/G, E2, or power action was
performed for this addendum.

## Baseline

| Item | Value |
|---|---|
| HEAD | `d678f098057bc1a590d4501c13e85f59830db2ac` |
| HEAD tree | `92d9ee964ea03d6ac15d9f743a4a9f62d7222f53` |
| Internal probe | `1.0.6` |
| Existing closure report | `sims-e1/evidence/TARGET_BINDING_CLOSURE_2026-09-29/report.md` |

The four previously identified 1.0.7 repair groups remain unchanged:

1. use a weak-reference-compatible alarm owner;
2. use `objects.ALL_HIDDEN_REASONS` for hidden-flag selection;
3. make the save-slot buffer read None-safe;
4. make the Sim queue/running-state reads None-safe.

This addendum evaluates whether a fifth repair group is required.

## A — Mechanical null-slot path

The proposed buffer repair makes `_save_snapshot()` return `slot_id=None`
when `get_save_slot_proto_buff()` returns `None`. The returned presence
row therefore still has a `save` mapping and can reach the current
post-poll branch.

`_session_open_from(row)` copies:

- `save["save_slot_guid"]` to `snapshot_guid`;
- `save["slot_id"]` to `snapshot_slot`;
- `body["sim_id"]` to `snapshot_sim`.

It also assigns those values to `_ARMED_SNAPSHOT` and constructs a
`session_open` mapping. `schema.make_record()` is a constructor and does
not validate the mapping. The validation boundary is
`TelemetryWriter.try_put()`, which calls `schema.validate_record()` and
converts a `SchemaError` into a dropped write (`False`).

The current poll tick invokes `_session_open_from(row)` after the
`observers.poll_once()` exception boundary. With `snapshot_slot=None`, the
closed-schema check for `session_open` rejects the row with
`SchemaError("session_open snapshot")`. No bounded `guard_exhausted` row is
created by this current path, and the partial `_ARMED_SNAPSHOT` assignment
occurs before the writer rejection.

Therefore the requested classification is:

```text
NULL_SLOT_SESSION_OPEN_PATH = REJECTED_BY_SCHEMA
```

The rejection is at writer validation, not inside `schema.make_record()`.

## F — All required identity fields

The closed `session_open` schema requires all three fields to be non-null:

```text
attestation.snapshot_guid is not None
attestation.snapshot_slot is not None
attestation.snapshot_sim is not None
```

The same mechanical result applies to each missing value:

| Missing value | Result |
|---|---|
| `save_slot_guid=None` | `SchemaError("session_open snapshot")` at writer validation |
| `slot_id=None` | `SchemaError("session_open snapshot")` at writer validation |
| `sim_id=None` | `SchemaError("session_open snapshot")` at writer validation |

The current observer converts `sim_info.id` with `str(...)`; the repair must
not allow an underlying missing identity to be disguised as the literal
string `"None"`. The completeness gate must inspect or preserve the value
before that conversion, and the row must not be passed to
`_session_open_from()` unless the resulting triple is complete.

## B — Canonical V1.2a meaning

V1.2a §5.5 defines the first *successful* poll as the point at which the
read-only armed snapshot guid/slot/sim triple is populated. Only after that
population does the implementation emit `session_open`.

V1.2a §11.3 defines `session_open` as a record with a populated snapshot.
V1.2a §12.2 defines an attended session as beginning after arm, start, and
the first successful poll. “Successful” therefore means successful
observation of the required identity triple, not merely a poll that returned
a syntactically formed mapping.

The plan treats transient values as a possible missingness status in general,
but V1.2a §§14-E/G and §18.1 do not relax the non-null `session_open`
contract: the completion point requires the guid/slot/sim values to be
available and stable.

## C — Canonical behavior

The canonical choice is:

```text
FAIL CLOSED
```

Rationale:

1. `session_open` has a closed, non-null triple contract.
2. Substantive rows follow only after `session_open`.
3. V1.2a §12.2 defines no pending-session-open state, timeout, or zero-byte-session
   semantics that would make deferred emission a valid independent state.
4. A null-identity `session_open` would directly contradict the closed
   schema.

Thus a poll with any missing guid, slot, or sim identity is not a successful
first poll. It must not open the session or emit a substantive presence row.

## D — Smallest source seam

The smallest seam is immediately after `observers.poll_once(...)` returns and
before `_session_open_from(row)` is called in `_poll_tick_body()`.

At that seam, inspect the complete triple:

```text
row["save"]["save_slot_guid"]
row["save"]["slot_id"]
row["body"]["sim_id"]
```

If any value is unavailable, route through the existing bounded failure
mechanism:

1. emit one valid `guard_exhausted` row with a bounded observation-failure
   reason;
2. call the existing `_cmd_stop()` path;
3. leave `_SESSION_OPENED` false and do not call `_session_open_from(row)`;
4. require the existing retry/re-arm sequence.

The exact reason token is not prescribed by V1.2a. A bounded detail such as
`OBSERVATION_FAILURE:SESSION_OPEN_IDENTITY_INCOMPLETE:<field>` is an
implementation label, not a new event kind or product semantic. The existing
`guard_exhausted` schema is physically writable with a non-null reason.

This seam also prevents partial `_ARMED_SNAPSHOT` state from being assigned
by `_session_open_from()` for an incomplete identity.

## E — Why defer is not canonical here

Deferring `session_open` would require an explicit pending state, a bounded
retry/timeout rule, and a defined handling for polls that have no substantive
rows. Those semantics are not present in V1.2a. Adding them would invent a
new lifecycle contract and could create an ambiguous zero-byte session.

V1.2a §14-E/G instead supplies the existing fail-closed guard/stop behavior
for a required getter that cannot produce a valid value. Therefore option 2
is not the canonical interpretation for this contract.

## Consolidated 1.0.7 repair delta

Add a fifth repair group to the existing four-item set:

```text
Before session-open construction, require a complete
(save_slot_guid, slot_id, sim_id) triple. Preserve missingness rather than
coercing it into a usable-looking string. On any missing value, emit one
schema-valid bounded guard_exhausted observation-failure row, stop through
the existing _cmd_stop() path, and leave session unopened. Do not relax the
closed schema, emit session_open with null identity, or introduce deferred
session-open state.
```

No source or test change was made by this addendum. Existing focused tests
cover valid first-poll binding and the closed schema, but do not currently
exercise the production `TelemetryWriter.try_put()` rejection for a null
session-open identity. The prior focused run remains 69 tests passing; it was
not rerun for this read-only addendum.

## Boundary result

```text
source changed? NO
tests changed? NO
artifact built? NO
Sims launched? NO
Sims command? NO
install/uninstall? NO
E1-A/B/G? NO
E2? NO
power action? NO
```

SIMS4_E1_SESSION_OPEN_IDENTITY_CLOSURE: COMPLETE
