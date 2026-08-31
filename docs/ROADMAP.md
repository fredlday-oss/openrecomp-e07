# OpenRecomp roadmap

This is a development roadmap and does not imply that external grant funding has been awarded.

A bounded clean MIPS32 synthetic vertical slice now passes through the same normalized IR V1, Module Image V1 and Core API V1 boundaries as the RV32I validation path. The roadmap therefore treats the second-architecture baseline as established while keeping broader MIPS32 ISA/ABI support evidence-gated.

## Months 1–2 — Core and IR stabilization

- continue hardening and documenting the versioned IR and Module Image contracts;
- harden translation/runtime boundaries;
- expand deterministic validation fixtures;
- maintain repeatable CI baselines across the proven/bounded guest paths.

## Months 3–4 — Expand second guest architecture

- extend MIPS32 beyond the current bounded little-endian synthetic subset;
- add additional ISA, control-flow, ABI and memory-semantics fixtures;
- grow adversarial and cross-architecture regression coverage;
- keep general MIPS32 support **CANDIDATE** until broader equivalent proof gates pass.

## Months 5–6 — Unreal interoperability layer

- refactor the UE5 proof into reusable host components;
- publish a documented sample integration;
- add Unreal-side validation where practical;
- improve diagnostics and integration ergonomics.

## Month 7 — Documentation and clean examples

- publish architecture and integration documentation;
- package redistributable synthetic/homebrew examples;
- add tutorials and reproducible integration walkthroughs.

## Month 8 — Release hardening

- close remaining validation gaps;
- improve CI and reproducibility;
- produce a tagged public milestone release;
- publish an updated technical demonstration.
