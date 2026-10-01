# J111 STOP evidence

OPERATOR=operator agent on the Owner's behalf
CHAIR = STOP (at least two single-seat dining chairs visible at the table on initial LAB_E1 lot view; multiple_chairs.png)
CHAIR_OBJECT_ID=NOT_RUN (no designation permitted after STOP)
SIGNATURE_POSTURE_NAME=NOT_RUN
L1_SAVE_OBSERVED = NOT_RUN (multiple-chair STOP before arm/save)
N5 = NOT_RUN (multiple-chair STOP)
GATE_P = NOT_RUN (multiple-chair STOP)
SAVE_TICKS=NOT_RUN
LIVE_CLASS_AFTER_SAVE=NOT_RUN
PREPARE_OUTPUT=NOT_RUN
HANDOFF_STATE=CLOSED
SESSION_FILE=none (never armed; no new session file)

The operator launched The Sims 4 through Steam, observed Version 1.128.90.1030 DX11 and ashley_e1_2.0.1 in the Mods dialog, and loaded LAB_E1 (not LAB_E1_FORK). At least two dining chairs were visible before any arm or game-option change. The job's hard limit and STOP condition applied immediately. No Buy-mode placement, option change, game save, Sit/Stand action, or E2 command occurred. The Sim was seated watching TV at initial load, as in J110.

Closeout: ashley_e1.disarm was submitted once before the physical Escape interruption. The Owner said continue. The operator reobserved the game, opened the menu, selected Exit Game, then Exit Game in the Save Game? dialog. Save and Exit was not selected. TS4_x64 process absent at after-inventory capture 2026-09-30T20:20:30+03:00.

Saves: 15 paths, lengths and SHA256 values identical before/after. No persisted-content change. NOTE: steam_autocloud.vdf LastWriteTime changed from 2026-09-30T17:25:52.6634649+03:00 to 2026-09-30T20:12:33.3554143+03:00, with identical bytes, per standing R2. Full inventories and saves_diff.json retained.

Autonomy setting was not changed because the chair STOP was already visible. Before/after Options.ini: autonomydisabledforactivesim = 0; autonomyhousehold = 1. No autonomy_off.png exists because that action was not performed.

Bootstrap: ashley_e1_bootstrap_45f5465a-7834-42dd-b10e-6b99f74ee574.jsonl, one row, load_disabled UNARMED, schema 2, probe 2.0.1, build 1.128.90.1030, Python 3.7.0, perf_counter true, 21/21 imports true. Session count for this launch = 0. N5/P counts and timings are inapplicable because no session was armed or sampled. Ledger before/after content is identical; no new SAVE_OBSERVED or designation.

The exact J110 architect adjudication is included at ../E2_FIRST_LOAD_2026-09-30_01/ARCHITECT_ADJUDICATION.md. Its acceptance is attributable to the architect, not a rewrite of the original operator report.

Operational interruptions: Steam approval timeout retried after 30s; detected concurrent user input caused reobservations before inputs. A physical Escape stopped Computer Use; it resumed only after Owner's explicit continue. Initial direct screenshot write to Domus failed EPERM; the exact screenshot was preserved via temporary file and authorized copy. No input ran in that failed cell.

Verdict: J111 STOPPED. No trial or lineage bootstrap acceptance claimed. Architect must dispatch the next authorized job.
