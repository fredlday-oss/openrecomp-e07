# OpenRecomp Phase 5 State

PHASE=5
BASELINE_TAG=openrecomp-phase4-pass
BASELINE_OBJECT=e7eaab18fee267b3d7962db13835c9e14dd77fc2
BASELINE_COMMIT=b3c71fb690f00b4811e8ec30c28f7725141295d0
BASELINE_TREE=f2ca3080915aa68f403526b89dfc17454687aed6
CURRENT_STAGE=P5-06
LAST_PASSED_STAGE=P5-05
STATUS=ACTIVE
NES_PLATFORM_STATUS=NOT_PROVEN
FINAL_VERDICT=NOT_PROVEN
OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN
OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
QUEUE_FREEZE=FROZEN
QUEUE_FREEZE_STAGES=P5-01..P5-99

## Phase-4 frozen boundary identities

- Tag `openrecomp-phase4-pass` (annotated, object
  `e7eaab18fee267b3d7962db13835c9e14dd77fc2`) resolves to commit
  `b3c71fb690f00b4811e8ec30c28f7725141295d0`, tree
  `f2ca3080915aa68f403526b89dfc17454687aed6`.
- Phase-4 terminal markers on the frozen tree:
  `OPENRECOMP_P4_99=PASS`,
  `OPENRECOMP_PHASE4_FINAL_VERDICT_V1=PASS tests=79`,
  `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=PASS` (bounded audited claim only),
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`.
- Frozen integrity identities:
  - `tools/test_phase4_final_verdict_v1.py` sha256
    `6c357c18401ebff522810e8106fdd70032a7a2774ea63ad1377351aa3ca22abd`
  - P4-99 official stdout: 2609 bytes raw, raw sha256
    `903308caf2167053de63f8d87a7376c09125c7ea0d0fd2d0fc08a90d90ec8c6e`,
    LF sha256
    `79c6f395637bf195e478b03eeadd009dfbf83df4e2e51648245a08d93acbca7d`
  - P4-99 record sha256
    `f13cf89155daaf07731097a7530a642c7cbd60cc5ae231e9f602139cdcc78154`
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

## Queue freeze record (P5-00 boundary)

- Frozen contract: `.openrecomp-phase5/STAGE_QUEUE.md` `## Queue freeze`, rows
  `P5-01` .. `P5-99` exactly as listed, effective before any P5-01
  implementation work.
- No stage status changed at the freeze: `P5-01` .. `P5-99` stay `QUEUED`
  until their own gates pass.
- The freeze is a control-plane record only: no capability claim, no change to
  the frozen Phase-1/Phase-2/Phase-3/Phase-4 boundaries and no promotion of
  the Phase-5 terminal marker.

## Stage ledger

| ID | Stage | Status | Evidence |
| --- | --- | --- | --- |
| P5-00 | Phase-5 boundary | PASS | `.openrecomp-phase5/evidence/P5-00/` |
| P5-01 | NES/iNES ingestion and inventory | PASS | `.openrecomp-phase5/evidence/P5-01/` |
| P5-02 | 2A03/6502 decode + reachable instruction frontier | PASS | `.openrecomp-phase5/evidence/P5-02/` |
| P5-03 | CPU semantics proof | PASS | `.openrecomp-phase5/evidence/P5-03/` |
| P5-04 | ProgramModel / CFG / functions / translation units | PASS | `.openrecomp-phase5/evidence/P5-04/` |
| P5-05 | NES CPU memory map + mapper model | PASS | `.openrecomp-phase5/evidence/P5-05/` |
| P5-06 | PPU boundary / deterministic graphics model | QUEUED | `.openrecomp-phase5/evidence/P5-06/` |
| P5-07 | APU/input/timing/interrupt boundary | QUEUED | `.openrecomp-phase5/evidence/P5-07/` |
| P5-08 | Host emission + NES platform adapter | QUEUED | `.openrecomp-phase5/evidence/P5-08/` |
| P5-09 | Native execution of legal NES fixture | QUEUED | `.openrecomp-phase5/evidence/P5-09/` |
| P5-10 | Independent NES reference equivalence | QUEUED | `.openrecomp-phase5/evidence/P5-10/` |
| P5-11 | Private TMNT compatibility run | QUEUED | `.openrecomp-phase5/evidence/P5-11/` |
| P5-12 | Reproducible NES package | QUEUED | `.openrecomp-phase5/evidence/P5-12/` |
| P5-90 | Phase-5 whole regression | QUEUED | `.openrecomp-phase5/evidence/P5-90/` |
| P5-91 | Evidence index + compatibility limitations | QUEUED | `.openrecomp-phase5/evidence/P5-91/` |
| P5-99 | Final Phase-5 verdict | QUEUED | `.openrecomp-phase5/evidence/P5-99/` |

## P5-00 acceptance criteria

1. Phase-4 frozen tag `openrecomp-phase4-pass` (annotated) resolves to the
   recorded object/commit/tree, and the Phase-5 branch descends from that
   boundary.
2. The Phase-4 final verdict gate independently re-passes in the reconstructed
   pre-verdict context with byte-identical stdout to the recorded official
   capture (2609 bytes raw, raw `903308ca...`, LF `79c6f395...`, exit 0, empty
   stderr, `tests=79`), and the committed P4-99 record and terminal marker
   verify as PASS.
3. The Phase-5 control plane exists (STATE, HANDOFF, STAGE_QUEUE, SCOPE,
   CONTROL_POLICY, EVIDENCE_SCHEMA, FIXTURE_POLICY, evidence/) and is
   deterministic; the queue `P5-01` .. `P5-99` is frozen and no new NES
   capability is claimed (`NES_PLATFORM_STATUS=NOT_PROVEN`).
4. ROM safety: the private fixture exists at its recorded path with the
   recorded size/hash; no ROM image or ROM-derived binary copy is tracked or
   present anywhere under the repository; `.gitignore` excludes `*.nes`,
   `*.fds`, `*.unf`, `*.unif` and commercial ROM directories.
5. Public/private fixture separation is recorded in `FIXTURE_POLICY.md`.
6. The working tree has no unexpected new untracked paths beyond the
   documented Phase-2/Phase-3 residue and the Phase-5 control plane.
