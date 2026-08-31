# OpenRecomp roadmap

This is a development roadmap and does not imply that external grant funding has been awarded.

A bounded clean MIPS32 synthetic vertical slice passes through the same normalized IR V1, Module Image V1 and Core API V1 boundaries as the RV32I validation path. A single portable C AOT backend consumes both normalized workloads and reproduces the Core API result after native compilation. The AOT hardening gate requires `-Werror`, a broader normalized-operation corpus, nine deterministic Core API/AOT fault-equivalence cases and GCC/Clang ASan+UBSan smoke execution. Native AOT ABI V1 freezes the first versioned host-facing binary contract and now passes bounded Linux GCC/Clang plus Windows x64 MSVC/clang-cl validation for the current RV32I and MIPS32 workloads. The roadmap therefore treats second-architecture, common code-generation, compiler-hardening, native-ABI design and initial cross-OS x64 portability as established while keeping broader ISA/platform and release-quality compiler claims evidence-gated.

## Months 1–2 — Core, IR, AOT and ABI portability

- continue hardening and documenting the versioned IR and Module Image contracts;
- preserve Native AOT ABI V1 layout/semantics while using it as the stable host boundary for follow-on integration;
- move Windows host work from proof-only DLL loading toward a reusable Native AOT ABI V1 host integration, with Unreal Engine as the next concrete integration target;
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

- refactor the UE5 proof into reusable host components;
- load and negotiate a Windows x64 OpenRecomp native AOT module through Native AOT ABI V1;
- bind Unreal-side host services through the versioned V1 callback table instead of guest-specific or proof-only calls;
- preserve independent authoritative runtime validation alongside visual presentation;
- publish a documented sample integration and improve diagnostics/integration ergonomics.

## Month 7 — Documentation and clean examples

- publish architecture and integration documentation;
- package redistributable synthetic/homebrew examples;
- add tutorials and reproducible integration walkthroughs;
- document the reference-vs-AOT, Native-ABI and cross-OS validation workflow for third-party contributors.

## Month 8 — Release hardening

- close remaining validation gaps;
- improve CI and reproducibility;
- promote a release-level compiler/module compatibility claim only after the frozen V1 ABI has passed the intended platform and host-integration matrix;
- produce a tagged public milestone release;
- publish an updated technical demonstration.
