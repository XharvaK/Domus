# Sims 4 Embodiment first-load acceptance

Evidence ID: `E1_ACCEPTANCE_2026-09-29_01`

## Terminal verdict

`FIRST_LOAD_ACCEPTANCE = BLOCKED`

Exact blocker:

`INSTRUMENTATION_FAILURE — required-import availability summary is absent from the new bootstrap load_disabled row. The row runtime keys are only python_version and perf_counter.`

The governing acceptance contract requires the bootstrap/import/runtime facts to include the required-import availability summary. The raw row is preserved locally. No arm/start command, scheduler trial, or later acceptance step was run after this blocker.

## INSTALL

- Root: `C:\Users\Xharv\OneDrive\Belgeler\Electronic Arts\The Sims 4`
- Destination: `C:\Users\Xharv\OneDrive\Belgeler\Electronic Arts\The Sims 4\Mods\AshleyE1\ashley_e1_1.0.0.ts4script`
- Artifact SHA256: `2B78CB40303A0228578BA1205FB6526A026F04B3F466B77A2EE4B4E40B8AA3E3`
- Duplicate Ashley E1 package count: `1`
- Install manifest: `install_manifest.json`
- Backup: `AshleyE1E1Backup_20260929050256`
- Cache cleanup: `localthumbcache.package` removed by installer; it was recreated during ordinary Sims setup before the pre-acceptance baseline.

## LAB

- Status: newly created.
- Save name: `LAB_E1`.
- Owner reported exactly one Sim in the household.
- Sims was fully quit before the pre-acceptance snapshot.

## ACCEPTANCE A-M

| Item | Status | Evidence |
|---|---|---|
| A | PASS | OWNER_ATTESTED: `PC 1.128.90.1030` |
| B | PASS | LIVE bootstrap: Python `3.7.0`; `perf_counter=true` |
| C | FAIL | LIVE bootstrap missing required-import availability summary; see `bootstrap_validation.json` |
| D | BLOCKED_BY_C | Not run |
| E | BLOCKED_BY_C | Not run |
| F | BLOCKED_BY_C | Not run |
| G | BLOCKED_BY_C | Not run |
| H | BLOCKED_BY_C | Only pre-acceptance snapshot exists; no acceptance interval was run |
| I | BLOCKED_BY_C | No probe commands executed |
| J | BLOCKED_BY_C | No state-machine exercise executed |
| K | BLOCKED_BY_C | Build verification was copied; live acceptance not run |
| L | BLOCKED_BY_C | No live acceptance interval |
| M | FAIL | LIVE bootstrap/root witness found, but required-import summary contract is incomplete |

## RUNTIME

- Sims build: `PC 1.128.90.1030`.
- Embedded Python self-report: `3.7.0`.
- Bootstrap found: yes; one new row within the acceptance window.
- Bootstrap path: `ashley_e1_bootstrap_0eae2882-c49b-4231-bde7-f42b02e7093b.jsonl`.
- Bootstrap SHA256: `E4EA640013E81EDE1F057B84A360DF6F8B05D3790AD05FA342EB15004139F3EB`.
- Root derivation: structurally verified to the exact Owner root.
- Required imports: not evidenced in bootstrap; acceptance stopped.
- Scheduler callbacks: not run.
- Pause continuity: not run.
- Post-stop callbacks: not run.
- Selectability result/type: not run.
- Body cardinality telemetry: not run.
- `session_open` ordering: not run.
- Critical drops: not run.
- Clock drops: not run.
- Writer state: not run.

## IMMUTABILITY

- Pre-acceptance save hashes captured in `pre_save_hashes.json`.
- Post-acceptance hashes were not taken because the acceptance interval never began after the load-bearing bootstrap blocker.
- The narrow wording `no persisted save-file change detected` is therefore not claimed for this blocked pass.

## BOUNDARY

- E1-A run? NO
- E1-B run? NO
- E1-G run? NO
- E2 touched? NO
- Product source modified? NO
- Artifact modified or rebuilt? NO
- Synthetic input used? NO
- Shutdown scheduled? NO
- Windows remains running.

## EVIDENCE

- Bundle: `sims-e1/evidence/E1_ACCEPTANCE_2026-09-29_01/`
- Raw bootstrap hash: `bootstrap_validation.json`
- Raw JSONL copy: `ashley_e1_bootstrap_0eae2882-c49b-4231-bde7-f42b02e7093b.jsonl`
- Acceptance report: `acceptance.md`
- Pre-acceptance save hashes: `pre_save_hashes.json`
- Build manifest: `manifest.json`
- Install manifest: `install_manifest.json`
- Build verification: `verify.log`
