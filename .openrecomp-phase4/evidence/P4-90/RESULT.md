# P4-90 result (PASS)

Stage: `P4-90` Phase-4 whole regression audit (frozen queue row).
Gate: `tools/test_phase4_whole_regression_v1.py` (78 checks, sha256
`1c601fb560e252257c93cc25c7c8fd8b5f1453222441e03f597c81a5bac9d5cb`).
Evidence: `.openrecomp-phase4/evidence/P4-90/`.

Markers issued:

- Stage marker: `OPENRECOMP_P4_90=PASS`
- Gate marker: `OPENRECOMP_PHASE4_WHOLE_REGRESSION_V1=PASS tests=78`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

## Objective (frozen queue)

Run the complete required Phase-1, Phase-2, Phase-3 and Phase-4 regression
set from the audited Phase-4 tree. Frozen earlier proof boundaries must
remain valid.

## Audit

- Frozen boundaries re-verified: the annotated Phase-3 tag object
  `ac315245...` resolving to commit `e16e4b29...`, tree `a940f0d8...`; the
  Phase-2 (`01b1d7cb...`) and Phase-1 (`46c2f971...`) tags; descent from the
  boundary; the root manifest `76f77bbc...` (134 entries); the Phase-3
  manifest `a7d0953c...` (24 entries); the P3-99 result (`c893250b...`) and
  gate (`ba581490...`) identities; and the committed P4-00/P4-08/P4-09/P4-10
  boundary records (status PASS, no failure).
- The Phase-4 boundary gate (P4-00) re-ran with the documented dynamic
  frozen-boundary hygiene (all modified tracked Phase-4 paths held out
  including modified `tools/test_phase4_*` files, committed boundary sidecars
  restored with binary-safe `git show` bytes) and reproduced its official
  stdout byte-for-byte (`953312d0...`). Because P4-00 re-runs the frozen
  Phase-3 final verdict (P3-99), that single re-run exercises the complete
  Phase-1/Phase-2/Phase-3 chain: Phase-1 host gates, P2-99 and every Phase-3
  stage gate P3-00..P3-09 with their byte-identical stdout.
- Every Phase-4 stage gate P4-01..P4-10 re-ran from the audited tree with
  empty stderr and reproduced its recorded official stdout byte-for-byte
  (`81c96314...`, `5cfc58f1...`, `cc2f73da...`, `e55ad6cb...`,
  `849af7fd...`, `d2a59e4a...`, `76dd4cf2...`, `4449d842...`,
  `8ab7d3fa...`, `8a9769d7...`), including the full native build, end-to-end
  execution and package rebuild.
- The Phase-1 host gates (`PASS=44 FAIL=0 SKIPPED=2`, `2a9d1bba...`) and the
  public-safety scan (`ad022ff1...`) re-ran unchanged.

## Gate hardening during the stage

Two audit-gate defects were found and fixed before the audit passed:
the boundary hygiene did not hold out modified `tools/test_phase4_*` files
(pinned by the manifest), and it restored tracked files through text-decoding
`git show`, which corrupted the modified binary package ZIP and tripped the
P4-00 worktree check. Both fixes are committed on the Phase-4 branch and the
final audit runs (byte-identical) exercise the corrected gate. No stage
contract, queue row, earlier boundary or claim changed.

## Determinism

- Two consecutive official audit runs: exit 0, empty stderr, stdout
  byte-identical raw (`f7bd0e30...`) and LF (`0301654481c42b65...`), and
  `p4_90_tests.json` byte-identical across both runs.
- Evidence: `official_runs.json`, `determinism.json`,
  `whole_regression.json`, per-gate captures.

## Limitations

- The audit re-runs gates and boundary records; it does not add capability.
- The P4-10 package snapshot remains bounded to the same tree state (the
  refreshed P4-10 evidence from this audit is committed with the P4-90
  boundary).
- `GENERIC_RUNTIME_STATUS=NOT_PROVEN`; the terminal verdict remains reserved
  for P4-99.

## Next stage

P4-91 - Evidence index + limitations.
