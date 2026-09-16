# OpenRecomp Phase 2 Handoff

STATUS: Phase 2 `COMPLETE` — `P2-99` (final verdict) issued `OPENRECOMP_P2_99=PASS` and `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` on the audited terminal tree. All stages P2-00, P2-01..P2-14, P2-20..P2-23, P2-30, P2-40, P2-50, P2-90 and P2-91 are `PASS`; the verdict is bounded to the exact claim in `.openrecomp-phase2/evidence/P2-99/final_claim_boundary.md` and implies no arbitrary NES ROM/MIPS32/commercial-game/console/cycle-accurate/PS1/PS2/Xbox/universal/future-architecture compatibility.

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
- P2-08 boundary (P2-09 starting commit): `10971b76090746081cb29ca3405f96da7f143011`
- P2-09 boundary (P2-10 starting commit): `161893389cca5a30aa462670f19ecabfc1be679d`
- P2-10 boundary (P2-11 starting commit): `62044d38feec255fbcceb72754e890e7b644c35e`
- P2-11 boundary (P2-12 starting commit): `6cb5ff40eca30eaeb383333c10bcf50165a167ce`
- P2-12 boundary (P2-13 starting commit): `aa9939a73addde9e029111a1c6b0a6a783dda8cc`
- P2-13 boundary (P2-14 starting commit): `c32a766a0b6499a239fcd4af351a73f1c172a1be`
- P2-14 boundary (P2-20 starting commit): `2fc27bfd80ef36b62ab3dc854562bbb4d0ce82db`
- branch: `phase2/opencode-v1`.

## P2-91 outcome

Stage: `OPENRECOMP_PHASE2_EVIDENCE_CLOSURE_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-91/RESULT.md`.
Markers: `OPENRECOMP_P2_91=PASS`,
`OPENRECOMP_PHASE2_EVIDENCE_CLOSURE_V1=PASS tests=882`.

- New deterministic closure gate `tools/test_phase2_evidence_closure_v1.py` (882
  checks). No `openrecomp/*.py` implementation source was modified; no
  architecture feature was added; no compatibility claim was broadened.
- Authoritative evidence index `PHASE2_EVIDENCE_INDEX.md` +
  `PHASE2_EVIDENCE_INDEX.json` cover all 23 completed stages with PASS marker,
  gate marker, check count, evidence directory, principal RESULT, fixture/input
  identity, generated/executable/package identity, deterministic-run identity
  and claim boundary. Every indexed identity is re-verified against frozen
  stage evidence; every indexed reference resolves.
- `PHASE2_LIMITATIONS.md` (13 proven/bounded-proven claims, 10
  unproven/out-of-scope claims) and `PHASE2_CLAIM_MATRIX.md` (23-key vocabulary:
  18 audited P2-90 claims unchanged + 5 closure claims) are the authoritative
  limitations and claim-to-evidence records.
- Host-path resolution: the nine P2-90-identified frozen occurrences are
  classified as seven historical frozen (six hash-pinned) and two safely
  relocatable metadata with host-neutral derivatives; no frozen file was
  modified; no new absolute host path exists in Phase-2 evidence, the
  control-plane narrative, shared sources or release packages. Details:
  `host_path_audit.md`, `host_path_occurrences.json`, `portable_derivatives/`.
- P2-90 whole-project regression rerun after all P2-91 changes: `PASS`, 361
  audit checks, 22 gates, 1990 gate checks, 0 failures, empty stderr; stdout
  content identical to the frozen P2-90 capture (`p2_90_rerun.txt`, LF content
  sha256 `00675593...`; recorded capture `74e9eada...` byte-identical). The six
  frozen P2-90 capture files were snapshotted, captured and restored
  byte-identically (`p2_90_capture_preservation.json`); the only regeneration
  delta is the expected manifest-count line (132 -> 133).
- Source integrity: `PASS`, 133 manifest entries; manifest delta exactly
  additive (removing the closure-gate line reproduces `1bf21db5...`).
  Legal/content policy clean.
- Determinism: two consecutive full gate runs byte-identical
  (`gate_determinism.txt`, `p2_91_run1.txt`, `p2_91_run2.txt`).
- Final marker preserved: `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN`
  (reserved for P2-99).

## P2-99 outcome

Stage: `OPENRECOMP_PHASE2_FINAL_VERDICT_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-99/RESULT.md`.
Markers: `OPENRECOMP_P2_99=PASS`, `OPENRECOMP_PHASE2_FINAL_VERDICT_V1=PASS`,
`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`.

- New deterministic terminal gate `tools/test_phase2_final_verdict_v1.py`. It
  re-verifies the completed-stage matrix (P2-00, P2-01..P2-14, P2-20..P2-23,
  P2-30, P2-40, P2-50, P2-90, P2-91), the Phase-1 boundary, the P2-91 evidence
  index, the terminal whole-project P2-90 regression re-run, the P2-91
  evidence-closure re-run, source integrity, the legal/content policy and the
  claim/limitation consistency, and issues the final verdict only when every
  required invariant passes.
- Terminal P2-90 re-run: `OPENRECOMP_P2_90=PASS`,
  `OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1=PASS tests=361 gates=22 gate_tests=1990`,
  0 failures; the terminal capture reproduces the frozen P2-90 capture
  byte-for-byte except the authorized final-verdict line, and the six frozen
  P2-90 capture files were snapshotted, regenerated, captured and restored
  byte-identically (`p2_90_capture_preservation.json`).
- P2-91 closure re-run on the terminal tree: `PASS tests=882`; source integrity:
  `PASS`, 134 manifest entries with the exact authorized terminal delta (P2-99
  gate entry added, the two terminal-aware gates' hashes refreshed, all other
  entries reproducing the P2-91 manifest `05180dec...` and the P2-90 manifest
  `1bf21db5...`); legal/content policy clean.
- Terminal-state contract transition (documented): the P2-90 and P2-91 gates now
  accept the P2-99 stage state and the terminal marker PASS only when the P2-99
  verdict evidence exists, declares PASS, pins the live P2-99 gate by SHA-256
  and the control plane states the terminal markers; unauthorized PASS claims
  still fail. The P2-91 closure gate's pre-terminal stdout remains byte-identical
  to its recorded run (`tests=882`).
- Bounded final claim issued for the accumulated evidence: an
  architecture-neutral static-recompilation pipeline taking supported synthetic
  guest programs through decoding, program modelling, control-flow recovery,
  translation, native host compilation, generic runtime execution,
  deterministic observable equivalence and reproducible packaging across the
  audited NES6502 and MIPS32 paths. Arbitrary NES ROM/MIPS32/commercial-game/
  complete-console/cycle-accurate/PS1/PS2/Xbox/universal/future-architecture
  compatibility remain `NOT_PROVEN`/`OUT_OF_SCOPE`.
- Determinism: two official terminal gate runs produced byte-identical stdout
  (`run1.txt` from `--run-regression`, `run2.txt` from the verify-only re-run;
  recorded in `gate_determinism.txt`).
- No prior stage was weakened; no frozen evidence was modified; the Phase-1 tag
  `openrecomp-phase1-pass` remains `46c2f971e1a42cf49bd936bad94697b81bf31002`.

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

## P2-09 outcome

Stage: `OPENRECOMP_P2_09_DETERMINISTIC_BUILD_PIPELINE_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-09/RESULT.md`.
Markers: `OPENRECOMP_P2_09=PASS`, `OPENRECOMP_DETERMINISTIC_BUILD_V1=PASS tests=120`.

- Module `openrecomp/build_pipeline.py`: deterministic build pipeline with canonical
  `openrecomp-build-manifest-v1` serialization (`BuildConfig`, `BuildSource`, `BuildInput`,
  `BuildArtifact`, `BuildArtifactKind`, `BuildToolchain`, `ToolchainIdentity`,
  `BuildManifest`, `BuildRun`, `BuildComparison`, `BuildReproducibility`, `BuildStatus`,
  `BuildError`); entry points `build_generated_host`, `build_generated_host_from`,
  `discover_toolchain`, `compare_runs`, `verify_artifact_hashes`.
- Toolchain detected, never assumed: `clang-cl.exe` 22.1.8 (target
  `x86_64-pc-windows-msvc`) + `lld-link.exe` 22.1.8; `/Brepro` passed directly to both
  (`/c /Brepro /Od /std:c11 /nologo`, `/Brepro /nologo`). No binary post-processing, no
  manual COFF timestamp editing, no post-link normalization.
- Two genuinely independent builds in distinct isolated directories (source regenerated per
  run, artifacts never copied) produced byte-identical source, object and executable hashes;
  classification `EXECUTABLE_REPRODUCIBLE`. A cross-root build reproduced the same hashes.
- Inspected `llvm-readobj` values: COFF `TimeDateStamp` `0x0` for both objects and
  `0x974E5A9` for both executables (identical across runs).
- The manifest contains no timestamp, temp directory, absolute path, username, hostname,
  pid, UUID or Python identity; the validator rejects those fields.
- `tools/test_build_pipeline_v1.py`: 120 deterministic checks, including output-only
  `--evidence-dir`, evidence-path independence, PE/COFF inspection, leakage checks and
  fail-closed contracts (source hash mismatch, ABI mismatch, malformed manifest, duplicate
  output, unsafe names, unsupported compiler, failed compile, over-strong claim).
- Optional native build/execution smoke test observed `42 0` (bounded synthetic smoke test,
  not equivalence). No P2-10 started.

## P2-10 outcome

Stage: `OPENRECOMP_P2_10_TINY_MIPS32_END_TO_END_PROOF_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-10/RESULT.md`.
Markers: `OPENRECOMP_P2_10=PASS`, `OPENRECOMP_MIPS32_END_TO_END_V1=PASS tests=108`.

- Dedicated gate `tools/test_mips32_end_to_end_v1.py` (108 checks). No second recompilation
  path was added; the proof reuses the frozen Phase-2 modules and adds only the gate and
  its evidence.
