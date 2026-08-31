# OpenRecomp

OpenRecomp is an open-source, architecture-neutral static recompilation framework with deterministic validation and modern host integration, including native, WebAssembly and Unreal Engine.

The project separates binary analysis, a versioned intermediate representation (IR), executable module packaging, translation, explicit host runtime services and host integration so the same core infrastructure can be reused across architectures and projects rather than tied to a single game or executable.

## Current status

| Area | Status |
| --- | --- |
| E07 RV32I synthetic fixture | **PROVEN** |
| Deterministic reference/translated equivalence | **PASS** |
| Native host execution | **PASS** |
| WebAssembly host execution | **PASS** |
| Normalized OpenRecomp IR V1 specification | **FROZEN-FOR-IMPLEMENTATION** |
| RV32I -> normalized IR V1 bridge | **PASS** — E07 equivalence |
| Core API V1 reference module/runtime | **PASS** — E07 equivalence |
| Production AOT IR V1 translator | **CANDIDATE** |
| Unreal Engine 5.8 Gate B runtime | **PROVEN-RUNTIME** |
| Unreal visual replay | **PASS** |
| MIPS32 second-adapter seam | **CANDIDATE** — interface only |

The hardened E07 V1.1 fixture is the first proven architecture path and validation harness. It is a proof component of the broader OpenRecomp project, not the total intended scope.

The normalized IR V1 contract is frozen for implementation. The E07 RV32I workload now has both a deterministic bridge into V1 and a reusable Core API V1 reference module/runtime path that reproduce the proven native/golden result. The production ahead-of-time V1 translator and second guest architecture remain separately gated.

## Architecture

```text
Guest binary
    ↓
Binary analysis / architecture frontend
    ↓
Normalized versioned OpenRecomp IR
    ↓
Module Image V1
    ↓
Core runtime / AOT translation boundary
    ↓
Explicit host runtime services
    ↓
Native / WebAssembly / Unreal Engine host
```

OpenRecomp's long-term objective is reusable infrastructure for preservation, interoperability, research, tooling and legally clean static recompilation projects.

## Normalized IR V1

The frozen normalized contract is documented in [`docs/IR_SPEC_V1.md`](docs/IR_SPEC_V1.md). Its machine schema is [`schema/openrecomp-ir-v1.schema.json`](schema/openrecomp-ir-v1.schema.json).

Validate the supplied example with:

```bash
python3 tools/validate_ir_v1.py examples/ir-v1/minimal.json
python3 tools/test_ir_v1.py
```

The RV32I bridge normalizes the current proven E07 workload into V1 and independently reproduces:

```text
IR_V1_BRIDGE_CHECKSUM=122010428
IR_V1_BRIDGE_RETURN_A0=48
OPENRECOMP_RV32I_IR_V1_EQUIVALENCE=PASS checksum=122010428
```

See [`docs/RV32I_IR_V1_BRIDGE.md`](docs/RV32I_IR_V1_BRIDGE.md).

## Core API V1

[`docs/CORE_API_V1.md`](docs/CORE_API_V1.md) defines the first reusable reference module/runtime API around normalized IR V1.

The public Python reference surface includes `ModuleImage`, `GuestState`, `GuestMemory`, `HostBinding`, `CallbackHostBinding`, `ReferenceExecutor` and `ExecutionResult`. Executable packaging is defined separately from the IR by [`schema/openrecomp-module-v1.schema.json`](schema/openrecomp-module-v1.schema.json).

For the E07 fixture, Module Image V1 packaging is deterministic and the generic Core API reference executor independently reaches:

```text
CORE_API_V1_CHECKSUM=122010428
CORE_API_V1_RETURN_A0=48
CORE_API_V1_OPERATIONS=3866
OPENRECOMP_CORE_API_V1_EQUIVALENCE=PASS checksum=122010428
```

This PASS is bounded to the current normalized E07 workload. It does not yet claim that the production ahead-of-time V1 translator or MIPS32 path is proven.

## Hardened E07 proof

The E07 V1.1 proof includes machine-enforced IR/schema checks, translator-consumed host contracts, checked guest memory, deterministic translation, native/WebAssembly parity, golden validation and adversarial rejection coverage.

Run:

```bash
./RUN.sh
```

A successful E07 V1.1 run ends with:

```text
PASS: E07 V1.1 HARDENED END-TO-END
```

See the existing [`evidence/`](evidence/) directory for detailed proof artifacts.

## Unreal Engine interoperability

OpenRecomp also has a validated Unreal Engine 5.8 interoperability proof using a legally redistributable synthetic workload.

The authoritative runtime proof reaches:

```text
OPENRECOMP_GATE_B PASS x=15 y=6 rgba=ff3aa7ff frame=8
```

A separate visual replay reaches:

```text
OPENRECOMP_DEMO PASS x=15 y=6 rgba=ff3aa7ff frame=8
```

The presentation replay does not replace the authoritative runtime validation.

See [`integrations/unreal/README.md`](integrations/unreal/README.md) and [`evidence/UNREAL_GATE_B_PUBLIC_SAFE.txt`](evidence/UNREAL_GATE_B_PUBLIC_SAFE.txt).

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/IR_SPEC_V1.md`](docs/IR_SPEC_V1.md)
- [`docs/RV32I_IR_V1_BRIDGE.md`](docs/RV32I_IR_V1_BRIDGE.md)
- [`docs/CORE_API_V1.md`](docs/CORE_API_V1.md)
- [`docs/PROOF_STATUS.md`](docs/PROOF_STATUS.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)
- [`docs/BUILDING.md`](docs/BUILDING.md)
- [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md)
- [`integrations/unreal/README.md`](integrations/unreal/README.md)
- [`DEPENDENCIES.md`](DEPENDENCIES.md)

## Contributing and security

See [`CONTRIBUTING.md`](CONTRIBUTING.md) before proposing code or architecture changes. Security-sensitive reports should follow [`SECURITY.md`](SECURITY.md). Significant project changes are tracked in [`CHANGELOG.md`](CHANGELOG.md).

## Rights firewall

The public repository uses original synthetic source and standard toolchain outputs only. It does **not** contain commercial game binaries/assets, console BIOS/firmware or keys, proprietary SDK material or proprietary console executable content.

## License

OpenRecomp E07 is distributed under the Apache License, Version 2.0. See [`LICENSE`](LICENSE). Third-party build/runtime dependency boundaries are documented in [`DEPENDENCIES.md`](DEPENDENCIES.md).
