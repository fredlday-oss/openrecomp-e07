# OpenRecomp architecture

OpenRecomp separates guest-specific analysis from common translation and runtime infrastructure so new architectures and hosts can reuse the same core pipeline.

```text
guest executable / clean machine-code fixture
 -> architecture adapter / analysis
 -> normalized versioned IR
 -> Module Image V1
 -> common execution boundary
      |-> Core API V1 ReferenceExecutor
      `-> hardened portable C AOT backend V1 -> native compiled module
 -> host runtime contract
 -> native / WebAssembly / Unreal Engine host
```

## RV32I proven path

The hardened E07 V1.1 fixture proves the RV32I synthetic path. Existing E07 evidence also validates deterministic translation, native execution, WebAssembly execution and golden regression behavior.

The current E07 runner uses its existing `0.1.1` proof IR, whose instruction records are still RV32I-shaped. That format remains intact so the proven evidence is not rewritten merely to introduce newer common interfaces.

The RV32I bridge lowers that proven fixture into normalized IR V1 and reproduces the native/golden result. That bridge is a bounded PASS for the current fixture/proven instruction subset, not a claim about arbitrary RV32I binaries.

## Normalized IR V1 boundary

[`IR_SPEC_V1.md`](IR_SPEC_V1.md) defines the architecture-neutral normalized IR contract with wire version `1.0.0`.

The normalized layer uses portable operations, explicit state, explicit memory semantics, named host calls and bounded control-flow targets. Guest-specific rules such as delay slots, link-register conventions and zero-register behavior are frontend responsibilities and must be lowered before common execution/translation consumes V1.

The contract itself was not extended to add MIPS32 or to harden the AOT backend. Both later frontiers validate consumers of the frozen normalized boundary rather than moving guest-specific or compiler-specific semantics into IR V1.

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

The E07 Core API gate packages the normalized RV32I workload twice, requires byte-identical Module Image V1 output, then executes it through the generic reference API and requires exact agreement with the independent bridge, native checksum and golden state.

The MIPS32 vertical-slice gate independently packages a second guest workload with the same Module Image V1 machinery and executes it through the same `ReferenceExecutor` implementation.

## MIPS32 second-guest vertical slice

[`MIPS32_VERTICAL_SLICE_V1.md`](MIPS32_VERTICAL_SLICE_V1.md) documents the first implemented second-guest path.

Its clean little-endian machine-word fixture covers a bounded MIPS32 subset including arithmetic, signed/unsigned comparison, conditional branches, aligned memory access, direct call/return, direct jump and architectural delay slots.

Delay slots remain a frontend responsibility. For example, branch conditions are captured before the delay instruction, while the delay instruction is normalized into ordinary portable operations before the V1 branch terminator. `jal` writes the guest link register before its delay instruction and only then issues the structured V1 call.

The independent MIPS32 machine-code reference and common Core API path agree on complete normalized register state, observable memory and checksum:

```text
v0=31
memory_word=19
checksum=1950232098
delay_slots=7
```

This establishes **PASS — bounded synthetic vertical slice** for MIPS32 and **PASS — bounded two-guest generalization** for the shared IR/Module/Core boundaries. It is not a claim of full MIPS32 support.

## Portable C AOT backend V1

[`AOT_TRANSLATOR_V1.md`](AOT_TRANSLATOR_V1.md) defines the first common ahead-of-time code-generation path after normalization.

The AOT backend consumes only validated normalized IR V1 and Module Image V1. It does not decode RV32I or MIPS32 instructions and contains no guest delay-slot/link-register semantics. Instead it lowers the already-normalized operations, state accesses, memory operations, structured control flow and host-call boundary into deterministic portable C.

The generated C exposes a compact architecture-neutral native-module interface. Host behavior is supplied through a callback boundary rather than compiled into the guest translator.

For each current guest workload:

1. the backend generates C twice and requires byte-identical output;
2. the same generated C is compiled independently with GCC and Clang using `-Wall -Wextra -Werror`;
3. both native compiler paths must produce identical behavioral result JSON;
4. the native AOT result must equal the existing Core API reference result exactly.

The current results are:

```text
RV32I AOT checksum=122010428, return a0=48, operations=3866
MIPS32 AOT checksum=1950232098, return v0=31, operations=100
```

## AOT hardening boundary

[`AOT_HARDENING_V1.md`](AOT_HARDENING_V1.md) adds compiler-quality evidence around the same common backend rather than creating another architecture path.

The hardening corpus is architecture-independent normalized IR. In little- and big-endian configurations it broadens coverage across the current arithmetic, comparison, cast, select, state, memory, call and control-flow operation families. Core API and GCC/Clang AOT execution must agree exactly on the successful result.

A separate nine-case valid-module corpus intentionally exercises deterministic runtime failures. Core API and AOT must agree on normalized fault categories for memory OOB, misalignment, operation limits, invalid shifts, traps, invalid bounded-indirect targets, call-depth limits, host failures and void host returns.

The same positive generated programs are also linked into standalone sanitizer executables and run under GCC and Clang AddressSanitizer + UndefinedBehaviorSanitizer. This establishes **PASS — bounded compiler-quality hardening**, while Windows/macOS parity and a stable external ABI remain separate gates.

## Host runtime boundary

`HostBinding` keeps normalized guest behavior separate from concrete host services. The common reference executor requires only a contract version, available symbols and a call boundary; it does not contain RV32I, MIPS32, Unreal Engine or E07 host semantics.

The AOT native module uses the same architectural separation through `openrecomp_set_host_callback`: generated guest code invokes a generic callback by normalized host symbol name, while the proof runner supplies deterministic host behavior externally.

The current exported AOT surface is exercised and tested, but it is not yet frozen as a stable third-party ABI. That compatibility contract is intentionally a later frontier.

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
- MIPS32 synthetic vertical slice: **PASS — bounded IR/Module/Core equivalence**
- Shared IR V1 / Module Image V1 / Core API across RV32I + MIPS32: **PASS — bounded two-guest validation**
- Portable C AOT backend across RV32I + MIPS32: **PASS — bounded hardened dual-architecture native equivalence**
- GCC/Clang `-Werror` and current generated AOT behavior: **PASS**
- Core API/AOT deterministic fault equivalence: **PASS — 9 bounded fault classes**
- GCC/Clang ASan+UBSan hardening smoke: **PASS — Linux little/big-endian fixtures**
- General MIPS32 ISA/frontend coverage: **CANDIDATE**
- Stable external native-module ABI: **CANDIDATE**
- Release-quality production AOT compiler pipeline: **CANDIDATE**
- Unreal Gate B: **PROVEN-RUNTIME**

The second guest architecture and hardened common AOT backend have crossed the common interfaces for bounded clean synthetic workloads. Broader architecture, ABI and compiler-platform support remains evidence-gated rather than inferred from these vertical slices.
