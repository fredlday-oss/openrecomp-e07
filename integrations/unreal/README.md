# OpenRecomp Unreal Engine 5.8 interoperability proofs

OpenRecomp currently has two separate Unreal Engine 5.8 runtime proof paths. They share the goal of deterministic host-visible validation, but neither substitutes for the other.

## Original Gate B proof

The original synthetic workload uses the deterministic input sequence:

```text
{1,1,3,0,2,3,1,0}
```

Expected final state:

```text
x=15
y=6
frame=8
rgba=ff3aa7ff
```

Authoritative runtime marker:

```text
OPENRECOMP_GATE_B PASS x=15 y=6 rgba=ff3aa7ff frame=8
```

Status: **PROVEN-RUNTIME**

The separate visual replay reaches:

```text
OPENRECOMP_DEMO PASS x=15 y=6 rgba=ff3aa7ff frame=8
```

Status: **PASS / presentation evidence**

The visual replay does not replace the authoritative Gate B validation.

## Native AOT ABI V1 host proof

`OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1` is a second, independent runtime path. Unreal loads a real Windows x64 OpenRecomp AOT DLL through `FPlatformProcess`, resolves only `openrecomp_native_aot_query`, negotiates the frozen Native AOT ABI V1, binds deterministic E07 host callbacks and validates the established AOT result.

Authoritative runtime marker:

```text
OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

Status: **PROVEN-RUNTIME**

The engine-independent host core also passes the four Windows compiler combinations formed by MSVC/clang-cl hosts and MSVC/clang-cl AOT modules before the UE runtime gate is exercised.

The installed ABI header, six Native AOT host source files and tested synthetic DLL were verified byte-for-byte against the CI handoff by SHA-256 before the runtime result was promoted.

See [`../../docs/UNREAL_NATIVE_AOT_HOST_V1.md`](../../docs/UNREAL_NATIVE_AOT_HOST_V1.md) and [`../../evidence/UNREAL_NATIVE_AOT_HOST_V1_PUBLIC_SAFE.txt`](../../evidence/UNREAL_NATIVE_AOT_HOST_V1_PUBLIC_SAFE.txt).

## Public evidence policy

The public repository intentionally excludes Unreal `Saved/`, `Intermediate/`, `Binaries/`, launcher logs, authentication metadata and machine-local build output. Raw Unreal startup logs must not be published; only allow-listed OpenRecomp proof markers are retained as public evidence.
