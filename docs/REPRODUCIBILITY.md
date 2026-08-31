# Reproducibility and evidence model

OpenRecomp separates immutable proof inputs from generated evidence and mutable project documentation.

## Proof-critical source manifest

`SOURCE_SHA256SUMS.txt` protects the source and data that directly define the original E07 proof, including architecture adapters, host contracts, the synthetic corpus, golden outputs, linker script, legacy IR schema, fixture source, proof/translation tools and the proof runner.

General project documentation is intentionally not part of this immutable E07 proof-input manifest. Documentation can evolve without invalidating that executable proof.

Newer IR V1/Core API/MIPS32 regression gates are independently enforced by GitHub Actions and their own deterministic comparisons rather than silently changing the historical E07 source manifest.

## E07 generated evidence

`RUN.sh` recreates `build/` and `evidence/` outputs, validates deterministic translation and compares host-visible outputs. A per-run manifest records generated-file hashes.

## RV32I normalized/Core reproducibility

The E07 CI additionally normalizes the proven RV32I path to IR V1 twice and requires byte-identical outputs, packages Module Image V1 twice and requires byte-identical outputs, then compares the Core API result with the independent bridge, native execution and committed golden state.

The bounded result is checksum `122010428`, observed `a0=48`.

## MIPS32 vertical-slice reproducibility

The MIPS32 gate starts from an original clean synthetic machine-word fixture. It:

1. runs fail-closed decoder/frontend tests;
2. lowers the fixture twice and requires byte-identical IR V1, execution-sidecar and frontend-report outputs;
3. validates normalized IR V1;
4. executes an independent machine-code MIPS32 reference path with architectural delay slots;
5. packages Module Image V1 twice and requires byte-identical output;
6. validates Module Image V1;
7. executes the same normalized workload through the shared Core API V1 `ReferenceExecutor`;
8. compares complete normalized register state, observable memory, source provenance and checksum across the independent reference/Core paths.

The current bounded MIPS32 result is `v0=31`, observable memory word `19`, seven delay slots and checksum `1950232098`.

## Golden validation

The committed E07 golden framebuffer, audio and state outputs remain regression references for the original RV32I fixture. The MIPS32 vertical slice uses explicit expected state/memory/checksum metadata plus independent cross-path agreement rather than reusing the E07 host-output goldens.

## Host parity

The E07 translated workload is executed through native and WebAssembly host paths and their checksums must agree. The host-free MIPS32 slice instead validates guest semantics by comparing an independent machine-code reference against the common IR/Module/Core path.

## Classification

Reproducibility does not automatically promote a feature's status:

- RV32I E07 path: **PROVEN**
- RV32I -> IR V1 bridge: **PASS — E07 equivalence**
- Core API V1 reference path: **PASS — E07 equivalence**
- MIPS32 synthetic vertical slice: **PASS — bounded equivalence**
- Shared IR/Module/Core boundary across RV32I + MIPS32: **PASS — bounded two-guest validation**
- General MIPS32 ISA/frontend coverage: **CANDIDATE**
- Production AOT IR V1 translator: **CANDIDATE**