- Synthetic/original 13-instruction MIPS32 fixture (52 bytes,
  `b33b597c28eb7f7239ee5079728c7f3e447387d4ed34525c445cf8c1e9234975`); no commercial
  ROM/ELF/game bytes.
- Real pipeline traversal: adapter decode -> P2-01 ProgramModel -> P2-02 CFG -> P2-03
  function discovery -> P2-04 call graph -> P2-05 translation units -> P2-06 classification
  (`jr r31` = `RETURN_LIKE`, no guessed targets; fails closed without evidence) -> P2-07
  host emission -> P2-09 deterministic build. P2-08 is `NOT_APPLICABLE_FOR_FIXTURE`.
- Independent expected observable (mathematical derivation + tiny independent reference
  interpreter + Phase-1 `mips32_oracle_v1` cross-check) equals the actual native observable
  exactly (`r5=11 r6=6 r7=1`, returncode 0, stable across runs).
- Two independent `/Brepro` builds: generated source, objects and executable byte-identical
  (`f94c95d2e86fca83f56e5e87a98bccaa1e2a4ced3fd9222aef29608592810f4e`);
  `EXECUTABLE_REPRODUCIBLE`; no binary post-processing.
- No P2-01..P2-09 implementation source modified; no prior test weakened; P2-11 not started.

## P2-11 outcome

Stage: `OPENRECOMP_P2_11_MIPS32_CALLS_STACK_MEMORY_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-11/RESULT.md`.
Markers: `OPENRECOMP_P2_11=PASS`, `OPENRECOMP_MIPS32_CALLS_MEMORY_V1=PASS tests=77`.

- Dedicated gate `tools/test_mips32_calls_memory_v1.py` (77 checks). One synthetic/original
  multi-function MIPS32 fixture with an o32-style stack frame, a direct `jal` call and
  checked `lw`/`sw` through the P2-08 memory boundary.
- Additive, opt-in P2-07 extension: `HostLoad`/`HostStore` emitted as checked
  `or_rt_memory_read`/`or_rt_memory_write` calls, gated on
  `HostEmitterConfig.runtime_abi`. Default output unchanged; P2-07/P2-08 gates still pass;
  no pointer casts.
- Real pipeline traversal: P2-01 two functions -> P2-02 CFG -> P2-03 discovery -> P2-04
  call graph `fn_1000 -> fn_1088` (`INTERNAL_DIRECT`) -> P2-05 two units -> P2-06 two
  `RETURN_LIKE` `jr ra` sites, no guessed targets -> P2-07 emission -> P2-08 memory
  boundary -> P2-09 deterministic build.
- Independent expected observable (true-MIPS32 reference interpreter with delay slots and
  `jal`/`jr $ra`, explicit derivation, RAM checksum `409079371`) equals the actual native
  observable (`r5=42 r2=21 sp=256 ra=0`, returncode 0, stable).
- Two independent `/Brepro` builds byte-identical (`program.exe bd719060...`);
  `EXECUTABLE_REPRODUCIBLE`; no binary post-processing.
- Runtime OOB memory access fails closed (`failed=1`, no host out-of-bounds write).
- Cross-stage adjustment: `tools/test_mips32_end_to_end_v1.py`'s obsolete
  `no-p2-11-evidence-directory` guard replaced by `no-p2-11-memory-emission-in-p2-10`
  (count unchanged at 108, replacement coverage; reason in P2-11 evidence). P2-10 semantics
  unchanged; its gate stdout hash changed.

## P2-12 outcome

Stage: `OPENRECOMP_P2_12_MIPS32_DIRECT_CFG_STRESS_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-12/RESULT.md`.
Markers: `OPENRECOMP_P2_12=PASS`, `OPENRECOMP_MIPS32_DIRECT_CFG_V1=PASS tests=96`.

- Dedicated gate `tools/test_mips32_direct_cfg_v1.py` (96 checks). No `openrecomp/*.py`
  implementation source modified; the stage reuses the existing pipeline and the P2-11
  opt-in memory emission.
- Synthetic/original 35-instruction MIPS32 fixture (140 bytes, `2e3309f3...`): counted loop
  with a backward branch and both outcomes, conditional branches, a direct `jal` call with
  `jr ra` returns, o32 `$ra` save/restore, and a bounded indirect dispatch (`jr r5`).
- Real pipeline traversal: P2-01 two functions -> P2-02 CFG (14 blocks; loop back edge;
  branch/call/unresolved-indirect edges) -> P2-03 discovery -> P2-04 call graph
  `fn_1000 -> fn_1080` -> P2-05 two units -> P2-06 dispatch `RESOLVED`/`EXACT_TARGET_SET`
  `(0x105c, 0x106c)` plus two `RETURN_LIKE` sites -> P2-07 switch emission with fail-closed
  default -> P2-08 memory boundary -> P2-09 deterministic build.
- Independent expected observable (true-MIPS32 reference interpreter with delay slots and
  `jal`/`jr $ra`) equals the actual native observable (`acc=15`, `r2=20`, case A `r6=120`,
  `r7=125`, `sp=248`, `ra=0`); returncode 0; stable.
- Two independent `/Brepro` builds byte-identical (`program.exe 3d92fc27...`);
  `EXECUTABLE_REPRODUCIBLE`; no binary post-processing.
- Out-of-set runtime selector (`0x2000`) hits the switch default and fails closed
  (`failed=1`); `BOUNDED_CANDIDATES` never promoted; evidence-free indirect control flow is
  `UNRESOLVED_INDIRECT_JUMP`.
- Cross-stage adjustment: `tools/test_mips32_calls_memory_v1.py`'s obsolete
  `no-p2-12-evidence-directory` guard replaced by `no-p2-12-switch-emission-in-p2-11`
  (count unchanged at 77, replacement coverage; reason in P2-12 evidence). P2-11 semantics
  unchanged; its gate stdout hash changed.

## P2-13 outcome

Stage: `OPENRECOMP_P2_13_RUNTIME_HOST_BOUNDARY_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-13/RESULT.md`.
Markers: `OPENRECOMP_P2_13=PASS`, `OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1=PASS tests=80`.

- Dedicated gate `tools/test_runtime_host_boundary_v1.py` (80 checks). No `openrecomp/*.py`
  implementation source modified; the stage reuses the P2-08 host-call seam and runtime ABI.
- Synthetic/original 5-instruction MIPS32 fixture (20 bytes, `7c9ba624...`): guest computes
  `r4=42`, a runtime-mediated `jr r4` site is classified `INDIRECT_CALL` with explicit P2-06
  `EXTERNAL_OR_RUNTIME_MEDIATED` evidence (mechanism `runtime-service`), then a continuation
  `r5 = result + 8`.
- Real pipeline traversal: P2-01 -> P2-02 CFG (`CALL_RETURN` continuation) -> P2-03 ->
  P2-04 -> P2-05 (unresolved call site preserved) -> P2-06 -> P2-07
  `or_rt_host_call(OR_RT_SERVICE_DEMO_DOUBLE, ...)` -> P2-08 ABI (service id 1, macro,
  known/unknown/arity dispatch, `RuntimeState` record) -> P2-09 deterministic build.
- Independent expected observable (guest arithmetic + declarative service `x -> 2x`):
  `r4=84`, `r5=92`, record `calls=1 last_service=1 last_arg=42 last_result=84`; actual
  native identical; returncode 0; stable.
- Two independent `/Brepro` builds byte-identical (`program.exe 8ab94ab0...`);
  `EXECUTABLE_REPRODUCIBLE`; no post-processing; no guest-to-host pointers.
- Unsupported declared service fails closed natively (`failed=1`, error recorded,
  continuation not executed). Host-call rule without external evidence, undeclared service,
  missing runtime ABI and malformed call operations are all rejected.
- Cross-stage adjustment: `tools/test_mips32_direct_cfg_v1.py`'s obsolete
  `no-p2-13-evidence-directory` guard replaced by `no-p2-13-host-call-emission-in-p2-12`
  (count unchanged at 96, replacement coverage; reason in P2-13 evidence). P2-12 semantics
  unchanged; its gate stdout hash changed.

## P2-14 outcome

Stage: `OPENRECOMP_P2_14_MIPS32_LARGER_OPEN_FIXTURE_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-14/RESULT.md`.
Markers: `OPENRECOMP_P2_14=PASS`, `OPENRECOMP_MIPS32_LARGER_FIXTURE_V1=PASS tests=82`.

- Dedicated gate `tools/test_mips32_larger_fixture_v1.py` (82 checks). No `openrecomp/*.py`
  implementation source modified; the stage reuses the existing pipeline/emitter/runtime ABI.
- Synthetic/original 4-function, 57-instruction MIPS32 fixture (228 bytes, `1c233f56...`):
  `main` loops `i = 1..20`, accumulates `outer(i) = 4i + 1` in memory, tracks the maximum
  with `bigger`, returns `total + best = 941`; `outer` calls `inner` with a nested frame.
- Real pipeline traversal: P2-01 four functions -> P2-02 CFG (18 blocks; loop conditional,
  back jump, three call continuations) -> P2-03 discovery -> P2-04 call graph (3
  `INTERNAL_DIRECT` edges) -> P2-05 four units (`[2,1,0,0]` call edges) -> P2-06 five
  `RETURN_LIKE` sites -> P2-07 emission (`25d8d85f...`) -> P2-08 memory boundary -> P2-09
  deterministic build.
- Deterministic recompilation: two independent structural runs with identical fingerprints
  and byte-identical source. Deterministic replay: three native executions with
  byte-identical stdout (`5a44a08c...`).
- Independent expected observable (reference interpreter 800 steps + derivation) equals the
  actual native observable (`total=860`, `best=81`, observable `941`); returncode 0.
- Two independent `/Brepro` builds byte-identical (`program.exe 1e81bf8c...`);
  `EXECUTABLE_REPRODUCIBLE`; no binary post-processing.
- Cross-stage adjustment: `tools/test_runtime_host_boundary_v1.py`'s obsolete
  `no-p2-14-evidence-directory` guard replaced by `no-guest-memory-access-in-p2-13` (count
  unchanged at 80, replacement coverage; reason in P2-14 evidence). P2-13 semantics
  unchanged; its gate stdout hash changed.
