# P8-90 result: whole-project regression

Status: `PASS` (215 checks)

Markers:

- `OPENRECOMP_P8_90=PASS`
- `OPENRECOMP_PHASE8_WHOLE_REGRESSION_V1=PASS tests=215`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase8_whole_regression_v1.py`.

## Frozen chain verified

- Phase-7 baseline annotated tag object `b07e0f69...` -> commit `2917aa65...`
  -> tree `59529c13...`; the pinned Phase-7 terminal evidence (P7-99 record,
  P7 control-plane and manifest) re-hashes exactly;
- the frozen P7-90 record hash chain: `RESULT.md`, `p7_90_tests.json`,
  `whole_regression.json`, `determinism.json`, `official_runs.json` all equal
  their pinned hashes, and the carried P6-90 record
  (`930f6ec57ea62b8e2e5aceb0fff2fc1369eafc876f51f6bf7f933b64bd8cb37f`) and
  its official stdout
  (`120d002830037ac26d5780e0cdb820f8dbd4bd55415e6f2b9aabb08cda8c97fa`)
  match, with the frozen coverage note intact (the live P6-90 re-run requires
  the documented ~80-minute pre-verdict reconstruction);
- Phase-3/4/5 annotated tags and commits/trees, Phase-6 commit/tree, and the
  Phase-1/2/6 boundary commits as ancestors of the baseline all re-verify;
- `openrecomp-phase6-pass` remains absent; no undocumented Phase-1..Phase-7
  tracked change exists against the baseline.

## Live historical re-runs

- Phase-1 host gates: exit 0, empty stderr, stdout byte-identical
  (`2a9d1bba...`, `PASS=44 FAIL=0 SKIPPED=2`).
- All fifteen Phase-7 stage gates `P7-00`..`P7-14`: re-run live in a
  reconstructed pre-verdict worktree at the frozen P7-90 commit
  `519c0e7313eb99d6dbd83a4853c070bd5fdf5d17` (the frozen gates assert the
  reserved pre-verdict terminal marker), with scratch evidence directories so
  no frozen evidence is modified. Every gate exits 0 with empty stderr and
  stdout byte-identical to the frozen official capture, exact test counts
  preserved (`P7-04` 289 checks, total phase-7 tests 852). The temporary
  worktree is removed and pruned.

## Phase-8 official gates

All thirteen completed Phase-8 gates re-run live with exit 0, empty stderr,
their stage `PASS` markers and stdout byte-identical to the committed official
captures: `P8-00` 68, `P8-01` 89, `P8-02` 43, `P8-03` 52, `P8-04` 30, `P8-05`
36, `P8-06` 25, `P8-07` 24, `P8-08` 26, `P8-09` 24, `P8-10` 15, `P8-11` 47,
`P8-12` 130.

## Counts

- Phase-7 stage-gate tests re-verified: 852;
- Phase-8 stage-gate tests re-verified: 611;
- **total re-verified tests: 1463** plus the Phase-1 host-gate matrix.

## Official runs

Command `python tools/test_phase8_whole_regression_v1.py`, exit 0, empty
stderr, both runs byte-identical: stdout 8873 bytes, raw sha256
`29652124b5d29baa4eec705eccd6a56f771a25d92dd710a3230e66bce9885d20`, LF
sha256 `54b911a8c0ae0864b7a7be1e19e86868d47929e13cd4146af70c3d0d0eb0e6c6`.

Sidecar identities: `whole_regression.json`
`b97e35c69f649d446c01d1c833e7e7da2a8886a37d58bf9249b66189f4b5f5e7`,
`p8_90_tests.json`
`fae269c57410444fda440346985ae9d944123cf67e96c75652dcf590bd6189c9`.

## Claim-ledger delta

- New evidence: the frozen Phase-1..Phase-7 behaviour and every Phase-8
  official gate re-verify deterministically on the audited tree; no frozen
  history or evidence was modified.
- The terminal marker remains reserved `NOT_PROVEN` until P8-91 and P8-99.

## Limitations

- The Phase-7 stage gates are re-run in the reconstructed pre-verdict context
  they were frozen in; the post-verdict tree cannot satisfy their reserved
  marker assertions by construction, which is the same documented coverage
  boundary Phase 7 applied to Phase 6.
- The full P6-90 live re-run remains the frozen Phase-7 coverage boundary
  (~80 minutes) and its frozen record is verified instead.

## Next stage

P8-91: build the final Phase-8 evidence index and claim/proof matrix,
separating PROVEN, BOUNDED/PASS and NOT_PROVEN areas, and verify that no
public evidence contains unauthorized or private binary material.
