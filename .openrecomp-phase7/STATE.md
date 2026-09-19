# OpenRecomp Phase 7 State

PHASE=7
BASELINE=openrecomp-phase6-pass
BASELINE_TAG_STATUS=ABSENT_RECONCILED
BASELINE_TAG_RECONCILIATION=P6-99 records that the frozen Phase-6 control policy required and created no terminal tag; the authoritative Phase-6 terminal boundary is the P6-99 verdict commit and tree recorded below. No tag is fabricated.
BASELINE_COMMIT=1643817d43196c43155805249137e4b4e4a21eb1
BASELINE_TREE=cda3f535be43dc6f3d4b457d11d356ae39ea34af
BASELINE_TERMINAL=OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS
BASELINE_GENERAL=OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
CURRENT_STAGE=P7-10
LAST_PASSED_STAGE=P7-10
STATUS=ACTIVE
TRANSLATION_FRONTIER_STATUS=NOT_PROVEN
QUEUE_FREEZE=FROZEN
QUEUE_FREEZE_STAGES=P7-01..P7-99
OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

## Phase-6 frozen boundary identities

- Phase-6 terminal commit `1643817d43196c43155805249137e4b4e4a21eb1`, tree
  `cda3f535be43dc6f3d4b457d11d356ae39ea34af`, on branch
  `phase6/nes-compat-v1`.
- The mission baseline tag `openrecomp-phase6-pass` is absent; the frozen
  Phase-6 P6-99 record explicitly states that no terminal tag was created or
  required. Phase 7 records `BASELINE_TAG_STATUS=ABSENT_RECONCILED` and uses
  the commit/tree identity above. No frozen tag, history, evidence or verdict
  is modified.
- Phase-6 terminal markers on the frozen tree:
  `OPENRECOMP_P6_99=PASS`,
  `OPENRECOMP_PHASE6_FINAL_VERDICT_V1=PASS tests=108`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS` (bounded audited public MMC1
  claim only),
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.
- P6-99 official stdout: 3750 bytes raw, raw sha256
  `d7e96e11d94202fff91380dc4020e5523aa7d87dacfb3f05ee35cbf469d3a365`,
  LF sha256
  `4fafd3842eb1df3d7f44f166cec6bd064d28e71121fffdb882e7ca1969c2978a`,
  regenerated record `p6_99_tests.json` sha256
  `e7e462f15ca64a2d8db130ec664ac309d5ebfef1c128fd392111d19e4be30ea4`.
- Earlier frozen boundaries verified by the P7-00 gate: Phase-5 tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d` -> commit
  `e8d3627a622d0ca3196b117c5112f29fabdb49e7` -> tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`; Phase-4 tag object
  `e7eaab18fee267b3d7962db13835c9e14dd77fc2` -> commit
  `b3c71fb690f00b4811e8ec30c28f7725141295d0` -> tree
  `f2ca3080915aa68f403526b89dfc17454687aed6`; Phase-3 tag object
  `ac31524504b1b5cc63aabcfd5132a3eb4275e8e9` -> commit
  `e16e4b29b90f379615f1af97e47747cd1d531796` -> tree
  `a940f0d84a32adaf191f7ff2bebfb24cc855cde0`; Phase-2 boundary commit
  `01b1d7cba8c931fca95d041389cfb1902b7c89fe`; Phase-1 boundary commit
  `46c2f971e1a42cf49bd936bad94697b81bf31002`.
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

- To be established at P7-03/P7-05/P7-07: original Apache-2.0 NES fixtures
  authored for Phase 7, with recorded provenance, toolchain, ROM hashes,
  PRG/CHR configuration, bank configuration, vectors and mapper metadata. At
  P7-00 no Phase-7 public fixture or translation/control-flow capability is
  claimed.

## Queue freeze record (P7-00 boundary)

- Frozen contract: `.openrecomp-phase7/STAGE_QUEUE.md` `## Queue freeze`, rows
  `P7-01` .. `P7-99` exactly as listed, effective before any P7-01
  implementation work.
