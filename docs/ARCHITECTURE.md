# OpenRecomp architecture

OpenRecomp separates guest-specific analysis from common translation and runtime infrastructure so new architectures and hosts can reuse the same core pipeline.

```text
guest executable
 -> architecture adapter / analysis
 -> normalized versioned IR
 -> Module Image V1
 -> common runtime / ahead-of-time translation boundary
 -> host runtime contract
 -> native / WebAssembly / Unreal Engine host
```

## Current proven path

The hardened E07 V1.1 fixture proves the RV32I synthetic path. Existing E07 evidence also validates deterministic translation, native execution, WebAssembly execution and golden regression behavior.

The current E07 runner uses its existing `0.1.1` proof IR, whose instruction records are still RV32I-shaped. That format remains intact so the proven evidence is not rewritten merely to introduce newer common interfaces.

## Normalized IR V1 boundary

[`IR_SPEC_V1.md`](IR_SPEC_V1.md) defines the architecture-neutral normalized IR contract with wire version `1.0.0`.

The normalized layer uses portable operations, explicit state, explicit memory semantics, named host calls and bounded control-flow targets. Guest-specific rules such as delay slots, link-register conventions and zero-register behavior are frontend responsibilities and must be lowered before common execution/translation consumes V1.

The E07 RV32I bridge now lowers the current proven fixture into normalized IR V1 and reproduces the native/golden result. That bridge is a bounded PASS for the current fixture/proven instruction subset, not a claim about arbitrary RV32I binaries.

## Module Image V1 and Core API

[`CORE_API_V1.md`](CORE_API_V1.md) defines the reusable reference module/runtime boundary around normalized IR V1.

IR V1 describes normalized code and typed guest-state semantics. Module Image V1 packages the execution context separately:

- exact IR and host-contract hashes;
- initialized guest-memory segments;
- initial typed state;
- entry/observation contract;
- deterministic execution limits;
- provenance.

The `openrecomp` reference package exposes `ModuleImage`, `GuestMemory`, `GuestState`, `HostBinding` and `ReferenceExecutor`.

The E07 Core API gate packages the same normalized RV32I workload twice, requires byte-identical Module Image V1 output, then executes it through the generic reference API and requires exact agreement with the independent bridge, native checksum and golden state.

The Core API V1 reference path is therefore **PASS — E07 equivalence**. A production ahead-of-time translator consuming this API remains **CANDIDATE**.

## Host runtime boundary

`HostBinding` keeps normalized guest behavior separate from concrete host services. The common executor requires only a contract version, available symbols and a call boundary; it does not contain RV32I, MIPS32, Unreal Engine or E07 host semantics.

Compatibility is fail-closed: unsupported IR, invalid module metadata, missing host bindings, integrity mismatches, memory faults and execution-limit violations are rejected rather than interpreted heuristically.

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
- Normalized IR V1 specification: **FROZEN-FOR-IMPLEMENTATION**
- RV32I -> normalized IR V1 bridge: **PASS — E07 equivalence**
- Core API V1 reference module/runtime: **PASS — E07 equivalence**
- Production AOT V1 translator: **CANDIDATE**
- Unreal Gate B: **PROVEN-RUNTIME**
- MIPS32 adapter seam: **CANDIDATE** / interface only

A broader architecture-neutral implementation is not PROVEN until at least a second guest architecture crosses equivalent deterministic gates through the same common interfaces.
