# OpenRecomp Phase 2 Handoff

STATUS: P2-04 `PASS`; P2-05 not started.

Frozen Phase-1 reference (verified):

- commit: `46c2f971e1a42cf49bd936bad94697b81bf31002`
- tag: `openrecomp-phase1-pass` (annotated object `8dbbd79ac3c7104bfa0374aecf2d9093be89c6c7`)
- verdict: `OPENRECOMP_PHASE1_MULTIARCH_PROOF=PASS`
- P2-00 boundary: `1b40269cc80cd19d49d8870f8e65aa1eced69885`
- P2-01 boundary: `a0c483029727168b1371aa9683e82900f9e14638`
- P2-02 boundary: `65386e45f9af1d581d0e14f8cca3940a6a82d75c`
- P2-03 boundary (P2-04 starting commit): `aa263bbedbd74a3dd0311fbf149a901cd50d7e44`
- branch: `phase2/opencode-v1`.

## P2-04 outcome

Stage: `OPENRECOMP_P2_04_CALL_GRAPH_RECOVERY_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-04/RESULT.md`.
Markers: `OPENRECOMP_P2_04=PASS`, `OPENRECOMP_CALL_GRAPH_V1=PASS tests=61`.

- Module `openrecomp/call_graph.py`: `build_call_graph(discovery)` /
  `build_call_graph_from(...)` -> `CallGraph`; one node per discovered `FunctionUnit`
  using the stable P2-03 id.
- `INTERNAL_DIRECT` (both discovered; evidence = call-site + callee), `EXTERNAL_DIRECT`
  (no discovered callee; inventory cross-checked), `UNRESOLVED_INDIRECT` (no target);
  indirect jumps excluded.
- Callers by exact P2-03 block ownership; callees by exact entry-address equality;
  function-interior/suppressed-entry targets fail closed; `FunctionUnit.direct_callees`
  reconciled against recovered internal callees.
- Recursion / mutual recursion (iterative Kosaraju) reported deterministically; per-site
  edge identity; canonical serialization/fingerprint.
- `tools/test_call_graph_v1.py`: 61 deterministic checks incl. >32-bit addresses,
  bounded NES6502 call graph, and all fail-closed rejections.
- No P2-01/P2-02/P2-03 source modified; frozen IR V1 / Module Image V1 untouched.

## Exact next action

Start P2-05: indirect-control-flow classification. Classify indirect call/jump sites
against evidence without guessing targets; separate provably-resolvable forms from
genuinely unresolved ones; keep PROVEN/CANDIDATE provenance; preserve the
`unresolved_call_sites` / `unresolved_jump_sites` separation. Do not implement
translation units (P2-06), the host emitter (P2-07) or IR lowering.

## Verification commands / results

```text
python tools/test_call_graph_v1.py
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61
(byte-identical across two runs; stdout sha256 ee4602245dfad5301385b958826dca112c0b600d7e418a37954d39172ea9b374)

python tools/test_functions_v1.py
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67

python tools/test_cfg_v1.py
OPENRECOMP_CFG_V1=PASS tests=82

python tools/test_program_model_v1.py
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49

python tools/phase1_host_gates_v1.py --json .openrecomp-phase2/evidence/P2-04/host_gates.json
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS

python tools/phase1_host_gates_v1.py --only source-integrity
PASS source-integrity  verified 114 manifest entries
```

## Evidence artifacts (UTF-8 text)

`.openrecomp-phase2/evidence/P2-04/`: `RESULT.md`, `call_graph_tests.json`,
`call_graph_tests.txt`, `host_gates.json`, `host_gates.txt`, `sample_call_graph.json`.

## Unresolved evidence / limitations

- Direct call graph only; indirect calls/jumps remain unresolved by design.
- `direct_callees` are provisional structural facts validated here, not ABI recovery.
- Cross-function tail/fallthrough transfers remain CFG edges, not call edges.
- `schema/*.json` / `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt`
  (pre-existing `update_sums.py` `schemas/` glob gap).
- Toolchain-gated gates `e07-hardened-end-to-end` and `external-repro-v1` require
  `clang`/`gcc`/POSIX and remain skipped; never counted as pass.

## Non-claims

No indirect-call resolution, jump-table recovery, complete whole-program recovery,
calling-convention/ABI recovery, translation units, IR lowering, AOT integration,
whole-game recompilation, console compatibility, generic runtime support or RT64
integration. The NES6502 validation is bounded and structural.

## Git status (short)

- Modified: `SOURCE_SHA256SUMS.txt` (114 entries), `.openrecomp-phase2/STATE.md`,
  `.openrecomp-phase2/HANDOFF.md`.
- Added (untracked): `openrecomp/call_graph.py`, `tools/test_call_graph_v1.py`,
  `.openrecomp-phase2/evidence/P2-04/`.
- Untouched untracked residue: `.openrecomp-phase2/backups/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No commit created.

Resume by reading `CONTROL_POLICY.md`, `SCOPE.md`, `STAGE_QUEUE.md`, `STATE.md`,
`HANDOFF.md`, and `EVIDENCE_SCHEMA.md`, then work only on `CURRENT_STAGE`.

OPENRECOMP_P2_04=PASS
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61
CURRENT_STAGE=P2-05
