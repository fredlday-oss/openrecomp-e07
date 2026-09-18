# OpenRecomp Phase 6 Handoff

STATUS: Phase 6 `ACTIVE` - stage P6-00 (Phase-6 boundary) passed and the
frozen queue `P6-01` .. `P6-99` is frozen. Phase 5 is COMPLETE and frozen at
annotated tag `openrecomp-phase5-pass` (object
`b5d6832ba2374b810f4c24500ed9093a9481fd8d`) =
`e8d3627a622d0ca3196b117c5112f29fabdb49e7`, tree
`468fb9788350de393d3de2ca9471b7d874ee8dc9`, with `OPENRECOMP_P5_99=PASS`,
`OPENRECOMP_PHASE5_FINAL_VERDICT_V1=PASS tests=87` and
`OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=PASS` (bounded audited claim only);
`OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` remains permanent.

Phase 6 objective (reserved `NOT_PROVEN` until P6-99): expand the proven
Phase-5 NROM static-recompilation path to a bounded, audited MMC1/mapper-1
platform path using an original Apache-2.0 public MMC1 fixture, with exact
independent MMC1 reference equivalence, and record the private TMNT image only
as a non-redistributed compatibility observation.

Reserved markers:

- `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN` (P6-99 may issue PASS for
  the bounded claim only)
- `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` (never promoted)

## Firm constraints carried into Phase 6

- Never mutate the frozen Phase-1/Phase-2/Phase-3/Phase-4/Phase-5 histories,
  tags, evidence, gates or verdicts. Phase-6 work is additive under
  `.openrecomp-phase6/` plus new `tools/test_phase6_*` gates.
- Never commit, copy, embed or package the private TMNT image bytes or any
  ROM-derived binary copy (`FIXTURE_POLICY.md`, `CONTROL_POLICY.md` rule 11).
- The public proof fixture is an original Apache-2.0 MMC1 NES program authored
  for Phase 6 with full recorded provenance.
- Fail closed on unsupported mappers, MMC1 variants/wiring and opcodes; never
  guess hardware behaviour.
- Never execute original guest CPU code directly on the host.
- One implementation frontier at a time; every official stage gate runs twice
  with byte-identical stdout and empty stderr.

## P6-00 outcome (PASS)

Markers: `OPENRECOMP_P6_00=PASS`,
`OPENRECOMP_PHASE6_BOUNDARY_V1=PASS tests=85`; terminal and general markers
reserved as `NOT_PROVEN`.

- Branch `phase6/nes-compat-v1` descends from the frozen Phase-5 boundary
  commit `e8d3627...`; tag object `b5d6832b...`, tree `468fb978...`.
- The Phase-5 final verdict gate independently re-passed twice in a
  reconstructed pre-verdict context with byte-identical stdout to the recorded
  official capture (2971 bytes raw `bc1f1e97...`, LF `2378b480...`,
  `tests=87`) and regenerated the committed `p5_99_tests.json`
  (`b0e8267c...`).
- Phase-6 control plane established and deterministic; queue `P6-01` ..
  `P6-99` frozen; `MMC1_PLATFORM_STATUS=NOT_PROVEN`; no MMC1 capability
  claimed.
- ROM safety verified: private fixture 262160 bytes / SHA-256 `2a9345e6...`
  present outside the worktree; no ROM image or private copy anywhere in the
  repository; `.gitignore` ROM rules effective; public/private separation
  recorded in `FIXTURE_POLICY.md`.
- Two official runs byte-identical raw (`9391a99a...`, 3201 bytes) and LF
  (`ca7ab210...`), empty stderr, exit 0; the regenerated
  `p6_00_tests.json` hash and full check list are recorded in the stage
  evidence.
- Evidence: `.openrecomp-phase6/evidence/P6-00/`.

## Exact next action

Proceed to P6-01 - MMC1 requirements and fixture inventory.
