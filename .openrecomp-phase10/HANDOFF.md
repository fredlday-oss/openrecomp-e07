# OpenRecomp Phase 10 Handoff

## Current boundary

- work branch `phase10/ps1-commercial-game-native-v1`, based exactly on the
  Phase-9 terminal commit `08c639d9032a364163f2985432744be420d402eb`
  (tree `900dccf06ce3d5df7b499a9f05a6ceea060114d7`);
- `P10-00` `PASS` (192 checks): frozen Phase-9 boundary, fixture/disc identity,
  inherited frontier reproduction, toolchains, control plane and frozen queue
  all verified; evidence in `.openrecomp-phase10/evidence/P10-00/`;
- no substantive compatibility implementation yet.

## Immediate next action

`P10-01` - BREAK semantic classification of the `break` at `0x80013390`.

Classify exactly, with independent public test evidence and a bounded handling
strategy:

- instruction encoding: SPECIAL funct `0x0D`, break code 1 (word `0x0000004d`);
- reachable predecessor: `0x8001338c` (the delay-slot `nop` of the `jal` at
  `0x80013388`), i.e. reached by call fall-through, not by a branch target;
- architectural BREAK semantics: synchronous Breakpoint exception
  (ExcCode 9 `Bp`), `EPC` = the BREAK address, `BD` = 0, no delay slot,
  exception vector at `0x80000080` (BEV=0) / `0xBFC00180` (BEV=1);
- why Hercules reaches it, whether continuation is expected, and whether the
  path is genuinely required;
- bounded handling strategy: represent the site as an explicit exception/trap
  record in the neutral structure (`InstructionFlow.TRAP`) and fail closed at
  runtime if it is actually executed; do not implement generic exception
  machinery merely to make the site pass.

Then run the official gate twice through the Phase-10 stage runner and record
the evidence.

## Known work queued after P10-00

- `P10-02`: resolve `CONTROL_WITHOUT_DELAY_SLOT` without manufacturing a delay
  slot, and re-run the Hercules structure analysis for the new frontier;
- `P10-03` .. `P10-11`: CPU/control frontier iteration, BIOS frontier, native
  execution entry, dynamic I/O discovery, GPU, interrupt/DMA/timing,
  CUE/BIN CD-ROM/filesystem/streaming, SPU/controller/game-loop, highest
  milestone;
- `P10-12`, `P10-90`, `P10-91`, `P10-99`: hardening, whole-project regression,
  evidence closure and the final bounded verdict.

## Private fixture notes

- primary executable `SLUS_005.29` (PS-X EXE), entry `0x800132e8`, text
  `0x80010000` size `0x0001f000`, stack `0x801ffff0`;
- single-track MODE2/2352 CUE; the CUE is the logical disc entry point;
- the boot extent on the disc is byte-identical to the primary executable;
- never record payload bytes, disassembly excerpts, disc sectors or
  reconstructive derived data.

## Working-tree residue (preserve untouched)

Tracked Phase-3 evidence files under `.openrecomp-phase3/evidence/P3-00/` are
modified by a historical verification-context re-run, and untracked residue
exists under `.openrecomp-phase2/`, `.openrecomp-phase3/`, `artifacts/` and
`tools/test_build_package_reproducibility_v1.py`. This residue predates Phase
10 and must never be committed, deleted or altered by Phase-10 work.
