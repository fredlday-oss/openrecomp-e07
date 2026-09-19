# P7-09 Native Execution of the Public Phase-7 Fixture - Result

Verdict: `PASS`

## Baseline

- Branch `phase7/nes-translation-frontier-v1` at the P7-08 boundary commit,
  descending from the frozen Phase-6 terminal commit
  `1643817d43196c43155805249137e4b4e4a21eb1`.

## Objective (frozen queue)

Build and run generated native host code exercising the newly proven
instruction/classification behaviour, bank-aware control flow, indirect
target resolution and runtime/platform interaction. No original guest
execution.

## Variants (public indirect-flow fixture)

| Variant | Runtime selector | Build | Executable sha256 | Result |
| --- | --- | --- | --- | --- |
| exact | 0 (proven single target `$8033`) | `EXECUTABLE_REPRODUCIBLE` | `23679fb8...` | `failed=0`, `exit=1`, `pc=$C205`, `steps=38`, `clock=108` |
| finite | 1 (proven set, index 2 -> `$8110`) | `EXECUTABLE_REPRODUCIBLE` | `7da08a48...` | `failed=0`, `exit=1`, `pc=$C205`, `steps=43`, `clock=123` |
| unresolved | 2 (`$8030` excluded) | `EXECUTABLE_REPRODUCIBLE` | `ea6bef23...` | `failed=1`, `error=pc outside the emitted image`, `pc=$8030`, `steps=33` |

All variants: 3 byte-identical runs (stdout and empty stderr), MMC1 runtime
state `mmc1_regs=0C000001`, PRG windows `(1, 3)` - the native runtime support
performs the bank commit and the switchable-window execution.

Path distinction: exact and finite reach the same exit thunk with distinct
RAM/state digests (`0xAA5AB26E...` vs `0x7F6B5F25...`), proving the resolved
dispatch targets executed; the unresolved variant fails closed exactly at the
excluded site with no host case emitted.

Host code only: the emitted program is the generated switch machine
(`switch (g_pc)`) with a case for the proven targets and no case for the
unresolved site; the original 6502 image is data in the deterministic runtime
support. The exact variant's executable is byte-identical to the P7-08 build.

## Official gate

- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-09
  --script tools/test_phase7_native_execution_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-09 --tests-json p7_09_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 1712 bytes raw, raw sha256
    `ac9c15e202f0b1d248785fd642671b020e51db3e3ae1db3493b4dede0637333c`,
    LF sha256
    `e393a62ca468fd50a32badae9a9d07ee05a3d6496ab249e982b0713517a35440`.
  - `p7_09_tests.json` sha256
    `d84bc50ee2a9520241cc863662aea3b4829c49137c8b5e1ef77601b7cefa7c28`,
    `tests=34`.
- Markers: `OPENRECOMP_P7_09=PASS`,
  `OPENRECOMP_PHASE7_NATIVE_EXECUTION_V1=PASS tests=34`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Changes

- Added `tools/test_phase7_native_execution_v1.py`.
- Updated `.openrecomp-phase7/SOURCE_SHA256SUMS.txt`, `STATE.md`,
  `STAGE_QUEUE.md`, `HANDOFF.md`.
- No frozen Phase-1..Phase-6 file was modified.

## Regressions

- `tools/test_nes_rom_v1.py`: exit 0, empty stderr.
- `tools/test_phase7_frontier_integration_v1.py` re-run into ignored scratch
  evidence: exit 0, empty stderr, `OPENRECOMP_P7_08=PASS`.

## Limitations

- Bounded to the three public dispatch paths; no general native dispatch of
  arbitrary indirect control flow.
- TMNT playability remains `NOT_PROVEN`.

## Evidence index

- `RESULT.md`, `changed_files.txt`, `native_execution.json`,
  `p7_09_tests.json`, `official_runs.json`, `determinism.json`,
  `run1.txt`, `run1.err.txt`, `run2.txt`, `run2.err.txt`.

## Next stage

P7-10 Independent reference equivalence.
