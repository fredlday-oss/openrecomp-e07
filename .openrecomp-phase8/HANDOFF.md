# OpenRecomp Phase 8 Handoff

STATUS: Phase 8 `ACTIVE` at P8-90 after P8-00..P8-12 `PASS`. The branch
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

## P8-05 outcome

- contract module `.openrecomp-phase8/src/p8_memory_contract_v1.py`: flat
  image `0x0..0x6710`, regions `0x0`+244 `r--`, `0x1000`+5300 `r-x`,
  `0x24c0`+571 `r--`, `0x2700`+16400 `rw-`, 16 KiB stack at
  `0x2710..0x6710`, write-only byte output window `0x10000000`
  (`p8_uart_write`), return-to-host termination, no kernel services;
- runtime support `.openrecomp-phase8/runtime/p8_runtime_support.c`
  implements the generic runtime ABI memory surface with region permissions,
  bounded access, deterministic counters and an output transcript;
- all 270 reachable memory accesses are register-based, none GP-relative,
  48 `$sp`-relative with maximum offset `0x104` inside the 16 KiB stack;
- native differential memory-contract test equals the independent Python
  model (outcomes, counters, transcript);
- the P8-05 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase8/evidence/P8-05/`.

## P8-06 outcome

- emission set (stable names, content hashes): `program.c` `3df423e0...`
  (byte-identical to the post-correction P8-04 emission), `p8_image_v1.c` `d5d95845...`,
  `p8_runtime_support.c` `9b5e70f5...`, `p8_driver.c` `e918de64...`;
- 7 host translation functions, 463 emitted neutral operations, deterministic
  two-run emission, no `main` in the program, no inline assembly or embedded
  instruction array, guest image inert data only;
- observable record and FNV-1a 64 digest recipe fixed in `p8_driver.c`;
- the P8-06 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase8/evidence/P8-06/`.

## P8-07 outcome

- clean audited build through `openrecomp.build_pipeline`:
  `EXECUTABLE_REPRODUCIBLE`, `program.exe` 226304 bytes, SHA-256
  `fb98c8a68c5c3af7bc30dab2e907910e1c1dfd665eb79e0ee7fcd60dd07a04dc` (all
  four objects byte-identical to the incremental path);
- content-hash incremental cache: cold 4 compiled / 0 reused, warm 0/4,
  corrupted entry 1 recompiled / 3 reused, executable byte-stable
  (`53abcedf...` incremental link output);
- documented `-Wparentheses-equality` diagnostics only; no other warnings;
- the P8-07 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase8/evidence/P8-07/`.

## P8-08 outcome

- the emission set was rebuilt reproducibly and executed three times with
  byte-identical stdout, exit code 0 and empty stderr;
- observable record: `failed=0`, `exit_status=0x00000000`, full 32-register
  boundary state (digest `0x7ee0f4a187050726`), memory digest
  `0x231c4a49e79c5e56`, transcript 33 bytes / digest `0xca6dcb87f8ac9814`
  equal to FNV-1a 64 of the FIPS-197 AES-128 known-answer line, reads 1136,
  writes 681, host calls 33, denied 0;
- the P8-08 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase8/evidence/P8-08/`.

## P8-09 outcome

- new independent reference `.openrecomp-phase8/src/p8_reference_mips32_v1.py`
  (own ELF loader, decoder, interpreter and runtime contract; no
  recompilation or Phase-3 imports);
- the reference executed the frozen ELF for 4572 instructions and matches the
  native record exactly on every observable: exit status, all 32 registers,
  register digest `0x7ee0f4a187050726`, memory digest `0x231c4a49e79c5e56`,
  transcript 33 bytes / digest `0xca6dcb87f8ac9814`, reads 1136, writes 681,
  host calls 33, denied 0; `excluded_observables` is empty;
- all values also equal the committed P8-08 evidence record;
- the P8-09 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase8/evidence/P8-09/`.

## P8-10 outcome

- new workflow module `.openrecomp-phase8/src/p8_workflow_v1.py` runs the
  deterministic bounded path and returns a structured result record;
- the frozen fixture completes the entire path (emission `3df423e0...`,
  `EXECUTABLE_REPRODUCIBLE`, native `exit_status=0x00000000`, reference
  equivalence with no excluded observables) and repeats identically;
- seven malformed/unsupported inputs fail closed with the explicit categories
  `UNSUPPORTED_ELF_CONTAINER` (x3), `UNSUPPORTED_ISA_SEMANTIC`,
  `UNRESOLVED_INDIRECT_CONTROL_FLOW`, `TOOLCHAIN_UNAVAILABLE`,
  `REFERENCE_MISMATCH`;
- the P8-10 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase8/evidence/P8-10/`.

## P8-11 outcome

- eight malformed/unsupported inputs rejected twice with identical records
  and explicit categories (ELF container, ISA semantics, unresolved indirect
  control flow), always before emission/build/execution;
- closed rule table re-verified (16 unsupported forms have no rule);
- new immutable-hash analysis cache with stale-entry rejection (tampered key
  inputs, different fixture identity) plus the content-hash object cache
  (changed source recompiles, corrupt object recompiles, warm build reuses);
- positive control: the frozen fixture still completes with equivalence;
- the P8-11 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase8/evidence/P8-11/`.

## P8-12 outcome

- implementation delta `none`; the gate re-ran the bounded path from clean
  inputs and reproduced every identity exactly;
- all twelve completed stages' run captures and sidecar hashes verified, the
  source manifest verifies, the control-plane ledger and markers verify, and
  the analysis cache rejects stale keys;
- the P8-12 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase8/evidence/P8-12/`.

## P8-90 outcome

- frozen Phase-7 baseline, terminal evidence and the P7-90/P6-90 record hash
  chain re-verify; the Phase-6 tag remains absent and no prior-phase tracked
  file changed;
- Phase-1 host gates re-run byte-identically (2a9d1bba...,
  PASS=44 FAIL=0 SKIPPED=2);
- all fifteen Phase-7 stage gates re-run live in a reconstructed pre-verdict
  worktree at 519c0e73... with scratch evidence, byte-identical stdout and
  exact counts (852 tests); the temporary worktree is removed;
- all thirteen Phase-8 gates re-run live with byte-identical committed
  captures (611 tests); total re-verified stage-gate tests 1463;
- the P8-90 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under .openrecomp-phase8/evidence/P8-90/.

## P8-91 outcome

- evidence_index.json indexes every committed Phase-8 evidence file;
- claim_ledger.json separates PROVEN (the exact bounded public real-ELF
  native path), BOUNDED/PASS (22-op ISA set, delay-slot folding, runtime
  contract, observable record, workflow/hardening) and NOT_PROVEN (general
  MIPS32, arbitrary ELF, complete ISA/o32 ABI, Linux/dynamic linking,
  exceptions, arbitrary indirect flow, PS1/PS2/game/commercial, cycle
  accuracy, cross-platform);
- public-safety verification finds no private identity, path or ROM/native
  binary material in the committed Phase-8 tree;
- the P8-91 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under .openrecomp-phase8/evidence/P8-91/.

## Exact next action

Complete P8-99: audit every Phase-8 stage record, require all required stage
records PASS, P8-90 and P8-91 PASS, exact frozen public fixture provenance,
native/reference agreement and the general-compatibility scope guards; only
then issue the terminal bounded verdict.
