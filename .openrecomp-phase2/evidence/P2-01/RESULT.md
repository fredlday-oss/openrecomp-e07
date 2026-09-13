# P2-01 — Shared architecture-neutral program model V1

VERDICT: `PASS`

STAGE MARKER: `OPENRECOMP_P2_01=PASS`
TEST MARKER: `OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49`

## Baseline

| Item | Value |
| --- | --- |
| Branch | `phase2/opencode-v1` |
| `HEAD` | `1b40269cc80cd19d49d8870f8e65aa1eced69885` (P2-00 boundary) |
| Phase-1 freeze tag | `openrecomp-phase1-pass` -> `46c2f971e1a42cf49bd936bad94697b81bf31002` (unchanged) |
| Predecessor stage | P2-00 `PASS` (`evidence/P2-00/RESULT.md`) |

## Objective

Create the first shared architecture-neutral structure between the adapter /
decoder seam and normalized execution IR:

```text
DecodedInstruction -> BasicBlock -> FunctionUnit -> ProgramModel
```

with explicit provenance classification, deterministic serialization and
fail-closed graph validation. No guest semantics, IR V1 or Module Image V1
change; no P2-02+ work.

## Changes

Added (no Phase-1 semantic file modified):

| File | Role |
| --- | --- |
| `openrecomp/program_model.py` | New neutral model: `DecodedInstruction`, `BasicBlock`, `FunctionUnit`, `ProgramModel`, `Successor`, `UnresolvedSite`, enums, validator, canonical serializer, adapter-shape helper. |
| `schema/openrecomp-program-v1.schema.json` | New JSON Schema for the wire format (`program_model_version = 1.0.0`). |
| `tools/validate_program_model_v1.py` | New CLI validator (schema + graph consistency), fail-closed exit 2. |
| `tools/test_program_model_v1.py` | New deterministic 49-test gate + marker. |
| `SOURCE_SHA256SUMS.txt` | Registered the two new `tools/*.py` (109 -> 111 entries). No existing hash changed. |
| `.openrecomp-phase2/evidence/P2-01/*` | This evidence bundle. |

Frozen IR V1 (`ir_version = 1.0.0`), Module Image V1 (`1.0.0`), Core API, the AOT /
native ABI and every Phase-1 adapter/frontend are untouched.

## Model summary

- **Addresses are arbitrary-precision integers.** `ProgramSource.address_width_bits`
  is descriptive (used only to reject out-of-width addresses when present), not a
  hard 32-bit assumption. Instructions carry an optional per-instruction extent
  (`size_bytes`), so fixed- and variable-length ISAs are both representable.
- **Neutral vocabulary.** `InstructionFlow` = NORMAL / BRANCH / JUMP / CALL /
  RETURN / INDIRECT_JUMP / INDIRECT_CALL / TRAP; `EdgeKind` = FALLTHROUGH /
  BRANCH_TAKEN / BRANCH_NOT_TAKEN / JUMP / CALL_RETURN / RETURN / INDIRECT / TRAP.
  No ISA mnemonic, encoding, delay-slot, endianness or memory-map assumption
  appears in the model.
- **Direct vs unresolved control flow.** A proven static target is `direct_target`;
  a computed target is `unresolved` with no target and an unresolved `INDIRECT`
  successor. `ProgramModel.direct_call_graph()` contains direct calls only;
  `unresolved_inventory()` lists indirect call and jump sites separately.
- **Provenance.** `EvidenceClass` = `PROVEN` / `CANDIDATE`. Every instruction,
  block, function, successor and unresolved site defaults to `CANDIDATE`; nothing
  promotes automatically. Classification round-trips through serialization.
- **Determinism.** `serialize()` is canonical (sorted keys, stable separators),
  functions/blocks are emitted in `(entry_address, id)` order, successors and
  callee/site lists are sorted; `fingerprint()` is the SHA-256 of those bytes;
  `ProgramModel.deserialize()` reconstructs an equal model.
- **Graph validation.** `validate()` (run at construction and after load) enforces
  unique ids, unique entry addresses, entry agreement, declared successor/callee
  references, successor/terminator coherence, address-width agreement and derives a
  consistent predecessor map. Violations raise `ProgramModelError`.
- **Reuse.** `instruction_from_adapter()` consumes the existing adapter `decode`
  shape (`address`, `op`, optional `length`/`target`) without re-decoding; the
  schema/validator split and canonical-JSON pattern follow the existing
  IR V1 / `arch_harness_v1.py` conventions.

## Commands and results (win32 / Python 3.14.6)

