# P6-09 Independent MMC1 Reference Equivalence - Result

Verdict: `PASS`

## Baseline

- Branch `phase6/nes-compat-v1` at the P6-08 boundary commit
  `4eac1f0c835570bb54cb5d8fd72da2e14ae87dde`, tree
  `89ef9c02c47faa97e7944f11b115894010acb1be` (Phase-5 frozen boundary
  `e8d3627a622d0ca3196b117c5112f29fabdb49e7`; tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).

## Objective (frozen queue)

Run identical deterministic input plans through the generated native result and
an independently structured reference implementation. Compare CPU state, RAM,
mapper state, PRG/CHR bank state, mirroring, frame/state digest, input
transcript, interrupt counts, services and bounded final state. Require exact
equivalence for the bounded proof.

## Changes (additive)

- `.openrecomp-phase6/src/p6_reference_v1.py`: new independently structured
  MMC1 reference driver. It drives the frozen independent `ReferenceNES6502`
  oracle over a local CPU bus / PPU register+memory / APU latch / OAM DMA /
  controller / frame+vblank+NMI model and composes the independently
  structured P6-02 .. P6-05 reference mapper models (explicit received-bit
  shift list, modulo banking, direct address-bit nametable mapping). It
  carries its own base-cost schedule for the exact fixture opcode set and
  intercepts the declared `$C089 jmp ($02FF)` run-exit site with the same
  service-binding semantics as the emitted native program.
- `tools/test_phase6_mmc1_reference_equiv_v1.py`: new P6-09 gate.
- `.openrecomp-phase6/SOURCE_SHA256SUMS.txt`, `STATE.md`,
  `STAGE_QUEUE.md`, `HANDOFF.md`: stage bookkeeping.
- No frozen file was modified. The generated host program and the P6-08
  primary-plan support source are byte-identical to the P6-08 recorded
  identities; the native executable was rebuilt from the same emitted sources.

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-09
  --script tools/test_phase6_mmc1_reference_equiv_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-09 --tests-json p6_09_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 4147 bytes raw, raw sha256
    `0144086e742cdc5441a5a10d1d7da8f5f8d1012281e2769fd5515d66c7f6952a`,
    LF sha256
    `dcfbcb016a2a4bd3be64fc88e296fe7fcbef5ddd3a33deac23323b9758f8bb72`.
  - `p6_09_tests.json` sha256
    `cddf93dce73250e9ab6f74a394625d3e23fe62afa1632ca353438a5d301b949f`,
    `tests=100`.
- Markers: `OPENRECOMP_P6_09=PASS`,
  `OPENRECOMP_PHASE6_MMC1_REFERENCE_EQUIVALENCE_V1=PASS tests=100`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Independent reference comparison

Three declared deterministic controller plans were built through the native
pipeline and run through the reference path; every observable matched exactly:

| plan | native support sha256 (prefix) | ram_fnv1a64 | state_fnv1a64 | exit_word |
| --- | --- | --- | --- | --- |
| `p6_08` `(00,01,80)` | `c15980d4...` (identical to P6-08) | `9B997E9AE6A788AD` | `0524F07A3A18DF2E` | `0101010101010000` |
| `all_buttons` `(FF,FF,FF)` | `00a7b9e1...` | `79C9048EE4CE6BB7` | `F6A79330E8BD2849` | `FFFFFFFFFFFF0000` |
| `mixed_bits` `(00,11,22)` | `3ccd7e20...` | `3161F0DB168A233A` | `A4ECF8389890818D` | `4444444444440000` |

All three plans share the bounded run: `steps=82731`, `clock=241746`,
`frames=9`, `nmi=6`, `pc=0xC089`, `exit_arg=0x0000C089`,
`ppu_fnv1a64=0xACDA2ECE461DE700`, `mmc1_regs=1F070703`, `mmc1_writes=5905`,
`prg_window_8000=3`, `prg_window_c000=3`, `chr_mode=1`, `mirroring=3`,
`prg_ram_enabled=0`. Compared categories (all exact, per plan): CPU state,
RAM/PPU/state digests, mapper registers/shift/count/writes, PRG window banks,
CHR banks (derived via the independent CHR reference model), mirroring,
nine-line frame transcript, controller transcript (`exit_word`), interrupt
counts, `p6.exit` service transcript and bounded final/exit state.

The reference schedule was cross-checked against the frozen audited cost table
for all 40 opcode forms / 262 fixture instructions (zero mismatches) and the
timing constants were verified equal. The primary plan reproduces the P6-08
pinned support identity, host-program identity, all pinned observables and the
pinned frame transcript; the reference reproduces the same pinned observables.

## Sensitivity and negative / fail-closed coverage

- Sensitivity: a cross-plan comparison is rejected as non-equivalent; tampered
  NMI entry cost and frame length both change the reference observables, so
  the comparison is not vacuous.
- Fail-closed without traceback: truncated ROM, unsupported mapper status,
  declared battery, declared PRG-RAM, empty input plan, out-of-range plan
  value, disabled `$6000-$7FFF` PRG-RAM window read and CHR-ROM write.

## Regressions

`tools/test_nes_rom_v1.py`, `tools/test_nes_platform_v1.py` and the
Phase-6 P6-01/P6-02/P6-03/P6-04/P6-05 gates all exit 0 with empty stderr
(earlier gates re-run into ignored scratch evidence; committed evidence
untouched). The P6-06/P6-07/P6-08 gates were not re-run here because the P6-09
gate re-verifies the P6-08 generated identities, pinned observables and frame
transcript directly, and the full nested re-run is P6-90 scope.

## Limitations

- Exact equivalence holds only for the audited public MMC1 fixture, the three
  declared bounded input plans and the bounded Phase-5/6 platform/timing
  model. No cycle accuracy, full PPU/APU accuracy, general NES compatibility
  or MMC1 board-variant coverage is claimed.
- The terminal marker remains `NOT_PROVEN` until P6-99; the general
  compatibility marker is permanent.

## Repository side effects

- Tracked additive changes: the new reference module and gate, the updated
  manifest/control-plane files and the P6-09 evidence.
- Untracked build/scratch artifacts under `.openrecomp-phase6/build/P6-09/`
  and `.openrecomp-phase6/scratch/P6-09/` remain outside version control
  (ignored); no ROM bytes exist in any evidence file.

## Evidence index

`RESULT.md`, `p6_09_tests.json`, `official_runs.json`, `determinism.json`,
`equivalence.json`, `sensitivity.json`, `schedule.json`, `regressions.json`,
`run1.txt`, `run2.txt`, `run1.err.txt`, `run2.err.txt`, `changed_files.txt`.

## Next stage

P6-10 - Private TMNT compatibility run.
