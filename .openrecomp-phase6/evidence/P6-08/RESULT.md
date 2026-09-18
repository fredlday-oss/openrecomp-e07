# P6-08 Native Execution of the Public MMC1 Fixture - Result

Verdict: `PASS`

## Baseline

- Branch `phase6/nes-compat-v1` at the P6-07 boundary commit (Phase-5 frozen
  boundary `e8d3627a622d0ca3196b117c5112f29fabdb49e7`; tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).

## Objective (frozen queue)

Emit host-native code and execute through the generic runtime/platform
adapter; demonstrate meaningful deterministic behaviour involving bank
switching, CPU, memory, PPU, input and timing; never execute original 6502
guest code directly.

## Changes (additive)

- `tools/test_phase6_mmc1_native_v1.py`: new P6-08 gate.
- `.openrecomp-phase6/SOURCE_SHA256SUMS.txt`, `STATE.md`, `STAGE_QUEUE.md`,
  `HANDOFF.md`: stage bookkeeping.
- No frozen file was modified; the emitted program/support identities are the
  same as recorded at P6-07.

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-08
  --script tools/test_phase6_mmc1_native_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-08 --tests-json p6_08_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 2913 bytes raw, raw sha256
    `178c5a79eef7989aff512597a1c50892f6237c6c8f015fe3ed64d2bd6143fbde`,
    LF sha256
    `33de32c6580f864728b32e39e73d785493d91114ae94397f81a15a4c197618e2`.
  - `p6_08_tests.json` sha256
    `4636f194f5e5cce599ed83bbce94800cd9a0bff2d59e0e2623c097e64205941a`.
- Markers: `OPENRECOMP_P6_08=PASS`,
  `OPENRECOMP_PHASE6_MMC1_NATIVE_V1=PASS tests=74`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Native build

- Host program (sha256 `6c1ccac5...`) plus MMC1 runtime support (sha256
  `c15980d4...`) built through the shared Phase-2 pipeline with
  `EXECUTABLE_REPRODUCIBLE` classification, two OK build runs, clang-cl /
  lld-link toolchain and a reproducible manifest.
- The host code is the emitted switch-over-PC machine for the 262 recovered
  instructions; the original 6502 guest bytes are never executed on the host.

## Deterministic execution

Three native runs produced byte-identical stdout with empty stderr and exit 0:

- CPU: `failed=0`, `exit=1`, `steps=82731`, `pc=0xC089`, `a=0x5C`,
  `x=0x06`, `y=0x04`, `sp=0xFF`, `p=0x25`, `exit_arg=0x0000C089`.
- Timing: `frames=9`, `nmi=6`, `clock=241746`; nine pinned frame transcript
  lines.
- Mapper: `mmc1_regs=1F070703`, `mmc1_shift=0`, `mmc1_count=0`,
  `mmc1_writes=5905`, `prg_window_8000=3`, `prg_window_c000=3`,
  `chr_mode=1`, `mirroring=3`, `prg_ram_enabled=0`.
- Memory/PPU/graphics: `ram_fnv1a64=0x9B997E9AE6A788AD`,
  `ppu_fnv1a64=0xACDA2ECE461DE700`, `state_fnv1a64=0x0524F07A3A18DF2E`,
  three distinct digests.
- Input: controller transcript `0101010101010000` for the declared plan
  `(0x00, 0x01, 0x80)`.

These observables jointly demonstrate bank switching (PRG/CHR windows and
5905 serial writes), CPU, memory, PPU, input and timing behaviour.

## Negative / fail-closed coverage

Support generation from a truncated ROM and a missing declared run-exit thunk
fail closed without traceback.

## Regressions

`tools/test_nes_rom_v1.py`, `tools/test_nes_platform_v1.py` and the P6-06 and
P6-07 gates all exit 0 with empty stderr (earlier gates re-run into ignored
scratch evidence; committed evidence untouched).

## Limitations

- Native execution is deterministic for the audited fixture and platform
  configuration; independent reference equivalence is P6-09 scope and the
  terminal marker remains `NOT_PROVEN`.
- No cycle accuracy or full PPU/APU accuracy is claimed; the timing model is
  the bounded Phase-5/6 platform model.

## Evidence files

`RESULT.md`, `p6_08_tests.json`, `official_runs.json`, `determinism.json`,
`build.json`, `executions.json`, `regressions.json`, `run1.txt`, `run2.txt`,
`run1.err.txt`, `run2.err.txt`, `changed_files.txt`.

## Next stage

P6-09 - Independent MMC1 reference equivalence.