- P2-90 annotation: the P2-14 gate itself was also adjusted during the P2-20 session. Its
  obsolete build-state guard `no-p2-20-evidence-directory` was replaced by the genuine
  P2-14 property `no-nes6502-dependency-in-p2-14` (count unchanged at 82; the replacement
  is visible in the P2-20..P2-50 regression captures). The frozen pre-adjustment capture
  `P2-14/p2_14_gate.txt` (`115c2c8a...`) is historical; the current P2-14 gate stdout hash
  is `197a6c5e5c5578ee6fced2eb45b937359bbd612dab8ec11bb4d5c2e6b717da51`.

## P2-20 outcome

Stage: `OPENRECOMP_P2_20_NES6502_PROGRAM_BRIDGE_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-20/RESULT.md`.
Markers: `OPENRECOMP_P2_20=PASS`, `OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1=PASS tests=86`.

- New bridge `openrecomp/frontends/nes6502.py` and dedicated gate
  `tools/test_nes6502_program_bridge_v1.py` (86 checks). No existing `openrecomp/*.py`
  implementation source modified.
- Synthetic/original 15-instruction NES6502 fixture (26 bytes,
  `0a236023c59fd5363d0ebdd6ffb18d9b4e792ebeaa11a72ca513b183539fa398`): entry `0x8000`,
  counted loop, indexed store, direct `jsr`/`rts`, direct `jmp`, indirect `jmp ($0300)`.
- Real pipeline traversal through the same shared layers as MIPS32: P2-01 ProgramModel
  (`architecture=nes6502`, 15 instructions) -> P2-02 CFG (8 blocks; loop back edge,
  call continuation, direct jump, unresolved indirect jump) -> P2-03 function discovery
  (`fn_8000`, `fn_8018`; unowned blocks `blk_8011`, `blk_8015` preserved) -> P2-04 call
  graph (one `INTERNAL_DIRECT` edge) -> P2-05 two translation units -> P2-06 one
  `UNRESOLVED_INDIRECT_JUMP` site at `0x8012` with no guessed targets.
- Deterministic fingerprints: program `0dfbf094...`, CFG `2924881e...`, functions
  `7b83a827...`, call graph `e99dce4b...`, units `d0062fed...`, classification
  `67113cc1...`; two independent `bridge_program` calls produce byte-identical
  serializations.
- Independent Phase-1 reference cross-check: `tools/nes6502_reference_v1.py` trace of 21
  executed instruction addresses is a subset of decoded instructions, executed
  control-flow set equals the model set, final state halted at `0x0202`, `a=15`, `x=1`.
- Shared-layer neutrality verified: the six shared Phase-2 modules contain no adapter,
  frontend, `nes6502`, `mips` or `6502` imports.
- Fail-closed: undocumented opcode, truncated operands, region past memory,
  entry-not-before-end, entry out of range, non-bytes memory image, and empty region
  selection all raise `NES6502BridgeError`.

## P2-21 outcome

Stage: `OPENRECOMP_P2_21_NES6502_HOST_EMITTER_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-21/RESULT.md`.
Markers: `OPENRECOMP_P2_21=PASS`, `OPENRECOMP_NES6502_HOST_EMITTER_V1=PASS tests=74`.

- New dedicated gate `tools/test_nes6502_host_emitter_v1.py` (74 checks). No existing
  `openrecomp/*.py` implementation source modified; the stage reuses the same
  architecture-neutral P2-01..P2-09 pipeline used by MIPS32.
- The P2-20 synthetic/original 15-instruction NES6502 fixture (26 bytes,
  `0a236023...`) is lowered to executable host code through adapter decode -> P2-01
  ProgramModel -> P2-02 CFG (8 blocks) -> P2-03 function discovery (`fn_8000`,
  `fn_8018`) -> P2-04 call graph (one `INTERNAL_DIRECT` edge) -> P2-05 two translation
  units -> P2-06 one `UNRESOLVED_INDIRECT_JUMP` site at `0x8012` -> P2-07 host emitter
  (`generated_source.c` `7d42947f...`) -> P2-08 generic runtime ABI (checked byte memory
  boundary) -> P2-09 deterministic build.
- Emitted register file: `a`, `c`, `ea`, `n`, `tmp`, `x`, `z` (guest A/X, C/Z/N flag
  temporaries, effective-address temp). Semantic rules are explicit per-op and cover
  the bounded fixture subset only.
- Independent Phase-1 reference cross-check: reference trace of 21 instructions; final
  reference state `a=15`, `x=1`, halted at `0x0202`. The generated native executable
  fails closed at the unresolved indirect `jmp ($0300)` with the same `a=15`, `x=1`.
- Deterministic recompilation and replay: two independent structural runs produce
  identical fingerprints and byte-identical generated source; two native executions
  produce byte-identical stdout
  (`sha256 99848de179b0b120e42eed2e4b68e6e14a2dfa950d1065ac615dd8a845d27f3c`).
- Two independent `/Brepro` builds produced byte-identical generated source, objects and
  executable (`program.exe dbba1e3a...`); classification `EXECUTABLE_REPRODUCIBLE`; no
  binary post-processing.
- Fail-closed: unresolved indirect jump emitted as `or_fail("unresolved indirect jump");
  return;`. Missing semantic rules and missing entry functions are rejected.

## P2-22 outcome

Stage: `OPENRECOMP_P2_22_NES_RUNTIME_BRIDGE_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-22/RESULT.md`.
Markers: `OPENRECOMP_P2_22=PASS`, `OPENRECOMP_NES_RUNTIME_BRIDGE_V1=PASS tests=66`.

- New module `openrecomp/frontends/nes_runtime.py`: `NESRuntimeAdapter` connects the
  generic runtime ABI to the NES CPU bus. CPU-visible memory uses `RuntimeMemory`;
  input uses `RuntimeInputSnapshot` mapped to the standard-controller protocol;
  frame/audio use declared host-call services (`nes.frame.submit`, `nes.audio.submit`).
- New dedicated gate `tools/test_nes_runtime_bridge_v1.py` (66 deterministic checks). No
  existing `openrecomp/*.py` implementation source modified; the shared layers are reused
  unchanged.
- Synthetic/original NES6502 fixture (42 bytes,
  `cc57bba3124f264cb6f4ec2b0e83cb82d3a9eeea551d18c098278c7eef827763`): the P2-21
  26-byte core region is preserved unchanged and expanded with controller-probe and
  frame/audio-trigger bytes. The fixture is generated deterministically in-tree.
- Memory contract exercised: 2 KiB RAM mirrors, PRG-ROM read and 16 KiB NROM mirror,
  PRG-RAM fail-closed when absent, disabled I/O and expansion-area fail-closed.
- Input contract exercised: generic digital channels map to NES controller bits;
  `$4016`/`$4017` serial reads return the mapped state with documented open-bus bits.
- Frame/audio contracts exercised: services read payloads from guest memory and submit
  deterministic `RuntimeFrame` / `RuntimeAudio` objects through the generic contracts.
- Host-call ABI integration exercised: service ids, numeric ids, macros and generic
  `RuntimeState.host_call` dispatch; arity mismatch fails closed.
- Shared-layer neutrality verified: the shared Phase-2 modules contain no `nes_runtime`,
  `frontends.nes_runtime`, `nes6502` or `adapters.nes6502` imports.
- Determinism: two consecutive gate runs produced byte-identical stdout
  (`sha256 4ae725be384b991c58d5e072930603b93c72c939df89c18f07749ae5c3db7b5c`).
- Relevant regressions re-run and passed: P2-01..P2-14, P2-20, P2-21, runtime ABI,
  host emitter, deterministic build, NES platform and source integrity.

## P2-23 outcome

Stage: `OPENRECOMP_NES_END_TO_END_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-23/RESULT.md`.
Markers: `OPENRECOMP_P2_23=PASS`, `OPENRECOMP_NES_END_TO_END_V1=PASS tests=50`.

- New dedicated gate `tools/test_nes_end_to_end_v1.py` (50 deterministic checks incl.
  regression re-runs and gate determinism). No existing `openrecomp/*.py` implementation
  source modified; the stage reuses the shared architecture-neutral P2-01..P2-09 pipeline.
- Synthetic/original 59-instruction NES6502 fixture (144 bytes,
  `dfadcbe759121b0705f2a7db3295127b7adceb403a6254897caee85f8a1c44c2`): the P2-21
  26-byte core region and the P2-22 controller-probe bytes are preserved; the previously
  placeholder frame/audio triggers are replaced by real host-call thunks (`svc_frame`,
  `svc_audio`) routed through the generic runtime ABI.
- Real pipeline traversal: adapter decode -> P2-01 ProgramModel -> P2-02 CFG -> P2-03
  function discovery (`fn_8000`) -> P2-04 call graph (1 node, 0 edges) -> P2-05 one
  translation unit -> P2-06 two `EXTERNAL_OR_RUNTIME_MEDIATED` service sites -> P2-07
  host emitter -> P2-08 generic runtime ABI (declared `nes.frame.submit` and
  `nes.audio.submit` services) -> P2-09 deterministic build.
- Generated source fingerprint `9819b40e9909b4056211f6f452297b502b99bc4be4f96fe797cdcdfd6aaf2b78`;
  two independent `/Brepro` builds produced byte-identical source, objects and executable
  (`EXECUTABLE_REPRODUCIBLE`); no binary post-processing.
- Independent reference: `tools/nes6502_reference_v1.py` + `NESRuntimeAdapter`, with the
  same runtime memory/input/frame/audio semantics used by the host support source. The
  reference and the native executable produced byte-identical observable output.
- Observable outputs compared: final guest A/X, controller-derived memory result,
  explicit memory cells, frame count/payload, audio count/payload, failed/error state.
- Determinism: three native executions produced byte-identical stdout
  (`sha256 c53c8ae8606b236c80d7c3fcd10d24da4f00752e15d933dcbdeb2f2882e81f82`); two
  independent full gate runs produced byte-identical stdout
  (`sha256 96dbf5965310bc17a21bfc9fdd38042d30067b1efe7eae41522033dcc2ad1540`).
