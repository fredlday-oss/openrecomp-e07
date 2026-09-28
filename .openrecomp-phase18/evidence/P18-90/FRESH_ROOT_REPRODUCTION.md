# P18-90 fresh / private-root reproduction

## Purpose
Prove the P18-90 integrated-regression gate does not depend on state left
behind by earlier runs: the gate and the authoritative dual-run stage runner
were re-executed against a clean, empty, private evidence root.

## Procedure
```
FRESH=<private-root>/p18_recovery/P18-90-freshroot
rm -rf "$FRESH"                       # asserted absent before the run
python3 .openrecomp-phase18/src/p18_stage_runner_v1.py --stage P18-90 \
  --script tools/test_phase18_whole_regression_v1.py \
  --evidence-dir "$FRESH" --tests-json p18_90_tests.json
```

## Result
- Return code 0; `P18-90_CHECKS=142`; `OPENRECOMP_P18_90=PASS`;
  `OPENRECOMP_PHASE18_WHOLE_REGRESSION_CONSISTENCY_V1=PASS`;
  `FIRST_FRAME_READY=NO`.
- Dual-run reproducibility holds inside the fresh root: identical raw and
  LF-normalized stdout, empty stderr both runs, zero exit both, byte-identical
  artifacts across both fresh runs.

## Artifact equality vs. the official evidence root
Every semantic artifact is byte-identical to the official P18-90 evidence:
`RESULT.json`, `closure.json`, `control_documents.json`,
`frontier_digests.json`, `frozen_phase17.json`, `manifest_audit.json`,
`marker_ledger.json`, `negative_tests.json`, `p18_90_tests.json`,
`public_safety.json`, `revalidation.json`, `stale_digest.json`,
`determinism.json`; plus `run1.txt`/`run2.txt`.

### The single permitted divergence
`official_runs.json` differs by exactly the embedded evidence-directory string
that the runner records as its own command display
(`.openrecomp-phase18/evidence/P18-90` vs the private roots' path). A
`json`-normalized diff shows only those two `"command"` entries differing;
`determinism.json` — which captures the reproducibility verdict itself — is
byte-identical. This is the same non-semantic runner-bookkeeping exclusion the
P18-07 fresh-root reproduction used, and it changes no stage verdict, no
marker and no frontier digest.

VERDICT: the P18-90 result is reproducible from a clean private root. The only
divergence is the runner's own self-recorded output path, which carries no
semantic content.
