# OpenRecomp Phase 2 Handoff

STATUS: P2-05 `PASS`; P2-06 not started.

Frozen Phase-1 reference (verified):

- commit: `46c2f971e1a42cf49bd936bad94697b81bf31002`
- tag: `openrecomp-phase1-pass` (annotated object `8dbbd79ac3c7104bfa0374aecf2d9093be89c6c7`)
- verdict: `OPENRECOMP_PHASE1_MULTIARCH_PROOF=PASS`
- P2-00 boundary: `1b40269cc80cd19d49d8870f8e65aa1eced69885`
- P2-01 boundary: `a0c483029727168b1371aa9683e82900f9e14638`
- P2-02 boundary: `65386e45f9af1d581d0e14f8cca3940a6a82d75c`
- P2-03 boundary: `aa263bbedbd74a3dd0311fbf149a901cd50d7e44`
- P2-04 boundary (P2-05 starting commit): `ea954d6306352fe63ed438cc43f107fe168471d4`
- branch: `phase2/opencode-v1`.

## P2-05 outcome

Stage: `OPENRECOMP_P2_05_TRANSLATION_UNITS_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-05/RESULT.md`.
Markers: `OPENRECOMP_P2_05=PASS`, `OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104`.

- Module `openrecomp/translation_units.py`: `build_translation_units` /
  `build_translation_units_from` -> `TranslationUnitSet`; exactly one `TranslationUnit`
  (`tu_<function.id>`) per P2-03 `FunctionUnit`.
- Structural packaging only: canonical block order, verbatim instructions/successors,
  P2-04 call edges per caller, unresolved call/jump sites, external targets with no
  invented callee, `entry_sources` + `EntryBasis` provenance, residual shared/suppressed/
  unowned evidence. Deterministic canonical serialization/fingerprint; round-trip byte
  identity; arbitrary-precision addresses. No IR lowering; fail closed with
  `TranslationUnitError`.
- `tools/test_translation_units_v1.py`: 104 deterministic checks.
- No P2-01/P2-02/P2-03/P2-04 source modified; frozen IR V1 / Module Image V1 untouched.

## Exact next action

Begin P2-06 only after confirming its definition against the controlling stage prompt.
`STAGE_QUEUE.md` labels P2-05 "Indirect-control-flow classification" and lists the
translation-unit model under P2-06; this execution was directed as
`OPENRECOMP_P2_05_TRANSLATION_UNITS_V1`, so P2-05 was implemented as translation units
and the queue label lags. Do not modify frozen Phase-1 behavior or the P2-01..P2-05
layers except through an evidence-backed stage.

## Verification commands / results

```text
python tools/test_translation_units_v1.py
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104
(byte-identical across two runs; stdout sha256 7209c6ff6bc40d131af0e04eae3c48d48d785ce864de46d0e406d81dbdbbc24a)

python tools/test_call_graph_v1.py
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61

python tools/test_functions_v1.py
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67

python tools/test_cfg_v1.py
OPENRECOMP_CFG_V1=PASS tests=82

python tools/test_program_model_v1.py
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49

python tools/phase1_host_gates_v1.py --json .openrecomp-phase2/evidence/P2-05/host_gates.json
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS

python tools/phase1_host_gates_v1.py --only source-integrity
PASS source-integrity  verified 115 manifest entries
```

## Evidence artifacts (UTF-8 text, no BOM)

`.openrecomp-phase2/evidence/P2-05/`: `RESULT.md`, `RESULT.json`, `determinism.txt`,
`changed_files.txt`, `translation_units_tests.json`, `translation_units_tests.txt`,
`host_gates.json`, `host_gates.txt`, `p2_04_call_graph.txt`, `p2_03_functions.txt`,
`p2_02_cfg.txt`, `p2_01_program_model.txt`.

## Unresolved evidence / limitations

- A translation unit is a structural package, not a lowered/emitted artifact.
- `direct_callees` are provisional structural facts validated across P2-04/P2-05, not ABI
  recovery.
- Indirect targets are never recovered; unresolved call/jump evidence is preserved.
- `schema/*.json` / `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt`
  (pre-existing `update_sums.py` `schemas/` glob gap).
- Toolchain-gated gates `e07-hardened-end-to-end` and `external-repro-v1` require
  `clang`/`gcc`/POSIX and remain skipped; never counted as pass.

## Non-claims

No IR lowering, host emission, AOT integration, indirect-call/jump-table resolution,
calling-convention/ABI recovery, whole-program recovery, whole-game recompilation,
console compatibility, generic runtime support or RT64 integration. The NES6502
validation is bounded and structural.

## Git status (short)

- Modified: `SOURCE_SHA256SUMS.txt` (115 entries), `.openrecomp-phase2/STATE.md`,
  `.openrecomp-phase2/HANDOFF.md`.
- Added (untracked): `openrecomp/translation_units.py`, `tools/test_translation_units_v1.py`,
  `.openrecomp-phase2/evidence/P2-05/`.
- Untouched untracked residue: `.openrecomp-phase2/backups/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No commit created.

Resume by reading `CONTROL_POLICY.md`, `SCOPE.md`, `STAGE_QUEUE.md`, `STATE.md`,
`HANDOFF.md`, and `EVIDENCE_SCHEMA.md`, then work only on `CURRENT_STAGE`.

OPENRECOMP_P2_05=PASS
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104
CURRENT_STAGE=P2-06
