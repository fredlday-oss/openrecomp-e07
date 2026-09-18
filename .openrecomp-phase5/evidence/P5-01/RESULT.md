# P5-01 NES/iNES Ingestion and Inventory - Result

Verdict: `PASS`

## Baseline

- Branch `phase5/nes-platform-v1` at commit `cca089e` (P5-00 boundary);
  Phase-4 frozen tag `openrecomp-phase4-pass` = `b3c71fb...` remains the
  baseline.

## Objective (frozen queue)

Implement/verify fail-closed iNES/NES 2.0 ingestion sufficient for the
selected fixtures; inventory header format, PRG ROM, CHR ROM/RAM,
mapper/submapper, mirroring, trainer, battery flag, vectors, reset entry,
interrupt vectors and unsupported metadata. Never guess unsupported mapper
behaviour.

## Public fixture (original, Apache-2.0)

- New source `.openrecomp-phase5/fixture/p5_public_fixture.asm`, assembled by
  the original deterministic Phase-5 assembler
  `.openrecomp-phase5/src/p5_fixture_asm_v1.py`, packed by
  `.openrecomp-phase5/src/p5_fixture_build_v1.py`.
- NROM-128 mapper 0, 16 KiB PRG, 8 KiB original CHR pattern, horizontal
  mirroring, vectors NMI `$C196`, RESET `$C000`, IRQ `$C1F7`.
- ROM SHA-256 `272c94cdc79463cd1020ff14db1892ba56af07e4cfda97f5f1df89dd807772b9`
  (24592 bytes); PRG `66e01e75...`; CHR `3280d502...`.
- The program exercises documented 6502 instructions/addressing modes (zero
  page, absolute, indexed with page crossing, indexed-indirect,
  indirect-indexed, relative branches, RMW, stack, flags), reset/NMI/IRQ
  vectors, one software BRK, PPU register use (PPUCTRL/PPUMASK/PPUSTATUS/
  PPUSCROLL/PPUADDR/PPUDATA/OAMADDR/OAMDATA/OAM DMA), controller serial reads
  into a per-frame transcript, the 2A03 SED/ADC binary-only behaviour, and a
  declared indirect run-exit service thunk at the NMOS page-wrap vector
  `$02FF`.
- All 231 assembled instructions cross-check (opcode, length, operands,
  branch targets) against the frozen `adapters.nes6502` decoder; two builds
  are byte-identical.

## Ingestion/inventory layer

- New `.openrecomp-phase5/src/p5_ines_v1.py`: wraps the frozen Phase-1 parser
  read-only, adds exact declared-size validation (truncation and trailing
  bytes fail closed), documented NES 2.0 sub-field inventory, extended/
  exponent size-form rejection, mapper/submapper classification, NROM-only
  vector extraction with an explicit unavailable status elsewhere, and an
  execution status with unsupported mappers blocked. The document contains
  only metadata/hashes/addresses, never ROM program bytes.

## Private fixture inventory (metadata only, never copied)

- `D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes`: 262160 bytes, SHA-256
  `2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1`.
- iNES/NES 2.0 signature, mapper 1 (MMC1 family), submapper 0, 128 KiB PRG,
  128 KiB CHR, horizontal mirroring, no trainer/battery/four-screen.
- PRG SHA-256 `2fbc367a...`, CHR SHA-256 `f9e354d5...`.
- Vectors unavailable (unsupported mapper; never guessed);
  `execution_status=BLOCKED_UNSUPPORTED_MAPPER`; the frozen `make_mapper`
  fails closed exactly as required.

## Negative/fail-closed coverage

Bad magic, truncated image, oversized image, zero PRG banks, NES 2.0
extended-size form, NES 2.0 PRG-size MSB declaration: all fail closed with
deterministic errors and no traceback. A crafted mapper-5 image is classified
and blocked rather than guessed.

## Official gate

- `python .openrecomp-phase5/src/p5_stage_runner_v1.py --stage P5-01
  --script tools/test_phase5_ingestion_v1.py --evidence-dir
  .openrecomp-phase5/evidence/P5-01 --tests-json p5_01_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 2074 bytes raw, raw sha256
    `6a895e0bce6015cc6086413245fddce1e27ffdc0433c745b1216228e2c3e4c98`,
    LF sha256
    `89a396952443ec2639231b37c924af2f5dad53cb4bc9142e612cbc86908cff43`.
  - `p5_01_tests.json` sha256
    `e2734be9192a22d2f961f8221cca38777b5f7b2adb4d7adf81842666ed1e9cb9`.
- Markers: `OPENRECOMP_P5_01=PASS`,
  `OPENRECOMP_PHASE5_INGESTION_INVENTORY_V1=PASS tests=53`,
  terminal/general markers reserved as `NOT_PROVEN`.
- Gate sha256 `2d4e8f8f9a5c1556cff89e0d366375c4501aa9f0320174c8ff6827dd42e2d1d5`;
  Phase-5 manifest verifies all seven entries.

## Regressions

`tools/test_nes_rom_v1.py` and `tools/test_nes_platform_v1.py` re-pass with
empty stderr (recorded in `regressions.json`); the frozen
`tools/nes_rom_v1.py` CLI accepts the public fixture with
`OPENRECOMP_NES_ROM_V1=PASS`.

## Evidence hygiene

No evidence file contains the public or private ROM byte images (checked
in-gate). The build is pure and writes no ROM file; ROM bytes exist only in
process memory and in the external private fixture location.

## Limitations

- The public fixture is an original bounded program, not a general NES
  software corpus; no general NES or mapper compatibility is claimed.
- NES 2.0 exponent/extended size forms are explicitly unsupported and fail
  closed.
- Vector extraction is proven only for the mapper-0 CPU mapping; the private
  mapper-1 image's vectors remain unavailable and blocked.

## Evidence files

`RESULT.md`, `p5_01_tests.json`, `official_runs.json`, `determinism.json`,
`ingestion.json`, `regressions.json`, `run1.txt`, `run2.txt`,
`run1.err.txt`, `run2.err.txt`.

## Next stage

P5-02 - 2A03/6502 decode + reachable instruction frontier.
