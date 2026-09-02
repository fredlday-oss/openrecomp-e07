# Changelog

Significant project changes will be recorded here.

## Unreleased

### Added

- `OPENRECOMP_EXTERNAL_REPRO_V1`: one-command clean-checkout Linux x86-64 reviewer path (`bash EXTERNAL_REPRO_V1.sh`) covering the hardened E07 RV32I proof, normalized IR/Module/Core execution, GCC/Clang Native AOT equivalence, the bounded MIPS32 vertical slice, the five-fixture MIPS32 Expansion V1 matrix and the tracked-file public-safety gate.
- Deterministic machine-readable External Repro V1 evidence (`RESULT.json` plus SHA-256) with hosted CI requiring a second complete invocation to reproduce the same semantic evidence byte-for-byte while leaving the tracked tree unchanged.
- `OPENRECOMP_MIPS32_EXPANSION_V1`: five clean synthetic MIPS32 fixtures covering expanded logical/shift operations, byte/halfword memory semantics, signed branch forms, nested call/stack behavior, HI/LO multiply and bounded big-endian memory execution.
- Independent reference, Core API and Native AOT equivalence gates for the expanded MIPS32 fixtures under Linux GCC/Clang and Windows x64 MSVC/clang-cl.
- Seven fail-closed expansion tests covering unsupported division under frozen IR V1, malformed encodings/targets, misaligned source or halfword access and execution-limit exhaustion.
- `OPENRECOMP_UNREAL_PLUGIN_V1`: reusable code-only `OpenRecompRuntime` Unreal Engine plugin with persistent Native AOT module wrapper, `UGameInstanceSubsystem`, bounded state/memory inspection, host-call bridge and synthetic example actor.
- Hosted Unreal-plugin gate for ABI-header identity, source layering, deterministic source/handoff packaging, validated Windows Native AOT module build and engine-independent execution.
- Local UE5.8 Windows x64 plugin runtime evidence: Editor/plugin build PASS and PIE result `observed_state=48`, checksum `122010428`, operations `3866`, with the returned plugin manifest matching the CI handoff exactly.
- `OPENRECOMP_UNREAL_PACKAGED_BUILD_V1`: opt-in packaged-runtime proof path through the existing `UOpenRecompSubsystem`, explicit Win64 `NonUFS` staging of the validated Native AOT DLL, scripted UE5.8 Development BuildCookRun packaging, packaged-executable launch and public-safe evidence extraction.
- Hosted packaged-build gate for source/staging contract validation, Windows PowerShell 5.1 parser/collector execution, validated module/host-core execution and deterministic runtime-handoff generation.
- Local UE5.8 Windows x64 Development packaged-runtime evidence: package PASS, exact CI DLL SHA-256 staging and packaged executable result `observed_state=48`, checksum `122010428`, operations `3866` outside Editor/PIE.

### Changed

- External reviewer reproducibility is now an explicit bounded Linux open-core gate rather than an instruction assembled from separate CI workflows; Unreal execution, Windows parity, other host platforms, Shipping packaging, arbitrary guest binaries and production-compiler claims remain outside that gate.
- The bounded MIPS32 evidence now includes a multi-fixture little/big-endian expansion while general MIPS32 frontend/ISA coverage remains `CANDIDATE`.
- `div/divu` remain explicitly outside the expansion because normalized IR V1 has no division/remainder semantic operation; IR V1 and Native AOT ABI V1 remain unchanged.
- Unreal integration now has a reusable plugin layer over frozen Native AOT ABI V1; its hosted source/module gates are reproducible in CI while UE5.8 build/PIE remains explicitly classified as local runtime evidence.
- Packaged Unreal deployment is now validated for the bounded UE5.8 Windows x64 **Development** configuration and synthetic RV32I workload; Shipping parity, other Unreal versions/platforms and arbitrary projects remain outside the proven scope.

## [0.2.0] - 2026-09-01

### Added

