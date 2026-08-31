# OpenRecomp AOT Windows Portability V1

**Frontier:** `OPENRECOMP_AOT_WINDOWS_PORTABILITY_V1`  
**Status:** **PASS — bounded Windows x64 MSVC/clang-cl dual-architecture validation**

This frontier validates the frozen Native AOT ABI V1 and hardened portable C backend on Windows x64 without changing the V1 public ABI layout or signatures.

## Proof boundary

The gate starts from the already-validated clean RV32I and bounded MIPS32 normalized workloads. Linux creates the reference IR V1, Module Image V1 and Core API result artifacts. A Windows x64 runner then regenerates the portable C and Native AOT ABI adapters from those exact validated inputs and compiles native DLLs independently with MSVC and clang-cl.

```text
Linux Core API reference
        |
        +---- RV32I IR/Module/Core result ----+
        |                                      |
        +---- MIPS32 IR/Module/Core result ----+----> Windows x64
                                                       |
                                              regenerate portable C
                                                       |
                                              regenerate ABI adapter
                                                       |
                                      +----------------+----------------+
                                      |                                 |
                                     MSVC                            clang-cl
                                      |                                 |
                                      +--------------- DLL -------------+
                                                       |
                                             Native AOT ABI V1
                                                       |
                                      exact Core/Linux result comparison
```

## Cross-platform source integrity

The first Windows CI run failed before code generation because the Windows checkout converted the host-contract text to CRLF, while Module Image V1 correctly binds the exact host-contract bytes by SHA-256. The loader therefore rejected the Windows checkout with a host-contract hash mismatch.

The repository now includes `.gitattributes` rules that keep proof/source metadata text at LF across platforms. The hash check was not weakened or bypassed. The next Windows run consumed the ordinary checked-out `contracts/host_contract.json` successfully, demonstrating that the byte-level integrity model remains fail-closed and portable.

## Frozen x64 ABI layout

`tools/native_aot_abi_layout_v1.c` is compiled independently by MSVC and clang-cl and statically verifies the Windows x64 layout of the already-frozen public header:

```text
sizeof(openrecomp_native_aot_host_v1) = 24
sizeof(openrecomp_native_aot_api_v1)  = 168
```

The probe also pins every public structure-field offset. The header itself is unchanged by this frontier.

Expected marker:

```text
OPENRECOMP_NATIVE_AOT_ABI_V1_WINDOWS_X64_LAYOUT=PASS
```

## Compiler gate

The current Windows proof uses the hosted Windows x64 Visual C++ environment and builds the same portable-C module + ABI adapter pairs with:

```text
MSVC cl      /std:c11 /O2 /W4 /WX /LD
clang-cl     /std:c11 /O2 /W4 /WX /LD
```

Both compilers successfully build RV32I and MIPS32 DLLs through the same V1 header and adapter.

## DLL export surface

`dumpbin /exports` is captured for every DLL. CI requires the complete OpenRecomp-named export set to contain exactly one symbol:

```text
openrecomp_native_aot_query
```

The private generated execution surface is therefore not promoted into the Windows public DLL contract.

Expected marker:

```text
OPENRECOMP_NATIVE_AOT_ABI_V1_WINDOWS_EXPORT_SURFACE=PASS
```

## ABI negotiation

Every compiler/architecture combination executes the existing Native AOT ABI V1 validation suite. It requires:

```text
OPENRECOMP_NATIVE_AOT_ABI_V1_QUERY=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_VERSION_REJECTION=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_SIZE_REJECTION=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_METADATA=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_HOST_NEGOTIATION=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_PRIVATE_SURFACE=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_LOADER=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1=PASS
OPENRECOMP_NATIVE_AOT_ABI_V1_WINDOWS_NEGOTIATION=PASS
```

The RV32I fixture exercises actual normalized host calls through the V1 callback bridge; the current MIPS32 fixture remains host-call-free.

## Execution results

Both Windows compilers reproduce the existing architecture-neutral results exactly.

RV32I:

```text
AOT_E07_CHECKSUM=122010428
AOT_E07_RETURN_A0=48
AOT_E07_OPERATIONS=3866
```

MIPS32:

```text
AOT_MIPS32_V0=31
AOT_MIPS32_CHECKSUM=1950232098
AOT_MIPS32_OPERATIONS=100
```

Each Windows result is compared with the Core API reference result produced in the Linux preparation job. MSVC and clang-cl result JSON must also be byte-identical for each guest workload.

Final markers:

```text
OPENRECOMP_AOT_WINDOWS_CODEGEN_DETERMINISTIC=PASS
OPENRECOMP_AOT_WINDOWS_RV32I=PASS
OPENRECOMP_AOT_WINDOWS_MIPS32=PASS
OPENRECOMP_AOT_WINDOWS_MSVC_CLANGCL_PARITY=PASS
OPENRECOMP_AOT_WINDOWS_LINUX_REFERENCE_PARITY=PASS
OPENRECOMP_AOT_WINDOWS_PORTABILITY_V1=PASS
```

## Evidence handling

The workflow uploads a public-safe Windows portability evidence artifact containing JSON result records, ABI-layout output and DLL-export listings. Generated DLLs and build products are not committed to the repository.

## Claim boundary

This frontier establishes a bounded Windows portability PASS for:

- Windows x64;
- the frozen Native AOT ABI V1 public header;
- MSVC and clang-cl warning-as-error builds;
- the existing RV32I E07 normalized workload;
- the bounded MIPS32 vertical-slice workload;
- exact Core/Linux observable-result parity;
- exact MSVC/clang-cl behavioral parity;
- fail-closed version/size/host negotiation;
- the single-query DLL export model.

It does **not** establish:

- Windows x86/32-bit hosts;
- Windows ARM64;
- macOS ABI parity;
- arbitrary RV32I or MIPS32 executables;
- full MIPS32 ISA/ABI support;
- ABI compatibility with a future incompatible V2;
- release-quality optimizing-compiler support;
- proprietary console executable support.

The strongest next platform-facing frontier is Unreal integration through Native AOT ABI V1 or macOS portability; broader MIPS32 ISA work remains a separate guest-coverage track.
