# P4-91 result (PASS)

Stage: `P4-91` Evidence index + limitations (frozen queue row).
Gate: `tools/test_phase4_evidence_index_v1.py` (31 checks, sha256
`490f9afff9e7a84d2821e3c1d826b24f8facb54238d9a882d5ac184dfbe2f34a`).
Evidence: `.openrecomp-phase4/evidence/P4-91/`.

Markers issued:

- Stage marker: `OPENRECOMP_P4_91=PASS`
- Gate marker: `OPENRECOMP_PHASE4_EVIDENCE_INDEX_V1=PASS tests=31`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

## Objective (frozen queue)

Create a complete Phase-4 evidence index and explicit claim ledger separating
PROVEN, BOUNDED, UNPROVEN, UNSUPPORTED and NOT TESTED. Record every material
limitation.

## Index

- `evidence_index.json`: every file under the stage evidence directories
  `P4-00` .. `P4-91` with path, size, sha256 and tracked status
  (355 files), the seven control-plane file hashes, the frozen Phase-3
  boundary identities and the package identity
  (`phase4_package_v1.zip`, sha256 `8790bfa9bfc632270c7cbc5e6cce5bf4d890fc7aa481c1bb02f44167adcc3e6f`).
- `claim_record.json`: the claim ledger with 12 PROVEN statements,
  3 BOUNDED statements, 9 UNPROVEN areas, 6
  UNSUPPORTED behaviours, 6 NOT TESTED areas and 8
  limitations, each with impact and evidence; terminal and general
  compatibility markers reserved as `NOT_PROVEN`, `COREMARK_STATUS` and
  `GENERIC_RUNTIME_STATUS` `NOT_PROVEN`.

## Determinism

- Two consecutive official runs: exit 0, empty stderr, stdout byte-identical
  raw (`49d14f5a...`) and LF, and `p4_91_tests.json` byte-identical across both
  runs.
- Index construction is deterministic (verified twice in-gate).

## Limitations

- The index and ledger describe the audited tree; they add no capability and
  promote no marker.
- Everything remains bounded to the audited fixtures, profiles, toolchains
  and declared policies as recorded in `claim_record.json`.
- `GENERIC_RUNTIME_STATUS=NOT_PROVEN`; the terminal verdict is reserved for
  P4-99.

## Next stage

P4-99 - Final Phase-4 verdict.
