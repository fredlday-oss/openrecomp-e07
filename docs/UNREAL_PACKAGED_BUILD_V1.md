# Unreal packaged build V1

`OPENRECOMP_UNREAL_PACKAGED_BUILD_V1` validates deployment of the existing `OpenRecompRuntime` plugin and frozen Native AOT ABI V1 through a real Unreal Engine 5.8 Windows x64 **Development** packaged build.

This is a bounded host/deployment result. It does not change guest execution semantics, IR V1, Module Image V1, Core API V1 or Native AOT ABI V1.

## Hosted CI layer

GitHub-hosted CI does not contain Unreal Engine. The hosted packaged-build gate therefore validates the parts that can be reproduced without UE5.8:

- the existing Plugin V1 source/ABI contract;
- the packaged-build source and Win64 `NonUFS` staging contract;
- deterministic RV32I module generation;
- MSVC build of the validated synthetic Native AOT DLL;
- engine-independent host-core execution with state `48`, checksum `122010428` and `3866` operations;
- Windows PowerShell 5.1 parsing and execution of the public-safe collector path;
- deterministic packaged-build handoff generation.

The final local-runtime handoff was produced from PR #19 source head:

```text
334a4ba603618b243c896c8122fd4cd730730e56
```

The corresponding hosted workflow artifact SHA-256 is:

```text
63f50d8dc25065ba51de06e43010a10dda12147ef311c196ba4f34e2fb5a0574
```

The deterministic inner handoff SHA-256 is:

```text
626d906a348122b4f7ab3d8f886a38a5060befca8a6a31ee3a6af9b7551e5fe9
```

The validated Native AOT DLL SHA-256 carried by that handoff is:

```text
f6a8679cbd763529b6dd5f33c2ffeac8e269d8f4e2d859e8b1c48dec8cc6b2b6
```

## UE5.8 Windows x64 Development package — local packaged runtime PASS

The exact CI handoff was installed into the existing UE5.8 project, then UE `BuildCookRun` produced a Windows x64 Development package. The packaged archive contained the validated Native AOT DLL with the exact CI SHA-256 above.

The packaged executable was then launched outside Editor/PIE with the opt-in `-OpenRecompPackagedProof` path. Execution crossed `UOpenRecompSubsystem` and the frozen Native AOT ABI V1 and produced the exact public-safe marker:

```text
OPENRECOMP_UNREAL_PACKAGED_BUILD_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

The returned public-safe result also records:

```text
OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_PACKAGE=PASS
CONFIGURATION=Development
PLATFORM=Win64
STAGED_DLL_SHA256=f6a8679cbd763529b6dd5f33c2ffeac8e269d8f4e2d859e8b1c48dec8cc6b2b6
```

The returned result ZIP SHA-256 is:

```text
2ca45d54c6d23bb0e14f896f324140679e20264812d63c975c4e8ca3fbcb7f21
```

Only the public-safe provenance/result files are treated as project evidence. Raw Unreal startup/launcher logs and the packaged binaries are not published.

## Classification

- hosted packaged-build source/module/handoff gate: **PASS — reproducible CI**;
- UE5.8 Windows x64 Development cook/package: **PASS — local environment**;
- packaged executable execution outside Editor/PIE: **PASS — local packaged runtime evidence**;
- validated Native AOT DLL staging identity: **PASS**;
- Shipping configuration parity: **not proven**;
- other Unreal versions/host platforms: **not proven**;
- arbitrary Unreal-project compatibility: **not proven**.

The local runtime result is not promoted to unqualified `PROVEN-RUNTIME` because UE5.8 is not available in project-controlled hosted CI. A self-hosted UE runner would strengthen reproducibility without changing the execution result itself.
