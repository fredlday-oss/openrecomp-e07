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
  index `0x2b`), temporal ordering by budget bisection, post-failure loops.

## Immediate next action

`P11-02` - dynamic indirect-control frontier. The causal site is exactly
classified as a PS1 BIOS A0 jump-table call (vector `0xA0`, index `0x2b`,
service id `ps1.bios.A0.2b`, no BIOS service implemented). P11-02 must
classify the site with evidence as an external/runtime-mediated transfer and
test whether serving the proven call moves the frontier. Any BIOS service
implementation must be evidence-backed and documented; unknown or unproven
services stay fail-closed. Instrumented and uninstrumented build products live
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
