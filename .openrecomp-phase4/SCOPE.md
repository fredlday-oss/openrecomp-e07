# OpenRecomp Phase 4 Scope

Final bounded objective (not yet proven):

`OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF`

## Phase-4 purpose

Turn the bounded Phase-3 CoreMark MIPS32 `-O1` real-ELF recompilation proof
into a reusable, architecture-neutral generic runtime / platform layer.

Phase 4 must remove fixture-specific assumptions from the execution boundary
and establish explicit reusable contracts for:

- generated-code <-> runtime interaction;
- guest memory;
- runtime services;
- deterministic I/O;
- timing;
- input/events;
- platform adapters;
- graphics/audio abstraction boundaries;
- an interactive legally clean fixture;
- end-to-end native execution through the generic runtime.

It must preserve OpenRecomp's existing architecture-neutral layers, must not
turn the core recompiler into a console-specific implementation, and must fail
closed wherever behavior is unresolved.

## Intended progression

fixture/input
-> ingestion
-> program recovery
-> translation
-> host emission
-> native build
-> generic runtime
-> platform adapter
-> deterministic execution

## Phase-4 goal (bounded)

The exact bounded generic-runtime/platform claim audited by the frozen Phase-4
queue is proven on the audited tree at P4-99:

- an explicit architecture-neutral generated-code <-> runtime ABI;
- an explicit guest memory/runtime model with fail-closed access semantics;
- typed, versioned runtime services with fail-closed unknown-service behavior;
- reusable bounded deterministic I/O, timing and input interfaces;
- a platform-adapter contract that does not contaminate the recompiler core;
- reusable graphics/audio adapter boundaries with no mandatory backend;
- a legally clean fixture materially more demanding than CoreMark;
- a first real platform-adapter execution proof and a bounded end-to-end
  generic-runtime native proof with independent reference verification,
  packaged reproducibly with whole-regression coherence.

## Claim boundary

Phase 4 must not claim and P4-99 must not silently imply:

- arbitrary binary compatibility;
- arbitrary MIPS32 compatibility;
- PS1 / PS2 / N64 / PSP / any console compatibility;
- game or commercial-title compatibility;
- cycle accuracy or hardware emulation;
- universal runtime completeness;
- integration with any particular renderer or audio backend (RT64, SDL,
  Vulkan, Direct3D or other) unless a future adapter explicitly proves it.

The bounded Phase-3 claim remains exactly as recorded by tag
`openrecomp-phase3-pass`; Phase 4 neither extends nor weakens it.

## Terminal markers

- `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF` — reserved until P4-99; each
  earlier stage records the value `NOT_PROVEN`. P4-99 may issue `PASS` only
  for the exact bounded claim above.
- `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN` — general
  console/commercial compatibility is out of scope and is never promoted by
  Phase 4.

## Out of scope

Console hardware emulation; cycle accuracy; copyrighted or console-derived
assets; proprietary SDK material; mandatory third-party renderer/audio
backends; performance claims; arbitrary self-modifying code.
