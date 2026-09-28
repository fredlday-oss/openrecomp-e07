# P18-05 Controller Review

Stage: P18-05 - DMA / ordering-table frontier
Controller: main (OpenRecomp autonomous controller)
Branch: phase18/ps1-first-frame-frontier-v1
Reviewed against: committed contract `.openrecomp-phase18/contracts/P18-05.md`

## Provenance of this work

Controller-authored implementation (no separate worker lane was used for this
stage). The module layers a fourth additive fail-closed overlay on the frozen
P17-06R runtime on top of the P18-02/P18-03/P18-04 overlays. Controller
inspected the diff, ran the authoritative dual gate, and ran an independent
fresh-private-root reproduction.

## Independent reproduction performed

- Controller authoritative dual gate:
  `python3 .openrecomp-phase18/src/p18_stage_runner_v1.py --stage P18-05 \
   --script tools/test_phase18_dma_frontier_v1.py \
   --evidence-dir .openrecomp-phase18/evidence/P18-05 --tests-json p18_05_tests.json`
  -> runner_status PASS, exit 0, empty stderr both runs, markers present both,
  tests_json present both, raw and LF stdout byte-identical, artifacts identical.
- Fresh-private-root reproduction with `OPENRECOMP_P18_PRIVATE_BUILD_ROOT_05`
  pointed at a new directory: every P18-05 artifact byte-identical to the
  official evidence set (RESULT.json, dma_frontier.json, dma_frontier.sha256,
  dma_verdict.json, negative_tests.json, ordering_table_model.json).

## What the stage mechanically establishes

- The DMA / ordering-table frontier is a real, evidence-backed state: the
  continuation executes 8270 instructions (8192 continuation budget, stop
  CONTINUATION_BUDGET_REACHED) with zero accesses to any DMA channel register;
  the DMA tap is empty.
- Proves the reachable-not-reached distinction: the generated runtime contains
  a genuine DMA-window tap gated on exactly 0x1f801080..0x1f8010ff (single
  gate, both literals present, record function free of any guest-PC constant),
  reduced through the shared `or_p18_phys` hardware-window reducer, with the
  read and write access hooks rewired to the DMA wrappers. The frontier is
  therefore a real unreached state, not a missing code path.
- Proves the tap, register decoder and GP0 classifier are genuine via a
  controlled probe compiled against the official generated runtime source,
  driving the generated DMA entry points (the same wrappers emitted
  memory-access sites call) with channel-2 MADR/BCR/CHCR and a channel-2 CHCR
  read, yielding real DMA-frontier events bound to an authenticated owner.
- Records that no reached instruction materialises the DMA window high half
  (759 reached PCs examined against 103424 records; zero sites).
- The bounded ordering-table traversal model (alignment, cycle, depth and
  command-count bounds, end-of-list bit, per-node command classification) is
  exercised by a positive three-node chain and by negative controls.
- Negative controls fail closed: out-of-window address, unaligned MADR,
  reserved CHCR sync mode, invalid/unaligned OT start, cyclic OT chain,
  node-cap and command-cap overflow, event without authenticated owner, and
  an empty frontier with no explicit NOT_REACHED status.
- Unknown GP0 command words classify UNKNOWN and are never treated as no-ops.

## Proof boundary

- Promotes NO frame/initialization/playability property. `FIRST_FRAME_READY=NO`;
  all `OPENRECOMP_PHASE18_*` claims NOT_PROVEN.
- DMA transfer semantics remain unexercised on the authentic path: no DMA-window
  access was reached during the bounded continuation. VRAM mutation and display
  configuration remain for P18-06.
- The controlled probe is explicitly evidence class PRIVATE_FIXTURE_BOUNDED and
  is not counted as authentic-execution proof.
- Phase-17 frozen authority unchanged; Phase 1-17 namespaces untouched.

## Verdict

ACCEPTED. The stage passes its bounded contract with independent reproduction.
next_stage: P18-06.
