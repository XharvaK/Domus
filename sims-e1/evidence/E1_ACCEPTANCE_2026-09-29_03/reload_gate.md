# E1_ACCEPTANCE_2026-09-29_03 — Fresh Reload Gate

The Owner reported that the fresh Main Menu/mod-list state was as expected.
The existing `LAB_E1` save was reused. The new loader row proves this was a
fresh `1.0.2` load:

- File: `bootstrap_1.0.2_reload.jsonl`
- Source SHA256: `95C5DF7132A356001333E1854C9C77C2BB4BE9CBCA75860C80666B9594B57961`
- `probe_version`: `1.0.2`
- `event_kind`: `load_disabled`
- `attestation.armed_name`: `UNARMED`
- `telemetry_session_id`: `null`
- Python: `3.7.0`
- `perf_counter`: `true`
- Required imports: 19/19 canonical keys, exact Boolean values, all `true`

This fresh bootstrap is recorded for the retry. It does not carry forward the
prior run's A/B/C/M dispositions.
