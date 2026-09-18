# P6-07 MMC1 Static-Recompilation Integration - Result

Verdict: `PASS`

## Baseline

- Branch `phase6/nes-compat-v1` at the P6-06 boundary commit (Phase-5 frozen
  boundary `e8d3627a622d0ca3196b117c5112f29fabdb49e7`; tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).

## Objective (frozen queue)

Ingest the real public MMC1 proof fixture, recover reachable code, build
ProgramModel/CFG/functions/translation units and integrate the mapper service
through the Phase-4/5 runtime contracts. No fabricated indirect targets or
hardware behaviour.

## Changes (additive)

- `.openrecomp-phase6/src/p6_frontier_v1.py`: bank-aware CPU image and
  reachable frontier for the MMC1 proof fixture.
- `.openrecomp-phase6/src/p6_structure_v1.py`: neutral structure build through
  the shared openrecomp layers.
- `.openrecomp-phase6/src/p6_cartridge_v1.py`: MMC1 cartridge service behind
  the Phase-5 bus protocol, composing the P6-02 .. P6-05 models.
- `.openrecomp-phase6/src/p6_emit_v1.py`: deterministic host-program emission
  (frozen Phase-5 emitter) and MMC1 runtime support generation.
- `tools/test_phase6_mmc1_recompile_v1.py`: new P6-07 gate.
- `.openrecomp-phase6/SOURCE_SHA256SUMS.txt`, `STATE.md`, `STAGE_QUEUE.md`,
  `HANDOFF.md`: stage bookkeeping.
- No frozen file was modified; the P6-01/P6-06 fixture identities are
  preserved.

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-07
  --script tools/test_phase6_mmc1_recompile_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-07 --tests-json p6_07_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 3170 bytes raw, raw sha256
    `d7842d364d5bbb5053936e5a073cee0c37a9d3379168b50d4fac42ce7b0127a0`,
    LF sha256
    `161b1867351b51cb2c4721e97f148b718845b5b178235bae1956290de8a20d0e`.
  - `p6_07_tests.json` sha256
    `32a688a0e428abdd9355b8f647e59736db44344b850f8c1a9927c46b19df71de`.
- Markers: `OPENRECOMP_P6_07=PASS`,
  `OPENRECOMP_PHASE6_MMC1_RECOMP_V1=PASS tests=65`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Reachable frontier (exact)

- Bank-aware image: fixed last bank `$C000-$FFFF`, mapper-selected low bank
  `$8000-$BFFF` under the documented post-reset state.
- 262 reachable instructions / 571 reachable bytes, all in the fixed bank;
  linear code span `$C000-$C23B` fully reachable with zero dead instructions.
- One unresolved indirect site at `$C089` (`jmp ($02FF)`, the declared
  page-wrap run-exit thunk) with empty target set; no interrupt (BRK) sites;
  14 dynamic return sites (`rts`/`rti`) recorded, never guessed.

## Neutral structure

- 262 instructions, 64 blocks, 15 functions, 15 translation units, 17 direct
  call sites; explicit reset/NMI/IRQ entries.
- Pinned fingerprints: CFG `f53b4f5c...`, discovery `c58ba164...`, call graph
  `de2a2669...`, units `3b9557b7...`, classification `b144500c...`.
- No fabricated function boundaries (boundary violations empty) and no
  fabricated indirect targets (single unresolved site with empty targets).

## Mapper service integration

- `P6Mmc1Cartridge` implements the frozen Phase-5 bus `cpu_read`/`cpu_write`
  protocol with an explicit `advance(cost)` cycle hook for the audited serial
  protocol.
- Verified: PRG banks 0..3 switch the `$8000` window and read bank-specific
  bytes; CHR 4 KiB banks 0..7 map PPU reads to the expected CHR bytes; all
  four mirroring modes select the expected nametable; a write on the cycle
  immediately after another is suppressed without changing the shift
  register; the `$6000-$7FFF` window fails closed.
- Unsupported mapper, declared PRG-RAM and undeclared indirect pointers fail
  closed.

## Host emission

- Host program emitted through the frozen Phase-5 emitter:
  deterministic (two identical builds), sha256 `6c1ccac5...`; uses only the
  typed runtime ABI externs and the single declared run-exit service.
- MMC1 runtime support source generated deterministically (sha256
  `c15980d4...`): bank-aware PRG/CHR/mirroring, disabled PRG-RAM, typed ABI.
  Native compilation and execution are P6-08 scope.

## Regressions

`tools/test_nes_rom_v1.py`, `tools/test_nes_platform_v1.py` and the P6-00 ..
P6-06 gates all exit 0 with empty stderr (earlier P6 gates re-run into ignored
scratch evidence; committed evidence untouched).

## Limitations

- P6-07 is static integration: the emitted host program and support are not
  yet compiled or executed, and the independent reference equivalence is P6-09
  scope. The terminal marker remains `NOT_PROVEN`.
- The P6-06 proof fixture executes entirely in the fixed bank; switchable-bank
  data reads exercise the mapper service, and the bounded claim does not
  include executing guest code from multiple banks.

## Evidence files

`RESULT.md`, `p6_07_tests.json`, `official_runs.json`, `determinism.json`,
`recompilation.json`, `mapper_service.json`, `emission.json`,
`regressions.json`, `run1.txt`, `run2.txt`, `run1.err.txt`, `run2.err.txt`,
`changed_files.txt`.

## Next stage

P6-08 - Native execution of public MMC1 fixture.
