# OpenRecomp roadmap

This is a development roadmap and does not imply that external grant funding has been awarded.

## Months 1–2 — Core and IR stabilization

- stabilize and document the versioned IR contract;
- harden translation/runtime boundaries;
- expand deterministic validation fixtures;
- establish repeatable CI baselines.

## Months 3–4 — Second guest architecture

- implement a second guest-architecture frontend;
- validate architecture-neutral IR/runtime boundaries;
- add cross-architecture regression coverage;
- keep status **CANDIDATE** until equivalent proof gates pass.

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
