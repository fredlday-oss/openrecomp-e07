# OpenRecomp roadmap

This is a forward-looking development roadmap. It is **not** a historical schedule and does not imply that external grant funding has been awarded.

Some work was completed earlier than the original phase ordering. The current baseline already includes bounded RV32I validation, the original MIPS32 vertical slice, post-v0.2.0 MIPS32 Expansion V1 with five little/big-endian synthetic fixtures, IR V1/Core API V1, the additive IR V1.1 `integer-divrem-v1` feature contract, a hardened common portable-C AOT backend, Native AOT ABI V1, Linux/Windows x64 portability, a one-command reproducible Linux external-reviewer path for the bounded open-core evidence, a reproducible Windows Native AOT host-core matrix, a reusable code-only `OpenRecompRuntime` Unreal plugin, local UE5.8 runtime evidence, a bounded end-to-end NES/NROM static-recompilation proof, a bounded NES/MMC1 platform proof, and a deterministic fail-closed ROM-to-native workflow for supported NES inputs.

The roadmap below therefore describes **remaining hardening, generalization, reproducibility and packaging work**, not a claim that every listed area is still unimplemented. The reusable open core and optional host-integration track are separated further in [`FUNDING_SCOPE.md`](FUNDING_SCOPE.md).

## Phase 1 — Core contracts and reproducibility

- continue hardening and documenting normalized IR V1, additive feature-gated IR revisions, Module Image V1 and Core API V1;
- preserve frozen IR V1.0 behavior while extending later wire versions only through explicit `required_features` gates;
- preserve Native AOT ABI V1 layout/semantics while it remains the stable host boundary;
- maintain deterministic native/WebAssembly/Core/AOT equivalence for the existing clean fixtures;
- expand negative/adversarial validation around parsing, memory, runtime faults, ABI negotiation and cross-OS byte integrity;
- keep the public-safety gate fail-closed and regression-tested;
- maintain `OPENRECOMP_EXTERNAL_REPRO_V1` as the clean Linux one-command reviewer path, with deterministic semantic evidence and no tracked-tree mutation;
- extend external-reviewer reproducibility to additional host platforms only through separate evidence gates rather than inferring parity from Linux.

## Phase 2 — Continue second-guest generalization

MIPS32 Expansion V1 now provides a bounded multi-fixture PASS beyond the original little-endian vertical slice. It covers additional logic/shifts, byte/halfword memory semantics, signed branch forms and delay slots, bounded nested call/stack behavior, HI/LO multiply, and one big-endian memory fixture across independent reference/Core/AOT and Linux/Windows compiler paths.

IR V1.1 now provides the supported additive `integer-divrem-v1` contract with deterministic architecture-neutral `udiv`, `urem`, `sdiv` and `srem` semantics. A separate bounded MIPS32 proof validates defined-domain `div/divu` lowering while deliberately excluding MIPS32 divide-by-zero and signed-overflow edge behavior from the guest claim.

Remaining second-guest work includes:

- expand MIPS32 `div/divu` coverage through the supported IR V1.1 feature using separately evidence-gated fixtures/frontends rather than mutating frozen Expansion V1;
- add further MIPS32 ISA families only with independent fixture-backed semantics;
- deepen bounded o32 ABI evidence beyond the current `$a0/$a1`, `$v0`, `$sp` and `$ra` call/stack fixture;
- complete bounded real-ELF static-memory validation for `.rodata`, initialized `.data`, zero-filled `.bss` and guest loads/stores before broad compiler-produced ELF claims;
- feed an unmodified, freely licensed compiler-produced MIPS32 ELF through the bounded loader/IR/Core/AOT path to expose real frontend gaps rather than designing only from synthetic fixtures;
- treat indirect control-flow target recovery as an explicit workstream: statically prove bounded jump/call candidate sets or stop with evidence that the target set is unresolved; do not guess or silently widen the runtime contract;
- define a first-class bounded indirect-call IR representation before claiming function-pointer, callback or vtable dispatch support; the existing bounded `indirect_jump` contract covers jump targets but direct-only `call` does not represent those calls today;
- consider unaligned load/store families and additional memory behavior as separate evidence gates;
- keep exceptions, coprocessors, floating point, atomics and privileged behavior outside supported claims until deliberately implemented and validated;
- run every added fixture through the independent machine-code reference, Core API and common hardened AOT backend;
- require expanded native modules to continue crossing Native AOT ABI V1 rather than adding architecture-specific host interfaces;
- retain explicit CANDIDATE/PASS boundaries until each broader claim has equivalent execution evidence.

## Phase 3 — AOT/compiler portability and release quality

- broaden compiler/platform coverage beyond current Linux x64 and Windows x64 evidence;
- treat macOS, Windows ARM64 and Windows x86 as separate evidence gates;
- extend hardening beyond the current warning/fault/sanitizer corpus;
- document a stable release process for generated modules and host compatibility;
- promote a release-quality compiler claim only after the intended portability/optimization/deployment matrix passes.

## Phase 4 — Optional host integration

