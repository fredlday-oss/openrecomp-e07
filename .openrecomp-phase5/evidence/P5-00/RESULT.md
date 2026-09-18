# P5-00 Phase-5 Boundary - Result

Verdict: `PASS`

## Baseline

- Branch: `phase5/nes-platform-v1` (created from `openrecomp-phase4-pass` for
  this stage; baseline commit `b3c71fb690f00b4811e8ec30c28f7725141295d0`).
- Baseline tag `openrecomp-phase4-pass`: annotated object
  `e7eaab18fee267b3d7962db13835c9e14dd77fc2` resolves to commit
  `b3c71fb690f00b4811e8ec30c28f7725141295d0`, tree
  `f2ca3080915aa68f403526b89dfc17454687aed6`.
- Frozen earlier boundaries re-verified: Phase-3 tag object
  `ac31524504b1b5cc63aabcfd5132a3eb4275e8e9` -> commit
  `e16e4b29b90f379615f1af97e47747cd1d531796`, tree
  `a940f0d84a32adaf191f7ff2bebfb24cc855cde0`; Phase-2 commit
  `01b1d7cba8c931fca95d041389cfb1902b7c89fe`; Phase-1 commit
  `46c2f971e1a42cf49bd936bad94697b81bf31002`; descent from the Phase-4
  boundary commit verified.

## Objective (frozen queue)

Verify the exact Phase-4 PASS boundary, rerun the Phase-4 final gate,
establish the Phase-5 control plane, ROM safety policy, public/private fixture
separation and the frozen queue. No NES capability claimed.

## Changes (additive)

- `.gitignore`: added the ROM safety section (`*.nes`, `*.fds`, `*.unf`,
  `*.unif`, `*.prg`, `*.chr`, `Roms/`, `roms/`).
- `.openrecomp-phase5/`: new control plane (`STATE.md`, `HANDOFF.md`,
  `STAGE_QUEUE.md`, `CONTROL_POLICY.md`, `EVIDENCE_SCHEMA.md`, `SCOPE.md`,
  `FIXTURE_POLICY.md`, `SOURCE_SHA256SUMS.txt`, `src/p5_stage_runner_v1.py`,
  `evidence/P5-00/`).
- `tools/test_phase5_boundary_v1.py`: new P5-00 gate.
- No frozen file was modified.

## Official gate

- Runner: `python .openrecomp-phase5/src/p5_stage_runner_v1.py --stage P5-00
  --script tools/test_phase5_boundary_v1.py --evidence-dir
  .openrecomp-phase5/evidence/P5-00 --tests-json p5_00_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 3025 bytes raw, raw sha256
    `825932c59263cae071ac49f49cf90865ec66e1f1b289aad9dc47d9eb4a3b7df0`,
    LF sha256
    `79bdbf3ce4160491a858bcded08c4e08852e907591ea6b4bfac20b2a22abb6e5`.
  - `p5_00_tests.json` sha256
    `4b87897f2297cd89419bf7fd53fc31e2f6ec70a8a05f3ea5f29c97ad5d3bd0f4`.
- Markers: `OPENRECOMP_P5_00=PASS`,
  `OPENRECOMP_PHASE5_BOUNDARY_V1=PASS tests=80`,
  `OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.
- Gate sha256 `219847b8a0265c660a3d6999efe95bcf607364bcd091c2b54da8f2dc84bc58fc`;
  runner sha256
  `5a00d338bd44aed3affb5f480be18fb602638b3be79dc7bbe3c0155034fe36dd`;
  Phase-5 manifest verifies both entries.

## Phase-4 final verdict re-verification

The Phase-4 final verdict gate (`tools/test_phase4_final_verdict_v1.py`, sha256
`6c357c18401ebff522810e8106fdd70032a7a2774ea63ad1377351aa3ca22abd`) was
re-run twice inside a reconstructed pre-verdict context: a temporary detached
worktree at the exact `openrecomp-phase4-pass` tag with only the two
post-verdict control-plane edits reverted (`LAST_PASSED_STAGE=P4-99` ->
`P4-91`; the promoted terminal marker in the queue back to its reserved
`NOT_PROVEN` form). Both runs:

- exit 0, empty stderr, 2609-byte stdout byte-identical to the recorded
  official capture (raw sha256
  `903308caf2167053de63f8d87a7376c09125c7ea0d0fd2d0fc08a90d90ec8c6e`, LF
  sha256 `79c6f395637bf195e478b03eeadd009dfbf83df4e2e51648245a08d93acbca7d`);
- `tests=79`, markers `OPENRECOMP_P4_99=PASS`,
  `OPENRECOMP_PHASE4_FINAL_VERDICT_V1=PASS tests=79`,
  `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=PASS`;
- regenerated `p4_99_tests.json` sha256
  `f13cf89155daaf07731097a7530a642c7cbd60cc5ae231e9f602139cdcc78154`,
  identical to the committed record.

The temporary worktree was removed and the repository worktree list pruned;
no tracked file in this worktree was touched by the reconstruction. The
committed Phase-4 record verifies as `PASS` with the terminal marker promoted
for the bounded claim only and
`OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN` permanent.

## ROM safety and fixture separation

- Private fixture `D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes` exists
  outside the worktree: 262160 bytes, SHA-256
  `2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1`, MD5
  `d60c64b46f9a6b5ee6a78bfe2fee7d48`.
- No `*.nes`/`*.fds`/`*.unf`/`*.unif`/`*.prg`/`*.chr` file is tracked or
  present in the worktree; no file anywhere in the repository matches the
  private image size and hash.
- `.gitignore` probes verified effective through `git check-ignore`
  (`probe.nes`, `probe.fds`, `probe.unf`, `probe.unif`, `Roms/probe.rom`,
  `roms/probe.rom`).
- Public/private separation and the public fixture provenance/licensing rules
  are recorded in `.openrecomp-phase5/FIXTURE_POLICY.md`; the private image is
  classified `PRIVATE_LOCAL_COMPATIBILITY_FIXTURE` and can never be the public
  proof fixture.

## Working tree

- Documented pre-existing Phase-2/Phase-3 untracked residue and the two
  Phase-3 re-run sidecars remain uncommitted as before.
- The P5-00 stage files are committed with this boundary; no unexpected path
  was present at the official runs.

## Limitations

- P5-00 adds no NES capability; `NES_PLATFORM_STATUS=NOT_PROVEN` and the
  terminal/general markers remain reserved.
- The Phase-4 verdict re-run is a documented reconstruction of the
  pre-verdict control-plane context, not a mutation of frozen history.
- The private fixture is recorded by metadata/hash only; no ROM bytes are
  stored in this repository.

## Evidence files

`RESULT.md`, `p5_00_tests.json`, `official_runs.json`, `determinism.json`,
`control_plane_manifest.txt`, `run1.txt`, `run2.txt`, `run1.err.txt`,
`run2.err.txt`.

## Next stage

P5-01 - NES/iNES ingestion and inventory.
