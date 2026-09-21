# OpenRecomp Phase 10 State

## Mission

Advance Disney's Hercules (`SLUS_005.29`, private legally obtained fixture)
from the frozen Phase-9 private frontier into deterministic native execution
through the existing OpenRecomp architecture, reusing the PS-X EXE ingestion,
PS1 image/memory contract, existing MIPS32 decode/semantics, shared
ProgramModel/CFG/function/call-graph/TU stack, architecture-neutral translation,
host emitter, generic runtime ABI and the Phase-9 PS1 platform boundaries.

No second PS1 frontend, MIPS decoder, CFG pipeline, host emitter or parallel
runtime architecture is created.

## Baseline

- Phase-9 terminal commit `08c639d9032a364163f2985432744be420d402eb`, tree
  `900dccf06ce3d5df7b499a9f05a6ceea060114d7`, branch
  `phase8/mips32-end-to-end-native-v1`.
- Phase-9 terminal verdict `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=PASS`
  for the exact bounded audited public fixture and behaviour only.
- Phase-10 work branch `phase10/ps1-commercial-game-native-v1`.
- Inherited permanent Phase-9 non-claims (never promoted by Phase 10):
  `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN`.

## Claim markers

- reserved terminal marker (never promoted before `P10-99`):
  `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN`
- reserved playability marker (promotable only at `P10-99` with milestone G):
  `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN`
- permanent general marker: `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`

## Starting frontier (inherited from Phase 9)

- 4068 reachable words (3972 supported, 96 recognized-unsupported, 0 invalid);
- 3 exception sites, 22 indirect calls, 18 indirect jumps, 3 external traps;
- first unresolved blocker `break` (external trap) at `0x80013390`;
- structure failure `CONTROL_WITHOUT_DELAY_SLOT`;
- BIOS discovery: 3 B0 candidates, 19 `INDIRECT_TARGET_UNKNOWN`;
- statically discoverable I/O-range accesses: 0;
- bounded execution `NOT_ATTEMPTED_BLOCKED_BY_FIRST_UNRESOLVED`.

## Fixture control

- private fixture directory discovered repository-relative; CUE and BIN
  filenames discovered from the directory, never assumed;
- CUE is the authoritative disc-image entry point;
- only non-reconstructive metadata is recorded; no payload bytes, no disc
  sectors, no reconstructive derived data;
- the fixture and the disc are never committed, copied or packaged.

## Stage status

| Stage | Status |
|---|---|
| P10-00 | PASS |
| P10-01 | PASS |
| P10-02 | PASS |
| P10-03 | PASS |
| P10-04 | PASS |
| P10-05 | PASS |
| P10-06 | PASS |
| P10-07 | PASS |
| P10-08 | PASS |
| P10-09 | PASS |
| P10-10 | PASS |
| P10-11 | PASS |
| P10-12 | PASS |
| P10-90 | PASS |
| P10-91, P10-99 | QUEUED |

## Stage records

### P10-00 — Phase-10 boundary + fixture/control plane

PASS (192 checks). Gate `tools/test_phase10_boundary_v1.py` run twice through
`.openrecomp-phase10/src/p10_stage_runner_v1.py` with byte-identical stdout
(7108 bytes LF, sha256 `c1c4ed3b...`), empty stderr and exit 0.

- frozen Phase-9 terminal boundary verified: commit
  `08c639d9032a364163f2985432744be420d402eb`, tree
  `900dccf06ce3d5df7b499a9f05a6ceea060114d7`, P9-99 terminal `PASS` for
  `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=PASS`, all 15 required
  Phase-9 stage records `PASS`, 16 frozen Phase-9 file hashes unchanged, no
  `openrecomp-phase9*` tag and the inherited Phase-6/7/8 reconciliations
  intact;
- Phase-10 branch `phase10/ps1-commercial-game-native-v1` descends exactly
  from the Phase-9 terminal commit; only the documented pre-existing Phase-3
  evidence residue differs in the Phase-1..9 trees;
- private fixture/disc identity verified: `SLUS_005.29` (129024 bytes,
  `c230ff5c...`), discovered CUE (101 bytes, `beea454d...`) with one
  `MODE2/2352` track and one referenced BIN (409452624 bytes,
  `2ce144ba...`), ISO9660 PVD at LBA 16, `SYSTEM.CNF;1` declaring
  `BOOT = cdrom:SLUS_005.29;1`, and boot extent LBA 23 byte-identical to the
  primary executable;
- inherited frontier reproduced exactly: 4068 reachable words, `break` at
  `0x80013390`, `CONTROL_WITHOUT_DELAY_SLOT`,
  `NOT_ATTEMPTED_BLOCKED_BY_FIRST_UNRESOLVED`;
- control plane, policies, evidence schema, frozen queue (`P10-01` ..
  `P10-99`), source manifest and stage runner created;
- no substantive compatibility implementation; all four claim markers remain
  unpromoted.
- evidence: `.openrecomp-phase10/evidence/P10-00/`.

### P10-01 — BREAK semantic classification

