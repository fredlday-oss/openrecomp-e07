# MIPS32 ELF Ingestion V1

## Status

`MIPS32 ELF Ingestion V1` is a bounded ingestion seam that connects a rights-safe, statically linked little-endian MIPS32 ELF executable to the existing MIPS32 Expansion V1 normalized IR/Core/AOT path.

It does not expand the MIPS32 instruction contract. It changes the source container from the synthetic `<address> <word>` fixture format to a real ELF32 executable and preserves the ELF artifact SHA-256 as source provenance.

## Accepted ELF scope

V1 accepts only inputs satisfying all of the following:

- ELF32;
- little-endian;
- `ET_EXEC`;
- `EM_MIPS`;
- a non-empty, file-backed, allocatable and executable `.text` section;
- `.text` address, file offset and size aligned to four bytes;
- an aligned ELF entry point inside `.text`;
- an ELF symbol table containing named `STT_FUNC` symbols in `.text`;
- the ELF entry point exactly matching a declared `STT_FUNC` symbol;
- no non-empty `SHT_REL` or `SHT_RELA` relocation sections;
- no allocatable semantic sections outside `.text`.

Standard MIPS metadata sections `.reginfo` and `.MIPS.abiflags` may be allocatable and are treated as container metadata only.

Anything outside this scope fails closed.

## Runtime sidecar

The runtime JSON remains deliberately separate from the executable container. It supplies deterministic execution policy and test-state information such as:

- memory size;
- initial register state;
- observed state slot;
- observable memory range;
- operation/reference-step limits;
- expected values for the bounded validation fixture.

The ELF is authoritative for executable layout:

- entry address comes from `e_entry`;
- function names/addresses come from `.text` `STT_FUNC` symbols;
- instruction words come from the ELF `.text` bytes.

If a runtime sidecar also declares entry/function information, it must agree exactly with the ELF or ingestion fails.

## Reused semantic path

After bounded ELF validation, the frontend calls the existing MIPS32 Expansion V1 lowering contract. The normalized source is identified as:

```text
architecture: mips32-le
adapter: openrecomp.mips32-elf-expansion-v1
```

The module namespace is:

```text
openrecomp.mips32.elf.expansion-v1.*
```

The ELF SHA-256 is propagated as `source_input_sha256` through normalized IR, Module Image, the independent MIPS32 reference result, Core V1 and native AOT results.

## Hosted proof fixture

The hosted gate assembles and links `examples/mips32-elf-v1/logic-shift.S` with GNU MIPS little-endian binutils into an actual `EM_MIPS` executable at guest address `0x1000`.

The resulting ELF is then validated and executed through:

1. bounded MIPS32 ELF ingestion;
2. MIPS32 Expansion V1 normalized IR;
3. independent MIPS32 reference execution;
4. Module Image V1 and Core V1;
5. portable C AOT and Native AOT ABI V1;
6. GCC and Clang native modules.

The reference, Core, GCC AOT and Clang AOT results must agree on the complete bounded architectural state and defined observables.

## Fail-closed cases

The unit/integration gates reject, among other cases:

- wrong ELF machine;
- big-endian ELF;
- entry outside `.text`;
- `.text` represented as `SHT_NOBITS`;
- missing static function symbols;
- runtime/ELF entry or function disagreement;
- relocations;
- unmodelled allocatable data sections;
- unsupported MIPS32 instructions through the existing Expansion V1 decoder/lowering contract;
- provenance disagreement between execution paths.

## Explicit non-claims

A V1 PASS does **not** prove support for:

- arbitrary MIPS32 ELF executables;
- big-endian MIPS32 ELF;
- dynamic linking;
- relocation processing;
- general `.data`, `.rodata`, `.bss`, TLS or loader semantics;
- shared objects or relocatable objects;
- arbitrary ABI/startup/runtime conventions;
- full MIPS32 ISA coverage;
- `div` / `divu` before architecture-neutral normalized semantics exist;
- proprietary executable ingestion.

Each of those requires a separate evidence gate.

## Required marker

```text
OPENRECOMP_MIPS32_ELF_INGESTION_V1=PASS
```
