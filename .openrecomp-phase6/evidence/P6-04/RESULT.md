# P6-04 MMC1 CHR Banking and Mirroring - Result

Verdict: `PASS`

## Baseline

- Branch `phase6/nes-compat-v1` at the P6-03 boundary commit (Phase-5 frozen
  boundary `e8d3627a622d0ca3196b117c5112f29fabdb49e7`; tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).

## Objective (frozen queue)

Implement required 8 KiB / 4 KiB CHR banking and one-screen lower/upper,
vertical and horizontal mirroring; differential PPU address-mapping
verification.

## Changes (additive)

- `.openrecomp-phase6/src/p6_mapper1_chr_v1.py`: CHR banking and nametable
  mirroring consuming the P6-02 serial register file.
- `.openrecomp-phase6/src/p6_mapper1_chr_reference_v1.py`: independently
  structured reference (division/modulo, explicit branch dispatch).
- `tools/test_phase6_mmc1_chr_v1.py`: new P6-04 gate.
- `.openrecomp-phase6/src/p6_mmc1_spec_v1.py`: CHR-003 requirement text
  clarified to power-of-two 8 KiB bank counts; classifier adds the
  `chr_bank_count_not_power_of_two` reason.
- `.openrecomp-phase6/MMC1_SUBSET.md`: records CHR mode/mirroring mapping and
  the nametable layout rule.
- `.openrecomp-phase6/SOURCE_SHA256SUMS.txt`, `STATE.md`, `STAGE_QUEUE.md`,
  `HANDOFF.md`: stage bookkeeping.
- No frozen file was modified.

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-04
  --script tools/test_phase6_mmc1_chr_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-04 --tests-json p6_04_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 2949 bytes raw, raw sha256
    `cbcb3697a0c7c43915cf8d45aee5c5e060cbaec4609ed07353fe9b0ce379340d`,
    LF sha256
    `4b6b1a0889c3b35d724229e9386a6ad5dd1c9923551d935c23ec14de76600b7d`.
  - `p6_04_tests.json` sha256
    `b705944ec84042c41ffa3fd21d86658f1aa309e28f6cc174e5a4d8ef92820253`.
- Markers: `OPENRECOMP_P6_04=PASS`,
  `OPENRECOMP_PHASE6_MMC1_CHR_V1=PASS tests=61`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Contract implemented

- CHR mode 0: one 8 KiB bank `(chr_bank_0 >> 1) & (8K_bank_count - 1)`.
- CHR mode 1: two independent 4 KiB banks
  `chr_bank_0 & (4K_bank_count - 1)` and `chr_bank_1 & (4K_bank_count - 1)`
  where `4K_bank_count = 2 * 8K_bank_count`.
- Supported CHR ROM: 8 KiB .. 128 KiB with power-of-two 8 KiB bank counts
  1, 2, 4, 8, 16.
- Nametable mirroring over `$2000-$3EFF`: one-screen lower/upper fix physical
  table 0/1 for all four logical tables; vertical selects on address bit 10;
  horizontal selects on address bit 11. Physical offset
  `table * 0x400 + (address & 0x3FF)`. Palette `$3F00-$3FFF` is a separate
  pass-through and is not part of this stage's nametable mapping.

## Differential verification

- CHR: 5 bank counts x 32 control values x 32 register 0 values x 32 register 1
  values with 6 probe addresses per combination; 1,013,760 comparisons
  against the independent reference with zero mismatches (both 8 KiB and 4 KiB
  mode mappings).
- Mirroring: every address `$2000-$3EFF` (7936 addresses) for all four modes,
  comparing selected physical table and physical offset: 63,488 comparisons,
  zero mismatches.
- Explicit one-screen lower/upper, vertical, horizontal tables and offset
  examples verified; serial integration maps `$0543`/`$1543` to 4 KiB banks
  5/2 and switches mirroring to horizontal.

## Negative / fail-closed coverage

CHR bank counts 0, 3, 5, 17, 32, booleans and strings are rejected;
CHR addresses outside `$0000-$1FFF` and nametable addresses outside
`$2000-$3EFF` are rejected; state is untouched after rejection. Non-power-of-
two declared CHR sizes classify `BLOCKED_UNSUPPORTED_MMC1_VARIANT` with
`chr_bank_count_not_power_of_two`.

## Regressions

`tools/test_nes_rom_v1.py`, `tools/test_nes_platform_v1.py`, the P6-00, P6-01,
P6-02 and P6-03 gates all exit 0 with empty stderr (earlier P6 gates re-run
into ignored scratch evidence; committed evidence untouched).

## Limitations

- CHR banking and mirroring only: PRG-RAM/variant boundary and the runtime
  integration remain separate stages. No execution or PPU-rendering claim is
  made; the terminal marker remains `NOT_PROVEN`.
- Nametable mapping covers `$2000-$3EFF`; palette pass-through is reported but
  is not a P6-04 claim.

## Evidence files

`RESULT.md`, `p6_04_tests.json`, `official_runs.json`, `determinism.json`,
`chr_banking.json`, `mirroring.json`, `reference_comparison.json`,
`regressions.json`, `run1.txt`, `run2.txt`, `run1.err.txt`, `run2.err.txt`,
`changed_files.txt`.

## Next stage

P6-05 - MMC1 PRG-RAM and variant boundary.