- Source integrity passed: `python tools/phase1_host_gates_v1.py --only source-integrity`
  verified 128 manifest entries.
- Relevant regressions re-run and passed: P2-01..P2-14, P2-20..P2-22, runtime ABI,
  host emitter, deterministic build, NES platform and source integrity.

## P2-30 outcome

Stage: `OPENRECOMP_P2_30_CROSS_ARCHITECTURE_NEUTRALITY_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-30/RESULT.md`.
Markers: `OPENRECOMP_P2_30=PASS`, `OPENRECOMP_CROSS_ARCHITECTURE_NEUTRALITY_V1=PASS tests=14`.

- New audit gate `tools/test_cross_architecture_neutrality_v1.py` (14 deterministic checks).
  No existing `openrecomp/*.py` implementation source modified.
- Shared modules audited: `openrecomp/program_model.py`, `cfg.py`, `functions.py`,
  `call_graph.py`, `translation_units.py`, `indirect_control_flow.py`, `host_emitter.py`,
  `runtime_abi.py`, `build_pipeline.py`.
- Architecture-specific boundary modules reviewed: `openrecomp/frontends/nes6502.py`,
  `openrecomp/frontends/nes_runtime.py`.
- Static import isolation: shared modules contain no imports from `adapters.*`,
  `adapters.nes6502`, `adapters.mips32`, `openrecomp.frontends.nes6502`, or
  `openrecomp.frontends.nes_runtime`.
- Static symbol isolation: shared modules contain no prohibited NES/6502/MIPS-specific
  constants, address layouts, register names, opcode tables, or platform symbols.
- Adapter isolation: NES-specific frontends import only from shared `openrecomp.*` modules
  and their own adapter (`adapters.nes6502`); no sibling-frontend or unrelated-adapter
  dependencies.
- Non-NES path exercised: synthetic/original 8-instruction MIPS32 fixture traversed
  P2-01 -> P2-02 -> P2-03 -> P2-04 -> P2-05 -> P2-06 -> P2-07; generated host source
  SHA-256 `be52ef25060e22f8c4677c2e87a2e89180f82ae88833c4d910ec11fe1881b9f6`;
  byte-identical across two emissions; contains no NES terms.
- Determinism: two consecutive full gate runs produced byte-identical stdout
  (`sha256 49a2a255e714d17ab00d224dc3f6f218df8eb0e00d26d60ecfc71c89404abb54`).
- Source integrity passed: `python tools/phase1_host_gates_v1.py --only source-integrity`
  verified 129 manifest entries.
- Relevant regressions re-run and passed: P2-01..P2-14, P2-20..P2-23, runtime ABI,
  host emitter, deterministic build, Phase-1 host gates and source integrity.
- No corrections were required; no architecture leakage was found in shared layers.

## P2-50 outcome

Stage: `OPENRECOMP_BUILD_PACKAGE_REPRODUCIBILITY_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-50/RESULT.md`.
Markers: `OPENRECOMP_P2_50=PASS`,
`OPENRECOMP_BUILD_PACKAGE_REPRODUCIBILITY_V1=PASS tests=174`.

- New architecture-neutral packaging module `openrecomp/release_package.py` and new
  deterministic gate `tools/test_build_package_reproducibility_v1.py` (174 checks with the
  full regression run). No existing `openrecomp/*.py` implementation source or existing
  test was modified.
- Representative targets: synthetic NES/NROM end-to-end fixture (P2-23, `dfadcbe7...`),
  synthetic 4-function MIPS32/non-NES fixture (P2-14, `1c233f56...`) and the shared
  runtime/build pipeline through the P2-08 generic runtime ABI (P2-40, `9323f245...`).
- Per target: two independent clean build roots, two isolated P2-09 runs each. Generated
  source, runtime support source, normalized compile/link command lines, build manifests,
  objects and executables are byte-identical across roots/runs; classification
  `EXECUTABLE_REPRODUCIBLE`; no binary post-processing and no normalization.
- Reproduced prior-stage identities exactly: P2-40 exe `96676bec...`, P2-14 exe
  `1e81bf8c...`, P2-23 exe `5afd387d...`.
- Deterministic release packages independently assembled from each root are byte-identical
  (`generic-runtime-pipeline fa72b5d169ad...`, `mips32-larger 1c1dac0ea994...`,
  `nes-nrom-end-to-end 71847f9d7ffd...`), contain exactly the expected entries
  (`generated.c`, `runtime_support.c`, `build_manifest.json`, `program.exe`,
  `release_manifest.json`, `SHA256SUMS.txt`), use fixed archive metadata and pass the
  content/legal-asset policy with no host-path/secret findings.
- Repeated runtime observations from independently built executables are byte-identical
  and equal the declared expected observables (4 executions per target); returncode 0.
- Nondeterminism audit: COFF object `TimeDateStamp` = 0; PE `TimeDateStamp` content-derived
  by `/Brepro` and identical across roots; PE debug directory holds exactly one
  `Repro (0x10)` `/Brepro` marker (objects none); no host-path/secret needles. All three
  targets classify `BYTE_DETERMINISTIC_NO_NORMALIZATION`.
- Provenance: canonical source-state fingerprint
  `5d93971b102b24e56b2c98bf4c6b6486f58e6c174700af1c77cf969f85024c54`; recorded pipeline
  source files re-verified against the working tree at package time.
- Fail-closed packaging coverage: unsafe/absolute/hidden/reserved names, forbidden
  extensions, console-image magic, absolute/temp paths, private-key/credential content,
  duplicate/empty packages, provenance/artifact mismatches, tampered archives, extra or
  removed entries, reordered/non-canonical manifests, checksum tamper and source-state
  tamper all reject.
- Regressions re-run and passed: P2-01..P2-14, P2-20..P2-23, P2-30, P2-40, NES platform,
  Phase-1 host gates (`PASS=44 FAIL=0 SKIPPED=2`) and source integrity (131 manifest
  entries; the new gate added via `update_sums.py`, no existing entry changed).
- Determinism: two consecutive full gate runs produced byte-identical stdout+stderr
  (`sha256 0616da411e9b3b12e485b43056981e5fc269565ac932d556912ff9e82e63c92d`).

## P2-90 outcome

Stage: `OPENRECOMP_PHASE2_WHOLE_REGRESSION_AUDIT_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-90/RESULT.md`.
Markers: `OPENRECOMP_P2_90=PASS`,
`OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1=PASS tests=361 gates=22 gate_tests=1990`.

- New deterministic audit gate `tools/test_phase2_whole_regression_v1.py`: re-runs every
  applicable completed Phase-2 gate (P2-01..P2-14, P2-20..P2-23, P2-30, P2-40, P2-50,
  NES platform), the Phase-1 host gates and source integrity, and audits cross-stage
  consistency, recorded identities, recorded stdout-hash claims, frozen captures, the
  asset/legal/content policy and the claim table. No `openrecomp/*.py` implementation
  source, gate or test was modified.
- Two consecutive full audit runs produced byte-identical stdout
  (`sha256 74e9eadaf0e17ca4a97790e4239f40883cc745cd9817c172f7fa6e2663ce1ee7`, 18136 bytes)
  and empty stderr. All 22 gates passed (1990 gate checks); every recorded marker, test
  count, identity and stdout hash claim reproduced (with the recorded capture convention
  or the frozen evidence-dir prefix reconstructed for path-printing gates).
- Corrections applied before the official runs (see `P2-90/corrections_report.md`):
  stale P2-50 archive/source-state claims in STATE/HANDOFF replaced by the
  evidence-derived values; the P2-20-session P2-14 guard replacement documented with the
  current stdout hash `197a6c5e...`; the gate-block source-integrity count corrected to
  132 entries.
- Bounded evidence-hygiene limitation documented, not rewritten: nine frozen evidence
  files in P2-00/P2-07/P2-08/P2-40/P2-50 contain host-environment identifiers; no new
  occurrences are permitted and P2-90-owned artifacts are host-path-free. Sanitization is
  deferred to P2-91.
- Expected manifest-count deltas: the P2-50 re-run on the P2-90 tree reproduces every
  package/payload/executable identity byte-identically; only `changed_files.txt`,
  `input_hashes.txt` and `source_integrity.txt` differ, exactly by the P2-90 gate
  registration (131 -> 132 manifest entries).
- Phase-1 host gates `PASS=44 FAIL=0 SKIPPED=2`; source integrity verified 132 manifest
  entries. Final marker preserved: `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN`
  (reserved for P2-99).

## P2-40 outcome

Stage: `OPENRECOMP_GENERIC_RUNTIME_INTEGRATION_V1`.
Evidence: `.openrecomp-phase2/evidence/P2-40/RESULT.md`.
Markers: `OPENRECOMP_P2_40=PASS`,
`OPENRECOMP_GENERIC_RUNTIME_INTEGRATION_V1=PASS tests=181`.

- New deterministic audit gate `tools/test_generic_runtime_integration_v1.py`
  (181/181 checks with the full regression run). No `openrecomp/*.py` implementation
  source modified; no shared runtime contract changed.
- Audited generic runtime modules: `openrecomp/runtime_abi.py`, `runtime.py`,
  `module.py`, `host_emitter.py` (runtime seam), `build_pipeline.py`.
  Architecture-specific boundary modules reviewed: `openrecomp/frontends/nes_runtime.py`,
  `openrecomp/frontends/nes6502.py`, Phase-1 headless platform layers.
- Static isolation: no prohibited platform imports, identifiers/strings, service names or
  NES/GB/SMS bus-address literals; no host-state imports in `runtime_abi`/`runtime`.
  Scanner self-test detects a planted leak; clean generic source is not flagged.
- Contract classification: 21 concepts classified (13 neutral, 5 adapter, 3
  architecture/frontend, 4 host), recorded in `contract_classification.md` and
  `p2_40_tests.json`.
