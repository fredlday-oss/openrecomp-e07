# P6-01 MMC1 Requirements and Fixture Inventory - Result

Verdict: `PASS`

## Baseline

- Branch `phase6/nes-compat-v1` at the P6-00 boundary commit (Phase-5 frozen
  boundary `e8d3627a622d0ca3196b117c5112f29fabdb49e7`; tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).

## Objective (frozen queue)

Define the supported MMC1 subset, inventory mapper 1 requirements, establish
an original Apache-2.0 public MMC1 fixture and inventory the private TMNT image
by metadata/hash only. No MMC1 execution capability claimed yet.

## Changes (additive)

- `.openrecomp-phase6/MMC1_SUBSET.md`: human-readable `MMC1_SUBSET_V1`
  contract.
- `.openrecomp-phase6/src/p6_mmc1_spec_v1.py`: machine-readable subset,
  26-entry requirement inventory and fail-closed classifier.
- `.openrecomp-phase6/src/p6_ines_v1.py`: MMC1-aware fail-closed ingestion
  built on the frozen Phase-5 ingestion (read-only), with power-on
  fixed-last-bank vector extraction for supported images only.
- `.openrecomp-phase6/src/p6_fixture_build_v1.py` and
  `.openrecomp-phase6/fixture/p6_public_fixture.asm`: deterministic builder
  and original Apache-2.0 MMC1 fixture source (P6-01 established revision).
- `.openrecomp-phase6/src/p6_private_fixture_v1.py`: private TMNT
  metadata/hash inventory (no bytes retained).
- `tools/test_phase6_mmc1_inventory_v1.py`: new P6-01 gate.
- `.openrecomp-phase6/SOURCE_SHA256SUMS.txt`, `STATE.md`, `STAGE_QUEUE.md`,
  `HANDOFF.md`: stage bookkeeping.
- No frozen file was modified.

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-01
  --script tools/test_phase6_mmc1_inventory_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-01 --tests-json p6_01_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 3140 bytes raw, raw sha256
    `2bfd8a5efe673085ea06cce7281d92414eebb46b10c51d5df2e9ecb16f4409d6`,
    LF sha256
    `d153a32d2fb2ebad91a944b8d7abad8ee5b827fab924bbde26b5308d7ed851f6`.
  - `p6_01_tests.json` sha256
    `69900ee9dcdb77606544d20659f167e93bca2d5733f926eaf456b02fecae12ad`.
- Markers: `OPENRECOMP_P6_01=PASS`,
  `OPENRECOMP_PHASE6_MMC1_INVENTORY_V1=PASS tests=85`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.
- Gate sha256 `57e4e07cfbe5ff3778b8e4672d9a8d2a23178167543ca02acba913c1102a27ce`;
  the Phase-6 manifest verifies the gate and every Phase-6 source entry.

## MMC1 supported subset

`MMC1_SUBSET_V1` fixes: four 5-bit registers selected by address bits 14:13;
five-write LSB-first serial protocol; bit-7 reset; documented consecutive-cycle
write suppression; power-on control `0x0C` (PRG mode 3, CHR mode 0, one-screen
lower); mirroring one-screen lower/upper/vertical/horizontal; PRG modes 0-3
with 32 KiB switching and fixed-first/fixed-last 16 KiB windows; CHR mode 0
(8 KiB) and mode 1 (two 4 KiB banks); PRG 16 KiB .. 256 KiB and CHR ROM
8 KiB .. 128 KiB bounds; no PRG-RAM/battery in the supported fixture. MMC1A/B/C
differences, SUROM/SXROM/SOROM 512 KiB variants, CHR-RAM boards,
four-screen/VS/PlayChoice and unproven board wiring are explicitly unsupported
and fail closed.

## Public MMC1 fixture

- Original Apache-2.0 fixture: 4 x 16 KiB PRG banks (bank 3 fixed last bank
  with code and vectors, banks 0-2 deterministic original data), 4 x 8 KiB CHR
  banks, horizontal mirroring, mapper 1.
- ROM SHA-256 `7d5514c7db89ae9be5cb98bc8c12f94761d187e2a52a28018fa87f0af971d833`
  (98320 bytes); PRG `2fc4064e...` (65536 bytes); CHR `4f9abd22...` (32768
  bytes); header `4e45531a040410000000000000000000`.
- Vectors: NMI `$C029`, RESET `$C000`, IRQ `$C02C`. 57 assembled
  instructions, all cross-checked against the frozen `adapters.nes6502`
  decoder; reset explicitly writes the MMC1 control/CHR/PRG registers.
- Two builds byte-identical; p6 ingestion classifies `SUPPORTED_MMC1`
  (4 PRG banks, 4 CHR banks) with stable fingerprint
  `0f985869fd3fa7366f045be4943535a39ba666a3fdd1f90f708197939a93141d`.

## Phase-5 preservation

- Phase-5 ingestion still reports mapper 1 as `BLOCKED_UNSUPPORTED_MAPPER`
  with vectors unavailable; the frozen `nes_rom_v1.make_mapper` still fails
  closed for mapper 1. The P6-01 layer is additive and does not weaken
  Phase-5 fail-closed behaviour.

## Private fixture inventory

- `PRIVATE_LOCAL_COMPATIBILITY_FIXTURE`: 262160 bytes, SHA-256
  `2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1`; NES 2.0
  container, mapper 1, submapper 0, 128 KiB PRG/CHR, horizontal mirroring, no
  trainer, no battery, no declared PRG-RAM. Cartridge contract
  `SUPPORTED_MMC1`; execution remains
  `BLOCKED_MMC1_MAPPER_NOT_YET_IMPLEMENTED` until P6-02 .. P6-05 land.
- Only hashes/metadata are recorded; no ROM bytes appear in any evidence file
  (verified by substring hygiene checks).

## Negative / fail-closed coverage

Bad magic, truncation, excess bytes, zero PRG banks, PRG size above the
supported range, CHR size above the supported range, absent CHR, battery,
declared PRG-RAM, non-zero submapper, four-screen metadata and unsupported
mapper are all rejected or classified with explicit reason codes; no test
produced a traceback.

## Regressions

`tools/test_nes_rom_v1.py` and `tools/test_nes_platform_v1.py` exit 0 with
empty stderr; raw stdout hashes recorded in `regressions.json`.

## Limitations

- P6-01 establishes the subset/fixture identity only: no MMC1 mapper execution,
  no bank switching, no equivalence claim. The terminal marker remains
  `NOT_PROVEN`.
- The fixture is the P6-01 established revision; P6-06 extends the behavioural
  coverage (bank switching, CHR switching, mirroring, graphics) over it.
- The private TMNT observation is metadata-only and outside every public
  claim.

## Evidence files

`RESULT.md`, `p6_01_tests.json`, `official_runs.json`, `determinism.json`,
`ingestion.json`, `mmc1_requirements.json`, `regressions.json`, `run1.txt`,
`run2.txt`, `run1.err.txt`, `run2.err.txt`, `changed_files.txt`.

## Next stage

P6-02 - MMC1 serial register protocol.
