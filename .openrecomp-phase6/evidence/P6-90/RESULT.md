# P6-90 Whole Regression - Result

Verdict: `PASS` (frozen chain re-verified; Phase-1 host gates, Phase-5 whole
regression and every Phase-6 stage gate re-executed deterministically)

## Baseline

- Branch `phase6/nes-compat-v1` at the P6-13 boundary commit
  `6c8d41e24ba71c8046cedf3f5b26cda521273070`, tree
  `9b5985bb7e648cebd6943f3bbc20581db5c75fc0`, descending from the Phase-5
  frozen boundary `e8d3627a622d0ca3196b117c5112f29fabdb49e7` (tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).

## Objective (frozen queue)

Re-run the required Phase-1, Phase-2, Phase-3, Phase-4, Phase-5 and Phase-6
gates from the audited tree. Preserve frozen historical evidence. Require
deterministic outputs.

## Changes (additive)

- `tools/test_phase6_whole_regression_v1.py`: new P6-90 gate implementing the
  frozen-chain re-verification, the Phase-1 host gate re-run, the Phase-5
  whole-regression re-run in its reconstructed pre-P5-90 context, and the
  re-run of every Phase-6 stage gate with byte-identical official stdout.
- `.openrecomp-phase6/SOURCE_SHA256SUMS.txt`: adds the new gate identity.
- `.openrecomp-phase6/STATE.md`, `STAGE_QUEUE.md`, `HANDOFF.md`: stage
  bookkeeping.
- No frozen Phase-1..5 or Phase-6 source, gate, evidence or control-plane file
  was modified; the transient Phase-4 sidecar restore logic found nothing to
  restore (`restored_frozen_sidecars = []`).

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-90
  --script tools/test_phase6_whole_regression_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-90 --tests-json p6_90_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 2836 bytes raw, raw sha256
    `120d002830037ac26d5780e0cdb820f8dbd4bd55415e6f2b9aabb08cda8c97fa`,
    LF sha256
    `a693d703e574618fa7f99100a0f0c33d63ddc1fc064cd2cb9d97d2eb5c24adec`.
  - `p6_90_tests.json` sha256
    `930f6ec57ea62b8e2e5aceb0fff2fc1369eafc876f51f6bf7f933b64bd8cb37f`,
    `tests=83`; both official runs produced the same tests-json hash.
- Markers: `OPENRECOMP_P6_90=PASS`,
  `OPENRECOMP_PHASE6_WHOLE_REGRESSION_V1=PASS tests=83`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Frozen chain and terminal records

- Phase-5 annotated tag object `b5d6832b...` -> commit `e8d3627a...` -> tree
  `468fb978...`; Phase-4 (object `e7eaab18...` / commit `b3c71fb6...` / tree
  `f2ca3080...`); Phase-3 (object `ac315245...` / commit `e16e4b29...` / tree
  `a940f0d8...`); Phase-2 commit `01b1d7cb...`; Phase-1 commit `46c2f971...`;
  HEAD descends from the Phase-5 boundary.
- Root manifest sha256 `76f77bbc...` with 134 entries; Phase-3 manifest sha256
  `a7d0953c...` with 24 entries; Phase-4 and Phase-5 manifests verified
  entry-wise; Phase-6 manifest verified entry-wise.
- P3-99 record `c893250b...` / gate `ba581490...` PASS with terminal
  `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=PASS`; P4-99 record `f13cf891...` /
  gate `6c357c18...` PASS with terminal
  `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=PASS`; P5-99 record `b0e8267c...` /
  gate `bc772128...` PASS with `tests=87`, terminal
  `OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=PASS`, general marker permanently
  `NOT_PROVEN`, and official captures byte-identical at 2971 bytes raw
  `bc1f1e97...`.
- Phase-2 terminal marker `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`
  verified in the frozen Phase-2 control plane.

## Re-executed gates

