# OPENRECOMP_UNREAL_PACKAGED_BUILD_V1 runtime gate

This handoff validates packaged Windows x64 deployment of the existing OpenRecompRuntime plugin and frozen Native AOT ABI V1 using the clean synthetic RV32I module.

## Evidence boundary

Hosted GitHub Actions verifies the plugin/source contract, deterministic handoff packaging, the validated synthetic DLL, and engine-independent execution. Unreal Engine itself is not present on hosted runners.

The local gate therefore requires Unreal Engine 5.8 on Windows x64 and uses a **Development** packaged build. This frontier does not claim Shipping-build parity, arbitrary Unreal projects, other host platforms, or general guest-binary compatibility.

## Required local sequence

1. Install `OpenRecompRuntime` from the handoff into the target UE5.8 project with `INSTALL_FROM_HANDOFF.ps1`.
2. Package the project with `RUN_PACKAGE.ps1`.
3. Launch the packaged executable with `RUN_PACKAGED_PROOF.ps1`.
4. Require this exact marker:

```text
OPENRECOMP_UNREAL_PACKAGED_BUILD_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

5. Return only the public-safe evidence, package result, provenance, and plugin manifest. Do not publish raw Unreal startup/authentication logs.

A successful package step also requires the staged archive to contain `openrecomp-e07-rv32i.dll`; the plugin stages that DLL as a Win64 `NonUFS` runtime dependency.
