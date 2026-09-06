# MIPS32 ELF Contract

- **Class**: ELFCLASS32 (1).
- **Architecture**: EM_MIPS (8).
- **Endianness**: Little-endian (ELFDATA2LSB = 1) supported. Big-endian fails closed.
- **Header Sizes**: e_ehsize >= 52, e_phentsize >= 32.
- **Executable-region authority**: Program Headers (PT_LOAD segments with PF_X flag).
- **Segment Bounds**:
  - p_filesz <= available file bytes from p_offset.
  - p_memsz >= p_filesz.
  - p_offset + p_filesz must not overflow or exceed file size.
  - p_vaddr + p_memsz must not overflow 32-bit address space.
- **Overlap Rule**: Overlapping executable memory regions are rejected (fail-closed).
- **Zero-sized Segments**: PT_LOAD with p_memsz == 0 is ignored.
- **Sections**: Section headers are not used for executable code extraction (SHT_NOBITS ignored).
- **Entry Point**: e_entry must be contained within a valid executable segment.
- **Unsupported features**: Big-endian MIPS32, 64-bit ELF (ELFCLASS64), non-executable load regions outside metadata.
