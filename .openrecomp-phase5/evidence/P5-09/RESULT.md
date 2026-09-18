# P5-09 Native Execution of the Legal NES Fixture - Result

Verdict: `PASS`

## Baseline

- Branch `phase5/nes-platform-v1` at commit `9937c58` (P5-08 boundary).

## Objective (frozen queue)

Produce and execute the native-host result for the legally clean NES fixture;
demonstrate meaningful interactive behaviour through CPU + memory + input +
timing + graphics/platform boundaries.

## Executions

Four declared controller plans over 11 virtual frames (8 recorded NMI frames):

| plan | platform byte | guest serial byte | observable effect |
| --- | --- | --- | --- |
| none | `00` | `00` | baseline |
| a | `01` | `80` | sprite X changes (OAM/PPU digest changes) |
| right | `80` | `01` | state_a changes (RAM digest changes) |
| a_right | `81` | `81` | both |

The fixture's serial read (`lsr a; rol input0`) reverses the platform button
order, so the guest-side byte is the bit-reverse of the platform controller
byte; the gate computes and verifies the exact reversal.

## Verification

- Every plan builds `EXECUTABLE_REPRODUCIBLE` and runs deterministically
  (two identical runs per plan): `failed=0`, `exit=1`, `frames=11`, `nmi=8`.
- The guest's own per-frame transcript (`$0400..$0407`) equals the exact
  bit-reversed plan bytes for every plan.
- Interactive state changes exactly as documented: the A-encoded plan changes
  PPU/OAM observables while the RIGHT-encoded plan changes guest RAM state;
  the RIGHT plan leaves the PPU digest equal to the no-input baseline; the
  combined plan is distinct from both.
- All four plans are pairwise distinct in final state; the nametable tile
  digests are unchanged by controller input (input does not affect graphics
  writes, only sprite/state data).

## Official gate

- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 1814 bytes raw, raw sha256
    `3b6f4b790864fcc33ccdefb9fcb89cedfbac83bee69d7513876165ad36fadf72`,
    LF sha256
    `7c1aeca99761125eb697067760387a73b89179203d99bb14b45a681d924f1cd0`.
  - `p5_09_tests.json` sha256
    `fad3501b9c0fe34a9bf5ceed783db63bcf0dc0b751cef06f0fca97c162ebdf71`.
- Markers: `OPENRECOMP_P5_09=PASS`,
  `OPENRECOMP_PHASE5_NATIVE_EXECUTION_V1=PASS tests=40`; terminal/general
  reserved as `NOT_PROVEN`.
- Gate sha256 `5f75539e5b985cdbe7ab9e48c85e370df50329cda1a1a85bd0683cc84ca2511f`;
  Phase-5 manifest verifies all twenty-three entries.

## Regressions

`tools/test_nes6502_host_emitter_v1.py` and `tools/test_nes_runtime_bridge_v1.py`
re-pass with empty stderr using scratch evidence directories (recorded in
`regressions.json`).

## Limitations

- The interaction is the fixture's documented scripted behaviour (four
  declared plans); no general game-input compatibility is claimed.
- Timing remains the bounded P5-07 virtual model; the graphics observable is
  the bounded tile-space/PPU digest, not rendered video.
- Independent equivalence against a separate reference is P5-10 scope.

## Evidence files

`RESULT.md`, `p5_09_tests.json`, `official_runs.json`, `determinism.json`,
`executions.json`, `interactivity.json`, `regressions.json`, `run1.txt`,
`run2.txt`, `run1.err.txt`, `run2.err.txt`.

## Next stage

P5-10 - Independent NES reference equivalence.
