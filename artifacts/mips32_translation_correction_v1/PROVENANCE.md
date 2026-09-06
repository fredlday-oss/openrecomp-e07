# PROVENANCE

- **Baseline OpenRecomp commit:** 14b1050f193a4a8770a398c29759af1186d553cc
- **Final commit:** cb87b56e4a5ce13bb1bab0e6d140cb1e2af1a98a
- **Branch:** main
- **Host OS:** Windows
- **Python version:** 3.11+
- **Compiler/toolchain versions:** MSVC via Python setuptools/distutils
- **Fixture generation command:** `python scratch/build_fixture.py`
- **Fixture SHA-256:** `c9b60aa0df3f95d7d35bbae92c2a99ccc65646bfb3ee44e7c3fc546146ee6e88` (see fixture_manifest.json)
- **Translation command:** `python tools/translate_mips32_elf_v1.py artifacts/mips32_translation_v1/TRANSLATION_FIXTURE.elf contracts/host_contract.json artifacts/mips32_translation_v1/ir.json artifacts/mips32_translation_v1/sidecar.json`
- **Packaging command:** `python tools/package_ir_v1_module.py artifacts/mips32_translation_v1/ir.json artifacts/mips32_translation_v1/sidecar.json contracts/host_contract.json artifacts/mips32_translation_v1/packaged_module.json`
- **Build command:** `python tools/aot_c_backend_v1.py artifacts/mips32_translation_v1/packaged_module.json artifacts/mips32_translation_v1/ir.json contracts/host_contract.json artifacts/mips32_translation_v1/generated.c`
- **Execution command:** `cmd /c "artifacts/mips32_translation_v1/host_execution.exe & echo %errorlevel%"`
- **Reference result:** 45
- **Native result:** 45
- **Test commands:** `python tools/test_mips32_microtests_v1.py`
- **Date/Time:** 2026-09-06T09:12:00+01:00
