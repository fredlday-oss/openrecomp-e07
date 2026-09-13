# OpenRecomp Phase 2 State

PHASE=2
BASELINE_TAG=openrecomp-phase1-pass
BASELINE_COMMIT=46c2f97
CURRENT_STAGE=P2-04
LAST_PASSED_STAGE=P2-03
STATUS=READY
FINAL_VERDICT=NOT_YET_EVALUATED

## Stage ledger

| ID | Stage | Status | Evidence |
| --- | --- | --- | --- |
| P2-00 | Baseline + control plane | `PASS` | `.openrecomp-phase2/evidence/P2-00/RESULT.md` |
| P2-01 | Shared program model V1 | `PASS` | `.openrecomp-phase2/evidence/P2-01/RESULT.md` |
| P2-02 | CFG construction V1 | `PASS` | `.openrecomp-phase2/evidence/P2-02/RESULT.md` |
| P2-03 | Function discovery V1 | `PASS` | `.openrecomp-phase2/evidence/P2-03/RESULT.md` |

## P2-03 result (PASS)

Stage: `OPENRECOMP_P2_03_FUNCTION_DISCOVERY_V1`.
Starting boundary commit: `65386e45f9af1d581d0e14f8cca3940a6a82d75c` (P2-02/P2-02 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Module `openrecomp/functions.py`: `discover_functions(cfg, *, program_entries,
  function_entries, include_direct_call_targets)` -> `FunctionDiscoveryResult`.
- Entry sources: `PROGRAM_ENTRY` (int default PROVEN, `EntryPoint` override),
  `DIRECT_CALL` (CFG call-site evidence), `EXPLICIT_PROVEN`, `EXPLICIT_CANDIDATE`;
  multiple bases per address preserved in `EntryBasis` and `FunctionUnit.entry_sources`.
- Ownership: deterministic priority (PROVEN before CANDIDATE, then lower address);
  candidate-inside-proven suppressed with explicit reason; contradictory PROVEN
  ownership fails closed (defensive); shared non-entry blocks get one deterministic
  owner recorded in `shared_blocks`; unowned disconnected blocks recorded.
- Call/indirect policy: caller owns the `CALL_RETURN` continuation only; callee never
  absorbed; external direct-call targets inventoried (no function invented); unresolved
  indirect calls/jumps never traverse or create functions.
- Evidence: entry PROVEN if any independent source PROVEN; `FunctionUnit.evidence`
  conservative (`combine_evidence` over entry, owned blocks and internal edges);
  CANDIDATE never promoted; survives serialization.
- P2-01 correction: optional `FunctionUnit.entry_sources` and `canonical_blocks()`
  (entry block first, remaining sorted by `(entry_address, id)`); schema adds optional
  `entry_sources`. Backwards compatible; existing byte representations where entry ==
  lowest block unchanged.
- Validation highlights: entry address greater than a lower reachable block round-trips
  serialize -> deserialize -> serialize; addresses above `0xFFFFFFFF`; bounded
  NES6502-derived CFG.

## Gates

```text
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
OPENRECOMP_CFG_V1=PASS tests=82
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
PASS source-integrity  verified 113 manifest entries
```

Determinism: two consecutive function-discovery runs produced byte-identical stdout
(`sha256 05218d8d1db991e2ff93679340490d59dcea24add7c3c8d2faee0bf26cbe39a8`).

## Next exact action

Begin P2-04 — direct CFG recovery / whole-program direct-call-graph construction and
validation over the discovered functions: consolidate `direct_call_sites` into a
validated inter-function direct call graph, keep unresolved indirect calls separate
(per `AGENTS.md`), and validate graph consistency using neutral evidence rules. Do not
implement translation units (P2-06), the host emitter (P2-07) or IR lowering.

## Carried-forward findings

- `update_sums.py` globs `schemas/*.json` while the directory is `schema/`, so
  `schema/*.json` (and `openrecomp/*.py`) remain outside the integrity manifest
  (pre-existing; deferred).
- `direct_callees` are provisional structural facts; the final validated whole-program
  call graph is P2-04.
- Toolchain-gated gates remain unexecutable on this host.
- No Phase-2 gate aggregator yet; stage gates are standalone deterministic tests.
- Future integration point: accept later PS2/R5900 evidence through the
  adapter/frontend descriptor seam without duplicating or anticipating the other PC's
  unmerged work.

## Git status (short)

- Modified: `openrecomp/program_model.py` (optional `entry_sources`, canonical block
  order), `schema/openrecomp-program-v1.schema.json` (optional `entry_sources`),
  `SOURCE_SHA256SUMS.txt` (one additive entry; 113 total), `STATE.md`, `HANDOFF.md`.
- Added (untracked): `openrecomp/functions.py`, `tools/test_functions_v1.py`,
  `.openrecomp-phase2/evidence/P2-03/`.
- Untouched untracked residue: `.openrecomp-phase2/backups/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No commit created.

OPENRECOMP_P2_03=PASS
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
CURRENT_STAGE=P2-04
