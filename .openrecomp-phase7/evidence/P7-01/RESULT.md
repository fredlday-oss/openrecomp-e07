# P7-01 TMNT Frontier Re-derivation - Result

Verdict: `PASS` (frontier re-derived with byte-identical classifications; no
translation changes)

## Baseline

- Branch `phase7/nes-translation-frontier-v1` at the P7-00 boundary commit
  (`phase7: complete P7-00 phase-7 boundary and freeze the P7 queue`),
  descending from the frozen Phase-6 terminal commit
  `1643817d43196c43155805249137e4b4e4a21eb1`, tree
  `cda3f535be43dc6f3d4b457d11d356ae39ea34af`.

## Objective (frozen queue)

Reproduce the Phase-6 private TMNT frontier from scratch with deterministic
classifications; confirm undocumented opcode `0x7C` at `0xC570`, unresolved
`$E2` indirect sites `0x86E8`/`0x8956`/`0x8F3C` and the bank-window candidate
frontier; prove no mapper blocker has returned. No translation changes.

## Method

`.openrecomp-phase7/src/p7_frontier_rederive_v1.py` re-runs the frozen
Phase-6 private pipeline (`p6_private_run_v1.run`) and the frozen Phase-6
workflow (`p6_workflow_v1.run`) on the live private image, then requires
canonical projectional equality with the committed Phase-6 records:

| Anchor | sha256 |
| --- | --- |
| P6-10 `tmnt_pipeline.json` | `0b8c9014fa11f9e363f1cfb1c569048f786b8baec2117769adb862b375a3ebdc` |
| P6-10 `blockers.json` | `6b8b789cb691da742c270b81c98849bbda952642ad393cc5a4af230bc97e41c5` |
| P6-12 `blockers.json` | `b5cb9ef40625195baef160717ae15647091d6b6b0a13c2f24b9c8dab5c4ea579` |
| P6-13 `frontier_record.json` | `e49a0b3422d6a65b5b50ce820db5c9f9d02ef3662aa114f5287db3a8232bf484` |
| P6-13 `private_workflow.json` | `07ce9a558582ed1178b08ff158e2bff41ce9939e0416aaf07fb0dc64f180dd0e` |

All eight comparison classes are true: pipeline projection, workflow
projection, frontier record, P6-10 blockers, P6-12 private blockers, runtime
support identity (`2e3fa4ba...`), image identity (`2a9345e6...`, 262160
bytes) and mapper-blocker supersession.

## Re-derived classifications

- Ingestion `SUPPORTED_MMC1`; variant `SUPPORTED_PROFILE`; no active mapper
  blocker (the P6-01 `BLOCKED_MMC1_MAPPER_NOT_YET_IMPLEMENTED` remains
  `SUPERSEDED`; the frozen Phase-5 mapper still fails closed by design).
- Power-on registers `{control: 12, prg_bank: 0, chr_bank_0: 0,
  chr_bank_1: 0}`; PRG windows `(0, 7)`; PRG-RAM disabled.
- Documented-control-flow frontier fails closed at `0xC570`
  (`0xc570: undocumented 6502 opcode 0x7c`) after 1250 candidate instructions
  / 2711 bytes (202 fixed window, 1048 low window), 42 distinct opcode forms,
  42 dynamic returns, no interrupt or outside-region targets,
  `pending_at_stop=11`, `truncated=false`.
- Opcode frontier `BLOCKED_UNSUPPORTED_OPCODE` with exactly one unsupported
  entry at `0xC570` (kind `undocumented_opcode`).
- Indirect control flow `UNRESOLVED`: `jmp ($00E2)` at `0x86E8`, `0x8956`,
  `0x8F3C`, each `UNRESOLVED_INDIRECT_JUMP` with empty targets.
- Blockers (exact order): `unsupported_opcode` / `unresolved_indirect_control_flow`
  / `bank_state_unresolved` / `platform_runtime_not_tested`.
- Translation `NOT_ATTEMPTED`, generated sources `NOT_GENERATED`, native
  build/execution `NOT_ATTEMPTED`, runtime platform `NOT_TESTED`.

## Official gate

- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-01
  --script tools/test_phase7_frontier_rederive_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-01 --tests-json p7_01_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 2589 bytes raw, raw sha256
    `fc9f6a0e1b8ed1501026964f3401ba6385239fd0fc3daf8d0f6d0c47d8f4a6e8`,
    LF sha256
    `bd28ad98b72eff864701d9f42826b764da0a0d1cc3d38003e1fb219a16a13b3e`.
  - `p7_01_tests.json` sha256
    `8c518674626f9f97a4a75700cb69805ca4b964c06268e4ea65804d3d7ee88d05`,
    `tests=49`; both runs produced the same tests-json hash.
- Markers: `OPENRECOMP_P7_01=PASS`,
  `OPENRECOMP_PHASE7_FRONTIER_REDERIVATION_V1=PASS tests=49`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Determinism

- The re-derivation record is canonical-identical across both in-gate runs
  and stable digests are recorded:
  pipeline projection `7de1bd5f...` (see `frontier_rederivation.json` for the
  full values), workflow projection and frontier record digests pinned in the
  stage record.

## Negative / fail-closed coverage

- Missing private path and a synthetic malformed `*.bin` container both fail
  closed as `P7FrontierError` without traceback.
- Evidence hygiene: the rederivation record contains no private ROM bytes;
  no ROM-extension file exists in the stage scratch tree; the workflow
  workspace declares no generated ROM files.

## Regressions

- `tools/test_nes_rom_v1.py`: exit 0, empty stderr.
- `tools/test_phase7_boundary_v1.py` re-run into ignored scratch evidence:
  exit 0, empty stderr, `OPENRECOMP_P7_00=PASS`.

## Changes

- Added `.openrecomp-phase7/src/p7_frontier_rederive_v1.py`.
- Added `tools/test_phase7_frontier_rederive_v1.py`.
- Updated `.openrecomp-phase7/SOURCE_SHA256SUMS.txt`,
  `.openrecomp-phase7/STATE.md`, `.openrecomp-phase7/STAGE_QUEUE.md` and
  `.openrecomp-phase7/HANDOFF.md`.
- The P7-00 boundary gate's `control-plane:current-stage` check was relaxed
  from an exact `P7-00` pin to the stage-shape `P7-\d\d` (no semantic change;
  required so frozen boundary gates can be re-run from later stages). The
  P7-00 evidence record remains unchanged; the boundary gate's re-run in this
  stage is recorded above.
- No frozen Phase-1..Phase-6 file was modified.

## Limitations

- The private frontier remains blocked (undocumented opcode, unresolved
  indirect jumps, bank-state ambiguity); no translation or native execution is
  claimed, and TMNT playability remains `NOT_PROVEN`.
- Re-derivation proves determinism and equality with the frozen Phase-6
  classifications, not that those classifications are complete.

## Evidence index

- `RESULT.md`, `changed_files.txt`, `frontier_rederivation.json`,
  `p7_01_tests.json`, `official_runs.json`, `determinism.json`,
  `run1.txt`, `run1.err.txt`, `run2.txt`, `run2.err.txt`.

## Next stage

P7-02 Undocumented opcode 0x7C classification.
