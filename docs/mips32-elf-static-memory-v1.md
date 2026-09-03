# MIPS32 ELF Static Memory V1

This milestone extends the bounded little-endian MIPS32 ELF ingestion path to deterministic static memory initialization.

## In scope

- ELF32, little-endian, `ET_EXEC`, `EM_MIPS`.
- Existing bounded Expansion V1 instruction/control-flow semantics.
- Real GNU-linked executable input.
- Required static sections:
  - file-backed allocatable read-only non-executable `.rodata`;
  - file-backed allocatable writable non-executable `.data`;
  - allocatable writable non-executable `SHT_NOBITS` `.bss`.
- Deterministic guest-memory placement from ELF section virtual addresses.
- `.rodata` and `.data` initial bytes copied into Module Image V1 memory segments.
- `.bss` represented as an explicit zero-filled Module Image V1 memory segment.
- Static section alignment, bounds, overlap and ELF attribute validation before normalization.
- Guest loads/stores through the existing architecture-neutral Core V1 memory operations.
- Full-ELF SHA-256 provenance through IR, Module Image, independent reference, Core and native AOT paths.
- Independent reference = Core V1 = GCC native AOT = Clang native AOT for the rights-safe fixture.
- Deterministic frontend, Module Image, portable C AOT and Native AOT ABI regeneration.

## Backward-compatibility boundary

The existing `openrecomp.mips32-elf-expansion-v1` text-only adapter is unchanged and continues to reject allocatable `.rodata`, `.data` and `.bss` sections. Static memory is accepted only through the explicit `openrecomp.mips32-elf-static-memory-v1` adapter.

## Current permission boundary

V1 validates ELF section attribute classification at ingestion time. Module Image V1 currently represents initialized bytes and addresses, not persistent read/write/execute permission bits. Therefore this milestone does **not** claim runtime write-protection enforcement for `.rodata`.

## Out of scope

- dynamic linking;
- relocation processing;
- TLS;
- GOT/PLT semantics;
- shared objects or PIE;
- big-endian ELF;
- arbitrary section layouts;
- arbitrary MIPS32 ISA coverage;
- runtime enforcement of ELF page/section permissions;
- proprietary binaries.

## Proof fixture

The rights-safe fixture uses a deterministic GNU MIPS linker layout:

- `.text`: `0x1000`;
- `.rodata`: `0x2000`, 4 bytes containing word `0x11223344`;
- `.data`: `0x3000`, 16 file-backed bytes containing word `0x01020304` followed by twelve linker-initialized zero bytes;
- `.bss`: `0x3010`, four zero-filled bytes.

The 16-byte `.data` extent is an observed property of the real GNU MIPS linker output used by this gate and is validated explicitly rather than hidden. The entire section is treated as initialized ELF data and carried into Module Image V1.

The guest reads `.rodata` and the first `.data` word, writes their sum to `.data`, verifies the real `.bss` at `0x3010` initially reads as zero, writes the same result to `.bss`, and returns that value. The final observable 20-byte memory window spans the complete `.data` section and `.bss`, so both initialized-data preservation and BSS zero-fill/write semantics are visible.

The bounded upstream gate is `MIPS32 ELF static memory V1` / `mips32-elf-static-memory-v1`.
