# OpenRecomp Phase 2 Handoff

STATUS: P2-08 `PASS`; P2-09 (Deterministic build pipeline) is `NEXT` and not started.

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
- P2-07 boundary (P2-08 starting commit): `30b4321011b963efce19b321c72b97f886ba2b3d`
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

## P2-08 outcome

Stage: `OPENRECOMP_P2_08_GENERIC_RUNTIME_ABI_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-08/RESULT.md`.
Markers: `OPENRECOMP_P2_08=PASS`, `OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests=169`.

- Module `openrecomp/runtime_abi.py`: first architecture-neutral generic runtime ABI V1
  (`RuntimeAbiVersion`, `RuntimeMemory`, `RuntimeServiceTable`, `RuntimeHostCallRequest`/
  `RuntimeHostCallRecord`, `RuntimeInputSnapshot`, `RuntimeFrame`, `RuntimeAudio`,
  `RuntimeFailure`/`RuntimeFailureCode`/`RuntimeResult`, `RuntimeConfig`/`RuntimeAbiConfig`,
  `RuntimeState`, `abi_c_declarations`/`abi_c_source`).
- Versioned ABI `openrecomp-generic-runtime-abi 1.0.0`; incompatible versions rejected with
  `ABI_VERSION_MISMATCH`.
- Bounded guest address space: checked read/write, explicit 8/16/32/64-bit width, explicit
  little/big endianness, deterministic out-of-range/width/endianness/segment-overlap and
  64-bit `address+width` overflow failures. No guest-to-host pointer exposure.
- Host calls fail closed for unknown service, arity mismatch and handler failure. Generic
  input/frame/audio contracts and an explicit failure/trap model. `RuntimeState` is
  deterministic (no wall-clock/random/pid/address/filesystem/locale/environment dependence).
- Bounded/additive P2-07 integration: `HostEmitterConfig.runtime_abi` (default null) +
  explicit `HostCallOperation`. A host call is emitted only for a declared service on an
  explicitly external/runtime-mediated P2-06 site; otherwise it fails closed. Default
  (`runtime_abi=None`) output is byte-identical to P2-07.
- `tools/test_runtime_abi_v1.py`: 169 deterministic checks plus an optional native
  compile+run of a synthetic host-call fixture (observed `42 0` == expected).
- No P2-00..P2-07 implementation source modified except the additive/opt-in
  `host_emitter.py` change; no prior test weakened; no P2-09 started.

## Queue reconciliation

The queue is reconciled to the executed sequence: `P2-04` = call-graph recovery
(COMPLETE), `P2-05` = translation-unit model (COMPLETE), `P2-06` =
indirect-control-flow classification (COMPLETE), `P2-07` = Host emitter V1 (COMPLETE),
`P2-08` = Generic runtime ABI V1 (COMPLETE), `P2-09` = Deterministic build pipeline (NEXT).
The original queue numbered `P2-04` Direct CFG recovery / `P2-05` Indirect-control-flow
classification / `P2-06` Translation-unit model; the reassignment is a control-plane
reconciliation caused by actual execution order and does not change the semantics, claims or
evidence of any frozen prior stage (`P2-00`..`P2-08`). It does not alter `ce9cd4f`,
`f9f2662`, `30b4321` or any earlier commit.

## Exact next action

Begin P2-09 — Deterministic build pipeline: reproducible generated-source/object/executable
metadata and hashing. Do not modify frozen Phase-1 behavior or the P2-00..P2-08 layers
except through an evidence-backed stage. P2-09 was **not** started in P2-08, and the final
Phase-2 end-to-end marker is not claimed.

## Verification commands / results

