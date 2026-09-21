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
- `P10-05` `PASS` (30 checks): the private executable is generated, built
  and executed deterministically as generated host code; the crt0 prefix
  runs, 1.79M guest accesses execute, and the run fails closed at an
  executed unresolved indirect jump. Milestone A established;
- `P10-06` `PASS` (26 checks): dynamic device discovery from the `P10-05`
  record plus the constant-base static complement;
- `P10-07` `PASS` (58 checks): the GPU frontier is exactly classified -
  GP1 status polling only (`0x14802000` stub, 65536 reads), zero GP0/GP1
  writes, zero unknown commands, no DMA, no modelled VRAM; the GPU is not
  the blocker;
- `P10-08` `PASS` (42 checks): the interrupt/DMA/timing frontier is exactly
  classified, all 11 denials are attributed by address and cause, the
  read-driven virtual-time contract is proven, and every unproven
  interaction stays fail-closed;
- evidence in `.openrecomp-phase10/evidence/P10-00/` .. `P10-08/`.

## Immediate next action

`P10-09` - disc / CD-ROM / streaming frontier.

Use the already verified CUE as the authoritative private disc source
(`P10-00` recorded its identity and the `SYSTEM.CNF` boot relationship; the CUE
and BIN filenames must again be discovered from the fixture directory, never
assumed). Evidence already available from `P10-07`/`P10-08`:

- CD-ROM register traffic: index/status writes at `0x1f801800` (15), parameter
  writes at `0x1f801802` (8), register-3 reads/writes at `0x1f801803` (2/3),
  and 10 command writes at `0x1f801801` of which 9 were served by the Phase-9
  boundary and 1 (command `0x80`) was blocked as unknown;
- no sector read has been observed, no ISO9660 access, no streaming and no XA
  evidence exists in the recorded frontier. Determine whether the blocked
  command and the absence of sector reads are pre- or post-failure behaviour
  and classify the actual requirement;
- do not extract or commit disc contents; record only hashes, names, counts,
  access classifications and operation traces;
- the P10-01/P10-06/P10-08 rule applies: no host-filesystem substitution for PS1
  CD behaviour, and unknown commands stay fail-closed.

## Known work queued after P10-09

- `P10-10`: controller/SPU/game-loop frontier;
- `P10-11`: highest evidence-supported milestone;
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
