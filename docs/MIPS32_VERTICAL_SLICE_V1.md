# MIPS32 vertical slice V1

**Frontier:** `OPENRECOMP_MIPS32_VERTICAL_SLICE_V1`  
**Status:** **PASS — bounded synthetic vertical slice**  
**Validated checksum:** `1950232098`  
**Validated result:** `v0 = 31`, observable memory word `19`

This frontier is OpenRecomp's first implemented second-guest-architecture path through the same normalized IR V1, Module Image V1 and Core API V1 interfaces already exercised by RV32I.

It is intentionally small and synthetic. The goal is to test whether the common boundaries actually generalize before broadening MIPS32 coverage.

## Clean fixture

The fixture in [`examples/mips32-v1/fixture.hex`](../examples/mips32-v1/fixture.hex) is an original synthetic sequence of little-endian MIPS32 instruction words. It contains no commercial executable, game asset, firmware, key or proprietary SDK material.

The bounded instruction subset exercises:

- `addiu`, `ori`, `lui`, `addu`;
- signed `slt` and unsigned `sltu`;
- `beq` and `bne`;
- aligned `lw` and `sw`;
- direct `jal` calls;
- `jr $ra` returns;
- direct `j`;
- architectural branch/jump/call/return delay slots;
- the architectural zero register;
- link-register state;
- 32-bit little-endian memory behavior.

## Pipeline

```text
synthetic MIPS32 machine words
        |
        +----------------------------+
        |                            |
        v                            v
independent MIPS32            MIPS32 frontend
reference executor                   |
        |                            v
        |                    normalized IR V1
        |                            |
        |                            v
        |                    Module Image V1
        |                            |
        |                            v
        |                     Core API V1
        |                     ReferenceExecutor
        |                            |
        +------------ compare -------+
                     |
                     v
          registers + memory + checksum
```

The machine-code reference executor does not execute normalized IR. It independently interprets the bounded MIPS32 words and their delay-slot behavior.

## Delay-slot lowering

Delay slots are a guest-architecture concern and do not appear as a special IR V1 operation.

The frontend normalizes them before common execution:

- branch conditions are computed from pre-delay-slot register state;
- the delay instruction executes regardless of branch direction;
- `jal` writes the architectural `ra = PC + 8` before its delay instruction;
- the delay instruction executes before the structured V1 `call`;
- direct jumps execute the delay instruction before the normalized `jump`;
- `jr $ra` executes its delay instruction before the normalized `return`.

Control transfers inside delay slots are rejected by this bounded frontend rather than guessed.

## Fail-closed frontend gate

The dedicated tests require rejection of:

- control flow inside a delay slot;
- an undeclared direct call target;
- the wrong endianness/architecture profile;
- misaligned instruction addresses;
- unsupported opcodes.

Repeated frontend runs must emit byte-identical normalized IR, sidecar metadata and frontend reports.

## Shared contracts

The MIPS32 frontend emits the existing normalized IR wire version `1.0.0` without extending the schema.

The observed portable operation set is:

```text
binop, branch, call, cast, compare, const, jump,
load, read_state, return, store, write_state
```

No MIPS32 opcode name is accepted as a normalized V1 `op`.

The generated executable package uses the existing Module Image V1 schema and is loaded/executed by the existing architecture-neutral Core API V1 implementation. The Core executor contains no MIPS32-specific instruction semantics.

## Equivalence result

The successful CI gate produced:

```text
OPENRECOMP_MIPS32_FRONTEND_V1_TESTS=PASS tests=7
MIPS32_FRONTEND_FUNCTIONS=2
MIPS32_DELAY_SLOTS_LOWERED=7
OPENRECOMP_MIPS32_NORMALIZATION_DETERMINISTIC=PASS
OPENRECOMP_IR_V1_VALID=PASS

MIPS32_REFERENCE_V0=31
MIPS32_REFERENCE_CHECKSUM=1950232098
MIPS32_REFERENCE_DELAY_SLOTS=7
OPENRECOMP_MIPS32_REFERENCE=PASS

OPENRECOMP_MIPS32_MODULE_PACKAGING_DETERMINISTIC=PASS
OPENRECOMP_MODULE_V1_VALID=PASS

MIPS32_CORE_API_V0=31
MIPS32_CORE_API_CHECKSUM=1950232098
MIPS32_CORE_API_OPERATIONS=100
OPENRECOMP_MIPS32_CORE_API_V1=PASS

OPENRECOMP_MIPS32_VERTICAL_SLICE_V1=PASS checksum=1950232098
```

The final gate compares the complete `r1..r31` normalized register state, the observable memory bytes, `v0`, the source-input provenance hash and the deterministic checksum between the independent machine-code reference and Core API paths.

## What this establishes

For the two current clean synthetic workloads, both RV32I and MIPS32 now cross the same normalized IR/module/runtime boundaries successfully.

This supports a bounded claim that the common IR V1, Module Image V1 and Core API V1 interfaces generalize across two materially different guest architectures.

## What remains CANDIDATE

This result does **not** prove:

- arbitrary MIPS32 executables;
- the full MIPS32 ISA or ABI;
- exception/interrupt/CP0 behavior;
- FPU/COP1 behavior;
- multiply/divide HI/LO behavior;
- unaligned MIPS load/store families;
- arbitrary indirect calls/jumps;
- branch-likely semantics;
- big-endian MIPS32;
- production ahead-of-time IR V1 code generation;
- any proprietary console runtime or executable.

Broader MIPS32 coverage must remain **CANDIDATE** until additional fixtures and validation gates are implemented.
