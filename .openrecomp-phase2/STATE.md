# OpenRecomp Phase 2 State

PHASE=2
BASELINE_TAG=openrecomp-phase1-pass
BASELINE_COMMIT=46c2f97
CURRENT_STAGE=P2-08
LAST_PASSED_STAGE=P2-07
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
| P2-07 | Host emitter V1 | `PASS` | `.openrecomp-phase2/evidence/P2-07/RESULT.md` |
| P2-08 | Generic runtime ABI V1 | `NEXT` | not started |

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

## P2-07 result (PASS)

Stage: `OPENRECOMP_P2_07_HOST_EMITTER_V1`.
Starting commit: `f9f2662b90c165a967fa943070e79688ff8198b1` (P2-06 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Module `openrecomp/host_emitter.py`: `emit_host_translation(translation_units,
  classification, *, config)` / `emit_host_translation_from(...)` -> `HostTranslationSet`,
  generating deterministic portable C (C99; only `<stdint.h>`/`<stddef.h>`).
- Emits only explicitly proven semantics: a `HostInstructionSemantics` rule must exist for
  the exact `(architecture, op)` pair; the bounded vocabulary is const/copy/add/sub/mul/
  and/or/xor/shl/lshr/ashr/signed+unsigned compare with explicit 8/16/32/64-bit masking.
- Direct fallthrough, conditional branch, jump, internal call, return and P2-06
  `RETURN_LIKE` are emitted; `RESOLVED` single targets are direct and finite sets use a
  `switch` with a fail-closed default.
- Fail closed: unsupported op, external direct call, unresolved/bounded/external
  indirect sites, unsupported/malformed classification, non-local edges, traps,
  un-normalized shifts and malformed input. `BOUNDED_CANDIDATES` are never promoted and no
  indirect target is guessed. Policy `BOUNDARY` (default) or `REJECT`.
- Deterministic identifiers/ordering/declarations/helpers; no absolute path, timestamp or
  Python identity; no IR lowering; no runtime ABI (P2-08); no guest execution.
- `tools/test_host_emitter_v1.py`: 106 deterministic checks (incl. an optional native
  compile+run of a synthetic 8-bit fixture: observed `44 0` == expected).
- No P2-00..P2-06 implementation or evidence modified.

## Gates

```text
OPENRECOMP_HOST_EMITTER_V1=PASS tests=106
OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
OPENRECOMP_CFG_V1=PASS tests=82
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
PASS source-integrity  verified 117 manifest entries
```

Determinism: two consecutive P2-07 gate runs produced byte-identical stdout
(`sha256 fb6e6e2c6ba660a5c3df75602a59c0501bf86ca53e0371e4942c0c76108c45d5`).

## Queue reconciliation note

The completed sequence is `P2-00` baseline, `P2-01` persistent program representation,
`P2-02` basic-block/CFG recovery, `P2-03` function recovery, `P2-04` call-graph recovery,
`P2-05` translation-unit model. The queue originally numbered `P2-04 Direct CFG recovery`,
`P2-05 Indirect-control-flow classification`, `P2-06 Translation-unit model`; it has been
reconciled to the executed sequence.

The indirect-control-flow classification work was assigned to `P2-06` with the original
safety requirement — classify resolvable versus unresolved indirect sites **without
guessing targets** — and is `PASS`. `P2-07` (Host emitter V1) is `PASS` and `P2-08`
(Generic runtime ABI V1) is `NEXT`.

This reassignment is a control-plane reconciliation caused by actual execution order. It
does not change the semantics, claims, evidence or PASS status of any frozen prior stage
(`P2-00`..`P2-07`), and it does not alter `ce9cd4f`, `f9f2662` or any earlier commit.

## Next exact action

Begin P2-08 — Generic runtime ABI V1: architecture-neutral CPU/memory/host-call/input/
frame/audio/runtime contracts. P2-08 was **not** started in P2-07. Keep architecture-
neutral contracts separate from platform implementations; do not claim the final Phase-2
marker. Do not modify the frozen Phase-1 behavior or the P2-00..P2-07 layers except
through an evidence-backed stage.

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
- P2-07 emits only rule-proven semantics; loads/stores/host calls, calling conventions and
  runtime services await P2-08. Emitted functions are void with no argument/return ABI.
- The P2-07 native compile+run is a bounded synthetic check, not an equivalence proof.
- Toolchain-gated gates remain unexecutable on this host.
- `STAGE_QUEUE.md` is reconciled to the executed sequence; `P2-07` is `COMPLETE` and
  `P2-08` is `NEXT`.

## Git status (short)

- P2-06 boundary commit: `f9f2662` (`phase2: complete P2-06 indirect control flow
  classification`); `HEAD` at P2-07 start.
- Current uncommitted changes: P2-07 implementation + evidence and the control-plane
  updates to `.openrecomp-phase2/STAGE_QUEUE.md`, `.openrecomp-phase2/STATE.md`,
  `.openrecomp-phase2/HANDOFF.md`, plus `SOURCE_SHA256SUMS.txt` (+1 entry).
- Untouched untracked residue: `.openrecomp-phase2/backups/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No commit created (P2-07 boundary commit intentionally not created).

OPENRECOMP_P2_07=PASS
OPENRECOMP_HOST_EMITTER_V1=PASS tests=106
CURRENT_STAGE=P2-08