PASS (111 checks). Gate `tools/test_phase10_break_v1.py` run twice through
`.openrecomp-phase10/src/p10_stage_runner_v1.py` with byte-identical stdout
(10274 bytes LF, sha256 `1b5cb814...`), empty stderr and exit 0.

- two independent implementations agree on the trap encodings (`break`
  funct `0x0d`, `syscall` funct `0x0c`, code field preserved);
- architectural semantics established: synchronous `Bp` (ExcCode 9) /
  `Sys` (ExcCode 8) exceptions, no delay slot, `EPC` = faulting instruction,
  `Cause.BD` = 0, vectors `0x80000080` (BEV=0) and `0xBFC00180` (BEV=1);
- public synthetic reproducers isolate the behaviour: flow stops at a trap,
  no fall-through successor is fabricated past a trap, the frozen Phase-8
  bridge fails closed with `CONTROL_WITHOUT_DELAY_SLOT` at the trap record
  (structural cause identified), a trap-free twin fixture structures cleanly,
  and a trap inside a delay slot is rejected rather than folded;
- fail-closed negatives cover non-trap records, inconsistent trap flags, traps
  with delay slots, traps with targets and code-field disagreement;
- private site context: region start = the PS-X EXE entry `0x800132e8`, no
  return before the site, reached only by the direct-call fall-through at
  `0x80013388` (chain: `0x80013388` call continuation, `0x8001338c` delay
  slot), role `entry-function-terminator-after-application-entry-call`,
  dynamic reachability `NOT_YET_DETERMINED`;
- bounded handling strategy: explicit terminal exception site with
  `InstructionFlow.TRAP`, fail-closed `GUEST_BREAK`/`GUEST_SYSCALL` at runtime;
- no generic exception machinery added; shared layers unchanged from the
  Phase-9 terminal commit.
- evidence: `.openrecomp-phase10/evidence/P10-01/`.

### P10-02 - CONTROL_WITHOUT_DELAY_SLOT reconciliation

PASS (65 checks). Gate `tools/test_phase10_structure_v1.py` ran twice through
the Phase-10 stage runner with byte-identical stdout (27560 bytes LF, sha256
6e55ceb6...), empty stderr and exit 0.

- exact cause: BREAK/SYSCALL control semantics; exception-raising instructions
  carry no delay slot while the frozen Phase-8 bridge required one for every
  control_flow record;
- additive .openrecomp-phase10/src/p10_structure_v1.py maps external-trap
  records to the shared neutral InstructionFlow.TRAP (no successor, no delay
  slot, no fabricated fall-through) and reuses the frozen Phase-8 delay-slot
  handling and the shared ProgramModel/CFG/functions/call-graph/units/
  indirect-control layers;
- additivity proof: for a trap-free fixture the Phase-10 bridge produces
  identical counts, neutral addresses and CFG/discovery/call-graph/units/
  program-model fingerprints to the frozen Phase-8 bridge;
- fail-closed negatives: CONTROL_WITHOUT_DELAY_SLOT, TRAP_WITH_DELAY_SLOT,
  TARGET_INTO_DELAY_SLOT, TRAP_CODE_OUT_OF_RANGE and DELAY_SLOT_IS_CONTROL;
- the frozen Phase-8/Phase-9 trees are unchanged and the frozen P9-11 gate
  still passes and still fails closed with CONTROL_WITHOUT_DELAY_SLOT;
- new frontier: 3433 neutral instructions, 635 folded delay slots, 739 blocks,
  889 edges, 110 functions/units, 209 internal and 22 unresolved call edges,
  40 unresolved indirect control sites, 3 exception sites; first unresolved
  indirect site 0x80013e7c jr; first site without a semantic rule
  0x80011a60 sh; 24 op types / 286 reachable instructions still need
  host-emitter rules;
- evidence: .openrecomp-phase10/evidence/P10-02/.

### P10-03 - Hercules CPU/control frontier iteration

PASS (144 checks). Gate `tools/test_phase10_semantics_v1.py` ran twice through
the Phase-10 stage runner with byte-identical stdout (3793 bytes LF, sha256
`f84e7feb...`), empty stderr and exit 0.

- 24 reachable op types gained additive rules (46 rules total); the frozen
  Phase-8 rules are reused unchanged and no frozen op is redefined;
- forms the scalar vocabulary cannot express exactly use explicit host
  services (`lwl`, `lwr`, `swl`, `swr`, `mult`, `mfhi`, `add.overflow.check`)
  implemented in the Phase-10 extension spliced into the frozen Phase-9
  platform runtime translation unit (frozen source hash-verified, one anchored
  substitution, everything else reused verbatim);
- an independently structured bounded MIPS32 reference interpreter agrees with
  the generated native build on all 32 registers, the RAM digest and the exit
  status for a synthetic fixture exercising every added non-trap op;
- 20 unaligned-merge vectors (4 alignments x 5 values) round-trip against the
  frozen Phase-3 byte-level `swl`/`swr` model;
