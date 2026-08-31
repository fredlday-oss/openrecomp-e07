# OpenRecomp roadmap

This is a development roadmap and does not imply that external grant funding has been awarded.

A bounded clean MIPS32 synthetic vertical slice passes through the same normalized IR V1, Module Image V1 and Core API V1 boundaries as the RV32I validation path. A single portable C AOT backend consumes both normalized workloads and reproduces the Core API result after GCC/Clang native compilation. The AOT hardening gate requires `-Werror`, a broader normalized-operation corpus, nine deterministic Core API/AOT fault-equivalence cases and GCC/Clang ASan+UBSan smoke execution. Native AOT ABI V1 now freezes the first versioned host-facing binary contract for portability testing and passes the current Linux GCC/Clang RV32I + bounded MIPS32 gates. The roadmap therefore treats second-architecture, common code-generation, compiler-hardening and initial native-ABI design as established while keeping platform parity, broader ISA coverage and release-quality compiler claims evidence-gated.

## Months 1–2 — Core, IR, AOT and ABI portability

- continue hardening and documenting the versioned IR and Module Image contracts;
- preserve Native AOT ABI V1 layout/semantics while validating it across additional host toolchains;
- make Windows the next concrete Native AOT ABI V1 portability target, followed by macOS where practical;
- test DLL/shared-library symbol visibility, fixed-width layout assumptions, callback calling conventions and loader behavior without silently mutating V1;
- expand deterministic and adversarial validation fixtures around the existing `-Werror`, sanitizer, runtime-fault and ABI-negotiation gates;
- maintain repeatable CI baselines across reference and AOT execution paths.

## Months 3–4 — Expand second guest architecture

- extend MIPS32 beyond the current bounded little-endian synthetic subset;
- add additional ISA, control-flow, ABI and memory-semantics fixtures;
- run the expanded fixtures through both Core API reference execution and the common hardened AOT backend;
- require expanded native modules to continue crossing Native AOT ABI V1 rather than adding architecture-specific host interfaces;
- grow adversarial and cross-architecture regression coverage;
- keep general MIPS32 support **CANDIDATE** until broader equivalent proof gates pass.

## Months 5–6 — Unreal interoperability layer

- refactor the UE5 proof into reusable host components;
- bind translated/AOT modules through Native AOT ABI V1 rather than a proof-only integration surface;
- publish a documented sample integration;
- add Unreal-side validation where practical;
- improve diagnostics and integration ergonomics.

## Month 7 — Documentation and clean examples

- publish architecture and integration documentation;
- package redistributable synthetic/homebrew examples;
- add tutorials and reproducible integration walkthroughs;
- document the reference-vs-AOT and Native-ABI validation workflow for third-party contributors.

## Month 8 — Release hardening

- close remaining validation gaps;
- improve CI and reproducibility;
- promote a release-level compiler/module compatibility claim only after the frozen V1 ABI has passed the intended platform matrix;
- produce a tagged public milestone release;
- publish an updated technical demonstration.
