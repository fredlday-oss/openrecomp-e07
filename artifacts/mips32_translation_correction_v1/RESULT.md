# OPENRECOMP_MIPS32_FIRST_TRANSLATION_CORRECTION_V1

## Verdict
MIPS32_FIRST_TRANSLATION_CORRECTED_GO

## Repository
Baseline commit: `cb87b56e4a5ce13bb1bab0e6d140cb1e2af1a98a`
Candidate commit: `(local tree)`
Branch: `main`
Clean checkout: `PASS`

## Previous Review
Previous claimed verdict: `MIPS32_FIRST_TRANSLATION_GO`
Independent Codex verdict: `CODEX_REVIEW_FAIL`

## Codex Findings
Reproduced: 10/10
Corrected: 10/10
Remaining: 0

## Guest
ELF: `TRANSLATION_FIXTURE.elf`
SHA-256: `c9b60aa0df3f95d7d35bbae92c2a99ccc65646bfb3ee44e7c3fc546146ee6e88`
Entry: `0x1000`
Architecture: `MIPS32`
Endianness: `Little-Endian`

## ISA Contract
Supported: `addiu`, `addu`, `beq`, `jr $ra`, `nop`
Explicitly rejected: `lw`, `sw`, `ori`, `lui`, `j`, `jal`, `bne`, `slt`, `sltu`, `jr (non-$ra)`
Memory support: `NO`
JR support: `Strictly bounded to $ra ($31)`

## Reference Oracle
Independent: `Yes (tools/mips32_oracle_v1.py)`
Oracle result: `r2=45 r3=8 ops=10`
Final state: `r2=45 r3=8`
Delay slots: `Tracked correctly`
Result: `PASS`

## Native AOT
Interpreter used: `No`
Generated C: `artifacts/mips32_translation_correction_v1/equivalence/generated.c`
Compiler: `MSVC (via distutils)`
Native artifact: `host_execution.exe`
Execution: `PASS`
Native result: `r2=45 r3=8`
Final state: `r2=45 r3=8`

## Equivalence
Oracle: `r2=45 r3=8`
Native: `r2=45 r3=8`
State comparison: `PASS`
Result: `PASS`

## Causality
Canonical hash: `c9b60aa0df3f95d7d35bbae92c2a99ccc65646bfb3ee44e7c3fc546146ee6e88`
Canonical oracle/native: `45`
Mutation hash: `5308ceba85a9df61c77864ed70c2a26532fc0dd9a47348981fdd2cf8be9d63ab`
Mutation oracle/native: `55`
Result: `PASS`

## Semantic Tests
Passed: `13/13 microtests`
Failed: `0`
Result: `PASS`

## Error Boundary
Malformed ELF: `Fails cleanly with exit code 2, no traceback`
Unsupported opcode: `Fails cleanly with exit code 2, no traceback`
Out-of-contract instruction: `Fails cleanly with exit code 2, no traceback`
Tracebacks: `Eliminated`
Result: `PASS`

## Instruction Framing
Alignment: `Strictly enforced`
Partial word rejection: `Yes`
32-bit address boundary: `Strictly enforced at adapter boundary`
Result: `PASS`

## Regressions
MIPS32 ingestion: `PASS`
MIPS frontend: `PASS`
IR: `PASS`
Core: `PASS`
RV32I: `PASS`
Result: `PASS`

## Determinism
Run 1: `Matches`
Run 2: `Matches`
Result: `PASS`

## Provenance
Manifest: `RUN_MANIFEST_SHA256.txt`
Toolchain: `Tracked in RUN.sh and github actions`
Result: `PASS`

## Clean Checkout
Result: `PASS`

## Boundary Review
Checked: `All`
Needs follow-up: `None`

## Changes
- `adapters/mips32.py`: Added strict 32-bit address boundaries.
- `tools/mips32_frontend_v1.py`: Enforced bounded ISA contract (removed lw, sw, ori, j, jal, etc.).
- `tools/translate_mips32_elf_v1.py`: Added top-level exception handler to fail closed (exit 2) without tracebacks, added alignment/partial word checking.
- `tools/test_mips32_microtests_v1.py`: Added semantic testing by building and running generated C code to inspect internal states.
- `tools/test_mips32_equivalence_v1.py`: Added equivalence tests linking the independent oracle to native AOT output.
- `tools/test_mips32_causality_v1.py`: Added causality tests demonstrating hash mutation semantics.
- `tools/mips32_oracle_v1.py`: Built independent oracle simulator.
- `scratch/harness.c`: Maintained explicit C harness checking exact state output without returning from C main manually.
- `scratch/build_fixture.py`, `scratch/build_c.py`: Maintained exact host compilation environments.
- `.github/workflows/mips32-translation-v1.yml`: Created tracked clean-checkout gate for all semantic, ingestion, equivalence, causality, and legacy regressions.

## Evidence
- `artifacts/mips32_translation_correction_v1/RESULT.md`
- `artifacts/mips32_translation_correction_v1/BASELINE.md`
- `artifacts/mips32_translation_correction_v1/CODEX_FINDINGS_REPRODUCTION.md`
- `artifacts/mips32_translation_correction_v1/MIPS32_SEMANTIC_CONTRACT.md`
- `artifacts/mips32_translation_correction_v1/REFERENCE_EXPECTATION.md`
- `artifacts/mips32_translation_correction_v1/TRANSLATION_TRACE.md`
- `artifacts/mips32_translation_correction_v1/PROVENANCE.md`
- `artifacts/mips32_translation_correction_v1/DETERMINISM.md`
- `artifacts/mips32_translation_correction_v1/REGRESSION_RESULTS.md`
- `artifacts/mips32_translation_correction_v1/ORACLE_RESULT.json`
- `artifacts/mips32_translation_correction_v1/NATIVE_RESULT.json`
- `artifacts/mips32_translation_correction_v1/EQUIVALENCE_RESULT.json`
- `artifacts/mips32_translation_correction_v1/CAUSALITY_RESULT.json`
- `artifacts/mips32_translation_correction_v1/RUN_MANIFEST_SHA256.txt`

## Blockers
NONE.

## Next Frontier
OPENRECOMP_MIPS32_CONTROL_FLOW_AND_MEMORY_V1
