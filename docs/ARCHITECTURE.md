# OpenRecomp architecture

OpenRecomp separates guest-specific analysis from common translation/runtime infrastructure so multiple guest architectures and host environments can reuse the same contracts.

```text
guest executable / clean machine-code fixture
 -> architecture frontend / analysis
 -> normalized OpenRecomp IR V1
 -> Module Image V1
 -> common execution boundary
      |-> Core API V1 ReferenceExecutor
      `-> portable C AOT backend
              -> private generated execution surface
              -> Native AOT ABI V1 adapter
              -> versioned native module
 -> explicit host services
 -> native / WebAssembly / optional engine integration
```

The open core does not depend on Unreal Engine. Engine integration consumes the versioned native-module boundary in the same way any other host can.

## RV32I reference path

The hardened E07 V1.1 synthetic fixture remains the first **PROVEN** guest path. Its historical `0.1.1` proof IR is kept intact so the original evidence is not rewritten merely to introduce newer interfaces.

The RV32I bridge lowers that fixture into normalized IR V1 and reproduces the established result:

```text
checksum=122010428
return a0=48
operations=3866
```

That bridge is a bounded PASS for the current clean fixture/proven instruction subset, not a claim about arbitrary RV32I binaries.

## Normalized IR V1

[`IR_SPEC_V1.md`](IR_SPEC_V1.md) defines the architecture-neutral wire contract (`1.0.0`).

The normalized layer contains portable operations, explicit typed state, explicit memory semantics, named host calls and bounded control flow. Guest-specific rules such as MIPS delay slots, link-register conventions and zero-register behavior are frontend responsibilities and must be lowered before common execution or translation consumes V1.

The IR schema was not expanded to add Windows, Unreal, compiler-specific behavior or MIPS-specific operations. Those are downstream consumers/tests of the common boundary.

## Module Image V1

IR V1 describes normalized code semantics. Module Image V1 packages execution context separately:

- exact IR and host-contract hashes;
- initialized guest-memory segments;
- initial typed state;
- entry/observation contract;
- deterministic execution limits;
- source provenance.

This keeps executable packaging and environment binding out of the normalized instruction schema.

## Core API V1

[`CORE_API_V1.md`](CORE_API_V1.md) defines the reusable reference runtime around Module Image V1. The public reference surface includes `ModuleImage`, `GuestMemory`, `GuestState`, `HostBinding` and `ReferenceExecutor`.

The E07 Core API path reproduces the bridge/native/golden result exactly. The bounded MIPS32 vertical slice packages a second guest workload through the same Module Image machinery and executes it through the same `ReferenceExecutor` implementation.

## MIPS32 second-guest vertical slice

[`MIPS32_VERTICAL_SLICE_V1.md`](MIPS32_VERTICAL_SLICE_V1.md) documents the first implemented second-guest path.

Its clean little-endian machine-word fixture covers a bounded subset including arithmetic, signed/unsigned comparison, conditional branches, aligned memory access, direct call/return, direct jump and architectural delay slots.

Delay slots remain frontend behavior. The frontend captures branch/link semantics and emits ordinary normalized IR before the common layers see the program.

The independent machine-code reference and Core API path agree on:

```text
v0=31
memory_word=19
checksum=1950232098
delay_slots=7
```

This establishes a bounded MIPS32 PASS and a bounded two-guest generalization PASS for the shared IR/Module/Core boundaries. General MIPS32 support remains CANDIDATE.

## Portable C AOT backend

[`AOT_TRANSLATOR_V1.md`](AOT_TRANSLATOR_V1.md) defines the common ahead-of-time code-generation path.

The backend consumes validated IR V1 + Module Image V1. It does not decode RV32I or MIPS32 and contains no guest delay-slot/link-register logic. It emits deterministic portable C from already-normalized operations.

For the current clean fixtures, generated C is compiled independently and required to reproduce Core API results exactly:

```text
RV32I  checksum=122010428, return a0=48, operations=3866
MIPS32 checksum=1950232098, return v0=31, operations=100
```

## AOT hardening

[`AOT_HARDENING_V1.md`](AOT_HARDENING_V1.md) adds compiler-quality evidence without expanding the guest-support claim.

The current hardening gate includes:

- warning-clean GCC/Clang compilation with `-Werror`;
- architecture-independent normalized-operation coverage;
- little- and big-endian positive fixtures;
- nine deterministic Core API/AOT fault-equivalence classes;
- GCC/Clang ASan + UBSan smoke execution.

## Native AOT ABI V1

[`NATIVE_AOT_ABI_V1.md`](NATIVE_AOT_ABI_V1.md) defines the first versioned host-facing binary boundary. Its public header is `include/openrecomp/native_aot_abi_v1.h`.

Finished proof modules expose one stable OpenRecomp discovery symbol:

```text
openrecomp_native_aot_query
```

The returned V1 table includes capability flags, module/IR/host/source metadata, explicit host binding, execution/result/error functions, state inspection and memory inspection. Unsupported ABI versions and incorrect structure sizes reject fail-closed.

Native AOT ABI V1 remains **FROZEN-FOR-PORTABILITY-TESTING**. Linux GCC/Clang and Windows x64 MSVC/clang-cl cross the same unchanged contract for the current bounded RV32I and MIPS32 workloads.

## Windows x64 portability

[`AOT_WINDOWS_PORTABILITY_V1.md`](AOT_WINDOWS_PORTABILITY_V1.md) validates the native boundary on Windows x64.

Windows regenerates portable C and ABI adapters from the validated inputs and builds both workloads under MSVC and clang-cl. The public V1 layout is pinned, DLL exports are checked, ABI negotiation is exercised, and observable results are compared with Linux/Core references.

The first Windows run exposed a real CRLF byte-integrity failure in a hashed host contract. `.gitattributes` now pins proof/source text to LF; the Module Image hash validation was not weakened.

## Host runtime boundary

`HostBinding` and Native AOT ABI V1 keep normalized guest behavior separate from concrete host services. Hosts expose versioned capabilities and callbacks rather than guest-architecture-specific interfaces.

Compatibility remains fail-closed: unsupported IR, invalid module metadata, integrity mismatches, ABI version/size mismatches, malformed host bindings, memory faults and execution-limit violations reject rather than being interpreted heuristically.

## Unreal Engine interoperability

Unreal Engine is an optional host-integration demonstration, not part of the required open core.

There are two separate local UE5.8 runtime paths:

```text
OPENRECOMP_GATE_B PASS x=15 y=6 rgba=ff3aa7ff frame=8
```

and the Native AOT path:

```text
RV32I IR V1
 -> Module Image V1
 -> portable C AOT
 -> Windows x64 DLL
 -> openrecomp_native_aot_query
 -> Native AOT ABI V1
 -> FPlatformProcess loader
 -> deterministic Unreal host callbacks
 -> validated result
