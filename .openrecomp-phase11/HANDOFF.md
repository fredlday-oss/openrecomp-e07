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

## Immediate next action

`P11-05` - GPU command-stream frontier. The exact next blocker is the
documented `A0:0x49` GPU_cw vector call at `0x8001b424` in `fn_8001b420`
(source `$t2` = `0x000000a0`, delay slot holds index `0x49`). P11-05 must
classify the request (the command word argument and its provenance, the call
site context, the register state), determine by causal A/B whether serving it
is required for progress, and implement only the evidence-required behaviour
through the frozen Phase-9 typed GPU boundary (known commands served, unknown
commands fail closed). Milestone C may be promoted only if genuine GP0/GP1
command writes are reached, ordered deterministically and classified; GP1
status polling alone does not qualify. Record the exact new frontier either
way. Working-tree note: the P11-02 gate's rule-count expectation is now
surface-relative to accommodate the growing additive rule set; its printed
stdout is unchanged. Instrumented and uninstrumented build products live under
`.openrecomp-phase11/build/` (untracked).

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
