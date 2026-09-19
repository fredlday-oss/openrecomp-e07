# P7-11 Private TMNT Frontier Run - Result

Verdict: `PASS` (private observation only; no ROM bytes recorded)

## Baseline

- Branch `phase7/nes-translation-frontier-v1` at the P7-10 boundary commit.

## Result

`.openrecomp-phase7/src/p7_private_frontier_v1.py` re-ran the private image
through the P7 machinery (classification, bank-aware reachability, indirect
evidence) against the frozen P6-10 anchor:

- Identity: 262160 bytes, SHA-256 `2a9345e6...` (unchanged).
- `0xC570`: the bank-aware walk still stops there (bank 7,
  `NES6502Error: undocumented 6502 opcode 0x7c`), but the byte is classified
  `DATA_NOT_CODE`: a 6-entry inline dispatch table (12 bytes) with code
  resuming at `0xC57C`; closure not yet applied.
- Three `$E2` sites: all `RESOLVED_FINITE_SET` - `0x86E8` bank 0 `PROVEN`
  (4 targets), `0x8956` candidate bank 0 (4 targets), `0x8F3C`
  `MODEL_UNREACHED` (300 feasible pairs over 8 banks).
- Bank-window frontier: 530 proven / 14027 unresolved-limited candidate
  identities across 8 physical banks (P6 power-on candidate: 1250 / 1048 low
  window) - `EXPANDED`.
- Translation: `NOT_ATTEMPTED` (incomplete proven frontier); native
  build/execution not reached. TMNT playability remains `NOT_PROVEN`.
- Blockers recorded: classified data table not skipped (needs P7-12
  closure), unresolved bank candidates remain, runtime platform `NOT_TESTED`.

## Official gate

- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-11
  --script tools/test_phase7_private_frontier_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-11 --tests-json p7_11_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 1255 bytes raw, raw sha256
    `5595d97801aeb230b2e74137e053a3a4330eb0cd6ed46aa3a934ae65d1f5483e`,
    LF sha256
    `dff3c3c6fc2c1d8c76b30d8c56f0b3451861b765021b76e81332595f365137e6`.
  - `p7_11_tests.json` sha256
    `ba137a655a5cc069d6584b590a685517eca06722755ea56ef529543a72f37ce5`,
    `tests=24`.
- Markers: `OPENRECOMP_P7_11=PASS`,
  `OPENRECOMP_PHASE7_PRIVATE_FRONTIER_RUN_V1=PASS tests=24`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Regressions

- `tools/test_nes_rom_v1.py`: exit 0, empty stderr.
- `tools/test_phase7_indirect_evidence_v1.py` re-run into scratch: PASS.

## Changes

- Added `.openrecomp-phase7/src/p7_private_frontier_v1.py` and
  `tools/test_phase7_private_frontier_v1.py`.
- Updated `.openrecomp-phase7/SOURCE_SHA256SUMS.txt`, `STATE.md`,
  `STAGE_QUEUE.md`.

## Limitations

- Private observation only; no public or general claim; TMNT playability not
  demonstrated.

## Evidence index

- `RESULT.md`, `changed_files.txt`, `private_frontier.json`,
  `p7_11_tests.json`, `official_runs.json`, `determinism.json`,
  `run1.txt`, `run1.err.txt`, `run2.txt`, `run2.err.txt`.

## Next stage

P7-12 Evidence-driven translation closure.
