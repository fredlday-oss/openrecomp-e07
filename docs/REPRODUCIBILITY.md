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

The original bounded MIPS32 gate begins from a clean synthetic little-endian machine-word fixture and compares independent machine-code reference execution with normalized IR V1 -> Module Image V1 -> Core API V1 execution.

The paths agree on complete normalized register state, observable memory and checksum:

```text
v0=31
memory_word=19
delay_slots=7
checksum=1950232098
```

That historical fixture remains intact and independently exercised after the post-v0.2.0 expansion work.

## MIPS32 expansion V1

Expansion V1 adds five separate synthetic workloads rather than replacing the original vertical slice. Each fixture is normalized twice and requires byte-identical IR/sidecar/frontend reports, is packaged twice into byte-identical Module Image V1 JSON, and is validated through three semantic paths:

1. an independent MIPS32 machine-word reference with architectural delay slots;
2. normalized IR V1 -> Module Image V1 -> Core API V1;
3. deterministic portable-C AOT -> Native AOT ABI V1.

The Linux AOT path compiles every fixture independently with GCC and Clang under warning-as-error gates. Windows x64 then regenerates the portable C and ABI adapter deterministically, compiles every fixture under MSVC and clang-cl, and requires exact observable parity with the Linux reference/Core evidence.

Established fixture results:

```text
logic-shift        arch=mips32-le checksum=435263539   operations=72 delay_slots=1
memory-width       arch=mips32-le checksum=4257846410  operations=60 delay_slots=1
branches-calls     arch=mips32-le checksum=2065440492  operations=75 delay_slots=9
mult-hilo          arch=mips32-le checksum=768371589   operations=44 delay_slots=1
big-endian-memory  arch=mips32-be checksum=938211822   operations=24 delay_slots=1
```

The comparison includes complete normalized state and observable memory. The multiply fixture explicitly compares `special:hi` and `special:lo`. The big-endian fixture validates byte/halfword/word behavior through the same architecture-neutral memory layer rather than a MIPS-specific backend path.

Expansion V1 also has fail-closed tests for unsupported division under frozen IR V1, malformed shift and REGIMM encodings, misaligned source records, branch targets leaving a declared function, misaligned halfword access and reference execution-limit exhaustion.

Expected aggregate markers include:

```text
OPENRECOMP_MIPS32_EXPANSION_DECODER=PASS
OPENRECOMP_MIPS32_EXPANSION_NEGATIVE_TESTS=PASS tests=7
OPENRECOMP_MIPS32_EXPANSION_REFERENCE=PASS
OPENRECOMP_MIPS32_EXPANSION_CORE_API=PASS
OPENRECOMP_MIPS32_EXPANSION_AOT=PASS
OPENRECOMP_MIPS32_EXPANSION_LINUX_COMPILERS=PASS
OPENRECOMP_MIPS32_EXPANSION_WINDOWS_COMPILERS=PASS
OPENRECOMP_MIPS32_EXPANSION_V1=PASS
```

`div/divu` remain intentionally outside this expansion because IR V1 has no division/remainder semantic operation. The reproducibility gate therefore fails closed rather than altering the frozen IR contract solely for guest-opcode coverage.

## Portable C AOT

The AOT gate translates validated normalized modules deterministically, compiles them independently and requires native results to reproduce the Core API oracle.

For the original dual-guest baseline:

```text
RV32I  checksum=122010428, a0=48, operations=3866
MIPS32 vertical slice checksum=1950232098, v0=31, operations=100
```

Expansion V1 additionally proves the five MIPS32 results above through the same backend under GCC/Clang and Windows x64 MSVC/clang-cl.

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

Linux GCC/Clang tests require deterministic adapter generation, exact query/version/size/metadata/host-binding behavior, private implementation symbols outside the stable public surface, and exact execution parity for the current RV32I and bounded MIPS32 workloads. Expansion V1 reuses the same unchanged V1 query/table contract for all five added MIPS32 modules.

The contract remains **FROZEN-FOR-PORTABILITY-TESTING**.

## Windows x64 portability

The Windows gate uses Linux/Core execution records as an independent oracle, then on Windows x64:

1. regenerates portable C and ABI adapters deterministically;
2. verifies the frozen V1 x64 structure layout where applicable;
3. builds native modules under `/W4 /WX` with MSVC and clang-cl;
4. exercises query/version/size/metadata/host negotiation;
5. executes the bounded workloads through both compilers;
6. requires exact Linux/Core and MSVC/clang-cl behavioral parity.

The original portability baseline remains:

```text
RV32I  checksum=122010428, a0=48, operations=3866
MIPS32 vertical slice checksum=1950232098, v0=31, operations=100
```

Expansion V1 extends the MIPS32 Windows execution evidence to all five added fixtures, including the bounded `mips32-be` memory workload. This is reproducible in hosted GitHub Actions.

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
- MIPS32 expansion V1: **PASS — bounded multi-fixture little/big-endian validation**
- Shared IR/Module/Core boundary: **PASS — bounded two-guest validation**
- Portable C AOT backend: **PASS — bounded dual-guest**
- Expanded MIPS32 Linux GCC/Clang AOT: **PASS — bounded**
- Expanded MIPS32 Windows x64 MSVC/clang-cl AOT: **PASS — bounded**
- AOT warning/fault/sanitizer hardening: **PASS — bounded**
- Native AOT ABI V1: **FROZEN-FOR-PORTABILITY-TESTING**
- Linux + Windows x64 Native AOT ABI: **PASS — bounded**
- Unreal Native AOT host core: **PASS — reproducible Windows CI**
- Unreal Native AOT UE5.8 PIE: **PASS — local runtime evidence**
- Original UE5.8 Gate B PIE: **PASS — local runtime evidence**
- General MIPS32 support: **CANDIDATE**
- macOS / Windows ARM64 / Windows x86 parity: **CANDIDATE**
- Release-quality compiler/plugin pipeline: **CANDIDATE**