- Memory genericity: 16-bit space does not wrap or mirror (no NES `& 0x7FF` behavior);
  20-bit/24-bit segments are addressable without truncation; widths {8,16,32,64};
  explicit endianness; 64-bit overflow fail-closed.
- Non-NES exercise: synthetic/original 11-instruction MIPS32 fixture (`9323f245...`)
  through P2-01..P2-09; generated host C (`c0a76e0f...`) uses only the generic
  `or_rt_*` boundary; native executable (`96676bec...`) matches the independent Python
  reference observable exactly; `EXECUTABLE_REPRODUCIBLE`; three synthetic services
  (frame/audio/input) routed through the generic ABI; native unsupported-service run
  fails closed (`failed=1`, continuation not executed).
- NES path exercised through the same generic contracts (controller bits via `$4016`,
  frame/audio via generic dispatch, arity/format/mapper/PPU/expansion fail-closed);
  both adapters share `RuntimeServiceTable.dispatch` unchanged.
- GB/GBC/SMS/RT64-like extension points documented with `abi_changes_required=none`.
- Regressions re-run and passed: P2-01..P2-14, P2-20..P2-23, P2-30, runtime ABI, host
  emitter, deterministic build, NES platform, Phase-1 host gates
  (`PASS=44 FAIL=0 SKIPPED=2`) and source integrity (130 manifest entries; the new gate
  added via `update_sums.py`, no existing entry changed).
- Determinism: two full consecutive gate runs produced byte-identical stdout
  (`sha256 405c90d1c867495b3ac568a62b0d7c7e9234ca5ef469cdc2510d307b8d148228`).

## Queue reconciliation

The queue is reconciled to the executed sequence: `P2-04` = call-graph recovery
(COMPLETE), `P2-05` = translation-unit model (COMPLETE), `P2-06` =
indirect-control-flow classification (COMPLETE), `P2-07` = Host emitter V1 (COMPLETE),
`P2-08` = Generic runtime ABI V1 (COMPLETE), `P2-09` = Deterministic build pipeline
(COMPLETE), `P2-10` = Tiny MIPS32 end-to-end proof (COMPLETE), `P2-11` = MIPS32
calls/stack/memory (COMPLETE), `P2-12` = MIPS32 direct CFG stress (COMPLETE), `P2-13` =
Runtime-host boundary (COMPLETE), `P2-14` = Larger MIPS32 open fixture (COMPLETE), `P2-20` =
NES6502 program bridge (COMPLETE), `P2-21` = NES6502 host emitter path (COMPLETE), `P2-22` =
NES runtime bridge (COMPLETE), `P2-23` = NES end-to-end proof (COMPLETE), `P2-30` =
cross-architecture neutrality audit (COMPLETE), `P2-40` = generic runtime integration audit
(COMPLETE), `P2-50` = build/package reproducibility (COMPLETE), `P2-90` = whole-project
regression (COMPLETE), `P2-91` = evidence index + limitations (COMPLETE), `P2-99` =
final verdict (NEXT). The original queue numbered
`P2-04` Direct CFG recovery / `P2-05`
Indirect-control-flow classification / `P2-06` Translation-unit model; the reassignment is a
control-plane reconciliation caused by actual execution order and does not change the
semantics, claims or evidence of any frozen prior stage (`P2-00`..`P2-23`). It does not alter
`ce9cd4f`, `f9f2662`, `30b4321`, `10971b7`, `1618933`, `62044d3`, `6cb5ff4`, `aa9939a`,
`c32a766`, `2fc27bf` or any earlier commit. `P2-22`, `P2-23`, `P2-30`, `P2-40`, `P2-50`,
`P2-90` and `P2-91` started and completed in prior/this working session respectively.

## Exact next action

None — Phase 2 is complete and closed at
`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`. Any future work is a new
phase; it must not weaken the P2-99 verdict, the P2-90/P2-91 gates, the frozen
evidence or the recorded claim boundaries. Re-verification entry point:
`python tools/test_phase2_final_verdict_v1.py` (terminal verify-only mode; use
`--run-regression` to also re-execute the whole-project P2-90 audit).

## Verification commands / results

