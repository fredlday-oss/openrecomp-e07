# P12-90 — Whole Phase-12 regression

Verdict: **PASS** (66 checks, deterministic twice).

Stage marker: `OPENRECOMP_P12_90=PASS`.

## What the gate verifies

- frozen Phase-11 boundary: base commit `665d11dc` is an ancestor; the frozen
  Phase-1..Phase-11 tracked trees (excluding the new `tools/test_phase12_*`
  gates) are byte-identical between base and HEAD and the worktree is clean;
- source integrity: `OPENRECOMP_PHASE12_SOURCE_INTEGRITY=PASS`;
- every required stage `P12-00`..`P12-40` has a `PASS` `RESULT.json` marker,
  committed two-run deterministic `official_runs.json` (identical stdout,
  empty stderr, exit 0, markers present) and identical artifacts;
- no proof marker is ever reported `PROVEN` across the stages.

## Totals

- stages verified: **14**
- committed stage checks: **183**
- regression gate checks: **66**

## Reserved markers

```
OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
```

## Note on historical build identities

The earlier private-fixture stages record the native executable identity at
their own stage boundary. The shared runtime was extended incrementally
(Phase-12 service surface), which changes the compiled executable bytes but not
their observable stdout/block digests; the regression therefore verifies the
committed two-run deterministic evidence and the stable observables, not
cross-stage executable-hash equality.

## Evidence

`regression.json`, `p12_90_tests.json`, `RESULT.json`, `official_runs.json`,
`determinism.json`, run stdout/stderr.

## Next stage

`P12-91` — evidence closure.
