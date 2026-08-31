# OpenRecomp architecture

OpenRecomp separates guest-specific analysis from common translation and runtime infrastructure so new architectures and hosts can reuse the same core pipeline.

```text
guest executable / clean machine-code fixture
 -> architecture adapter / analysis
 -> normalized versioned IR
 -> Module Image V1
 -> common execution boundary
      |-> Core API V1 ReferenceExecutor
      `-> hardened portable C AOT backend V1
              -> private generated execution surface
              -> Native AOT ABI V1 adapter
              -> versioned native module
 -> host runtime contract
 -> Linux / Windows x64 / WebAssembly / Unreal Engine host paths
```

## RV32I proven path

The hardened E07 V1.1 fixture proves the RV32I synthetic path. Existing E07 evidence also validates deterministic translation, native execution, WebAssembly execution and golden regression behavior.

The current E07 runner uses its existing `0.1.1` proof IR, whose instruction records are still RV32I-shaped. That format remains intact so the proven evidence is not rewritten merely to introduce newer common interfaces.

The RV32I bridge lowers that proven fixture into normalized IR V1 and reproduces the native/golden result. That bridge is a bounded PASS for the current fixture/proven instruction subset, not a claim about arbitrary RV32I binaries.

## Normalized IR V1 boundary

[`IR_SPEC_V1.md`](IR_SPEC_V1.md) defines the architecture-neutral normalized IR contract with wire version `1.0.0`.

The normalized layer uses portable operations, explicit state, explicit memory semantics, named host calls and bounded control-flow targets. Guest-specific rules such as delay slots, link-register conventions and zero-register behavior are frontend responsibilities and must be lowered before common execution/translation consumes V1.

The contract itself was not extended to add MIPS32, harden the AOT backend, introduce the native ABI or pass Windows portability. Those later frontiers validate consumers of the frozen normalized boundary rather than moving guest-, compiler- or platform-specific semantics into IR V1.

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

For each current guest workload, Linux CI generates C twice, requires byte-identical output, compiles it independently with GCC and Clang under warning-as-error gates, and requires exact Core API behavioral parity. The Windows portability gate independently regenerates the same source form on Windows and compiles it with MSVC and clang-cl.

The current bounded results remain:

```text
RV32I AOT checksum=122010428, return a0=48, operations=3866
MIPS32 AOT checksum=1950232098, return v0=31, operations=100
```

## AOT hardening boundary

[`AOT_HARDENING_V1.md`](AOT_HARDENING_V1.md) adds compiler-quality evidence around the same common backend rather than creating another architecture path.

The hardening corpus is architecture-independent normalized IR. In little- and big-endian configurations it broadens coverage across the current arithmetic, comparison, cast, select, state, memory, call and control-flow operation families. Core API and GCC/Clang AOT execution must agree exactly on the successful result.

A separate nine-case valid-module corpus intentionally exercises deterministic runtime failures. Core API and AOT must agree on normalized fault categories for memory OOB, misalignment, operation limits, invalid shifts, traps, invalid bounded-indirect targets, call-depth limits, host failures and void host returns.

The same positive generated programs are also linked into standalone sanitizer executables and run under GCC and Clang AddressSanitizer + UndefinedBehaviorSanitizer. This establishes **PASS — bounded compiler-quality hardening**.

## Native AOT ABI V1 boundary

[`NATIVE_AOT_ABI_V1.md`](NATIVE_AOT_ABI_V1.md) defines the first versioned host-facing binary boundary for compiled AOT modules. Its public C header is `include/openrecomp/native_aot_abi_v1.h`.

The portable C backend's older execution functions form a **private link-time interface** for finished V1 proof modules. `tools/native_aot_abi_v1.py` consumes the validated `ModuleImage` and deterministically emits a small module-specific adapter that binds those private functions to the V1 public table.

The public module surface is discovered through one symbol:

```text
openrecomp_native_aot_query
```

The query requires the exact `0x00010000` ABI version and exact V1 structure size. It returns an immutable function table containing capability flags; module, IR, host-contract and source-provenance metadata; explicit host binding with opaque user data; execution/result/error functions; state inspection; and guest-memory inspection.

The RV32I proof exercises the V1 host callback bridge with real normalized host calls. The current MIPS32 fixture is host-call-free and exercises the same ABI without a host binding.

Native AOT ABI V1 remains **FROZEN-FOR-PORTABILITY-TESTING**. Linux GCC/Clang and Windows x64 MSVC/clang-cl now both cross that unchanged contract for the current bounded RV32I and MIPS32 workloads.

## Windows x64 native portability

[`AOT_WINDOWS_PORTABILITY_V1.md`](AOT_WINDOWS_PORTABILITY_V1.md) validates the frozen native boundary on a materially different OS/toolchain family.

The Windows gate does not rebuild a new architecture-specific interface. Linux first produces the validated IR V1, Module Image V1 and Core API reference records. Windows x64 then regenerates portable C and the ABI adapter from those exact inputs and builds both workloads independently with MSVC and clang-cl.

The unchanged public V1 header is layout-checked by both Windows compilers:

```text
sizeof(openrecomp_native_aot_host_v1) = 24
sizeof(openrecomp_native_aot_api_v1)  = 168
```

Every V1 public field offset is pinned by static assertions. `dumpbin /exports` additionally requires the complete OpenRecomp-named DLL export set to contain exactly `openrecomp_native_aot_query`.

Both compilers pass the same query/version/size/metadata/host-binding/private-surface/loader tests and reproduce the Linux/Core reference outputs exactly:

```text
RV32I  checksum=122010428, return a0=48, operations=3866
MIPS32 checksum=1950232098, return v0=31, operations=100
```

The first Windows run also exposed a cross-platform byte-integrity issue: CRLF conversion changed the checked-out host-contract bytes and Module Image hash validation correctly rejected them. `.gitattributes` now pins proof/source text to LF. The hash model was not weakened or bypassed.

## Host runtime boundary

`HostBinding` keeps normalized guest behavior separate from concrete host services. The common reference executor requires only a contract version, available symbols and a call boundary; it does not contain RV32I, MIPS32, Unreal Engine or E07 host semantics.

The native ABI preserves the same separation. Hosts provide `openrecomp_native_aot_host_v1`, which contains the V1 structure size/version, opaque user data and a normalized host-call callback. The ABI adapter forwards that callback to the generated module's private implementation surface.

Compatibility remains fail-closed: unsupported IR, invalid module metadata, integrity mismatches, ABI version/size mismatches, malformed host bindings, memory faults and execution-limit violations are rejected rather than interpreted heuristically.

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
- Native AOT ABI V1 contract: **FROZEN-FOR-PORTABILITY-TESTING**
- Native AOT ABI V1 Linux GCC/Clang: **PASS — bounded RV32I + MIPS32 execution**
- Native AOT ABI V1 Windows x64 MSVC/clang-cl: **PASS — bounded RV32I + MIPS32 execution and Linux/Core parity**
- Native AOT ABI V1 single-symbol public surface: **PASS — Linux + Windows x64 proof modules**
- General MIPS32 ISA/frontend coverage: **CANDIDATE**
- macOS / Windows ARM64 / Windows x86 Native AOT ABI parity: **CANDIDATE**
- Release-quality production AOT compiler pipeline: **CANDIDATE**
- Unreal Gate B: **PROVEN-RUNTIME**

The second guest architecture, hardened common AOT backend and versioned native ABI have crossed the common interfaces for bounded clean synthetic workloads on Linux and Windows x64. Broader architecture and compiler-platform support remains evidence-gated rather than inferred from these vertical slices.
