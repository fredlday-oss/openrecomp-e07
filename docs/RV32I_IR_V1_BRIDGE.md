# RV32I to OpenRecomp IR V1 bridge

**Frontier:** `OPENRECOMP_RV32I_IR_V1_BRIDGE_V1`  
**Status:** **PASS — E07 equivalence**  
**Validated checksum:** `122010428`  
**Validated return state:** `a0 = 48`

This is the first implementation bridge from the existing E07 `0.1.1` RV32I representation to the normalized OpenRecomp IR `1.0.0` contract.

The bridge is deliberately additive. It does not replace or rewrite the already-PROVEN E07 path.

## Purpose

The bridge answers a narrower question before MIPS32 work begins:

> Can the current proven RV32I fixture be normalized into IR V1 and still produce the same deterministic observable result?

The answer for the current E07 fixture and proven RV32I subset is **yes**. This remains an implementation/equivalence gate for the normalized IR contract, not a claim that the final production translator API is complete.

## Pipeline

```text
synthetic RV32I ELF
        |
        v
existing E07 loader / decoder
        |
        v
legacy E07 IR 0.1.1
        |
        v
bridge_rv32i_ir_v1.py
        |
        +----> normalized IR V1 1.0.0
        |
        +----> deterministic execution sidecar
                       |
                       v
              run_ir_v1_bridge.py
                       |
                       v
             observable state/checksum
                       |
                       v
        compare with proven E07 native + golden state
```

## Normalization rules

The bridge lowers the RV32I subset already proven by E07 into portable V1 operations.

- `addi` -> `binop add`
- `andi` -> `binop and`
- `slli` -> `binop shl`
- `srli` -> `binop lshr`
- `add` / `xor` -> matching portable `binop`
- `lui` -> typed `const`
- `lw` / `lhu` -> explicit address calculation + typed `load`
- `sw` -> explicit address calculation + `store`
- `beq` / `bne` / `bltu` / `bgeu` -> typed `compare` + `branch`
- direct `jal` calls -> structured `call` or named `host_call`
- standard `jalr x0,0(ra)` -> structured `return`

Guest register values are represented as explicit V1 state slots (`gpr:x1` through `gpr:x31`). Register x0 is normalized as constant zero and writes to x0 are discarded.

For direct calls the bridge still writes the guest link register with the architectural return PC before issuing the structured V1 call. This preserves guest-visible link-register state for compiler-generated prologue/epilogue code while allowing portable V1 control flow to represent the call itself.

Any `jalr` pattern other than the standard return form is rejected by this V1 bridge. The bridge does not invent an indirect-call target set.

## Execution sidecar

IR V1 deliberately remains unchanged by this frontier.

The E07 loader already exposes initialized ELF allocation sections, while IR V1 currently describes normalized code/state semantics rather than an executable image container. The bridge therefore emits a separate deterministic sidecar containing:

- initial stack-pointer state used by the existing E07 runtime;
- non-`.text` allocatable memory bytes from the validated loader;
- memory-size contract;
- source hashes;
- operation limit;
- the state slot used for the final `a0` observation.

This sidecar is bridge/runtime packaging, **not part of the IR V1 wire contract**. Module packaging belongs in a later core API/runtime frontier.

## Equivalence gate

The CI proof first runs the complete existing E07 hardened proof. It then:

1. normalizes the generated legacy IR twice and requires byte-identical V1 output and sidecars;
2. validates the generated normalized document using `tools/validate_ir_v1.py`;
3. executes the V1 representation with `tools/run_ir_v1_bridge.py`;
4. compares final `a0`, host-call counters and checksum with committed golden state;
5. independently compares the V1 checksum with the native E07 checksum produced in the same CI run;
6. rejects any legacy guest opcode name appearing as a normalized V1 `op`.

The validated CI run produced:

```text
OPENRECOMP_RV32I_IR_V1_NORMALIZATION_DETERMINISTIC=PASS
OPENRECOMP_IR_V1_VALID=PASS
IR_V1_BRIDGE_CHECKSUM=122010428
IR_V1_BRIDGE_RETURN_A0=48
OPENRECOMP_IR_V1_BRIDGE_RUNTIME=PASS
IR_V1_BRIDGE_FUNCTIONS=7
IR_V1_BRIDGE_OPERATIONS=3866
OPENRECOMP_RV32I_IR_V1_EQUIVALENCE=PASS checksum=122010428
```

The portable operation set observed by the bridge was:

```text
binop, branch, call, compare, const, host_call, jump,
load, read_state, return, store, write_state
```

No legacy RV32I opcode name is accepted as a normalized V1 operation.

## Proof boundary

This PASS proves equivalence for the current synthetic E07 RV32I fixture and proven instruction subset.

It does **not** prove:

- arbitrary RV32I executables;
- unsupported indirect calls;
- MIPS32;
- a final production OpenRecomp runtime API;
- a generic binary/container packaging format.

MIPS32 remains **CANDIDATE** until its own implementation and equivalence gates pass.
