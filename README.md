# OpenRecomp

OpenRecomp is an open-source, architecture-neutral static recompilation framework with deterministic validation and explicit host interfaces.

The project separates binary analysis, a versioned intermediate representation (IR), executable module packaging, reference execution, ahead-of-time translation and host integration so the reusable core is not tied to a single game, console or engine.

Unreal Engine is an optional consumer of the versioned native-module interface, not a dependency of the OpenRecomp core.

> **Start here:** [Current Technical Status](docs/TECHNICAL_STATUS.md) · [Architecture](docs/ARCHITECTURE.md) · [Evidence Model](docs/EVIDENCE_MODEL.md) · [Platforms](docs/PLATFORMS.md) · [Commercial Evaluation Pilot](COMMERCIAL_PILOT.md)

## Current technical status

| Area | Status |
| --- | --- |
| RV32I bounded validation path | **PROVEN for published fixtures** |
| Normalized OpenRecomp IR V1 | **FROZEN-FOR-IMPLEMENTATION** |
| MIPS32 validation/recompilation path | **BOUNDED / expanding** |
| Portable native AOT backend | **BOUNDED / demonstrated** |
| Native AOT ABI V1 | **FROZEN-FOR-PORTABILITY-TESTING** |
| Linux + Windows x64 native validation | **PASS for documented bounded fixtures** |
| Deterministic/reproducible evidence gates | **PASS for published gates** |
| Unreal Engine host integration | **BOUNDED; optional integration** |
| PlayStation-era (PS1) static-recompilation research | **ACTIVE — general compatibility NOT PROVEN** |
| General legacy-game compatibility | **NOT PROVEN** |

The short table is intentionally conservative. See [`docs/TECHNICAL_STATUS.md`](docs/TECHNICAL_STATUS.md) and [`docs/PROOF_STATUS.md`](docs/PROOF_STATUS.md) for the evidence boundaries behind each statement.

## Current public milestone

**OpenRecomp v0.2.0** is the first formal public research/developer milestone. It freezes the evidence-backed open-core architecture and reviewer-facing validation state at that release boundary; it is not a claim of general guest-binary compatibility or a production-quality optimizing compiler.

Post-v0.2.0 work expands the architecture and applies the same evidence-first approach to increasingly realistic legacy-software paths. Release notes remain immutable historical records rather than being rewritten to imply later capabilities.

See [`docs/RELEASE_V0_2_0.md`](docs/RELEASE_V0_2_0.md) and [`docs/RELEASE_CHECKLIST_V0_2_0.md`](docs/RELEASE_CHECKLIST_V0_2_0.md).

## Architecture

```text
Guest binary / machine-code fixture
    ↓
fail-closed ingestion + architecture frontend
    ↓
decode / control-flow / reachability / semantics
    ↓
Normalized OpenRecomp IR V1
    ↓
Module Image V1
    ↓
    ├── reference / Core API execution
    └── portable AOT translation
             ↓
       native AOT module
             ↓
       Native AOT ABI V1
             ↓
explicit runtime + host services
    ↓
native host / WebAssembly validation / optional engine integration
    ↓
deterministic comparison + evidence capture
```

OpenRecomp's central design goal is not merely to emit native code. It is to make the path from guest binary to observed result reviewable: unsupported semantics, unresolved control flow and missing platform services remain explicit compatibility frontiers instead of being silently treated as supported.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/EVIDENCE_MODEL.md`](docs/EVIDENCE_MODEL.md).

## PlayStation-era research

OpenRecomp is actively developing a bounded PlayStation-era (PS1) static-recompilation path using legally obtained software. The work exercises executable ingestion, MIPS-family decoding and semantics, control-flow recovery, runtime/service boundaries and deterministic evidence against increasingly realistic inputs.

This is research in progress. **General PS1 compatibility and complete commercial-title playability are NOT PROVEN unless a specific published result explicitly establishes the narrower claim.** No Sony or PlayStation affiliation or endorsement is implied.

See [`docs/TECHNICAL_STATUS.md`](docs/TECHNICAL_STATUS.md) and [`docs/PLATFORMS.md`](docs/PLATFORMS.md).

## Reproducible proof entry points

For the focused hardened E07 proof:

```bash
./RUN.sh
```

Expected terminal marker:

```text
PASS: E07 V1.1 HARDENED END-TO-END
```

For the broader bounded Linux x86-64 reviewer path from a clean checkout:

```bash
bash EXTERNAL_REPRO_V1.sh
```

Expected terminal marker:

```text
OPENRECOMP_EXTERNAL_REPRO_V1=PASS
```

The reviewer gate emits deterministic semantic evidence and covers the documented RV32I path, bounded MIPS32 fixtures, native AOT loading, public-safety validation and tracked-tree immutability. It does not claim arbitrary guest binaries, Unreal execution, every host platform or production compiler status.

See [`docs/EXTERNAL_REPRO_V1.md`](docs/EXTERNAL_REPRO_V1.md).

## Key published bounded results

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

The repository also contains an expanded bounded MIPS32 fixture suite across reference/Core/AOT paths and Linux/Windows toolchains. These are validation fixtures, not claims of arbitrary RV32I or MIPS32 executable support.

## Native AOT ABI V1

The public native-module contract is [`include/openrecomp/native_aot_abi_v1.h`](include/openrecomp/native_aot_abi_v1.h). Finished proof modules expose the versioned discovery entry point:

```text
openrecomp_native_aot_query
```

Linux GCC/Clang and Windows x64 MSVC/clang-cl validate the same frozen V1 layout for the documented bounded workloads. Unsupported ABI versions and incorrect structure sizes reject fail-closed.

