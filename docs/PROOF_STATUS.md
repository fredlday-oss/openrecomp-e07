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
| Production AOT IR V1 translator | **CANDIDATE** | Reference executor is proven for the E07 fixture; reusable production code generation remains a later gate |
| MIPS32 second-adapter seam | **CANDIDATE** | Interface only; not an implemented/proven architecture |
| Unreal Engine 5.8 build | **PASS** | Validated locally |
| Unreal Gate B PIE runtime | **PROVEN-RUNTIME** | Public-safe runtime evidence |
| Unreal visual replay | **PASS** | Presentation evidence, separate from authoritative Gate B |

## Claim policy

**PROVEN** means the current evidence directly validates the stated path.

**PASS** means a bounded validation/test completed successfully.

**PROVEN-RUNTIME** means the expected behavior was observed and validated during actual runtime execution.

**CANDIDATE** means an interface or future direction exists but the implementation has not crossed the required proof gate.

**FROZEN-FOR-IMPLEMENTATION** is a specification state, not a proof state. It means the contract is sufficiently defined and mechanically validated to implement against, while broader runtime/generalization claims remain gated on execution evidence.

The RV32I IR V1 bridge and Core API V1 PASS results are intentionally bounded to the current E07 synthetic fixture and proven RV32I instruction subset. They do not promote MIPS32, arbitrary RV32I binaries, or the future production ahead-of-time V1 translator to PROVEN.
