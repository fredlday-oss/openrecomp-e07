# MIPS32 expansion V1

`OPENRECOMP_MIPS32_EXPANSION_V1` broadens the post-v0.2.0 second-guest evidence without promoting OpenRecomp to general MIPS32 support.

The expansion deliberately reuses the frozen normalized IR V1, Module Image V1, Core API V1, portable-C AOT backend and Native AOT ABI V1. It adds no MIPS32-specific host interface and does not change the public native ABI.

## Evidence scope

Five clean synthetic fixtures exercise separate semantic areas:

| Fixture | Architecture | Coverage | Checksum | Core/AOT operations | Delay slots |
| --- | --- | --- | ---: | ---: | ---: |
| `logic-shift` | `mips32-le` | logical ops, fixed/variable shifts, signed/unsigned comparisons/immediates | `435263539` | `72` | `1` |
| `memory-width` | `mips32-le` | `lb/lbu/lh/lhu/lw`, `sb/sh/sw`, sign extension and alignment | `4257846410` | `60` | `1` |
| `branches-calls` | `mips32-le` | `blez/bgtz/bltz/bgez`, delay slots, nested direct calls, `$a0/$a1`, `$sp`, `$ra` save/restore | `2065440492` | `75` | `9` |
| `mult-hilo` | `mips32-le` | signed/unsigned multiply plus `mfhi/mflo` | `768371589` | `44` | `1` |
| `big-endian-memory` | `mips32-be` | big-endian word/byte/halfword memory behavior | `938211822` | `24` | `1` |

The older `examples/mips32-v1` vertical slice remains independently intact. The expansion uses a separate frontend profile and fixture directory so the v0.2.0 evidence path is not rewritten retrospectively.

## Expanded decoded subset

Expansion V1 adds bounded support for:

```text
sll srl sra sllv srlv srav
addu subu and or xor nor
slt sltu slti sltiu
addiu andi ori xori lui
beq bne blez bgtz bltz bgez
lb lbu lh lhu lw
sb sh sw
j jal jr
mult multu mfhi mflo
```

`nop` remains supported as the zero word.

This list is a fixture-backed subset, not a complete ISA declaration.

## Division boundary

`div` and `divu` are intentionally rejected by this frontier.

Normalized IR V1 currently has no division/remainder operation. Rather than silently change the frozen IR contract merely to increase MIPS32 opcode coverage, the decoder fails closed with an explicit diagnostic. Division semantics can be considered in a future IR revision or separately justified architecture-neutral extension.

## Independent evidence paths

Each fixture is checked through three execution paths:

```text
synthetic MIPS32 machine words
        |
        +--> independent MIPS32 reference machine
        |
        +--> MIPS32 expansion frontend
                 |
                 v
          normalized IR V1
                 |
                 v
           Module Image V1
            /          \
           v            v
   Core API V1     portable C AOT
                        |
                        v
                Native AOT ABI V1
```

The checker requires complete state parity, observable-memory parity, the expected deterministic checksum, and Core/AOT operation-count parity. HI/LO state is compared explicitly for the multiply fixture.

## Compiler/platform matrix

Linux hosted CI compiles every expanded native module with:

```text
GCC   -std=c11 -O2 -Wall -Wextra -Werror
Clang -std=c11 -O2 -Wall -Wextra -Werror
```

Windows x64 hosted CI compiles every expanded module through the unchanged Native AOT ABI V1 with:

```text
MSVC     /std:c11 /O2 /W4 /WX /LD
clang-cl /std:c11 /O2 /W4 /WX /LD
```

Both Windows compiler results must match the independent Linux reference/Core evidence for every fixture.

## Negative/fail-closed coverage

Expansion V1 also tests rejection/fault behavior for:

- `div/divu` while IR V1 lacks division semantics;
- malformed fixed-shift encoding;
- unsupported `REGIMM` encoding;
- misaligned source instruction records;
- branch targets leaving a declared function;
- misaligned halfword memory access;
- reference execution-limit exhaustion.

Expected markers include:

```text
OPENRECOMP_MIPS32_EXPANSION_DECODER=PASS
OPENRECOMP_MIPS32_EXPANSION_NEGATIVE_TESTS=PASS tests=7
OPENRECOMP_MIPS32_EXPANSION_REFERENCE=PASS
OPENRECOMP_MIPS32_EXPANSION_CORE_API=PASS
OPENRECOMP_MIPS32_EXPANSION_AOT=PASS
OPENRECOMP_MIPS32_EXPANSION_LINUX_COMPILERS=PASS
OPENRECOMP_MIPS32_EXPANSION_WINDOWS_COMPILERS=PASS
OPENRECOMP_MIPS32_EXPANSION_V1=PASS
```

## Claim boundary

This evidence upgrades the project from one MIPS32 vertical-slice fixture to a **bounded multi-fixture MIPS32 expansion PASS**.

It does **not** establish:

- arbitrary MIPS32 executable support;
- full MIPS32 ISA coverage;
- complete o32 ABI support;
- unaligned-load/store instruction families such as `lwl/lwr/swl/swr`;
- exceptions, coprocessors, privileged instructions or floating point;
- `div/divu` in normalized IR V1;
- general MIPS32 frontend/ISA coverage.

`General MIPS32 frontend/ISA coverage` therefore remains **CANDIDATE**.
