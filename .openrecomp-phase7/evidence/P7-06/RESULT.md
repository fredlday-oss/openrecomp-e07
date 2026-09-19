# P7-06 Indirect Jump Evidence Model - Result

Verdict: `PASS`

## Baseline

- Branch `phase7/nes-translation-frontier-v1` at the P7-05 boundary commit,
  descending from the frozen Phase-6 terminal commit
  `1643817d43196c43155805249137e4b4e4a21eb1`.

## Objective (frozen queue)

Build deterministic analysis for the three `$E2` indirect sites tracking
pointer writes, reads, bank state, memory provenance and feasible target
sets; represent `RESOLVED_EXACT`, `RESOLVED_FINITE_SET`, `UNRESOLVED` and
`IMPOSSIBLE` explicitly; never guess targets.

## Model

`.openrecomp-phase7/src/p7_indirect_evidence_v1.py`:

- reaching definitions on the unique straight-line predecessor chain (a
  middle entry fails closed to `UNRESOLVED`);
- value sources: `constant` (`lda #imm`), `rom_read` (`lda abs`), paired
  `table` reads (`lda abs,x`/`lda abs,y`), otherwise unknown;
- bounded abstract simulation of the chain computes the 8-bit index-register
  domain (masks, shifts, transfers, increments; full-range entry);
- candidate pointers are enumerated per evaluated physical bank (table bytes
  from the bank mapped at the window), and each candidate target is validated
  (PRG window, target bank, documented decode) - never guessed;
- explicit states with pointer writes/reads, index domain, table base,
  per-bank rows and target lists; bank provenance comes from the P7-04
  bank-aware identities (proven/candidate/model-unreached).

## Private `$E2` sites (metadata/derived evidence only)

All three sites classify `RESOLVED_FINITE_SET`:

| Site | Bank provenance | Evaluated banks | Index domain | Table | Feasible targets | Infeasible |
| --- | --- | --- | --- | --- | --- | --- |
| `0x86E8` | `PROVEN` (bank 0) | `[0]` | `{0,2,4,6}` | `$8FB8`/`$8FB9` | 4: `$86FB`, `$879D`, `$87B1`, `$8802` (bank 0) | 0 |
| `0x8956` | `UNRESOLVED` (candidate bank 0) | `[0]` | `{0,2,4,6}` | `$8FCC`/`$8FCD` | 4: `$8D03`, `$8D2A`, `$8D78`, `$8E6E` (bank 0) | 0 |
| `0x8F3C` | `MODEL_UNREACHED` | all 8 | 128 even values | `$8FC0`/`$8FC1` | 300 (target bank, target) pairs | 442 |

Site `0x86E8` has proven bank 0 provenance; the other two carry explicit
unresolved/unreached provenance and enumerate all evaluated physical banks
instead of guessing. The bank model itself remains
`BLOCKED_UNDECODABLE` at the unresolved private frontier (530 proven / 14027
unresolved-limited instructions).

## Public unit states (original synthetic images)

| State | Pattern | Result |
| --- | --- | --- |
| `RESOLVED_EXACT` | `lda #lo; sta $E2; lda #hi; sta $E3; jmp ($E2)` -> `$C100` | exact single target `$C100` |
| `RESOLVED_FINITE_SET` | masked table index `{0,2,4,6}` -> `$C100/$C110/$C120/$C130` | four proven targets |
| `UNRESOLVED` | pointer bytes from RAM loads | fail closed, no targets |
| `IMPOSSIBLE` | constants `$1234` outside the PRG windows | empty feasible set |

## Official gate

- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-06
  --script tools/test_phase7_indirect_evidence_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-06 --tests-json p7_06_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 2170 bytes raw, raw sha256
    `2e407ded7e3e015beb00f45762399c0de6de168c5267d93b0770f3d59c3781e7`,
    LF sha256
    `d8fc208e2d1fb1514cdf5947d5423fc0fc0ae9ca92758f2258bf8770753d2a16`.
  - `p7_06_tests.json` sha256
    `700c9d332836f224a35ab7c82c1bf19b3dd2c843efdc3a8ad17320e8d388415c`,
    `tests=51`.
- Markers: `OPENRECOMP_P7_06=PASS`,
  `OPENRECOMP_PHASE7_INDIRECT_MODEL_V1=PASS tests=51`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Fail-closed / negative coverage

- Short decode image and missing private path raise `P7IndirectError`.
- Non-table/non-enumerable sources, non-unique chains, out-of-window and
  undecodable candidates are explicit states, never fabricated targets.
- Evidence hygiene: no private ROM bytes in `indirect_evidence.json`; no
  ROM-extension file in the stage scratch tree.

## Regressions

- `tools/test_nes_rom_v1.py`: exit 0, empty stderr.
- `tools/test_phase7_bank_structure_v1.py` re-run into ignored scratch
  evidence: exit 0, empty stderr, `OPENRECOMP_P7_05=PASS`.

## Changes

- Added `.openrecomp-phase7/src/p7_indirect_evidence_v1.py`.
- Added `tools/test_phase7_indirect_evidence_v1.py`.
- Updated `.openrecomp-phase7/SOURCE_SHA256SUMS.txt`, `STATE.md`,
  `STAGE_QUEUE.md`, `HANDOFF.md`.
- No frozen Phase-1..Phase-6 file was modified.

## Limitations

- The finite sets are feasible target sets derived from proven value sources;
  they are not claims of exact runtime behavior (the selector value is
  runtime state), and TMNT playability remains `NOT_PROVEN`.
- The bank model for the private image remains blocked at the unresolved
  frontier; `$8F3C` is evaluated across all physical banks as
  `MODEL_UNREACHED`.

## Evidence index

- `RESULT.md`, `changed_files.txt`, `indirect_evidence.json`,
  `p7_06_tests.json`, `official_runs.json`, `determinism.json`,
  `run1.txt`, `run1.err.txt`, `run2.txt`, `run2.err.txt`.

## Next stage

P7-07 Public indirect-control-flow proof fixture.
