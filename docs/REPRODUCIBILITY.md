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

## External Reproducibility V1 — reproducible Linux reviewer PASS

`OPENRECOMP_EXTERNAL_REPRO_V1` provides a single external-reviewer command over the established open-core evidence:

```bash
bash EXTERNAL_REPRO_V1.sh
```

The gate requires a clean tracked checkout, records the exact source commit, executes the hardened E07 proof, regenerates RV32I normalized IR/Module/Core and GCC/Clang Native AOT evidence, executes the bounded MIPS32 vertical slice and all five Expansion V1 fixtures through the independent reference/Core/AOT matrix, validates Native AOT ABI V1 loading, restores the reviewed tracked evidence tree after the legacy E07 runner recreates `evidence/`, runs the unchanged fail-closed public-safety scanner, and requires no tracked-tree mutation at completion.

A successful run writes:

```text
evidence/external-repro-v1/RESULT.json
evidence/external-repro-v1/RESULT.sha256
evidence/external-repro-v1/RESULT.md
```

Hosted CI checks out the exact PR/source head, runs the complete reviewer command twice, and requires the two semantic `RESULT.json` records and their SHA-256 files to be byte-identical. Environment/compiler patch versions are recorded separately and are not treated as semantic evidence.

This is classified as **PASS — reproducible Linux reviewer path**. It does not establish Windows execution, Unreal runtime behavior, macOS/non-x64 host parity, Shipping packaged parity, arbitrary guest-binary compatibility or production optimizing-compiler status. See [`EXTERNAL_REPRO_V1.md`](EXTERNAL_REPRO_V1.md).

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

## Unreal Plugin V1 evidence layers

Plugin V1 reuses the same frozen Native AOT ABI and separates its hosted and UE-specific evidence.

### Plugin source/module gate — reproducible CI PASS

Hosted GitHub Actions verifies the plugin descriptor/source layout, byte identity of the embedded public ABI header with the canonical header, rejection of legacy private AOT symbols, deterministic source packaging, validated RV32I module generation, MSVC DLL build, engine-independent host-core execution and deterministic UE handoff generation.

The validated handoff is tied to PR #18 source head `8bd9928f4eb01f471c7a33117634c729585a832e`, workflow run `33564491900` and CI artifact SHA-256 `7fd6433c2e0d5d05fb11602cce314f76d9d8e185a8264c85c6bd288985e8e191`.

### Plugin UE5.8 build + PIE — local runtime PASS

The CI handoff was installed on Windows x64 with UE5.8. The returned result reports:

```text
OPENRECOMP_UNREAL_PLUGIN_V1_UE58_BUILD=PASS
OPENRECOMP_UNREAL_PLUGIN_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

The returned plugin SHA-256 manifest exactly matches the CI handoff manifest, and every plugin file in the CI handoff verifies against that manifest. The returned result ZIP has SHA-256 `1cace48a5ab5384cbbfeb47bee8ec8a0e263561c4dce57c881f0f8a68017650d`.

Only the allow-listed build/runtime/provenance record is tracked in the repository. The raw Unreal log is not public evidence. Because UE5.8 itself is not available in hosted CI, this remains **PASS — local runtime evidence**. It does not establish packaged-game deployment or arbitrary Unreal-project compatibility.

## Unreal Packaged Build V1 evidence layers

Packaged Build V1 reuses Plugin V1 and the frozen Native AOT ABI without introducing a new execution interface.

### Packaged-build source/module/handoff gate — reproducible CI PASS

Hosted GitHub Actions verifies the Plugin V1 contract, the Win64 `NonUFS` runtime-dependency staging contract, deterministic RV32I module generation, MSVC Native AOT DLL build, engine-independent host-core execution, Windows PowerShell 5.1 parsing/execution of the public-safe collector path and deterministic packaged-build handoff generation.

The final handoff used for the local packaged-runtime gate is tied to PR #19 source head:

```text
334a4ba603618b243c896c8122fd4cd730730e56
```

Its hosted workflow artifact SHA-256 is:

```text
63f50d8dc25065ba51de06e43010a10dda12147ef311c196ba4f34e2fb5a0574
```

The deterministic inner handoff SHA-256 is:

```text
626d906a348122b4f7ab3d8f886a38a5060befca8a6a31ee3a6af9b7551e5fe9
```

The validated DLL in that handoff has SHA-256:

```text
f6a8679cbd763529b6dd5f33c2ffeac8e269d8f4e2d859e8b1c48dec8cc6b2b6
```

### UE5.8 Development package + packaged executable — local packaged runtime PASS

The exact CI handoff was installed into the UE5.8 Windows x64 project. `BuildCookRun` completed a Development Win64 package and the packaged archive contained the validated DLL with the exact CI SHA-256 above.

The packaged executable was then launched outside Editor/PIE with `-OpenRecompPackagedProof` and reproduced:

```text
OPENRECOMP_UNREAL_PACKAGED_BUILD_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

The returned public-safe result ZIP has SHA-256:

```text
2ca45d54c6d23bb0e14f896f324140679e20264812d63c975c4e8ca3fbcb7f21
```

The returned package record reports `CONFIGURATION=Development`, `PLATFORM=Win64` and the same staged DLL SHA-256. The result archive contains only provenance, manifest and public-safe result records; raw Unreal logs and packaged binaries are not project evidence.

Because UE5.8 is not available in hosted project CI, the package/run is classified as **PASS — local packaged runtime evidence**. This result does not establish Shipping configuration parity, arbitrary Unreal-project compatibility, other Unreal versions or other host platforms.

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
- External Reproducibility V1: **PASS — reproducible Linux reviewer path**
- Unreal Native AOT host core: **PASS — reproducible Windows CI**
- Unreal Native AOT UE5.8 PIE: **PASS — local runtime evidence**
- OpenRecompRuntime Plugin V1 hosted gate: **PASS — reproducible Windows CI/source contract**
- OpenRecompRuntime Plugin V1 UE5.8 build + PIE: **PASS — local runtime evidence**
- Unreal Packaged Build V1 hosted gate: **PASS — reproducible Windows CI/source/staging/handoff contract**
- UE5.8 Windows x64 Development packaged runtime: **PASS — local packaged runtime evidence**
- Original UE5.8 Gate B PIE: **PASS — local runtime evidence**
- General MIPS32 support: **CANDIDATE**
- macOS / Windows ARM64 / Windows x86 parity: **CANDIDATE**
- Shipping Unreal packaged parity / arbitrary Unreal deployment: **CANDIDATE**
- Release-quality compiler/plugin pipeline: **CANDIDATE**