# P7-10 Independent Reference Equivalence - Result

Verdict: `PASS`

## Baseline

- Branch `phase7/nes-translation-frontier-v1` at the P7-09 boundary commit,
  descending from the frozen Phase-6 terminal commit
  `1643817d43196c43155805249137e4b4e4a21eb1`.

## Objective (frozen queue)

Compare generated native execution against independently structured reference
execution over CPU state, RAM, mapper/bank state, PPU state, controller
transcript, interrupt counts, indirect-control-flow transcript, translation/
service transcript and bounded final state; require exact bounded equivalence.

## Result (exact and finite proven paths)

For both variants the native binary fields and the reference fields are equal
for every field except `clock`:

- `failed=0`, `exit=1`, `pc=$C205`, identical `a/x/y/sp/p`, `steps`,
  `frames=1`, `nmi=0`, `exit_arg=0x0000C205`, RAM/PPU/state FNV digests,
  `mmc1_regs=0C000001`, `mmc1_shift/count/writes`, PRG windows `(1,3)`,
  `chr_mode`, `mirroring`, `prg_ram_enabled`, and identical `exit_word`
  (`0000000000000000`) and frame transcript
  `frame[0]=00,C42A06F7E7A28E25,39E9FBAE5A7B29A5`;
- indirect transcript: exact variant `$8013 -> $8033`, finite variant
  `$8025 -> $8110`, matching the model assignments and present in the
  reference executed set; service transcript `p7.exit` with `args=[$C205]`;
- timing delta: native `clock` is exactly 2 cycles lower per executed resolved
  indirect site (the resolved `jmp ($E2)` is emitted as a direct jump with
  cost 3 instead of 5). Cycle accuracy is explicitly out of scope and the
  delta is recorded as the only excluded observable.

## Unresolved path (documented policy divergence)

The native variant fails closed (`failed=1`, `error=pc outside the emitted
image`, `pc=$8030`), while the reference executes the unresolved site and
reaches the runtime target `$C200`. This divergence is the required
fail-closed policy and is recorded explicitly.

## Official gate

- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-10
  --script tools/test_phase7_reference_equivalence_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-10 --tests-json p7_10_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 1693 bytes raw, raw sha256
    `72ac30cbd57bedf1b883c09a3ded1831fe8975609da003a7ed1062d527d7c47c`,
    LF sha256
    `fa724d622bec7ff97bb221d5108d1e312182e384d49747e2114f8429d17e950b`.
  - `p7_10_tests.json` sha256
    `94c484c0cd91569f3428be918b9df95804f883e6eb20b9ec165d5d97dab8c0d1`,
    `tests=35`.
- Markers: `OPENRECOMP_P7_10=PASS`,
  `OPENRECOMP_PHASE7_REFERENCE_EQUIVALENCE_V1=PASS tests=35`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Changes

- Extended `.openrecomp-phase7/src/p7_dispatch_reference_v1.py` with the
  full native-observable field recipe (digests, frames, NMI accounting,
  transcripts); existing dispatch checks unchanged.
- Added `tools/test_phase7_reference_equivalence_v1.py`.
- Updated `.openrecomp-phase7/SOURCE_SHA256SUMS.txt`, `STATE.md`,
  `STAGE_QUEUE.md`, `HANDOFF.md`.
- No frozen Phase-1..Phase-6 file was modified.

## Regressions

- `tools/test_nes_rom_v1.py`: exit 0, empty stderr.
- `tools/test_phase7_native_execution_v1.py` re-run into ignored scratch
  evidence: exit 0, empty stderr, `OPENRECOMP_P7_09=PASS`.

## Limitations

- Bounded to the proven public paths; the timing delta is recorded and no
  cycle-accuracy claim is made.
- No private or general-compatibility claim is derived.

## Evidence index

- `RESULT.md`, `changed_files.txt`, `reference_equivalence.json`,
  `p7_10_tests.json`, `official_runs.json`, `determinism.json`,
  `run1.txt`, `run1.err.txt`, `run2.txt`, `run2.err.txt`.

## Next stage

P7-11 Private TMNT frontier run with Phase-7 support.
