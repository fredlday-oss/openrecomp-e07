# OpenRecomp Native AOT ABI V1

**Frontier:** `OPENRECOMP_NATIVE_AOT_ABI_V1`  
**Contract state:** **FROZEN-FOR-PORTABILITY-TESTING**  
**Execution status:** **PASS — bounded Linux GCC/Clang + Windows x64 MSVC/clang-cl dual-architecture validation**

Native AOT ABI V1 defines the first public binary boundary between an OpenRecomp native AOT module and a host process.

It is deliberately separate from normalized IR V1, Module Image V1 and the portable C backend. Guest-specific rules are already normalized before this boundary; the ABI exposes execution, host binding and observation services rather than guest ISA semantics.

## Public header

The public C contract is:

```text
include/openrecomp/native_aot_abi_v1.h
```

The ABI uses fixed-width integer types for cross-toolchain data fields and function parameters. Pointer fields are used only where a process-local pointer is required, such as callback user data, strings and output buffers.

The ABI version constant is:

```text
OPENRECOMP_NATIVE_AOT_ABI_V1 = 0x00010000
```

## Single public entry point

A V1 native module exposes one stable OpenRecomp symbol:

```c
const openrecomp_native_aot_api_v1 *
openrecomp_native_aot_query(uint32_t requested_abi,
                            uint32_t minimum_api_size);
```

The Linux proof links the underlying generated execution functions with hidden visibility. The Windows proof independently inspects DLL exports with `dumpbin`. Both require the stable OpenRecomp surface to expose the V1 query while keeping the generated execution surface private.

The query succeeds only when the caller requests the exact V1 version and the exact V1 structure size. Unsupported versions, zero/short sizes and oversized layouts fail closed with a null result.

## Module API table

A successful query returns an immutable `openrecomp_native_aot_api_v1` table owned by the module. It contains:

- ABI structure size and version;
- capability flags;
- module identifier;
- Module Image format version;
- normalized IR version;
- host-contract version;
- source architecture;
- source-input SHA-256 provenance;
- source address width and endianness;
- host binding;
- execution;
- observed state and function return;
- operation count and deterministic error text;
- state enumeration/value inspection;
- guest-memory size/read access.

The metadata is generated from the already-validated `ModuleImage` rather than accepted from unvalidated command-line strings.

## Capability flags

V1 currently defines:

```text
OPENRECOMP_NATIVE_AOT_CAP_STATE_INSPECTION
OPENRECOMP_NATIVE_AOT_CAP_MEMORY_READ
OPENRECOMP_NATIVE_AOT_CAP_HOST_CALLS
OPENRECOMP_NATIVE_AOT_CAP_DETERMINISTIC_FAULTS
```

`HOST_CALLS` is emitted only when the normalized module declares required host symbols. The state, memory-read and deterministic-fault capabilities are present for current V1 modules.

## Host binding

Hosts bind through `openrecomp_native_aot_host_v1`:

```text
struct_size
abi_version
user_data
call
```

The callback receives the opaque `user_data` pointer, normalized host-symbol name, fixed-width argument count and argument array, plus explicit output-value and has-value fields.

The module rejects a host structure whose size or ABI version does not exactly match V1, or whose callback is null. Passing a null host pointer explicitly unbinds the host and is accepted.

The ABI adapter bridges this public callback to the portable C backend's private link-time host-call surface. The private surface is an implementation detail and is not part of the V1 compatibility promise.

## Deterministic adapter generation

`tools/native_aot_abi_v1.py` consumes the same validated inputs as the AOT module:

```text
Module Image V1
normalized IR V1
host contract
```

It emits a deterministic module-specific C adapter containing immutable metadata and the V1 dispatch table. Linux and Windows gates regenerate adapters from validated inputs and require repeated output to be byte-identical.

## Linux execution evidence

The finished RV32I and MIPS32 Linux shared modules are built from portable-C AOT output plus the Native AOT ABI V1 adapter. Both are compiled independently with GCC and Clang using warning-as-error builds and hidden default symbol visibility.

