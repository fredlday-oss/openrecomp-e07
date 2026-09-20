# OpenRecomp Phase 8 Handoff

STATUS: Phase 8 `ACTIVE` at P8-02 after P8-00 and P8-01 `PASS`. The branch
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

## P8-01 outcome

- frozen fixture: upstream `tiny-AES-c` AES-128-ECB at pinned commit
  `23856752fbd139da0b8ca6e471a13d5bcc99a08d`, The Unlicense, built with the
  Phase-3-recorded Zig 0.13.0 toolchain from OpenRecomp-authored freestanding
  port files;
- ELF SHA-256
  `0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65`,
  12904 bytes, ELF32 LE `EM_MIPS` `ET_EXEC`, O32/MIPS32/non-PIC, entry
  `0x2490`; two isolated builds byte-identical;
- existing-pipeline reconnaissance: 509 reachable words (508 supported,
  1 `movz` at `0x2440`), 23 delay slots (16 non-nop), 5 branches / 8 direct
  calls / 3 jumps / 7 returns, no indirect control flow, no unresolved sites;
- the P8-01 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase8/evidence/P8-01/`.

## Exact next action

Complete P8-02: re-derive the complete current pipeline frontier for the
frozen fixture through the existing ELF ingestion, target policy, decode,
semantics inventory, executable-region discovery and reachable-code frontier;
classify every gap into already supported, recognized but unsupported,
unresolved control flow, ABI/runtime gap, memory-image gap, translation gap,
host-emission gap and toolchain/build gap; produce a deterministic frontier
report. PASS means the frontier itself is completely and reproducibly
characterized, not that the ELF is executable.
