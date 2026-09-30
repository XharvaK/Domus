# E1 First-Load Acceptance — 2026-09-29 Retry 03

## Candidate

- Internal probe: `1.0.2`
- Artifact SHA256: `C73AFC3B7AC8FCE547B507491E0918DBEB21F583BAE21D07BFB213D7C6398F98`
- Repository HEAD: `64341679db058ed81cf10f99f619325f26507923`
- Existing LAB: `LAB_E1`
- Autosave setup: Owner-attested all four triggers `OFF`

## Fresh dispositions

| Gate | Disposition | Evidence |
|---|---|---|
| A | OWNER-REPORTED EXPECTED | `reload_gate.md`; exact menu transcription was not repeated in the report |
| B | PASS | `reload_gate.md`; Python `3.7.0`, `perf_counter=true` |
| C | PASS | `reload_gate.md`; 19/19 required keys, exact Boolean `true` |
| M | PASS | `reload_gate.md`; fresh `load_disabled`, `UNARMED`, structural root |
| H | BLOCKED | `save_hash_delta_reload.md` |

D–L were not executed after the repeated save delta. No probe command was
entered. E1-A, E1-B, E1-G, and E2 were not run.

## Boundary

- `1.0.2` remains installed as the sole Ashley package.
- No source change, rebuild, or reinstall occurred.
- Historical `E1_ACCEPTANCE_2026-09-29_01` and blocked retry `02` evidence were
  not modified.
- No synthetic input was used.
- Windows remains running.
