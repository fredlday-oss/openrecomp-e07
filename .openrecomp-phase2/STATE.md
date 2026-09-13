# OpenRecomp Phase 2 State

PHASE=2
BASELINE_TAG=openrecomp-phase1-pass
BASELINE_COMMIT=46c2f97
CURRENT_STAGE=P2-07
LAST_PASSED_STAGE=P2-06
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
| P2-06 | Indirect-control-flow classification V1 | `PASS` | `.openrecomp-phase2/evidence/P2-06/RESULT.md` |
| P2-07 | Host emitter V1 | `NEXT` | not started |

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

## P2-06 result (PASS)

Stage: `OPENRECOMP_P2_06_INDIRECT_CONTROL_FLOW_CLASSIFICATION_V1`.
Starting commit: `ce9cd4fc3aa87cbe9009c39abd52c5de083080e1` (P2-05 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Module `openrecomp/indirect_control_flow.py`: `classify_indirect_control_flow(units, *,
  evidence=())` / `classify_indirect_control_flow_from(...)` -> `IndirectControlFlowSet`.
- Categories: `RESOLVED`, `BOUNDED_CANDIDATES`, `EXTERNAL_OR_RUNTIME_MEDIATED`,
  `RETURN_LIKE`, `UNRESOLVED_INDIRECT_CALL`, `UNRESOLVED_INDIRECT_JUMP`,
  `UNSUPPORTED_OR_MALFORMED`. Proof bases: `EXACT_CONSTANT_TARGET`, `EXACT_TARGET_SET`,
  `ADAPTER_EVIDENCE`, `BOUNDED_CANDIDATE_EVIDENCE`, `EXTERNAL_RUNTIME_EVIDENCE`,
  `STRUCTURAL_RETURN_EVIDENCE`, `NONE`.
- Unknown remains unknown: no target is inferred from metadata, nearby code, opcode or
  reason strings; `RESOLVED` requires PROVEN evidence; bounded candidates are never
  promoted. Each classification preserves function/block/instruction/site provenance, the
  original `UnresolvedSite`, `provenance`, `targets`/`target_functions`, mechanism/detail
  and `evidence`.
- Deterministic canonical serialization/fingerprint; round-trip byte identity;
  arbitrary-precision addresses (64-bit and >64-bit). No IR lowering; no host emission;
  no architecture-specific semantics.
- `tools/test_indirect_control_flow_v1.py`: 134 deterministic checks.
- P2-05 `TranslationUnitSet` is read without mutation; unowned control flow is preserved
  as residual evidence (`IndirectControlFlowSet.unowned_control_flow`) and not classified.
- No P2-00..P2-05 implementation or evidence modified.

## Gates

```text
OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
OPENRECOMP_CFG_V1=PASS tests=82
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
PASS source-integrity  verified 116 manifest entries
```

Determinism: two consecutive P2-06 gate runs produced byte-identical stdout
(`sha256 866d290a59228e5bd01f5bc026d2a2b1ca5558e28e9165b2dea42e00464d72a2`).

## Queue reconciliation note

The completed sequence is `P2-00` baseline, `P2-01` persistent program representation,
`P2-02` basic-block/CFG recovery, `P2-03` function recovery, `P2-04` call-graph recovery,
`P2-05` translation-unit model. The queue originally numbered `P2-04 Direct CFG recovery`,
`P2-05 Indirect-control-flow classification`, `P2-06 Translation-unit model`; it has been
reconciled to the executed sequence.

The indirect-control-flow classification work was assigned to `P2-06` with the original
safety requirement — classify resolvable versus unresolved indirect sites **without
guessing targets** — and is now `PASS` (see the P2-06 result above). `P2-07` is Host
emitter V1 and is `NEXT`.

This reassignment is a control-plane reconciliation caused by actual execution order. It
does not change the semantics, claims, evidence or PASS status of any frozen prior stage
(`P2-00`..`P2-06`), and it does not alter commit `ce9cd4f` or any earlier commit.

## Next exact action

Begin P2-07 — Host emitter V1: deterministic generated host code for a bounded proven
subset, consuming the classified structural pipeline. P2-07 was **not** started in P2-06.
Do not lower/authorize unsupported semantics; fail closed on unresolved or unsupported
indirect sites. Do not modify the frozen Phase-1 behavior or the P2-00..P2-06 layers
except through an evidence-backed stage.

## Carried-forward findings

- `update_sums.py` globs `schemas/*.json` while the directory is `schema/`, so
  `schema/*.json` (and `openrecomp/*.py`) remain outside the integrity manifest
  (pre-existing; deferred).
- `direct_callees` are provisional structural facts validated across P2-04/P2-05, not ABI
  recovery.
- P2-06 classifies indirect sites but does not recover targets by analysis; unresolved
  sites remain `UNRESOLVED_INDIRECT_CALL` / `UNRESOLVED_INDIRECT_JUMP` and bounded candidate
  sets remain `BOUNDED_CANDIDATES`.
- Unowned control flow is preserved as P2-06 residual evidence and is not classified.
- Toolchain-gated gates remain unexecutable on this host.
- `STAGE_QUEUE.md` is reconciled to the executed sequence; `P2-06` is `COMPLETE` and
  `P2-07` is `NEXT`.

## Git status (short)

- P2-05 boundary commit: `ce9cd4f` (`phase2: complete P2-05 translation units`).
- Current uncommitted changes: P2-06 implementation + evidence and the control-plane
  updates to `.openrecomp-phase2/STAGE_QUEUE.md`, `.openrecomp-phase2/STATE.md`,
  `.openrecomp-phase2/HANDOFF.md`, plus `SOURCE_SHA256SUMS.txt` (+1 entry).
- Untouched untracked residue: `.openrecomp-phase2/backups/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No commit created (P2-06 boundary commit intentionally not created).

OPENRECOMP_P2_06=PASS
OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134
CURRENT_STAGE=P2-07
