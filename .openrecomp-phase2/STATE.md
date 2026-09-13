# OpenRecomp Phase 2 State

PHASE=2
BASELINE_TAG=openrecomp-phase1-pass
BASELINE_COMMIT=46c2f97
CURRENT_STAGE=P2-06
LAST_PASSED_STAGE=P2-05
STATUS=READY
FINAL_VERDICT=NOT_YET_EVALUATED

## Stage ledger

| ID | Stage | Status | Evidence |
| --- | --- | --- | --- |
| P2-00 | Baseline + control plane | `PASS` | `.openrecomp-phase2/evidence/P2-00/RESULT.md` |
| P2-01 | Shared program model V1 | `PASS` | `.openrecomp-phase2/evidence/P2-01/RESULT.md` |
| P2-02 | CFG construction V1 | `PASS` | `.openrecomp-phase2/evidence/P2-02/RESULT.md` |
| P2-03 | Function discovery V1 | `PASS` | `.openrecomp-phase2/evidence/P2-03/RESULT.md` |
| P2-04 | Call-graph recovery V1 | `PASS` | `.openrecomp-phase2/evidence/P2-04/RESULT.md` |
| P2-05 | Translation units V1 | `PASS` | `.openrecomp-phase2/evidence/P2-05/RESULT.md` |

## P2-05 result (PASS)

Stage: `OPENRECOMP_P2_05_TRANSLATION_UNITS_V1`.
Starting commit: `ea954d6306352fe63ed438cc43f107fe168471d4` (P2-04 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Module `openrecomp/translation_units.py`: `build_translation_units(discovery, *,
  call_graph=None)` / `build_translation_units_from(...)` -> `TranslationUnitSet`;
  `TranslationUnitSet` contains exactly one `TranslationUnit` (`unit_id = "tu_" +
  function.id`) per P2-03 `FunctionUnit`.
- Structural package only: canonical block order (entry first, then `(entry_address,
  id)`), verbatim instructions/successors, P2-04 call edges per caller, unresolved
  call/jump sites, external targets without invented callees, `entry_sources` +
  `EntryBasis` provenance, and residual `shared_blocks` / `suppressed_entries` /
  `unowned_blocks` / `unowned_control_flow` evidence.
- Deterministic canonical serialization/fingerprint; round-trip byte identity;
  arbitrary-precision addresses (64-bit and >64-bit fixtures).
- No IR lowering; no architecture-specific semantics; no invented targets; no discarded
  unowned evidence; fail closed with `TranslationUnitError`.
- `tools/test_translation_units_v1.py`: 104 deterministic checks.
- No P2-01/P2-02/P2-03/P2-04 source modified.

## Gates

```text
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
OPENRECOMP_CFG_V1=PASS tests=82
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
PASS source-integrity  verified 115 manifest entries
```

Determinism: two consecutive P2-05 gate runs produced byte-identical stdout
(`sha256 7209c6ff6bc40d131af0e04eae3c48d48d785ce864de46d0e406d81dbdbbc24a`).

## Stage-naming note

`STAGE_QUEUE.md` labels P2-05 "Indirect-control-flow classification" and lists the
translation-unit model under P2-06. This execution was explicitly directed as
`OPENRECOMP_P2_05_TRANSLATION_UNITS_V1`, so P2-05 was implemented as the translation-unit
packaging stage. `STAGE_QUEUE.md` was intentionally left unchanged; confirm the exact
P2-06 definition against the controlling stage prompt before starting it.

## Next exact action

Begin P2-06 only after confirming its definition against the controlling stage prompt.
Do not implement it as part of P2-05. Do not modify the frozen Phase-1 behavior or the
P2-01..P2-05 layers except through an evidence-backed stage.

## Carried-forward findings

- `update_sums.py` globs `schemas/*.json` while the directory is `schema/`, so
  `schema/*.json` (and `openrecomp/*.py`) remain outside the integrity manifest
  (pre-existing; deferred).
- `direct_callees` are provisional structural facts validated across P2-04/P2-05, not ABI
  recovery.
- Indirect calls/jumps remain unresolved evidence; no indirect target is recovered.
- Toolchain-gated gates remain unexecutable on this host.
- STAGE_QUEUE naming for P2-05/P2-06 lags the executed directive (see above).

## Git status (short)

- Modified: `SOURCE_SHA256SUMS.txt` (one additive entry; 115 total), `.openrecomp-phase2/STATE.md`,
  `.openrecomp-phase2/HANDOFF.md`.
- Added (untracked): `openrecomp/translation_units.py`, `tools/test_translation_units_v1.py`,
  `.openrecomp-phase2/evidence/P2-05/`.
- Untouched untracked residue: `.openrecomp-phase2/backups/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No commit created.

OPENRECOMP_P2_05=PASS
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104
CURRENT_STAGE=P2-06
