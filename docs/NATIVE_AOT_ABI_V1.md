# OpenRecomp Native AOT ABI V1

**Frontier:** `OPENRECOMP_NATIVE_AOT_ABI_V1`  
**Contract state:** **FROZEN-FOR-PORTABILITY-TESTING**  
**Execution status:** **PASS — bounded Linux GCC/Clang dual-architecture validation**

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

The current Linux proof links the underlying generated execution functions with hidden visibility. CI verifies that legacy execution symbols such as `openrecomp_run`, `openrecomp_set_host_callback`, `openrecomp_state_value` and `openrecomp_memory_read` are not dynamically visible from the finished module.

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

It emits a deterministic module-specific C adapter containing the immutable metadata and V1 dispatch table. CI generates each adapter twice and requires byte-identical output:

```text
OPENRECOMP_NATIVE_AOT_ABI_RV32I_DETERMINISTIC=PASS
OPENRECOMP_NATIVE_AOT_ABI_MIPS32_DETERMINISTIC=PASS
```

## Dual-architecture execution evidence

The finished RV32I and MIPS32 shared modules are built from:

```text
portable-C AOT output
+
Native AOT ABI V1 adapter
```

Both are compiled independently with GCC and Clang using warning-as-error builds and hidden default symbol visibility. For every compiler/architecture combination, CI requires:

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

The existing architecture-neutral AOT result gate remains unchanged:

```text
RV32I checksum=122010428, return a0=48, operations=3866
MIPS32 checksum=1950232098, return v0=31, operations=100
OPENRECOMP_IR_V1_AOT_DUAL_ARCH=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_DUAL_ARCH=PASS
```

The RV32I path also exercises real host calls through the new V1 callback bridge. The MIPS32 fixture is host-call-free, so together the current fixtures test both host-bound and host-free module configurations.

## Compatibility policy

Native AOT ABI V1 is now frozen as the interface to use for the next portability work. Changes that alter structure layout, function signatures, field meaning or version negotiation must not silently mutate `0x00010000`; an incompatible contract requires a new ABI version.

This freeze is a development compatibility contract, not evidence that every operating system/compiler ABI has already been validated.

## Claim boundary

This frontier establishes:

- a versioned public C header;
- a single query/discovery symbol;
- fail-closed version and size negotiation;
- module/provenance metadata;
- explicit capability flags;
- explicit host callback binding with user data;
- state, memory, execution and error dispatch through a function table;
- hidden legacy execution symbols in the Linux proof modules;
- deterministic adapter generation;
- GCC/Clang execution through the ABI for the existing RV32I and bounded MIPS32 workloads.

It does **not** yet establish:

- Windows DLL ABI compatibility;
- macOS dylib ABI compatibility;
- 32-bit host-process compatibility;
- binary compatibility with future incompatible ABI revisions;
- arbitrary RV32I or MIPS32 binaries;
- full MIPS32 ISA/ABI coverage;
- a release-quality optimizing compiler pipeline;
- proprietary console executable support.

Windows portability is the next intended evidence gate, using this V1 header without changing its layout.
