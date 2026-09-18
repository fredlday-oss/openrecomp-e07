# P5-05 NES CPU Memory Map / Mapper Model - Result

Verdict: `PASS`

## Baseline

- Branch `phase5/nes-platform-v1` at commit `b5e17e8` (P5-04 boundary).

## Objective (frozen queue)

Implement the bounded platform memory model needed by the audited fixture:
2 KiB internal RAM + mirrors, PPU register window, APU/I/O window, controller
ports, cartridge PRG mapping, mapper behaviour required by the fixture,
SRAM/PRG-RAM if applicable. Unknown mappings fail closed.

## Delivered

- New `.openrecomp-phase5/src/p5_bus_v1.py`: original bounded NES CPU bus and
  NROM (mapper 0) cartridge window:
  - 2 KiB RAM mirrored through `$1FFF`;
  - `$2000-$3FFF` routed as register `(address - $2000) & 7` to an attached
    PPU port (PPU semantics are P5-06 scope);
  - APU/IO `$4000-$4013` latches, `$4015` status, `$4017` frame-counter
    latch, `$4014` OAM DMA copying 256 bytes through the CPU bus;
  - standard controller strobe/serial protocol;
  - `$4018-$401F` and `$4020-$5FFF` fail closed; absent PRG-RAM in
    `$6000-$7FFF` fails closed; non-NROM mappers fail closed at construction;
  - NROM PRG ROM at `$8000-$FFFF` with documented 16 KiB mirroring for
    NROM-128 and ignored ROM writes.
- New `tools/test_phase5_bus_v1.py` gate.

## Differential verification (against the frozen independent platform)

- 2 KiB RAM swept and every one of the four mirrors compared: exact.
- All 8192 PPU window addresses routed with identical register indices and
  values (recording PPU port on both sides): exact (log hash recorded).
- APU/IO latches/status and `$4000-$4017` read values: exact.
- Controller protocol (three states, strobes, 14-step transcripts): exact.
- OAM DMA through `$4014`: 256-byte OAM image exact.
- Cartridge reads across all 32 KiB of PRG: exact; ignored ROM writes exact.
- Fail-closed windows (`$4018`, `$401F`, `$4020`, `$5FFF`, `$6000`, `$7FFF`,
  read and write): both implementations fail closed for every pair.
- 5000-operation deterministic mixed differential over RAM/APU/controller/PPU
  register windows: zero mismatches; final RAM/APU/controller/OAM/VRAM/palette
  and PPU register/latch state all equal.

## Negative coverage

Non-NROM mapper, invalid controller port and out-of-range addresses fail
closed with deterministic errors.

## Official gate

- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 1094 bytes raw, raw sha256
    `16f49c60d9a94eb2b4010489e60cd1cddd7885e3827f829cebbd6f59fc4ce773`,
    LF sha256
    `2783ea498ba9275e208a7e1eef79e6e21201b838143e071b3054a7f604c2d7b5`.
  - `p5_05_tests.json` sha256
    `46d7ad1a2e7c7a0828475c749eed078f7992925aa4a3ea1a556ea306b8a14a6e`.
- Markers: `OPENRECOMP_P5_05=PASS`,
  `OPENRECOMP_PHASE5_MEMORY_MAP_V1=PASS tests=21`; terminal/general reserved
  as `NOT_PROVEN`.
- Gate sha256 `be2d0b8fde58b16cd96bfe30f96ab7967e341deea0a9ade8f4babeb5fc73f828`;
  Phase-5 manifest verifies all fifteen entries.

## Regressions

`tools/test_nes_platform_v1.py` and `tools/test_nes_rom_v1.py` re-pass with
empty stderr (recorded in `regressions.json`).

## Limitations

- The PPU port is an interface at this stage; deterministic PPU semantics are
  P5-06 scope. The routing of the PPU register window is proven.
- Only NROM (mapper 0) is implemented; all other mappers fail closed.
- No cycle timing claim; the bus is a deterministic functional model.

## Evidence files

`RESULT.md`, `p5_05_tests.json`, `official_runs.json`, `determinism.json`,
`bus.json`, `regressions.json`, `run1.txt`, `run2.txt`, `run1.err.txt`,
`run2.err.txt`.

## Next stage

P5-06 - PPU boundary / deterministic graphics model.