```text
python tools/test_phase2_evidence_closure_v1.py
OPENRECOMP_P2_91=PASS
OPENRECOMP_PHASE2_EVIDENCE_CLOSURE_V1=PASS tests=882
(two consecutive full gate runs byte-identical; hashes and captures in gate_determinism.txt, p2_91_run1.txt, p2_91_run2.txt)
(evidence index complete for all 23 stages; every indexed identity and reference re-verified)
(limitations record and claim matrix share the 23-key vocabulary; final marker not claimed)
(nine frozen host-path occurrences classified and hash-pinned; no new absolute host path; release packages clean)
(P2-90 regression capture validated: OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1=PASS tests=361 gates=22 gate_tests=1990)
(source integrity PASS, 133 manifest entries, additive manifest delta only)
(OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN preserved; reserved for P2-99)

python tools/test_phase2_evidence_closure_v1.py --run-regression
(executes the P2-90 whole-project audit after all P2-91 changes; official run ~5315 s, exit 0, tests=884; captures p2_90_rerun.txt and p2_90_rerun/)
(OPENRECOMP_P2_90=PASS; 361 audit checks, 22 gates, 1990 gate checks, 0 failures, empty stderr)
(rerun stdout content identical to the frozen P2-90 capture 74e9eada...; LF content sha256 00675593...)
(six frozen P2-90 capture files snapshotted, regenerated, captured and restored byte-identically; only manifest-count delta 132 -> 133)
(one development execution before the check correction is retained as p2_91_regression_run_development_fail.txt; nested P2-90 audit passed there too)

python tools/test_build_package_reproducibility_v1.py --evidence-dir .openrecomp-phase2/evidence/P2-50
OPENRECOMP_P2_50=PASS
OPENRECOMP_BUILD_PACKAGE_REPRODUCIBILITY_V1=PASS tests=174
(two consecutive full gate runs byte-identical; stdout+stderr sha256 0616da411e9b3b12e485b43056981e5fc269565ac932d556912ff9e82e63c92d)
(two independent clean build roots x two isolated runs per representative: source/manifest/object/executable byte-identical)
(generic-runtime-pipeline exe 96676bec... archive fa72b5d169ad...; mips32-larger exe 1e81bf8c... archive 1c1dac0ea994...; nes-nrom-end-to-end exe 5afd387d... archive 71847f9d7ffd...)
(all EXECUTABLE_REPRODUCIBLE; nondeterminism classification BYTE_DETERMINISTIC_NO_NORMALIZATION; no post-processing)
(repeated native observations byte-identical and equal to the declared expected observables; returncodes 0)
(package content policy clean; no console-image magics, host paths, temp paths, keys or credentials; source-state fingerprint 5d93971b...)
(P2-01..P2-14, P2-20..P2-23, P2-30, P2-40, NES platform, Phase-1 host gates PASS=44 FAIL=0 SKIPPED=2, source integrity 131 entries)

python tools/test_phase2_whole_regression_v1.py
OPENRECOMP_P2_90=PASS
OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1=PASS tests=361 gates=22 gate_tests=1990
(two consecutive full audit runs byte-identical; stdout sha256 74e9eadaf0e17ca4a97790e4239f40883cc745cd9817c172f7fa6e2663ce1ee7; stderr empty)
(all 22 gates pass with recorded markers/test counts; frozen captures reproduce with the documented one-line guard deltas)
(all recorded fixture/source/object/executable/package identities and stdout-hash claims reproduce)
(phase-1 host gates PASS=44 FAIL=0 SKIPPED=2; source integrity verified 132 manifest entries; P2-90 gate registered via update_sums.py)
(legal/asset policy clean for tracked tree, P2-90 artifacts and release packages; nine frozen earlier-stage host-path occurrences documented)
(OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN preserved; reserved for P2-99)

python tools/test_generic_runtime_integration_v1.py --evidence-dir .openrecomp-phase2/evidence/P2-40 --json .openrecomp-phase2/evidence/P2-40/p2_40_tests.json
OPENRECOMP_P2_40=PASS
OPENRECOMP_GENERIC_RUNTIME_INTEGRATION_V1=PASS tests=181
(byte-identical across two full gate runs; stdout sha256 405c90d1c867495b3ac568a62b0d7c7e9234ca5ef469cdc2510d307b8d148228)
(static isolation empty; scanner self-test detects a planted NES/6502 leak)
(synthetic 11-instruction MIPS32 fixture 9323f245... -> generated source c0a76e0f... -> program.exe 96676bec...)
(non-NES runtime exercise: synthetic.frame.submit / synthetic.audio.submit / synthetic.input.poll through the generic ABI)
(native observable == independent Python reference observable; EXECUTABLE_REPRODUCIBLE; unsupported service fails closed)
(NES path exercised through the same generic contracts; GB/GBC/SMS/RT64-like extension points documented, abi_changes_required=none)
(P2-01..P2-14, P2-20..P2-23, P2-30, runtime ABI, host emitter, deterministic build, NES platform, Phase-1 host gates PASS=44 FAIL=0 SKIPPED=2)
(source integrity verified 130 manifest entries after update_sums.py added the new gate)

python tools/test_cross_architecture_neutrality_v1.py --evidence-dir .openrecomp-phase2/evidence/P2-30 --json .openrecomp-phase2/evidence/P2-30/p2_30_tests.json
OPENRECOMP_P2_30=PASS
OPENRECOMP_CROSS_ARCHITECTURE_NEUTRALITY_V1=PASS tests=14
(byte-identical across two full gate runs; stdout sha256 49a2a255e714d17ab00d224dc3f6f218df8eb0e00d26d60ecfc71c89404abb54)
(shared modules contain no architecture-specific imports or symbols)
(MIPS32 path exercised through P2-01..P2-07; host source sha256 be52ef25...)
(P2-01..P2-14 and P2-20..P2-23 regressions passed; source integrity verified 129 entries)

python tools/test_nes_end_to_end_v1.py --evidence-dir .openrecomp-phase2/evidence/P2-23 --json .openrecomp-phase2/evidence/P2-23/p2_23_tests.json
OPENRECOMP_NES_END_TO_END_V1=PASS tests=50
(byte-identical across two full gate runs; stdout sha256 96dbf5965310bc17a21bfc9fdd38042d30067b1efe7eae41522033dcc2ad1540)
(fixture dfadcbe7... -> generated source 9819b40e... -> program.exe 5afd387d...)
(native observable == independent reference observable; failed=0 error=; a=64 x=1; input_result=0x41)
(frame_payload=ff0000ff00ff00ff0000ffffffffff00 audio_payload=10203040)
(three native executions byte-identical; EXECUTABLE_REPRODUCIBLE)

python tools/test_nes_runtime_bridge_v1.py --evidence-dir .openrecomp-phase2/evidence/P2-22 --json .openrecomp-phase2/evidence/P2-22/p2_22_tests.json
OPENRECOMP_NES_RUNTIME_BRIDGE_V1=PASS tests=66
(byte-identical across two runs; stdout sha256 4ae725be384b991c58d5e072930603b93c72c939df89c18f07749ae5c3db7b5c)
(fixture cc57bba3... -> 42 bytes; P2-21 26-byte core preserved; expanded for controller/frame/audio)
(memory/input/frame/audio contracts exercised through the generic runtime ABI)
(shared-layer neutrality verified; no NES assumptions leaked into openrecomp/*.py shared modules)

python tools/test_nes6502_host_emitter_v1.py --evidence-dir .openrecomp-phase2/evidence/P2-21 --json .openrecomp-phase2/evidence/P2-21/p2_21_tests.json
OPENRECOMP_NES6502_HOST_EMITTER_V1=PASS tests=74
(byte-identical across two runs; stdout sha256 e66406e043b9dab859f5cf56ea537f333be7b59619e8c7bbb06bad4fd45f57e4)
(fixture 0a236023... -> generated source 7d42947f... -> program.exe dbba1e3a...)
(native observable failed=1 error=unresolved indirect jump; a=15 x=1; ram_checksum=1430085296)
(independent Phase-1 reference cross-check: halted 0x0202, a=15, x=1)
(two native executions byte-identical; EXECUTABLE_REPRODUCIBLE)

python tools/test_nes6502_program_bridge_v1.py --evidence-dir .openrecomp-phase2/evidence/P2-20 --json .openrecomp-phase2/evidence/P2-20/p2_20_tests.json
OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1=PASS tests=86
(byte-identical across two runs; stdout sha256 d104147c5bbc176af44499aed94320e095350f8e9e7f6fafbab8667d33025f03)
(region 0a236023... -> 15 instructions, 8 cfg blocks, 2 functions, 2 units, 1 unresolved indirect site)
(independent Phase-1 reference trace == model control-flow set; halted 0x0202, a=15, x=1)
(no host emission; no build pipeline; structural bridge only)

python tools/test_nes_platform_v1.py
OPENRECOMP_NES_PLATFORM_V1=PASS tests=10

python tools/test_mips32_calls_memory_v1.py
OPENRECOMP_MIPS32_CALLS_MEMORY_V1=PASS tests=77
(byte-identical across two runs; current stdout sha256 35e92fa780eb842ee060edd747fd33d3e919699e7a753ccf864d88fb157e9b81)
(committed P2-11 evidence recorded the pre-adjustment hash c0b39d65...; see P2-12 RESULT.md)
(fixture 4ce3fdab... -> generated source 4637ba67... -> program.exe bd719060...)
(independent expected observable == native actual observable; EXECUTABLE_REPRODUCIBLE)
(runtime OOB memory access fails closed: failed=1)

python tools/test_mips32_end_to_end_v1.py
OPENRECOMP_MIPS32_END_TO_END_V1=PASS tests=108
(byte-identical across two runs; stdout sha256 347da29f2a3ede17719ea3c10f8fcf7ac1dd5a0c1bb849eace0b12f19fe0d8aa)
(committed P2-10 evidence recorded the pre-adjustment hash 5327f11c...; see P2-11 RESULT.md)

python tools/test_mips32_direct_cfg_v1.py
OPENRECOMP_MIPS32_DIRECT_CFG_V1=PASS tests=96
(byte-identical across two runs; current stdout sha256 6f19a2742dd8a2ff8688b8712585fa5e2657ed1dd9f9050f510c0d2dde7d0ee9)
(committed P2-12 evidence recorded the pre-adjustment hash d01ec8f0...; see P2-13 RESULT.md)
(fixture 2e3309f3... -> generated source 36ba17c8... -> program.exe 3d92fc27...)
(loop acc=15; bounded switch case A -> r6=120, r7=125; EXECUTABLE_REPRODUCIBLE)
(out-of-set selector hits switch default: failed=1)

python tools/test_runtime_host_boundary_v1.py
OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1=PASS tests=80
(byte-identical across two runs; current stdout sha256 cf94b655d95dba72840823a9212b0d022d577bf7c73f9fe58fc8e864e464597f)
(committed P2-13 evidence recorded the pre-adjustment hash 8617ed85...; see P2-14 RESULT.md)
(fixture 7c9ba624... -> generated source 8c602b35... -> program.exe 8ab94ab0...)
(guest r4=42 -> service demo.double -> r4=84, continuation r5=92; EXECUTABLE_REPRODUCIBLE)
(unsupported service fails closed natively: failed=1)

python tools/test_mips32_larger_fixture_v1.py
OPENRECOMP_MIPS32_LARGER_FIXTURE_V1=PASS tests=82
(byte-identical across two runs; stdout sha256 115c2c8a69ed3a9ebb33e990ffa9350a970e8c6f2ea258a40187365baaf6d3e9)
(fixture 1c233f56... -> generated source 25d8d85f... -> program.exe 1e81bf8c...)
(deterministic recompilation: identical fingerprints + byte-identical source)
(deterministic replay: 3 runs, stdout sha256 5a44a08c...; observable 941; EXECUTABLE_REPRODUCIBLE)

python tools/test_build_pipeline_v1.py
OPENRECOMP_DETERMINISTIC_BUILD_V1=PASS tests=120
(byte-identical across two runs; stdout sha256 db055b5cd622a7ef188901ef8da65898e2dac0cacb03c0ee2fb6caeec5b3e273)
(two independent clang-cl/lld-link /Brepro builds: source/object/executable hashes identical)
(classification EXECUTABLE_REPRODUCIBLE; smoke test observed "42 0" returncode 0)
(native optional compile+run: clang-cl, observed "42 0", expected "42 0")

python tools/test_runtime_abi_v1.py
OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests=169

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

python tools/phase1_host_gates_v1.py --json .openrecomp-phase2/evidence/P2-40/host_gates.json
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
(full Phase-1 host-gate run; toolchain-gated gates skipped, never counted as passes)

python tools/phase1_host_gates_v1.py --only source-integrity
PASS source-integrity  verified 130 manifest entries
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

## Evidence artifacts (UTF-8 text, no BOM)

`.openrecomp-phase2/evidence/P2-91/`: `RESULT.md`, `RESULT.json`,
`PHASE2_EVIDENCE_INDEX.md`, `PHASE2_EVIDENCE_INDEX.json`, `PHASE2_LIMITATIONS.md`,
`PHASE2_CLAIM_MATRIX.md`, `host_path_audit.md`, `host_path_occurrences.json`,
`portable_derivatives/` (`README.md`, `P2-07_native_compile.portable.txt`,
`P2-08_determinism.portable.txt`), `p2_90_rerun.txt`, `p2_90_rerun/` (nested P2-90 evidence
plus `frozen_phase1_host_gates_stdout.txt`, `frozen_source_integrity_stdout.txt`),
`p2_90_rerun.json`, `p2_90_capture_preservation.json`, `p2_90_capture_preservation.txt`,
`p2_91_tests.json`, `legal_policy_audit.json`, `source_integrity.txt`, `changed_files.txt`,
`gate_determinism.txt`, `p2_91_run1.txt`, `p2_91_run2.txt`, `p2_91_regression_run.txt`,
`p2_91_regression_run.err`.

`.openrecomp-phase2/evidence/P2-50/`: `RESULT.md`, `RESULT.json`, `p2_50_tests.json`,
`clean_build_description.txt`, `toolchain_identity.txt`, `input_hashes.txt`,
`source_state.txt`, `generated_source_hashes.txt`, `compiler_command_lines.txt`,
`build_manifest_comparison.txt`, `build_manifest_<rep>.json`, `object_hashes.txt`,
`executable_hashes.txt`, `reproducibility_comparison.txt`, `nondeterminism_analysis.txt`,
`runtime_equivalence.txt`, `package_hashes.txt`, `package_contents.txt`,
`release_manifest_<rep>.json`, `package_<rep>.zip`, `recorded_artifact_hashes.json`,
`changed_files.txt`, `source_integrity.txt`, `host_gates.json`, `regression_results.json`,
`gate_determinism.txt`, `p2_50_run1.txt`, `p2_50_run2.txt`, and regression captures for the
21 re-run gates. (`<rep>` is one of `generic-runtime-pipeline`, `mips32-larger`,
`nes-nrom-end-to-end`.)

`.openrecomp-phase2/evidence/P2-40/`: `RESULT.md`, `RESULT.json`,
`contract_classification.md`, `responsibility_analysis.md`,
`dependency_findings.txt`, `determinism.txt`, `changed_files.txt`, `fixture.txt`,
`pipeline_cfg.txt`, `pipeline_functions.txt`, `pipeline_translation_units.txt`,
`pipeline_indirect_control_flow.txt`, `generated_source.c`,
`generated_source_sha256.txt`, `runtime_abi_contract.txt`, `static_isolation.json`,
`build_manifest.json`, `build_run_1.txt`, `build_run_2.txt`, `native_execution.txt`,
`expected_vs_actual.txt`, `unsupported_service.txt`, `nes_path_exercise.txt`,
`regression_results.json`, `source_integrity.txt`, `host_gates.json`,
`p2_40_tests.json`, `run1.txt`, `run2.txt`.

`.openrecomp-phase2/evidence/P2-30/`: `RESULT.md`, `RESULT.json`, `changed_files.txt`,
`p2_30_tests.json`, `run1.txt`, `run2.txt`.

`.openrecomp-phase2/evidence/P2-14/`: `RESULT.md`, `RESULT.json`, `determinism.txt`,
`changed_files.txt`, `fixture.txt`, `pipeline_cfg.txt`, `pipeline_functions.txt`,
`pipeline_call_graph.txt`, `pipeline_translation_units.txt`,
`pipeline_indirect_control_flow.txt`, `generated_source.c`, `generated_source_sha256.txt`,
`build_manifest.json`, `build_run_1.txt`, `build_run_2.txt`, `native_execution.txt`,
`expected_vs_actual.txt`, `recompilation.txt`, `replay.txt`, `p2_14_gate.txt`,
`p2_14_tests.json`, `host_gates.json`, `host_gates.txt`, `source_integrity.txt`, and
regression captures `p2_13_runtime_host_boundary.txt`, `p2_12_mips32_direct_cfg.txt`,
`p2_11_mips32_calls_memory.txt`, `p2_10_mips32_end_to_end.txt`,
`p2_09_deterministic_build.txt`, `p2_08_runtime_abi.txt`, `p2_07_host_emitter.txt`,
`p2_06_indirect_control_flow.txt`, `p2_05_translation_units.txt`, `p2_04_call_graph.txt`,
`p2_03_functions.txt`, `p2_02_cfg.txt`, `p2_01_program_model.txt`.

`.openrecomp-phase2/evidence/P2-22/`: `RESULT.md`, `RESULT.json`, `changed_files.txt`,
`fixture.txt`, `adapter.txt`, `frame_submission.txt`, `audio_submission.txt`,
`input_mapping.txt`, `gate_determinism.txt`, `p2_22_run1.txt`, `p2_22_run2.txt`,
`p2_22_tests.json`, `source_integrity.txt`, and regression captures for
P2-01..P2-14, P2-20, P2-21, NES platform and source integrity.

`.openrecomp-phase2/evidence/P2-21/`: `RESULT.md`, `RESULT.json`, `fixture.txt`,
`bridge_summary.txt`, `pipeline_cfg.txt`, `pipeline_functions.txt`,
`pipeline_call_graph.txt`, `pipeline_translation_units.txt`,
`pipeline_indirect_control_flow.txt`, `generated_source.c`,
`generated_source_sha256.txt`, `build_manifest.json`, `build_run_1.txt`,
`build_run_2.txt`, `native_execution.txt`, `expected_vs_actual.txt`,
`reference_comparison.txt`, `determinism.txt`, `gate_determinism.txt`,
`p2_21_gate.txt`, `p2_21_tests.json`, `host_gates.json`, `source_integrity.txt`, and
regression captures `p2_20_nes6502_program_bridge.txt`,
`p2_14_mips32_larger_fixture.txt`, `p2_13_runtime_host_boundary.txt`,
`p2_12_mips32_direct_cfg.txt`, `p2_11_mips32_calls_memory.txt`,
`p2_10_mips32_end_to_end.txt`, `p2_09_deterministic_build.txt`,
`p2_08_runtime_abi.txt`, `p2_07_host_emitter.txt`, `p2_06_indirect_control_flow.txt`,
`p2_05_translation_units.txt`, `p2_04_call_graph.txt`, `p2_03_functions.txt`,
`p2_02_cfg.txt`, `p2_01_program_model.txt`.

`.openrecomp-phase2/evidence/P2-20/`: `RESULT.md`, `fixture.txt`, `bridge_summary.txt`,
`pipeline_cfg.txt`, `pipeline_functions.txt`, `pipeline_call_graph.txt`,
`pipeline_translation_units.txt`, `pipeline_indirect_control_flow.txt`,
`p2_20_gate.txt`, `p2_20_tests.json`, `source_integrity.txt`, and regression captures
`p2_14_mips32_larger_fixture.txt`, `p2_13_runtime_host_boundary.txt`,
`p2_12_mips32_direct_cfg.txt`, `p2_11_mips32_calls_memory.txt`,
`p2_10_mips32_end_to_end.txt`, `p2_09_deterministic_build.txt`,
`p2_08_runtime_abi.txt`, `p2_07_host_emitter.txt`, `p2_06_indirect_control_flow.txt`,
`p2_05_translation_units.txt`, `p2_04_call_graph.txt`, `p2_03_functions.txt`,
`p2_02_cfg.txt`, `p2_01_program_model.txt`.

## Unresolved evidence / limitations

- P2-90 proves only that the completed Phase-2 stages still pass together and that their
  cross-stage evidence is internally consistent on the audited tree. It does not upgrade
  any bounded stage claim (synthetic fixtures only; no general NES/MIPS32/console
  compatibility). The claim classification table is
  `.openrecomp-phase2/evidence/P2-90/claim_classification.md`.
- Nine frozen evidence files in P2-00/P2-07/P2-08/P2-40/P2-50 contain absolute
  host-environment identifiers (working-copy/compiler/interpreter paths). They are
  enumerated in `.openrecomp-phase2/evidence/P2-90/corrections_report.md`; no new
  occurrence is permitted by the P2-90 gate, and sanitization is deferred to P2-91 because
  these files are pinned by hash-recorded PASS evidence.
- P2-40's stdout embeds the evidence-dir path it passes to the nested Phase-1 host-gates
  invocation, so reproducing its recorded stdout hash requires reconstructing the frozen
  evidence-dir prefix; P2-30/P2-50 recorded stdout hashes use a UTF-16LE-BOM CRLF
  redirection convention. The P2-90 audit verifies the recorded conventions explicitly.
- The P2-50 gate's `changed_files.txt`, `input_hashes.txt` and `source_integrity.txt` are
  manifest-count dependent; on the P2-90 tree they differ from the frozen P2-50 recordings
  exactly by the P2-90 gate registration (131 -> 132 entries). All package/payload/
  executable identities still reproduce byte-identically.
- `RuntimeState` is a deterministic contract surface for fixtures, not a guest execution
  engine; it does not execute generated host code.
- The generated C contains only boundary declarations (`extern or_rt_*`); no runtime
  implementation is generated. P2-13 supplies a fixture runtime-support implementation for
  the declared service; platform runtime integration is later work.
- P2-11 adds opt-in `HostLoad`/`HostStore` through the runtime ABI; only word-width aligned
  `lw`/`sw` are covered. Delay slots, calling conventions and most runtime services remain
  outside the emitted set, and emitted functions are void with no argument/return ABI.
- A finite resolved target set requires a runtime target value; it is dispatched with a
  `switch` that fails closed outside the proven set. Bounded dispatch target sets and
  runtime service identities are supplied by explicit evidence; the pipeline never recovers
  or guesses them by analysis.
- The P2-09 build pipeline builds bounded synthetic generated host fixtures plus synthetic
  runtime-support sources; they are not whole-guest recompilations.
- Object/executable reproducibility is demonstrated for this host's clang-cl/lld-link pair.
  Other toolchains may require different deterministic flags and are classified honestly.
- P2-10..P2-14 prove only bounded synthetic MIPS32 fixtures (13, 16, 35, 5 and 57
  instructions); not full MIPS32 support, not PS2 support and not guest/host equivalence.
  The neutral CFG/emitter do not model delay slots as first-class semantics; fixtures use
  `nop` delay slots and unreachable delay-slot blocks are preserved as unowned residual
  evidence. Call/return is modeled structurally; the fixtures' o32 `$ra` save/restore makes
  that agree with true MIPS32 for those cases, but general `$ra` dataflow is not recovered,
  and saved-`$ra` RAM bytes may differ (so no RAM checksum is part of the observable).
- P2-20 proves only the structural program bridge for a bounded synthetic NES6502 region
  (15 instructions, 26 bytes). It does not generate host code, execute translated code, or
  claim NES equivalence, compatibility, or whole-guest recompilation. The indirect
  `jmp ($0300)` site is `UNRESOLVED_INDIRECT_JUMP`; the runtime target is never guessed.
- P2-21 proves only that the same bounded synthetic NES6502 fixture can be lowered into an
  executable host program through the shared Phase-2 pipeline. The emitted subset covers
  only the operations exercised by the fixture; the 6502 stack effects of `jsr`/`rts` are
  not modeled (structural call/return emits native C function calls). Memory accesses are
  byte-wide but emitted through the generic runtime ABI using the configured 16-bit word
  width; the fixture runtime support interprets the ABI call as a byte access. This is a
  documented fixture simplification, not a claim about general NES memory mapping.
- P2-22 proves only the runtime-bridge infrastructure for a bounded synthetic NROM fixture.
  It connects memory, input, frame and audio contracts to the NES platform adapter but does
  not implement a full PPU/APU, does not run generated host code and does not claim
  commercial-ROM or whole-game compatibility. PPU register accesses, expansion areas,
  disabled I/O and unsupported mappers fail closed.
- P2-23 proves only end-to-end equivalence for the bounded synthetic NES/NROM fixture
  described above. It is not a general NES6502 recompiler, does not support commercial ROMs,
  does not implement a full PPU/APU, and does not claim whole-guest or whole-game
  equivalence. Mapper 0 (NROM) only; unsupported mappers, disabled I/O, expansion areas and
  PPU/APU register access fail closed.
- `tools/test_mips32_end_to_end_v1.py` (P2-10), `tools/test_mips32_calls_memory_v1.py`
  (P2-11), `tools/test_mips32_direct_cfg_v1.py` (P2-12) and
  `tools/test_runtime_host_boundary_v1.py` (P2-13) were each adjusted for one obsolete
  cross-stage guard; their committed evidence records the pre-adjustment stdout hashes. See
  the P2-11/P2-12/P2-13/P2-14 `RESULT.md`.
- `schema/*.json` / `openrecomp/*.py` (including `runtime_abi.py`, `build_pipeline.py` and
  `host_emitter.py`) remain outside `SOURCE_SHA256SUMS.txt` (pre-existing `update_sums.py`
  `schemas/` glob gap); their hashes are recorded in `changed_files.txt` / `RESULT.json`.
- P2-30 proves only that the audited shared Phase-2 layers (`openrecomp/program_model.py`,
  `cfg.py`, `functions.py`, `call_graph.py`, `translation_units.py`,
  `indirect_control_flow.py`, `host_emitter.py`, `runtime_abi.py`, `build_pipeline.py`)
  contain no unjustified NES6502/MIPS32/platform-specific leakage for the audited paths. It
  does not prove that every future architecture can be integrated without new generic
  abstractions, nor does it prove arbitrary NES, MIPS32, PS2, Xbox, or commercial-game
  compatibility.
- P2-40 proves only that the audited generic runtime contracts
  (`openrecomp/runtime_abi.py`, `runtime.py`, `module.py`, the `host_emitter.py` runtime
  seam and `build_pipeline.py`) are architecture-neutral for the supported Phase-2 paths.
  It does not prove complete generic console emulation, arbitrary future-architecture
  compatibility, complete NES PPU/APU behavior, arbitrary commercial-game runtime
  compatibility, cycle accuracy or full hardware emulation.
- P2-40's non-NES native exercise covers exactly one bounded synthetic 11-instruction
  MIPS32 fixture, its three fixture-declared services and a gate-local synthetic platform
  adapter. GB/GBC/SMS support is documented as extension points only (no adapter
  implemented), and RT64-like backends remain optional later host-side work.
- P2-40 found no generic-runtime leakage, so no shared runtime code changed. The new audit
  gate was added to `SOURCE_SHA256SUMS.txt` via `update_sums.py` (129 -> 130 entries); no
  existing manifest entry changed.
- P2-50 adds `openrecomp/release_package.py` (new architecture-neutral module, outside the
  `SOURCE_SHA256SUMS.txt` glob set like the other `openrecomp/*.py` modules) and
  `tools/test_build_package_reproducibility_v1.py` (added via `update_sums.py`, 130 -> 131
  entries; no existing entry changed).
- P2-50 proves reproducibility only for the three audited representative fixtures, the
  detected `clang-cl` 22.1.8 / `lld-link` 22.1.8 toolchain on this host and the audited
  canonical ZIP packaging path. Other compilers, operating systems, architectures or
  toolchain versions may require different deterministic flags and are not claimed.
- P2-50 "clean build" means fresh isolated build roots with regenerated sources and no
  artifact reuse; no fresh git checkout is created because the Phase-2 control policy
  forbids parallel worktrees. Package provenance records a canonical source-state list
  (repo-relative file + SHA-256) re-verified against the working tree, and the tracked
  pipeline tools/adapters are covered by `SOURCE_SHA256SUMS.txt`.
- P2-50 found no binary nondeterminism: COFF `TimeDateStamp` is 0, the PE
  `TimeDateStamp` is content-derived by `/Brepro`, the PE debug directory holds exactly one
  `Repro (0x10)` marker, and no host-path/secret needles appear in objects or executables.
  No normalization or binary post-processing was applied or needed.
- P2-50 packaging is bounded to generated source, runtime support source, build manifest
  and host executable payloads plus the release manifest and checksums file; it packages no
  objects, caches or console assets, and no commercial material is involved.
- Toolchain-gated gates `e07-hardened-end-to-end` and `external-repro-v1` require
  `clang`/`gcc`/POSIX and remain skipped; never counted as pass.

## Non-claims

No full MIPS32 recompilation, full NES6502 recompilation, IR lowering, guest/host
equivalence, console-specific runtime, BIOS/HLE, GPU/APU/DSP, controller backend, audio
device, window, AOT integration, whole-game recompilation, console compatibility or RT64
integration. The generic runtime ABI is a contract surface only. The deterministic build
pipeline and the P2-10..P2-14 end-to-end proofs were validated on bounded synthetic fixtures,
not on a commercial guest. P2-20 was completed but proves only the structural program bridge
for a bounded synthetic NES6502 region; it does not generate host code or execute translated
code. P2-21 proves only that the same bounded synthetic NES6502 fixture can be lowered to an
executable host program; it is not full NES6502 recompilation, not NES equivalence and not
whole-guest recompilation. P2-22 proves only the runtime-bridge infrastructure for a bounded
synthetic NROM fixture: memory, input, frame and audio contracts are connected through the
generic runtime ABI, but no full PPU/APU emulation, no commercial-game compatibility and no
whole-guest equivalence is claimed. P2-23 proves only end-to-end equivalence for the
bounded synthetic NES/NROM fixture described above; it is not a general NES6502 recompiler,
does not support commercial ROMs, does not implement a full PPU/APU, and does not claim
whole-guest or whole-game equivalence. P2-30 proves only architecture-neutrality of the
audited shared Phase-2 layers for the supported MIPS32 and NES6502 paths; it does not prove
universal future-architecture integrability or arbitrary commercial compatibility. P2-40
proves only that the audited generic runtime contracts are architecture-neutral for the
supported Phase-2 paths; it does not prove complete generic console emulation, arbitrary
future-architecture compatibility, complete NES PPU/APU behavior, arbitrary commercial-game
runtime compatibility, cycle accuracy or full hardware emulation. P2-50 proves only
byte-level build/package reproducibility for the three audited synthetic representative
fixtures, the detected host toolchain and the audited packaging path; it does not prove
reproducibility across other compilers, operating systems, architectures or future
toolchains, and it does not prove arbitrary game compatibility. The final
`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` marker is issued by the P2-99
terminal verdict only for the bounded claim recorded in
`.openrecomp-phase2/evidence/P2-99/final_claim_boundary.md`; it does not imply
arbitrary NES ROM compatibility, arbitrary MIPS32 executable compatibility,
commercial-game compatibility, complete NES hardware emulation, cycle accuracy,
PS1/PS2/Xbox compatibility, universal-console support or arbitrary
future-architecture compatibility.

## Git status (short)

- P2-14 boundary commit: `2fc27bf` (`phase2: complete P2-14 larger MIPS32 open fixture`);
  `HEAD` at P2-20 start.
- Current uncommitted changes: the P2-90 audit gate + evidence
  (`tools/test_phase2_whole_regression_v1.py`, `.openrecomp-phase2/evidence/P2-90/`),
  control-plane corrections/updates to `.openrecomp-phase2/STATE.md`,
  `.openrecomp-phase2/HANDOFF.md`, `.openrecomp-phase2/STAGE_QUEUE.md`, plus the earlier
  P2-50 packaging module + gate + evidence
  (`openrecomp/release_package.py`, `tools/test_build_package_reproducibility_v1.py`,
  `.openrecomp-phase2/evidence/P2-50/`), P2-40 generic runtime integration audit gate +
  evidence (`tools/test_generic_runtime_integration_v1.py`,
  `.openrecomp-phase2/evidence/P2-40/`), the P2-30 cross-architecture neutrality audit
  gate + evidence (`tools/test_cross_architecture_neutrality_v1.py`,
  `.openrecomp-phase2/evidence/P2-30/`), the P2-23 NES end-to-end gate + evidence
  (`tools/test_nes_end_to_end_v1.py`, `.openrecomp-phase2/evidence/P2-23/`), the P2-22
  NES runtime-bridge adapter + gate + evidence (`openrecomp/frontends/nes_runtime.py`,
  `tools/test_nes_runtime_bridge_v1.py`, `.openrecomp-phase2/evidence/P2-22/`), the prior
  P2-21 NES6502 host-emitter gate + evidence (`tools/test_nes6502_host_emitter_v1.py`,
  `.openrecomp-phase2/evidence/P2-21/`), the P2-20 bridge + gate + evidence
  (`openrecomp/frontends/nes6502.py`, `tools/test_nes6502_program_bridge_v1.py`,
  `.openrecomp-phase2/evidence/P2-20/`), plus the prior P2-14 uncommitted changes
  (`tools/test_mips32_larger_fixture_v1.py`, `.openrecomp-phase2/evidence/P2-14/`,
  updated `tools/test_runtime_host_boundary_v1.py`, `SOURCE_SHA256SUMS.txt`).
- Untouched pre-existing untracked residue: `.openrecomp-phase2/backups/`,
  `.openrecomp-phase2/scratch/` (now also holding the P2-90 raw gate captures under
  `scratch/P2-90/regressions/`), `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No P2-20, P2-21, P2-22, P2-23, P2-30, P2-40, P2-50 or P2-90 boundary commit created
  (left for independent review).

Resume by reading `CONTROL_POLICY.md`, `SCOPE.md`, `STAGE_QUEUE.md`, `STATE.md`,
`HANDOFF.md`, and `EVIDENCE_SCHEMA.md`, then work only on `CURRENT_STAGE`.

OPENRECOMP_P2_50=PASS
OPENRECOMP_BUILD_PACKAGE_REPRODUCIBILITY_V1=PASS tests=174
OPENRECOMP_P2_40=PASS
OPENRECOMP_GENERIC_RUNTIME_INTEGRATION_V1=PASS tests=181
OPENRECOMP_P2_30=PASS
OPENRECOMP_CROSS_ARCHITECTURE_NEUTRALITY_V1=PASS tests=14
OPENRECOMP_P2_23=PASS
OPENRECOMP_NES_END_TO_END_V1=PASS tests=50
OPENRECOMP_P2_22=PASS
OPENRECOMP_NES_RUNTIME_BRIDGE_V1=PASS tests=66
OPENRECOMP_P2_21=PASS
OPENRECOMP_NES6502_HOST_EMITTER_V1=PASS tests=74
OPENRECOMP_P2_20=PASS
OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1=PASS tests=86
OPENRECOMP_P2_90=PASS
OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1=PASS tests=361 gates=22 gate_tests=1990
OPENRECOMP_P2_91=PASS
OPENRECOMP_PHASE2_EVIDENCE_CLOSURE_V1=PASS tests=882
OPENRECOMP_P2_99=PASS
OPENRECOMP_PHASE2_FINAL_VERDICT_V1=PASS
OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS
CURRENT_STAGE=P2-99
LAST_PASSED_STAGE=P2-99
