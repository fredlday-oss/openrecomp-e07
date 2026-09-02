# OpenRecomp

OpenRecomp is an open-source, architecture-neutral static recompilation framework with deterministic validation and explicit host interfaces.

The project separates binary analysis, a versioned intermediate representation (IR), executable module packaging, reference execution, ahead-of-time translation and host integration so the reusable core is not tied to a single game, console or engine.

Unreal Engine is an optional consumer of the versioned native-module interface, not a dependency of the OpenRecomp core.

## Current public milestone

**OpenRecomp v0.2.0** is the first formal public research/developer milestone. It freezes the current evidence-backed open-core architecture and reviewer-facing validation state; it is not a claim of general guest-binary compatibility or a production-quality optimizing compiler.

Post-v0.2.0 development is tracked separately from the immutable release notes. Current development adds bounded multi-fixture MIPS32 expansion evidence, a reusable `OpenRecompRuntime` Unreal plugin and a bounded UE5.8 Windows x64 Development packaged-build validation without changing IR V1 or Native AOT ABI V1.

See [`docs/RELEASE_V0_2_0.md`](docs/RELEASE_V0_2_0.md) for the bounded v0.2.0 release notes and [`docs/RELEASE_CHECKLIST_V0_2_0.md`](docs/RELEASE_CHECKLIST_V0_2_0.md) for its publication/reproducibility gate.

## Current evidence status

| Area | Status |
| --- | --- |
| E07 RV32I synthetic fixture | **PROVEN** — fresh-clone hardened proof |
| Native / WebAssembly equivalence | **PASS** |
| Normalized OpenRecomp IR V1 | **FROZEN-FOR-IMPLEMENTATION** |
| RV32I -> IR V1 bridge | **PASS** — checksum `122010428` |
| Module Image / Core API V1 | **PASS** — checksum `122010428`, `a0=48`, 3,866 operations |
| MIPS32 synthetic vertical slice | **PASS** — checksum `1950232098`, bounded subset |
| MIPS32 expanded synthetic suite | **PASS** — five bounded little/big-endian fixtures across reference/Core/AOT/Linux/Windows |
| Portable C AOT backend | **PASS** — RV32I + bounded MIPS32 |
| AOT warning/fault/sanitizer hardening | **PASS** — GCC/Clang bounded corpus |
| Native AOT ABI V1 | **FROZEN-FOR-PORTABILITY-TESTING** |
| Native AOT ABI Linux + Windows x64 | **PASS** — GCC/Clang/MSVC/clang-cl bounded fixtures |
| Unreal Native AOT host core | **PASS** — reproducible Windows four-way compiler/module CI matrix |
| UE5.8 Native AOT PIE runtime | **PASS — local runtime evidence** — synthetic RV32I module |
| OpenRecompRuntime plugin V1 hosted gate | **PASS** — source/ABI contract, deterministic handoff, validated Windows module/host-core execution |
| OpenRecompRuntime plugin V1 UE5.8 build + PIE | **PASS — local runtime evidence** — state `48`, checksum `122010428`, operations `3866` |
| Unreal packaged build V1 hosted gate | **PASS** — source/staging contract, PowerShell 5.1 collector smoke, deterministic handoff and validated host-core path |
| UE5.8 Windows x64 Development packaged runtime | **PASS — local packaged runtime evidence** — exact CI DLL staged; packaged executable outside Editor/PIE reproduced state `48`, checksum `122010428`, operations `3866` |
| Original UE5.8 Gate B PIE runtime | **PASS — local runtime evidence** |
| General MIPS32 support | **CANDIDATE** |
| macOS / Windows ARM64 / Windows x86 ABI parity | **CANDIDATE** |
| Release-quality compiler/plugin pipeline | **CANDIDATE** |

The detailed evidence boundaries and terminology are maintained in [`docs/PROOF_STATUS.md`](docs/PROOF_STATUS.md). Locally executed Unreal results are intentionally identified as local evidence because hosted CI does not contain Unreal Engine; the engine-independent Windows host core and Plugin/Packaged-Build source/module gates remain independently reproducible in GitHub Actions.

## Architecture

```text
Guest binary / clean machine-code fixture
    ↓
Architecture frontend
    ↓
Normalized OpenRecomp IR V1
    ↓
Module Image V1
    ↓
    ├── Core API V1 reference executor
    └── Portable C AOT backend
             ↓
       native AOT module
             ↓
       Native AOT ABI V1
             ↓
Explicit host services
    ↓
Native / WebAssembly / optional engine integration
```

