# P18-07 fresh-root reproduction

## Purpose
Prove P18-07 does not depend on state left behind by earlier runs: the stage was
re-run against a clean, empty evidence directory and a private build root.

## Procedure
```
python3 .openrecomp-phase18/src/p18_stage_runner_v1.py --stage P18-07 \
  --script tools/test_phase18_first_frame_assessment_v1.py \
  --evidence-dir /tmp/p18_recovery/P18-07-freshroot \
  --tests-json p18_07_tests.json
```

## Result
- Return code 0, `P18-07_CHECKS=59`, `OPENRECOMP_P18_07=PASS`,
  `OPENRECOMP_PHASE18_FIRST_FRAME_ASSESSMENT=PASS`, `FIRST_FRAME_READY=NO`.
- Every produced artifact is byte-identical to the official evidence:
  `RESULT.json`, `first_frame_assessment.json`,
  `first_frame_assessment.sha256`, `causal_link_ledger.json`,
  `promotion_controls.json`, `negative_tests.json`, `p18_07_tests.json`.

VERDICT: the P18-07 result is reproducible from a clean evidence root.
