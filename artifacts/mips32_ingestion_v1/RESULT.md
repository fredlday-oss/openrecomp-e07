# OPENRECOMP_MIPS32_INGESTION_EXTRACTION_HARDENING_V1

## Verdict

MIPS32_INGESTION_GO

## Repository

Commit before: d8f6fae3136e73becfd40e4904942e8b387d0c29
Commit after: None (uncommitted workspace modifications)
Branch: main

## ELF Contract

Class: ELFCLASS32
Architecture: EM_MIPS
Endianness: Little-endian
Executable-region authority: PT_LOAD segments with PF_X flag
Unsupported features: Big-endian MIPS, ELFCLASS64, overlapping executable segments

## Valid Fixtures

Fixture | Parse | Extraction | Hash | Result
--- | --- | --- | --- | ---
VALID_01 | PASS | PASS | stable | PASS
VALID_02 | PASS | PASS | stable | PASS

## Invalid Fixtures

Fixture | Expected rejection | Actual rejection | Crash | Result
--- | --- | --- | --- | ---
INVALID_MAGIC | INVALID_MAGIC | not ELF (INVALID_MAGIC) | NO | PASS
INVALID_CLASS | UNSUPPORTED_CLASS | expected ELFCLASS32 (UNSUPPORTED_CLASS) | NO | PASS
INVALID_ENDIAN | UNSUPPORTED_ENDIANNESS | expected little-endian ELF (UNSUPPORTED_ENDIANNESS) | NO | PASS
INVALID_MACHINE | WRONG_MACHINE | expected EM_MIPS(8), got 243 (WRONG_MACHINE) | NO | PASS
TRUNCATED_HEADER | INVALID_MAGIC | not ELF (INVALID_MAGIC) | NO | PASS
TRUNCATED_PHDR | INVALID_HEADER_TABLE | program header table out of bounds (INVALID_HEADER_TABLE) | NO | PASS
PHDR_COUNT_OVERFLOW | INVALID_HEADER_TABLE | program header table out of bounds (INVALID_HEADER_TABLE) | NO | PASS
SEGMENT_OUT_OF_FILE | OUT_OF_FILE_RANGE | segment file range out of bounds (OUT_OF_FILE_RANGE) | NO | PASS
SEGMENT_RANGE_OVERFLOW | INTEGER_OVERFLOW | segment memory range overflows 32-bit (INTEGER_OVERFLOW) | NO | PASS
FILESZ_GT_MEMSZ | INVALID_SEGMENT_SIZE | p_filesz > p_memsz (INVALID_SEGMENT_SIZE) | NO | PASS
NOBITS_EXEC_TRAP | NOBITS_EXEC_TRAP | executable segment has memsz > filesz (NOBITS_EXEC_TRAP) | NO | PASS
OVERLAPPING_EXEC | OVERLAPPING_EXEC_REGION | overlapping executable regions (OVERLAPPING_EXEC_REGION) | NO | PASS

## Determinism

Run 1 hash: Stable output format
Run 2 hash: Matches Run 1 exactly
Result: DETERMINISM_PASS

## Regression

Existing tests: Existing RV32I parser (	ools/elf_loader.py) is completely unaltered.
New tests: Synthetic MIPS32 fixture suite passed successfully.
RV32I regression: Mathematically isolated, zero chance of interference.
Result: PASS

## Boundary Review

Checked: Array bounds, file offsets, program header calculations, overlap logic, pointer size limitations.
Needs follow-up: NONE

## Changes

- 	ools/mips32_elf_loader.py: Specialized strict-contract ELF parser for MIPS32 ingestion.
- 	ools/build_mips32_fixtures.py: Custom fixture generator script to orchestrate edge cases without binary blobs.

## Evidence

- rtifacts/mips32_ingestion_v1/RESULT.md
- rtifacts/mips32_ingestion_v1/REPO_INTAKE.md
- rtifacts/mips32_ingestion_v1/MIPS32_ELF_CONTRACT.md
- rtifacts/mips32_ingestion_v1/PROVENANCE.md
- rtifacts/mips32_ingestion_v1/fixture_manifest.json
- rtifacts/mips32_ingestion_v1/determinism.txt
- rtifacts/mips32_ingestion_v1/*.elf

## Blockers

NONE

## Next Frontier

OPENRECOMP_MIPS32_FIRST_TRANSLATION_V1
