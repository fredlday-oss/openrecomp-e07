# OpenRecomp Phase 2 State

PHASE=2
BASELINE_TAG=openrecomp-phase1-pass
BASELINE_COMMIT=46c2f97
CURRENT_STAGE=P2-11
LAST_PASSED_STAGE=P2-10
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
| P2-08 | Generic runtime ABI V1 | `PASS` | `.openrecomp-phase2/evidence/P2-08/RESULT.md` |
| P2-09 | Deterministic build pipeline | `PASS` | `.openrecomp-phase2/evidence/P2-09/RESULT.md` |
| P2-10 | Tiny MIPS32 end-to-end proof | `PASS` | `.openrecomp-phase2/evidence/P2-10/RESULT.md` |
| P2-11 | MIPS32 calls/stack/memory | `NEXT` | not started |

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

## P2-08 result (PASS)

Stage: `OPENRECOMP_P2_08_GENERIC_RUNTIME_ABI_V1`.
Starting commit: `30b4321011b963efce19b321c72b97f886ba2b3d` (P2-07 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Module `openrecomp/runtime_abi.py`: first architecture-neutral generic runtime ABI V1
  (`RuntimeAbiVersion`, `RuntimeMemory`, `RuntimeService`/`RuntimeServiceTable`,
  `RuntimeHostCallRequest`/`RuntimeHostCallRecord`, `RuntimeInputSnapshot`, `RuntimeFrame`,
  `RuntimeAudio`, `RuntimeFailure`/`RuntimeFailureCode`/`RuntimeResult`,
  `RuntimeConfig`/`RuntimeAbiConfig`, `RuntimeState`, `abi_c_declarations`/`abi_c_source`).
- Versioned ABI `openrecomp-generic-runtime-abi 1.0.0`; incompatible versions are detected
  and rejected with `ABI_VERSION_MISMATCH`.
- Bounded guest address space: checked read/write, explicit 8/16/32/64-bit width, explicit
  little/big endianness, and deterministic failures for out-of-range, unsupported width,
  unsupported endianness, segment overlap and 64-bit `address+width` overflow. Guest
  addresses are never host pointers; byte access returns immutable `bytes` copies.
- Host calls: stable service identity plus deterministic argument/result representation;
  unknown services, arity mismatch and handler failure all fail closed. No console API is
  invented.
- Generic input (ordered digital/analog channels with canonicalization), frame
  (geometry/format/checksum) and audio (format/rate/channels/frames/checksum) contracts;
  no controller layout, graphics backend or audio backend is assumed.
- Explicit failure/trap model with stable codes; `RuntimeState` is deterministic (no
  wall-clock/random/pid/address/filesystem/locale/environment dependence) with a
  configuration-seeded RNG hook and canonical serialization/fingerprint.
- Bounded P2-07 emitter integration: `HostEmitterConfig.runtime_abi` (default null) plus an
  explicit `HostCallOperation` rule. A host call is emitted only for a declared service on
  an explicitly external/runtime-mediated P2-06 site; undeclared services, missing config
  and non-external sites fail closed. Default (`runtime_abi=None`) output is byte-identical
  to P2-07, so fail-closed behavior and the bounded semantic subset are preserved.
- `tools/test_runtime_abi_v1.py`: 169 deterministic checks (incl. an optional native
  compile+run of a synthetic host-call fixture: observed `42 0` == expected).
- No P2-00..P2-07 implementation source modified except the additive/opt-in
  `host_emitter.py` change; no prior test weakened; no P2-09 started.

## P2-09 result (PASS)

Stage: `OPENRECOMP_P2_09_DETERMINISTIC_BUILD_PIPELINE_V1`.
Starting commit: `10971b76090746081cb29ca3405f96da7f143011` (P2-08 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Module `openrecomp/build_pipeline.py`: deterministic build pipeline with canonical
  `openrecomp-build-manifest-v1` serialization, explicit toolchain provenance, isolated
  independent runs and an honest reproducibility classification
  (`SOURCE_REPRODUCIBLE` / `MANIFEST_REPRODUCIBLE` / `OBJECT_REPRODUCIBLE` /
  `EXECUTABLE_REPRODUCIBLE` / `FUNCTIONALLY_REBUILT_BUT_BINARY_DIFFERS` /
  `TOOLCHAIN_UNAVAILABLE`; no claim may exceed observed artifact equality).
- Toolchain detected, never assumed: `clang-cl.exe` 22.1.8 (target
  `x86_64-pc-windows-msvc`) + `lld-link.exe` 22.1.8, with `/Brepro` passed directly to
  both. No binary post-processing and no manual COFF timestamp editing.
- Two genuinely independent builds in distinct directories, regenerating the generated
  source each run, produced byte-identical source, object and executable hashes
  (`generated.c b75d7656...`, `generated.obj fc452409...`, `runtime_support.obj
  51910f33...`, `program.exe de03764e...`); inspected COFF `TimeDateStamp` is `0x0` for
  both objects and `0x974E5A9` for both executables; classification
  `EXECUTABLE_REPRODUCIBLE`.
- The manifest records no timestamp, temporary directory, absolute path, username,
  hostname, pid, UUID or Python identity, and the validator rejects such fields.
- `tools/test_build_pipeline_v1.py`: 120 deterministic checks, including output-only
  `--evidence-dir` generation and evidence-path independence (two evidence roots
  byte-identical; the destination path never influences manifest, source, artifacts,
  classification or gate stdout). Optional native build/execution smoke test observed
  `42 0` (bounded synthetic smoke test, not equivalence).
- Fail closed: source hash mismatch, ABI mismatch, malformed manifest, duplicate output,
  unsafe/absolute names, unsupported compiler, failed compile/link, missing artifact,
  artifact-hash mismatch, over-strong reproducibility claim.
- No P2-00..P2-08 implementation source modified; no prior test weakened; no P2-10 started.

## P2-10 result (PASS)

Stage: `OPENRECOMP_P2_10_TINY_MIPS32_END_TO_END_PROOF_V1`.
Starting commit: `161893389cca5a30aa462670f19ecabfc1be679d` (P2-09 boundary).
Branch: `phase2/opencode-v1`. Phase-1 tag `openrecomp-phase1-pass` verified unchanged at
`46c2f971e1a42cf49bd936bad94697b81bf31002`.

- Dedicated gate `tools/test_mips32_end_to_end_v1.py` (108 deterministic checks). No second
  recompilation path was added; the proof reuses the frozen Phase-2 modules.
- Synthetic/original 13-instruction MIPS32 fixture (52 bytes, SHA-256
  `b33b597c28eb7f7239ee5079728c7f3e447387d4ed34525c445cf8c1e9234975`): `addiu`/`beq`/`nop`
  (delay slot)/`addiu`/`bne`/`nop`/`addu`/`subu`/`slt`/`jr r31`/`nop`. No commercial
  ROM/ELF/game bytes.
- Real pipeline traversal: adapter decode -> P2-01 ProgramModel -> P2-02 CFG (6 blocks;
  taken/not-taken/fallthrough/indirect edges) -> P2-03 function discovery (`fn_1000`;
  `blk_1030` preserved unowned) -> P2-04 call graph (1 node, 0 edges) -> P2-05 translation
  units (`tu_fn_1000`) -> P2-06 classification (`jr r31` at `0x102c` = `RETURN_LIKE`,
  `STRUCTURAL_RETURN_EVIDENCE`, no guessed targets; fails closed as `UNRESOLVED_INDIRECT_JUMP`
  without evidence) -> P2-07 host emission (generated source
  `8570ea4a11321118a3fff270e0dc9756d2a4ee7a52421ece1d2d892384118fbb`) -> P2-09 deterministic
  build. P2-08 is `NOT_APPLICABLE_FOR_FIXTURE` (no host service/runtime-mediated call).
- Independent expected observable (mathematical derivation + tiny independent reference
  interpreter + Phase-1 `mips32_oracle_v1` cross-check on reduced synthetic ELF fixtures)
  equals the actual native observable exactly (`r5=11 r6=6 r7=1`; stdout
  `failed=0` + register dump); returncode `0`; secondary execution identical.
- Two independent `/Brepro` builds: generated source, objects and executable byte-identical
  (`program.exe f94c95d2e86fca83f56e5e87a98bccaa1e2a4ced3fd9222aef29608592810f4e`);
  classification `EXECUTABLE_REPRODUCIBLE`; no binary post-processing.
- No P2-01..P2-09 implementation source modified; no prior test weakened; P2-11 not started.
- Final marker `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF` remains `NOT_PROVEN` (the
  control plane reserves the final marker for the P2-99 final verdict).

## Gates

```text
OPENRECOMP_MIPS32_END_TO_END_V1=PASS tests=108
OPENRECOMP_DETERMINISTIC_BUILD_V1=PASS tests=120
OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests=169
OPENRECOMP_HOST_EMITTER_V1=PASS tests=106
OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
OPENRECOMP_CFG_V1=PASS tests=82
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
PASS source-integrity  verified 120 manifest entries
```

Determinism: two consecutive P2-10 gate runs produced byte-identical stdout
(`sha256 5327f11c756e57fd23cae7243ae1222c8b2f990dc9884b8a5165787f1829b424`).

## Queue reconciliation note

The completed sequence is `P2-00` baseline, `P2-01` persistent program representation,
`P2-02` basic-block/CFG recovery, `P2-03` function recovery, `P2-04` call-graph recovery,
`P2-05` translation-unit model. The queue originally numbered `P2-04 Direct CFG recovery`,
`P2-05 Indirect-control-flow classification`, `P2-06 Translation-unit model`; it has been
reconciled to the executed sequence.

The indirect-control-flow classification work was assigned to `P2-06` with the original
safety requirement — classify resolvable versus unresolved indirect sites **without
guessing targets** — and is `PASS`. `P2-07` (Host emitter V1), `P2-08` (Generic runtime ABI
V1), `P2-09` (Deterministic build pipeline) and `P2-10` (Tiny MIPS32 end-to-end proof) are
`PASS`, and `P2-11` (MIPS32 calls/stack/memory) is `NEXT`.

This reassignment is a control-plane reconciliation caused by actual execution order. It
does not change the semantics, claims, evidence or PASS status of any frozen prior stage
(`P2-00`..`P2-10`), and it does not alter `ce9cd4f`, `f9f2662`, `30b4321`, `10971b7`,
`1618933` or any earlier commit.

## Next exact action

Begin P2-11 — MIPS32 calls/stack/memory: multiple functions, stack frames, loads/stores
through the end-to-end path. P2-11 was **not** started in P2-10. Do not modify the frozen
Phase-1 behavior or the P2-00..P2-10 layers except through an evidence-backed stage. Do not
claim the final Phase-2 end-to-end marker.

## Carried-forward findings

- `update_sums.py` globs `schemas/*.json` while the directory is `schema/`, so
  `schema/*.json` (and `openrecomp/*.py`, including `runtime_abi.py` and
  `build_pipeline.py`) remain outside the integrity manifest (pre-existing; deferred).
- `direct_callees` are provisional structural facts validated across P2-04/P2-05, not ABI
  recovery.
- P2-06 classifies indirect sites but does not recover targets by analysis; unresolved
  sites remain `UNRESOLVED_INDIRECT_CALL` / `UNRESOLVED_INDIRECT_JUMP` and bounded candidate
  sets remain `BOUNDED_CANDIDATES`.
- Unowned control flow is preserved as P2-06 residual evidence and is not classified.
- P2-07 emits only rule-proven semantics; loads/stores, calling conventions and most runtime
  services remain outside the emitted subset. Emitted functions are void with no
  argument/return ABI.
- P2-08 defines the generic runtime ABI and a bounded host-call seam. The generated C
  contains only boundary declarations (`extern or_rt_*`); no runtime implementation is
  generated, and `RuntimeState` is a deterministic contract surface rather than a guest
  execution engine.
- P2-09 builds a bounded synthetic generated host fixture plus a synthetic runtime-support
  source on this host's clang-cl/lld-link pair. Object/executable reproducibility is
  demonstrated for that toolchain; other toolchains may need different deterministic flags
  and are classified honestly.
- P2-10 proves only a 13-instruction synthetic MIPS32 fixture. The neutral CFG/emitter do
  not model delay slots as first-class semantics; the fixture uses `nop` delay slots, and
  the post-`jr` delay slot is preserved as unowned residual evidence rather than executed.
  No calls/stack/loads/stores are covered (P2-11/P2-12).
- The P2-07/P2-08 native compile+run checks, the P2-09 build/execution smoke test and the
  P2-10 end-to-end comparison are bounded synthetic checks, not equivalence proofs.
- Toolchain-gated gates remain unexecutable on this host.
- `STAGE_QUEUE.md` is reconciled to the executed sequence; `P2-10` is `COMPLETE` and
  `P2-11` is `NEXT`.

## Git status (short)

- P2-09 boundary commit: `1618933` (`phase2: complete P2-09 deterministic build pipeline`);
  `HEAD` at P2-10 start.
- Current uncommitted changes: P2-10 gate + evidence
  (`tools/test_mips32_end_to_end_v1.py`, `.openrecomp-phase2/evidence/P2-10/`) and the
  control-plane updates to `.openrecomp-phase2/STAGE_QUEUE.md`,
  `.openrecomp-phase2/STATE.md`, `.openrecomp-phase2/HANDOFF.md`, plus
  `SOURCE_SHA256SUMS.txt` (+1 entry, 119 -> 120).
- Untouched pre-existing untracked residue: `.openrecomp-phase2/backups/`,
  `.openrecomp-phase2/scratch/`, `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No commit created (P2-10 boundary commit intentionally not created).

OPENRECOMP_P2_10=PASS
OPENRECOMP_MIPS32_END_TO_END_V1=PASS tests=108
OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN
CURRENT_STAGE=P2-11
