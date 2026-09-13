# OpenRecomp Phase 2 Handoff

STATUS: P2-06 `PASS`; P2-07 (Host emitter V1) is `NEXT` and not started.

Frozen Phase-1 reference (verified):

- commit: `46c2f971e1a42cf49bd936bad94697b81bf31002`
- tag: `openrecomp-phase1-pass` (annotated object `8dbbd79ac3c7104bfa0374aecf2d9093be89c6c7`)
- verdict: `OPENRECOMP_PHASE1_MULTIARCH_PROOF=PASS`
- P2-00 boundary: `1b40269cc80cd19d49d8870f8e65aa1eced69885`
- P2-01 boundary: `a0c483029727168b1371aa9683e82900f9e14638`
- P2-02 boundary: `65386e45f9af1d581d0e14f8cca3940a6a82d75c`
- P2-03 boundary: `aa263bbedbd74a3dd0311fbf149a901cd50d7e44`
- P2-04 boundary (P2-05 starting commit): `ea954d6306352fe63ed438cc43f107fe168471d4`
- P2-05 boundary (P2-06 starting commit): `ce9cd4fc3aa87cbe9009c39abd52c5de083080e1`
- branch: `phase2/opencode-v1`.

## P2-06 outcome

Stage: `OPENRECOMP_P2_06_INDIRECT_CONTROL_FLOW_CLASSIFICATION_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-06/RESULT.md`.
Markers: `OPENRECOMP_P2_06=PASS`, `OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134`.

- Module `openrecomp/indirect_control_flow.py`: `classify_indirect_control_flow` /
  `classify_indirect_control_flow_from` -> `IndirectControlFlowSet`.
- Categories: `RESOLVED`, `BOUNDED_CANDIDATES`, `EXTERNAL_OR_RUNTIME_MEDIATED`,
  `RETURN_LIKE`, `UNRESOLVED_INDIRECT_CALL`, `UNRESOLVED_INDIRECT_JUMP`,
  `UNSUPPORTED_OR_MALFORMED`. Proof bases: `EXACT_CONSTANT_TARGET`, `EXACT_TARGET_SET`,
  `ADAPTER_EVIDENCE`, `BOUNDED_CANDIDATE_EVIDENCE`, `EXTERNAL_RUNTIME_EVIDENCE`,
  `STRUCTURAL_RETURN_EVIDENCE`, `NONE`.
- Unknown remains unknown: no target is invented from metadata, nearby code, opcode or
  reason strings; `RESOLVED` requires PROVEN evidence; bounded candidates are never
  promoted; unresolved sites stay explicit. Each classification preserves function/block/
  instruction/site provenance, the original `UnresolvedSite`, `provenance`, targets and
  evidence.
- Deterministic canonical serialization/fingerprint; round-trip byte identity;
  arbitrary-precision addresses (64-bit and >64-bit). No IR lowering; no host emission;
  no architecture-specific semantics.
- P2-05 `TranslationUnitSet` is read without mutation; unowned control flow is preserved
  as residual evidence and not classified.
- `tools/test_indirect_control_flow_v1.py`: 134 deterministic checks.
- No P2-00..P2-05 implementation or evidence modified; frozen IR V1 / Module Image V1
  untouched.

## Queue reconciliation

The queue is reconciled to the executed sequence: `P2-04` = call-graph recovery
(COMPLETE), `P2-05` = translation-unit model (COMPLETE), `P2-06` =
indirect-control-flow classification (COMPLETE), `P2-07` = Host emitter V1 (NEXT). The
original queue numbered `P2-04` Direct CFG recovery / `P2-05` Indirect-control-flow
classification / `P2-06` Translation-unit model; the reassignment is a control-plane
reconciliation caused by actual execution order and does not change the semantics, claims
or evidence of any frozen prior stage (`P2-00`..`P2-06`). It does not alter commit
`ce9cd4f` or any earlier commit.

## Exact next action

Begin P2-07 — Host emitter V1: deterministic generated host code for a bounded proven
subset, consuming the classified structural pipeline. Fail closed on unresolved or
unsupported indirect sites; do not authorise unsupported semantics. P2-07 was **not**
started in P2-06. Do not modify frozen Phase-1 behavior or the P2-00..P2-06 layers
except through an evidence-backed stage.

## Verification commands / results

```text
python tools/test_indirect_control_flow_v1.py
OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134
(byte-identical across two runs; stdout sha256 866d290a59228e5bd01f5bc026d2a2b1ca5558e28e9165b2dea42e00464d72a2)

python tools/test_translation_units_v1.py
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104

python tools/test_call_graph_v1.py
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61

python tools/test_functions_v1.py
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67

python tools/test_cfg_v1.py
OPENRECOMP_CFG_V1=PASS tests=82

python tools/test_program_model_v1.py
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49

python tools/phase1_host_gates_v1.py --json .openrecomp-phase2/evidence/P2-06/host_gates.json
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS

python tools/phase1_host_gates_v1.py --only source-integrity
PASS source-integrity  verified 116 manifest entries
```

## Evidence artifacts (UTF-8 text, no BOM)

`.openrecomp-phase2/evidence/P2-06/`: `RESULT.md`, `RESULT.json`, `determinism.txt`,
`changed_files.txt`, `indirect_control_flow_tests.json`, `indirect_control_flow_tests.txt`,
`host_gates.json`, `host_gates.txt`, `source_integrity.txt`, `p2_05_translation_units.txt`,
`p2_04_call_graph.txt`, `p2_03_functions.txt`, `p2_02_cfg.txt`, `p2_01_program_model.txt`.

## Unresolved evidence / limitations

- P2-06 classifies sites but does not recover targets by analysis; classifications are
  driven by explicit `IndirectControlFlowEvidence` proof claims.
- Bounded candidate sets stay `BOUNDED_CANDIDATES`; they are never resolved.
- Unowned control flow is preserved as residual evidence but is not classified, because
  its call/jump kind is not structurally attributable.
- `schema/*.json` / `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt`
  (pre-existing `update_sums.py` `schemas/` glob gap).
- Toolchain-gated gates `e07-hardened-end-to-end` and `external-repro-v1` require
  `clang`/`gcc`/POSIX and remain skipped; never counted as pass.

## Non-claims

No automatic indirect-call/jump-table resolution, constant propagation, symbolic
execution, pointer scanning, ABI recovery, IR lowering, host emission, AOT integration,
whole-game recompilation, console compatibility, generic runtime support or RT64
integration. The NES6502 validation is bounded and structural.

## Git status (short)

- P2-05 boundary commit: `ce9cd4f` (`phase2: complete P2-05 translation units`); `HEAD` at
  P2-06 start.
- Current uncommitted changes: P2-06 implementation + evidence plus control-plane updates
  to `.openrecomp-phase2/STAGE_QUEUE.md`, `.openrecomp-phase2/STATE.md`,
  `.openrecomp-phase2/HANDOFF.md`, plus `SOURCE_SHA256SUMS.txt` (+1 entry).
- Untouched untracked residue: `.openrecomp-phase2/backups/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No P2-06 boundary commit created (left for independent review).

Resume by reading `CONTROL_POLICY.md`, `SCOPE.md`, `STAGE_QUEUE.md`, `STATE.md`,
`HANDOFF.md`, and `EVIDENCE_SCHEMA.md`, then work only on `CURRENT_STAGE`.

OPENRECOMP_P2_06=PASS
OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134
CURRENT_STAGE=P2-07
