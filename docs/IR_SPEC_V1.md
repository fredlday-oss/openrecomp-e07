# OpenRecomp Normalized IR V1

**Wire version:** `1.0.0`  
**Specification status:** **FROZEN-FOR-IMPLEMENTATION**  
**Current implementation status:** **CANDIDATE** until a frontend/translator path executes this format end to end.

This document defines the first architecture-neutral OpenRecomp intermediate representation contract. It is intentionally introduced alongside the existing E07 `0.1.1` IR rather than replacing the already-PROVEN E07 path in place.

## 1. Design goals

IR V1 exists to make the boundary between guest-specific analysis and common translation/runtime code explicit and testable.

The core rules are:

- guest instruction names do not appear as portable IR operations;
- guest delay slots, link-register conventions and other ISA-specific control rules are lowered by the frontend before portable translation;
- integer width, signed comparison, memory width and misalignment behavior are explicit;
- host interaction uses named host calls rather than guest ABI assumptions;
- indirect control flow is bounded by an explicit candidate set;
- temporary values are block-local in V1;
- state that must survive a control-flow edge is explicit guest state or memory;
- unknown required features are rejected rather than guessed;
- consumers must fail closed on schema or semantic validation failure.

## 2. Relationship to E07

The hardened E07 proof currently emits `ir_version: 0.1.1` and the existing translator consumes RV32I-shaped decoded instruction records directly.

That path remains unchanged and **PROVEN**.

IR V1 is the normalized contract that future frontend work should target. Migrating the current RV32I frontend and implementing the MIPS32 vertical slice are separate implementation frontiers. Until an execution path consumes V1, this specification must not be described as a proven runtime path.

## 3. Module envelope

Every V1 module contains:

- `ir_version` — exactly `1.0.0` for this schema;
- `module_id` — stable module identifier;
- `source` — guest architecture provenance and binary hash;
- `required_features` — capabilities a consumer must understand;
- `host_contract_version` — version of the external host contract expected by the module;
- `required_host_symbols` — complete set of host calls the module may issue;
- `entry_function` — function ID used as the translated entry point;
- `functions` — normalized functions and basic blocks.

The `source` object records the guest architecture, adapter identity, address width, byte order and SHA-256 of the source input. Those fields are provenance; portable operations must not depend on guest opcode names.

## 4. Version and feature compatibility

OpenRecomp uses semantic-version intent for normalized IR:

- **major** — incompatible structural or semantic change;
- **minor** — additive capability that can be gated by `required_features`;
- **patch** — clarification or validation tightening that does not change valid-program semantics.

A consumer must reject an unsupported major version.

A consumer must also reject a module containing an unknown `required_features` entry. This prevents a newer producer from silently relying on semantics an older translator does not implement.

V1 validator feature identifiers are currently:

- `core-v1`
- `host-call`
- `bounded-indirect-jump`

A module need only list features it requires.

## 5. Integer values

Portable scalar types are:

- `i1`
- `i8`
- `i16`
- `i32`
- `i64`

Constants are represented as non-negative canonical bit patterns and must fit their declared width. Signed meaning is introduced by operations such as signed comparisons or sign extension, not by storing negative JSON integers.

Arithmetic is fixed-width modular arithmetic. Frontends are responsible for lowering any guest behavior that differs from the selected portable operation.

Shift operations are portable operations, not guest opcodes. A frontend must explicitly normalize guest-specific shift-count behavior before or while constructing V1.

## 6. Temporary values and explicit state

Instruction results use IDs such as `%v0`.

V1 temporaries are **block-local**. An instruction or terminator may only reference a temporary already defined earlier in the same block.

Values that must survive a control-flow edge must be represented through explicit state or memory. This constraint is deliberate: it avoids introducing SSA phi semantics before the project needs them and keeps the first cross-architecture contract simple to validate.

`read_state` and `write_state` address named state slots. Slot names are frontend-defined provenance such as `gpr:a0`; common translation treats them as opaque state identifiers rather than architecture-specific opcodes.

## 7. Portable instructions

V1 defines the following instruction families.

### `const`

Creates a typed fixed-width constant.

### `read_state` / `write_state`

Reads or updates an explicit guest-state slot.