- Reviewer-response hardening for evidence provenance, development-process transparency and funding-scope separation.
- `DEVELOPMENT_PROCESS.md` documenting human responsibility, material AI/automation disclosure and the rule that generated output is not evidence by itself.
- `docs/FUNDING_SCOPE.md` separating the reusable open-core milestone track from optional host-integration/portability work.
- Regression coverage for `tools/public_safety_scan.py` when a tracked file is missing from the working tree.
- `OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1`: engine-independent Native AOT host core, Unreal DLL/query wrapper, proof actor, Windows cross-toolchain host/module CI matrix, installer and public-safe evidence collector.
- Local UE5.8 Windows x64 runtime evidence consuming the frozen Native AOT ABI V1 through `openrecomp_native_aot_query`, with observed state `48`, checksum `122010428` and `3866` operations.
- `OPENRECOMP_AOT_WINDOWS_PORTABILITY_V1`: Windows x64 Native AOT ABI validation under MSVC and clang-cl, including fixed layout, DLL export, negotiation and Linux/Core parity checks.
- `OPENRECOMP_NATIVE_AOT_ABI_V1`: public fixed-width C contract with the versioned `openrecomp_native_aot_query` discovery entry point, deterministic module adapter generation and fail-closed version/size negotiation.
- `OPENRECOMP_AOT_HARDENING_V1`: warning-clean compiler gates, architecture-independent hardening corpus, nine deterministic Core API/AOT fault-equivalence classes and GCC/Clang ASan+UBSan smoke execution.
- Common deterministic normalized IR V1 -> portable C ahead-of-time backend shared by the current RV32I and bounded MIPS32 workloads.
- Clean synthetic little-endian MIPS32 vertical slice with independent machine-code reference execution and exact IR V1/Module Image V1/Core API equivalence checks.
- OpenRecomp Core API V1 reference package with `ModuleImage`, `GuestState`, `GuestMemory`, `HostBinding` and `ReferenceExecutor`.
- Module Image V1 schema binding normalized IR, host contract, memory image, initial state, provenance and deterministic execution limits.
- Deterministic RV32I E07 `0.1.1` -> normalized IR V1 `1.0.0` bridge and equivalence gate.
- Normalized OpenRecomp IR V1 (`1.0.0`) specification, schema, semantic validator and acceptance/rejection tests.
- Repository production hardening, hardened E07 CI, public-safety scanning, documentation-link validation and contributor/security/build/reproducibility guidance.
- Public release metadata, release notes and publication checklist for v0.2.0.

### Changed

- Unreal runtime status is reported as **PASS — local runtime evidence** rather than an unqualified `PROVEN-RUNTIME` claim when the UE5.8 environment is not reproducible in hosted project CI. The engine-independent Windows host-core matrix remains a reproducible CI PASS.
- The original Unreal Gate B PIE result is likewise reported as **PASS — local runtime evidence**; its visual replay remains presentation evidence only.
- README and architecture documentation present the reusable open core first and Unreal as an optional consumer of Native AOT ABI V1 rather than a core dependency.
- `docs/ROADMAP.md` distinguishes the current implemented baseline from remaining forward-looking hardening/generalization work; earlier-than-planned host prototypes are not represented as still-unimplemented future milestones.
- Funding/milestone guidance requires already-completed work and proposed work to be separated and discourages overlapping funding claims across core and host-specific tracks.
- `tools/public_safety_scan.py` fails closed with a controlled diagnostic if `git ls-files` fails, a tracked file is missing, or a tracked text file cannot be read; missing files no longer produce a raw Python traceback.
- Native AOT ABI V1 remains **FROZEN-FOR-PORTABILITY-TESTING**; incompatible layout/signature changes require a new ABI version.
- Windows checkout byte stability is enforced with `.gitattributes` after CRLF conversion of a hashed host contract was correctly rejected by Module Image integrity validation.
- Portable C AOT output remains warning-clean for the established dual-architecture workloads and hardening corpus; Linux compiler gates use `-Wall -Wextra -Werror`.
- The shared IR V1, Module Image V1 and Core API V1 boundary is boundedly validated with both RV32I and MIPS32 synthetic workloads; broader MIPS32 support remains `CANDIDATE`.
- Source-integrity policy keeps proof-critical inputs separate from mutable project documentation.
