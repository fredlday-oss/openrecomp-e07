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
- `P10-09` `PASS` (46 checks): the disc identity is re-verified and the
  CD-ROM frontier is exactly classified (register-level command traffic
  only; `READ_N`/`SET_MODE`/`SET_LOCATION`, one blocked `0x80`, no data
  path reached); nothing implemented;
- `P10-10` `PASS` (36 checks): the controller/SPU/game-loop frontier is
  classified - no controller consumption, SPU configuration only, and a
  served busy-poll loop instead of a frame loop;
- `P10-11` `PASS` (38 checks): the highest demonstrated milestone is **A**,
  hash-bound to the committed stage evidence, with B..G explicitly not
  established;
- evidence in `.openrecomp-phase10/evidence/P10-00/` .. `P10-11/`.

## Immediate next action

`P10-12` - hardening and reproducibility. Required coverage:

1. malformed inputs reject deterministically (PS-X EXE ingestion negatives,
   malformed analysis records, malformed trap/memory-control evidence);
2. unsupported BREAK/exception behaviour fails closed (already covered at
   `P10-01`; re-verify against the current tree);
3. unresolved control flow fails closed (unresolved indirect call/jump stubs);
4. unknown BIOS calls fail closed (`P10-04`);
5. unknown MMIO / unknown device commands fail closed (`P10-07`..`P10-10`);
6. stale cache rejected and changed disc/executable identity invalidates cached
   analysis: the immutable-hash analysis cache must include the executable
   SHA-256, CUE SHA-256, BIN SHA-256, frontend/semantic/model/runtime/disc-model
   versions, and must not accept a hit on filename equality alone;
7. CUE/BIN material never enters repository evidence (public-safety scan over
   all committed Phase-10 evidence);
8. no original guest machine code executes at runtime (generated program has no
   guest bytes and no opcode dispatch);
9. clean native rebuild succeeds and repeated execution is deterministic
   (transcript/state identities repeat exactly);
10. record the bounded-execution limitation and its mitigation explicitly
    (default budget plus bounded host timeout; the budget bounds accesses, not
    execution).

## Known work queued after P10-12

- `P10-90`: whole-project regression (all frozen Phase-1..9 gates plus every
  completed Phase-10 official gate);
- `P10-91`: evidence index and proof matrix;
- `P10-99`: final bounded verdict.

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