- fail-closed native negatives: `break`, `syscall`, signed `addi` overflow,
  executed unresolved `jalr`, and an unmapped `lwl` each terminate with
  `failed=1`;
- the private Hercules structure satisfies every precondition (22 `jalr` with
  `$ra`, 635 ruled folded delay slots, no unruled reachable op) and is now
  emittable end to end;
- evidence: `.openrecomp-phase10/evidence/P10-03/`.

### P10-04 - Hercules BIOS frontier

PASS (51 checks). Gate `tools/test_phase10_bios_v1.py` ran twice through the
Phase-10 stage runner with byte-identical stdout (1822 bytes LF, sha256
`b0573540...`), empty stderr and exit 0.

- the 22 reachable indirect-call sites classify exactly: 3 BIOS vector calls
  (B0 index `0x56` once, `0x57` twice) and 19 unresolved targets (13 proven
  written by a memory load, 6 explicitly unresolved across a control-flow
  boundary); no target is guessed;
- the observed call convention is recorded: `$t2` carries the vector base
  (`0x000000b0`), `$t1` the function index as a delay-slot constant;
- the Phase-9 typed service boundary is reused unchanged with no service
  implemented, `bios_image: none`, unknown-service policy `fail-closed`, and
  `semantics_determined: false`;
- synthetic fixtures cover the accepted `A0`/`B0`/`C0` and KSEG0 forms, the
  resolved-internal-call form, a call with no constant index, an
  out-of-image constant target and a memory-loaded target;
- native fail-closed negatives: a BIOS vector call and a read of the low BIOS
  table window both terminate with `failed=1`;
- evidence: `.openrecomp-phase10/evidence/P10-04/`.

### P10-05 - Native execution entry

PASS (30 checks). Gate `tools/test_phase10_native_v1.py` ran twice through the
Phase-10 stage runner with byte-identical stdout (1040 bytes LF, sha256
`16efd5a6...`), empty stderr and exit 0.

- the private executable translated through the existing architecture-neutral
  emitter and the Phase-10 runtime: 110 functions (`program.c` 520039 bytes),
  the 2 MiB guest RAM window as inert data, the frozen Phase-9 platform
  runtime with three anchored Phase-10 substitutions, and the frozen Phase-9
  observable driver;
- original MIPS machine code never executes: no guest payload bytes, no
  opcode dispatch and no image include in `program.c`; the guest image is
  inert data;
- reproducible build (two isolated runs, both `OK`), executable SHA-256
  `972a0ebb...`, repeated execution byte-identical;
- deterministic translated entry into the guest entry `0x800132e8`; the guest
  crt0 effect is observable (`$gp` `0x8002ed78`, `$fp` `0x80200000`, `$sp`
  `0x801ffe00`) and the guest RAM digest changed;
- 982859 reads + 799023 writes + 11 denied + 8235 device events = 1790128
  accounted accesses against an explicit 2000000 access budget that was NOT
  reached, so the blocker is real game code;
- termination category `UNRESOLVED_INDIRECT_JUMP` at an executed unresolved
  indirect jump (exact site not observable with the frozen driver; the
  complete candidate set is recorded); a fail-closed failure aborts only the
  current translated function, so the traffic record includes progress after
  the first failure (re-issued evidence records this explicitly);
- 79 Phase-10 MIPS host-service calls and GPU/input (both capped at 4096),
  SPU (5) and CD-ROM (38) port events, which grounds `P10-06`;
- milestone `A` (translated native execution begins) established; milestone B
  and beyond explicitly not claimed;
- evidence: `.openrecomp-phase10/evidence/P10-05/`.

### P10-06 - Dynamic PS1 I/O discovery

PASS (26 checks). Gate `tools/test_phase10_io_v1.py` ran twice through the
Phase-10 stage runner with byte-identical stdout (1074 bytes LF, sha256
`fa234657...`), empty stderr and exit 0.

- dynamic source: the deterministic `P10-05` native record (GPU and controller
  events capped at 4096, SPU 5, CD-ROM 38, 11 denied accesses, access budget
  not reached, termination `UNRESOLVED_INDIRECT_JUMP`);
- static complement: 1107 reachable access sites, 769 with an unresolved
  (memory-loaded pointer) base carrying slice evidence, 338 resolved to RAM
  globals, 0 resolvable to an audited device range - device addresses are
  computed at runtime, so dynamic evidence is the only source;
- the audited Phase-9 port ranges are reused unchanged; no device map is
  invented;
- no device is extended at this stage; the observed classes are already served
  by the Phase-9 typed port boundary and unmodelled ports/commands stay
  fail-closed;
- evidence: `.openrecomp-phase10/evidence/P10-06/`.

### P10-07 - GPU command execution frontier

PASS (58 checks). Gate `tools/test_phase10_gpu_v1.py` ran twice through the
Phase-10 stage runner with byte-identical stdout (2036 bytes LF, sha256
`97519d67...`), empty stderr and exit 0.

