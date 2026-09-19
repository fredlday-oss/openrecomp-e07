# P7-00 Phase-7 Boundary - Result

Verdict: `PASS` (control plane established and queue frozen; no new
translation/control-flow capability claimed)

## Baseline

- Branch `phase7/nes-translation-frontier-v1`, created at the frozen Phase-6
  terminal commit `1643817d43196c43155805249137e4b4e4a21eb1`, tree
  `cda3f535be43dc6f3d4b457d11d356ae39ea34af`, descending from the Phase-5
  frozen boundary `e8d3627a622d0ca3196b117c5112f29fabdb49e7` (tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).
- Phase-6 terminal markers on the frozen tree:
  `OPENRECOMP_P6_99=PASS`,
  `OPENRECOMP_PHASE6_FINAL_VERDICT_V1=PASS tests=108`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS` (bounded audited public MMC1
  claim only),
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.
- P6-99 record `p6_99_tests.json` sha256
  `e7e462f15ca64a2d8db130ec664ac309d5ebfef1c128fd392111d19e4be30ea4`.

## Baseline reconciliation: `openrecomp-phase6-pass`

The mission baseline names an annotated tag `openrecomp-phase6-pass`. The tag
is absent, and the frozen Phase-6 P6-99 record states explicitly:

> Terminal tag: not created - the frozen Phase-6 control policy does not
> require one; the terminal boundary is the P6-99 verdict commit on branch
> `phase6/nes-compat-v1` (pre-verdict baseline
> `69cb116f87be0a0ac444097c940bfc2ba50716bc`).

Deterministic checks confirm: `git rev-parse --verify
refs/tags/openrecomp-phase6-pass` fails, `refs/heads/phase6/nes-compat-v1`
resolves to `1643817...`, its tree is `cda3f535...`, and the branch descends
from the Phase-5 boundary. Phase 7 records
`BASELINE_TAG_STATUS=ABSENT_RECONCILED` in `STATE.md` and does not fabricate,
create or modify any frozen tag, history, evidence or verdict.

## Objective (frozen queue)

Verify the exact frozen Phase-6 PASS boundary, re-run the Phase-6 terminal
verdict gate deterministically, establish the Phase-7 control plane, freeze
the queue `P7-01` .. `P7-99` and claim no new translation/control-flow
capability yet.

## Official gate

- Gate: `tools/test_phase7_boundary_v1.py`
- Runner: `python .openrecomp-phase7/src/p7_stage_runner_v1.py --stage P7-00
  --script tools/test_phase7_boundary_v1.py --evidence-dir
  .openrecomp-phase7/evidence/P7-00 --tests-json p7_00_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 3690 bytes raw, raw sha256
    `8d5b206b158ed3198243bc5845b6dba8eaa66edfc60420bb6ac870e3dc5476ca`,
    LF sha256
    `66052b58e6224ae558497e39c3c71d2b4c1a79d3f19c476b5769540fe6cc019b`.
  - `p7_00_tests.json` sha256
    `d0ef5d68a42459d47c64bda3a078db8ab97cf73bd45da9e6141cb8fab02593de`,
    `tests=96`; both runs produced the same tests-json hash.
- Markers: `OPENRECOMP_P7_00=PASS`,
  `OPENRECOMP_PHASE7_BOUNDARY_V1=PASS tests=96`,
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.

## Phase-6 terminal re-run (reconstructed pre-verdict context)

The frozen P6-99 gate verifies the pre-verdict control-plane state, so it is
re-run in a temporary detached worktree at `1643817...` with only the
post-verdict control-plane fields reverted (deterministic anchors, each
verified before replacement):

- `STATE.md`: `LAST_PASSED_STAGE=P6-99` -> `P6-91`,
  `MMC1_PLATFORM_STATUS=PROVEN` -> `NOT_PROVEN`,
  `FINAL_VERDICT=PASS` -> `NOT_PROVEN`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS` -> `NOT_PROVEN`;
- `STAGE_QUEUE.md`: `P6-99` row `COMPLETE` -> `QUEUED`, all promoted
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS` markers -> `NOT_PROVEN`.

