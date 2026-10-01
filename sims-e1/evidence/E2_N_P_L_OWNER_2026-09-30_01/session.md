# E2 negative controls, pause qualification and lineage trial (2026-09-30, evening)

Probe 2.0.1 (artifact `C2993BDC…3FE1`, J104), Sims PC 1.128.90.1030, LAB_E1 → LAB_E2_FORK.
Recorded and adjudicated by the architect (Claude/Opus) from the raw telemetry in this folder, under the Owner's full-authorization direction.

## Who acted

- 21:04–21:15: **operator agent on the Owner's behalf** (ChatGPT desktop Codex, J113), N1, N2 and a first N3 attempt. The operator session then died.
- From 21:17: **the Owner's own hand**, guided step by step by the architect. Tokens for `sit` were copied to the Owner's clipboard by an architect-run watcher reading `PREPARE_OK` from telemetry (the probe's console replies aren't visible on screen; see Findings).
- Every result below is taken from telemetry, not from what anyone saw on screen.

## Files

| File | What |
|---|---|
| `ashley_e1_863ffab5-….jsonl` | armed session from J111b through E2-P and L1b; closed `DISARM_CLEAN` at 21:43:18 (complete; earlier folders hold snapshots of it) |
| `ashley_e1_0d15935a-….jsonl` | L2 reload session + the L3 unsaved-play segment; closed `DISARM_CLEAN` 21:48:47 |
| `ashley_e1_1437e3d1-….jsonl` | L3 reload session + the L4 Save-As; closed `DISARM_CLEAN` |
| `ashley_e1_f12538bb-….jsonl` | L4 fork-load session; closed `DISARM_CLEAN` 21:52:46 |
| `ashley_e2_lineage_ledger.jsonl` | the lineage ledger after the session |
| `saves_after.txt` | save-folder inventory (name, length, mtime, SHA256) after the game exited |

## N1–N4 (plan §8.4): all PASS, no push

| Control | Time | Actor | Telemetry | Verdict |
|---|---|---|---|---|
| N1 nonexistent id `99999999999` | 21:05:26 | operator agent | `PREPARE_REJECT NO_OBJECT` | PASS |
| N1 non-seat `118245043789434035` | 21:06:01 | operator agent | `PREPARE_REJECT AFFORDANCE_NOT_OFFERED` | PASS |
| N1 excluded E1 sofa `118245043789434044` | 21:06:35 | operator agent | `PREPARE_REJECT OBJECT_EXCLUDED` | PASS |
| N2 stale token | 21:07:12 → 21:08:41 (89 s) | operator agent | `ADMIT_REJECT TOKEN_EXPIRED` | PASS |
| N3 attempt 1 | 21:11:26 → 21:13:03 | operator agent | `TOKEN_EXPIRED` (the operator was too slow) | not a result |
| N3 attempt 2 | 21:22:52 → 21:23:08 | Owner | the Owner sat the Sim on the **neighbouring** chair `…057`; `ADMIT_REJECT STALE_SNAPSHOT` (detail `BODY_BUSY`) | valid rejection, wrong chair; not counted |
| **N3** | 21:26:58 → 21:27:06 | Owner | Owner-side Sit on the designated chair `…055` after prepare; `ADMIT_REJECT STALE_SNAPSHOT` (detail `PRECONDITION_PRESENT`) | **PASS** |
| **N4** replay of the N3 token | 21:28:00 | Owner | `ADMIT_REJECT REPLAY_REJECTED` | **PASS** |

From J113's start to the end of N4: 0 `PUSHED`/`CLAIM` rows, and 0 `SCRIPT_WITH_USER_INTENT` entries on the body.

## E2-P (plan §7): P1, P2, P5, P6 PASS; P3, P4 answered

