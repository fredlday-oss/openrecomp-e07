# OpenRecomp Phase 10 Handoff

## Current boundary

- work branch `phase10/ps1-commercial-game-native-v1`, based exactly on the
  Phase-9 terminal commit `08c639d9032a364163f2985432744be420d402eb`
  (tree `900dccf06ce3d5df7b499a9f05a6ceea060114d7`);
- `P10-00` `PASS` (192 checks): frozen Phase-9 boundary, fixture/disc identity,
  inherited frontier reproduction, toolchains, control plane and frozen queue;
- `P10-01` `PASS` (111 checks): BREAK/SYSCALL classification, public synthetic
  reproducers and the exact private site context;
- evidence in `.openrecomp-phase10/evidence/P10-00/` and `P10-01/`.

## Immediate next action

`P10-02` - reconcile `CONTROL_WITHOUT_DELAY_SLOT` without manufacturing a
delay slot, then re-run the Hercules structure analysis and record the new
exact frontier.

Established at `P10-01`: the cause is BREAK/SYSCALL control semantics. The
frozen Phase-8 bridge requires a delay slot for every record with
`control_flow` true; an `external-trap` record (`break`/`syscall`) has none by
definition. The reconciliation is additive:

- add an exception-aware structure bridge under `.openrecomp-phase10/src/`
  that maps `external-trap` records to the shared neutral
  `InstructionFlow.TRAP` (no successor, no delay slot, no fabricated
  fall-through) and reuses the frozen Phase-8 delay-slot folding and emission
  order for every other record;
- do NOT modify the frozen Phase-8 module; the frozen P9-11 gate must keep
  failing closed with `CONTROL_WITHOUT_DELAY_SLOT` unchanged;
- negative coverage: a control transfer whose delay slot is genuinely missing
  must still fail closed with `CONTROL_WITHOUT_DELAY_SLOT`, a delay-slot trap
  must still be rejected, and `TARGET_INTO_DELAY_SLOT` must still fail closed;
- re-run the Hercules structure analysis and record the new frontier counts
  and the new first blocker.

## Known work queued after P10-02

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
