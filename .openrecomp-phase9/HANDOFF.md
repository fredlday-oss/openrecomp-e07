# OpenRecomp Phase 9 Handoff

STATUS: Phase 9 `IN_PROGRESS` -- `P9-00` boundary and acceleration control
plane established and `P9-01` PS-X EXE ingestion complete at the frozen
Phase-8 terminal boundary. The terminal marker
`OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF` remains `NOT_PROVEN`;
`OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` and
`OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` are permanent.

## Baseline

- Branch: `phase8/mips32-end-to-end-native-v1`.
- Phase-8 terminal commit:
  `61136fc37cf0810e64241addd8f57a91872bc0af`.
- Phase-8 terminal tree:
  `f9262497b82fe0027c3b23432ba7bd8cbccdf433`.
- Phase-8 terminal verdict (P8-99): `PASS` for the exact bounded audited
  public Phase-8 fixture and behaviour only.
- Phase-8 terminal tag: absent (`ABSENT_RECONCILED`); no tag is fabricated.

## Objective

Prove one bounded PS1 platform/runtime integration path by reusing the
existing Phase-8 MIPS32 end-to-end native pipeline:

```
PS-X EXE
  -> PS-X EXE ingestion / load-image reconstruction
  -> existing MIPS32 decode
  -> shared ProgramModel / CFG / functions / call graph / translation units
  -> existing host emitter
  -> PS1 platform runtime adapter
  -> deterministic native build / execution
  -> bounded validation
```

The private Hercules `SLUS_005.29` fixture is a legally obtained local
validation input only. It is never a public `PASS` criterion on its own and
contributes only non-reconstructive metadata to evidence. Any public terminal
claim requires a legally redistributable OpenRecomp-authored or openly
licensed PS1 fixture.

## P9-00 outcome

- the exact Phase-8 terminal commit/tree/branch boundary and P8-99 terminal
  evidence were verified; no Phase-8 terminal tag exists and none was created;
- the frozen Phase-1 through Phase-8 tracked files and Phase-8 terminal
  evidence hashes re-verified on disk; the Phase-8 source manifest re-verifies
  unchanged; the inherited Phase-6/Phase-7 reconciliation records are present;
- the additive Phase-9 control plane, fixture policy, evidence schema,
  acceleration policy (fast/terminal gates, the
  `openrecomp-phase9-analysis-cache-v1` cache key contract, incremental-build
  policy, private-fixture cache handling), frozen queue and source manifest
  were established;
- the recorded toolchain set (Python, Git, clang/clang-cl, lld-link, Ninja,
  CMake, Zig 0.13.0) was captured in `evidence/P9-00/toolchains.json`;
- the P9-00 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase9/evidence/P9-00/`.

## Frozen queue

Rows `P9-01` .. `P9-99` are frozen at the P9-00 `PASS` boundary in
`.openrecomp-phase9/STAGE_QUEUE.md`. The next stage is `P9-02` (PS1 executable
image and memory-map contract).

## P9-01 outcome

- additive, fail-closed PS-X EXE ingestion
  (`.openrecomp-phase9/src/p9_psx_exe_v1.py`) and an original deterministic
  PS-X EXE builder (`.openrecomp-phase9/fixture/psx_fixture_builder_v1.py`)
  were established;
- 163 checks: canonical synthetic round-trip, BSS/GP positive paths, identity
  leak checks and 22 malformed/unsupported forms rejected with stable codes;
- the private Hercules fixture was ingested and reduced to
  non-reconstructive metadata (file/payload hashes, header fields,
  reserved-region hash and counts) with no executable bytes committed;
- the P9-01 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase9/evidence/P9-01/`.

## Known work for P9-02

- define the explicit PS1 guest address-space model (2 MiB main RAM KSEG0
  window, KSEG1 mirror classification, scratchpad/IO/BIOS ranges as explicit
  unsupported-or-service regions), region permissions and stack contract;
- map the ingested payload into a bounded flat image without silent masking;
- no invented mappings: every address translation decision is explicit and
  fail-closed.

## P9-02 outcome

- additive contract module `.openrecomp-phase9/src/p9_memory_map_v1.py`: 2 MiB
  main RAM with KSEG0/KSEG1 mirrors, named regions (text rwx, BSS rw,
  ram_free rw, explicit bounded 16 KiB stack rw), explicit disabled/unsupported
  classifications for KUSEG/scratchpad/I/O/BIOS/KSEG2, deterministic flat
  image and chunking, fail-closed translation codes;
- 128 checks including KSEG mirror equivalence, permission/region coverage,
  negative overlap and chunk-limit cases, and contract determinism;
- the private Hercules fixture contributed a non-reconstructive contract
  summary only;
