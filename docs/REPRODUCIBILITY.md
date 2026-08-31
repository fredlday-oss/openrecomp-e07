# Reproducibility and evidence model

OpenRecomp separates immutable proof inputs from generated evidence and mutable project documentation.

## Proof-critical source manifest

`SOURCE_SHA256SUMS.txt` protects the source and data that directly define the E07 proof, including architecture adapters, host contracts, the synthetic corpus, golden outputs, linker script, IR schema, fixture source, proof/translation tools and the proof runner.

General project documentation is intentionally not part of this immutable proof-input manifest. Documentation can evolve without invalidating the executable proof.

## Generated evidence

`RUN.sh` recreates `build/` and `evidence/` outputs, validates deterministic translation and compares host-visible outputs. A per-run manifest records generated-file hashes.

## Golden validation

The committed golden framebuffer, audio and state outputs act as regression references for the current E07 fixture.

## Host parity

The translated workload is executed through native and WebAssembly host paths. Their checksums must agree.

## Classification

Reproducibility does not automatically promote a feature's status:

- RV32I E07 path: **PROVEN**
- MIPS32 adapter seam: **CANDIDATE**
