# MIPS32 ELF Ingestion Repository Intake

## Git Context
- **Commit:** d8f6fae3136e73becfd40e4904942e8b387d0c29
- **Branch:** main
- **Status:** Clean working directory

## Inventory
- **Relevant files:**
  - 	ools/elf_loader.py: Current ELF loader, supports only RV32I and uses section-based extraction (.text).
  - 	ools/mips32_frontend_v1.py: Current MIPS32 frontend, ingests .hex files rather than ELFs.
  - 	ools/make_ir.py: Converts parsed ELF + RV32I into IR.
  - RUN.sh: Main test script validating the RV32I ingestion and end-to-end functionality.
- **Existing architecture abstraction:**
  - Architectures are abstracted in dapters/ (dapters/riscv32.py, dapters/mips32.py).
- **Existing RV32I ingestion path:**
  - Synthetic ELF -> 	ools/elf_loader.py -> Section-based parsing (.text) -> 	ools/make_ir.py -> IR JSON.
- **Reusable components:**
  - Struct unpacking logic from 	ools/elf_loader.py.
  - Hashing routines for provenance.
- **Missing MIPS32 functionality:**
  - No MIPS32 ELF parsing.
  - No program-header (PT_LOAD) based executable region extraction.
  - No fail-closed validation for endianness, segment bounds, or overlapping segments.
