# D11: fix the automatic inbox start (probe 2.2.1) using several import-time hooks, plus the ZONE/CONSOLE split and the tick `except`

From: Architect. To: Manager → Operator (Codex Sol light). Date: 2026-10-01. Results: continue `outbox\D11_RESULTS.md`.
**Base:** domus-next **da68647**. **Branch:** `d11-autostart`.
**A bugfix to the falsified C3b**, so under the Owner rule there's **no separate review run**. The XQX pinned gate (J118) is the check.

**Install and live check:** combined with the **D12 live run** (one Owner session, one install).

## Why

- **Live fact:** at ts4script import, `services.get_zone_manager()` is None.
- **R-Z2 (PARTIAL)** found module-level registries that exist at import. None of them is proven for 1.128.
- So D11 registers **several cheap, idempotent, injection-free hooks**, each of which tries the same arming step. The live check records which one fired first. Nothing is patched or replaced.

## Build (`sims-e1/src/ashley_e1/probe.py`, plus the schema only if needed)

1. **`_try_arm_zone(source)`** is idempotent and never raises:
   - if `services.current_zone()` is not None and it has `register_callback`, register `z.register_callback(6, lambda: _start_inbox_pump(source))` **once per zone object**. Track it with a set of `id(z)` plus a weak reference if one is available; otherwise clear the set when the zone changes. **6 = ZoneState.RUNNING** (numeric literal with a comment, no `zone` import, no `sys.modules['zone']`);
   - if `services.get_zone_manager()` is not None, call `register_callback(0, _on_zone_added)` **once per manager object**.
2. **Hooks registered at `initialize_probe`, each wrapped in try/except, each recorded in the bootstrap summary as registered or failed:**
   - **H-T (R-Z2 #1):** `services.get_instance_manager(sims4.resources.Types.SNIPPET).add_on_load_complete(lambda m: _try_arm_zone('tuning'))`. Confirm that `sims4.resources` falls under the approved `sims4` root.
   - **H-C:** `sims4.callback_utils.add_callbacks((CallbackEvent.POSTURE_GRAPH_BUILD_EXIT,), lambda *a, **k: _try_arm_zone('posture'))`, and the same for `HOUSEHOLD…EXIT` and `TRANSITION_SEQUENCE…EXIT` **if** those names exist in the enum (resolve them by attribute access inside try/except, **not** `getattr`). A firing after the zone is RUNNING arms and starts the pump at once (see 3).
   - **H-I:** the existing immediate attempt at import, `_try_arm_zone('import')`.
3. **`_start_inbox_pump(source)`:** the same idempotent start as now.
   - If it's called while the zone is already RUNNING (when `register_callback(6, …)` fires immediately), it starts at once.
   - It sets `inbox_autostart = "ZONE:<source>"`.
   - The console `ashley_e1.inbox` sets `"CONSOLE"` **only if** the pump isn't already running. If it is, the reply is `INBOX ON (already, <source>)`, and no second alarm is created.
4. **Closed values for `inbox_autostart`:** `NOT_STARTED`, `MANAGER_UNAVAILABLE`, `ZONE:import|tuning|posture|household|transition|manager`, `CONSOLE`.
   - **If** `schema.py` validates that field as a closed set, this is a schema change: bump to **v4**, per the rule that any change bumps the integer. Otherwise there's no bump. Say which applies.
5. **The tick `except` (D10e NOTE):** `_inbox_tick` catches `Exception` per file. It counts `inbox_errors` (shown in `status`), moves the file to `done` with an `ERROR` reply when possible, and **never** lets an exception reach the alarm callback.
6. **Version 2.2.1** at every site (`__init__`, schema `PROBE_VERSION`, build/verify/install/remove defaults, README) and an **A12 note row:** add "A12a: automatic start via import-time hooks (tuning load-complete / callback_utils / zone-manager), qualified live" after A12, byte-exact as written here.
7. **Guards:** `check_guards` passes unchanged. If `add_on_load_complete` or `add_callbacks` is flagged, STOP; don't weaken the guard.

## Tests (red-first at da68647, fakes only)

- Each hook calls `_try_arm_zone` with its source, and a failing registration is recorded without raising.
- Arming is idempotent per zone and per manager.
- A RUNNING callback that fires immediately starts the pump once.
- After an automatic start, the console gives `already` and no second alarm.
- The status and bootstrap show the closed values.
- The tick `except` behaves as specified: a raising writer increments `inbox_errors` and the tick returns normally.
- `test_portability` stays green. Run the full suite on 3.13 and on 3.14 via `uv`.

## Then

1. **J118 (XQX):** the pinned 3.7.0 gate on the D11 tip; 3 equal hashes; 0 fail.
2. **Don't install yet.** The 2.2.1 install happens at the start of the D12 live session (the J-job for that), once the D12 code is accepted.
