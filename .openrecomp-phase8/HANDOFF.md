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

## P8-02 outcome

- every reachable word classified exactly once against the existing layers:
  215 emitter-ready, 48 word-width memory, 15 control (delay-slot), 8 `jal`
  (delay-slot + link register), 222 host-emitter width gap (`lb`/`lbu`/`sb`),
  1 translation semantics gap (`movz` at `0x2440`);
- measured gaps: 23 delay-slot sites (16 non-nop), 8 o32 link-register call
  sites with 4 `$ra` saves / 4 restores / 3 scratch uses / 1 entry zeroing,
  1 runtime host-service window, 1 memory-image contract, 0 unresolved
  control flow, 0 native toolchain gap;
- all reused Phase-3 module hashes equal their frozen manifest entries;
- the P8-02 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase8/evidence/P8-02/`.

## P8-03 outcome

- new additive bridge `.openrecomp-phase8/src/p8_structure_v1.py` folds MIPS32
  delay slots into their control instructions (size 8) and drives the frozen
  ELF through the existing neutral ProgramModel/CFG/functions/call
  graph/translation-unit layers;
- 486 neutral instructions (509 reachable - 23 folded delay slots, 16
  non-nop), 27 blocks, 25 edges, 7 functions, 7 units, 8 internal call edges
  matching the frontier `jal` sites, 0 unresolved sites, 0 unowned blocks,
  entry `fn_2490`/`tu_fn_2490`, deterministic fingerprints;
- fail-closed mutations rejected with stable codes; a synthetic indirect
  rewrite is classified unresolved with no invented target;
- the P8-03 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase8/evidence/P8-03/`.

## P8-04 outcome

- additive host-emitter extensions: width/sign-explicit `HostLoad`,
  width-explicit `HostStore`, `HostSelect`, opt-in folded delay-slot protocol
  and opt-in link-register materialization; default output byte-compatible;
- closed MIPS32 rule table for exactly the fixture's reachable ops; all 486
  neutral instructions emit deterministically (fingerprint `6a957bd1...`);
- differential native-vs-reference execution of the new semantics (byte
  loads/stores, `movz`, delay-slot order on taken/not-taken/call/return
  paths, `$ra` save/clobber/restore) passes exactly;
- unsupported MIPS32 forms and malformed delay/link metadata fail closed;
- direct dependency gates re-pass unchanged; the P8-04 gate passed twice with
  byte-identical stdout, empty stderr and exit 0. Evidence is under
  `.openrecomp-phase8/evidence/P8-04/`.

## Exact next action

Complete P8-05: validate the frozen fixture's required static memory and
runtime contract -- executable memory, `.rodata`, initialized `.data`,
zero-filled `.bss`, stack requirements, bounded guest memory access and the
explicit output host service -- by reusing the existing memory/runtime
architecture, with no Linux kernel emulation. Define the exact host-side
observable contract for P8-06..P8-08.
