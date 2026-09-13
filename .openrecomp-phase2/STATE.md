# OpenRecomp Phase 2 State

PHASE=2
BASELINE_TAG=openrecomp-phase1-pass
BASELINE_COMMIT=46c2f97
CURRENT_STAGE=P2-05
LAST_PASSED_STAGE=P2-04
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

## P2-04 result (PASS)

Stage: `OPENRECOMP_P2_04_CALL_GRAPH_RECOVERY_V1`.
Starting commit: `aa263bbedbd74a3dd0311fbf149a901cd50d7e44` (P2-03 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Module `openrecomp/call_graph.py`: `build_call_graph(discovery)` /
  `build_call_graph_from(cfg, functions, *, entry_function_id, external_direct_call_targets)`
  -> `CallGraph`; one node per discovered `FunctionUnit` (stable P2-03 id).
- Edge classes: `INTERNAL_DIRECT` (caller + callee both discovered; edge evidence =
  call-site + callee evidence), `EXTERNAL_DIRECT` (direct target with no discovered
  function; inventory cross-checked with P2-03), `UNRESOLVED_INDIRECT` (no target/callee).
  Indirect jumps are excluded from the call graph.
- Callers assigned by exact P2-03 block ownership; callees resolved by exact
  `FunctionUnit.entry_address` equality; interior/boundary-but-not-entry targets fail
  closed; `FunctionUnit.direct_callees` reconciled against recovered internal callees.
- Recursion (`recursive_functions`), mutual recursion (`mutual_recursion_components` via
  iterative Kosaraju), per-callsite edge identity, conservative evidence, and
  deterministic canonical serialization/fingerprint.
- `tools/test_call_graph_v1.py`: 61 deterministic checks including >32-bit addresses,
  bounded NES6502 call graph, and all fail-closed rejections.
- No P2-01/P2-02/P2-03 source modified.

## Gates

```text
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
OPENRECOMP_CFG_V1=PASS tests=82
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
PASS source-integrity  verified 114 manifest entries
```

Determinism: two consecutive call-graph runs produced byte-identical stdout
(`sha256 ee4602245dfad5301385b958826dca112c0b600d7e418a37954d39172ea9b374`).

## Next exact action

Begin P2-05 — indirect-control-flow classification: classify indirect call/jump sites
against evidence without guessing targets, distinguish provably-resolvable forms from
genuinely unresolved ones, keep PROVEN/CANDIDATE provenance, and preserve the
`unresolved_call_sites` / `unresolved_jump_sites` separation. Do not implement
translation units (P2-06), the host emitter (P2-07) or IR lowering.

## Carried-forward findings

- `update_sums.py` globs `schemas/*.json` while the directory is `schema/`, so
  `schema/*.json` (and `openrecomp/*.py`) remain outside the integrity manifest
  (pre-existing; deferred).
- Direct-call graph only; indirect calls/jumps remain unresolved by design.
- Toolchain-gated gates remain unexecutable on this host.
- No Phase-2 gate aggregator yet; stage gates are standalone deterministic tests.
- Future integration point: accept later PS2/R5900 evidence through the
  adapter/frontend descriptor seam without duplicating or anticipating the other PC's
  unmerged work.

## Git status (short)

- Modified: `SOURCE_SHA256SUMS.txt` (one additive entry; 114 total), `STATE.md`,
  `HANDOFF.md`.
- Added (untracked): `openrecomp/call_graph.py`, `tools/test_call_graph_v1.py`,
  `.openrecomp-phase2/evidence/P2-04/`.
- Untouched untracked residue: `.openrecomp-phase2/backups/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No commit created.

OPENRECOMP_P2_04=PASS
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61
CURRENT_STAGE=P2-05
