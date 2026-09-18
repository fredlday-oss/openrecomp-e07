# P5-91 Evidence Index + Compatibility Limitations - Result

Verdict: `PASS`

## Baseline

- Branch `phase5/nes-platform-v1` at commit `291b239` (P5-90 boundary).

## Objective (frozen queue)

Create a complete evidence index and claim ledger separating PROVEN, BOUNDED,
UNPROVEN, UNSUPPORTED and NOT TESTED, and clearly separating the legal public
fixture result, the private TMNT compatibility observations and general NES
compatibility.

## Index

- `evidence_index.json`: every file under `.openrecomp-phase5/evidence/`
  for stages `P5-00` .. `P5-12` and `P5-90` (path, size, sha256, tracked
  status), the eight control-plane file hashes, the Phase-5 manifest entries,
  the frozen Phase-1..Phase-4 boundary identities and the package identity
  (`phase5_nes_package_v1.zip`,
  sha256 `447f72cc616d80fa72e3681c5acd34b00833d7e3fe3fb5bf8bf3230347cc4c13`).
- The gate independently walks the filesystem and verifies every indexed file
  and control-plane hash.

## Claim ledger

- Public fixture result (separate section): 12 PROVEN statements, 4 BOUNDED
  statements.
- Private TMNT observations (separate section, non-redistributed, no public
  claim): 4 observations including the recorded private SHA-256, the
  fail-closed mapper classification and the candidate frontier/blockers.
- General NES compatibility (separate section): status `NOT_PROVEN` with
  7 UNPROVEN areas, 4 UNSUPPORTED behaviours and 6 NOT TESTED areas.
- Vocabulary explicitly recorded (`PROVEN`, `BOUNDED`, `UNPROVEN`,
  `UNSUPPORTED`, `NOT TESTED`); terminal and general markers remain
  `NOT_PROVEN`.

## Official gate

- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 1150 bytes raw, raw sha256
    `33b23f588eb58dcc253e9c09bc0734df641d83c2b88fa6d105ae6a23fa817738`,
    LF sha256
    `af7c7c060949bc445d0c03a4469c5177316f7f329b715d5a77bf5681da133e73`.
  - `p5_91_tests.json` sha256
    `37b0fce80110e9fa06bdc5d974cb2b544bf75649d0c278966f80797b1d92c861`.
- Markers: `OPENRECOMP_P5_91=PASS`,
  `OPENRECOMP_PHASE5_EVIDENCE_INDEX_V1=PASS tests=26`; terminal/general
  reserved as `NOT_PROVEN`.
- Gate sha256 `31d81d25830449f66e43003252a0ada53b2a422285deb1e9e076648c54c81db0`.

## Regressions

`tools/test_phase5_tmnt_private_v1.py` (scratch evidence) and
`tools/test_nes_rom_v1.py` re-pass with empty stderr.

## Limitations

- The index and ledger describe the audited tree; they add no capability and
  promote no marker.
- Everything remains bounded to the audited fixtures, plans, profiles and
  documented policies.

## Evidence files

`RESULT.md`, `p5_91_tests.json`, `official_runs.json`, `determinism.json`,
`evidence_index.json`, `claim_record.json`, `regressions.json`, `run1.txt`,
`run2.txt`, `run1.err.txt`, `run2.err.txt`.

## Next stage

P5-99 - Final Phase-5 verdict.
