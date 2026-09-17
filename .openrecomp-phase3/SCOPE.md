# OpenRecomp Phase 3 Scope

Final objective (not yet proven):

`OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF`

## Phase-3 purpose

Phase 3 moves beyond tiny synthetic fixtures and proves that the Phase-2
architecture works on a substantial compiler-produced MIPS32 ELF.

Intended progression:

CoreMark source
-> reproducible MIPS32 ELF build
-> ELF ingestion
-> sections/data image
-> MIPS32 decoding
-> ProgramModel
-> CFG
-> function recovery
-> call graph
-> translation units
-> static data/global reconstruction
-> host emission
-> native host build
-> generic runtime
-> execution
-> independent MIPS32 reference execution
-> deterministic observable equivalence
-> reproducible package

## First substantial target

CoreMark, compiled from source to a legally clean MIPS32 ELF.

- The source must come from its authoritative open-source tree (EEMBC
  `eembc/coremark`) with recorded repository identity, revision/commit,
  license and exact source hashes.
- Do not use an unknown downloaded precompiled MIPS binary.
- Target characteristics: ELF32, MIPS, little-endian, MIPS32 ISA, O32 ABI,
  statically linked or freestanding, no dynamic linker, soft-float initially,
  non-PIC where practical, deterministic benchmark inputs.
- Initial optimisation target is `-O1`. Do not begin with `-O2`; an
  independently built `-O2` version is a later stress target only after the
  `-O1` end-to-end path passes.
- Symbols may be retained for evidence/reference, but OpenRecomp correctness
  must not depend on symbols unless a stage explicitly classifies that
  dependence.

## Phase-3 goal

A substantial, legally clean, compiler-produced MIPS32 program can be
statically recompiled to a native host executable with independently verified
deterministic observable equivalence.

## Claim boundary

Phase 2 remains the proven bounded end-to-end framework result. Phase 3 must
not initially claim:

- arbitrary MIPS32 ELF support,
- PS1 compatibility,
- PS2 compatibility,
- game compatibility,
- commercial binary compatibility.

## Out of scope

Broad commercial compatibility; arbitrary self-modifying code; console
hardware emulation; cycle accuracy; copyrighted asset extraction; optimisation
before correctness.