The strongest current generalization result is bounded but concrete: two materially different clean synthetic guest paths, RV32I and MIPS32, cross the same normalized IR, Module Image and Core API boundaries. The MIPS32 evidence now spans several independent little-endian semantic fixtures plus a bounded big-endian memory fixture. The same portable C backend reproduces their reference results after native compilation.

## Reproducible proof entry point

From a fresh clone, run:

```bash
./RUN.sh
```

A successful hardened E07 run ends with:

```text
PASS: E07 V1.1 HARDENED END-TO-END
```

The hardened proof includes malformed/adversarial ELF rejection, schema and host-contract checks, checked guest memory, native/WebAssembly parity, golden regression and reproducibility checks.

Additional CI gates cover IR V1, Core API V1, the original and expanded MIPS32 evidence, AOT translation/hardening, Native AOT ABI portability, Unreal plugin/packaged-build source and handoff validation, public safety and documentation.

For the v0.2.0 release metadata gate, run:

```bash
python3 tools/verify_release_v0_2_0.py
```

Expected marker:

```text
OPENRECOMP_V0_2_RELEASE_METADATA=PASS
```

## Key bounded results

RV32I / E07:

```text
checksum   = 122010428
return a0  = 48
operations = 3866
```

MIPS32 vertical slice:

```text
checksum   = 1950232098
return v0  = 31
operations = 100
delay slots lowered = 7
```

MIPS32 expansion V1:

```text
logic-shift        checksum=435263539   operations=72  delay_slots=1
memory-width       checksum=4257846410  operations=60  delay_slots=1
branches-calls     checksum=2065440492  operations=75  delay_slots=9
mult-hilo          checksum=768371589   operations=44  delay_slots=1
big-endian-memory  checksum=938211822   operations=24  delay_slots=1
```

Each expansion fixture agrees across an independent MIPS32 machine-code reference, Core API V1, Linux GCC/Clang AOT, and Windows x64 MSVC/clang-cl AOT through Native AOT ABI V1.

These are validation fixtures, not claims of arbitrary RV32I or MIPS32 executable support. `div/divu` remain outside expansion V1 because frozen IR V1 has no division/remainder operation.

## Native AOT ABI V1

The public native-module contract is [`include/openrecomp/native_aot_abi_v1.h`](include/openrecomp/native_aot_abi_v1.h). Finished proof modules expose the versioned discovery entry point:

```text
openrecomp_native_aot_query
```

Linux GCC/Clang and Windows x64 MSVC/clang-cl validate the same frozen V1 layout for the current bounded workloads. Unsupported ABI versions and incorrect structure sizes reject fail-closed.

See [`docs/NATIVE_AOT_ABI_V1.md`](docs/NATIVE_AOT_ABI_V1.md) and [`docs/AOT_WINDOWS_PORTABILITY_V1.md`](docs/AOT_WINDOWS_PORTABILITY_V1.md).

## Unreal interoperability

OpenRecomp includes Unreal Engine interoperability as a host-integration demonstration, not as part of the required open core.

The engine-independent Native AOT host core is reproducibly tested in Windows CI across:

```text
MSVC host     -> MSVC module
MSVC host     -> clang-cl module
clang-cl host -> MSVC module
clang-cl host -> clang-cl module
```

A separate UE5.8 Windows x64 PIE run locally loaded the synthetic RV32I module through `openrecomp_native_aot_query` and recorded:

```text
observed_state = 48
checksum       = 122010428
operations     = 3866
```

Post-v0.2.0, `OpenRecompRuntime` packages the same boundary as a reusable code-only plugin with a persistent Native AOT module wrapper, `UOpenRecompSubsystem` and a clean synthetic example actor. Hosted CI verifies the plugin source/ABI contract, deterministic handoff and validated Windows module/host-core path. A separate UE5.8 Windows x64 run built the plugin without source edits and produced:

