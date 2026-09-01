# Reproducibility and evidence model

OpenRecomp separates immutable proof inputs, generated evidence, mutable documentation and machine-local runtime observations.

## Original E07 proof inputs

`SOURCE_SHA256SUMS.txt` protects the source/data that directly define the original E07 proof, including architecture adapters, host contracts, the synthetic corpus, golden outputs, linker script, legacy IR schema, fixture source and proof/translation tooling.

General project documentation is intentionally outside that immutable manifest. Documentation can evolve without invalidating the executable E07 proof.

`RUN.sh` recreates generated build/evidence output and validates deterministic translation, native/WebAssembly parity, golden regression and adversarial rejection behavior.

## Cross-platform byte stability

`.gitattributes` pins proof/source text to LF so exact byte hashes remain stable across Linux and Windows checkouts.

This policy was introduced after the first Windows portability run converted a hashed host contract to CRLF and Module Image validation correctly rejected it by SHA-256. The hash check was not weakened or bypassed.

## RV32I normalized/Core path

The E07 CI additionally:

1. normalizes the proven RV32I path to IR V1 twice and requires byte-identical output;
2. packages Module Image V1 twice and requires byte-identical output;
3. validates the normalized IR and module package;
4. executes through Core API V1;
5. compares the result with independent bridge/native/golden evidence.

Current bounded result:

```text
checksum=122010428
a0=48
operations=3866
```

## MIPS32 vertical slice

The bounded MIPS32 gate begins from a clean synthetic machine-word fixture and compares two independent execution paths:

- machine-code reference execution with architectural delay slots;
- normalized IR V1 -> Module Image V1 -> Core API V1.

The paths agree on complete normalized register state, observable memory and checksum:

```text
v0=31
memory_word=19
delay_slots=7
checksum=1950232098
```

## Portable C AOT

For both current guest workloads the AOT gate:

1. translates the validated normalized module twice and requires byte-identical C;
2. compiles independently with GCC and Clang;
3. executes through Native AOT ABI V1;
4. requires compiler behavioral parity;
5. compares the native result with the Core API oracle.

Current bounded results:

```text
RV32I  checksum=122010428, a0=48, operations=3866
MIPS32 checksum=1950232098, v0=31, operations=100
```

Generated compiler binaries are not required to be byte-identical; reproducibility is defined as deterministic OpenRecomp-generated source/adapters plus exact observable behavioral parity.

## AOT hardening

The architecture-independent hardening gate adds:

- little/big-endian positive normalized-IR fixtures;
- warning-clean GCC/Clang compilation;
- nine deterministic Core API/AOT fault-equivalence classes;
- GCC/Clang ASan + UBSan smoke execution.

The nine fault categories are:

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

## Native AOT ABI V1

Native AOT ABI V1 adds a deterministic module-specific adapter around the generated implementation surface. The adapter is produced from validated Module Image V1/IR/host-contract inputs.

Linux GCC/Clang tests require deterministic adapter generation, exact query/version/size/metadata/host-binding behavior, private implementation symbols outside the stable public surface, and exact execution parity for the current RV32I and bounded MIPS32 workloads.

The contract remains **FROZEN-FOR-PORTABILITY-TESTING**.

## Windows x64 portability

The Windows gate uses Linux/Core execution records as an independent oracle, then on Windows x64:

1. regenerates portable C and ABI adapters deterministically;
2. verifies the frozen V1 x64 structure layout under MSVC and clang-cl;
3. builds current RV32I/MIPS32 DLLs under `/W4 /WX`;
4. checks the public DLL OpenRecomp export set;
5. exercises query/version/size/metadata/host negotiation;
6. executes both workloads through both compilers;
7. requires exact Linux/Core and MSVC/clang-cl behavioral parity.

Established results remain:

```text
RV32I  checksum=122010428, a0=48, operations=3866
MIPS32 checksum=1950232098, v0=31, operations=100
```

This is reproducible in hosted GitHub Actions.

## Unreal Native AOT evidence layers

The Unreal integration deliberately separates what hosted CI can reproduce from what currently requires a local UE installation.

### Engine-independent host core — reproducible CI PASS

Windows CI builds the synthetic RV32I AOT module with MSVC/clang-cl and the host core with MSVC/clang-cl, then executes all four host/module compiler combinations.

Each combination validates normalized metadata, rejects a missing required host, exercises the deterministic E07 callback bridge and reproduces:

```text
UNREAL_NATIVE_AOT_SOURCE_ARCH=riscv32-rv32i
UNREAL_NATIVE_AOT_OBSERVED_STATE=48
UNREAL_NATIVE_AOT_CHECKSUM=122010428
UNREAL_NATIVE_AOT_OPERATIONS=3866
OPENRECOMP_UNREAL_NATIVE_AOT_HOST_CORE_V1=PASS
```

### UE5.8 PIE — local runtime PASS

The CI workflow packages the synthetic DLL plus the exact ABI header and host source as a handoff. On a Windows machine with UE5.8 installed, the handoff was installed, hashed and built. The returned manifest matched the tested source/header/DLL set to the CI handoff by SHA-256.

PIE then produced:

```text
OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

The public repository retains only allow-listed proof lines, not the raw Unreal startup/launcher log.

Because the actual UE5.8 environment is not available in hosted project CI, this is classified as **PASS — local runtime evidence**, not as an unqualified reproducible runtime proof. A project-controlled self-hosted Unreal runner would strengthen this evidence layer.

## Public-safety reproducibility

The tracked-file public-safety scan is part of CI. It rejects generated Unreal output directories, tracked raw logs and selected credential/private-key markers.

The scanner also has a regression test for the case where `git ls-files` references a file that is missing from the working tree. That case must fail closed with a controlled `OPENRECOMP_PUBLIC_SAFETY=FAIL` diagnostic and no Python traceback.

## Classification summary

- RV32I E07 path: **PROVEN**
- RV32I -> IR V1 bridge: **PASS**
- Core API V1 reference path: **PASS**
- MIPS32 synthetic vertical slice: **PASS — bounded**
- Shared IR/Module/Core boundary: **PASS — bounded two-guest validation**
- Portable C AOT backend: **PASS — bounded dual-guest**
- AOT warning/fault/sanitizer hardening: **PASS — bounded**
- Native AOT ABI V1: **FROZEN-FOR-PORTABILITY-TESTING**
- Linux + Windows x64 Native AOT ABI: **PASS — bounded**
- Unreal Native AOT host core: **PASS — reproducible Windows CI**
- Unreal Native AOT UE5.8 PIE: **PASS — local runtime evidence**
- Original UE5.8 Gate B PIE: **PASS — local runtime evidence**
- General MIPS32 support: **CANDIDATE**
- macOS / Windows ARM64 / Windows x86 parity: **CANDIDATE**
- Release-quality compiler/plugin pipeline: **CANDIDATE**
