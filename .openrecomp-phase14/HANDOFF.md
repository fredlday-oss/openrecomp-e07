# OpenRecomp Phase 14 Handoff

## Current boundary

- work branch `phase14/ps1-hercules-init-closure-v1`, based exactly on the frozen
  Phase-13 terminal commit `7bb4502450d47a0d3f3b207a072c5729277af278`;
- `P14-00`..`P14-11`, `P14-20`, `P14-30`, `P14-40`, `P14-50`, `P14-90`, `P14-91`,
  `P14-99` all `PASS` with two-run deterministic evidence; `P14-08` is
  `PASS_NOT_REQUIRED`;
- reserved claim markers remain `NOT_PROVEN`.

## Exact next action

None. Phase 14 is complete with the bounded terminal verdict
`PASS_BOUNDED_INITIALIZATION_CLOSURE_FRONTIER_REMAINS`. The initialization proof
remains `NOT_PROVEN` at the exact technical frontier `0x1F801074` (I_STAT/I_MASK
interrupt-mask MMIO), which the frozen Phase-9 device boundary fails closed. The
next work would implement a bounded, deterministic interrupt-mask MMIO model
(and root-counter/GPU-status wait semantics) then continue toward the `A0:0x43`
`Exec` / TITLE-overlay transition.

## Proven Phase-14 results

- `OPENRECOMP_PHASE14_B0_56_GETC0TABLE_V1=PASS`;
- `OPENRECOMP_PHASE14_C0_TABLE_SURFACE_V1=PASS`;
- `OPENRECOMP_PHASE14_EARLY_CARD_PATCH_V1=PASS`;
- `OPENRECOMP_PHASE14_CARD_CONTINUATION_V1=PASS`;
- `OPENRECOMP_PHASE14_B0_57_LIVE_VALIDATION_V1=PASS`;
- `OPENRECOMP_PHASE14_CARD_INIT_CHAIN_V1=PASS`;
- `OPENRECOMP_PHASE14_CARD_IRQ_V1=NOT_REQUIRED`;
- `OPENRECOMP_PHASE14_INITIALIZATION_REPLAY_V1=PASS`.

## Exact unresolved blocker

`BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` at the interrupt-mask MMIO register
`0x1F801074` (I_STAT/I_MASK). The live initialization path reaches 14
memory-denial fail-closed events (`failed=1`,
`error="runtime memory write failed"`) around block event 467000, plus
root-counter (`0x1F801110`) and GPU-status (`0x1F801814`) polling. The inherited
initialization contract is unmet (`INIT-BOUNDARY` mechanically true,
`INIT-NO-FAIL-CLOSED` false).

## P14-90 note

`p13-source-integrity` is verified by the canonical Git-blob verifier
`.openrecomp-phase14/src/p14_frozen_phase13_integrity_v1.py` (17 entries, 1 CRLF
checkout-convention variant), and the branch-pinned Phase-13 boundary gate is
replaced by the branch-agnostic frozen-tree verifier
`.openrecomp-phase14/src/p14_frozen_phase13_boundary_v1.py`. No frozen Phase-13
file, manifest or evidence was modified.

## Verification commands

```
python .openrecomp-phase14/src/p14_source_manifest_v1.py
python .openrecomp-phase14/src/p14_frozen_phase13_integrity_v1.py
python .openrecomp-phase12/src/p12_source_manifest_v1.py
python .openrecomp-phase14/src/p14_stage_runner_v1.py \
  --stage P14-05 --script tools/test_phase14_frontier_v1.py \
  --evidence-dir .openrecomp-phase14/evidence/P14-05 --tests-json p14_05_tests.json
python .openrecomp-phase14/src/p14_stage_runner_v1.py \
  --stage P14-90 --script tools/test_phase14_whole_regression_v1.py \
  --evidence-dir .openrecomp-phase14/evidence/P14-90 --tests-json p14_90_tests.json
python .openrecomp-phase14/src/p14_stage_runner_v1.py \
  --stage P14-99 --script tools/test_phase14_final_verdict_v1.py \
  --evidence-dir .openrecomp-phase14/evidence/P14-99 --tests-json p14_99_tests.json
```

## Notes

- `THIRD_PARTY_CODE_IMPORTED=NO`;
- the frozen Phase-11/Phase-12/Phase-13 trees and all read-only reconnaissance
  directories are untouched;
- no private fixture or BIOS bytes are committed.
