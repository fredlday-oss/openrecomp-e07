# P7-91 Evidence Index and Compatibility Matrix - Result

Verdict: `PASS` (`tests=30`)

## Baseline

- Branch `phase7/nes-translation-frontier-v1` at the P7-90 boundary commit.

## Evidence index

`index_digest` and counts are in `evidence_index.json`: every Phase-7
evidence file (excluding this stage's own in-progress directory) is indexed
with path/size/sha256/tracked status, independently re-walked and re-hashed,
and remains deterministic across runs.

## Claim ledger (five separate areas)

| Area | Status | Basis |
| --- | --- | --- |
| Phase-5 public NROM | `PROVEN` | frozen Phase-6 claim ledger (7 proven / 4 bounded) |
| Phase-6 public MMC1 | `PROVEN` | frozen Phase-6 claim ledger (11 proven / 5 bounded) |
| Phase-7 public translation/control-flow | `PROVEN` | 11 proven / 5 bounded public claims (classification, bank-aware reachability and structure, indirect evidence, public fixtures, integration, native execution, reference equivalence, closure, workflow) |
| Private TMNT compatibility | `UNPROVEN` | four observations, three blockers, playability `NOT_PROVEN` |
| General NES compatibility | `UNPROVEN` | no general claim |

All stage records P7-00..P7-14 and P7-90 are `PASS`. Eight limitations are
recorded (general NES, commercial/TMNT, universal undocumented opcodes, all
indirect recovery, arbitrary bank-switched binaries, cycle accuracy, full
PPU/APU, FDS/arbitrary 6502).

## Scope guard

The ledger rejects synthetic promotion: general-NES promotion, private
compatibility promotion, general-marker promotion, playability promotion and
Phase-7 bounded-claim demotion all fail closed.

## Official gate

- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-91
  --script tools/test_phase7_evidence_index_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-91 --tests-json p7_91_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 1453 bytes raw, raw sha256
    `63d7be7d59e989f6a64e2e30956ee4b578dc7e06c99ce257c327908f0e9b99ea`,
    LF sha256
    `74a31c7473c0f9131c007412bbb5019ad298995b1979bcd63a55fa50f9d268c4`.
  - `p7_91_tests.json` sha256
    `d08f04342df6b6c2fa9a4d0ecc7d72ed427875509c951685a2e80d26da30c862`
    in both runs.
- Markers: `OPENRECOMP_P7_91=PASS`,
  `OPENRECOMP_PHASE7_EVIDENCE_INDEX_V1=PASS tests=30`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Changes

- Added `.openrecomp-phase7/src/p7_evidence_index_v1.py` and
  `tools/test_phase7_evidence_index_v1.py`.
- Updated `.openrecomp-phase7/SOURCE_SHA256SUMS.txt`, `STATE.md`,
  `STAGE_QUEUE.md`, `HANDOFF.md`.
- No frozen file was modified.

## Evidence index

- `RESULT.md`, `changed_files.txt`, `evidence_index.json`,
  `claim_record.json`, `p7_91_tests.json`, `official_runs.json`,
  `determinism.json`, `run1.txt`, `run1.err.txt`, `run2.txt`,
  `run2.err.txt`.

## Next stage

P7-99 Final Phase-7 verdict.