- the P9-02 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase9/evidence/P9-02/`.

## Known work for P9-03

- feed the reachable executable frontier through the existing Phase-8 MIPS32
  decode / ProgramModel / CFG / function / call-graph / translation-unit
  stack, reusing `p3_code_frontier_v1` and `p8_structure_v1` unchanged;
- record exact instruction/block/function/call/control-flow counts for the
  original public fixture, and the reachable frontier + first unresolved
  blocker for the private fixture;
- unresolved indirect control flow must fail closed.

## P9-03 outcome

- additive bridge `.openrecomp-phase9/src/p9_image_bridge_v1.py` and original
  public fixture `.openrecomp-phase9/fixture/p9_public_fixture_v1.py`;
- public fixture: 46 reachable words (all supported, no unresolved), 39
  neutral instructions, 9 blocks, 8 edges, 3 functions, 2 internal call
  edges, 3 translation units, entry `fn_80010000`, pinned fingerprints;
- injected `jalr` fails closed as one unresolved indirect call;
- private Hercules frontier: 4068 reachable words (96 recognized-unsupported),
  22 indirect calls, 18 indirect jumps, 3 traps; first blocker `break` at
  `0x80013390`; structure bridge fail-closed `CONTROL_WITHOUT_DELAY_SLOT`;
- the P9-03 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase9/evidence/P9-03/`.

## Known work for P9-04

- classify every reachable instruction of the public fixture exactly once
  against the frozen Phase-8 semantics/emitter paths;
- add only directly required, independently verified semantics (expected:
  none for the public fixture);
- explicitly classify the private fixture's reachable unsupported words
  (`lwl/lwr/swl/swr`, `jalr`, `addi`, `break`, `syscall`) and any COP0/GTE or
  unusual MIPS-I forms without inventing behaviour.

## P9-04 outcome

- additive closure module `.openrecomp-phase9/src/p9_semantics_v1.py`
  reusing the frozen Phase-8 rule table and emitter configuration unchanged;
- public fixture: 39/39 neutral instructions covered exactly once, no
  uncovered sites, no flow mismatches; deterministic emission fingerprint
  `78d099ed...`; injected `lwl` fails closed as uncovered;
- private fixture: 96 reachable recognized-unsupported words classified into
  five explicit categories, no unknown op, no reachable COP0/GTE;
- the P9-04 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase9/evidence/P9-04/`.

## Known work for P9-05

- discover reachable BIOS/system-service calls for the bounded fixtures
  (public fixture: none expected; private fixture: the 22 unresolved `jalr`
  sites classified, not resolved);
- build an explicit typed, versioned host-side service boundary (no BIOS
  image) with unknown services failing closed;
- implement only services required by the bounded fixture.

## P9-05 outcome

- additive boundary module `.openrecomp-phase9/src/p9_bios_boundary_v1.py`:
  typed/versioned service boundary, BIOS A0/B0/C0 vectors declared recognized
  but unimplemented, `UNKNOWN_SERVICE`/`UNIMPLEMENTED_SERVICE` fail-closed
  codes, bounded backward call-site classification;
- public fixture requires no BIOS service; an injected A0 call is discovered
  as one candidate and fails closed;
- private fixture: 22 reachable indirect call sites classify as 3 BIOS B0
  candidates (`0x80015fa4`, `0x80026ebc`, `0x80026f74`) and 19
  `INDIRECT_TARGET_UNKNOWN`; no BIOS implementation;
- the P9-05 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase9/evidence/P9-05/`.

## Known work for P9-06

- identify reachable GPU/GP0/GP1-facing behaviour in the public fixture
  (GP0/GP1 word writes) and the private fixture frontier;
- create the clean platform adapter boundary (typed port map, bounded event
  recording) without attempting GPU emulation;
- keep unknown GPU commands as explicit unresolved blockers.

## P9-06 outcome

- additive modules `.openrecomp-phase9/src/p9_io_discovery_v1.py` (bounded
  same-block I/O access discovery with immediate-only base/value
  reconstruction) and `.openrecomp-phase9/src/p9_gpu_boundary_v1.py`
  (non-emulating GPU adapter, typed event transcript, unknown-command
  blockers, labelled read stubs);
- public fixture: exactly two reachable GPU writes discovered (GP0
  `0x000000a0` -> `NOP`, GP1 `0x00000000` -> `RESET_GPU`), stable transcript
  digest `b190376b...`;
- private fixture: 0 discoverable GPU-range accesses in the bounded
  same-block window over the reachable frontier (explicitly not guessed);
- the P9-06 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase9/evidence/P9-06/`.

## Known work for P9-07

- classify controller, timer, event and interrupt requirements;
- the public fixture reads the controller port (`0x1f801040`) and timer 0
  counter (`0x1f801100`); add deterministic virtual-input and virtual-time
  interfaces with explicit bounded semantics;
- no interrupt delivery is claimed; event requirements are classified.

## P9-07 outcome

- additive module `.openrecomp-phase9/src/p9_input_timer_v1.py`: deterministic
  virtual input, virtual time (`counter-read-returns-tick-then-advances`),
  labelled stubs, explicit not-modelled interrupt blockers;
- public fixture: JOY_DATA read returns `0x00000000`, TIMER0 read returns tick
  0 and advances; transcript digest `819ac68b...`;
- private fixture: 0 discoverable joy/timer/interrupt-range accesses;
- the P9-07 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase9/evidence/P9-07/`.

## Known work for P9-08

- classify reachable audio/SPU interactions; the public fixture writes the
  SPUCNT low byte (`0x1f801daa`);
- establish an explicit audio service/runtime contract with bounded event
  recording and fail-closed unsupported behaviour.
