# P5-10 Independent NES Reference Equivalence - Result

Verdict: `PASS`

## Baseline

- Branch `phase5/nes-platform-v1` at commit `35974e6` (P5-09 boundary).

## Objective (frozen queue)

Run the same bounded fixture through an independently implemented or
independently structured NES reference path and compare deterministic
observables: CPU state, RAM digest, frame/state digest, controller transcript,
interrupt counts, platform/service transcript and exit/final bounded state.

## Delivered

- New `.openrecomp-phase5/src/p5_reference_v1.py`: driver for the frozen,
  independently written `ReferenceNES6502` (`tools/nes6502_reference_v1.py`)
  routed through the frozen independent platform (`tools/nes_platform_v1.py`
  `NesMachine` + `tools/nes_headless_v1.py` `NesReference6502`) with the exact
  P5-07 scheduling policy (frame/vblank units, NMI entry cost, base opcode
  costs, per-frame input plan) and the same declared exit-site interception
  (`$C0FD`); it emits the identical canonical observable layout and FNV-1a 64
  state digest as the native support.
- New `tools/test_phase5_reference_equiv_v1.py` gate.

## Equivalence (four plans, exact)

For each of the four declared controller plans (none / A / RIGHT / A+RIGHT):

- native build reproducible and deterministic;
- every compared field equal: `failed`, `error`, `exit`, `steps`, `pc`, `a`,
  `x`, `y`, `sp`, `p`, `frames`, `nmi`, `clock`, `exit_arg` and all three
  digests (`ram_fnv1a64`, `ppu_fnv1a64`, `state_fnv1a64`);
- the full 11-line frame transcript (input byte, tile-space digest, PPU
  digest) byte-identical;
- the guest transcript word (`$0400..$0407`) and exit state identical;
- interrupt counts and frame counts identical.

Example (plan none): `steps=90900`, `clock=298315`, `pc=0xC0FD`, `p=0x27`,
`nmi=8`, `frames=11`, `ram_fnv1a64=0xD274F78FE0904D46`,
`state_fnv1a64=0x48306098348F5680` on both paths.

## Sensitivity

Tampering with the scheduling policy (NMI entry cost or frame length) makes
the reference observable differ from the audited native observable, proving
the comparison detects divergence.

## Official gate

- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 1489 bytes raw, raw sha256
    `077e99f253d75795665d920b265c3a2533231f99a7eb5d2cc390c6b2ee44e552`,
    LF sha256
    `1a1a62622d7e026a46d6c18f490b6b1dd6216a25a4948ad93fcebda044222f64`.
  - `p5_10_tests.json` sha256
    `2fb083841f6c9467adfa4d82c8d3865f9d23e3f15568ef1b96d85c182d5e04eb`.
- Markers: `OPENRECOMP_P5_10=PASS`,
  `OPENRECOMP_PHASE5_REFERENCE_EQUIVALENCE_V1=PASS tests=37`; terminal/
  general reserved as `NOT_PROVEN`.
- Gate sha256 `ee611fd9d2e3c5b00b39205092012e51228eff93b4cb10aa0220443734aa334d`;
  Phase-5 manifest verifies all twenty-five entries.

## Regressions

`tools/test_nes_headless_v1.py` and `tools/test_nes6502_state_v1.py` re-pass
with empty stderr (recorded in `regressions.json`).

## Limitations

- Equivalence is exact for the audited fixture, declared plans and the bounded
  scheduling policy; it is not a general NES compatibility or cycle-accuracy
  claim.
- The reference path intercepts the one declared exit site; the original
  indirect jump target is never invented or executed.
- Digest equality is a strong deterministic observable, not a formal proof of
  memory equality; the transcript and field-level comparisons constrain it.

## Evidence files

`RESULT.md`, `p5_10_tests.json`, `official_runs.json`, `determinism.json`,
`equivalence.json`, `sensitivity.json`, `regressions.json`, `run1.txt`,
`run2.txt`, `run1.err.txt`, `run2.err.txt`.

## Next stage

P5-11 - Private TMNT compatibility run.