- exact classification: 65536 recorded GPU events, all 32-bit reads of GP1
  (`0x1f801814`) returning the audited contract stub `0x14802000`; zero GP0/GP1
  writes, zero blocked GPU events, zero unknown commands, zero transfer-class
  and zero DMA-controller traffic; VRAM is not modelled and no digest is
  fabricated;
- reads and writes are separated before classification, so a status value is
  never misread as a command;
- implemented subset: exactly one operation - the GP1 status read returns the
  audited Phase-9 boundary contract stub. The A/B comparison shows the recorded
  access traffic is identical with and without the stub, so no behavioural
  assumption is introduced;
- public synthetic native fixtures: known GP0 `NOP`/`POLYGON` writes are served
  and recorded (`failed=0`, `denied=0`); an unknown GP0 command fails closed
  (`failed=1`, `denied=1`, blocked event, class `UNKNOWN_COMMAND`);
- denial attribution: 1 controller/interrupt BLOCKER (`I_MASK`), 1 CD-ROM
  BLOCKER (unknown command `0x80`), 0 GPU/SPU, 9 unrecorded;
- GPU-side blocker: none. The first remaining blocker is the executed
  unresolved indirect jump (control flow), which precedes any GPU command
  write, followed by the access-budget bound. Milestone C is NOT established;
- documented divergence: the runtime composition advanced (diagnostic event
  capacity, GPU status-read stub). No earlier stage assumption or identity was
  falsified, so no earlier stage was re-issued;
- evidence: `.openrecomp-phase10/evidence/P10-07/`.

### P10-08 - Interrupt / DMA / timing frontier

PASS (42 checks). Gate `tools/test_phase10_timing_v1.py` ran twice through the
Phase-10 stage runner with byte-identical stdout (1661 bytes LF, sha256
`749e3c6e...`), empty stderr and exit 0.

- the deterministic non-RAM access log (17 signatures, no overflow) closes the
  `P10-07` open item: platform denials 6 (`I_MASK` read 1, DMA channel-2 write
  1, low/null write 1, memory-control delay writes 2, CD-ROM unknown command 1)
  plus budget denials 5 equal the runtime's denied counter 11 exactly;
- served observations 218112: GPU status 109035 and timer1 counter 109035
  (exactly one-to-one, i.e. a single polling loop with both probes served) plus
  CD-ROM 37 and SPU 5;
- the virtual-time abstraction is recorded explicitly: a read-driven counter
  returning `tick & 0xffff` (not cycle accurate, no wall-clock dependency), and
  is proven by a public synthetic fixture (0, 1, 2 across three reads);
- nothing new is implemented: the interrupt-mask read, the DMA channel-2
  configuration write and the memory-control delay writes are all left
  fail-closed with the evidence showing none is proven required; DMA needs
  VRAM/transfer state and delay registers need a timing model, so accepting
  them would invent device behaviour;
- public synthetic native negatives confirm the deterministic fail-closed
  behaviour for all three denied interactions;
- the bounded-execution limitation (the access budget bounds accesses, not
  execution) is recorded as a `P10-12` hardening item;
- evidence: `.openrecomp-phase10/evidence/P10-08/`.

### P10-09 - Disc / CD-ROM / streaming frontier

PASS (46 checks). Gate `tools/test_phase10_disc_v1.py` ran twice through the
Phase-10 stage runner with byte-identical stdout (1720 bytes LF, sha256
`0d049cc1...`), empty stderr and exit 0.

- disc identity re-verified exactly against the `P10-00` record: the CUE is
  discovered from the fixture directory (101 bytes, `beea454d...`), the
  referenced BIN (409452624 bytes, `2ce144ba...`) with one `MODE2/2352` track
  and `INDEX 01 00:00:00`, ISO9660 174087 sectors, root extent LBA 22, and the
  `SYSTEM.CNF` boot extent byte-identical to `SLUS_005.29`;
- exact CD-ROM register frontier: index/status writes 15, parameter writes 8,
  interrupt-enable reads 2 / writes 3, command writes 10;
- command bytes classified with the audited 32-entry Phase-9 command table:
  `READ_N` 4, `SET_MODE` 4, `SET_LOCATION` 1, unknown `0x80` 1 (blocked,
  fail-closed);
- the disc data path is NOT reached: no sector transfer, no ISO9660 access, no
  file open/read, no overlay, no resource load, no streaming, no XA and no
  asynchronous CD event appears in the transcript;
- nothing is implemented (no disc behaviour is reached; implementing it would
  be speculative); the boundary accepts the commands without performing any
  transfer, so a data consumer would receive the explicit contract stub rather
  than host filesystem data;
- public synthetic fixtures: `SET_MODE`/`READ_N` served, unknown `0x80`
  fail-closed, data-port read returns the contract stub and never disc bytes;
- evidence: `.openrecomp-phase10/evidence/P10-09/`.

### P10-10 - Controller / SPU / game-loop frontier

PASS (36 checks). Gate `tools/test_phase10_input_spu_v1.py` ran twice through
the Phase-10 stage runner with byte-identical stdout (1310 bytes LF, sha256
`4660005f...`), empty stderr and exit 0.

