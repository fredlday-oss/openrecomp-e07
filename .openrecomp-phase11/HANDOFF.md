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
  budget.

## Immediate next action

`P11-03` - event / interrupt / DMA progress contract. The remaining BIOS
surface is exactly enumerated (see `evidence/P11-02/frontier.json`):
`A0:0x3f` printf, `A0:0x30` srand, `A0:0x44` FlushCache, `A0:0x49` GPU_cw,
`A0:0x70` _bu_init, `A0:0x43` DoExecute, `B0:0x12`/`0x13`/`0x3f`/`0x4a`/`0x4b`/
`0x56`/`0x57` and `C0:0x02`/`0x03`/`0x0a`. P11-03 must determine by causal A/B
whether initialization requires interrupt delivery/acknowledgement, DMA
completion, timer transitions or memory-control state, implement only
proven-necessary behaviour, and keep unproven interactions fail-closed.
Instrumented and uninstrumented build products live under
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
