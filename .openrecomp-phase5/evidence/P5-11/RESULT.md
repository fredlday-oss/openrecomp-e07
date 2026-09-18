# P5-11 Private TMNT Compatibility Run - Result

Verdict: `PASS` (for the private analysis only; TMNT is not a public target)

## Baseline

- Branch `phase5/nes-platform-v1` at commit `bda0c12` (P5-10 boundary).

## Objective (frozen queue)

Use only `D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes`; perform a private
compatibility analysis/run and record ROM SHA-256, mapper/cartridge metadata,
reachable CPU frontier, missing mapper/PPU/APU/runtime requirements, how far
the static-recompilation pipeline gets and fail-closed blockers. No ROM bytes
committed or packaged.

## Private fixture classification

- `PRIVATE_LOCAL_COMPATIBILITY_FIXTURE`; path recorded; 262160 bytes; SHA-256
  `2a9345e6...`; PRG SHA-256 `2fbc367a...` (128 KiB); CHR SHA-256 `f9e354d5...`
  (128 KiB).
- iNES/NES 2.0 signature, mapper 1 (MMC1/SxROM family), submapper 0,
  horizontal mirroring, no trainer/battery/four-screen.

## Pipeline progress and blockers

- Ingestion succeeds (`BLOCKED_UNSUPPORTED_MAPPER` execution status).
- The frozen `make_mapper` fails closed for mapper 1, and the Phase-5
  `P5Cartridge` fails closed for non-NROM; no mapper behaviour is guessed.
- Candidate frame (explicitly `CANDIDATE / NOT PROVEN`): documented SxROM
  power-on fixed-bank frame (last PRG bank at `$C000-$FFFF`) yields candidate
  vectors NMI `$C3A3`, RESET `$FFD8`, IRQ `$C412`.
- Candidate bounded frontier (budget 20000, `CANDIDATE / NOT PROVEN`):
  351 instructions, 59 distinct opcode forms, stops at
  `decode: 0xc570: undocumented 6502 opcode 0x7c` (most plausibly data or an
  unresolved banking path, not proven code), and two control-flow targets
  outside the fixed bank (`$864C`, `$901E`) that require an MMC1 PRG-bank
  model.
- Precise blockers: `BLOCKED_UNSUPPORTED_MAPPER` (MMC1 banking, CHR banking,
  mirroring control) and `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` (out-of-bank
  targets, frontier stop). Public claim: none.

## Verification

- Two analyses byte-identical (deterministic).
- Evidence contains only hashes, metadata, addresses, counts and derived
  analysis; neither the ROM image nor the fixed bank appears in any evidence
  file (checked in-gate).

## Official gate

- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 1328 bytes raw, raw sha256
    `24a1bad9d108b84c53a6fb46bbf48ffc46756990f89dd09fe6c3bcf1f0e37281`,
    LF sha256
    `5f604ff48573be19074074026887c2feb94823eeb63248a762b784133346dd72`.
  - `p5_11_tests.json` sha256
    `8ab307adf0c34095ba549c39ae41fe519bba89c87603136aaa5dc4d9e186f3ee`.
- Markers: `OPENRECOMP_P5_11=PASS`,
  `OPENRECOMP_PHASE5_PRIVATE_COMPAT_V1=PASS tests=31`; terminal/general
  reserved as `NOT_PROVEN`.
- Gate sha256 `046ea71e66414b11bcff6fa1f3f31e4fd796f3f25b41d2507ed796b7910d4a77`;
  Phase-5 manifest verifies all twenty-seven entries.

## Regressions

`tools/test_nes_rom_v1.py` and the P5-01 ingestion gate (scratch evidence)
re-pass with empty stderr (recorded in `regressions.json`).

## Limitations

- The candidate frontier is not proven execution: mapper-1 banking is
  unsupported, so no TMNT compatibility claim is made and TMNT is not required
  to pass.
- The private image must never enter the public package; the P5-12 package
  gate re-verifies this.

## Evidence files

`RESULT.md`, `p5_11_tests.json`, `official_runs.json`, `determinism.json`,
`tmnt_analysis.json`, `blockers.json`, `regressions.json`, `run1.txt`,
`run2.txt`, `run1.err.txt`, `run2.err.txt`.

## Next stage

P5-12 - Reproducible NES package.
