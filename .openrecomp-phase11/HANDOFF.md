# OpenRecomp Phase 11 Handoff

## Current boundary

- work branch `phase11/ps1-playability-v1`, based exactly on the Phase-10
  terminal commit `8961682aa36e14db979e8e8dbe88e04fa2b4c87a`
  (tree `4a58d9238d76a490560c588bb470fd9e6a58cafe`);
- `P11-00` `PASS` (482 checks): frozen Phase-10 boundary/integrity, fixture
  identity, frozen structure/emission identity, live milestone-A reproduction,
  inherited non-claims, control plane and frozen queue;
- `P11-01` `PASS` (583 checks): additive opt-in instrumentation, trace
  semantics equivalence, exact causal frontier (BIOS A0 call at `0x80026ccc`,
  index `0x2b`), temporal ordering by budget bisection, post-failure loops;
- `P11-02` `PASS` (1466 checks): exact BIOS vector classification of all 19
  reachable indirect sites, the causal site resolved as `ps1.bios.A0.2b`
  memset (documented semantics, checked memory boundary), public synthetic
  service fixtures, frontier movement to `A0:0x3f` printf at `0x80026cec`
  (block index 468147), and a deterministic 8,000,000 block-entry execution
  budget;
- `P11-03` `PASS` (1329 checks): the documented `A0:0x3f` printf service is
  served and verified by public synthetic fixtures; deterministic bisection
  proves the whole progress to the frontier is RAM-only (access index 506040,
  zero device traffic, zero non-RAM signatures) so no event/interrupt/DMA/
  timer/memory-control behaviour is proven necessary (zero delta); the new
  exact frontier is the driver-method indirect call at `0x80016204` with the
  statically proven method pointer `0x80016384`;
- `P11-04` `PASS` (851 checks): the frozen frontier is extended from the
  statically proven driver-method entry `0x80016384` (4068 + 264 = 4332
  reachable words; 121 functions / 793 blocks), the driver-method call is
  resolved with `EXACT_CONSTANT_TARGET` evidence through the additive guarded
  dispatch, two newly reachable op types (`nor`, `sllv`) receive independently
  verified additive rules, and the frontier moves to the documented `A0:0x49`
  GPU_cw vector call at `0x8001b424` (block index 468286). Milestone B is
  NOT promoted.
- `P11-05` `PASS` (294 checks): `GUEST_VALUE_CONFIRMED` preserves the
  diagnostic result without private payload material; the documented
  one-argument, void `A0:0x49` `GPU_cw` service submits through the frozen
  typed GP0 boundary; public original fixtures cover ordered known NOPs,
  unknown commands, malformed calls, control flow and absence of fabricated
  GPU/device state; the causal A/B records exactly one required GP0 write of
  `0x0002a244`, classified opcode `0x00` / known `NOP`, and moves the frontier
  to `0x8001882c` at block index 468323. Milestone C is PROVEN for the exact
  private fixture; B, D and G remain NOT_PROVEN. The frozen P11-04 gate passes
  unchanged at 851 checks.
- `P11-06` `PASS` (75 checks): the exact RAM pointer chain proves the observed
  target `0x8001a7dc`; extending from it adds 10 reachable words / one function
  / one block and the existing guarded exact-target dispatch resolves
  `0x8001882c`. The translated guest function reaches the frozen typed GP1
  boundary with `0x03000001`, classified known `DISPLAY_ENABLE`, then performs
  one guest RAM bookkeeping byte. A/B is byte-identical before the old
  frontier; B adds one GP1 write, one RAM write and zero host-service calls.
  No GPU/DMA/VRAM behavior is added. The new exact frontier is fail-closed
  `B0:0x57` at `0x80015fa4`, block index 468341. P11-05 passes unchanged at
  294 checks.
- `P11-07` `PASS`, rigorously bounded (41 checks): pinned PSX-SPX,
  PCSX-Redux/OpenBIOS and independent PCSX HLE sources establish B0:57 as
  no-argument `GetB0Table`, returning a mutable word-indexed B0 table guest
  pointer in `$v0`. The private caller immediately requires the 32-bit B0:0x5B
  entry and performs the publicly documented target-relative pad-error patch
  pattern (two derived pointers and eleven word clears). No public source
  establishes a portable guest B0:0x5B target/code object compatible with the
  no-BIOS-runtime scope, so the stage records
  `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`. No runtime service/table/target or
  device behavior is added; the frontier remains `0x80015fa4`, block 468341,
  and milestone D remains NOT_PROVEN. P11-06 and P11-05 pass unchanged twice.

## Immediate next action

Stop at the P11-07 `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` boundary. To resume,
obtain public evidence for a guest-addressable B0:0x5B target representation
and its required writable target-relative object, including how unsupported
readable entries remain callable fail-closed stubs, without loading or
executing a BIOS. A retail table value, private reference value, arbitrary
pointer, empty table or OpenBIOS build address alone is insufficient.

Do not start P11-08 while this serial frontier is unresolved. If adequate
public evidence becomes available, construct the bounded B variant, require an
identical prefix through block 468341, and record the exact next fail-closed
frontier. Milestone D still requires a valid rendered frame proven
semantically or by an approved non-reconstructive hash. Build products live
under `.openrecomp-phase11/build/` (untracked).

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
10 and must never be committed, deleted or altered by Phase-11 work.
