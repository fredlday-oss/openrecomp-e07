# OpenRecomp

OpenRecomp is an open-source, architecture-neutral static recompilation framework with deterministic validation and modern host integration, including native, WebAssembly and Unreal Engine.

The project separates binary analysis, a versioned intermediate representation (IR), ahead-of-time translation, explicit host runtime services and host integration so the same core infrastructure can be reused across architectures and projects rather than tied to a single game or executable.

## Current status

| Area | Status |
| --- | --- |
| E07 RV32I synthetic fixture | **PROVEN** |
| Deterministic reference/translated equivalence | **PASS** |
| Native host execution | **PASS** |
| WebAssembly host execution | **PASS** |
| Normalized OpenRecomp IR V1 specification | **FROZEN-FOR-IMPLEMENTATION** |
| Unreal Engine 5.8 Gate B runtime | **PROVEN-RUNTIME** |
| Unreal visual replay | **PASS** |
| MIPS32 second-adapter seam | **CANDIDATE** — interface only |

The hardened E07 V1.1 fixture is the first proven architecture path and validation harness. It is a proof component of the broader OpenRecomp project, not the total intended scope.

The normalized IR V1 contract is specified and mechanically validated, but it is intentionally **not** described as a proven runtime path until the current RV32I frontend/translator and a second guest architecture execute through that common representation.

## Architecture

```text
Guest binary
    ↓
Binary analysis / architecture frontend
    ↓
Normalized versioned OpenRecomp IR
    ↓
Ahead-of-time translation
    ↓
Explicit host runtime services
    ↓
Native / WebAssembly / Unreal Engine host
```

OpenRecomp's long-term objective is reusable infrastructure for preservation, interoperability, research, tooling and legally clean static recompilation projects.

## Normalized IR V1

The first frozen normalized contract is documented in [`docs/IR_SPEC_V1.md`](docs/IR_SPEC_V1.md). Its machine schema is [`schema/openrecomp-ir-v1.schema.json`](schema/openrecomp-ir-v1.schema.json).

Validate the supplied example with:

```bash
python3 tools/validate_ir_v1.py examples/ir-v1/minimal.json
python3 tools/test_ir_v1.py
```

IR V1 is additive to the existing E07 `0.1.1` proof format. Migration of RV32I into normalized V1 is a later implementation gate so the already-PROVEN E07 path is not rewritten merely to publish the specification.

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
