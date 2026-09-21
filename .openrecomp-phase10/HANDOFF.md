# OpenRecomp Phase 10 Handoff

## Current boundary

- work branch `phase10/ps1-commercial-game-native-v1`, based exactly on the
  Phase-9 terminal commit `08c639d9032a364163f2985432744be420d402eb`
  (tree `900dccf06ce3d5df7b499a9f05a6ceea060114d7`);
- `P10-00` `PASS` (192 checks): frozen Phase-9 boundary, fixture/disc identity,
  inherited frontier reproduction, toolchains, control plane and frozen queue;
- `P10-01` `PASS` (111 checks): BREAK/SYSCALL classification, public synthetic
  reproducers and the exact private site context;
- `P10-02` `PASS` (65 checks): `CONTROL_WITHOUT_DELAY_SLOT` reconciled by the
  additive exception-aware structure bridge; the Hercules structure completes;
- `P10-03` `PASS` (144 checks): additive semantic rules for all 24
  unruled reachable op types, Phase-10 runtime extension spliced into the
  frozen Phase-9 platform runtime, independent reference agreement on a
  native build, and fail-closed negatives;
- `P10-04` `PASS` (51 checks): the 22 reachable indirect-call sites are
  classified exactly (3 BIOS B0 vector calls with function indices, 19
  unresolved with explicit evidence), and the typed BIOS boundary stays
  fail-closed with no BIOS material;
- evidence in `.openrecomp-phase10/evidence/P10-00/`, `P10-01/`,
  `P10-02/`, `P10-03/` and `P10-04/`.

## Immediate next action

`P10-05` - native execution entry for Hercules.

Generate and build Hercules-derived native host code (original MIPS machine
code must not execute at runtime) and establish deterministic entry into
translated game code. Record:

- guest entry PC (`0x800132e8`), initial register state and stack state;
- memory-image identity;
- the translated control-flow trace identity;
- the first host/service transition;
- the termination/blocker category.

Expected first blocker candidates, in address order: a direct call into the
`jal 0x80015f18` region (critical-section helper), the BIOS B0 vector call at
`0x80015fa4`, an unresolved indirect call, or an unmapped guest memory access.
Graphics and playability are not required at this stage.

## Known work queued after P10-05

- `P10-06` .. `P10-11`: dynamic I/O discovery, GPU, interrupt/DMA/timing,
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
