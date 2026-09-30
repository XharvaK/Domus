# E1 First-Load Acceptance — 2026-09-29 Retry

## Candidate

- Internal probe: `1.0.2`
- Artifact SHA256: `C73AFC3B7AC8FCE547B507491E0918DBEB21F583BAE21D07BFB213D7C6398F98`
- Repository HEAD: `64341679db058ed81cf10f99f619325f26507923`
- Product-facing name: `Embodiment 1.0.0`
- LAB: existing `LAB_E1` reused

## Fresh dispositions

| Gate | Disposition | Evidence |
|---|---|---|
| A | PASS | `A_main_menu_mods.md`; build `PC 1.128.90.1030`, one entry, version `1.0.2` |
| B | PASS | `B_C_M_bootstrap.md`; Python `3.7.0`, `perf_counter=true` |
| C | PASS | `B_C_M_bootstrap.md`; 19/19 required keys, exact Boolean `true` |
| M | PASS | `B_C_M_bootstrap.md`; fresh `load_disabled`, `UNARMED`, structural root |
| H | BLOCKED | `save_hash_delta_pre_arm.md` |

D–L were not executed after the load-bearing H failure. No probe command was
entered. E1-A, E1-B, E1-G, and E2 were not run.

## Boundary

- Historical `E1_ACCEPTANCE_2026-09-29_01` evidence was not modified.
- No source files were changed.
- No synthetic input was used.
- No Owner Save was reported during the acceptance interval.
- Windows remains running.