- controller: zero accesses to the controller window; the guest never touches
  the data port, so no scripted input is consumed - recorded as
  `NOT_REACHED_BY_THE_PRIVATE_FRONTIER`, not implemented speculatively;
- deterministic scripted input is proven by a public synthetic fixture (button
  pattern `0xc1f3` written and read back unchanged, `failed=0`, `denied=0`);
- SPU: 5 configuration events (one `spu_control` write `0xc001`, two
  `spu_cd_audio` volume writes `0x3fff`, two zero reads), no RAM transfer, no
  blocked event; audio output is not required and not implemented;
- game loop: no frame loop and no vsync/interrupt-driven wait is reached; the
  reached loop is a served busy-poll loop (GPU status and timer1 counter read
  exactly one-to-one, 109035 each);
- timer1 counter reads 109035 and interrupt-port accesses 1 (`I_MASK`,
  fail-closed);
- nothing is implemented; unserved interactions remain fail-closed;
- evidence: `.openrecomp-phase10/evidence/P10-10/`.

### P10-11 - Highest Hercules milestone

PASS (38 checks). Gate `tools/test_phase10_milestone_v1.py` ran twice through
the Phase-10 stage runner with byte-identical stdout (1284 bytes LF, sha256
`29a3d4a2...`), empty stderr and exit 0.

- highest demonstrated milestone: **A** (translated native execution begins),
  re-derived from the committed evidence and hash-bound to it;
- B (initialisation completes): NOT established - the guest fails closed inside
  its initialisation path at an executed unresolved indirect jump;
- C (GPU command stream reached): NOT established - only GP1 status reads,
  zero GP0/GP1 command writes;
- D/E/F: NOT established - no frame or present observable, and the reached loop
  is a served busy-poll loop rather than a frame loop;
- G (controllable gameplay): NOT established - the controller data port is
  never touched and no input-driven state progression exists;
- the playability promotion rule is recorded: milestone G with deterministic
  scripted-input evidence is the only basis for a playability claim, and it is
  absent;
- evidence: `.openrecomp-phase10/evidence/P10-11/`.

### P10-12 - Hardening and reproducibility

PASS (56 checks). Gate `tools/test_phase10_hardening_v1.py` ran twice through
the Phase-10 stage runner with byte-identical stdout (2046 bytes LF, sha256
`5ddd24b3...`), empty stderr and byte-identical generated sidecars.

- 12 synthesised malformed PS-X EXE containers reject with their exact stable
  codes; malformed trap records and a delay-slot-less control transfer still
  fail closed; a malformed BIOS analysis invents no service;
- live fail-closed negatives: an executed `break` and an unknown GP0 command
  both terminate with explicit errors and no continuation;
- the identity-bound analysis cache misses on every identity/version/
  configuration change (9 invalidations), rejects missing provenance and
  rejects corrupt entries;
- the public-safety scan of 117 committed evidence files finds no private
  payload hex/base64/ASCII run and no absolute host path;
- a clean rebuild reproduces every committed cross-stage observable exactly
  (reads/writes/denied/host calls/budget counters/failure category/device event
  counts and the crt0 register state);
- the bounded-execution limitation is recorded with its mitigation;
- one gate-internal correction was applied before the official runs (the safety
  scan now excludes the stage directory it writes) so the scan is
  deterministic;
- evidence: `.openrecomp-phase10/evidence/P10-12/`.

### P10-90 - Whole-project regression

PASS (155 checks). Gate `tools/test_phase10_whole_regression_v1.py` ran twice
through the Phase-10 stage runner with byte-identical raw stdout (5279 bytes,
sha256 `90630afd...`; LF capture `0370518d...`), empty stderr and exit 0.

- frozen boundary identity re-verified: Phase-9 terminal commit
  `08c639d9032a364163f2985432744be420d402eb`, tree
  `900dccf06ce3d5df7b499a9f05a6ceea060114d7`, frozen branch tip, the frozen
  Phase-9 hashes (10), the frozen Phase-8 terminal records (6), the documented
  prior tracked diff and the frozen Phase-8/Phase-9/Phase-10 source manifests
  (33 entries);
- live re-runs with byte-identical stdout: the Phase-1 host harness
  (44 pass / 0 fail / 2 toolchain skips), the twelve frozen Phase-9 gates
  P9-01..P9-12 into scratch evidence (1101 tests), and all thirteen Phase-10
  gates P10-00..P10-12 into scratch evidence (1633 tests); the committed
  Phase-10 evidence root is verified untouched;
- the frozen Phase-8 terminal audits (`P8-90` 215, `P8-91` 27, `P8-99` 92) are
  verified through the frozen `P9-90` in-place record and the frozen evidence
  hashes; the reconstruction mechanism was resolved during this stage (see
  `P10-90 reconstruction diagnosis`): the isolated `P8-00` reconstruction
  reproduces the frozen stdout `8bc1af62...` twice, and the live three-gate
  re-run remains non-reproducible only because the frozen Phase-8 evidence
  embeds the absolute worktree path (1 of 27 sidecars measured divergent);
