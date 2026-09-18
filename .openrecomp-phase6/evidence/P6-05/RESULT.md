# P6-05 MMC1 PRG-RAM and Variant Boundary - Result

Verdict: `PASS`

## Baseline

- Branch `phase6/nes-compat-v1` at the P6-04 boundary commit (Phase-5 frozen
  boundary `e8d3627a622d0ca3196b117c5112f29fabdb49e7`; tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).

## Objective (frozen queue)

Implement the PRG-RAM behaviour required by the supported fixture; explicitly
classify unsupported MMC1 board variants/features; do not infer board wiring
not proven by cartridge evidence.

## Changes (additive)

- `.openrecomp-phase6/src/p6_mapper1_variant_v1.py`: disabled PRG-RAM window
  contract and the V-001 .. V-012 variant ledger/classifier.
- `tools/test_phase6_mmc1_variant_v1.py`: new P6-05 gate.
- `.openrecomp-phase6/MMC1_SUBSET.md`: records the supported profile, disabled
  window and the variant ledger.
- `.openrecomp-phase6/SOURCE_SHA256SUMS.txt`, `STATE.md`, `STAGE_QUEUE.md`,
  `HANDOFF.md`: stage bookkeeping.
- No frozen file was modified.

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-05
  --script tools/test_phase6_mmc1_variant_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-05 --tests-json p6_05_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 2761 bytes raw, raw sha256
    `315fd5eaf7ca5bc1ff190c38ebb50d66d6af7785c0f9bfb38e7dbbf11279d6d4`,
    LF sha256
    `d1a6b25f66f1eed6a38038fd693997abcd6e88b5000db199c8f111779dfe6246`.
  - `p6_05_tests.json` sha256
    `deb10bca4db4efc7acc93b781ffc6f0e5ef7a1182ba4649da4c691cb8406ea85`.
- Markers: `OPENRECOMP_P6_05=PASS`,
  `OPENRECOMP_PHASE6_MMC1_VARIANT_V1=PASS tests=61`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Contract implemented

- Supported profile `discrete_mmc1_chr_rom_no_wram`: declared PRG-RAM/NVRAM 0,
  no battery, power-of-two PRG/CHR bank counts, submapper 0.
- The `$6000-$7FFF` PRG-RAM window is disabled: reads and writes fail closed.
- Declared PRG-RAM/NVRAM or battery fails closed at construction; wiring is
  never inferred from cartridge metadata or private-image behaviour.
- The V-001 .. V-012 ledger classifies board variants explicitly; only V-001
  is supported and V-011 (clone/FPGA implementations) is `NOT_TESTED`.

## Verification

- PRG-RAM contract verified for the public fixture and the private TMNT
  metadata: window disabled, no declared RAM/battery; boundary reads/writes
  (`$6000`, `$7000`, `$7FFF`), out-of-window addresses, boolean addresses,
  non-8-bit values and declared-RAM/battery constructions all fail closed.
- Deterministic classifications verified for eleven probes: battery,
  PRG-RAM, CHR-RAM, non-zero submapper, four-screen, VS UniSystem,
  PlayChoice, three-bank PRG, three-bank CHR, 512 KiB PRG and mapper 2;
  every status and variant label matched the expected explicit value.
- Public and private contract classification both `SUPPORTED_PROFILE` with no
  variant labels.

## Regressions

`tools/test_nes_rom_v1.py`, `tools/test_nes_platform_v1.py` and the P6-00 ..
P6-04 gates all exit 0 with empty stderr (earlier P6 gates re-run into ignored
scratch evidence; committed evidence untouched).

## Limitations

- PRG-RAM support is exactly "disabled window": no board with declared
  PRG-RAM/NVRAM is supported, and the private TMNT classification is a
  contract classification only (no execution claim). The terminal marker
  remains `NOT_PROVEN`.
- Board wiring, MMC1A/B/C differences and clone behaviour remain explicitly
  outside the supported subset.

## Evidence files

`RESULT.md`, `p6_05_tests.json`, `official_runs.json`, `determinism.json`,
`prg_ram.json`, `variants.json`, `regressions.json`, `run1.txt`, `run2.txt`,
`run1.err.txt`, `run2.err.txt`, `changed_files.txt`.

## Next stage

P6-06 - Public MMC1 proof fixture.
