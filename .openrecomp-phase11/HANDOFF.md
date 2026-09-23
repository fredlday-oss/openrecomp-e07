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
- `P11-RC` `PASS` (179 checks), control-only, from baseline
  `515e3fb0e660d3c7975e3828eb3e26ac025c7cf2`: 124 committed files under
  P11-00 through P11-07 are byte-identical; the source-integrity manifest
  passes with 23 entries; P11-00/P11-07/P11-06/P11-05 pass unchanged twice at
  482/41/75/294 checks. The original P11-08 through P11-12 rows remain
  verbatim, those stages were not executed and have no verdict, and the only
  permitted route is `P11-RC -> P11-90 -> P11-91 -> P11-99`. No runtime,
  BIOS, semantic, translation, emission or guest-state behavior changes.
- `P11-90` first stopped with FAIL before a PASS boundary: in an isolated
  checkout on the exact frozen Phase-10 branch, commit and tree, the Phase-1
  host harness failed source integrity because the checkout lacked the
  pre-existing untracked `tools/test_build_package_reproducibility_v1.py`
  file listed in the frozen root manifest (the original worktree copy matches
  the manifest SHA-256
  `2b9b09386c6f530f41b4cfe3b8d9dec868ae858603e5b0bc54ae8f5c37691085`;
  the isolated harness reported 43 PASS, one FAIL and two toolchain skips).
  The audited verification-context recovery defined in `CONTROL_POLICY.md`
  then materialized the 28 hash-pinned Phase-2 files in the isolated worktree
  only from their tracked pre-untracking Git blobs at `b9356999`, and the
  re-run gate passed twice with byte-identical stdout (17588 raw bytes,
  SHA-256 `2f18d76d...`) and sidecars: `OPENRECOMP_P11_90=PASS`, 262 checks,
  empty stderr, exit 0. The failed attempt is preserved under
  `evidence/P11-90/initial-failed-attempt/`. No proof marker moved; P11-91
  and P11-99 were not started.

## Immediate next action

The P11-90 whole-project regression gate passes deterministically and its
official evidence is recorded under `.openrecomp-phase11/evidence/P11-90/`;
the Phase-11 regression repair commit is the P11-90 predecessor commit.
P11-91 and P11-99 may begin only after that commit exists; do not start,
simulate or assign a verdict to them, or to P11-08 through P11-12, before
then. The isolated Phase-10 worktree stays at
`D:/OpenRecomp/worktrees/p11-90-phase10-regression` with its recovered
verification-context files untracked. The original Phase-2/Phase-3 residue
and root untracked file remain untouched.

The P11-07 `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` result remains the exact
runtime frontier. A future licensed replacement-BIOS investigation is outside
Phase 11 and requires a new control plane, branch, architecture/license review
and explicit user authorization.

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
