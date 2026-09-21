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
- evidence in `.openrecomp-phase10/evidence/P10-00/` .. `P10-07/`.

## Immediate next action

`P10-08` - interrupt / DMA / timing frontier, prioritized by the dependencies
`P10-07` exposed:

1. the `I_MASK` write at `0x1f801074` (1 BLOCKER event, denied) and the
   interrupt status/mask contract (`p9_input_timer_v1.I_STAT`/`I_MASK`);
2. the 9 unrecorded denials: addresses inside the I/O window outside the
   modelled ports, or outside the modelled windows. The denied address is not
   observable; obtaining it needs either an anchored runtime substitution that
   records the first denied address, or an equivalent mechanism;
3. the deterministic virtual-time contract: timer counter reads at
   `0x1f801110` return `g_p9_ticks & 0xffff` and advance the tick; timer
   mode/target reads return 0. Determine what the guest actually depends on;
4. the bounded-execution limitation: the access budget bounds memory accesses,
   not execution. A post-truncation loop with no memory access hangs. Add a
   deterministic bound that cannot hang (for example a bounded count of
   denied/budget-denied accesses after which the runtime keeps failing
   deterministically *and* the emission cannot spin without an access), or
   record the limitation with an explicit mitigation decision;
5. the CD-ROM unknown command `0x80` is owned by `P10-09`; record the
   dependency but do not implement disc behaviour here.

Do not claim cycle accuracy; document every timing abstraction explicitly.

## Known work queued after P10-08

- `P10-09` .. `P10-11`: disc/CD-ROM/streaming, controller/SPU/game-loop,
  highest milestone;
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
