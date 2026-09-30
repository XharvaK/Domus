# E1 First-Load Acceptance — Corrected Attempt Within Retry 04

| Gate | Disposition | Evidence |
|---|---|---|
| A | OWNER-REPORTED VERIFIED | `A_main_menu_mods.md` |
| B | PASS | `corrected_bootstrap_1.0.3.jsonl` |
| C | PASS | `corrected_bootstrap_1.0.3.jsonl`; 19/19 exact `true` |
| M | PASS | `corrected_bootstrap_1.0.3.jsonl`; fresh `load_disabled`, `UNARMED` |
| Unarmed `start` | PASS | corrected save gate remained clean; no session/writer evidence |
| `BADNAME` arm | PASS | corrected save gate remained clean; no session/writer evidence |
| Valid `LAB_E1` arm | BLOCKED | `corrected_command_dispatch_failure.md` |

The valid-arm witness required by the 1.0.3 acceptance did not appear. The
run stopped before `start` and before the canonical D–L sequence.
