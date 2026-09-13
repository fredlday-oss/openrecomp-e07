# OpenRecomp Phase 2 Scope

Final objective:

`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`

## Required pipeline

guest input
→ validated ingestion
→ decoded instructions
→ recovered blocks/functions
→ explicit CFG
→ persistent program representation
→ architecture-neutral IR / translation units
→ generated host source/object
→ generic runtime ABI
→ executable host program
→ deterministic observable-state comparison

## Primary architecture

MIPS32 / PS2-oriented path.

## Secondary architecture

NES6502 / NES, used to prove shared Phase-2 layers are not MIPS-specific.

## Generic runtime V1

Architecture-neutral contracts for guest memory, CPU-state ownership, deterministic ticks/time, deterministic RNG hook where required, input, frame/presentation submission, audio submission, logging, controlled host-call dispatch, resource/file stubs for synthetic/open fixtures, and shutdown/result reporting.

Platform-specific behavior remains outside the generic runtime contract.

## Out of scope

Broad commercial compatibility; arbitrary self-modifying code; full PS2 GS/SPU2/VU emulation; cycle-perfect legacy-console emulation; RT64 as mandatory dependency; PSP/PS1/SNES/Mega Drive production support; copyrighted asset extraction; optimization before correctness.
