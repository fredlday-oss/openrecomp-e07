# OpenRecomp Phase 2 Handoff

STATUS: P2-03 `PASS`; P2-04 not started.

Frozen Phase-1 reference (verified):

- commit: `46c2f971e1a42cf49bd936bad94697b81bf31002`
- tag: `openrecomp-phase1-pass` (annotated object `8dbbd79ac3c7104bfa0374aecf2d9093be89c6c7`)
- verdict: `OPENRECOMP_PHASE1_MULTIARCH_PROOF=PASS`
- P2-00 boundary: `1b40269cc80cd19d49d8870f8e65aa1eced69885`
- P2-01 boundary: `a0c483029727168b1371aa9683e82900f9e14638`
- P2-02 boundary (P2-03 starting commit): `65386e45f9af1d581d0e14f8cca3940a6a82d75c`
- branch: `phase2/opencode-v1`.

## P2-03 outcome

Stage: `OPENRECOMP_P2_03_FUNCTION_DISCOVERY_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-03/RESULT.md`.
Markers: `OPENRECOMP_P2_03=PASS`, `OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67`.

- Module `openrecomp/functions.py`: `discover_functions` / `FunctionDiscoveryResult` /
  `FunctionDiscoveryError` / `FunctionEntry` / `FunctionEntrySource` / `EntryBasis` /
  `SuppressedEntry` / `SharedBlock` / `ExternalDirectCallTarget`.
- Entry sources: `PROGRAM_ENTRY`, `DIRECT_CALL`, `EXPLICIT_PROVEN`,
  `EXPLICIT_CANDIDATE`; multiple bases per address preserved.
- Ownership priority PROVEN-then-CANDIDATE, lower address first; candidate-inside-proven
  suppressed with explicit reason; contradictory PROVEN ownership fails closed;
  shared non-entry blocks single-owner + recorded; unowned disconnected blocks recorded.
- Caller/callee isolation: caller owns `CALL_RETURN` continuation only; callee never
  absorbed; external direct-call targets inventoried; unresolved indirect calls/jumps
  never traversed or promoted.
- Evidence conservative (`combine_evidence` over entry + owned blocks + internal edges);
  CANDIDATE never promoted; survives serialization.
- P2-01 correction: optional `FunctionUnit.entry_sources`; `canonical_blocks()`
  entry-first deterministic serialization; schema gains optional `entry_sources`.
- `tools/test_functions_v1.py`: 67 deterministic checks, including entry block above a
  lower reachable block, >32-bit addresses, bounded NES6502 CFG, and all fail-closed
  rejections.
- Frozen IR V1 / Module Image V1 / Phase-1 semantics unchanged; P2-02 CFG unchanged.

## Exact next action

Start P2-04: whole-program direct-call-graph construction and validation over the
discovered functions. Consolidate `ControlFlowGraph.direct_call_sites` (and the
discovered functions' provisional `direct_callees`) into a validated inter-function
direct call graph; keep unresolved indirect calls separate per `AGENTS.md`; validate
graph consistency using neutral evidence rules. Do not implement translation units
(P2-06), the host emitter (P2-07) or IR lowering.

## Verification commands / results

```text
python tools/test_functions_v1.py
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
(byte-identical across two runs; stdout sha256 05218d8d1db991e2ff93679340490d59dcea24add7c3c8d2faee0bf26cbe39a8)

python tools/test_cfg_v1.py
OPENRECOMP_CFG_V1=PASS tests=82

python tools/test_program_model_v1.py
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49

python tools/phase1_host_gates_v1.py --json .openrecomp-phase2/evidence/P2-03/host_gates.json
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS

python tools/phase1_host_gates_v1.py --only source-integrity
PASS source-integrity  verified 113 manifest entries
```

## Evidence artifacts (UTF-8 text)

`.openrecomp-phase2/evidence/P2-03/`: `RESULT.md`, `function_tests.json`,
`function_tests.txt`, `host_gates.json`, `host_gates.txt`,
`sample_functions.program.json`, `sample_functions.discovery.json`.

## Unresolved evidence / limitations

- Function discovery is evidence-entry driven; no prologue/alignment/symbol/ABI
  heuristics.
- `direct_callees` are provisional; final whole-program call graph is P2-04.
- Shared non-entry blocks have a single deterministic owner (P2-01 ownership is unique).
- External direct-call targets inventoried, not discovered.
- `schema/*.json` / `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt`
  (pre-existing `update_sums.py` `schemas/` glob gap).
- Toolchain-gated gates `e07-hardened-end-to-end` and `external-repro-v1` require
  `clang`/`gcc`/POSIX and remain skipped; never counted as pass.

## Non-claims

No complete/heuristic function recovery, indirect-call resolution, final whole-program
call graph, jump-table recovery, calling-convention/ABI recovery, translation units,
IR lowering, AOT integration, whole-game recompilation, console compatibility, generic
runtime support or RT64 integration. The NES6502 validation is bounded and structural.

## Git status (short)

- Modified: `openrecomp/program_model.py`, `schema/openrecomp-program-v1.schema.json`,
  `SOURCE_SHA256SUMS.txt` (113 entries), `.openrecomp-phase2/STATE.md`,
  `.openrecomp-phase2/HANDOFF.md`.
- Added (untracked): `openrecomp/functions.py`, `tools/test_functions_v1.py`,
  `.openrecomp-phase2/evidence/P2-03/`.
- Untouched untracked residue: `.openrecomp-phase2/backups/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No commit created.

Resume by reading `CONTROL_POLICY.md`, `SCOPE.md`, `STAGE_QUEUE.md`, `STATE.md`,
`HANDOFF.md`, and `EVIDENCE_SCHEMA.md`, then work only on `CURRENT_STAGE`.

OPENRECOMP_P2_03=PASS
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
CURRENT_STAGE=P2-04
