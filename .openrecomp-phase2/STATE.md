# OpenRecomp Phase 2 State

PHASE=2
BASELINE_TAG=openrecomp-phase1-pass
BASELINE_COMMIT=46c2f97
CURRENT_STAGE=P2-02
LAST_PASSED_STAGE=P2-01
STATUS=READY
FINAL_VERDICT=NOT_YET_EVALUATED

## Stage ledger

| ID | Stage | Status | Evidence |
| --- | --- | --- | --- |
| P2-00 | Baseline + control plane | `PASS` | `.openrecomp-phase2/evidence/P2-00/RESULT.md` |
| P2-01 | Shared program model V1 | `PASS` | `.openrecomp-phase2/evidence/P2-01/RESULT.md` |

## P2-01 result (PASS)

- Added `openrecomp/program_model.py`: the architecture-neutral
  `DecodedInstruction -> BasicBlock -> FunctionUnit -> ProgramModel` structure with
  `EvidenceClass` (PROVEN/CANDIDATE), direct-vs-unresolved control flow, arbitrary-
  precision addresses, optional per-instruction width, graph validation and
  canonical deterministic serialization (`program_model_version = 1.0.0`).
- Added `schema/openrecomp-program-v1.schema.json`,
  `tools/validate_program_model_v1.py` (schema + graph validator) and
  `tools/test_program_model_v1.py` (`OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49`).
- Evidence: 64-bit synthetic model and real NES 6502 (variable-length) model both
  build/validate/serialize; 14 graph-consistency rejections + 5 constructor
  rejections + undocumented-opcode fail-closed; PROVEN survives serialization;
  two runs byte-identical.
- `SOURCE_SHA256SUMS.txt` gained the two new tool entries (109 -> 111). No Phase-1
  file changed; frozen IR V1 / Module Image V1 untouched.
- Full Phase-1 host suite: `44 PASS / 0 FAIL / 2 SKIPPED`
  (`OPENRECOMP_PHASE1_HOST_GATES_V1=PASS`).

## Next exact action

Begin P2-02 — deterministic basic-block recovery over the shared model: discover
blocks from decoded instruction streams with explicit direct-control-flow leaders,
record malformed/ambiguous cases as fail-closed rejections (never guessed), and
validate the result through `openrecomp/program_model.py`. Do not implement
function recovery (P2-03) or CFG recovery (P2-04) yet.

## Carried-forward findings

- `update_sums.py` globs `schemas/*.json` while the directory is `schema/`, so
  `schema/*.json` (including the new program schema) is still outside the integrity
  manifest (pre-existing; deferred).
- Toolchain-gated gates remain unexecutable on this host.
- No Phase-2 gate harness yet aggregates stage markers; P2-01's gate is the
  standalone deterministic test.
- Future integration point: accept later PS2/R5900 evidence through the
  adapter/frontend descriptor seam without duplicating or anticipating the other
  PC's unmerged work. The model is parameterized by source/adapter metadata rather
  than 32-bit-only or MIPS-classic assumptions.

## Git status (short)

- Modified: `SOURCE_SHA256SUMS.txt` (two additive tool entries).
- Added (untracked): `openrecomp/program_model.py`,
  `schema/openrecomp-program-v1.schema.json`,
  `tools/validate_program_model_v1.py`, `tools/test_program_model_v1.py`,
  `.openrecomp-phase2/evidence/P2-01/`.
- Untouched untracked residue: `.openrecomp-phase2/backups/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No commit created.
