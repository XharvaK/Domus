# E1 Acceptance 2026-09-29_05 — Start Blocker

The Owner submitted the canonical production command `ashley_e1.start` twice
while LAB_E1 was confirmed unpaused. The bounded second submission was
allowed because repeated start is a canonical no-op when sampling is already
active.

Observed after the second submission at `2026-09-29T05:20:43.3887433Z`:

- Session UUID: `f4130399-d119-4db8-8e98-299d41be054e`
- Session file: `ashley_e1_f4130399-d119-4db8-8e98-299d41be054e.jsonl`
- File length: `0` bytes
- Shared-read SHA256: `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`
- File last-write time remained `2026-09-29T05:16:45.6859224Z`, the arm time
- JSONL row count: `0`
- `session_open`: absent
- First poll: absent
- Sampling telemetry: absent
- Alarm telemetry: absent
- Sims process count: `1`
- Sims exception/Ashley log hit: none observed

The saves comparison against `saves_baseline.json` found zero changed files.

## Finite blocker

The production `ashley_e1.start` path produced no first poll or
`session_open` witness after two submitted commands during confirmed unpaused
live gameplay. The A–M acceptance cannot proceed because the scheduler and
sampling witness are absent.

No source change, rebuild, reinstall, synthetic input, E1-A/B/G, E2, or power
action was performed after this blocker was observed.
