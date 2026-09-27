# OpenRecomp Phase 18 Handoff

## Summary
Phase 18 begins from the frozen Phase-17 terminal authority (tag
`openrecomp-phase17-pass`, commit
`d7cc5d09eebde398ca6ff3f3dad8dd5841913b69`, tree
`ad3aa822e5a02905ebc25477f7b6c69d0bffa055`). `P18-00` establishes the
Phase-18 control plane, re-verifies the frozen authority from live Git,
inventories imported reconnaissance as reference material, and re-derives the
GPUSTAT polling frontier from the committed P17-06R transcript.

## Invariants
1. Commit `d7cc5d09eebde398ca6ff3f3dad8dd5841913b69` is the immutable ancestor.
2. Phase-1 through Phase-17 files and evidence are frozen.
3. No guest binary bytes committed to Git.
4. Historical Phase-17 markers are preserved verbatim; Phase 18 uses its own
   `OPENRECOMP_PHASE18_*` namespace.

## Next Action
Author and execute `P18-01` (GPUSTAT polling model investigation). Author the
stage contract before claiming the stage complete. Do NOT begin Phase 19.

## Exact handoff checkpoint
- next_stage: P18-01
- The binding frontier constraint is recorded in
  `evidence/P18-00/frontier_analysis.json`: under `ZERO_FILL_RECORDED` every
  GPUSTAT read returns zero, so the guest's poll exit condition (bit 26 =
  ready-to-receive-command) can never be evaluated true. `P18-01` must
  investigate whether a faithful state-driven GPUSTAT model (not a
  title-specific constant) explains and escapes the loop, with positive and
  negative tests.
