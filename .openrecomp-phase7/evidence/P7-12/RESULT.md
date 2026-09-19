# P7-12 Evidence-Driven Translation Closure - Result

Verdict: `PASS`

## Baseline

- Branch `phase7/nes-translation-frontier-v1` at the P7-11 boundary commit.

## Closure rule (evidence-required, no speculation)

`.openrecomp-phase7/src/p7_inline_closure_v1.py` adds exactly the
inline-dispatch closure P7-11 proved necessary:

- detect structurally: a `jsr` whose fallthrough is an undocumented byte
  stream, whose callee consumes the pushed return address, and whose
  fallthrough decodes as an in-window little-endian pointer table with at
  least one target;
- close: skip the classified table bytes, follow the callee and the proven
  finite target set, resume after the table;
- fail closed everywhere else: undocumented bytes, unresolved indirect jumps,
  table spans and budgets stop the walk.

## Public verification (P7-03 fixture)

| Metric | Baseline | Closure |
| --- | --- | --- |
| Instructions | 15 | 41 (delta +26) |
| Tables | - | 1 at `$C01B` (site `$C018`, callee `$C100`, 3 targets `$C07C/$C090/$C0A0`, resume `$C021`) |
| Stop | table byte `0x7C` | none (all reached bytes documented) |

All three proven targets are reached in the closure walk, matching the P7-03
runtime evidence.

## Private application

| Metric | Baseline (power-on image) | Closure |
| --- | --- | --- |
| Instructions | 1250 | 1255 (delta +5) |
| Table | - | 1 at `$C570` (site `$C56D`, callee `$C71F`, 6 targets, resume `$C57C`) |
| New stop | `$C570` (`0x7C`) | `$BB6B` (undocumented `0xE3`) |

The `0xC570` blocker is resolved for the closed walk; the frontier now
advances to the next undocumented byte. Remaining bank-provenance ambiguity
and platform behaviour remain explicit blockers.

## Official gate

- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-12
  --script tools/test_phase7_translation_closure_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-12 --tests-json p7_12_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 1448 bytes raw, raw sha256
    `0c8493017263764219bf0668fec7381d60cc1961a6286d3726b04b7229013956`,
    LF sha256
    `7156ce51fcd580993b0fdffd631db90731611ad4b64ce4d3a1f5712315762ec3`.
  - `p7_12_tests.json` sha256
    `9afb4236186644108099e87b8789beda70451668cd5c394d9bef8c259908b6d9`,
    `tests=27`.
- Markers: `OPENRECOMP_P7_12=PASS`,
  `OPENRECOMP_PHASE7_TRANSLATION_CLOSURE_V1=PASS tests=27`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Negative / fail-closed coverage

- A `jsr` followed by undocumented bytes with a non-consuming callee yields
  no table (no false closure).
- An empty/out-of-window table yields no closure.
- A 3-node budget stops with `budget` (fail closed).

## Regressions

- `tools/test_nes_rom_v1.py`: exit 0, empty stderr.
- `tools/test_phase7_private_frontier_v1.py` re-run into scratch: PASS.

## Changes

- Added `.openrecomp-phase7/src/p7_inline_closure_v1.py` and
  `tools/test_phase7_translation_closure_v1.py`.
- Updated `.openrecomp-phase7/SOURCE_SHA256SUMS.txt`, `STATE.md`,
  `STAGE_QUEUE.md`.

## Limitations

- Closure is bounded to the audited inline-dispatch form; no general
  undocumented-code recovery.
- The private closure is over the power-on image; bank-aware integration is
  tracked separately.

## Evidence index

- `RESULT.md`, `changed_files.txt`, `inline_closure.json`,
  `p7_12_tests.json`, `official_runs.json`, `determinism.json`,
  `run1.txt`, `run1.err.txt`, `run2.txt`, `run2.err.txt`.

## Next stage

P7-13 Second private TMNT run.
