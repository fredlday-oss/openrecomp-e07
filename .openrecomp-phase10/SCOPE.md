# OpenRecomp Phase 10 Scope

## Mission

Advance Disney's Hercules (`SLUS_005.29`) from the frozen Phase-9 private
frontier into deterministic native execution through the existing OpenRecomp
architecture, reusing:

```
PS-X EXE ingestion
  -> PS1 image/memory contract
  -> existing MIPS32 decode/semantics
  -> shared ProgramModel / CFG / function recovery / call graph / TUs
  -> architecture-neutral translation
  -> existing host emitter
  -> generic runtime ABI
  -> Phase-9 PS1 BIOS/GPU/input/timer/event/SPU/CD boundaries
  -> native build
  -> deterministic execution
  -> progressively stronger game milestones
```

No second PS1 frontend, MIPS decoder, CFG pipeline, host emitter or parallel
runtime architecture is created. Shared components are extended only where
direct Phase-10 evidence demonstrates a real gap.

## Starting frontier

Phase 9 established, and P10-00 reproduces:

- 4068 reachable words;
- first unresolved blocker: `break` at `0x80013390`;
- structural failure: `CONTROL_WITHOUT_DELAY_SLOT`;
- BIOS discovery: 3 B0 candidates, 19 unknowns;
- discoverable static I/O-range accesses: 0;
- bounded execution: `NOT_ATTEMPTED_BLOCKED_BY_FIRST_UNRESOLVED`.

## Milestones

Milestones are distinct and must never be conflated:

| Milestone | Meaning |
|---|---|
| A | translated native execution begins |
| B | game initialization completes |
| C | GPU command stream reached |
| D | first valid rendered frame |
| E | title/logo screen |
| F | menu reached |
| G | controllable gameplay |

Only milestone G may support `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=PASS`,
and only with deterministic scripted-input evidence of actual game-state
progression.

## Claims

Until terminal evidence proves otherwise:

- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN`
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

General PS1 compatibility remains permanently `NOT_PROVEN`. Native execution
does not prove playability.

## Out of scope

- full PS1 hardware emulation, cycle accuracy, PS2, cross-platform playability;
- BIOS emulation or BIOS image use;
- complete GPU/DMA/SPU/CD-ROM device emulation beyond reachable requirement;
- any workload other than the audited bounded fixtures;
- redistribution of the private commercial fixture.
