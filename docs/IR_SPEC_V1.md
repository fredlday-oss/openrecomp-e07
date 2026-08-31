# OpenRecomp Normalized IR V1

**Wire version:** `1.0.0`  
**Specification status:** **FROZEN-FOR-IMPLEMENTATION**  
**Current implementation status:** **CANDIDATE** until a frontend/translator path executes this format end to end.

This document defines the first architecture-neutral OpenRecomp intermediate representation contract. It is introduced alongside the existing E07 `0.1.1` IR rather than replacing the already-PROVEN E07 path in place.

## 1. Design goals

IR V1 makes the boundary between guest-specific analysis and common translation/runtime code explicit and testable.

Core rules:

- guest instruction names do not appear as portable IR operations;
- guest delay slots, link-register conventions and other ISA-specific control rules are lowered by the frontend;
- integer width, signed comparison, memory width and misalignment behavior are explicit;
- persistent guest state is declared as typed state slots;
- function parameters and return types are explicit;
- host interaction uses named host calls rather than guest ABI assumptions;
- indirect control flow is bounded by an explicit candidate set;
- temporary values are block-local in V1;
- unknown required features are rejected rather than guessed;
- consumers fail closed on schema or semantic validation failure.

## 2. Relationship to E07

The hardened E07 proof currently emits `ir_version: 0.1.1` and the existing translator consumes RV32I-shaped decoded instruction records directly.

That path remains unchanged and **PROVEN**.

IR V1 is the normalized contract future frontend work should target. Migrating the current RV32I frontend and implementing the MIPS32 vertical slice are separate implementation frontiers. Until an execution path consumes V1, this specification must not be described as a proven runtime path.

## 3. Module envelope

Every V1 module contains:

- `ir_version` — exactly `1.0.0` for this schema;
- `module_id` — stable module identifier;
- `source` — guest architecture provenance and binary hash;
- `required_features` — capabilities a consumer must understand;
- `host_contract_version` — version of the external host contract expected by the module;
- `required_host_symbols` — complete set of host calls the module may issue;
- `state_slots` — typed persistent guest-state locations;
- `entry_function` — function ID used as the translated entry point;
- `functions` — typed normalized functions and basic blocks.

The `source` object records guest architecture, adapter identity, address width, byte order and SHA-256 of the source input. These are provenance fields; portable operations must not depend on guest opcode names.

## 4. Version and feature compatibility

OpenRecomp uses semantic-version intent for normalized IR:

- **major** — incompatible structural or semantic change;
- **minor** — additive capability gated by `required_features`;
- **patch** — clarification or validation tightening that does not change valid-program semantics.

A consumer must reject an unsupported major version and any unknown `required_features` entry.

Current V1 feature identifiers:

- `core-v1`
- `host-call`
- `bounded-indirect-jump`

A module only lists features it requires.

## 5. Integer and type model

Portable scalar types are `i1`, `i8`, `i16`, `i32`, and `i64`.

Constants are non-negative canonical bit patterns and must fit their declared width. Signed meaning is introduced by operations such as signed comparisons or sign extension, not by negative JSON integers.

Arithmetic is fixed-width modular arithmetic. Frontends must lower guest behavior that differs from the selected portable operation.

The semantic validator type-checks operation operands, casts, memory addresses, state access, branches, returns and direct-call signatures. There are no implicit integer truncations or extensions in V1.

## 6. Temporary values and explicit state

Instruction results use IDs such as `%v0`.

V1 temporaries are **block-local**. An instruction or terminator may only reference a temporary already defined earlier in the same block. Function parameters are available in the entry block.

Values that must survive a control-flow edge are represented through explicit state or memory. This avoids introducing SSA phi semantics before the project needs them.

Every persistent state slot is declared once in top-level `state_slots` with an explicit integer type. `read_state` and `write_state` must match the declared type. Names such as `gpr:a0` are frontend-defined state identifiers; common translation treats the name as opaque rather than as a guest opcode.

## 7. Function signatures

Each function declares:

- `params` — ordered typed parameters;
- `return_type` — an integer type or `null` for void;
- one or more basic blocks.

Direct `call` arguments must exactly match the callee parameter types. A produced call result, when retained, must match the callee return type. A void callee cannot produce a result.

A `return` terminator must agree with the containing function signature.

## 8. Portable instructions

### `const`
Creates a typed fixed-width constant.

