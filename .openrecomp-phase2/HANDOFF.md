# OpenRecomp Phase 2 Handoff

STATUS: P2-01 `PASS`; P2-02 not started.

Frozen Phase-1 reference (verified):

- commit: `46c2f971e1a42cf49bd936bad94697b81bf31002`
- tag: `openrecomp-phase1-pass` (annotated object `8dbbd79ac3c7104bfa0374aecf2d9093be89c6c7`)
- verdict: `OPENRECOMP_PHASE1_MULTIARCH_PROOF=PASS`
- P2-00 boundary commit: `1b40269cc80cd19d49d8870f8e65aa1eced69885`
- branch: `phase2/opencode-v1`.

## P2-01 outcome

Evidence: `.openrecomp-phase2/evidence/P2-01/RESULT.md`.
Markers: `OPENRECOMP_P2_01=PASS`, `OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49`.

- `openrecomp/program_model.py`: neutral
  `DecodedInstruction -> BasicBlock -> FunctionUnit -> ProgramModel` with
  `EvidenceClass` (PROVEN/CANDIDATE), direct vs unresolved control flow,
  arbitrary-precision addresses, optional instruction extent, graph validation and
  canonical serialization (`program_model_version = 1.0.0`).
- `schema/openrecomp-program-v1.schema.json` + `tools/validate_program_model_v1.py`:
  wire schema and fail-closed schema+graph validator.
- `tools/test_program_model_v1.py`: 49 deterministic checks, including real NES 6502
  variable-length decoding and a 64-bit synthetic model.
- Frozen IR V1 / Module Image V1 / Phase-1 semantics unchanged.
- Full Phase-1 host suite: `44 PASS / 0 FAIL / 2 SKIPPED`
  (`OPENRECOMP_PHASE1_HOST_GATES_V1=PASS`).

## Exact next action

Start P2-02: deterministic basic-block recovery on top of `openrecomp/program_model.py`.
Discover blocks from a decoded instruction stream using explicit direct-control-flow
leaders; malformed/ambiguous cases must fail closed (raise, never guess). Validate
results through `ProgramModel`. Do not implement function recovery (P2-03) or CFG
recovery (P2-04).

## Verification commands / results

```text
python tools/test_program_model_v1.py
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49

python tools/validate_program_model_v1.py <program.json>
OPENRECOMP_PROGRAM_MODEL_V1_VALID=PASS

python tools/phase1_host_gates_v1.py --json .openrecomp-phase2/evidence/P2-01/host_gates.json
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS

python tools/phase1_host_gates_v1.py --only source-integrity
PASS source-integrity  verified 111 manifest entries
```

## Unresolved evidence / limitations

- P2-01 is structural only: no instruction/block recovery, no IR lowering.
- `schema/*.json` remains outside `SOURCE_SHA256SUMS.txt` (pre-existing `schemas/`
  glob gap in `update_sums.py`).
- Toolchain-gated gates `e07-hardened-end-to-end` and `external-repro-v1` require
  `clang`/`gcc`/POSIX and remain skipped; never counted as pass.
- No Phase-2 gate aggregator yet; stage gates are standalone deterministic tests.

## Git status (short)

- Modified: `SOURCE_SHA256SUMS.txt` (two additive entries; 111 total).
- Added (untracked): `openrecomp/program_model.py`,
  `schema/openrecomp-program-v1.schema.json`,
  `tools/validate_program_model_v1.py`, `tools/test_program_model_v1.py`,
  `.openrecomp-phase2/evidence/P2-01/`.
- Untouched untracked residue: `.openrecomp-phase2/backups/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No commit created.

Resume by reading `CONTROL_POLICY.md`, `SCOPE.md`, `STAGE_QUEUE.md`, `STATE.md`,
`HANDOFF.md`, and `EVIDENCE_SCHEMA.md`, then work only on `CURRENT_STAGE`.
