# OpenRecomp architecture

OpenRecomp separates guest-specific analysis from common translation and runtime infrastructure so new architectures and hosts can reuse the same core pipeline.

```text
guest executable
 -> architecture adapter / analysis
 -> versioned IR
 -> validation + ahead-of-time translation
 -> host runtime contract
 -> native / WebAssembly / Unreal Engine host
```

## Current proven path

The hardened E07 V1.1 fixture proves the RV32I synthetic path. Existing E07 evidence also validates deterministic translation, native execution, WebAssembly execution and golden regression behavior.

## Versioned IR and runtime boundary

The versioned IR is the boundary between guest-specific analysis and downstream translation. The host runtime contract keeps translated guest behavior separate from host services and allows the same translated model to target different environments.

## Unreal Engine interoperability

The Unreal Engine 5.8 proof demonstrates a host integration outside the native/WebAssembly fixture. The authoritative Gate B runtime validation is separate from the timer-driven visual replay used for presentation.

Expected final state:

```text
x=15
y=6
frame=8
rgba=ff3aa7ff
```

Authoritative runtime proof:

```text
OPENRECOMP_GATE_B PASS x=15 y=6 rgba=ff3aa7ff frame=8
```

Presentation replay:

```text
OPENRECOMP_DEMO PASS x=15 y=6 rgba=ff3aa7ff frame=8
```

## Generalization status

- RV32I E07 path: **PROVEN**
- Native/WebAssembly parity: **PASS**
- Unreal Gate B: **PROVEN-RUNTIME**
- MIPS32 adapter seam: **CANDIDATE** / interface only

Future guest architectures remain unproven until they pass equivalent validation gates.
