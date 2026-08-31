# OpenRecomp proof status

| Component | Status | Evidence / notes |
| --- | --- | --- |
| E07 RV32I synthetic path | **PROVEN** | Hardened E07 V1.1 proof |
| Deterministic translation | **PASS** | Existing E07 evidence |
| Native execution | **PASS** | Existing E07 evidence |
| WebAssembly execution | **PASS** | Existing E07 evidence |
| Golden regression | **PASS** | Existing E07 evidence |
| Normalized IR V1 specification | **FROZEN-FOR-IMPLEMENTATION** | Schema, semantic validator and acceptance/rejection tests |
| RV32I -> normalized IR V1 bridge | **PASS** | Deterministic normalization and execution match E07 native/golden checksum `122010428`, return `a0=48`, and host counters |
| Module Image V1 packaging | **PASS** | Repeated packaging is byte-identical; hashes bind IR, host contract and initialized memory |
| Core API V1 reference module/runtime | **PASS** | Generic `ModuleImage` + `ReferenceExecutor` path matches bridge/native/golden checksum `122010428`, return `a0=48`, 3,866 operations and output hashes |
| MIPS32 synthetic vertical slice | **PASS** | Independent machine-code reference and shared IR V1/Module V1/Core API path match complete register state, memory and checksum `1950232098`; 7 delay slots lowered |
| Cross-architecture IR/Module/Core boundary | **PASS** | Bounded validation crosses both RV32I and MIPS32 synthetic guest workloads through the same normalized contracts |
| Portable C AOT backend V1 | **PASS** | One common IR V1 backend generates deterministic C for both current guest workloads; compiled native results equal Core API results exactly |
| GCC/Clang AOT behavioral parity | **PASS** | The same generated C produces identical proof-result JSON after native compilation with both compilers for RV32I and MIPS32 fixtures |
| General MIPS32 frontend/ISA coverage | **CANDIDATE** | Current implementation is a bounded little-endian subset, not arbitrary MIPS32 |
| Release-quality production AOT compiler pipeline | **CANDIDATE** | Current portable C backend is execution-backed but still bounded to the current synthetic workloads/IR subset |
| Unreal Engine 5.8 build | **PASS** | Validated locally |
| Unreal Gate B PIE runtime | **PROVEN-RUNTIME** | Public-safe runtime evidence |
| Unreal visual replay | **PASS** | Presentation evidence, separate from authoritative Gate B |

## Claim policy

**PROVEN** means the current evidence directly validates the stated path.

**PASS** means a bounded validation/test completed successfully.

**PROVEN-RUNTIME** means the expected behavior was observed and validated during actual runtime execution.

**CANDIDATE** means an interface or future direction exists but the implementation has not crossed the required proof gate.

**FROZEN-FOR-IMPLEMENTATION** is a specification state, not a proof state. It means the contract is sufficiently defined and mechanically validated to implement against, while broader runtime/generalization claims remain gated on execution evidence.

The RV32I results remain bounded to the E07 synthetic fixture/proven RV32I subset. The MIPS32 result is separately bounded to `OPENRECOMP_MIPS32_VERTICAL_SLICE_V1`: a clean little-endian synthetic machine-word fixture covering arithmetic, signed/unsigned comparison, branches, aligned `lw`/`sw`, direct call/return, direct jump and delay-slot lowering.

The cross-architecture IR/Module/Core PASS means the same normalized IR V1, Module Image V1 and Core API V1 boundaries have been validated with two materially different synthetic guest architectures.

`OPENRECOMP_IR_V1_AOT_TRANSLATOR_V1` adds a separate bounded PASS: the same architecture-neutral portable C backend consumes both normalized workloads, emits byte-identical C on repeated translation, and after GCC/Clang compilation reproduces the existing Core API result exactly. This does **not** promote arbitrary RV32I/MIPS32 executables, full MIPS32 ISA/ABI coverage, untested IR operation combinations, broader platform/compiler portability, optimization correctness, or a release-quality production compiler pipeline to PROVEN.
