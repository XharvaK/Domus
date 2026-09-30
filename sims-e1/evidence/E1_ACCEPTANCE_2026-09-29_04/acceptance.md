# E1 First-Load Acceptance — 2026-09-29 Retry 04

## Candidate

- Internal probe: `1.0.3`
- Artifact SHA256: `98C701FFAA2EAA2D5363F81D190FA400C2A4786DA25C061E6523807F852547B3`
- Repository HEAD: `2c1a3ea94a069a7d63176a43cf3bd84e06305e36`
- Existing LAB: `LAB_E1`
- Autosave setup: Owner-attested all four triggers `OFF`

## Fresh dispositions

| Gate | Disposition | Evidence |
|---|---|---|
| A | OWNER-REPORTED VERIFIED | `A_main_menu_mods.md` |
| B | PASS | `B_C_M_bootstrap.md`; Python `3.7.0`, `perf_counter=true` |
| C | PASS | `B_C_M_bootstrap.md`; 19/19 required keys, exact Boolean `true` |
| M | PASS | `B_C_M_bootstrap.md`; fresh `load_disabled`, `UNARMED`, structural root |
| Early unarmed start | PASS | `early_binding_unarmed_start.md`; rejected, no session/writer evidence |
| H | BLOCKED | `save_hash_delta_early_binding.md` |

`BADNAME` and valid `LAB_E1` arm were not entered. D–L were not executed.
The command-dispatch binding cannot be qualified from this run because the
required save gate failed before the decisive valid-arm witness.

## Boundary

- Historical `E1_ACCEPTANCE_2026-09-29_01`, `_02`, and `_03` evidence was not modified.
- No source change, rebuild, or second installation occurred during acceptance.
- No E1-A, E1-B, E1-G, E2, or synthetic input was used.
- Windows remains running.
