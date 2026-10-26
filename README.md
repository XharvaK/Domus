# Domus

**Give your agent a home.**

Domus is the embodiment project for [Ashley](https://github.com/XharvaK/Ashley):
it gives her a body and a home in The Sims 4, in stages E0–E7. It is a work in
progress, not production-ready, and not a general-purpose mod.

## Frozen constraints

- **One world, one Ashley.** The Sim is Ashley's body, not a second Ashley.
- **Engine script only.** Actions go through the game's own scripting; never
  keyboard or mouse emulation.
- **Truth and attribution first.** Every observation says where it came from;
  what the Owner did, what the game did on its own, and what Ashley asked for
  are never confused.
- **E1 is observe-only.** Actuation begins at E2, and only on the Owner's
  command.

## Where it stands

Stage status is recorded in the evidence and the plans, not on this page:
E1 (observe-only probe) is accepted by evidence in
[`sims-e1/evidence/E1_ADJUDICATION_2026-09-29.md`](sims-e1/evidence/E1_ADJUDICATION_2026-09-29.md);
E2 (Owner-commanded actuation) is implemented in the probe and awaits its
first-load gate and trials, run on the Owner's Windows PC with the game.

## Layout

| Path | What |
|---|---|
| [`sims-e1/`](sims-e1/README.md) | The in-game probe (Python for the game's CPython 3.7 runtime): source, tests, build/verify/install tools, and runtime evidence |
| [`docs/`](docs/) | Governing design and stage plans |
| [`docs/superseded/`](docs/superseded/) | Earlier drafts, kept for provenance only |

## Governing documents

| Document | Role |
|---|---|
| [`PROJECT_ASHLEY_SIMS4_EMBODIMENT_DESIGN_V7_3_2a.md`](docs/PROJECT_ASHLEY_SIMS4_EMBODIMENT_DESIGN_V7_3_2a.md) | Master design: laws, programme E0–E7, open-item ledger |
| [`PROJECT_ASHLEY_SIMS4_EMBODIMENT_E2_IMPLEMENTATION_READY_PLAN_V1.md`](docs/PROJECT_ASHLEY_SIMS4_EMBODIMENT_E2_IMPLEMENTATION_READY_PLAN_V1.md) | Current stage plan: E2 actuation experiment (Owner-accepted) |
| [`PROJECT_ASHLEY_SIMS4_EMBODIMENT_E0_E1_IMPLEMENTATION_READY_PLAN_V1_2a.md`](docs/PROJECT_ASHLEY_SIMS4_EMBODIMENT_E0_E1_IMPLEMENTATION_READY_PLAN_V1_2a.md) | E0/E1 plan; E1 is complete, and E0 is the Owner's to redo |

Supporting: [`PROJECT_ASHLEY_SIMS4_E1_PRE_IMPLEMENTATION_SOURCE_RESOLUTION_V1_2.md`](docs/PROJECT_ASHLEY_SIMS4_E1_PRE_IMPLEMENTATION_SOURCE_RESOLUTION_V1_2.md)
(source evidence for E1).

## Owner decisions recorded 2026-09-29

- Sims cognition uses a **separate embodiment budget** with its own fuse,
  active only while a session is armed (master §9, §20 E3-B1; Ashley's Growth
  V1 plan §5.6, §5.7).
- Reasoning effort for in-world decisions is chosen from the CA-03 benchmark,
  not in advance.
- Domus runtime work (E2 gate and trials) runs on the Owner's Windows dev PC.

## Relation to Ashley

Ashley's cognition stays in the Ashley repository; its embodiment seam (G6)
is reserved there until the stage gates are met. Domus holds the game side:
the probe, its evidence, and the embodiment design. The probe, design drafts
and E1 evidence moved here from the Ashley repository on 2026-09-30; their
earlier history is in that repository.

## Verifying the probe

From PowerShell on the dev PC, with the pinned CPython 3.7 toolchain:

```powershell
powershell -ExecutionPolicy Bypass -File sims-e1\tools\verify.ps1
```

`build.ps1` produces `Domus_<version>.ts4script` into `sims-e1/build/` (not tracked);
`install.ps1 -SimsRoot <The Sims 4 user folder>` installs it with the game
closed.