Result: two identical runs with exit 0, empty stderr, stdout 3750 bytes raw
sha256 `d7e96e11d94202fff91380dc4020e5523aa7d87dacfb3f05ee35cbf469d3a365`,
LF sha256 `4fafd3842eb1df3d7f44f166cec6bd064d28e71121fffdb882e7ca1969c2978a`
and regenerated `p6_99_tests.json` sha256 `e7e462f1...` - byte-identical to
the recorded official P6-99 capture and record. The temporary worktree was
removed; no tracked file in the Phase-7 worktree was touched.

Reconstruction findings (recorded in `p7_00_tests.json`):
`returncode_zero_both=true`, `stderr_empty_both=true`, `identical_raw=true`,
`identical_stderr=true`, `raw_bytes=3750`, `tests_sha256=e7e462f1...`.

## Control plane

- `.openrecomp-phase7/`: `STATE.md`, `HANDOFF.md`, `STAGE_QUEUE.md`,
  `CONTROL_POLICY.md`, `EVIDENCE_SCHEMA.md`, `SCOPE.md`,
  `FIXTURE_POLICY.md`, `SOURCE_SHA256SUMS.txt`, `src/`, `evidence/`.
- Frozen queue: rows `P7-01` .. `P7-99` (17 rows: P7-01..P7-14, P7-90,
  P7-91, P7-99), names and required outcomes exactly as frozen at this
  boundary; all `QUEUED`.
- Reserved markers recorded in both `STATE.md` and `STAGE_QUEUE.md`:
  `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`.
- `SOURCE_SHA256SUMS.txt` covers the stage runner and the boundary gate and
  verifies.
- Control-plane digest:
  `control_plane_manifest.txt` sha256
  `86f2bcd01afebfb6799bb333c9868739fd9950c1025e899c3c8a688c38a43fa6`.

## ROM safety

- Private fixture present at its recorded path, 262160 bytes, SHA-256
  `2a9345e6...`, MD5 `d60c64b4...`; outside the worktree.
- No tracked ROM-extension file, no ROM-extension file anywhere in the
  worktree, no byte-identical copy of the private image anywhere in the
  worktree; `.gitignore` ROM rules and probes verified.
- Public/private separation recorded in `FIXTURE_POLICY.md`; Phase-7 public
  fixtures are original Apache-2.0 programs to be authored at P7-03/P7-05/
  P7-07.

## Changes

- Added `.openrecomp-phase7/` control plane, source manifest, stage runner and
  P7-00 evidence set.
- Added `tools/test_phase7_boundary_v1.py`.
- Modified `.gitignore` (additive: `.openrecomp-phase7/build/` and
  `.openrecomp-phase7/scratch/` transient workspaces).
- No frozen Phase-1..Phase-6 file was modified.

## Fail-closed / negative coverage

- The gate fails closed (exit 1, no traceback) on any control-plane anchor
  mismatch, manifest mismatch, tag/commit/tree mismatch, P6-99 record change,
  reconstruction stdout/record mismatch, ROM-safety violation, unexpected
  worktree path or unexpected on-disk ROM copy.
- The reconstruction verifies anchor counts before patching
  (`recon:*: anchor count != 1` otherwise) and removes its temporary worktree
  even on failure.

## Limitations

- No translation, control-flow, bank-state or opcode capability is claimed at
  P7-00; `TRANSLATION_FRONTIER_STATUS=NOT_PROVEN`.
- The Phase-6 baseline tag remains absent and is recorded as reconciled; the
  Phase-7 baseline is the P6-99 commit/tree identity.
- TMNT remains a private local compatibility fixture with four recorded
  blockers; playability is `NOT_PROVEN`.

## Evidence index

- `RESULT.md`, `changed_files.txt`, `control_plane_manifest.txt`,
  `p7_00_tests.json`, `official_runs.json`, `determinism.json`,
  `run1.txt`, `run1.err.txt`, `run2.txt`, `run2.err.txt`.

## Next stage

P7-01 TMNT frontier re-derivation.