- Phase-1: `tools/phase1_host_gates_v1.py` re-ran directly, exit 0, empty
  stderr, `OPENRECOMP_PHASE1_HOST_GATES_V1=PASS` and
  `OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2` (the two skips are
  recorded unavailable external POSIX/gcc toolchains), including the
  source-integrity-only re-run.
- Phase-4: the P4-99 final verdict gate is re-executed inside the Phase-5
  whole-regression reconstruction (through P5-00), re-verifying the
  Phase-1/2/3/4 chain records.
- Phase-5: the frozen P5-90 whole-regression gate re-ran in its deterministic
  reconstructed pre-P5-90 context (detached worktree at the parent of the
  P5-90 completion commit `ee6a98af45...`, with the frozen P5-90 gate and the
  untracked public helper restored and the local Phase-3 toolchain junction
  present); exit 0, empty stderr, stdout byte-identical to the recorded
  official capture (2039 bytes raw `e487dbc0...`) and `p5_90_tests.json`
  sha256 `431d4e5a...` identical. This re-executes P5-00 .. P5-12, all
  byte-identical to their recorded captures.
- Phase-6: every stage gate re-ran from the audited tree with byte-identical
  official stdout, empty stderr and exit 0:
  `P6-00` 3201 B, `P6-01` 3140 B, `P6-02` 2305 B, `P6-03` 2444 B,
  `P6-04` 2949 B, `P6-05` 2761 B, `P6-06` 3073 B, `P6-07` 3170 B,
  `P6-08` 2913 B, `P6-09` 4147 B, `P6-10` 2886 B, `P6-11` 2871 B,
  `P6-12` 4375 B, `P6-13` 3261 B.

## Phase-2/Phase-3 coverage boundary

- The Phase-2 and Phase-3 stage-gate re-executions are pinned by their frozen
  boundary tags, frozen source manifests, terminal verdict records and the
  P4-99/P5-99 chains (the Phase-5 reconstruction re-runs the Phase-4 final
  verdict, which re-verifies the Phase-3 record and the Phase-2/Phase-1
  boundary commits). Their whole-regression gates (P2-90/P3-90) are not
  re-executable outside their frozen execution contexts without altering
  frozen Phase-2/Phase-3 trees; this matches the Phase-5 whole-regression
  precedent, which re-verified rather than re-ran the earlier-phase gates.
  No frozen file was changed to obtain this coverage.

## Evidence immutability and side effects

- No tracked evidence under `.openrecomp-phase5/evidence` or
  `.openrecomp-phase6/evidence` was modified by the re-runs
  (`immutability:no-tracked-evidence-modified`).
- The transient Phase-4 sidecar restore check found nothing to restore.
- No private ROM bytes appear in any P6-90 evidence file.
- Scratch and reconstruction workspaces are removed; only ignored scratch
  paths are used.

## Claim ledger deltas

- No new capability; this stage is a verification audit. The terminal marker
  remains `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`; general
  compatibility remains
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Limitations

- P6-90 re-executes the Phase-1 host gates, the Phase-5 chain (including the
  Phase-4 verdict reconstruction) and the complete Phase-6 stage chain; the
  Phase-2/Phase-3 stage-gate bodies are covered by frozen records and the
  re-executed verdict chains, not by direct re-execution (recorded above).
- The two Phase-1 host checks that require unavailable external POSIX/gcc
  toolchains remain `SKIPPED_TOOLCHAIN_UNAVAILABLE`, exactly as recorded.
- No general NES compatibility, all-MMC1 coverage, game compatibility, cycle
  accuracy or full PPU/APU accuracy is claimed.

## Repository side effects

- Tracked additive changes: new gate, manifest entry, updated control plane,
  P6-90 evidence. Scratch/build artifacts remain ignored; no ROM copy exists.

## Evidence index

`RESULT.md`, `p6_90_tests.json`, `official_runs.json`, `determinism.json`,
`whole_regression.json`, `run1.txt`, `run2.txt`, `run1.err.txt`,
`run2.err.txt`, `changed_files.txt`.

## Next stage

P6-91 - Evidence index and compatibility matrix.
