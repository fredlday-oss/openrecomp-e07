# OpenRecomp Phase 8 Handoff

STATUS: Phase 8 `ACTIVE` at P8-01 after P8-00 `PASS`. The branch
`phase8/mips32-end-to-end-native-v1` starts exactly at annotated tag
`openrecomp-phase7-pass`: tag object `b07e0f691262ed3ae0bc2fd6ebb3e3d3c5222800`,
commit `2917aa6549ab975cffdeb50120514c1723f7e493`, tree
`59529c130d759ceb1ca9e6c65a510fa373656b01`.

## Objective

Prove one bounded real MIPS32 end-to-end native recompilation path for exactly
one frozen legally redistributable compiler-produced MIPS32 ELF, reusing the
existing ELF ingestion, decode/semantics, shared ProgramModel/CFG/function
layers, architecture-neutral translation, host emitter, and generic runtime /
native ABI boundary. The terminal marker
`OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF` remains `NOT_PROVEN` until
P8-99. `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` is
permanent.

## P8-00 outcome

- the annotated Phase-7 baseline tag object, peeled commit and tree were
  verified; the branch is at exactly that commit;
- the Phase-7 terminal evidence and control-plane hashes were re-verified on
  disk, no Phase-1..Phase-7 tracked file changed against the baseline commit,
  and no Phase-6 terminal tag exists (`ABSENT_RECONCILED` inherited);
- the additive Phase-8 control plane, fixture policy, evidence schema,
  acceleration policy (fast/terminal gates, analysis-cache key contract,
  incremental-build policy), frozen queue and source manifest were
  established;
- the recorded toolchain set (Python, Git, clang/clang-cl, lld-link, Ninja,
  CMake, Zig 0.13.0) was captured in `evidence/P8-00/toolchains.json`;
- the P8-00 gate passed twice with byte-identical stdout, empty stderr, and
  exit 0. Evidence is under `.openrecomp-phase8/evidence/P8-00/`.

## Exact next action

Complete P8-01: select and freeze one legally redistributable
compiler-produced real MIPS32 ELF. Record source/provenance, licence, pinned
revision, acquisition/build path, SHA-256, size, ELF identity
(class/endianness/machine/type/ABI/ISA/entry/segments/sections) and immutable
fixture identity; prefer a fixture complex enough to exercise real
compiler-produced behaviour but small enough to keep the Phase-8 loop fast.
No native or equivalence claim is made at P8-01.
