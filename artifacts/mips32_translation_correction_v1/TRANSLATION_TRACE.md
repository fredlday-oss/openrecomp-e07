# Translation Trace

The translation trace validates the output of `tools/translate_mips32_elf_v1.py` on `artifacts/mips32_translation_v1/TRANSLATION_FIXTURE.elf`.

It generated a syntactically correct `ir.json` describing the deterministic blocks. The `sidecar.json` contains memory layouts and boundaries.

Execution trace was successfully tracked in the equivalence test `tools/test_mips32_equivalence_v1.py` which compiled it to C and executed natively.
