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
| P10-06 .. P10-12 | QUEUED |
| P10-90, P10-91, P10-99 | QUEUED |

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
  complete candidate set is recorded);
- 79 Phase-10 MIPS host-service calls and GPU/input (both capped at 4096),
  SPU (5) and CD-ROM (38) port events, which grounds `P10-06`;
- milestone `A` (translated native execution begins) established; milestone B
  and beyond explicitly not claimed;
- evidence: `.openrecomp-phase10/evidence/P10-05/`.

## Open blockers

- the first blocker is an executed unresolved indirect jump (18 candidate
  sites); no address-observable failing-PC evidence is available with the
  frozen Phase-9 driver.



