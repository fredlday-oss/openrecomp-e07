# P7-14 Reusable Bank-Aware ROM-to-Native Workflow - Result

Verdict: `PASS`

## Baseline

- Branch `phase7/nes-translation-frontier-v1` at the P7-13 boundary commit.

## Workflow

`.openrecomp-phase7/src/p7_workflow_v1.py` (`p7_rom_to_native_v1`): one
deterministic entry point accepting a local ROM path and producing inventory,
compatibility classification, bank-aware frontier, `$E2` indirect
classification, the inline-dispatch closure, generated native sources/build
when supported, and explicit fail-closed blockers otherwise. The source ROM is
never copied into a ROM-extension file, never executed and never embedded in
evidence.

## Verified runs

| Input | Status | Frontier | Indirect | Output |
| --- | --- | --- | --- | --- |
| Public bank-switching fixture | `COMPLETED` | `OK`, 26 proven / 0 unresolved | run-exit thunk only | sources generated, native `EXECUTABLE_REPRODUCIBLE` |
| Public indirect-flow fixture | `COMPLETED_WITH_FRONTIER` | `OK`, 61 specialized identities | exact + finite resolved (lowest-target policy), 1 unresolved recorded | sources generated, native `EXECUTABLE_REPRODUCIBLE`, runtime fail-closed site |
| Private TMNT image | `FAIL_CLOSED` | `BLOCKED_UNDECODABLE` at `0xC570`, 530 proven / 14027 unresolved-limited | 30 unsupported pointer sites + unresolved `$E2` entries | no sources, no build, hashes only |

Workspace hygiene: no byte-identical ROM copy and no ROM-extension file in
any workspace; the private image is never written anywhere.

## Official gate

- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-14
  --script tools/test_phase7_workflow_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-14 --tests-json p7_14_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 1518 bytes raw, raw sha256
    `d53e840443598b37a2d04e4afb8dbc58772e2af7f4d06ca5f7b1ca695e881699`,
    LF sha256
    `69216467b0463b3f14c71284dddb43300942f4fce5a88fbd89f4cca8aa8438b8`.
  - `p7_14_tests.json` sha256
    `8e2ead4a0dd3fa0d11722e5122b58d4a049ecf64289f3eed7de79d7194577ea2`,
    `tests=33`.
- Markers: `OPENRECOMP_P7_14=PASS`,
  `OPENRECOMP_PHASE7_BANK_WORKFLOW_V1=PASS tests=33`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Regressions

- `tools/test_nes_rom_v1.py`: exit 0, empty stderr.
- `tools/test_phase7_private_run2_v1.py` re-run into scratch: PASS.

## Changes

- Added `.openrecomp-phase7/src/p7_workflow_v1.py` and
  `tools/test_phase7_workflow_v1.py`.
- Updated `.openrecomp-phase7/SOURCE_SHA256SUMS.txt`, `STATE.md`,
  `STAGE_QUEUE.md`.

## Limitations

- Bounded to the audited mechanisms; the private image fails closed with its
  exact blockers; no general compatibility claim.

## Evidence index

- `RESULT.md`, `changed_files.txt`, `workflow.json`, `p7_14_tests.json`,
  `official_runs.json`, `determinism.json`, `run1.txt`, `run1.err.txt`,
  `run2.txt`, `run2.err.txt`.

## Next stage

P7-90 Whole regression.
