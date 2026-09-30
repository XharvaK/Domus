# E1 Acceptance 2026-09-29_07 — Bootstrap gate

The Owner loaded `LAB_E1` and reported stable gameplay. No Ashley command was
entered before this inspection.

## Fresh bootstrap

- path: `C:\Users\Xharv\OneDrive\Belgeler\Electronic Arts\The Sims 4\AshleyE1Telemetry\ashley_e1_bootstrap_c8946558-988d-4fba-9fcd-23b71d0412e0.jsonl`
- SHA256: `9036DEC0F48835BF787E57AB6BAFE564C5F85C75A32588F8838501CFFBE11928`
- bytes: `1019`
- probe version: `1.0.7`
- Sims build: `1.128.90.1030`
- embedded Python: `3.7.0`
- `perf_counter`: `true`
- attested armed name: `UNARMED`
- telemetry root: present

Required-import gate:

- count: `19`
- missing keys: none
- extra keys: none
- non-Boolean-true values: none

The `load_disabled` row contains no save, body, world, zone, or interaction
content. Its attestation snapshot fields remain null as required before arm.

## Pre-arm save gate

- baseline inventory SHA256: `66D7BF89233B22CE69014B63E138673989B27357A8618BEB2F7AA1EF285DB052`
- stable-load inventory SHA256: `66D7BF89233B22CE69014B63E138673989B27357A8618BEB2F7AA1EF285DB052`
- file count: `12` before and after
- persisted saves unchanged: `true`

## State

- Sims running: `true`
- arm command: not entered
- start command: not entered
- telemetry session: none
- first-poll gate: pending
