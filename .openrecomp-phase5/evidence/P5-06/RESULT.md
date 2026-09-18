# P5-06 PPU Boundary / Deterministic Graphics Model - Result

Verdict: `PASS`

## Baseline

- Branch `phase5/nes-platform-v1` at commit `4b4da23` (P5-05 boundary).

## Objective (frozen queue)

Implement a Phase-5-bounded PPU/platform interface sufficient for the public
fixture, kept behind the Phase-4 graphics boundary. Record nametable/palette/
OAM access, register semantics required by the fixture, frame/vblank timing
assumptions and unsupported PPU behaviours. Do not claim full PPU or cycle
accuracy.

## Delivered

- New `.openrecomp-phase5/src/p5_ppu_v1.py`: original deterministic
  CPU-facing PPU register/memory surface:
  - `$2000-$2007` register semantics including PPUSTATUS read side effects,
    shared write latch, OAMDATA increment, PPUSCROLL ordering, PPUADDR high/
    low and the PPUDATA one-byte read buffer with immediate palette reads;
  - PPU memory: CHR (ROM read-only / optional RAM), 2 KiB VRAM with the
    documented horizontal/vertical nametable mapping, `$3000-$3EFF` mirrors,
    palette with `$3F10/$3F14/$3F18/$3F1C` mirrors, greyscale read masking;
  - deterministic vblank event surface (`set_vblank`, `nmi_enabled`) for the
    P5-07 delivery boundary;
  - bounded graphics observation: a 32x30 GRAY8 tile-space `RuntimeFrame`
    (one byte per nametable tile) plus canonical PPU state digests,
    transported through the Phase-4 `HeadlessGraphics` boundary. This is a
    bounded state model, not emulated video output.
- New `tools/test_phase5_ppu_v1.py` gate.

## Differential verification (against the frozen independent PPU)

- 3000-step deterministic register script over all eight registers with the
  documented latch behaviour: zero mismatches; full PPU state (registers,
  latches, VRAM, palette, OAM) compared at every step.
- All 16384 PPU memory addresses: reads exact; writes exact; all 8192 CHR-ROM
  writes fail closed on both sides.
- Nametable mirroring verified for both horizontal and vertical arrangements
  across `$2000-$3EFF`.
- Frame observation: deterministic, sensitive to VRAM change, correct
  dimensions/format/payload, and accepted by the Phase-4 graphics boundary
  with the exact frame checksum recorded.
- Timing assumptions documented: explicit vblank event, NMI delivery at
  instruction boundaries (P5-07), virtual NTSC nominal frame model, and no
  cycle/sprite/zero-hit/fine-scroll/four-screen claims.

## Negative coverage

Four-screen mirroring, CHR-ROM writes, unknown registers and out-of-range
addresses fail closed; the module contains no renderer/audio-backend tokens
(Phase-4 no-mandatory-backend rule).

## Official gate

- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 1534 bytes raw, raw sha256
    `d064c0ba9c6ce93c60e62ec92746d3671da9b8b8eb75f6cc6bf5a5d26d4f7ad2`,
    LF sha256
    `25850ae8b4ee1a3fddd3e54f4aa972c4e0c26b5d811e7024e91d38cda00874e3`.
  - `p5_06_tests.json` sha256
    `2a5bc85f362684dbb5c1bc8d80a115dd4bcdb8b7d99649d1cf10165c01ab7dd2`.
- Markers: `OPENRECOMP_P5_06=PASS`,
  `OPENRECOMP_PHASE5_PPU_BOUNDARY_V1=PASS tests=32`; terminal/general
  reserved as `NOT_PROVEN`.
- Gate sha256 `c5ba83aa1ff9eef469282ec6925a4fe8170b6670389d736ee570888151f475d4`;
  Phase-5 manifest verifies all seventeen entries.

## Regressions

`tools/test_phase4_graphics_audio_v1.py` and `tools/test_nes_platform_v1.py`
re-pass with empty stderr (recorded in `regressions.json`).

## Limitations

- No rendering, sprite evaluation, sprite-0/overflow timing, fine-scroll
  behaviour or cycle accuracy; the graphics observable is a bounded tile-space
  state view only.
- CHR-RAM mode is implemented but the audited fixture uses CHR ROM; PPU
  semantics beyond the fixture's needs are not claimed.
- Vblank/NMI delivery scheduling is P5-07 scope.

## Evidence files

`RESULT.md`, `p5_06_tests.json`, `official_runs.json`, `determinism.json`,
`ppu.json`, `frame.json`, `regressions.json`, `run1.txt`, `run2.txt`,
`run1.err.txt`, `run2.err.txt`.

## Next stage

P5-07 - APU/input/timing/interrupt boundary.
