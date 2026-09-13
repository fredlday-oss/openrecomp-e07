# OpenRecomp Phase 2 Handoff

STATUS: P2-02 `PASS`; P2-03 not started.

Frozen Phase-1 reference (verified):

- commit: `46c2f971e1a42cf49bd936bad94697b81bf31002`
- tag: `openrecomp-phase1-pass` (annotated object `8dbbd79ac3c7104bfa0374aecf2d9093be89c6c7`)
- verdict: `OPENRECOMP_PHASE1_MULTIARCH_PROOF=PASS`
- P2-00 boundary: `1b40269cc80cd19d49d8870f8e65aa1eced69885`
- P2-01 boundary (P2-02 starting commit): `a0c483029727168b1371aa9683e82900f9e14638`
- branch: `phase2/opencode-v1`.

## P2-02 outcome

Evidence: `.openrecomp-phase2/evidence/P2-02/RESULT.md`.
Markers: `OPENRECOMP_P2_02=PASS`, `OPENRECOMP_CFG_V1=PASS tests=82`.

- `openrecomp/cfg.py`: deterministic neutral `build_cfg` / `ControlFlowGraph`.
  Boundaries derive from explicit entries, proven direct targets and structural
  continuation via `DecodedInstruction.size_bytes`; direct calls record call sites
  and keep only the `CALL_RETURN` continuation; indirect jumps/calls stay
  unresolved with explicit inventories; `CLOSED`/`OPEN` modes; conservative
  `PROVEN`/`CANDIDATE` propagation.
- Backwards-compatible `openrecomp/program_model.py` change: unresolved
  target-bearing successors may now carry a `detail` (required for OPEN CFG).
- `tools/test_cfg_v1.py`: 82 deterministic checks incl. real NES6502 variable-width
  decode, 64-bit addresses, both CFG modes, and all required fail-closed rejections.
- Frozen IR V1 / Module Image V1 / Phase-1 semantics unchanged.

## Exact next action

Start P2-03: function recovery over the neutral CFG — entry/function ownership with
explicit unknown/unresolved regions and a direct-call graph built from
`ControlFlowGraph.direct_call_sites` (direct calls only; unresolved indirect calls
kept separate per `AGENTS.md`). Heuristic ownership stays `CANDIDATE`; ambiguous
cases must fail closed. Do not implement translation units (P2-06), host emitter
(P2-07) or IR lowering.

## Verification commands / results

```text
python tools/test_cfg_v1.py
OPENRECOMP_CFG_V1=PASS tests=82
(byte-identical across two runs; stdout sha256 483df98e4ecb6a64441d22692ddcd54777ec52956dc041dae44242cb32886e70)

python tools/test_program_model_v1.py
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49

python tools/phase1_host_gates_v1.py --json .openrecomp-phase2/evidence/P2-02/host_gates.json
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS

python tools/phase1_host_gates_v1.py --only source-integrity
PASS source-integrity  verified 112 manifest entries
```

## Unresolved evidence / limitations

- No function discovery/call graph/indirect resolution in P2-02 (P2-03+).
- `schema/*.json` and `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt`
  (pre-existing `update_sums.py` `schemas/` glob gap); covered by tests and hashes in
  RESULT.md.
- Toolchain-gated gates `e07-hardened-end-to-end` and `external-repro-v1` require
  `clang`/`gcc`/POSIX and remain skipped; never counted as pass.
- No Phase-2 gate aggregator yet; stage gates are standalone deterministic tests.

## Git status (short)

- Modified: `openrecomp/program_model.py` (validator relaxation),
  `SOURCE_SHA256SUMS.txt` (one additive entry; 112 total).
- Added (untracked): `openrecomp/cfg.py`, `tools/test_cfg_v1.py`,
  `.openrecomp-phase2/evidence/P2-02/`.
- Untouched untracked residue: `.openrecomp-phase2/backups/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No commit created.

Resume by reading `CONTROL_POLICY.md`, `SCOPE.md`, `STAGE_QUEUE.md`, `STATE.md`,
`HANDOFF.md`, and `EVIDENCE_SCHEMA.md`, then work only on `CURRENT_STAGE`.
