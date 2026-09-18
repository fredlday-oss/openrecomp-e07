# P6-00 Phase-6 Boundary - Result

Verdict: `PASS`

## Baseline

- Branch: `phase6/nes-compat-v1` (created from `openrecomp-phase5-pass` for
  this stage; baseline commit `e8d3627a622d0ca3196b117c5112f29fabdb49e7`).
- Baseline tag `openrecomp-phase5-pass`: annotated object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d` resolves to commit
  `e8d3627a622d0ca3196b117c5112f29fabdb49e7`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`.
- Frozen earlier boundaries re-verified: Phase-4 tag object
  `e7eaab18fee267b3d7962db13835c9e14dd77fc2` -> commit
  `b3c71fb690f00b4811e8ec30c28f7725141295d0`, tree
  `f2ca3080915aa68f403526b89dfc17454687aed6`; Phase-3 tag object
  `ac31524504b1b5cc63aabcfd5132a3eb4275e8e9` -> commit
  `e16e4b29b90f379615f1af97e47747cd1d531796`, tree
  `a940f0d84a32adaf191f7ff2bebfb24cc855cde0`; Phase-2 commit
  `01b1d7cba8c931fca95d041389cfb1902b7c89fe`; Phase-1 commit
  `46c2f971e1a42cf49bd936bad94697b81bf31002`; descent from the Phase-5
  boundary commit verified.

## Objective (frozen queue)

Verify the exact Phase-5 PASS boundary, re-run the Phase-5 final verdict
deterministically, establish the Phase-6 control plane, public/private fixture
separation and the frozen queue. No MMC1 capability claimed.

## Changes (additive)

- `.gitignore`: added `.openrecomp-phase6/build/` and
  `.openrecomp-phase6/scratch/` transient workspace rules.
- `.openrecomp-phase6/`: new control plane (`STATE.md`, `HANDOFF.md`,
  `STAGE_QUEUE.md`, `CONTROL_POLICY.md`, `EVIDENCE_SCHEMA.md`, `SCOPE.md`,
  `FIXTURE_POLICY.md`, `SOURCE_SHA256SUMS.txt`,
  `src/p6_stage_runner_v1.py`, `evidence/P6-00/`).
- `tools/test_phase6_boundary_v1.py`: new P6-00 gate.
- No frozen file was modified.

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-00
  --script tools/test_phase6_boundary_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-00 --tests-json p6_00_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 3201 bytes raw, raw sha256
    `9391a99a241f0813584587b0bc4db7559f18ebc500897ca8c43bcce03b64e972`,
    LF sha256
    `ca7ab21017aa5f89699b718ef6541d9f440a3d75a17730eb6343b90d4a148ffd`.
  - `p6_00_tests.json` sha256
    `24c15b25fabc0f1ed3d7621f709800f95dea4e7f4925a0965803752b3d04b257`.
- Markers: `OPENRECOMP_P6_00=PASS`,
  `OPENRECOMP_PHASE6_BOUNDARY_V1=PASS tests=85`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.
- Gate sha256 `0bc63e46c60f81a6b9dc86cb3eb61c91ea4cb10614822e4687384b776b958018`;
  runner sha256
  `2167f6e2210b11d716c11c4416b2a43c34a2643c684dc0dffe7b5985014de3d0`; the
  Phase-6 manifest verifies both entries.

## Phase-5 final verdict re-verification

The Phase-5 final verdict gate (`tools/test_phase5_final_verdict_v1.py`, sha256
`bc772128a91344e17d1ed00fb5e2b503aae8a0ef5e4ad9de35b7fbdfcba52143`) was
re-run twice inside a reconstructed pre-verdict context: a temporary detached
worktree at the exact `openrecomp-phase5-pass` tag with only the two
post-verdict control-plane edits reverted (`LAST_PASSED_STAGE=P5-99` ->
`P5-91`; the promoted terminal marker in the queue back to its reserved
`NOT_PROVEN` form). Both runs:

- exit 0, empty stderr, 2971-byte stdout byte-identical to the recorded
  official capture (raw sha256
  `bc1f1e97f9f34cb06eba388a96e3879e4304e9a38a7224051d1c05aceced1591`, LF
  sha256 `2378b480a1be7cbb10219e3da0c0171c48de962fb45c31ac8033c28e0f133907`);
- `tests=87`, markers `OPENRECOMP_P5_99=PASS`,
  `OPENRECOMP_PHASE5_FINAL_VERDICT_V1=PASS tests=87`,
  `OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=PASS`;
- regenerated `p5_99_tests.json` sha256
  `b0e8267c70ab2e990ca74665d8020ba463280447dd9f5fb370f4411cfb6e72c9`,
  identical to the committed record.

The temporary worktree was removed and the repository worktree list pruned;
no tracked file in this worktree was touched by the reconstruction. The
committed Phase-5 record verifies as `PASS` with the terminal marker promoted
for the bounded claim only and
`OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` permanent.

## Control-plane freeze

- The queue rows `P6-01` .. `P6-99` are frozen exactly as recorded in
  `.openrecomp-phase6/STAGE_QUEUE.md` `## Queue freeze`; the freeze changes no
  stage status and adds no capability claim.
- `MMC1_PLATFORM_STATUS=NOT_PROVEN`, `FINAL_VERDICT=NOT_PROVEN` and the
  terminal/general Phase-6 markers remain reserved.

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
- Public/private separation and the public MMC1 fixture
  provenance/licensing rules are recorded in
  `.openrecomp-phase6/FIXTURE_POLICY.md`; the private image is classified
  `PRIVATE_LOCAL_COMPATIBILITY_FIXTURE` and can never be the public proof
  fixture.

## Working tree

- Documented pre-existing Phase-2/Phase-3 untracked residue and the two
  Phase-3 re-run sidecars remain uncommitted as before.
- The P6-00 stage files are committed with this boundary; no unexpected path
  was present at the official runs.

## Limitations

- P6-00 adds no MMC1 capability; the terminal/general markers remain reserved
  and `MMC1_PLATFORM_STATUS=NOT_PROVEN`.
- The Phase-5 verdict re-run is a documented reconstruction of the
  pre-verdict control-plane context, not a mutation of frozen history.
- The private fixture is recorded by metadata/hash only; no ROM bytes are
  stored in this repository.

## Evidence files

`RESULT.md`, `p6_00_tests.json`, `official_runs.json`, `determinism.json`,
`control_plane_manifest.txt`, `run1.txt`, `run2.txt`, `run1.err.txt`,
`run2.err.txt`, `changed_files.txt`.

## Next stage

P6-01 - MMC1 requirements and fixture inventory.
