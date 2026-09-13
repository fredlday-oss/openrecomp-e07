# OpenRecomp Phase 2 Handoff

STATUS: P2-07 `PASS`; P2-08 (Generic runtime ABI V1) is `NEXT` and not started.

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
- P2-06 boundary (P2-07 starting commit): `f9f2662b90c165a967fa943070e79688ff8198b1`
- branch: `phase2/opencode-v1`.

## P2-07 outcome

Stage: `OPENRECOMP_P2_07_HOST_EMITTER_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-07/RESULT.md`.
Markers: `OPENRECOMP_P2_07=PASS`, `OPENRECOMP_HOST_EMITTER_V1=PASS tests=106`.

- Module `openrecomp/host_emitter.py`: `emit_host_translation` /
  `emit_host_translation_from` -> `HostTranslationSet`, generating deterministic portable
  C (C99; only `<stdint.h>`/`<stddef.h>`).
- Explicit semantic seam: a `HostInstructionSemantics` rule is required for the exact
  `(architecture, op)` pair; the emitter never infers semantics from mnemonics. Bounded
  vocabulary: const/copy/add/sub/mul/and/or/xor/shl/lshr/ashr and signed/unsigned compare
  with explicit 8/16/32/64-bit masking.
- Control flow: direct fallthrough, conditional branch, jump, internal call, return and
  P2-06 `RETURN_LIKE`; `RESOLVED` single targets are direct, finite sets use a `switch`
  with a fail-closed default.
- Fail closed: unsupported op, external direct call, unresolved/bounded/external indirect
  sites, unsupported/malformed classification, non-local edges, traps, un-normalized
  shifts, malformed input. `BOUNDED_CANDIDATES` are never promoted; no indirect target is
  guessed. Policy `BOUNDARY` (default) or `REJECT`.
- Deterministic identifiers/ordering/declarations/helpers; no absolute path, timestamp or
  Python identity; no IR lowering; no runtime ABI (P2-08); no guest execution.
- `tools/test_host_emitter_v1.py`: 106 deterministic checks plus an optional native
  compile+run of a synthetic 8-bit fixture (observed `44 0` == expected).
- No P2-00..P2-06 implementation or evidence modified; frozen IR V1 / Module Image V1
  untouched.

## Queue reconciliation

The queue is reconciled to the executed sequence: `P2-04` = call-graph recovery
(COMPLETE), `P2-05` = translation-unit model (COMPLETE), `P2-06` =
indirect-control-flow classification (COMPLETE), `P2-07` = Host emitter V1 (COMPLETE),
`P2-08` = Generic runtime ABI V1 (NEXT). The original queue numbered `P2-04` Direct CFG
recovery / `P2-05` Indirect-control-flow classification / `P2-06` Translation-unit model;
the reassignment is a control-plane reconciliation caused by actual execution order and
does not change the semantics, claims or evidence of any frozen prior stage
(`P2-00`..`P2-07`). It does not alter `ce9cd4f`, `f9f2662` or any earlier commit.

## Exact next action

Begin P2-08 — Generic runtime ABI V1: architecture-neutral CPU/memory/host-call/input/
frame/audio/runtime contracts. Keep architecture-neutral contracts separate from platform
implementations and do not claim the final Phase-2 marker. P2-08 was **not** started in
P2-07. Do not modify frozen Phase-1 behavior or the P2-00..P2-07 layers except through an
evidence-backed stage.

## Verification commands / results

```text
python tools/test_host_emitter_v1.py
OPENRECOMP_HOST_EMITTER_V1=PASS tests=106
(byte-identical across two runs; stdout sha256 fb6e6e2c6ba660a5c3df75602a59c0501bf86ca53e0371e4942c0c76108c45d5)
(native optional compile+run: clang, observed "44 0", expected "44 0")

python tools/test_indirect_control_flow_v1.py
OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134

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

python tools/phase1_host_gates_v1.py --json .openrecomp-phase2/evidence/P2-07/host_gates.json
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS

python tools/phase1_host_gates_v1.py --only source-integrity
PASS source-integrity  verified 117 manifest entries
```

## Evidence artifacts (UTF-8 text, no BOM)

`.openrecomp-phase2/evidence/P2-07/`: `RESULT.md`, `RESULT.json`, `determinism.txt`,
`changed_files.txt`, `native_compile.txt`, `host_emitter_tests.json`,
`host_emitter_tests.txt`, `host_gates.json`, `host_gates.txt`, `source_integrity.txt`,
`p2_06_indirect_control_flow.txt`, `p2_05_translation_units.txt`, `p2_04_call_graph.txt`,
`p2_03_functions.txt`, `p2_02_cfg.txt`, `p2_01_program_model.txt`, and synthetic
generated-C fixtures `sample_generated_*.c`.

## Unresolved evidence / limitations

- The bounded V1 subset is rule-driven and small; loads, stores, host calls, delay slots,
  calling conventions and runtime services are not emitted.
- A finite resolved target set requires a runtime target value; it is dispatched with a
  `switch` that fails closed outside the proven set.
- Emitted functions are void with no argument/return ABI (deferred to P2-08).
- The native compile+run proves only that a synthetic fixture compiles and computes one
  arithmetic result; it is not an equivalence proof.
- `schema/*.json` / `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt`
  (pre-existing `update_sums.py` `schemas/` glob gap).
- Toolchain-gated gates `e07-hardened-end-to-end` and `external-repro-v1` require
  `clang`/`gcc`/POSIX and remain skipped; never counted as pass.

## Non-claims

No full MIPS32 recompilation, IR lowering, guest/host equivalence, generic runtime ABI or
memory/IO contracts, AOT integration, whole-game recompilation, console compatibility or
RT64 integration. The final `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` marker is not
claimed.

## Git status (short)

- P2-06 boundary commit: `f9f2662` (`phase2: complete P2-06 indirect control flow
  classification`); `HEAD` at P2-07 start.
- Current uncommitted changes: P2-07 implementation + evidence plus control-plane updates
  to `.openrecomp-phase2/STAGE_QUEUE.md`, `.openrecomp-phase2/STATE.md`,
  `.openrecomp-phase2/HANDOFF.md`, plus `SOURCE_SHA256SUMS.txt` (+1 entry).
- Untouched untracked residue: `.openrecomp-phase2/backups/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No P2-07 boundary commit created (left for independent review).

Resume by reading `CONTROL_POLICY.md`, `SCOPE.md`, `STAGE_QUEUE.md`, `STATE.md`,
`HANDOFF.md`, and `EVIDENCE_SCHEMA.md`, then work only on `CURRENT_STAGE`.

OPENRECOMP_P2_07=PASS
OPENRECOMP_HOST_EMITTER_V1=PASS tests=106
CURRENT_STAGE=P2-08