Unreal Engine remains an optional consumer of OpenRecomp through Native AOT ABI V1, not part of the required open-core architecture.

`OPENRECOMP_UNREAL_PLUGIN_V1` provides a reusable code-only runtime plugin with a persistent Native AOT module wrapper, game-instance subsystem and synthetic example consumer. Hosted CI verifies its source/ABI contract and handoff generation; a separate UE5.8 Windows x64 run built the plugin and executed the synthetic RV32I module in PIE with state `48`, checksum `122010428` and `3866` operations. That UE execution remains local runtime evidence.

`OPENRECOMP_UNREAL_PACKAGED_BUILD_V1` extends the same plugin/ABI path through a real UE5.8 Windows x64 **Development** BuildCookRun package. The exact CI Native AOT DLL was staged in the packaged archive, and the packaged executable launched outside Editor/PIE with the same state `48`, checksum `122010428` and `3866` operations. Hosted CI verifies the source/staging contract, PowerShell 5.1 collector path, validated host-core execution and deterministic runtime handoff; the actual UE package/run remains local packaged runtime evidence.

Remaining Unreal/engine-host work includes:

- make the UE runtime evidence more reproducible, ideally with a project-controlled self-hosted CI runner or equivalent scripted environment;
- expand host-service bindings only when justified by clean fixtures;
- validate Shipping configuration separately from the current Development package;
- preserve independent authoritative runtime validation alongside presentation;
- improve diagnostics, plugin lifecycle coverage and integration documentation;
- treat broader Unreal versions, projects and host platforms as separate evidence gates rather than inferring them from the current synthetic Windows UE5.8 result.

The current UE5.8 PIE and Development packaged-build evidence is intentionally described as **local runtime PASS**, while the engine-independent Windows host core and Plugin/Packaged-Build source/module gates are reproducible in hosted CI.

## Phase 5 — NES/NROM end-to-end static recompilation — complete

Phase 5 proved a bounded NES platform path using an original Apache-2.0 NROM fixture.

Completed evidence includes:

- fail-closed iNES/NES 2.0 ingestion and inventory;
- exact reachable 2A03/6502 frontier and differential CPU-semantics validation;
- neutral ProgramModel/CFG/function/translation-unit integration;
- bounded NES CPU bus, PPU, input/timing/interrupt and runtime boundaries;
- generated host-native execution of the public fixture;
- exact independent-reference equivalence across deterministic input plans;
- reproducible public packaging with no private/commercial ROM bytes;
- explicit retention of `OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Phase 6 — MMC1 compatibility expansion — complete

Phase 6 extended the bounded NES path from NROM to MMC1 using an original Apache-2.0 public fixture.

Completed evidence includes:

- MMC1 serial-register protocol;
- required PRG/CHR bank switching and mirroring modes;
- bounded variant/PRG-RAM handling with fail-closed unsupported cases;
- generated native execution and independent MMC1 reference equivalence;
- a deterministic ROM-to-native workflow that classifies unsupported container/mapper/variant/opcode/control-flow/bank-state/toolchain cases explicitly;
- private TMNT compatibility analysis with no ROM redistribution.

The private TMNT target is **not** claimed playable. MMC1 is no longer the blocker; the current private frontier is translation/control-flow related.

## Phase 7 — NES translation/control-flow frontier — current

Phase 7 focuses on the exact frontier exposed by the private TMNT compatibility run while keeping the public proof based on redistributable fixtures.

Planned work includes:

- evidence-backed classification of opcode byte `0x7C` at `0xC570`;
- bank-aware executable identity and reachability across MMC1 PRG states;
- bounded indirect-control-flow recovery for the three observed `jmp ($E2)` sites without guessing targets;
- public fixtures for any newly supported semantics/control-flow mechanism;
- generated native execution and independent-reference equivalence for the bounded Phase-7 public proof;
- repeated private TMNT frontier runs to identify the next exact blocker;
- extension of the reusable ROM-to-native workflow only for mechanisms actually proven by evidence.

TMNT playability is not required for Phase-7 PASS and must remain unproven unless meaningful generated-native interactive execution is actually demonstrated.

## Phase 8 — return to MIPS32 end-to-end native recompilation — planned

After the Phase-7 NES translation/control-flow frontier is frozen, the main implementation frontier is expected to return to MIPS32.

The intended Phase-8 direction is:

- reuse the already-proven real-ELF ingestion/decode work rather than rebuilding it;
- keep one legally redistributable real MIPS32 ELF continuously exercising the pipeline;
- drive that ELF through the shared ProgramModel/CFG/translation layers;
- generate host-native code through the common runtime/ABI path;
- require deterministic native execution and independently structured reference equivalence;
- use targeted intermediate gates and reserve the expensive full historical regression primarily for the terminal whole-regression stage;
- cache immutable-hash analysis and stable generated build artifacts where safe;
- preserve one serial implementation frontier while allowing only non-mutating parallel verification/documentation/test-vector work.

A later console-specific MIPS track should begin only after the architecture-neutral real-MIPS32 native path is itself evidence-backed.
