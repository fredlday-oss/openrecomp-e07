# OpenRecomp Phase 2 State

PHASE=2
BASELINE_TAG=openrecomp-phase1-pass
BASELINE_COMMIT=46c2f97
CURRENT_STAGE=P2-03
LAST_PASSED_STAGE=P2-02
STATUS=READY
FINAL_VERDICT=NOT_YET_EVALUATED

## Stage ledger

| ID | Stage | Status | Evidence |
| --- | --- | --- | --- |
| P2-00 | Baseline + control plane | `PASS` | `.openrecomp-phase2/evidence/P2-00/RESULT.md` |
| P2-01 | Shared program model V1 | `PASS` | `.openrecomp-phase2/evidence/P2-01/RESULT.md` |
| P2-02 | CFG construction V1 | `PASS` | `.openrecomp-phase2/evidence/P2-02/RESULT.md` |

## P2-02 result (PASS)

- Added `openrecomp/cfg.py`: neutral `build_cfg` / `ControlFlowGraph` with
  `EntryPoint`, `CallSite`, `CFGMode` (CLOSED/OPEN), `CFGError` and
  `combine_evidence`. Boundaries are derived only from explicit entries, proven
  direct targets, and structural continuation using `DecodedInstruction.size_bytes`
  (no ISA/fixed-width assumptions).
- Direct calls record call sites and add only the `CALL_RETURN` continuation; the
  callee is never absorbed. Indirect jumps/calls stay explicitly unresolved with
  inventories; no targets are guessed.
- Evidence is conservative: `PROVEN` only when every input is `PROVEN`;
  `CANDIDATE` never silently promoted; classification survives serialization.
- Backwards-compatible P2-01 change: `ProgramModel._validate_block` now permits
  unresolved target-bearing successors that carry a `detail` (needed for OPEN-mode
  edges). No P2-01 test weakened; P2-01 still `tests=49`.
- Gates: `OPENRECOMP_CFG_V1=PASS tests=82` (byte-identical across two runs);
  `OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49`; full Phase-1 host suite
  `44 PASS / 0 FAIL / 2 SKIPPED`; `source-integrity` verified 112 entries.
- No schema change required; the CFG wraps into the frozen P2-01 ProgramModel for
  validation.

## Next exact action

Begin P2-03 — function recovery: entry/function ownership over the neutral CFG with
explicit unknown/unresolved regions and a direct-call graph (direct calls only;
unresolved indirect calls separate, per `AGENTS.md`). Heuristic ownership stays
`CANDIDATE`; ambiguous cases fail closed. Do not implement translation units (P2-06),
the host emitter (P2-07) or IR lowering.

## Carried-forward findings

- `update_sums.py` globs `schemas/*.json` while the directory is `schema/`, so
  `schema/*.json` (and `openrecomp/*.py`) remain outside the integrity manifest
  (pre-existing; deferred).
- Toolchain-gated gates remain unexecutable on this host.
- No Phase-2 gate aggregator yet; stage gates are standalone deterministic tests.
- Future integration point: accept later PS2/R5900 evidence through the
  adapter/frontend descriptor seam without duplicating or anticipating the other PC's
  unmerged work. The CFG builder is parameterized by neutral flow/size metadata rather
  than 32-bit-only or MIPS-classic assumptions.

## Git status (short)

- Modified: `openrecomp/program_model.py` (backwards-compatible validator relaxation),
  `SOURCE_SHA256SUMS.txt` (one additive tool entry; 112 total).
- Added (untracked): `openrecomp/cfg.py`, `tools/test_cfg_v1.py`,
  `.openrecomp-phase2/evidence/P2-02/`.
- Untouched untracked residue: `.openrecomp-phase2/backups/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No commit created.
