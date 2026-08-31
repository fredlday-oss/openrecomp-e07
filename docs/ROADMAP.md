# OpenRecomp roadmap

This is a development roadmap and does not imply that external grant funding has been awarded.

A bounded clean MIPS32 synthetic vertical slice passes through the same normalized IR V1, Module Image V1 and Core API V1 boundaries as the RV32I validation path. A single portable C AOT backend consumes both normalized workloads and reproduces the Core API result after native compilation. The AOT hardening gate requires `-Werror`, a broader normalized-operation corpus, nine deterministic Core API/AOT fault-equivalence cases and GCC/Clang ASan+UBSan smoke execution. Native AOT ABI V1 freezes the first versioned host-facing binary contract and passes bounded Linux GCC/Clang plus Windows x64 MSVC/clang-cl validation for the current RV32I and MIPS32 workloads. Unreal Engine 5.8 now also consumes the frozen Windows x64 ABI in an execution-backed Native AOT host proof for the E07 RV32I workload. The roadmap therefore treats second-architecture validation, common code generation, compiler hardening, native-ABI design, Windows x64 portability and the first real-engine Native AOT host integration as established while keeping broader ISA/platform, packaging and release-quality compiler/plugin claims evidence-gated.

## Months 1–2 — Core, IR, AOT and ABI portability

- continue hardening and documenting the versioned IR and Module Image contracts;
- preserve Native AOT ABI V1 layout/semantics while using it as the stable host boundary for follow-on integration;
- maintain Linux/Windows x64 compiler and runtime parity for the current synthetic proof modules;
- treat macOS, Windows ARM64 and Windows x86 as separate future portability evidence gates rather than inferring them from Windows x64;
- expand deterministic and adversarial validation fixtures around the existing warning-clean, sanitizer, runtime-fault, ABI-negotiation and cross-OS integrity gates;
- maintain repeatable CI baselines across Core API and AOT execution paths.

## Months 3–4 — Expand second guest architecture

- extend MIPS32 beyond the current bounded little-endian synthetic subset;
- add additional ISA, control-flow, ABI and memory-semantics fixtures;
- run the expanded fixtures through both Core API reference execution and the common hardened AOT backend;
- require expanded native modules to continue crossing Native AOT ABI V1 rather than adding architecture-specific host interfaces;
- grow adversarial and cross-architecture regression coverage;
- keep general MIPS32 support **CANDIDATE** until broader equivalent proof gates pass.

## Months 5–6 — Unreal interoperability layer

- evolve the proven `OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1` path into reusable Unreal host components/plugin structure;
- preserve `openrecomp_native_aot_query` and Native AOT ABI V1 as the module boundary rather than introducing Unreal-specific guest interfaces;
- expand Unreal-side host service bindings beyond the current deterministic proof host where justified by clean fixtures;
- add packaged-build/deployment validation separately from the current Editor/PIE runtime proof;
- preserve independent authoritative runtime validation alongside visual presentation;
- publish a documented sample integration and improve diagnostics/integration ergonomics.

## Month 7 — Documentation and clean examples

- publish architecture and integration documentation;
- package redistributable synthetic/homebrew examples;
- add tutorials and reproducible integration walkthroughs;
- document the reference-vs-AOT, Native-ABI, cross-OS and Unreal-host validation workflow for third-party contributors.

## Month 8 — Release hardening

- close remaining validation gaps;
- improve CI and reproducibility;
- promote a release-level compiler/module/plugin compatibility claim only after the frozen V1 ABI has passed the intended platform, deployment and host-integration matrix;
- produce a tagged public milestone release;
- publish an updated technical demonstration.
