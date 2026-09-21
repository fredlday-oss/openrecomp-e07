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
  statically proven method pointer `0x80016384`.

## Immediate next action

`P11-04` - milestone B: initialization completion. The exact next blocker is
the driver-method indirect call at `0x80016204` (`fn_800161ec`, block index
468281) whose source pointer `0x80016384` is a statically initialized image
value (driver structure `0x80029624`, field offset 12; the pointer occurs
exactly once in the image at `0x80029630` and starts with a function prologue).
P11-04 should translate the proven target as an additional entry point,
classify the site with explicit evidence (dynamic/static proven target set with
a fail-closed default), and continue until a post-initialization boundary can
be defined and tested; if initialization cannot be proven complete, classify
the exact remaining blocker without promoting milestone B. Instrumented and
uninstrumented build products live under `.openrecomp-phase11/build/`
(untracked).

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
