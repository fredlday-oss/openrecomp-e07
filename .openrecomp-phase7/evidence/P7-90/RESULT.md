# P7-90 Whole Regression - Result

Verdict: `PASS` (`tests=72`)

## Baseline

- Branch `phase7/nes-translation-frontier-v1` at the P7-14 boundary commit
  (`de20b6c`, then the documented P7-90 gate control updates).

## Regression coverage

- Phase-7 source manifest, root/Phase-3/Phase-4/Phase-5/Phase-6 manifests
  verified; P6-99 record hash pinned; frozen tag/commit/tree chain verified
  (Phase-5 object `b5d6832b...` -> commit `e8d3627a...` -> tree
  `468fb978...`; Phase-4/3/2/1 boundaries; Phase-6 commit
  `1643817d...`/tree `cda3f535...` with its missing terminal tag recorded).
- Phase-1 host gates re-run live: `PASS=44 FAIL=0 SKIPPED=2`, stdout raw
  sha256 `2a9d1bba...` identical to the frozen capture.
- Frozen Phase-6 whole-regression record verified: `PASS tests=83`, official
  stdout raw `120d002830037ac26d5780e0cdb820f8dbd4bd55415e6f2b9aabb08cda8c97fa`
  (2836 bytes), all 14 Phase-6 stage gates `stdout_matches_official`, and the
  Phase-5 whole-regression re-run inside it raw
  `e487dbc0...`. A live P6-90 re-run requires a ~80 minute pre-verdict
  reconstruction (the frozen P6-00 gate verifies the reserved Phase-6 terminal
  marker); this is the documented coverage boundary.
- All 15 Phase-7 stage gates `P7-00` .. `P7-14` re-run live into scratch
  evidence: exit 0, empty stderr and raw stdout byte-identical to every
  recorded official capture (P7-00 `8d5b206b...` .. P7-14 `d53e8404...`).
- No frozen history, tag, evidence or verdict was modified; all re-runs wrote
  only to `.openrecomp-phase7/scratch/P7-90/`.

## Official gate

- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-90
  --script tools/test_phase7_whole_regression_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-90 --tests-json p7_90_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 2378 bytes raw, raw sha256
    `ddbd5ba43cdf9bb71c73ae659fd10f47d36464004290c921affe082881b3dc9d`,
    LF sha256
    `8ca4da87e91de46d8828fc56bc2962390cc44eaa2564c476135a2f9ca623620b`.
  - `p7_90_tests.json` sha256
    `c0b4433bdba9cc2bd80186652fcef4dddb824500839497821e05c99b6fda88d5`,
    `tests=72`.
- Markers: `OPENRECOMP_P7_90=PASS`,
  `OPENRECOMP_PHASE7_WHOLE_REGRESSION_V1=PASS tests=72`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Changes

- Added `tools/test_phase7_whole_regression_v1.py` (committed as a documented
  pre-boundary control update) and updated the Phase-7 source manifest.
- Updated `.openrecomp-phase7/STATE.md`, `STAGE_QUEUE.md`, `HANDOFF.md`.
- No frozen file was modified.

## Evidence index

- `RESULT.md`, `changed_files.txt`, `whole_regression.json`,
  `p7_90_tests.json`, `official_runs.json`, `determinism.json`,
  `run1.txt`, `run1.err.txt`, `run2.txt`, `run2.err.txt`.

## Next stage

P7-91 Evidence index and compatibility matrix.
