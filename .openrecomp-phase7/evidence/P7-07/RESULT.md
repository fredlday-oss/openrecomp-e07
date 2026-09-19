# P7-07 Public Indirect-Control-Flow Fixture - Result

Verdict: `PASS`

## Baseline

- Branch `phase7/nes-translation-frontier-v1` at the P7-06 boundary commit,
  descending from the frozen Phase-6 terminal commit
  `1643817d43196c43155805249137e4b4e4a21eb1`.

## Objective (frozen queue)

Original Apache-2.0 fixture covering the supported indirect-resolution
mechanism, exercising exact single target, multiple feasible targets, the
unresolved/fail-closed case and relevant bank switching, with
differential/reference verification.

## Public fixture identity

| Field | Value |
| --- | --- |
| Fixture | `openrecomp-phase7-indirect-flow-fixture` |
| License / origin | Apache-2.0 / original |
| Sources | `.openrecomp-phase7/fixture/p7_indirect_flow_fixture.asm`, `p7_indirect_flow_bank.asm` |
| ROM sha256 / size | `1c9ad6582576a5c7c12a27b8a0077257c7c414142cd81ffdc92cb4a8ff1c9248` / 73744 |
| PRG / CHR | 4 x 16 KiB / 1 x 8 KiB, mapper 1, horizontal |
| Sites (bank 1) | `$8013` exact, `$8025` finite, `$8030` unresolved |
| Run-exit thunk | `$C205` (`run_exit`) |

Bank 1 hosts three `jmp ($E2)` sites selected by runtime selector `$10`; the
fixed bank commits bank 1 through an unrolled constant write sequence and
provides the finish thunk at `$C200`.

## Evidence model result (proven bank-1 provenance)

| Site | Classification | Domain | Feasible targets |
| --- | --- | --- | --- |
| `$8013` | `RESOLVED_EXACT` | - | `$8033` (bank 1) |
| `$8025` | `RESOLVED_FINITE_SET` | `{0,2,4,6}` | `$8100`, `$8110`, `$8120`, `$8130` (bank 1) |
| `$8030` | `UNRESOLVED` | - | none (RAM-sourced pointer bytes) |

All three sites carry `PROVEN` bank-1 provenance from the bank-aware model
(50 proven instructions, 0 unresolved).

## Differential / reference verification

| Runtime selector | Path | Markers (`$0300`/`$0301`/`$0302`) | Target check |
| --- | --- | --- | --- |
| 0 | exact | `$E0` / `$01` / `$F0` | `$8033` executed |
| 1 | finite (index 2) | `$F2` / `$02` / `$F0` | `$8110` executed (model-predicted target) |
| 2 | unresolved runtime | `$00` / `$00` / `$F0` | fixed `$C200` executed; model correctly files closed with no targets |

All three runs reached the declared exit site through the frozen independent
6502 core over the frozen MMC1 platform with the decode windows synced to the
live bank state.

## Official gate

- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-07
  --script tools/test_phase7_indirect_fixture_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-07 --tests-json p7_07_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 2006 bytes raw, raw sha256
    `30175c6a64bdf8292ad31a1240eee8a0ab742224d5fc3aa9981025152380541e`,
    LF sha256
    `1890e432f7897ea182de14dd3497a8afb27139b87d2374fca8ea086b5d9accb7`.
  - `p7_07_tests.json` sha256
    `4b3491a7595cbcdc9a9f4e4f7f2ee91b10c50b082692bd47285d10b278490b52`,
    `tests=42`.
- Markers: `OPENRECOMP_P7_07=PASS`,
  `OPENRECOMP_PHASE7_INDIRECT_FIXTURE_V1=PASS tests=42`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Negative / fail-closed coverage

- Invalid selector patch types (`-1`, `True`) are rejected.
- A zeroed finite table yields `IMPOSSIBLE` (no feasible targets).
- Short decode images raise `P7IndirectError`.
- Evidence hygiene: no private ROM bytes; no ROM-extension file in scratch.

## Regressions

- `tools/test_nes_rom_v1.py`: exit 0, empty stderr.
- `tools/test_phase7_indirect_evidence_v1.py` re-run into ignored scratch
  evidence: exit 0, empty stderr, `OPENRECOMP_P7_06=PASS`.

## Changes

- Added `.openrecomp-phase7/fixture/p7_indirect_flow_fixture.asm` and
  `p7_indirect_flow_bank.asm`.
- Added `.openrecomp-phase7/src/p7_indirect_flow_fixture_v1.py`.
- Added `tools/test_phase7_indirect_fixture_v1.py`.
- Extended `.openrecomp-phase7/src/p7_dispatch_reference_v1.py` cost table
  with `lda zp`, `and #`, `cmp #`, `beq`, `lda abs,y` (documented costs).
- Updated `.openrecomp-phase7/SOURCE_SHA256SUMS.txt`, `STATE.md`,
  `STAGE_QUEUE.md`, `HANDOFF.md`.
- No frozen Phase-1..Phase-6 file was modified.

## Limitations

- Bounded to the three dispatch forms the model proves; runtime selector
  values outside 0/1 take the unresolved path, whose target is runtime state.
- No general indirect-control-flow recovery claim is made.

## Evidence index

- `RESULT.md`, `changed_files.txt`, `indirect_fixture.json`,
  `p7_07_tests.json`, `official_runs.json`, `determinism.json`,
  `run1.txt`, `run1.err.txt`, `run2.txt`, `run2.err.txt`.

## Next stage

P7-08 Translation frontier integration.
