# P7-13 Second Private TMNT Frontier Run - Result

Verdict: `PASS` (private observation only; no ROM bytes recorded)

## Baseline

- Branch `phase7/nes-translation-frontier-v1` at the P7-12 boundary commit.

## Result

The complete private pipeline re-ran with the P7-12 closure applied:

- Inline table closed: 1 table at `$C570` (site `$C56D`, callee `$C71F`,
  6 targets, resume `$C57C`); closure walk 1255 instructions vs the
  1250-instruction baseline (delta +5).
- New frontier stop: `0xBB6B` (undocumented opcode `0xE3`), replacing the
  former `0xC570` stop; the `0x7C` byte is no longer a blocker.
- Bank-aware frontier unchanged: 530 proven / 14027 unresolved-limited
  candidate identities across 8 banks.
- Three `$E2` sites remain `RESOLVED_FINITE_SET` (4/4/300 targets).
- Translation/native build/native execution: `NOT_ATTEMPTED`; native
  execution reached: no; meaningful interactive behaviour: no.
- Exact remaining blockers: unclassified undocumented byte `0xE3` at
  `$BB6B`, unresolved bank-state candidates, runtime platform `NOT_TESTED`.

## Official gate

- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-13
  --script tools/test_phase7_private_run2_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-13 --tests-json p7_13_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 1226 bytes raw, raw sha256
    `a18cbb4a3b137e087ff02daa9b2234c462593ec9d2fe711b762154af4b8f89e4`,
    LF sha256
    `a265d36bd4c55ed03d5cff350025a2dccafe58c8109b23d73dc6a83ca62693b1`.
  - `p7_13_tests.json` sha256
    `8713d1e520b689f303ebefcae530b901b4c0de7f0552d9807f5a0fb345c044d3`,
    `tests=22`.
- Markers: `OPENRECOMP_P7_13=PASS`,
  `OPENRECOMP_PHASE7_PRIVATE_FRONTIER_RUN2_V1=PASS tests=22`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Regressions

- `tools/test_nes_rom_v1.py`: exit 0, empty stderr.
- `tools/test_phase7_translation_closure_v1.py` re-run into scratch: PASS.

## Changes

- Added `tools/test_phase7_private_run2_v1.py`.
- Updated `.openrecomp-phase7/SOURCE_SHA256SUMS.txt`, `STATE.md`,
  `STAGE_QUEUE.md`.

## Limitations

- Private observation only; TMNT playability remains `NOT_PROVEN`; no public
  claim is derived.

## Evidence index

- `RESULT.md`, `changed_files.txt`, `private_frontier_run2.json`,
  `p7_13_tests.json`, `official_runs.json`, `determinism.json`,
  `run1.txt`, `run1.err.txt`, `run2.txt`, `run2.err.txt`.

## Next stage

P7-14 Reusable bank-aware ROM-to-native workflow.
