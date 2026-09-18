# P6-02 MMC1 Serial Register Protocol - Result

Verdict: `PASS`

## Baseline

- Branch `phase6/nes-compat-v1` at the P6-01 boundary commit (Phase-5 frozen
  boundary `e8d3627a622d0ca3196b117c5112f29fabdb49e7`; tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).

## Objective (frozen queue)

Implement deterministic five-write shift-register semantics, reset-bit
behaviour, register selection and the consecutive/write-edge behaviours
required by the audited fixtures; malformed/unsupported states fail closed;
differential tests against an independent reference.

## Changes (additive)

- `.openrecomp-phase6/src/p6_mmc1_serial_v1.py`: deterministic MMC1 serial
  register file and write protocol.
- `.openrecomp-phase6/src/p6_mmc1_serial_reference_v1.py`: independently
  structured reference model (explicit received-bit list, independent window
  predicate and slot arithmetic) used only for differential testing.
- `tools/test_phase6_mmc1_serial_v1.py`: new P6-02 gate.
- `.openrecomp-phase6/MMC1_SUBSET.md`: records the exact audited
  consecutive-cycle suppression model.
- `.openrecomp-phase6/SOURCE_SHA256SUMS.txt`, `STATE.md`, `STAGE_QUEUE.md`,
  `HANDOFF.md`: stage bookkeeping.
- No frozen file was modified.

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-02
  --script tools/test_phase6_mmc1_serial_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-02 --tests-json p6_02_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 2305 bytes raw, raw sha256
    `caf7bb5c0a6c09621b6b0bbe1ec2990c696f0d6e910feac220fa727bf0ebb2c1`,
    LF sha256
    `ed0061090d5b50be03cf80dd44c2cf48f6871ebc0506d9d14fecc3761e2dafc6`.
  - `p6_02_tests.json` sha256
    `86ca0e02c0031a7d0f51847979ea0966622d407cff0deb0d072e4db8748fb9e5`.
- Markers: `OPENRECOMP_P6_02=PASS`,
  `OPENRECOMP_PHASE6_MMC1_SERIAL_V1=PASS tests=47`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Protocol contract implemented

- Four 5-bit registers selected by CPU address bits 14:13 (`control`
  `$8000-$9FFF`, `chr_bank_0` `$A000-$BFFF`, `chr_bank_1` `$C000-$DFFF`,
  `prg_bank` `$E000-$FFFF`).
- Five writes commit a register, least-significant bit first; the fifth write
  reports the committed register and value.
- A write with bit 7 set resets the shift register (shift and count cleared)
  and does not commit.
- Audited suppression model: a write that lands on the CPU cycle immediately
  after another MMC1 write is ignored and leaves all state, including the
  last-write cycle, unchanged. A write at a same cycle or a gap of two or more
  cycles is processed.
- Power-on: control `0x0C` (PRG mode 3, CHR mode 0, one-screen lower), all
  other registers `0`, shift register cleared, no last-write cycle.

## Differential verification

- 4940+ comparison steps of implementation vs independent reference, zero
  mismatches, checked after every write on action, action register/name,
  committed value and full model state (registers, shift, count, last cycle).
- Exhaustive classes: all 256 first-write value classifications; all 4
  windows x all 32 five-write values (128 commits); all 4 windows x 32
  reset-bit interleavings (128 sequences); suppression and write-edge
  sequences; 3000 deterministic pseudo-random mixed writes (seed `0x504602`)
  containing commits, resets and suppressed writes.
- The public fixture control write (`0x0F`) replays to the expected commit.

## Negative / fail-closed coverage

Writes outside `$8000-$FFFF`, values outside an 8-bit range, negative cycles,
non-integer addresses and boolean values raise `MMC1SerialError`; an unknown
register name to `register_value` fails closed; state is untouched after every
rejected call. No test produced a traceback.

## Regressions

`tools/test_nes_rom_v1.py`, `tools/test_nes_platform_v1.py`, the P6-01
inventory gate and the P6-00 boundary gate all exit 0 with empty stderr; the
P6-01/P6-00 re-runs write into ignored scratch evidence so committed evidence
is untouched. Raw stdout hashes are recorded in `regressions.json`.

## Limitations

- P6-02 proves the serial register protocol only. PRG mapping, CHR mapping,
  mirroring and PRG-RAM behaviour are separate stages; no execution claim is
  made and the terminal marker remains `NOT_PROVEN`.
- The suppression model is the audited `MMC1_SUBSET_V1` contract; MMC1A/B/C
  hardware differences remain explicitly unsupported.

## Evidence files

`RESULT.md`, `p6_02_tests.json`, `official_runs.json`, `determinism.json`,
`serial_protocol.json`, `reference_comparison.json`, `regressions.json`,
`run1.txt`, `run2.txt`, `run1.err.txt`, `run2.err.txt`, `changed_files.txt`.

## Next stage

P6-03 - MMC1 PRG banking.
