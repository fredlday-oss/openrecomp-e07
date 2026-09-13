# P1-02 — Multi-architecture core scaffolding without regression

VERDICT: `PASS`

## Source revision and working-tree state

- `HEAD = bd5f02fcd21cf42a3d1e24a67c9a285825462b76`, branch `main` (unchanged during this stage).
- No commit created. No existing file was modified in this stage except
  `tools/phase1_host_gates_v1.py` (one new gate entry) and `SOURCE_SHA256SUMS.txt` (regenerated).

## Deliverables

| File | Role |
| --- | --- |
| `openrecomp/frontends/__init__.py` | new additive package (docstring only) |
| `openrecomp/frontends/scaffold.py` | architecture-neutral, fail-closed scaffolding: `validate_decode` (decode-contract shape) and `IRBuilder` (IR V1 + execution-sidecar assembly) |
| `tools/test_frontend_scaffold_v1.py` | 28-test fail-closed gate + deterministic synthetic Core API proof |

## Design (strictly additive, contract-driven)

`openrecomp/frontends/scaffold.py` implements the executable frontend contract
(`contracts/frontend_contract_v1.json`, `docs/FRONTEND_CONTRACT_V1.md`) for NEW
guest frontends. The established RV32I and MIPS32 paths do not import it and
were not modified.

- `validate_decode(insn)` fails closed on a non-dict result, an address outside
  the guest address space, a missing/empty op name, or a malformed instruction
  word.
- `IRBuilder` assembles normalized IR V1 and its execution sidecar and
  re-validates every document with `tools.validate_ir_v1.validate_document`
  before returning it — a scaffolding-built document can never bypass frozen
  IR V1. Checks mirror the validator/executor rules exactly (never stricter):
  declared slots/types, unique ids, defined-only operands, exact
  `i<address_bits>` address operands, store value width == access width,
  normalized constant shift counts (the executor faults on unnormalized
  runtime shifts), one terminator per block, non-overlapping in-range memory
  segments, declared entry function/observe slot/initial state.
- `zext_to_address` encodes the contract's `narrow_address_rule` for
  SM83/Z80/6502-family guests (zero-extended guest addresses in `i32`).
- No guest-ISA knowledge exists anywhere in the scaffolding; per-ISA decoders
  and lowerings belong to `adapters/<architecture>.py` and
  `tools/<architecture>_frontend_v1.py` (P1-10+).

## Verification

New gate `frontend-scaffold-v1` (added to `tools/phase1_host_gates_v1.py`):

```text
python tools/test_frontend_scaffold_v1.py
OPENRECOMP_FRONTEND_SCAFFOLD_V1=PASS tests=28
```

The 28 tests cover:

- 5 decode-contract rejections (missing op, negative/bool address, non-int word, non-dict);
- 14 emit-time rejections (undeclared slot, unnormalized shift, duplicate result id,
  undefined operand, store width mismatch, load address type, write type mismatch,
  cast width rule, compare type mismatch, undeclared host symbol, call result/type pairing,
  empty trap reason, instruction after terminator, duplicate terminator);
- 6 build-time rejections (missing terminator, unknown jump target, OOB segment,
  undeclared initial-state slot, unknown entry function, undeclared observe slot);
- build determinism (two builds byte-identical);
- sidecar contract shape (all six required keys, source hash provenance);
- the deterministic synthetic proof.

### Synthetic 8-bit-style proof through the neutral chain

A synthetic workload built purely through the scaffolding (i8/i1 state slots,
8-bit arithmetic with wrap, compare+branch, i8 loads/stores, zero-extended
address, select, direct call to a second function, plus a validated-but-unreached
`indirect_jump` dispatch block and `trap` block) was packaged as Module Image V1
and executed twice through the architecture-neutral Core API `ReferenceExecutor`:

```text
observed_state = 10
function_return = 10
memory[0..1]    = [122, 10]
operations      = 27   (pinned after the first verified run)
```

Both runs produced identical state; the IR/sidecar are byte-identical across
two builds. The expectation was hand-derived from the fixture bytes before
pinning (documented in the test file header).

## Regression baseline

```text
python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=18 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

Existing gates unchanged: `frontend-contract-v1` still reports
`CHECKS=20 PROBES=13 CHAIN_PROOFS=2 FAIL=0`; the MIPS32 vertical-slice chain
still reproduces `checksum=1950232098 return_v0=31 operations=100
delay_slots=7`; RV32I minimal module still yields `observed_state=22`.
`SOURCE_SHA256SUMS.txt` regenerated with `update_sums.py` (69 entries) and the
integrity gate passes.

## Semantic assumptions

None about CPU behaviour. The only modelling decisions are the contract's
documented rules: narrow-address guests are modelled at `address_bits=32`, and
the scaffolding mirrors the validator/executor semantics without extending
frozen IR V1.

## Remaining limitations

- The scaffolding is proven by a synthetic fixture, not yet by a real guest
  decoder; SM83 (P1-10+), Z80 (P1-20+) and 6502-family (P1-30+) frontends will
  be the first production consumers.
- Variable (non-constant) shift amounts remain the caller's normalization
  obligation, exactly as in the existing IR V1 contract.

## Verdict

`PASS` — additive, architecture-neutral scaffolding exists with a fail-closed
28-test gate and a deterministic synthetic proof through frozen IR V1, Module
Image V1 and Core API V1; no existing behaviour changed.
