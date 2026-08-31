# Reproducibility and evidence model

OpenRecomp separates immutable proof inputs from generated evidence and mutable project documentation.

## Proof-critical source manifest

`SOURCE_SHA256SUMS.txt` protects the source and data that directly define the original E07 proof, including architecture adapters, host contracts, the synthetic corpus, golden outputs, linker script, legacy IR schema, fixture source, proof/translation tools and the proof runner.

General project documentation is intentionally not part of this immutable E07 proof-input manifest. Documentation can evolve without invalidating that executable proof.

Newer IR V1/Core API/MIPS32/AOT/Native-ABI/Windows-portability regression gates are independently enforced by GitHub Actions and their own deterministic comparisons rather than silently changing the historical E07 source manifest.

`.gitattributes` pins proof/source text files to LF so exact byte hashes remain stable across Linux and Windows checkouts. This was added after the first Windows portability run correctly rejected a CRLF-converted host contract by SHA-256; hash validation was not weakened.

## E07 generated evidence

`RUN.sh` recreates `build/` and `evidence/` outputs, validates deterministic translation and compares host-visible outputs. A per-run manifest records generated-file hashes.

## RV32I normalized/Core reproducibility

The E07 CI additionally normalizes the proven RV32I path to IR V1 twice and requires byte-identical outputs, packages Module Image V1 twice and requires byte-identical outputs, then compares the Core API result with the independent bridge, native execution and committed golden state.

The bounded result is checksum `122010428`, observed `a0=48`.

## MIPS32 vertical-slice reproducibility

The MIPS32 gate starts from an original clean synthetic machine-word fixture. It:

1. runs fail-closed decoder/frontend tests;
2. lowers the fixture twice and requires byte-identical IR V1, execution-sidecar and frontend-report outputs;
3. validates normalized IR V1;
4. executes an independent machine-code MIPS32 reference path with architectural delay slots;
5. packages Module Image V1 twice and requires byte-identical output;
6. validates Module Image V1;
7. executes the same normalized workload through the shared Core API V1 `ReferenceExecutor`;
8. compares complete normalized register state, observable memory, source provenance and checksum across the independent reference/Core paths.

The current bounded MIPS32 result is `v0=31`, observable memory word `19`, seven delay slots and checksum `1950232098`.

## Portable C AOT reproducibility

The AOT gate consumes the already-validated IR V1 and Module Image V1 outputs for both current guest workloads.

For each architecture it:

1. translates the same normalized module to portable C twice;
2. requires the generated C files to be byte-identical;
3. compiles the same generated C independently with GCC and Clang using `-Wall -Wextra -Werror`;
4. executes both native modules through Native AOT ABI V1;
5. requires GCC and Clang behavioral result JSON to be byte-identical;
6. compares the AOT result with the existing Core API reference result exactly.

The current bounded AOT results are:

```text
RV32I checksum=122010428, a0=48, operations=3866
MIPS32 checksum=1950232098, v0=31, operations=100
```

Generated compiler binaries are not required to be byte-identical because compiler/toolchain metadata and code-generation choices may legitimately differ. The reproducibility requirement is deterministic OpenRecomp-generated source/adapters plus exact observable behavioral parity.

## AOT hardening reproducibility

`OPENRECOMP_AOT_HARDENING_V1` adds an architecture-independent normalized-IR corpus around the same backend. The positive program is generated and executed in both little- and big-endian configurations and covers the current integer binops, comparison predicates, cast forms, select, state operations, memory operations, direct calls, structured control flow, bounded indirect control flow, returns and trap representation.

For each positive configuration the Core API reference and GCC/Clang native AOT results must agree on observed state, function return, operation count, state snapshot and observable memory. The established result is:

```text
AOT_HARDENING_POSITIVE=2147483672
```

The hardening gate also constructs nine valid modules that intentionally fail during execution. Core API and AOT are required to agree on a normalized deterministic fault class under both compilers:

```text
memory-oob       -> memory-fault
misalignment     -> misalignment
operation-limit  -> operation-limit
shift-count      -> shift-count
trap             -> trap
indirect-target  -> indirect-target
call-depth       -> call-depth
host-failure     -> host-failure
host-void        -> host-void
```

Finally, the little- and big-endian positive generated sources are compiled as standalone executables under GCC and Clang with AddressSanitizer and UndefinedBehaviorSanitizer. CI enables leak detection and halt-on-error semantics and requires clean execution.

The current hardening markers are:

```text
AOT_HARDENING_FAULT_CASES=9
OPENRECOMP_AOT_HARDENING_WARNING_CLEAN=PASS
OPENRECOMP_AOT_HARDENING_FAULT_EQUIVALENCE=PASS
OPENRECOMP_AOT_HARDENING_GCC_SANITIZERS=PASS
OPENRECOMP_AOT_HARDENING_CLANG_SANITIZERS=PASS
OPENRECOMP_AOT_HARDENING_V1=PASS
```

## Native AOT ABI V1 reproducibility

Native AOT ABI V1 adds a deterministic module-specific adapter around the portable-C implementation surface. The adapter is generated from the validated Module Image V1, normalized IR V1 and host contract, so its public metadata is bound to the same validated execution inputs.

For both RV32I and MIPS32, Linux CI generates the adapter twice, requires byte-identical output, builds backend + adapter independently with GCC and Clang using hidden default symbol visibility, validates exact query/version/size/metadata/host-binding behavior, verifies representative private symbols are not dynamically visible, and executes the existing AOT proof through the V1-aware loader.

The deterministic generation markers are:

