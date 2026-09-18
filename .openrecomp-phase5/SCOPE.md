# OpenRecomp Phase 5 Scope

Final bounded objective (not yet proven):

`OPENRECOMP_PHASE5_NES_PLATFORM_PROOF`

## Phase-5 purpose

Prove that the frozen Phase-4 generic runtime / platform architecture can
support a real second CPU architecture and console platform: the Nintendo
Entertainment System (Ricoh 2A03 / NMOS 6502-family CPU) through a static
recompilation path, not an emulator wrapper.

Phase 5 reuses the frozen architecture-neutral ProgramModel / CFG /
function-discovery / translation-unit / host-emission / runtime layers where
technically appropriate and keeps every NES-specific behaviour behind explicit
frontend / platform / runtime adapter boundaries that live under
`.openrecomp-phase5/`.

## Intended progression

legal public iNES fixture (original, Apache-2.0)
-> fail-closed iNES/NES 2.0 ingestion + inventory
-> 2A03/6502 decode + reachable frontier
-> CPU semantics proof (independent reference vectors)
-> ProgramModel / CFG / functions / translation units
-> bounded NES CPU memory map + mapper model
-> bounded PPU boundary / deterministic graphics model
-> APU / input / timing / interrupt boundary
-> host emission through the Phase-4 generic ABI
-> NES platform adapter binding the Phase-4 runtime contracts
-> deterministic native execution
-> independent NES reference equivalence
-> reproducible public package

The private local TMNT image is analysed only as an additional compatibility
target and never enters public artifacts.

## Phase-5 goal (bounded)

The exact bounded NES static-recompilation claim audited by the frozen
Phase-5 queue is proven on the audited tree at P5-99:

- fail-closed ingestion and full inventory of the selected iNES images;
- exact reachable/dead/unsupported opcode frontier for the public fixture;
- exact CPU semantics for every instruction required by the reachable public
  fixture path, differentially verified against an independently structured
  reference model;
- a neutral program structure (ProgramModel/CFG/functions/translation units)
  with explicit reset/NMI/IRQ roots and no fabricated boundaries or indirect
  targets;
- a bounded NES CPU memory map and the mapper behaviour required by the public
  fixture, with unknown mappings failing closed;
- a bounded PPU boundary sufficient for the public fixture, behind the Phase-4
  graphics boundary, with no full-PPU or cycle-accuracy claim;
- bounded controller input, NMI/vblank event delivery and frame timing, with
  APU access handled only as far as the fixture requires;
- deterministic native host code emitted for the proven NES CPU subset and
  connected through the Phase-4 runtime/platform adapter interfaces; the
  original 6502 guest program is never executed directly on the host;
- a native execution of the legally clean fixture with meaningful interactive
  behaviour across CPU + memory + input + timing + graphics/platform
  boundaries;
- independent reference equivalence over deterministic observables (CPU
  state, RAM digest, frame/state digest, controller transcript, interrupt
  counts, service transcript, bounded final state);
- a reproducible public package containing only redistributable artifacts;
- a private, non-redistributed TMNT compatibility observation with its exact
  mapper/hardware frontier and fail-closed blockers recorded.

## Claim boundary

A Phase-5 PASS must not claim and P5-99 must not silently imply:

- all NES games or all mappers work;
- cycle accuracy or full PPU accuracy;
- full APU accuracy or audio equivalence;
- commercial-game compatibility;
- Famicom Disk System compatibility;
- arbitrary 6502 binary compatibility;
- general NES compatibility beyond the audited public fixture.

## Terminal markers

- `OPENRECOMP_PHASE5_NES_PLATFORM_PROOF` - reserved until P5-99; every earlier
  stage records the value `NOT_PROVEN`. P5-99 may issue `PASS` only for the
  exact bounded claim above.
- `OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` - general NES /
  commercial compatibility is out of scope and is never promoted by Phase 5.

## Out of scope

Console hardware emulation; cycle accuracy; copyrighted or console-derived
assets; ROM redistribution of any kind; proprietary SDK material; mandatory
third-party renderer/audio backends; performance claims; arbitrary
self-modifying code; FDS images.
