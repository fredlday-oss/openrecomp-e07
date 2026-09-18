# P5-04 Neutral Program Structure - Result

Verdict: `PASS`

## Baseline

- Branch `phase5/nes-platform-v1` at commit `371c9dd` (P5-03 boundary).

## Objective (frozen queue)

Bridge the NES program into the shared architecture-neutral layers. Do not
fabricate function boundaries or indirect targets. Represent interrupt/reset
roots explicitly.

## Delivered

- New `.openrecomp-phase5/src/p5_structure_v1.py`: real-fixture bridge through
  the frozen `openrecomp.frontends.nes6502` seam into the shared Phase-2
  layers (P2-01 ProgramModel, P2-02 CFG, P2-03 functions, P2-04 call graph,
  P2-05 translation units, P2-06 indirect-control-flow classification).
- New `tools/test_phase5_structure_v1.py` gate.

## Structure (231 instructions, region `[$C000,$C1FD)`)

- Explicit roots: RESET `$C000` (vector `$FFFC/$FFFD`), NMI `$C196` (vector
  `$FFFA/$FFFB`), IRQ `$C1F7` (vector `$FFFE/$FFFF`), and the documented BRK
  continuation `$C0A8` (the single BRK at `$C0A6` pushes PC+2; the IRQ
  handler's RTI returns there). Each root maps to a distinct neutral function.
- CFG: 48 blocks (fingerprint `d6dfe7a8...`); discovery: 11 functions
  (`2839d54f...`); call graph: 7 resolved internal direct edges
  (`f0a4381e...`), call sites pinned; translation units: 11
  (`5523eae9...`); indirect classification: `6bc9b98f...`.
- Function entries are exactly the four documented roots plus the seven direct
  JSR targets; `boundary_violations` is empty - no fabricated boundaries.
- Complete control-flow ownership: `unowned_control_flow` empty; one TRAP site
  at `$C0A6`; the single `$C0FD jmp ($02FF)` site is
  `UNRESOLVED_INDIRECT_JUMP` with empty `targets`/`target_functions` - no
  invented indirect targets.
- Reachable relationship: the neutral model covers all 230 P5-02 reachable
  instructions plus exactly one extra (the dead padding NOP at `$C0A7`);
  `missing_instructions` is empty.

## Official gate

- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 1598 bytes raw, raw sha256
    `937e3c2c73dd6ad1f8f9b7d1c920771edf6856787f6b201c5a98acdda605afd6`,
    LF sha256
    `bed9d7a5113bd7d47087eb21f4b2ed00112250f188f703abcd86c413223e6313`.
  - `p5_04_tests.json` sha256
    `9d3e924cd98048307604fc29cf80cc1a427d0da67484ead38d37fb3f7d57f85b`.
- Markers: `OPENRECOMP_P5_04=PASS`,
  `OPENRECOMP_PHASE5_NEUTRAL_STRUCTURE_V1=PASS tests=34`; terminal/general
  reserved as `NOT_PROVEN`.
- Gate sha256 `7a261f75e73a1f560401465156eb4b085ea9449db1156f9122ad652ebb183994`;
  Phase-5 manifest verifies all thirteen entries.

## Regressions

`tools/test_nes6502_program_bridge_v1.py` and
`tools/test_indirect_control_flow_v1.py` re-pass with empty stderr (recorded
in `regressions.json`).

## Limitations

- The structure is exact for the audited public fixture; no claim is made for
  other images.
- RTS/RTI return targets remain dynamic; the BRK continuation is represented
  as a documented root rather than an inferred call edge.
- The single indirect service thunk stays unresolved by design; its runtime
  binding is P5-08 scope.

## Evidence files

`RESULT.md`, `p5_04_tests.json`, `official_runs.json`, `determinism.json`,
`structure.json`, `boundaries.json`, `regressions.json`, `run1.txt`,
`run2.txt`, `run1.err.txt`, `run2.err.txt`.

## Next stage

P5-05 - NES CPU memory map + mapper model.
