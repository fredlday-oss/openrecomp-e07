# P2-90 claim classification

| claim | classification | basis |
|---|---|---|
| MIPS32 shared-path operation | `BOUNDED_PROVEN` | synthetic 13/16/35/5/57-instruction fixtures; no general MIPS32 support |
| NES runtime bridge | `BOUNDED_PROVEN` | bounded synthetic NROM fixture; memory/input/frame/audio contracts via the generic ABI; no PPU/APU implementation |
| NES synthetic end-to-end native recompilation | `BOUNDED_PROVEN` | one synthetic 59-instruction NROM fixture; reference observable equals native observable |
| NES/6502 frontend integration | `BOUNDED_PROVEN` | one synthetic 26-byte NES6502 region through P2-01..P2-06 (P2-20) and one bounded emitted subset (P2-21); no full 6502 support |
| PS1/PS2/Xbox compatibility | `OUT_OF_SCOPE` | not implemented, not claimed |
| Phase-2 final end-to-end proof marker | `NOT_PROVEN` | OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF is reserved for P2-99 and remains NOT_PROVEN |
| arbitrary MIPS32 binary compatibility | `NOT_PROVEN` | bounded synthetic fixtures only |
| arbitrary NES ROM compatibility | `NOT_PROVEN` | no general NES ROM support is implemented or claimed |
| architecture-neutral shared analysis pipeline | `PROVEN` | static import/symbol isolation over the audited shared modules plus MIPS32 and NES6502 path exercises (P2-30); neutral is proven for the audited modules and synthetic fixtures only |
| commercial-game compatibility | `NOT_PROVEN` | no commercial ROM/game is used or supported |
| complete NES hardware compatibility | `NOT_PROVEN` | no full PPU/APU/mapper implementation |
| cycle accuracy | `OUT_OF_SCOPE` | cycle-exact behavior is not modeled or claimed |
| deterministic repeated execution | `PROVEN` | byte-identical stdout across repeated gate runs and repeated native executions for the audited fixtures |
| future architecture compatibility | `NOT_PROVEN` | GB/GBC/SMS/RT64-like extension points are documented only; no adapter implemented |
| generic runtime neutrality | `PROVEN` | no platform leakage in the audited generic runtime modules; adapters share the generic contracts unchanged (P2-40) |
| observable equivalence | `BOUNDED_PROVEN` | declared observable sets for synthetic fixtures only; not general guest/host equivalence |
| reproducible native build | `BOUNDED_PROVEN` | detected clang-cl/lld-link 22.1.8 toolchain on this host for the audited fixtures |
| reproducible release package | `BOUNDED_PROVEN` | audited canonical packaging path for three representative fixtures |