- totals: 16 historical gates / 1435 historical re-verified tests, 13 Phase-10
  gates / 1633 Phase-10 tests, 3068 re-verified tests in total;
- claim-ledger delta: none; the terminal, playability and general markers stay
  `NOT_PROVEN` and the highest demonstrated milestone stays `A`;
- evidence: `.openrecomp-phase10/evidence/P10-90/`.

## Status at the P10-12 closure

Stages `P10-00` .. `P10-12` are `PASS` and committed on
`phase10/ps1-commercial-game-native-v1`; the frozen terminal sequence
`P10-90` (whole-project regression), `P10-91` (evidence index) and `P10-99`
(final bounded verdict) is queued and **not attempted**.

Highest demonstrated milestone: **A** (translated native execution begins),
hash-bound to the committed stage evidence at `P10-11`.

Claim markers at this boundary:

- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN` (reserved for
  `P10-99`; the underlying native-execution result itself is established and
  reproduced at `P10-12`)
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN`
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

## P10-90 execution plan (not yet attempted)

1. Frozen Phase-1..Phase-9 gates: re-run the Phase-9 boundary gate
   (`tools/test_phase9_boundary_v1.py`) and the frozen Phase-9 official gates
   with their frozen runners, plus the Phase-8 terminal gates. Phase 7 required
   the documented reconstructed pre-verdict worktree mechanism used by P8-90 /
   P9-90; reuse exactly that mechanism (see `.openrecomp-phase9/evidence/P9-90/`
   for the recorded reconstruction recipe).
2. Phase-10 gates: re-run all thirteen through the Phase-10 stage runner:
   `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage <STAGE>
   --script <gate> --evidence-dir .openrecomp-phase10/evidence/<STAGE>
   --tests-json <tests.json>` for `<STAGE>`/`<gate>` in
   `P10-00/tools/test_phase10_boundary_v1.py`,
   `P10-01/tools/test_phase10_break_v1.py`,
   `P10-02/tools/test_phase10_structure_v1.py`,
   `P10-03/tools/test_phase10_semantics_v1.py`,
   `P10-04/tools/test_phase10_bios_v1.py`,
   `P10-05/tools/test_phase10_native_v1.py`,
   `P10-06/tools/test_phase10_io_v1.py`,
   `P10-07/tools/test_phase10_gpu_v1.py`,
   `P10-08/tools/test_phase10_timing_v1.py`,
   `P10-09/tools/test_phase10_disc_v1.py`,
   `P10-10/tools/test_phase10_input_spu_v1.py`,
   `P10-11/tools/test_phase10_milestone_v1.py`,
   `P10-12/tools/test_phase10_hardening_v1.py`.
3. Expect: every stage gate passes twice with byte-identical stdout, empty
   stderr and exit 0; the committed evidence sidecars are regenerated
   identically. `P10-02`, `P10-03`, `P10-05`, `P10-06` were each re-issued at
   least once during the phase; their recorded hashes in the corresponding
   `RESULT.md` files are the current ones, so a divergence there means a real
   regression and must be investigated, not papered over.
4. Capture exact gate/test counts, stdout hashes, stderr state and sidecar
   identities under `.openrecomp-phase10/evidence/P10-90/`.

Durations: the Phase-10 gates that build and run the native Hercules program
(P10-05, P10-07, P10-08, P10-09, P10-10, P10-12) take minutes each per run and
each official run is doubled by the runner; budget hours, not minutes, and run
them with a generous timeout (the gates themselves use 5400 s per native run).

## P10-90 audit status: PASS (resolved at the P10-90 recovery)

`P10-90` was first attempted and did **not** reach `PASS`; the findings below
were recorded and are now resolved (see `Resolution` at the end of this
section). The audit tool `tools/test_phase10_whole_regression_v1.py` performs,
on one tree:

- the frozen Phase-9 boundary/terminal hash checks, the documented prior tracked
  diff and the frozen Phase-9 source manifest;
- a live Phase-1 host harness re-run (44 pass / 0 fail / 2 toolchain skips,
  byte-identical stdout to the frozen P8-90 capture);
- live re-runs of twelve of the thirteen frozen Phase-9 gates with byte-identical
  stdout to their committed captures;
- live re-runs of all thirteen Phase-10 gates with byte-identical stdout to their
  committed captures and no tracked evidence modified;
- the committed-evidence safety scan and the permanent scope guards.

### Findings requiring action before P10-90 can PASS

1. **Branch-context gates cannot be re-run live on the Phase-10 branch.** The
   frozen `P8-90`/`P8-91`/`P8-99` gates assert the frozen branch name, and the
   frozen `P9-00` boundary gate does too. Phase 10 deliberately works on
   `phase10/ps1-commercial-game-native-v1` (P10-00 policy). A reconstruction
   worktree on the frozen branch fails the gates' own worktree-hygiene and
   generated-artifact expectations, so the tool documents the reconciliation:
   those four gates are verified by frozen evidence hashes, the frozen branch-tip
   identity (equal to the audited commit/tree) and the frozen `P9-90` record
   (which re-ran the Phase-8 terminal gates live on that same commit/tree with
   byte-identical stdout). This is recorded, not silent.
