# MIPS32 Semantic Contract

## Supported Instructions
The MIPS32 translation boundary currently strictly enforces support for only the following synthetic instruction subset:
- `addiu` (Add immediate unsigned, sign-extends immediate)
- `addu` (Add unsigned)
- `beq` (Branch on equal)
- `jr $ra` (Jump register, strictly bounded to `$ra` / `$31`)
- `nop` (No operation)

## Bounded Semantics
- **Memory Translation**: `MEMORY_TRANSLATION_SUPPORTED = NO`. `lw`, `sw`, and other guest memory operations are strictly rejected at this stage.
- **Function / Control Flow Scope**: This translation path models a single synthetic entry function. Bounded basic-block discovery is supported, but general interprocedural translation, arbitrary discontiguous executable-region support, and general `jal` function discovery are currently unsupported.
- **Branch Delay Slots**: Handled correctly for `beq` (taken and not-taken) and `jr`.
- **Registers**: Standard 32-bit integer registers are modeled. Writes to `$zero` are discarded. Reads from `$zero` return `0`.
