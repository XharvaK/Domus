AUTONOMY_OFF = FAILED (UI Off and selected-Sim disable applied; non-idle autonomy later occurred during interruption)
CHAIR = DESIGNATED 118245043789434055
L1_SAVE_OBSERVED = PASS
N5 = PASS (OWNER_DIRECT; declared Stand deviation)
GATE_P = PASS (telemetry; no visible console response)

Operator: operator agent on the Owner's behalf.
One menu Save was clicked at epoch 1790789706653. SAVE_OBSERVED at 1790789707550: guid 2773024768, slot 2, sim 118245043779534861, ticks 1286977, loaded_from_slot_id 2. CLASSIFIED CONTINUES_LAST_SAVE.
Chair Sit clicked 1790789754830. PIE_MENU affordance 31564 interaction 5620 target 118245043789434055 first observed 1790789755197. SIGNATURE_LEARNED detail sit at 1790789756218. 108 chair posture samples from 1790789756217 to 1790789865765, 109.548 seconds.
DECLARED DEVIATION: chair/Sim menus did not offer Stand. No substitute interaction selected from those menus. Authorized Go Here at 1790789865510 stood the Sim and moved it at least three tiles by visual observation. No coordinates available in telemetry. N5's standalone Stand action was not performed.
Prepare submitted once at 1790789935605. Console output verbatim: no visible response text (see prepare_output.png). Telemetry PREPARE_OK token 5f3be50a1fc84c0b and DESIGNATED_BODY at 1790789935768. No ashley_e2.sit typed. No retries.
Post-prepare samples span 319.547 seconds: zero PUSHED/CLAIM, SCRIPT_WITH_USER_INTENT entries, or chair posture returns. Zero guard/exception rows. Initial 60-second autonomy observation had passive idle only. Later toilet-use-sitting 14427, Toilet_Use_Action 40413, toilet-flush 14426 target 118245043789434022 and sink_washHands 14241 target 118245043789434023 occurred during physical-Escape interruption, epochs 1790790144004 through 1790790170575. Not clicked by operator; not cancelled while Computer Use was stopped. On Owner continue, Sim was standing idle; no current non-idle activity to cancel.
Options.ini after: autonomydisabledforactivesim = 1; autonomyhousehold = 1. Gameplay UI initially and at apply displayed Off. Do not equate this with verified complete autonomy suppression.
Owner continue: reobserved pending ashley_e1.stop text, submitted Return once, closed console via Ctrl+Shift+C, clicked pause. No disarm or exit. HANDOFF_STATE=ARMED_STOPPED_PAUSED, supported by action history, ceased telemetry and handoff.png; stop has no visible response or stop checkpoint.
Snapshot copy 2026-09-30T20:46:34.3269869+03:00: 697 rows, 1278606 bytes, sequences 0..696, no gaps. All-row monotonic regressions 11 due to mixed event ordering; presence-only regressions 0. Bootstrap Python 3.7.0, perf_counter true, 21 required imports true. Session remains open and snapshot ends before pause because sampling was stopped.
15 save paths before, 16 after; Slot_00000002.save.ver4 was added by permitted backup rotation, no paths removed. Six content changes: Slot_00000002.save and .ver0 through .ver4 only. No outside-LAB content changes. No second save, Save-As, object edits or trial push. Analysis JSON and raw inventories retained.
