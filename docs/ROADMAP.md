# OpenRecomp roadmap

This is a development roadmap and does not imply that external grant funding has been awarded.

A bounded clean MIPS32 synthetic vertical slice now passes through the same normalized IR V1, Module Image V1 and Core API V1 boundaries as the RV32I validation path. A single portable C AOT backend also consumes both normalized workloads and reproduces the Core API result after GCC/Clang native compilation. The roadmap therefore treats the second-architecture and first common code-generation baselines as established while keeping broader ISA coverage and production compiler quality evidence-gated.

## Months 1–2 — Core, IR and AOT stabilization

- continue hardening and documenting the versioned IR and Module Image contracts;
- harden the portable C AOT backend and exported native-module ABI;
- add explicit negative/adversarial AOT cases and more IR-operation combinations;
- extend compiler/host portability beyond the current Linux GCC/Clang proof;
- expand deterministic validation fixtures;
- maintain repeatable CI baselines across reference and AOT execution paths.

## Months 3–4 — Expand second guest architecture

- extend MIPS32 beyond the current bounded little-endian synthetic subset;
- add additional ISA, control-flow, ABI and memory-semantics fixtures;
- run the expanded fixtures through both Core API reference execution and the common AOT backend;
- grow adversarial and cross-architecture regression coverage;
- keep general MIPS32 support **CANDIDATE** until broader equivalent proof gates pass.

## Months 5–6 — Unreal interoperability layer

- refactor the UE5 proof into reusable host components;
- define how translated/AOT modules bind Unreal host services through stable interfaces;
- publish a documented sample integration;
- add Unreal-side validation where practical;
- improve diagnostics and integration ergonomics.

## Month 7 — Documentation and clean examples

- publish architecture and integration documentation;
- package redistributable synthetic/homebrew examples;
- add tutorials and reproducible integration walkthroughs;
- document the reference-vs-AOT validation workflow for third-party contributors.

## Month 8 — Release hardening

- close remaining validation gaps;
- improve CI and reproducibility;
- define and freeze a public release-level compiler/module ABI only after compatibility testing;
- produce a tagged public milestone release;
- publish an updated technical demonstration.
