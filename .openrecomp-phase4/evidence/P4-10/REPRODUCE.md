# Reproducing the OpenRecomp Phase-4 generic runtime / platform layer

This package is a deterministic snapshot of the audited Phase-4 tree
(branch `phase4/generic-runtime-v1`, descending from the frozen Phase-3 tag
`openrecomp-phase3-pass` = `e16e4b29b90f379615f1af97e47747cd1d531796`).

## Requirements

- Python 3.11 (standard library only for the gates).
- `git` with the recorded repository history (the Phase-1/Phase-2/Phase-3
  frozen tags).
- External toolchains, pinned by recorded identity and not shipped:
  - `zig` 0.13.0 (`zig cc` = clang 18.1.5, LLD 18.1.6) at
    `.openrecomp-phase3/tools/zig/zig.exe` for the MIPS32 fixtures;
  - LLVM/clang-cl 22.1.8 plus `lld-link.exe` for the deterministic host
    build pipeline.
  The fixture and translation are rebuilt from source by the gates; no
  prebuilt binary is required.

## Package contents

- `control/` - the Phase-4 control plane (policy, scope, queue, state,
  handoff, evidence schema, source manifest).
- `src/` - the Phase-4 runtime/ABI/memory/service/I/O/adapter/graphics-audio,
  fixture translation and reference modules.
- `contracts/`, `ports/` - the generated-code <-> runtime ABI contract
  document, C header and the frozen Phase-3 instance profile.
- `fixture/` - the original Apache-2.0 interactive fixture sources and its
  deterministic input plan.
- `gates/` - every Phase-4 stage gate.
- `generated/` - the generated host translation for the fixture
  (`p4_fixture_program.c`, `p4_fixture_support.c`), pinned to
  `abd138ea` / `755a004630`.
- `evidence/` - the tracked stage evidence `P4-00` .. `P4-09`.
- `P4_PACKAGE_MANIFEST.json` - member sizes, sha256 hashes and the canonical
  package fingerprint.

## Reproduction

1. Check out the audited commit and verify the frozen chain:

       git rev-parse openrecomp-phase3-pass^{commit}
       python tools/test_phase4_boundary_v1.py

2. Rebuild the fixture and its translation deterministically:

       python tools/test_phase4_fixture_v1.py
       python tools/test_phase4_adapter_execution_v1.py

3. Re-run the end-to-end proof with the independent reference:

       python tools/test_phase4_generic_runtime_proof_v1.py

4. Rebuild this package and verify its manifest:

       python tools/test_phase4_package_regression_v1.py

5. Whole-regression audit (P4-90):

       python tools/test_phase4_whole_regression_v1.py

## Reproducibility bound

Package bytes are reproducible from the same tree state. The external
toolchains are pinned by identity in the stage evidence; rebuilding the
fixture ELF and the native executable requires those exact toolchains.