```text
python tools/test_program_model_v1.py
  OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49
  exit 0
  two consecutive runs byte-identical stdout
  stdout sha256 = c52847e67a35e8890bc1e9e2c7c474e2e8dfe7bce567190018b459fb8645b9df

python tools/validate_program_model_v1.py <sample>.json
  OPENRECOMP_PROGRAM_MODEL_V1_VALID=PASS

python update_sums.py
  SOURCE_SHA256SUMS.txt: 109 -> 111 entries (2 additions, 0 modifications)

python tools/phase1_host_gates_v1.py --only source-integrity
  PASS source-integrity  verified 111 manifest entries
  OPENRECOMP_PHASE1_HOST_GATES_V1=PASS

python tools/phase1_host_gates_v1.py --json .openrecomp-phase2/evidence/P2-01/host_gates.json
  OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
  OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

## Required test coverage (49 checks)

1. Straight-line basic block: 64-bit address `0x1_0000_0000` preserved, entry
   lookup, fallthrough predecessor derivation, round-trip.
2. Conditional branch (NES `beq`, real decode): two successors
   (`BRANCH_TAKEN` + `BRANCH_NOT_TAKEN`), `BRANCH` terminal classification,
   variable-length sizes (2/1), predecessor derivation.
3. Direct call (NES `jsr`): `direct_call_graph()` = `fn_main -> fn_9000`,
   `direct_callees` recorded, no unresolved inventory.
4. Unresolved: indirect call site (function-level) + indirect jump
   (block-level), both inventoried and excluded from the direct call graph.
5. Evidence: default `CANDIDATE` for instruction/block/function and for
   `instruction_from_adapter`; `PROVEN` survives serialize/deserialize.
6. Determinism: identical serialization across rebuilds, byte round-trip,
   stable fingerprint, and order-independent serialization of functions.
7. Schema: all four sample models validate against the JSON Schema; CLI accepts a
   valid document and rejects a malformed one.
8. Fail-closed rejections (14 `ProgramModelError` cases + 5 constructor cases):
   duplicate block/function id, dangling successor, successor address mismatch,
   unknown direct callee, function-entry mismatch, return-block with successor,
   branch with one successor, call without `CALL_RETURN`, resolved indirect jump,
   address exceeding declared width, unknown entry function, unsorted
   instructions, unsupported model version, indirect instruction with a direct
   target, resolved successor without target, unresolved successor with target,
   non-serializable metadata, invalid evidence.
9. Adapter fail-closed: decoding the undocumented NES opcode `0x02` raises
   `NES6502Error` (never guessed).

## Deterministic artifacts

| Artifact | SHA-256 |
| --- | --- |
| `program_model_test.txt` (captured gate stdout) | `aa9a7f54b2610f71906719eeb092c9cf3bdf6f0805a2a7e04681b7bd48452ceb` |
| `sample_nes_call.program.json` (serialized model) | `a509bc22f90ad2d240e3202f61a7768b1151bdb52a7df6ee8dd022906ae75fcd` |
| `host_gates.json` (full Phase-1 suite) | `01b9f62392bb5c06eaab7734a202f0178773322b2a4859bcc324ce5e861a95a4` |
| `openrecomp/program_model.py` | `8fb52e18157923e5fbca1f6532d31d3748da5b84ece1d9def15802bfa40144c8` |
| `schema/openrecomp-program-v1.schema.json` | `3338e6c1925f58060fa77f31c13c0c527b067a0a58d6a7c97e6e7e48c2f51915` |
| `tools/test_program_model_v1.py` | `8d4347da236ca97c11806cd9aeb400a95e0ab69022216d425eb64dfa3ddb80e3` |
| `tools/validate_program_model_v1.py` | `b3809531c1243933ebaf93aed04aa623e0e72c5e0d8dce62aec01e1feafc693f` |

`sample_nes_call.program.json` is the model fingerprint
`a509bc22f90ad2d240e3202f61a7768b1151bdb52a7df6ee8dd022906ae75fcd`
(direct call graph `[{"from":"fn_main","to":"fn_9000"}]`).

## Architecture neutrality evidence

- A 64-bit model (`synthetic-64`, addresses above `2**32`, big-endian) and a
  16-bit NES 6502 model (real `nes6502.decode_full`, variable-length instructions)
  both build, validate and serialize through the same code.
- `openrecomp/program_model.py` imports no adapter and contains no ISA knowledge;
  the only adapter touchpoint is the documented `decode` result shape.
- The enums and field set are sufficient to describe fixed-width (MIPS/R5900/
  RISC-V-like), variable-width (6502/Z80/SM83), little- or big-endian, 16/32/64-bit
  guests without redesign, which covers the SCOPE list (NES/SNES/SMS/Mega Drive/
  GB/GBC/GBA/PS1/PSP/PS2/Xbox) at the structural layer. No such adapters are
  implemented in P2-01.

## Relevant regressions

- Full Phase-1 host suite (run once on this tree): `44 PASS / 0 FAIL / 2 SKIPPED`
  (`OPENRECOMP_PHASE1_HOST_GATES_V1=PASS`); the two skips are the toolchain-gated
  `e07-hardened-end-to-end` and `external-repro-v1`.
- `source-integrity` passes with the two new tool entries (111 total).
- No Phase-1 semantic source was modified (only `SOURCE_SHA256SUMS.txt` gained two
  entries).

## Limitations / non-claims

- The model is structural only. Block/function **recovery** is P2-02/P2-03; this
  stage validates structure supplied by a builder/recovery stage.
- No lowering to normalized IR V1 is implemented here (the bridge is later work);
  IR V1 / Module Image V1 remain frozen and unchanged.
- `schema/*.json` is still outside `SOURCE_SHA256SUMS.txt` because of the
  pre-existing `update_sums.py` `schemas/` glob gap; the new schema is therefore
  validated by the test/CLI but not by the integrity manifest (carried forward from
  P2-00).
- Unresolved semantics fail closed: they are recorded as unresolved sites, never
  as guessed targets; unsupported encodings raise at the adapter.
- No Phase-2 gate harness aggregates stage markers yet; P2-01's gate is the
  standalone deterministic test.

## Repository side effects

- Modified: `SOURCE_SHA256SUMS.txt` (two additive entries).
- Added: `openrecomp/program_model.py`,
  `schema/openrecomp-program-v1.schema.json`,
  `tools/validate_program_model_v1.py`, `tools/test_program_model_v1.py`,
  `.openrecomp-phase2/evidence/P2-01/`.
- Untouched untracked paths (excluded by the pre-flight rule):
  `.openrecomp-phase2/backups/`, `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`.
- No commit created.

## Next stage

P2-01 is `PASS`. Advance to P2-02 — deterministic basic-block recovery over the
neutral model, with malformed/ambiguous cases failing closed.