### `read_state` / `write_state`
Reads or updates a declared typed guest-state slot.

### `binop`
Portable integer operations: `add`, `sub`, `mul`, `and`, `or`, `xor`, `shl`, `lshr`, `ashr`.

### `compare`
Produces `i1` with `eq`, `ne`, unsigned `ult/ule/ugt/uge`, or signed `slt/sle/sgt/sge`.

### `cast`
`zext`, `sext`, `trunc`, or same-width `bitcast`. Extension and truncation direction is validated.

### `select`
Selects one of two same-typed operands using an `i1` condition.

### `load` / `store`
Memory operations explicitly state access width, alignment, misalignment policy and load signedness. Module byte order comes from `source.endianness`.

Memory addresses must use the module address type (`i32` for a 32-bit guest, `i64` for a 64-bit guest). Stores require an explicitly width-matched value; frontends must emit a cast rather than rely on implicit truncation.

Out-of-bounds behavior remains governed by the runtime memory contract; the current OpenRecomp policy is deterministic fail-closed faulting.

### `call`
Calls another function in the same module by ID using the declared normalized signature. Guest calling conventions must already be lowered into explicit values/state.

### `host_call`
Calls a named host-contract symbol present in `required_host_symbols`. Host ABI signature authority remains the external host contract.

## 9. Terminators

Every block has exactly one terminator.

### `jump`
Transfers to a named block in the same function.

### `branch`
Transfers to one of two named blocks using an `i1` condition.

### `return`
Returns according to the containing function signature.

### `indirect_jump`
Carries an address-typed target plus a non-empty `candidate_blocks` set. Unbounded indirect control flow is not valid V1.

This does not claim every real binary can be statically bounded. A frontend that cannot establish an acceptable target set must stop at a candidate/blocking-evidence state rather than invent targets.

### `trap`
Terminates execution with an explicit deterministic reason.

## 10. Guest-specific behavior

The normalized layer intentionally has no `riscv_*`, `mips_*`, delay-slot or raw-opcode operation family.

Frontend responsibilities include:

- RV32I `jal`/`jalr` link behavior;
- MIPS32 branch/jump delay-slot behavior;
- zero-register semantics;
- calling-convention register placement;
- architecture-specific alignment/fault rules;
- special-register behavior.

A frontend lowers these semantics into portable operations, typed explicit state and explicit control flow. If a guest semantic cannot be represented correctly, the frontend must reject the module or the IR specification must be deliberately extended through the version/feature process.

## 11. Determinism

For the same normalized module and host contract, translation should be deterministic.

IR V1 forbids hidden dependencies on wall clock, random state or machine-local process state. Such behavior belongs behind an explicit host contract and must be represented as a required host capability.

## 12. Validation layers

V1 has two validation layers:

1. `schema/openrecomp-ir-v1.schema.json` validates wire structure and operation shapes.
2. `tools/validate_ir_v1.py` validates semantic/type invariants that JSON Schema cannot express cleanly.

Semantic checks include:

- supported feature set;
- unique function, parameter, block, state-slot and result IDs;
- valid entry function;
- address-width bounds;
- block-local definition-before-use;
- explicit state-slot typing;
- operation, cast, branch, return and memory type consistency;
- direct-call signature validation;
- valid direct and bounded-indirect block targets;
- declared host symbols;
- constant width bounds;
- memory alignment consistency.

`tools/test_ir_v1.py` exercises acceptance and fail-closed rejection cases.

## 13. Example

A machine-valid minimal module is provided at `examples/ir-v1/minimal.json`.

Validate it with:

```bash
python3 tools/validate_ir_v1.py examples/ir-v1/minimal.json
python3 tools/test_ir_v1.py
```

Expected markers:

```text
OPENRECOMP_IR_V1_VALID=PASS
OPENRECOMP_IR_V1_SPEC=PASS tests=15
```

## 14. Proof status

The V1 **specification and validation contract** can be mechanically tested now. That does not make the runtime implementation PROVEN.

Intended progression:

1. V1 schema/spec/validator — **FROZEN-FOR-IMPLEMENTATION**;
2. RV32I frontend lowering into V1 — future implementation gate;
3. common V1 translator/runtime path — future implementation gate;
4. MIPS32 frontend lowering into the same V1 contract — second-architecture generalization gate;
5. deterministic cross-architecture evidence — required before claiming architecture-neutral implementation as PROVEN.
