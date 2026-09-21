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
- evidence in `.openrecomp-phase10/evidence/P10-00/` .. `P10-06/`.

## Immediate next action

`P10-07` - GPU command execution frontier.

The unblocking infrastructure is already in place: the additive Phase-10
observable driver `.openrecomp-phase10/runtime/p10_observable_driver_v1.c`
prints the bounded-execution counters and the typed platform event transcripts
(`ev_<device>_<i>=service,direction,width,flags,address,value`; GPU up to 4096,
the other devices up to 64). Select it with
`p10_emission_v1.build_build_set(..., driver="phase10")`.

Already observed with that driver on the private executable (a full
build+run cycle, recorded here so it does not have to be rediscovered):

- GPU: 4096 recorded events (capped) whose first 64 are all GP1 `RESET_GPU`
  (`0x1f801814`, command `0x00`); the GPU stream is therefore dominated by
  repeated reset sequences early on. Classify the whole recorded prefix with
  `p9_gpu_boundary_v1.classify_gp0` / `classify_gp1` and report the class
  histogram, the GP0/GP1 split and the unknown-command count.
- CD-ROM: 38 events: index/status writes (`0x1f801800`), parameter writes
  (`0x1f801802` values `0x80`, `0x00`, `0x03`), and one BLOCKER event at
  `0x1f801801` with value `0x80` (unknown CD-ROM command, fail-closed denial).
- SPU: 5 events: volume writes `0x3fff` at `0x1f801db0`/`0x1f801db2`, control
  write `0xc001` at `0x1f801daa`, and reads of `0x1f801db8`/`0x1f801dba`.
- Controller/timers: `I_MASK` write at `0x1f801074` (BLOCKER, denied - interrupt
  ports are not modelled) and timer1 counter reads at `0x1f801110` returning the
  deterministic virtual tick.
- 11 denied accesses in total and 79 Phase-10 MIPS service calls with 0 service
  failures.

P10-07 PASS requires the required GP0/GP1 command classes, the DMA interaction
classification (the observed GPU path is CPU port writes; no DMA-controller
register range is modelled, so any DMA assumption must stay explicit) and the
VRAM state required for progress, with deterministic command evidence - or an
explicit `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` record for anything the
transcript cannot decide.

## Known work queued after P10-07

- `P10-08` .. `P10-11`: interrupt/DMA/timing, CUE/BIN CD-ROM/filesystem/
  streaming, SPU/controller/game-loop, highest milestone;
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