```

The engine-independent Native AOT host core is reproducibly tested in GitHub Actions across the four MSVC/clang-cl host/module compiler combinations. A separate local UE5.8 Windows x64 PIE run produced:

```text
OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

The UE runtime result is therefore recorded as **PASS — local runtime evidence**, while the Windows host-core layer is a reproducible CI PASS. The installed source/header/DLL set was matched to the CI handoff by SHA-256 before the local run was retained.

## Current generalization boundary

- RV32I E07 synthetic path: **PROVEN**
- Native/WebAssembly equivalence: **PASS**
- Normalized IR V1: **FROZEN-FOR-IMPLEMENTATION**
- RV32I -> IR V1 bridge: **PASS**
- Core API V1: **PASS**
- MIPS32 vertical slice: **PASS — bounded**
- Shared IR/Module/Core across RV32I + MIPS32: **PASS — bounded**
- Portable C AOT backend: **PASS — bounded dual-guest**
- AOT compiler/fault/sanitizer hardening: **PASS — bounded**
- Native AOT ABI V1: **FROZEN-FOR-PORTABILITY-TESTING**
- Linux/Windows x64 Native AOT ABI execution: **PASS — bounded**
- Unreal Native AOT host core: **PASS — reproducible Windows CI**
- UE5.8 Native AOT runtime: **PASS — local runtime evidence**
- Original UE5.8 Gate B runtime: **PASS — local runtime evidence**
- General MIPS32 support: **CANDIDATE**
- macOS / Windows ARM64 / Windows x86 parity: **CANDIDATE**
- Release-quality compiler/plugin pipeline: **CANDIDATE**

Broader architecture, platform, deployment and release-quality support remains evidence-gated rather than inferred from the current vertical slices.