| Q | Evidence | Answer |
|---|---|---|
| P1 | `REQUEST_PUSHED` 21:30:45.272; next row `PAUSED`, ticks frozen at 4596197 for 36 s | PASS |
| P2 | `REQUEST_REMOVED` 21:31:41.271, then `NORMAL`; ticks 4596606 → 4621123 in 24.5 s (~1000/s, the E1-B rate) | PASS |
| P3 | pause 21:32:48 → Owner pressed 1× at 21:32:56 → `NORMAL`, running while the probe request was still live; `REQUEST_REMOVED` at 21:33:47 changed nothing | **the Owner's UI wins** over the probe's pause request |
| P4 | during an Owner-ordered nap the game entered native `SUPER_SPEED3` (~36,000 ticks/s); probe pause 21:36:33.5 → `PAUSED`, ticks frozen at 5075955 for 13 s; release 21:36:47.2 → back to `SUPER_SPEED3` (not NORMAL) | **the probe pause overrides the native fast-forward while live; release restores the game's own request** |
| P5 | pause 21:34:24, then `ashley_e1.stop` → `speed_event RELEASED_ON_DISARM` (detail `STOP`) 21:34:32; the game ran unsampled (ticks 4751230 → 4769996 at restart) | PASS |
| P6 | save hashes after E2-P identical to the post-J111b inventory (16 files) | PASS |

## E2-L (plan §9, A1, A9): L1–L4 PASS, ε = 0

| Step | Evidence | Verdict |
|---|---|---|
| L1 | J111b bootstrap save: `SAVE_OBSERVED` slot 2 ticks 1286977 → `CONTINUES_LAST_SAVE` (evidence `…_02`); **L1b** 21:39:51: `SAVE_OBSERVED` slot 2 ticks **S1 = 5331484**, loaded_from 2 → `CONTINUES_LAST_SAVE` | PASS |
| L2 | stop, disarm, load LAB_E1: `LOAD_OBSERVED` ticks 5331484 → `CLASSIFIED CONTINUES_LAST_SAVE`; **ε = \|T − S1\| = 0** | PASS |
| L3 | 77 s of unsaved play (session `0d15935a`, ticks 5352401 → 5427978), reload: `CLASSIFIED CONTINUES_LAST_SAVE` at 5331484, so those rows are an **abandoned branch** | PASS |
| L4 | Save-As `LAB_E2_FORK` 21:50:20: `SAVE_OBSERVED` **slot 5**, ticks 5561482, loaded_from 2, same guid; load fork + `arm lab_e1_fork`: `CLASSIFIED FORK` slot 5 ticks 5561482 | PASS |
| L5 | skipped by the Owner (plan header) | NOT_EXERCISED |

The arm label `LAB_E1_FORK` was used for the save named `LAB_E2_FORK`, because the arm vocabulary is closed (declared).

## Saves

Compared with the post-J111b inventory: `Slot_00000002.save` and its `.ver0–4` rotation changed (the L1b Owner save; the game's own rotation). `Slot_00000005.save` is new (the L4 Owner Save-As). Every other file (slots 3, 4, `ffffffff` and their versions, `steam_autocloud.vdf`) is byte-identical. **Saves changed only by Owner saves.**

## Findings

1. **Zone change while sampling (exercised live, unplanned).** During L3 the Owner opened the menu and loaded LAB_E1 before `stop`/`disarm`. The session file ends at 21:45:19 (the last row shows `paused` from the menu), with no close record. After the reload `arm` was refused (the state was still SAMPLING), and `start` counted as redundant. A later `stop` + `disarm` at 21:48:45–47 wrote `PRE_DISARM` + `session_close DISARM_CLEAN` with zero drops, and a fresh `arm`/`start` then worked. No data loss and no fabrication. E1 had covered this path only in unit tests.
2. **Console replies invisible.** `sims4.commands.output` text from the probe isn't shown on screen (also J111b). Outcomes are fully in telemetry. Cosmetic; worth a later fix.
3. **E2 event attestation.** `lineage_event` rows carry `attestation.armed_name = UNARMED` even while the session is armed (e.g. the L4 `CLASSIFIED FORK` row under an armed `LAB_E1_FORK` session). A telemetry-truth nit for a later build.
4. **`speed_event` phase naming.** The STOP fail-safe release is reported as `RELEASED_ON_DISARM` with detail `STOP`. The name is inexact; the detail is correct.
5. **Autonomy leaks.** With household autonomy Off and selected-Sim autonomy disabled in the UI, the Sim still autonomously went to sleep, cooked, and sat on the sofa. That doesn't affect N/P/L. For T trials it can only produce `OUTCOME_UNKNOWN` (a recorded competing cause), never a false PASS.