```text
OPENRECOMP_NATIVE_AOT_ABI_RV32I_DETERMINISTIC=PASS
OPENRECOMP_NATIVE_AOT_ABI_MIPS32_DETERMINISTIC=PASS
```

Each GCC/Clang module also requires:

```text
OPENRECOMP_NATIVE_AOT_ABI_V1_QUERY=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_VERSION_REJECTION=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_SIZE_REJECTION=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_METADATA=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_HOST_NEGOTIATION=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_PRIVATE_SURFACE=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_LOADER=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_DUAL_ARCH=PASS
```

The contract remains **FROZEN-FOR-PORTABILITY-TESTING**.

## Windows x64 AOT reproducibility

`OPENRECOMP_AOT_WINDOWS_PORTABILITY_V1` tests that frozen ABI on a separate OS/toolchain family while retaining the Linux/Core execution records as the independent oracle.

The gate:

1. builds the validated RV32I and MIPS32 IR V1, Module Image V1 and Core API results on Linux;
2. transfers those generated reference artifacts to an ordinary Windows x64 checkout;
3. relies on repository LF policy so hashed source/contract bytes remain identical across the checkout boundary;
4. regenerates portable C and Native AOT ABI adapters twice on Windows and requires byte-identical output for each architecture;
5. compiles the unchanged public V1 header layout probe under both MSVC and clang-cl with warnings as errors;
6. requires `sizeof(openrecomp_native_aot_host_v1) == 24`, `sizeof(openrecomp_native_aot_api_v1) == 168`, and every pinned public field offset to match;
7. builds RV32I and MIPS32 DLLs independently with MSVC and clang-cl under `/W4 /WX`;
8. captures `dumpbin /exports` and requires `openrecomp_native_aot_query` to be the only OpenRecomp-named DLL export;
9. runs exact V1 query/version/size/metadata/host/private-surface/loader tests on all four DLLs;
10. executes both workloads through both Windows toolchains, requires exact Core/Linux reference equality, and requires MSVC/clang-cl result JSON to be byte-identical.

The first Windows attempt stopped at step 3 because CRLF conversion changed `contracts/host_contract.json` and the Module Image loader reported a host-contract SHA-256 mismatch. That failure was preserved as evidence that integrity validation fails closed. `.gitattributes` fixed checkout-byte stability; no hash comparison was bypassed.

The established Windows results are:

```text
RV32I  checksum=122010428, a0=48, operations=3866
MIPS32 checksum=1950232098, v0=31, operations=100
```

Final markers include:

```text
OPENRECOMP_AOT_WINDOWS_CODEGEN_DETERMINISTIC=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_WINDOWS_X64_LAYOUT=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_WINDOWS_EXPORT_SURFACE=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_WINDOWS_NEGOTIATION=PASS
OPENRECOMP_AOT_WINDOWS_RV32I=PASS
OPENRECOMP_AOT_WINDOWS_MIPS32=PASS
OPENRECOMP_AOT_WINDOWS_MSVC_CLANGCL_PARITY=PASS
OPENRECOMP_AOT_WINDOWS_LINUX_REFERENCE_PARITY=PASS
OPENRECOMP_AOT_WINDOWS_PORTABILITY_V1=PASS
```

Generated DLLs are not committed. The workflow retains public-safe JSON/layout/export evidence as an Actions artifact.

## Golden validation

The committed E07 golden framebuffer, audio and state outputs remain regression references for the original RV32I fixture. The MIPS32 vertical slice uses explicit expected state/memory/checksum metadata plus independent cross-path agreement rather than reusing the E07 host-output goldens.

## Host parity

The E07 translated workload is executed through native and WebAssembly host paths and their checksums must agree. The host-free MIPS32 slice validates guest semantics by comparing an independent machine-code reference against the common IR/Module/Core path.

The portable C AOT path adds another independent execution form: native code produced from normalized IR rather than interpreted by `ReferenceExecutor`. Native AOT ABI V1 keeps host semantics outside generated guest code and makes the host-call bridge explicit and versioned. Windows x64 now executes that same boundary under two additional compiler toolchains and is checked against the Linux/Core oracle.

## Classification

Reproducibility does not automatically promote a feature's status:

- RV32I E07 path: **PROVEN**
- RV32I -> IR V1 bridge: **PASS — E07 equivalence**
- Core API V1 reference path: **PASS — E07 equivalence**
- MIPS32 synthetic vertical slice: **PASS — bounded equivalence**
- Shared IR/Module/Core boundary across RV32I + MIPS32: **PASS — bounded two-guest validation**
- Portable C AOT backend V1: **PASS — bounded hardened dual-architecture equivalence**
- GCC/Clang `-Werror` and behavioral parity: **PASS — current dual-architecture fixtures + hardening corpus**
- Core API/AOT fault equivalence: **PASS — 9 bounded fault classes**
- GCC/Clang ASan+UBSan: **PASS — Linux little/big-endian hardening fixtures**
- Native AOT ABI V1 contract: **FROZEN-FOR-PORTABILITY-TESTING**
- Native AOT ABI V1 Linux GCC/Clang: **PASS — bounded dual-architecture execution**
- Native AOT ABI V1 Windows x64 MSVC/clang-cl: **PASS — bounded dual-architecture execution and Linux/Core parity**
- Cross-platform proof-text byte stability: **PASS — Linux/Windows LF-stable hashed inputs**
- General MIPS32 ISA/frontend coverage: **CANDIDATE**
- macOS / Windows ARM64 / Windows x86 Native AOT ABI parity: **CANDIDATE**
- Release-quality production AOT compiler pipeline: **CANDIDATE**
