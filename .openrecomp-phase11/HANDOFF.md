# OpenRecomp Phase 11 Handoff

## Current boundary

- work branch `phase11/ps1-playability-v1`, based exactly on the Phase-10
  terminal commit `8961682aa36e14db979e8e8dbe88e04fa2b4c87a`
  (tree `4a58d9238d76a490560c588bb470fd9e6a58cafe`);
- `P11-00` `PASS` (482 checks): frozen Phase-10 boundary/integrity, fixture
  identity, frozen structure/emission identity, live milestone-A reproduction,
  inherited non-claims, control plane and frozen queue.

## Immediate next action

`P11-01` - milestone-A progress causality. Established so far by read-only
execution-budget bisection over the frozen `P10-05` build product: the first
fail-closed event is an executed unresolved indirect jump at guest access
index 9430 (all accesses before it are RAM accesses, `nonram_signatures=0`,
one MIPS host-service call), while the GPU-status/timer1 busy-poll loop is
entered later (0 GPU events at budget 250000). The exact failing site, the
executing functions and the loop's guest PCs are not yet observable; P11-01
must add a bounded, opt-in execution trace (additive host-emitter hook plus an
additive Phase-11 extension/driver), verify the trace does not change guest
semantics, establish the causal frontier, and record it.

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