2. **Stale stage evidence from the documented composition advance.** `P10-03`
   was stale (149 vs 151 checks) and has been re-issued. Any other stage whose
   sidecars embed the runtime composition (`P10-05`, `P10-07`, `P10-08`) must be
   re-issued the same way before P10-90 can require in-place reproducibility.
3. **Accidental re-tracking corrected.** A Phase-10 `git add ... tools` sweep
   re-tracked `tools/test_build_package_reproducibility_v1.py`, which Phase 2 had
   deliberately untracked; the frozen Phase-1 public-safety scan caught it. It
   has been untracked again (two correction commits) and the scan passes.

### Resolution

1. the `P10-00`/`P10-05`/`P10-06` sidecar staleness is resolved by the scratch
   redirection: the completed stages record the runtime composition at their own
   boundary (the documented `P10-07`/`P10-08` advance) and downstream gates bind
   earlier records by hard-coded digest, so in-place regeneration cannot be
   byte-identical; the gate re-runs now write scratch evidence (the frozen
   Phase-9-gate recipe) and the committed evidence root is verified untouched;
2. the tool's stale worktree references were replaced by the measured
   reconciliation record: the live three-gate re-run is not byte-reproducible
   because the frozen Phase-8 evidence embeds the absolute worktree path (the
   `P8-01` sidecar; 1 of 27 sidecars measured divergent);
3. the Phase-10 source manifest was regenerated (33 entries);
4. the official runner ran the gate twice with byte-identical raw stdout, empty
   stderr, exit 0 and identical sidecars (`P10-90` `PASS`, 155 checks).

## P10-90 reconstruction diagnosis (deterministic, read-only)

### 1. Identity of the reconstruction

| Item | Value |
|---|---|
| expected frozen commit | `08c639d9032a364163f2985432744be420d402eb` |
| expected frozen tree | `900dccf06ce3d5df7b499a9f05a6ceea060114d7` |
| actual HEAD (worktree) | `08c639d9032a364163f2985432744be420d402eb` (match) |
| actual tree (worktree) | `900dccf06ce3d5df7b499a9f05a6ceea060114d7` (match) |
| branch in worktree | `phase8/mips32-end-to-end-native-v1` (the branch the frozen gates assert) |

### 2-4. Mismatch set against the audited source material

Tracked files (2922): 2659 byte-identical; **261 line-ending-only** (identical
Git blobs, differing working-tree bytes only - checkout normalisation); **2
content mismatches**, both the *documented pre-existing Phase-3 residue*
(`.openrecomp-phase3/evidence/P3-00/p3_00_tests.json`,
`.openrecomp-phase3/evidence/P3-00/residue_manifest.txt`), whose audited form is
the modified main-worktree form while the reconstruction holds the committed
blob - i.e. the reconstruction is *more* frozen there, which is correct.

**15644 untracked files (310 MB) plus ignored generated outputs** (for example
`.openrecomp-phase8/build/P8-01/candidate-a/p8_aes128_mips32_O1.elf`, the zig
toolchain under `.openrecomp-phase3/tools/zig`, and the audit input
`tools/test_build_package_reproducibility_v1.py`) are absent in a fresh
worktree. These are generated/untracked dependencies of the frozen gates.

After materialising the audited working-tree bytes for every file under the
frozen roots (`phase1..phase9`, `tools`, `openrecomp`, `adapters`, `contracts`,
`schema`, `corpus`), all three frozen manifests verify with **zero** mismatches:
root 134/134, Phase-8 30/30, Phase-9 35/35 entries.

### 5. Provenance of the one frozen-manifest failure before the fix

`.openrecomp-phase8/fixture/p8_start.S`: expected/main SHA-256
`9ee18734…`; reconstruction SHA-256 `3f1a17cd…`; **blob ids identical**
(`713f25e7…` for HEAD, main and the blob) - a pure line-ending/checkout
normalisation artefact (cause D), not a content difference.

### 6. Root cause classification