For every compiler/architecture combination, CI requires:

```text
OPENRECOMP_NATIVE_AOT_ABI_V1_QUERY=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_VERSION_REJECTION=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_SIZE_REJECTION=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_METADATA=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_HOST_NEGOTIATION=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_PRIVATE_SURFACE=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_LOADER=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1=PASS
```

The architecture-neutral results remain:

```text
RV32I checksum=122010428, return a0=48, operations=3866
MIPS32 checksum=1950232098, return v0=31, operations=100
OPENRECOMP_IR_V1_AOT_DUAL_ARCH=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_DUAL_ARCH=PASS
```

The RV32I path exercises real host calls through the V1 callback bridge. The MIPS32 fixture is host-call-free, so together the current fixtures test both host-bound and host-free module configurations.

## Windows x64 execution evidence

[`AOT_WINDOWS_PORTABILITY_V1.md`](AOT_WINDOWS_PORTABILITY_V1.md) validates this **unchanged header** on Windows x64.

MSVC and clang-cl independently compile a static layout probe that requires:

```text
sizeof(openrecomp_native_aot_host_v1) = 24
sizeof(openrecomp_native_aot_api_v1)  = 168
```

Every public V1 field offset is also statically pinned. Both compilers then build RV32I and MIPS32 DLLs under `/W4 /WX`, `dumpbin /exports` confirms `openrecomp_native_aot_query` is the only OpenRecomp-named DLL export, and all four DLLs pass the same V1 negotiation/metadata/host/loader tests.

Both Windows toolchains reproduce the established Core/Linux results exactly:

```text
RV32I checksum=122010428, return a0=48, operations=3866
MIPS32 checksum=1950232098, return v0=31, operations=100
OPENRECOMP_AOT_WINDOWS_MSVC_CLANGCL_PARITY=PASS
OPENRECOMP_AOT_WINDOWS_LINUX_REFERENCE_PARITY=PASS
OPENRECOMP_AOT_WINDOWS_PORTABILITY_V1=PASS
```

The first Windows run also proved that the byte-integrity contract fails closed: CRLF checkout conversion changed the hashed host-contract bytes and Module Image validation rejected the input. Repository LF policy was fixed with `.gitattributes`; the ABI and hash-validation semantics were not relaxed.

## Compatibility policy

Native AOT ABI V1 is frozen as the interface for current portability and host-integration work. Changes that alter structure layout, function signatures, field meaning or version negotiation must not silently mutate `0x00010000`; an incompatible contract requires a new ABI version.

This freeze is a development compatibility contract. Linux x64 and Windows x64 now have execution evidence for the current bounded workloads, but that does not automatically establish other operating systems or host architectures.

## Claim boundary

This contract plus current execution evidence establishes:

- a versioned public C header;
- a single query/discovery symbol;
- fail-closed version and size negotiation;
- module/provenance metadata;
- explicit capability flags;
- explicit host callback binding with user data;
- state, memory, execution and error dispatch through a function table;
- deterministic adapter generation;
- GCC/Clang execution through the ABI for the existing RV32I and bounded MIPS32 workloads on Linux;
- MSVC/clang-cl execution through the unchanged ABI for those same workloads on Windows x64;
- frozen Windows x64 structure layout and query-only DLL export behavior;
- exact Linux/Core ↔ Windows observable parity for the bounded fixtures.

It does **not** establish:

- macOS dylib ABI compatibility;
- Windows ARM64 compatibility;
- Windows x86/32-bit compatibility;
- binary compatibility with future incompatible ABI revisions;
- arbitrary RV32I or MIPS32 binaries;
- full MIPS32 ISA/ABI coverage;
- a release-quality optimizing compiler pipeline;
- proprietary console executable support.

The next intended Windows host-integration gate is to load and drive a native AOT module through this V1 interface from the reusable Unreal Engine host layer. macOS and other Windows architectures remain separate portability frontiers.