### `binop`

Portable integer operations:

`add`, `sub`, `mul`, `and`, `or`, `xor`, `shl`, `lshr`, `ashr`.

### `compare`

Produces `i1` using an explicit predicate:

`eq`, `ne`, unsigned `ult/ule/ugt/uge`, or signed `slt/sle/sgt/sge`.

### `cast`

`zext`, `sext`, `trunc`, or `bitcast`.

### `select`

Selects one of two operands from an `i1`-style condition.

### `load` / `store`

Memory operations explicitly state:

- access width: 8/16/32/64 bits;
- alignment requirement;
- `misaligned_policy`: `allow` or `fault`;
- load signedness.

Module byte order comes from `source.endianness`.

Out-of-bounds behavior remains governed by the host/runtime memory contract. The existing project policy is fail-closed deterministic faulting.

### `call`

Calls another function in the same V1 module by function ID. Guest calling conventions must already have been lowered into explicit values/state.

### `host_call`

Calls a named host-contract symbol. The symbol must be present in `required_host_symbols`.

A call may omit `result` and `result_type` for a void result. If either is present, both must be present.

## 8. Terminators

Every block has exactly one terminator.

### `jump`

Transfers to a named block in the same function.

### `branch`

Transfers to one of two named blocks according to a condition operand.

### `return`

Returns from the current normalized function, optionally with a value.

### `indirect_jump`

Carries a target value plus a non-empty `candidate_blocks` set. Unbounded indirect control flow is not valid V1.

This does not claim that every real binary can be statically bounded. It defines the contract required for the V1 translator. A frontend that cannot establish an acceptable target set must stop at a candidate/blocking evidence state rather than invent targets.

### `trap`

Terminates execution with an explicit deterministic reason.

## 9. Guest-specific behavior

The normalized layer intentionally has no `riscv_*`, `mips_*`, delay-slot or raw-opcode operation family.

Examples of frontend responsibilities include:

- RV32I `jal`/`jalr` link behavior;
- MIPS32 branch/jump delay-slot behavior;
- architecture-specific zero-register behavior;
- calling-convention register placement;
- architecture-specific alignment/fault rules;
- special-register behavior.

A frontend lowers those semantics into portable operations, explicit state and explicit control flow. If a guest semantic cannot be represented correctly, the frontend must reject the module or the IR specification must be deliberately extended through the version/feature process.

## 10. Determinism

For the same normalized module and host contract, translation should be deterministic.

IR V1 forbids hidden dependencies on wall clock, random state or machine-local process state. Such behavior belongs behind an explicit host contract and must be represented as a required host capability.

## 11. Validation layers

V1 has two validation layers:

1. `schema/openrecomp-ir-v1.schema.json` validates wire structure and operation shapes.
2. `tools/validate_ir_v1.py` validates semantic invariants that JSON Schema cannot express cleanly.

Semantic checks include:

- supported feature set;
- unique function/block/result IDs;
- valid entry function;
- address-width bounds;
- block-local definition-before-use;
- valid direct and indirect block targets;
- declared host symbols;
- valid call targets;
- call result/result-type pairing;
- constant width bounds;
- memory alignment consistency.

`tools/test_ir_v1.py` exercises both acceptance and rejection cases.

## 12. Example

A machine-valid minimal module is provided at:

`examples/ir-v1/minimal.json`

Validate it with:

```bash
python3 tools/validate_ir_v1.py examples/ir-v1/minimal.json
python3 tools/test_ir_v1.py
```

Expected markers:

```text
OPENRECOMP_IR_V1_VALID=PASS
OPENRECOMP_IR_V1_SPEC=PASS tests=11
```

## 13. Proof status

The V1 **specification and validation contract** can be mechanically tested now.

That does not make the runtime implementation PROVEN. The intended progression is:

1. V1 schema/spec/validator — **FROZEN-FOR-IMPLEMENTATION**;
2. RV32I frontend lowering into V1 — future implementation gate;
3. common V1 translator/runtime path — future implementation gate;
4. MIPS32 frontend lowering into the same V1 contract — second-architecture generalization gate;
5. deterministic cross-architecture evidence — required before claiming architecture-neutral implementation as PROVEN.
