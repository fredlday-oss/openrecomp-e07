# P7-05 Bank-Aware ProgramModel / CFG Integration - Result

Verdict: `PASS`

## Baseline

- Branch `phase7/nes-translation-frontier-v1` at the P7-04 boundary commit,
  descending from the frozen Phase-6 terminal commit
  `1643817d43196c43155805249137e4b4e4a21eb1`.

## Objective (frozen queue)

Extend the neutral program representation only as needed to distinguish
banked code identities; recover CFG/function/translation-unit structure
without fabricating cross-bank edges; preserve architecture-neutral
boundaries; include a public redistributable bank-switching fixture.

## Public bank-switching fixture

| Field | Value |
| --- | --- |
| Fixture | `openrecomp-phase7-bank-switching-structure-fixture` |
| License / origin | Apache-2.0 / original |
| Source | `.openrecomp-phase7/fixture/p7_bank_switching_fixture.asm` |
| Source sha256 | `f17abf04...` (in `bank_structure.json`) |
| ROM sha256 / size | `902a9c4281a7616a67f12df08b2b3526867f1bff831c982530c53cc769cbd53a` / 73744 |
| PRG / CHR | 4 x 16 KiB / 1 x 8 KiB, mapper 1, horizontal |
| Exit site | `$C024` (`jmp ($02FF)` run-exit thunk) |

The fixed bank (bank 3) commits PRG bank 1 through an unrolled five-write
constant sequence and calls `$8000`; the bank-1 routine calls back into the
fixed helper at `$C100`; banks 0 and 2 hold different routines that are never
selected.

## Bank-aware structure

`.openrecomp-phase7/src/p7_bank_structure_v1.py` builds one architecture-
neutral structure per proven physical bank identity using only the shared
neutral layers (`openrecomp.cfg`, `..functions`, `..call_graph`,
`..translation_units`, `..indirect_control_flow`) through the frozen
`openrecomp.frontends.nes6502` bridge:

- bank 1: 4 proven instructions, 1 function, 1 translation unit, entry
  `$8000` (cross-bank call entry), external `jsr $C100` -> bank 3;
- bank 3: 22 proven instructions, >= 4 functions, >= 2 translation units,
  entries `$C000`/`$C100` (cross-bank call entry) and `$C140`/`$C141`,
  external `jsr $8000` -> bank 1, one unresolved indirect site at `$C024`
  with no fabricated targets;
- two proven cross-bank call edges total; zero merged CPU addresses.

## Verified behavior

- Reachability: `OK`, 26 proven instructions, 0 unresolved, banks {1, 3}.
- Reference execution through the frozen independent 6502 core and MMC1
  platform (decode windows synced to the live bank state): exit reached at
  `$C024`, markers `$0300=$77`, `$0301=$77`, `$0302=$42`, both `$8000` and
  `$C100` executed.
- No-fabrication fail-closed: a mutated cross-bank edge, a missing cross-bank
  edge, a non-OK reachability document and a truncated PRG are all rejected
  with `P7BankStructureError`/`BankReachabilityError`.

## Official gate

- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-05
  --script tools/test_phase7_bank_structure_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-05 --tests-json p7_05_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 1917 bytes raw, raw sha256
    `70bd60cafacba93b19faac42a598a70d17767e21df24f7e56c6f8f76c4c1ec17`,
    LF sha256
    `74c0bb5412f101e7d0ec027c21e8bbb8d43dc799b26141ef3bf15a8ed0dc961e`.
  - `p7_05_tests.json` sha256
    `670fd4bc26dcc5c831be739455c1d1a5ad5775593c7e92b2b3fe6fccfc757355`,
    `tests=38`.
- Markers: `OPENRECOMP_P7_05=PASS`,
  `OPENRECOMP_PHASE7_BANK_STRUCTURE_V1=PASS tests=38`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Changes

- Added `.openrecomp-phase7/fixture/p7_bank_switching_fixture.asm` and
  `.openrecomp-phase7/src/p7_bank_switching_fixture_v1.py`.
- Added `.openrecomp-phase7/src/p7_bank_structure_v1.py`.
- Added `tools/test_phase7_bank_structure_v1.py`.
- Extended `.openrecomp-phase7/src/p7_bank_reachability_v1.py` additively
  with bank-qualified `instructions` and `edges` outputs (existing checks and
  P7-04 evidence unchanged).
- Updated `.openrecomp-phase7/src/p7_dispatch_reference_v1.py` to sync the
  decode image with the live MMC1 window state (needed for switchable-window
  execution; P7-03 reference behavior unchanged and re-verified).
- Updated `.openrecomp-phase7/SOURCE_SHA256SUMS.txt`, `STATE.md`,
  `STAGE_QUEUE.md`, `HANDOFF.md`.
- No frozen Phase-1..Phase-6 file was modified.

## Limitations

- The structure covers only proven physical-bank identities; unresolved
  candidates are excluded (recorded as `rejected_unresolved_identities`).
- Bank 0/2 routines are intentionally never selected; the fixture is a
  bounded structural proof, not general banked-program recovery.

## Evidence index

- `RESULT.md`, `changed_files.txt`, `bank_structure.json`, `p7_05_tests.json`,
  `official_runs.json`, `determinism.json`, `run1.txt`, `run1.err.txt`,
  `run2.txt`, `run2.err.txt`.

## Next stage

P7-06 Indirect jump evidence model for the three `$E2` sites.
