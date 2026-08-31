# OpenRecomp IR V1 portable C AOT translator V1

**Frontier:** `OPENRECOMP_IR_V1_AOT_TRANSLATOR_V1`  
**Status:** **PASS — bounded dual-architecture AOT equivalence**

This frontier adds the first common ahead-of-time backend that consumes normalized OpenRecomp IR V1 rather than guest-specific instruction records.

The backend is intentionally simple and inspectable: validated IR V1 + Module Image V1 are translated deterministically into portable C, then compiled to native code. The resulting native module is executed independently of the Python `ReferenceExecutor` and compared against the existing reference result.

## Common pipeline

```text
RV32I frontend/bridge ----+
                          |
                          v
                    normalized IR V1
                          |
MIPS32 frontend -----------+
                          |
                          v
                    Module Image V1
                          |
                          v
                  portable C AOT V1
                          |
                    generated C
                          |
                +---------+---------+
                |                   |
                v                   v
               GCC                Clang
                |                   |
                +---------+---------+
                          |
                          v
                   native module
                          |
                          v
              deterministic result
                          |
                          v
                 Core API comparison
```

The AOT backend contains no RV32I or MIPS32 opcode semantics. Guest-specific rules, including MIPS32 delay slots, are already normalized by the architecture frontend before the common backend sees the program.

## Inputs

`tools/aot_c_backend_v1.py` accepts:

```text
Module Image V1
normalized IR V1
host contract
```

It loads those through the existing fail-closed `ModuleImage` validation path before generating code. This binds translation to the exact IR hash, source provenance, host-contract version/hash, initialized memory, typed initial state, entry point and deterministic limits.

## Generated native-module interface

The generated C exports a small architecture-neutral runtime surface:

```text
openrecomp_set_host_callback
openrecomp_run
openrecomp_observed_state
openrecomp_function_return
openrecomp_function_has_return
openrecomp_operations
openrecomp_state_count
openrecomp_state_name
openrecomp_state_value
openrecomp_memory_size
openrecomp_memory_read
openrecomp_error
```

Host calls use one callback boundary instead of embedding E07, Unreal, RV32I or MIPS32 host semantics into the translator.

The test runners bind the already-existing deterministic E07 host behavior for the RV32I proof. The MIPS32 vertical slice requires no host calls.

## Portable operation lowering

The backend lowers the normalized V1 operation families used by the current fixtures:

- constants and typed state reads/writes;
- integer arithmetic and bitwise operations;
- signed/unsigned comparisons;
- casts and selects;
- bounded/aligned guest-memory loads and stores;
- direct calls;
- named host calls;
- direct branches/jumps;
- bounded indirect jumps;
- returns and traps.

Execution retains the Module Image V1 operation limit and call-depth limit. Memory faults, misalignment faults, failed host calls, invalid indirect targets and unsupported behavior fail closed.

## Deterministic code generation

Each architecture input is translated twice and the generated C files must be byte-identical:

```text
OPENRECOMP_AOT_RV32I_C_DETERMINISTIC=PASS
OPENRECOMP_AOT_MIPS32_C_DETERMINISTIC=PASS
```

The same generated source is compiled independently with GCC and Clang. Both compiler outputs must produce byte-identical result JSON for each fixture:

```text
OPENRECOMP_AOT_RV32I_COMPILER_PARITY=PASS
OPENRECOMP_AOT_MIPS32_COMPILER_PARITY=PASS
```

Compiler binaries themselves are not expected to be byte-identical; behavioral parity is the gate.

## RV32I result

The AOT native module reproduces the proven E07/Core API result:

```text
AOT_E07_CHECKSUM=122010428
AOT_E07_RETURN_A0=48
AOT_E07_OPERATIONS=3866
OPENRECOMP_AOT_E07_V1=PASS
```

The final AOT JSON is required to equal the Core API V1 JSON exactly, including deterministic host counters and framebuffer/audio payload hashes.

## MIPS32 result

The same AOT backend consumes the MIPS32 vertical slice's normalized IR and reproduces its Core API result:

```text
AOT_MIPS32_V0=31
AOT_MIPS32_CHECKSUM=1950232098
AOT_MIPS32_OPERATIONS=100
OPENRECOMP_AOT_MIPS32_V1=PASS
```

The comparison includes complete normalized register state, observable memory, function return, operation count, source provenance and checksum.

## Dual-architecture gate

The final gate requires both architectures to match their independent Core API reference paths exactly:

```text
OPENRECOMP_IR_V1_AOT_RV32I=PASS
OPENRECOMP_IR_V1_AOT_MIPS32=PASS
OPENRECOMP_IR_V1_AOT_DUAL_ARCH=PASS
```

This is the first execution-backed evidence that a single common AOT backend can consume normalized code originating from two materially different guest architectures.

## Claim boundary

This PASS is deliberately bounded. It establishes the portable C AOT backend for the current clean synthetic RV32I and MIPS32 workloads and their exercised IR V1 operation subset.

It does **not** yet establish:

- arbitrary RV32I or MIPS32 binaries;
- full MIPS32 ISA/ABI coverage;
- production optimization correctness;
- a stable external C ABI for third-party hosts;
- Windows/macOS compiler parity;
- WebAssembly compilation of the new AOT backend;
- a release-quality production compiler pipeline;
- proprietary console executable support.

Those remain separate validation frontiers.
