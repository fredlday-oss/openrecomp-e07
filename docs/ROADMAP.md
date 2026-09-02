# OpenRecomp roadmap

This is a forward-looking development roadmap. It is **not** a historical schedule and does not imply that external grant funding has been awarded.

Some work was completed earlier than the original phase ordering. The current baseline already includes bounded RV32I validation, the original MIPS32 vertical slice, post-v0.2.0 MIPS32 Expansion V1 with five little/big-endian synthetic fixtures, IR V1/Core API V1, a hardened common portable-C AOT backend, Native AOT ABI V1, Linux/Windows x64 portability, a reproducible Windows Native AOT host-core matrix, a reusable code-only `OpenRecompRuntime` Unreal plugin, local UE5.8 runtime evidence for both the Native AOT host proof and Plugin V1 synthetic consumer, and a bounded UE5.8 Windows x64 Development packaged-build/runtime PASS outside Editor/PIE.

The roadmap below therefore describes **remaining hardening, generalization, reproducibility and packaging work**, not a claim that every listed area is still unimplemented. The reusable open core and optional host-integration track are separated further in [`FUNDING_SCOPE.md`](FUNDING_SCOPE.md).

## Phase 1 — Core contracts and reproducibility

- continue hardening and documenting normalized IR V1, Module Image V1 and Core API V1;
- preserve Native AOT ABI V1 layout/semantics while it remains the stable host boundary;
- maintain deterministic native/WebAssembly/Core/AOT equivalence for the existing clean fixtures;
- expand negative/adversarial validation around parsing, memory, runtime faults, ABI negotiation and cross-OS byte integrity;
- keep the public-safety gate fail-closed and regression-tested;
- improve reproducibility instructions so external reviewers can rerun the open-core proof from a fresh clone.

## Phase 2 — Continue second-guest generalization

MIPS32 Expansion V1 now provides a bounded multi-fixture PASS beyond the original little-endian vertical slice. It covers additional logic/shifts, byte/halfword memory semantics, signed branch forms and delay slots, bounded nested call/stack behavior, HI/LO multiply, and one big-endian memory fixture across independent reference/Core/AOT and Linux/Windows compiler paths.

Remaining second-guest work includes:

- add further MIPS32 ISA families only with independent fixture-backed semantics;
- deepen bounded o32 ABI evidence beyond the current `$a0/$a1`, `$v0`, `$sp` and `$ra` call/stack fixture;
- decide division/remainder at the architecture-neutral IR layer before supporting `div/divu`; frozen IR V1 currently has no such operation;
- consider unaligned load/store families, additional control flow and memory behavior as separate evidence gates;
- keep exceptions, coprocessors, floating point and privileged behavior outside supported claims until deliberately implemented and validated;
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

## Phase 5 — Documentation and clean examples

- publish architecture and integration walkthroughs;
- package redistributable synthetic/homebrew examples;
- document the reference-vs-AOT, Native-ABI and cross-OS validation workflow for third-party contributors;
- maintain explicit development-process and evidence-provenance documentation;
- keep funding/milestone descriptions clear about completed work versus proposed work.

## Phase 6 — Next public milestone

- close selected validation gaps after v0.2.0 without rewriting the published tag or release evidence;
- improve CI and reproducibility;
- produce a later tagged public milestone only when its bounded evidence scope is stable;
- publish an updated technical demonstration/evidence summary when useful;
- avoid broadening PROVEN/PASS claims beyond the actual evidence matrix.