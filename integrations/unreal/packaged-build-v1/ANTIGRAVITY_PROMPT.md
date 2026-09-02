# Antigravity task: OPENRECOMP_UNREAL_PACKAGED_BUILD_V1

Execute the packaged-build runtime gate exactly as provided. Do not redesign the plugin, Native AOT ABI, IR, Core API, or proof workload.

## Inputs

- This extracted handoff directory contains `OpenRecompRuntime/`, the validated synthetic Native AOT DLL, packaging/runtime scripts, a SHA-256 manifest, and provenance.
- Use a real Unreal Engine 5.8 Windows x64 project supplied by the operator.
- Use the installed Unreal Engine 5.8 root supplied by the operator.

## Rules

- Do not edit OpenRecomp source to make compilation/package/runtime pass.
- Do not change expected state/checksum/operation values.
- Do not replace the validated DLL.
- If UHT/UBT/cook/package fails, stop and return the failure evidence instead of patching around it.
- Do not publish raw Unreal startup/launcher/authentication logs.
- Do not claim Shipping-build parity; this gate uses a Development packaged build.

## Procedure

1. Read `OPENRECOMP_PACKAGED_BUILD_V1_PROVENANCE.txt` and `OPENRECOMP_PACKAGED_BUILD_V1_SHA256SUMS.txt`.
2. Verify every handoff file covered by the manifest before installation.
3. Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\INSTALL_FROM_HANDOFF.ps1 -ProjectDir <PROJECT_DIRECTORY> -ForceReplace
```

4. Package with:

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_PACKAGE.ps1 -ProjectFile <PROJECT_UPROJECT> -UE5Root <UE_5.8_ROOT> -ArchiveRoot <EMPTY_ARCHIVE_DIRECTORY>
```

5. Do not continue unless `OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_PACKAGE=PASS` is produced.
6. Run the packaged executable proof:

```powershell
powershell -ExecutionPolicy Bypass -File .\RUN_PACKAGED_PROOF.ps1 -ArchiveRoot <ARCHIVE_DIRECTORY>
```

7. Require the exact runtime line:

```text
OPENRECOMP_UNREAL_PACKAGED_BUILD_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

8. Create `OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_RUNTIME_RESULT.zip` containing only:
   - `PACKAGED_BUILD_RESULT.txt`
   - `OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_RUNTIME_PUBLIC_SAFE.txt`
   - `OPENRECOMP_PACKAGED_BUILD_V1_PROVENANCE.txt`
   - `OPENRECOMP_PACKAGED_BUILD_V1_SHA256SUMS.txt`
   - a short `RESULT.md` stating package PASS/runtime PASS or the precise failed gate.

Do not include raw stdout/stderr, Unreal logs, Saved/Logs, packaged binaries, credentials, launcher data, or account identifiers in the returned result ZIP.
