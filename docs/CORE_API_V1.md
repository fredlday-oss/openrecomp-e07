# OpenRecomp Core API V1

**Frontier:** `OPENRECOMP_CORE_API_V1`  
**API version:** `1.0.0`  
**Purpose:** reusable module/runtime boundary for normalized IR V1

Core API V1 turns the temporary RV32I bridge execution packaging into explicit reusable interfaces without changing the frozen normalized IR V1 wire contract.

## Public reference API

The Python reference package exports:

- `ModuleImage` — validated binding of normalized IR, host contract, memory image, initial state, entry point and execution limits;
- `MemorySegment` / `GuestMemory` — deterministic bounded guest memory;
- `GuestState` — typed persistent state slots declared by IR V1;
- `HostBinding` — architecture-neutral host-call boundary;
- `CallbackHostBinding` — lightweight host binding for tests and simple integrations;
- `ReferenceExecutor` — architecture-neutral executable semantics for normalized IR V1;
- `ExecutionResult` — function return, observed state, operation count and host/state snapshots.

The package is a reference implementation and validation surface. It is not yet the final production ahead-of-time translator API.

## Module Image V1

`schema/openrecomp-module-v1.schema.json` defines packaging metadata outside the IR itself.

A module image binds:

```text
normalized IR V1
+ exact IR SHA-256
+ source-input provenance
+ exact host-contract version + SHA-256
+ guest memory size and initialized segments
+ typed initial state values
+ entry function
+ state slot used for externally observed result
+ deterministic operation/call-depth limits
```

This resolves the packaging gap identified by `OPENRECOMP_RV32I_IR_V1_BRIDGE_V1`: initialized ELF data/BSS and runtime state no longer need to be interpreted as part of the IR wire format.

IR remains the normalized code/state semantics contract. Module Image V1 is the executable packaging contract.

## Integrity model

`ModuleImage.from_files()` validates all of the following before execution:

- Module Image V1 JSON Schema;
- normalized IR V1 structural and semantic validation;
- module ID and entry-function agreement with IR;
- exact normalized-IR SHA-256;
- exact host-contract SHA-256 and version;
- source-input provenance agreement;
- declared/typed initial state slots;
- observed state slot declaration;
- memory size agreement with the host contract;
- per-segment SHA-256;
- segment bounds and non-overlap;
- deterministic-fault memory policy.

The loader fails closed on mismatch rather than repairing or guessing metadata.

## Runtime interfaces

### `GuestState`

State values are constrained by the integer type declared in IR V1. Reads or writes to undeclared slots fail deterministically.

### `GuestMemory`

Guest memory owns a fixed byte array and explicit initial segments. Load/store operations enforce bounds, alignment policy, access width and module byte order.

### `HostBinding`

The normalized executor sees only:

```python
contract_version
symbols
call(symbol, args)
snapshot()
```

The executor therefore contains no RV32I, MIPS32, Unreal Engine or E07-specific host behavior.

### `ReferenceExecutor`

The reference executor implements the portable IR V1 operation families and terminators. It consumes only normalized IR, Module Image V1 and a `HostBinding`.

The executor enforces module operation and call-depth limits and rejects missing host bindings or unsupported runtime behavior.

## E07 migration/equivalence proof

The existing bridge still creates:

```text
legacy E07 IR 0.1.1
 -> normalized IR V1
 -> deterministic bridge sidecar
```

Core API V1 adds:

```text
normalized IR V1 + bridge sidecar + host contract
 -> package_ir_v1_module.py
 -> Module Image V1
 -> ModuleImage
 -> ReferenceExecutor
 -> HostBinding
 -> observable result
```

The E07 CI gate requires Module Image V1 packaging to be byte-identical across two independently normalized bridge outputs.

It then executes the normalized fixture through the Core API and compares the complete result with the earlier bridge interpreter, committed golden state and native E07 checksum.

The expected equivalence marker is:

```text
OPENRECOMP_CORE_API_V1_EQUIVALENCE=PASS checksum=122010428
```

## Why the old bridge interpreter remains

`tools/run_ir_v1_bridge.py` is intentionally retained as an independent oracle during this frontier.

Deleting it immediately would make the new Core API compare only with itself. Keeping both paths allows CI to require exact agreement while the common runtime is being extracted.

A later cleanup may retire the bridge interpreter only after the common API has independent coverage and another guest architecture exercises the same interfaces.

## Proof boundary

Core API V1 establishes a reusable reference module/runtime interface and executes the current proven E07 RV32I workload through it.

It does **not** yet prove:

- a production ahead-of-time V1 translator;
- arbitrary RV32I executables;
- MIPS32 support;
- architecture-neutrality across two implemented guest architectures;
- Unreal Engine plugin-level integration through this API.

Those remain later gates.