| Class | Finding |
|---|---|
| A incorrect reconstruction source | no - the worktree head/tree equal the frozen commit/tree exactly |
| B incomplete materialisation | yes - the untracked/ignored dependency set (occurrence) |
| C generated files required by the frozen gate | yes - compiled fixtures, toolchain, audit inputs |
| D line-ending / checkout normalisation | yes - 261 tracked files plus `p8_start.S`; blobs identical |
| E pre-verdict state absent from the frozen commit | no for the Phase-8 terminal gates; the pre-verdict reconstruction is only needed for the Phase-7 chain, which P8-90 performs internally with a detached worktree |
| F Phase-10 files leaking into the historical worktree | no - the worktree contains zero reconstruction-only untracked files |
| G other | one residual: `P8-00`'s `frozen:no-new-prior-residue` flags two paths as modified in the reconstruction - `.openrecomp-phase1/UPDATE_ROM_INVENTORY.ps1` and `.openrecomp-phase4/fixture/p4_start.S` - while the *same audited bytes* are status-clean in the main worktree. The check tolerates `git status` lines only for phases 2 and 3. Measured facts: the shared config has `core.autocrlf=true`, `core.eol` unset, `.gitattributes` gives both paths `text=auto`; the index form is LF for both; the audited working-tree form is CRLF for the `.ps1` and LF for the `.S`; the main worktree is status-clean for both under `autocrlf` true/false/unset; the Git blob ids are identical between the audited tree and the frozen commit; `git ls-files -v` reports normal (`H`) flags, so `assume-unchanged`/`skip-worktree` are not involved. Disproved: blob-form rewriting (still flagged) and the index-flag hypothesis. **Resolved** (see the resolution section below): in the pure audited-byte configuration the only non-tolerated flagged path is `.openrecomp-phase4/fixture/p4_start.S` (the `.ps1` is clean there), the flag is a stat-cache effect of the byte-exact materialisation, and `git update-index --really-refresh` restores the audited stat cache so the check passes. |

### 7. What the historical gate genuinely requires

The frozen Phase-8 terminal gates require a **hybrid reconstructed state**: the
frozen committed tree, **plus** the audited working-tree byte forms for tracked
files **plus** the audited untracked/ignored generated material. They do not
require a pre-verdict control-plane reconstruction (that is needed only for the
Phase-7 stage chain, which the frozen P8-90 gate reconstructs internally with a
detached worktree at the frozen P7-90 commit).

### 8. Comparison with the successful Phase-8/Phase-9 mechanisms

* the frozen `P8-90` gate reconstructs the Phase-7 chain with
  `git worktree add --detach <tmp> <P7_90_COMMIT>`, verifies the pre-verdict
  marker and runs the Phase-7 stage gates with scratch evidence - a detached
  worktree works there because those gates assert pre-verdict markers only, not
  branch or worktree hygiene;
* `P9-90` ran the Phase-8 terminal gates **in place** because Phase 9 remained
  on the frozen branch, so the audited working-tree state existed naturally; it
  only snapshotted/restored frozen evidence;
* Phase 10 deliberately works on `phase10/ps1-commercial-game-native-v1`
  (P10-00 policy), so "in place" cannot satisfy the frozen branch assertions;
  the equivalent mechanism is the **branch-checkout worktree plus audited-byte
  materialisation**, which this diagnosis validated to the point where
  `P8-91` and `P8-99` reproduce **byte-identical stdout** and `P8-90` fails only
  through its inner `P8-00` residue assertion.

### Resolution (P10-90 recovery): the exact measured mechanism

The measurement was performed and the mechanism is fully determined:

1. expected prior-residue set: the audited main worktree is status-clean for
   `.openrecomp-phase1` .. `.openrecomp-phase7` except the two documented
   Phase-3 evidence files; P8-00 tolerates `git status` lines only for phases 2
   and 3 (the audited phase-2/3 line-ending/verdict context);
2. in the pure audited-byte materialisation configuration the only
   non-tolerated flagged path was `.openrecomp-phase4/fixture/p4_start.S`; the
   `.ps1` is clean there (audited CRLF worktree, LF index, system
   `core.autocrlf=true`);
3. the flag is a stat-cache effect, not a content difference: the audited main
   worktree is status-clean because its index stat cache is valid, while
   byte-exact materialisation invalidates the reconstruction's stat cache and
   `git status` then flags the path through the CRLF round-trip path;
4. the minimal proven fix is to reproduce the audited stat cache:
   `git update-index --really-refresh` in the reconstruction worktree after
   materialisation; `.openrecomp-phase4/fixture/p4_start.S` then reports clean
   and `frozen:no-new-prior-residue` passes with the remaining flagged lines all
   in phases 2/3;
5. the isolated P8-00 `--verify-only` reconstruction reproduced the frozen
   stdout `8bc1af6294db8b70b92792362226cb56666f6affaffa3ffd657ce7caba503562`
   twice (exit 0, empty stderr), and all three frozen manifests verify with zero
   mismatches (root 134/134, Phase-8 30/30, Phase-9 35/35).

The same reconstruction was then run through the full frozen `P8-90` gate: all
frozen checks up to and including `P8-00` pass (and `P8-11` passes), but `P8-12`
evidence closure cannot pass in a reconstruction: the frozen Phase-8 evidence
embeds the absolute worktree path (the `P8-01` sidecar records the toolchain
path; exactly 1 of the 27 frozen sidecars diverges). The frozen `P9-90`
in-place record is therefore the mechanism that remains in use for the three
Phase-8 terminal gates.

## Open blockers

- the executed unresolved indirect jump blocks initialisation; the exact
  failing guest PC is not observable;
- milestones B..G are unreachable without resolving that control-flow frontier;
- the access budget cannot interrupt a post-truncation guest loop with no
  memory access (mitigated by the default budget plus a bounded host timeout);
- SPU RAM transfer, interrupt delivery, DMA, memory-control timing, disc data
  transfer and controller consumption remain unreached/unimplemented.










