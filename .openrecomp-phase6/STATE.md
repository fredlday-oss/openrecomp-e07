# OpenRecomp Phase 6 State

PHASE=6
BASELINE_TAG=openrecomp-phase5-pass
BASELINE_OBJECT=b5d6832ba2374b810f4c24500ed9093a9481fd8d
BASELINE_COMMIT=e8d3627a622d0ca3196b117c5112f29fabdb49e7
BASELINE_TREE=468fb9788350de393d3de2ca9471b7d874ee8dc9
CURRENT_STAGE=P6-03
LAST_PASSED_STAGE=P6-03
STATUS=ACTIVE
MMC1_PLATFORM_STATUS=NOT_PROVEN
FINAL_VERDICT=NOT_PROVEN
OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN
OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
QUEUE_FREEZE=FROZEN
QUEUE_FREEZE_STAGES=P6-01..P6-99

## Phase-5 frozen boundary identities

- Tag `openrecomp-phase5-pass` (annotated, object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`) resolves to commit
  `e8d3627a622d0ca3196b117c5112f29fabdb49e7`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`.
- Phase-5 terminal markers on the frozen tree:
  `OPENRECOMP_P5_99=PASS`,
  `OPENRECOMP_PHASE5_FINAL_VERDICT_V1=PASS tests=87`,
  `OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=PASS` (bounded audited claim only),
  `OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.
- Frozen integrity identities:
  - `tools/test_phase5_final_verdict_v1.py` sha256
    `bc772128a91344e17d1ed00fb5e2b503aae8a0ef5e4ad9de35b7fbdfcba52143`
  - P5-99 official stdout: 2971 bytes raw, raw sha256
    `bc1f1e97f9f34cb06eba388a96e3879e4304e9a38a7224051d1c05aceced1591`,
    LF sha256
    `2378b480a1be7cbb10219e3da0c0171c48de962fb45c31ac8033c28e0f133907`
  - P5-99 record sha256
    `b0e8267c70ab2e990ca74665d8020ba463280447dd9f5fb370f4411cfb6e72c9`
  - Phase-4 boundary: tag object
    `e7eaab18fee267b3d7962db13835c9e14dd77fc2`, commit
    `b3c71fb690f00b4811e8ec30c28f7725141295d0`, tree
    `f2ca3080915aa68f403526b89dfc17454687aed6`
  - Phase-3 boundary: tag object
    `ac31524504b1b5cc63aabcfd5132a3eb4275e8e9`, commit
    `e16e4b29b90f379615f1af97e47747cd1d531796`, tree
    `a940f0d84a32adaf191f7ff2bebfb24cc855cde0`
  - Phase-2 boundary `openrecomp-phase2-pass` =
    `01b1d7cba8c931fca95d041389cfb1902b7c89fe`; Phase-1 boundary
    `openrecomp-phase1-pass` = `46c2f971e1a42cf49bd936bad94697b81bf31002`.
- Documented untracked residue preserved from Phase 2/3 (unchanged):
  `.openrecomp-phase2/backups/`, `.openrecomp-phase2/scratch/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`, the frozen
  verification-context files, the Phase-3 external source/toolchain/build sets
  and the re-run sidecars `.openrecomp-phase3/evidence/P3-00/p3_00_tests.json`
  and `.openrecomp-phase3/evidence/P3-00/residue_manifest.txt`.

## Private fixture identity

- `D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes` classified
  `PRIVATE_LOCAL_COMPATIBILITY_FIXTURE`; size 262160 bytes; SHA-256
  `2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1`.
  Never committed, copied or packaged. See `FIXTURE_POLICY.md`.

## Public proof fixture identity

- To be established at P6-01/P6-06: an original Apache-2.0 MMC1 NES fixture
  authored for Phase 6, with recorded provenance, toolchain, ROM hash,
  PRG/CHR configuration, vectors and mapper metadata. At P6-00 no public MMC1
  fixture or MMC1 capability is claimed.

## Queue freeze record (P6-00 boundary)

- Frozen contract: `.openrecomp-phase6/STAGE_QUEUE.md` `## Queue freeze`, rows
  `P6-01` .. `P6-99` exactly as listed, effective before any P6-01
  implementation work.
- No stage status changed at the freeze: `P6-01` .. `P6-99` stay `QUEUED`
  until their own gates pass.
- The freeze is a control-plane record only: no capability claim, no change to
  the frozen Phase-1/Phase-2/Phase-3/Phase-4/Phase-5 boundaries and no
  promotion of the Phase-6 terminal marker.

## Stage ledger

| ID | Stage | Status | Evidence |
| --- | --- | --- | --- |
| P6-00 | Phase-6 boundary | PASS | `.openrecomp-phase6/evidence/P6-00/` |
| P6-01 | MMC1 requirements and fixture inventory | PASS | `.openrecomp-phase6/evidence/P6-01/` |
| P6-02 | MMC1 serial register protocol | PASS | `.openrecomp-phase6/evidence/P6-02/` |
| P6-03 | MMC1 PRG banking | PASS | `.openrecomp-phase6/evidence/P6-03/` |
| P6-04 | MMC1 CHR banking and mirroring | QUEUED | - |
| P6-05 | MMC1 PRG-RAM and variant boundary | QUEUED | - |
| P6-06 | Public MMC1 proof fixture | QUEUED | - |
| P6-07 | MMC1 static-recompilation integration | QUEUED | - |
| P6-08 | Native execution of public MMC1 fixture | QUEUED | - |
| P6-09 | Independent MMC1 reference equivalence | QUEUED | - |
| P6-10 | Private TMNT compatibility run | QUEUED | - |
| P6-11 | Evidence-driven platform expansion | QUEUED | - |
| P6-12 | Reusable ROM-to-native workflow | QUEUED | - |
| P6-13 | Second private TMNT compatibility run | QUEUED | - |
| P6-90 | Whole regression | QUEUED | - |
| P6-91 | Evidence index and compatibility matrix | QUEUED | - |
| P6-99 | Final Phase-6 verdict | QUEUED | - |

## P6-00 acceptance criteria

1. Phase-5 frozen tag `openrecomp-phase5-pass` (annotated) resolves to the
   recorded object/commit/tree, and the Phase-6 branch descends from that
   boundary.
2. The Phase-5 final verdict gate independently re-passes in the reconstructed
   pre-verdict context with byte-identical stdout to the recorded official
   capture (2971 bytes raw, raw `bc1f1e97...`, LF `2378b480...`, exit 0, empty
   stderr, `tests=87`), and the committed P5-99 record and terminal marker
   verify as PASS.
3. The Phase-6 control plane exists (STATE, HANDOFF, STAGE_QUEUE, SCOPE,
   CONTROL_POLICY, EVIDENCE_SCHEMA, FIXTURE_POLICY, evidence/) and is
   deterministic; the queue `P6-01` .. `P6-99` is frozen and no new MMC1
   capability is claimed (`MMC1_PLATFORM_STATUS=NOT_PROVEN`).
4. ROM safety: the private fixture exists at its recorded path with the
   recorded size/hash; no ROM image or ROM-derived binary copy is tracked or
   present anywhere under the repository; `.gitignore` excludes `*.nes`,
   `*.fds`, `*.unf`, `*.unif` and commercial ROM directories.
5. Public/private fixture separation is recorded in `FIXTURE_POLICY.md`.
6. The working tree has no unexpected new untracked paths beyond the
   documented Phase-2/Phase-3 residue and the Phase-6 control plane.
