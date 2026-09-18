# OpenRecomp Phase 5 Handoff

STATUS: Phase 5 `ACTIVE` - P5-00 (Phase-5 boundary) is being executed. Phase 4
is complete and frozen at annotated tag `openrecomp-phase4-pass` (object
`e7eaab18fee267b3d7962db13835c9e14dd77fc2`) =
`b3c71fb690f00b4811e8ec30c28f7725141295d0`, tree
`f2ca3080915aa68f403526b89dfc17454687aed6`, with
`OPENRECOMP_P4_99=PASS`,
`OPENRECOMP_PHASE4_FINAL_VERDICT_V1=PASS tests=79` and
`OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=PASS` (bounded audited claim only);
`OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN` and
`COREMARK_STATUS=NOT_PROVEN` remain permanent.

Phase 5 objective (reserved `NOT_PROVEN` until P5-99): prove the bounded NES /
2A03 static-recompilation path on a legally clean public iNES fixture through
the frozen Phase-4 generic runtime and platform-adapter contracts, with
independent reference equivalence, and record the private TMNT image only as a
non-redistributed compatibility observation.

Reserved markers:

- `OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN` (P5-99 may issue PASS for
  the bounded claim only)
- `OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` (never promoted)

## Firm constraints carried into Phase 5

- Never mutate the frozen Phase-1/Phase-2/Phase-3/Phase-4 histories, tags,
  evidence, gates or verdicts. Phase-5 work is additive under
  `.openrecomp-phase5/` plus new `tools/test_phase5_*` gates.
- Never commit, copy, embed or package the private TMNT image bytes or any
  ROM-derived binary copy (`FIXTURE_POLICY.md`, `CONTROL_POLICY.md` rule 10).
- The public proof fixture is an original Apache-2.0 NES program authored for
  Phase 5 with full recorded provenance.
- Fail closed on unsupported mappers/opcodes/hardware; never guess.
- Never execute original guest CPU code directly on the host.

## Exact next action

Execute P5-00: run `tools/test_phase5_boundary_v1.py` twice through the
Phase-5 stage runner, confirm the Phase-4 final verdict gate re-passes in the
reconstructed context byte-identically, capture evidence, update STATE/HANDOFF,
and commit the P5-00 boundary. Then proceed to P5-01 (NES/iNES ingestion and
inventory).

## P5-00 outcome (PASS)

Markers: `OPENRECOMP_P5_00=PASS`,
`OPENRECOMP_PHASE5_BOUNDARY_V1=PASS tests=80`; terminal and general markers
reserved as `NOT_PROVEN`.

- Branch `phase5/nes-platform-v1` descends from the frozen Phase-4 boundary
  commit `b3c71fb...`; tag object `e7eaab18...`, tree `f2ca3080...`.
- The Phase-4 final verdict gate independently re-passed twice in the
  reconstructed pre-verdict context with byte-identical stdout to the recorded
  official capture (2609 bytes raw `903308ca...`, LF `79c6f395...`,
  `tests=79`) and regenerated the committed `p4_99_tests.json`
  (`f13cf891...`).
- Phase-5 control plane established and deterministic; queue `P5-01` ..
  `P5-99` frozen; `NES_PLATFORM_STATUS=NOT_PROVEN`; no NES capability claimed.
- ROM safety verified: private fixture 262160 bytes / SHA-256 `2a9345e6...`
  present outside the worktree, no ROM image or private copy anywhere in the
  repository, `.gitignore` ROM rules effective; public/private separation
  recorded in `FIXTURE_POLICY.md`.
- Two official runs byte-identical raw (`825932c5...`, 3025 bytes) and LF
  (`79bdbf3c...`), empty stderr, exit 0; `p5_00_tests.json` identical
  (`e11a3cde...`).
- Evidence: `.openrecomp-phase5/evidence/P5-00/`.
