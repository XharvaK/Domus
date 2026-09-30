# E1 Acceptance 2026-09-29_07 — ARM gate

The Owner entered the canonical arm command after the fresh bootstrap gate.

```text
ashley_e1.arm LAB_E1
```

## Observed state

- Sims process: running
- fresh session file: `ashley_e1_e08c49af-f0d4-4cd0-86f6-cfc45bd84aa8.jsonl`
- session UUID: `e08c49af-f0d4-4cd0-86f6-cfc45bd84aa8`
- file size before start: `0` bytes
- file state: open/locked by the running game process
- telemetry rows before start: none
- `session_open` before start: none
- sampling rows before start: none
- start command: not yet entered

The zero-byte locked file is the expected writer-open state before the first
sampling callback. Its hash is intentionally deferred until the game closes
the file.
