# P5-07 APU/Input/Timing/Interrupt Boundary - Result

Verdict: `PASS`

## Baseline

- Branch `phase5/nes-platform-v1` at commit `c5ad851` (P5-06 control-plane
  boundary).

## Objective (frozen queue)

Implement the bounded interfaces required by the fixture for controller
input, NMI, IRQ if required, vblank/event delivery, frame timing and APU
accesses. Audio may remain bounded/unsupported where the fixture does not
require observable audio equivalence.

## Delivered

- New `.openrecomp-phase5/src/p5_platform_v1.py`: deterministic virtual
  platform scheduler:
  - documented base-cost table covering all 151 official opcodes (table
    sha256 `57447c2c...`); page-cross and taken-branch penalties are
    explicitly not modelled;
  - virtual frame of 29780 clock units with a 2273-unit vblank window
    (documented NTSC nominal), driven instruction by instruction;
  - per-frame controller-0 input plan applied at frame starts with a full
    transcript (frame index, clock, input byte, NMI queue, tile-space digest);
  - NMI queued at vblank start when PPUCTRL bit 7 is set and delivered by the
    driver at the next instruction boundary; vblank flag set at frame start
    and cleared at window end or by a PPUSTATUS read;
  - explicit asserted-line IRQ interface with acknowledgment (the fixture
    uses software BRK only);
  - APU latches/status remain bus-owned; no audio equivalence claim.
- New `tools/test_phase5_platform_v1.py` gate.

## Verification

- Cost table covers all 151 official opcodes with documented base values
  (spot checks pinned); table digest pinned.
- 300000-NOP schedule: clock 600000 units, 21 frames at exact boundaries,
  input plan applied per frame, 21 NMIs queued and 21 delivered, 21 vblank
  windows at the documented offsets.
- Vblank set/clear semantics and NMI-disabled behaviour verified.
- IRQ assert/take/deassert semantics verified.
- APU register latches/status differentially compared against the frozen
  independent platform: exact.
- Two identical runs produce byte-identical transcripts (digest equality).
- Fail-closed: undocumented opcode cost, empty/invalid input plan, invalid
  frame/vblank timing.

## Frozen-evidence note

The P5-06 regression run of `tools/test_phase4_graphics_audio_v1.py` (without
an evidence override) refreshed the committed Phase-4 P4-06 sidecar
(`phase4_entries` 30 -> 32) as a deterministic re-run artifact. The refreshed
file was restored to the committed bytes with a targeted checkout; the frozen
Phase-4 record is unchanged. P5-07's own Phase-4 regression writes to
`.openrecomp-phase5/scratch/` and leaves frozen evidence untouched. P5-90 will
apply the documented dynamic boundary hygiene.

## Official gate

- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 1572 bytes raw, raw sha256
    `062678b94f0a8b5b0821342dd3a512223bec381e9dbcb6de035cdb5cf2d2ce41`,
    LF sha256
    `dd9087ae15437377c4acaa82687b20892d14d9adf20cb3954c3e93927efd8fb7`.
  - `p5_07_tests.json` sha256
    `ca98795c260353dc774c589f80960f38793ec80218b5973c73b0823d61be3030`.
- Markers: `OPENRECOMP_P5_07=PASS`,
  `OPENRECOMP_PHASE5_TIMING_INPUT_V1=PASS tests=34`; terminal/general
  reserved as `NOT_PROVEN`.
- Gate sha256 `8a02b4c84efef106b1d781b32cb88cfa25b46ee0f8916156b80887c56353a346`;
  Phase-5 manifest verifies all nineteen entries.

## Regressions

`tools/test_nes_platform_v1.py` and `tools/test_phase4_deterministic_io_v1.py`
(scratch evidence) re-pass with empty stderr (recorded in `regressions.json`).

## Limitations

- The timing model is bounded and explicitly not cycle accurate.
- Hardware IRQ delivery is a bounded interface; the fixture does not use it.
- No audio synthesis or audio equivalence claim.

## Evidence files

`RESULT.md`, `p5_07_tests.json`, `official_runs.json`, `determinism.json`,
`platform.json`, `transcript.json`, `regressions.json`, `run1.txt`,
`run2.txt`, `run1.err.txt`, `run2.err.txt`.

## Next stage

P5-08 - Host emission + NES platform adapter.