```text
OPENRECOMP_UNREAL_PLUGIN_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

`OPENRECOMP_UNREAL_PACKAGED_BUILD_V1` then validates the same plugin and frozen ABI in a UE5.8 Windows x64 **Development** package. Hosted CI verifies the source/staging contract and deterministic handoff. The local gate staged the exact CI Native AOT DLL, packaged the project with UE BuildCookRun, launched the packaged executable outside Editor/PIE and produced:

```text
OPENRECOMP_UNREAL_PACKAGED_BUILD_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866
```

All UE execution results remain explicitly classified as local runtime evidence because the engine itself is not present in hosted project CI. Public evidence contains only allow-listed OpenRecomp markers/provenance; raw Unreal launcher/startup logs and packaged binaries are excluded. Shipping parity, other Unreal versions/platforms and arbitrary projects remain separate future gates.

See [`docs/UNREAL_NATIVE_AOT_HOST_V1.md`](docs/UNREAL_NATIVE_AOT_HOST_V1.md), [`docs/UNREAL_PLUGIN_V1.md`](docs/UNREAL_PLUGIN_V1.md), [`docs/UNREAL_PACKAGED_BUILD_V1.md`](docs/UNREAL_PACKAGED_BUILD_V1.md) and [`integrations/unreal/README.md`](integrations/unreal/README.md).

## Project scope and funding boundaries

The reusable open-core milestone track and optional host-integration/portability track are separated in [`docs/FUNDING_SCOPE.md`](docs/FUNDING_SCOPE.md). Funding applications should distinguish already-completed evidence from proposed work and avoid treating a proprietary engine as a dependency of the architecture-neutral core.

## Development process

OpenRecomp uses a human-led process that may include automated and AI-assisted development/review tools. Material machine assistance is disclosed, but generated output is never treated as proof by itself. Acceptance remains evidence-driven through tests, runtime checks and review.

See [`DEVELOPMENT_PROCESS.md`](DEVELOPMENT_PROCESS.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Rights firewall

Public tests and examples use original synthetic, homebrew or otherwise clearly redistributable inputs. The repository does **not** contain commercial game binaries/assets, console BIOS/firmware or keys, proprietary SDK material, authentication logs or proprietary console executable content.

The public-safety gate scans tracked material and is designed to fail closed, including when an expected tracked file is missing from the working tree.

## Documentation

- [`docs/RELEASE_V0_2_0.md`](docs/RELEASE_V0_2_0.md)
- [`docs/RELEASE_CHECKLIST_V0_2_0.md`](docs/RELEASE_CHECKLIST_V0_2_0.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/IR_SPEC_V1.md`](docs/IR_SPEC_V1.md)
- [`docs/RV32I_IR_V1_BRIDGE.md`](docs/RV32I_IR_V1_BRIDGE.md)
- [`docs/CORE_API_V1.md`](docs/CORE_API_V1.md)
- [`docs/MIPS32_VERTICAL_SLICE_V1.md`](docs/MIPS32_VERTICAL_SLICE_V1.md)
- [`docs/MIPS32_EXPANSION_V1.md`](docs/MIPS32_EXPANSION_V1.md)
- [`docs/AOT_TRANSLATOR_V1.md`](docs/AOT_TRANSLATOR_V1.md)
- [`docs/AOT_HARDENING_V1.md`](docs/AOT_HARDENING_V1.md)
- [`docs/NATIVE_AOT_ABI_V1.md`](docs/NATIVE_AOT_ABI_V1.md)
- [`docs/AOT_WINDOWS_PORTABILITY_V1.md`](docs/AOT_WINDOWS_PORTABILITY_V1.md)
- [`docs/UNREAL_NATIVE_AOT_HOST_V1.md`](docs/UNREAL_NATIVE_AOT_HOST_V1.md)
- [`docs/UNREAL_PLUGIN_V1.md`](docs/UNREAL_PLUGIN_V1.md)
- [`docs/UNREAL_PACKAGED_BUILD_V1.md`](docs/UNREAL_PACKAGED_BUILD_V1.md)
- [`docs/PROOF_STATUS.md`](docs/PROOF_STATUS.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/FUNDING_SCOPE.md`](docs/FUNDING_SCOPE.md)
- [`docs/BUILDING.md`](docs/BUILDING.md)
- [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md)
- [`DEVELOPMENT_PROCESS.md`](DEVELOPMENT_PROCESS.md)
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`SECURITY.md`](SECURITY.md)
- [`DEPENDENCIES.md`](DEPENDENCIES.md)

## License

OpenRecomp is distributed under the Apache License, Version 2.0. See [`LICENSE`](LICENSE).