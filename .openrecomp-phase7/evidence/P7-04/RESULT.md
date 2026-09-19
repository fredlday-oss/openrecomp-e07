# P7-04 Bank-Aware Cartridge Reachability Model - Result

Verdict: `PASS`

## Baseline

- Branch `phase7/nes-translation-frontier-v1` at the P7-03 boundary commit,
  descending from the frozen Phase-6 terminal commit
  `1643817d43196c43155805249137e4b4e4a21eb1`.

## Objective (frozen queue)

Model executable reachability across MMC1 PRG bank states; track fixed and
switchable windows explicitly; associate code addresses with cartridge bank
state where required; never merge different physical bank contents that share
CPU address ranges; fail closed when bank provenance is ambiguous.

## Model

`.openrecomp-phase7/src/p7_bank_reachability_v1.py`:

- code identity is `(physical_prg_bank, cpu_address)`; a CPU address reached
  under different banks is reported in `multi_bank_cpu_addresses` and never
  merged;
- window layout comes from the frozen independent reference model
  (`p6_mapper1_prg_reference_v1.reference_window_banks`): 240 layout
  combinations across bank counts 1/2/4/8/16, control 0x00/0x04/0x08/0x0A/
  0x0C/0x0E/0x0F/0x1F and PRG values 0/1/2/3/5/7 all match;
- control-register and PRG-register provenance are tracked separately, so an
  unknown PRG value does not taint a window that mode 3 keeps fixed;
- statically unrolled five-write constant sequences commit concrete register
  values (LSB first, bit-7 shift reset, address-bit register selection);
- ambiguous writers (non-constant value, indexed/indirect store, two
  consecutive mapper writes whose cycle-adjacent suppression cannot be
  excluded) mark the affected register unresolved and expand the possible
  physical banks individually with `UNRESOLVED` provenance, bounded by
  `unresolved_limit` (4096) with `unresolved_limited` recorded;
- `PROVEN`-provenance window-spanning instructions, undecodable reachable
  opcodes and budgets fail closed (`BLOCKED_WINDOW_SPAN`,
  `BLOCKED_UNDECODABLE`, `BLOCKED_BUDGET`, `BLOCKED_TARGET_OUTSIDE`);
  `UNRESOLVED` candidates are recorded, not hard-failed.

## Verified cases

| Case | Fixture PRG sha256 | Result |
| --- | --- | --- |
| Proven commit + switchable call (4 banks, target 2) | `b7d80a86...` | `OK`, bank 2 `PROVEN` (3 instructions at `$8000`), switch value 2 / windows `(2,3)` mode 3, no merge |
| Bit-7 shift reset before the sequence (target 1) | `1781380d...` | `OK`, bank 1 `PROVEN`, switch value 1 |
| Unknown write values | `f1cc4ad8...` | `OK`, unresolved-limited; banks 0-2 have 0 proven, bank 3 keeps the 16 pre-switch proven instructions; `$8000` reached under all 4 banks (`multi_bank_cpu_addresses["32768"]=[0,1,2,3]`) |
| Consecutive MMC1 writes | `ab6cca54...` | `OK`, unresolved-limited, ambiguity recorded ("consecutive") |
| Window-spanning instruction at `$BFFF` | `1764bedb...` | `BLOCKED_WINDOW_SPAN` at `$BFFF` bank 1 (fail closed) |
| Frozen public Phase-6 MMC1 proof fixture (`9e10dce5...`) | - | `OK`, 28 proven instructions in fixed bank 3, unresolved-limited expansion, 42 unresolved mapper writes (loop-based serial writes) |

## Fail-closed / negative coverage

- Unsupported bank count, PRG size mismatch, out-of-window root, invalid
  budget/unresolved-limit all raise `BankReachabilityError`.
- A 5-node budget yields `BLOCKED_BUDGET`.
- `window_banks_partial` matches the frozen reference for all 240
  combinations including masked PRG values and single-bank images.

## Official gate

- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-04
  --script tools/test_phase7_bank_reachability_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-04 --tests-json p7_04_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 10014 bytes raw, raw sha256
    `4ff35a0ca6eb7953c5e07f7267b84e2162e4e517979f9dc55a98078f321a2ce6`,
    LF sha256
    `897f6904474dce95a7bce78a78cf6571301f94570e3493a9ede7b2afde54f99e`.
  - `p7_04_tests.json` sha256
    `12ddbd033d9ecf73946777c8ac095c411575b6a401d6b8a23de1e07a495bd35d`,
    `tests=289`.
- Markers: `OPENRECOMP_P7_04=PASS`,
  `OPENRECOMP_PHASE7_BANK_REACHABILITY_V1=PASS tests=289`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Regressions

- `tools/test_nes_rom_v1.py`: exit 0, empty stderr.
- `tools/test_phase7_classification_fixture_v1.py` re-run into ignored
  scratch evidence: exit 0, empty stderr, `OPENRECOMP_P7_03=PASS`.

## Changes

- Added `.openrecomp-phase7/src/p7_bank_reachability_v1.py` (model) and
  `.openrecomp-phase7/src/p7_bank_fixtures_v1.py` (original Apache-2.0
  synthetic fixtures).
- Added `tools/test_phase7_bank_reachability_v1.py`.
- Updated `.openrecomp-phase7/SOURCE_SHA256SUMS.txt`, `STATE.md`,
  `STAGE_QUEUE.md`, `HANDOFF.md`.
- No frozen Phase-1..Phase-6 file was modified.

## Limitations

- The model is static; it does not model cycle-adjacent MMC1 write
  suppression (two adjacent mapper writes fail closed).
- Loop-based serial write sequences (as in the Phase-6 public fixture) cannot
  be resolved statically and expand to `UNRESOLVED` candidates instead of
  proven banks; no claim is made about the private image's actual bank
  sequence.
- PRG-RAM windows are out of scope for execution.

## Evidence index

- `RESULT.md`, `changed_files.txt`, `bank_reachability.json`,
  `p7_04_tests.json`, `official_runs.json`, `determinism.json`,
  `run1.txt`, `run1.err.txt`, `run2.txt`, `run2.err.txt`.

## Next stage

P7-05 Bank-aware ProgramModel / CFG integration (with public bank-switching
fixture).