- No stage status changed at the freeze: `P7-01` .. `P7-99` stay `QUEUED`
  until their own gates pass.
- The freeze is a control-plane record only: no capability claim, no change to
  the frozen Phase-1/Phase-2/Phase-3/Phase-4/Phase-5/Phase-6 boundaries and no
  promotion of the Phase-7 terminal marker.

## Stage ledger

| ID | Stage | Status | Evidence |
| --- | --- | --- | --- |
| P7-00 | Phase-7 boundary | PASS | `.openrecomp-phase7/evidence/P7-00/` |
| P7-01 | TMNT frontier re-derivation | PASS | `.openrecomp-phase7/evidence/P7-01/` |
| P7-02 | Undocumented opcode 0x7C classification | PASS | `.openrecomp-phase7/evidence/P7-02/` |
| P7-03 | Public undocumented-opcode proof fixture | PASS | `.openrecomp-phase7/evidence/P7-03/` |
| P7-04 | Bank-aware cartridge reachability model | PASS | `.openrecomp-phase7/evidence/P7-04/` |
| P7-05 | Bank-aware ProgramModel / CFG integration | PASS | `.openrecomp-phase7/evidence/P7-05/` |
| P7-06 | Indirect jump evidence model | PASS | `.openrecomp-phase7/evidence/P7-06/` |
| P7-07 | Public indirect-control-flow proof fixture | PASS | `.openrecomp-phase7/evidence/P7-07/` |
| P7-08 | Translation frontier integration | PASS | `.openrecomp-phase7/evidence/P7-08/` |
| P7-09 | Native execution of public Phase-7 fixture | PASS | `.openrecomp-phase7/evidence/P7-09/` |
| P7-10 | Independent reference equivalence | PASS | `.openrecomp-phase7/evidence/P7-10/` |
| P7-11 | Private TMNT frontier run | QUEUED | - |
| P7-12 | Evidence-driven translation closure | QUEUED | - |
| P7-13 | Second private TMNT run | QUEUED | - |
| P7-14 | Reusable bank-aware ROM-to-native workflow | QUEUED | - |
| P7-90 | Whole regression | QUEUED | - |
| P7-91 | Evidence index and compatibility matrix | QUEUED | - |
| P7-99 | Final Phase-7 verdict | QUEUED | - |

## P7-00 acceptance criteria

1. The exact frozen Phase-6 terminal boundary is verified: commit
   `1643817d43196c43155805249137e4b4e4a21eb1`, tree
   `cda3f535be43dc6f3d4b457d11d356ae39ea34af`, terminal record
   `p6_99_tests.json` sha256
   `e7e462f15ca64a2d8db130ec664ac309d5ebfef1c128fd392111d19e4be30ea4`, and
   the recorded absence of a Phase-6 terminal tag is reconciled without
   fabricating a frozen artifact.
2. The Phase-6 final verdict gate independently re-passes twice in a
   reconstructed pre-verdict context with byte-identical stdout to the
   recorded official capture (3750 bytes raw, raw `d7e96e11...`, LF
   `4fafd384...`, exit 0, empty stderr, `tests=108`) and regenerates the
   committed `p6_99_tests.json` (`e7e462f1...`).
3. The Phase-7 control plane exists (STATE, HANDOFF, STAGE_QUEUE, SCOPE,
   CONTROL_POLICY, EVIDENCE_SCHEMA, FIXTURE_POLICY, evidence/) and is
   deterministic; the queue `P7-01` .. `P7-99` is frozen and no new
   translation/control-flow capability is claimed
   (`TRANSLATION_FRONTIER_STATUS=NOT_PROVEN`).
4. ROM safety: the private fixture exists at its recorded path with the
   recorded size/hash; no ROM image or ROM-derived binary copy is tracked or
   present anywhere under the repository; `.gitignore` excludes `*.nes`,
   `*.fds`, `*.unf`, `*.unif` and commercial ROM directories.
5. Public/private fixture separation is recorded in `FIXTURE_POLICY.md`.
6. The working tree has no unexpected new untracked paths beyond the
   documented Phase-2/Phase-3 residue and the Phase-7 control plane.
