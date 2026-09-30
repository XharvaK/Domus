# Corrected Attempt — Valid Arm Dispatch Failure

After the corrected clean pre-command save gate and the expected rejected
unarmed `ashley_e1.start` and rejected `ashley_e1.arm BADNAME`, the Owner
entered exactly:

```text
ashley_e1.arm LAB_E1
```

The Owner reported no visible result. Immediate filesystem inspection at
`2026-09-29T04:19:23.8942761Z` found:

- six bootstrap JSONL files total, including the fresh 1.0.3 bootstrap;
- zero non-bootstrap telemetry/session files;
- no `session_open` row;
- no session UUID evidence;
- no writer/session JSONL;
- no alarm evidence;
- corrected save baseline unchanged;
- no extra save files.

The required `_cmd_arm()` mechanical witness is absent. `ashley_e1.start`
was not entered after this failure.
