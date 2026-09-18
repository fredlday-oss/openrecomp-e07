# P6-03 MMC1 PRG Banking - Result

Verdict: `PASS`

## Baseline

- Branch `phase6/nes-compat-v1` at the P6-02 boundary commit (Phase-5 frozen
  boundary `e8d3627a622d0ca3196b117c5112f29fabdb49e7`; tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).

## Objective (frozen queue)

Implement the required 32 KiB and 16 KiB PRG modes, fixed-first/fixed-last
behaviour and the bank masking required by the proven cartridge configuration;
exhaustive bounded reference vectors.

## Changes (additive)

- `.openrecomp-phase6/src/p6_mapper1_prg_v1.py`: MMC1 PRG window mapping
  consuming the P6-02 serial register file.
- `.openrecomp-phase6/src/p6_mapper1_prg_reference_v1.py`: independently
  structured reference (modulo arithmetic, dispatch decoding).
- `tools/test_phase6_mmc1_prg_v1.py`: new P6-03 gate.
- `.openrecomp-phase6/src/p6_mmc1_spec_v1.py`: PRG-004/PRG-005 requirement
  text clarified to power-of-two bank counts; classifier adds the
  `prg_bank_count_not_power_of_two` reason.
- `.openrecomp-phase6/MMC1_SUBSET.md`: records the masking rule and the
  power-of-two bank-count bound.
- `.openrecomp-phase6/SOURCE_SHA256SUMS.txt`, `STATE.md`, `STAGE_QUEUE.md`,
  `HANDOFF.md`: stage bookkeeping.
- No frozen file was modified.

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-03
  --script tools/test_phase6_mmc1_prg_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-03 --tests-json p6_03_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 2444 bytes raw, raw sha256
    `13b2b2f178ab260e583f14de9461c800c148ae4e8fd1072ad9f6af4405f05c55`,
    LF sha256
    `949380183b9cee6802677b98f9473ae99ef5728ce106dc552f968148ca40203e`.
  - `p6_03_tests.json` sha256
    `d789ee8937ee458b267321bb3f00b45fb22270ed60698c2a2a3ecb826d3b4531`.
- Markers: `OPENRECOMP_P6_03=PASS`,
  `OPENRECOMP_PHASE6_MMC1_PRG_V1=PASS tests=50`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Contract implemented

- 32 KiB modes (control PRG mode 0/1): register low bit ignored, selected
  32 KiB bank covers both `$8000-$BFFF` and `$C000-$FFFF`.
- Mode 2: bank 0 fixed at `$8000-$BFFF`, register bank at `$C000-$FFFF`.
- Mode 3: register bank at `$8000-$BFFF`, last bank fixed at `$C000-$FFFF`.
- Bank masking: `bank = register & (bank_count - 1)` with power-of-two bank
  counts 1, 2, 4, 8, 16 (16 KiB .. 256 KiB).
- Power-on mode 3 maps `(0, last)` as documented.

## Differential verification

- Exhaustive bounded vectors: 5 bank counts x 32 control values x 32 register
  values = 5120 combinations, with 40960 address-mapping comparisons over
  window boundaries; zero mismatches against the independent reference.
- 160 mode 0/1 equivalence checks (the low register bit is ignored) and 480
  explicit fixed-first/fixed-last/32 KiB semantic checks.
- Serial integration: control `0x0F` and PRG register `2` committed through
  the P6-02 serial file produce window banks `(2, 3)` and the expected ROM
  offsets; public 4-bank layout `(0, 3)` and private 8-bank contract layout
  `(0, 7)`.

## Negative / fail-closed coverage

Bank counts 0, 3, 5, 17, 32, booleans and strings are rejected; addresses
below `$8000`, above `$FFFF` and booleans are rejected; state is untouched
after rejection. Non-power-of-two declared PRG sizes classify
`BLOCKED_UNSUPPORTED_MMC1_VARIANT` with `prg_bank_count_not_power_of_two`.

## Regressions

`tools/test_nes_rom_v1.py`, `tools/test_nes_platform_v1.py`, the P6-01, P6-02
and P6-00 gates all exit 0 with empty stderr (earlier P6 gates re-run into
ignored scratch evidence; committed evidence untouched).

## Limitations

- PRG banking only: CHR banking, mirroring and PRG-RAM remain separate stages.
  No execution claim is made; the terminal marker remains `NOT_PROVEN`.
- Non-power-of-two PRG ROM sizes and bank counts above 16 are explicitly
  unsupported rather than guessed.

## Evidence files

`RESULT.md`, `p6_03_tests.json`, `official_runs.json`, `determinism.json`,
`prg_banking.json`, `reference_comparison.json`, `regressions.json`,
`run1.txt`, `run2.txt`, `run1.err.txt`, `run2.err.txt`, `changed_files.txt`.

## Next stage

P6-04 - MMC1 CHR banking and mirroring.