See [`docs/NATIVE_AOT_ABI_V1.md`](docs/NATIVE_AOT_ABI_V1.md) and [`docs/AOT_WINDOWS_PORTABILITY_V1.md`](docs/AOT_WINDOWS_PORTABILITY_V1.md).

## Unreal interoperability

OpenRecomp includes Unreal Engine interoperability as a host-integration demonstration, not as part of the required open core. Hosted gates validate the engine-independent source/module boundary while separately identified local evidence covers the documented UE5.8 Windows x64 runtime demonstrations.

Unreal is therefore an example consumer of the Native AOT ABI rather than the architecture around which OpenRecomp is built.

See [`docs/UNREAL_NATIVE_AOT_HOST_V1.md`](docs/UNREAL_NATIVE_AOT_HOST_V1.md), [`docs/UNREAL_PLUGIN_V1.md`](docs/UNREAL_PLUGIN_V1.md), [`docs/UNREAL_PACKAGED_BUILD_V1.md`](docs/UNREAL_PACKAGED_BUILD_V1.md) and [`integrations/unreal/README.md`](integrations/unreal/README.md).

## Commercial evaluation

OpenRecomp is available for bounded commercial feasibility evaluations of legacy executable software supplied by organisations that own or are authorised to provide it.

A pilot is an engineering investigation, **not a guaranteed port**. It can establish how far a target currently progresses, identify the compatibility frontier, produce reproducible technical evidence and outline the work required for further native execution or modernisation.

See [`COMMERCIAL_PILOT.md`](COMMERCIAL_PILOT.md) and [`docs/COMMERCIAL_TECHNICAL_OVERVIEW.md`](docs/COMMERCIAL_TECHNICAL_OVERVIEW.md).

## Evidence model

OpenRecomp uses explicit evidence classifications such as **PROVEN**, **BOUNDED**, **CANDIDATE** and **NOT PROVEN**. A PASS marker is scoped to its gate contract; it does not automatically establish a broader compatibility claim.

Repeated deterministic gates, integrity hashes, fail-closed behaviour and machine-readable results are used where appropriate. Unsupported behaviour is treated as useful engineering information rather than hidden.

See [`docs/EVIDENCE_MODEL.md`](docs/EVIDENCE_MODEL.md).

## Development process

OpenRecomp uses a human-led process that may include automated and AI-assisted development/review tools. Material machine assistance is disclosed, but generated output is never treated as proof by itself. Acceptance remains evidence-driven through tests, runtime checks and review.

See [`DEVELOPMENT_PROCESS.md`](DEVELOPMENT_PROCESS.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Rights firewall

Public tests and examples use original synthetic, homebrew or otherwise clearly redistributable inputs. The repository does **not** contain commercial game binaries/assets, console BIOS/firmware or keys, proprietary SDK material, authentication logs or proprietary console executable content.

Commercial/customer material is kept separate from the public repository unless publication is explicitly authorised and lawful.

## Documentation

### Technical overview
- [`docs/TECHNICAL_STATUS.md`](docs/TECHNICAL_STATUS.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/EVIDENCE_MODEL.md`](docs/EVIDENCE_MODEL.md)
- [`docs/PLATFORMS.md`](docs/PLATFORMS.md)
- [`docs/PROOF_STATUS.md`](docs/PROOF_STATUS.md)

### Core interfaces and validation
- [`docs/IR_SPEC_V1.md`](docs/IR_SPEC_V1.md)
- [`docs/RV32I_IR_V1_BRIDGE.md`](docs/RV32I_IR_V1_BRIDGE.md)
- [`docs/CORE_API_V1.md`](docs/CORE_API_V1.md)
- [`docs/MIPS32_VERTICAL_SLICE_V1.md`](docs/MIPS32_VERTICAL_SLICE_V1.md)
- [`docs/MIPS32_EXPANSION_V1.md`](docs/MIPS32_EXPANSION_V1.md)
- [`docs/AOT_TRANSLATOR_V1.md`](docs/AOT_TRANSLATOR_V1.md)
- [`docs/AOT_HARDENING_V1.md`](docs/AOT_HARDENING_V1.md)
- [`docs/NATIVE_AOT_ABI_V1.md`](docs/NATIVE_AOT_ABI_V1.md)
- [`docs/AOT_WINDOWS_PORTABILITY_V1.md`](docs/AOT_WINDOWS_PORTABILITY_V1.md)
- [`docs/EXTERNAL_REPRO_V1.md`](docs/EXTERNAL_REPRO_V1.md)

### Integration, commercial and project material
- [`docs/UNREAL_NATIVE_AOT_HOST_V1.md`](docs/UNREAL_NATIVE_AOT_HOST_V1.md)
- [`docs/UNREAL_PLUGIN_V1.md`](docs/UNREAL_PLUGIN_V1.md)
- [`docs/UNREAL_PACKAGED_BUILD_V1.md`](docs/UNREAL_PACKAGED_BUILD_V1.md)
- [`COMMERCIAL_PILOT.md`](COMMERCIAL_PILOT.md)
- [`docs/COMMERCIAL_TECHNICAL_OVERVIEW.md`](docs/COMMERCIAL_TECHNICAL_OVERVIEW.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/FUNDING_SCOPE.md`](docs/FUNDING_SCOPE.md)
- [`docs/BUILDING.md`](docs/BUILDING.md)
- [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md)
- [`DEVELOPMENT_PROCESS.md`](DEVELOPMENT_PROCESS.md)