```text
python tools/test_runtime_abi_v1.py
OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests=169
(byte-identical across two runs; stdout sha256 3c0abaf52efa534b2dc639efceb15cd6e5aa17a4ec218d5515b1160f260809a8)
(native optional compile+run: clang, observed "42 0", expected "42 0")

python tools/test_host_emitter_v1.py
OPENRECOMP_HOST_EMITTER_V1=PASS tests=106

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

python tools/phase1_host_gates_v1.py --json .openrecomp-phase2/evidence/P2-08/host_gates.json
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS

python tools/phase1_host_gates_v1.py --only source-integrity
PASS source-integrity  verified 118 manifest entries
```

## Evidence artifacts (UTF-8 text, no BOM)

`.openrecomp-phase2/evidence/P2-08/`: `RESULT.md`, `RESULT.json`, `determinism.txt`,
`changed_files.txt`, `runtime_abi_tests.json`, `runtime_abi_tests.txt`, `host_gates.json`,
`host_gates.txt`, `source_integrity.txt`, `p2_07_host_emitter.txt`,
`p2_06_indirect_control_flow.txt`, `p2_05_translation_units.txt`, `p2_04_call_graph.txt`,
`p2_03_functions.txt`, `p2_02_cfg.txt`, `p2_01_program_model.txt`, plus the synthetic
generated-C fixture `sample_generated_runtime_host_call.c` and scenario output
`synthetic_runtime_fixture.txt`.

## Unresolved evidence / limitations

- `RuntimeState` is a deterministic contract surface for fixtures, not a guest execution
  engine; it does not execute generated host code.
- The generated C contains only boundary declarations (`extern or_rt_*`); no runtime
  implementation is generated. Platform runtime integration is later work.
- The bounded P2-07 semantic subset is unchanged; loads, stores, delay slots, calling
  conventions and most runtime services remain outside the emitted set.
- A finite resolved target set requires a runtime target value; it is dispatched with a
  `switch` that fails closed outside the proven set.
- Emitted functions are void with no argument/return ABI.
- The native compile+run proves only that a synthetic fixture compiles and returns one
  host-call result; it is not an equivalence proof.
- `schema/*.json` / `openrecomp/*.py` (including `runtime_abi.py`) remain outside
  `SOURCE_SHA256SUMS.txt` (pre-existing `update_sums.py` `schemas/` glob gap); their hashes
  are recorded in `changed_files.txt` / `RESULT.json`.
- Toolchain-gated gates `e07-hardened-end-to-end` and `external-repro-v1` require
  `clang`/`gcc`/POSIX and remain skipped; never counted as pass.

## Non-claims

No full MIPS32 recompilation, IR lowering, guest/host equivalence, console-specific runtime,
BIOS/HLE, GPU/APU/DSP, controller backend, audio device, window, AOT integration,
whole-game recompilation, console compatibility or RT64 integration. The generic runtime ABI
is a contract surface only; the P2-09 deterministic build pipeline was not started. The final
`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` marker is not claimed.

## Git status (short)

- P2-07 boundary commit: `30b4321` (`phase2: complete P2-07 host emitter v1`); `HEAD` at
  P2-08 start.
- Current uncommitted changes: P2-08 implementation + evidence (`openrecomp/runtime_abi.py`,
  additive `openrecomp/host_emitter.py`, `tools/test_runtime_abi_v1.py`,
  `.openrecomp-phase2/evidence/P2-08/`) plus control-plane updates to
  `.openrecomp-phase2/STAGE_QUEUE.md`, `.openrecomp-phase2/STATE.md`,
  `.openrecomp-phase2/HANDOFF.md`, plus `SOURCE_SHA256SUMS.txt` (+1 entry, 117 -> 118).
- Untouched untracked residue: `.openrecomp-phase2/backups/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No P2-08 boundary commit created (left for independent review).

Resume by reading `CONTROL_POLICY.md`, `SCOPE.md`, `STAGE_QUEUE.md`, `STATE.md`,
`HANDOFF.md`, and `EVIDENCE_SCHEMA.md`, then work only on `CURRENT_STAGE`.

OPENRECOMP_P2_08=PASS
OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests=169
CURRENT_STAGE=P2-09
