# P1-03 — Shared architecture test/evidence harness

VERDICT: `PASS`

## Source revision and working-tree state

- `HEAD = bd5f02fcd21cf42a3d1e24a67c9a285825462b76`, branch `main` (unchanged).
- Modified in this stage: `tools/phase1_host_gates_v1.py` (two new gates), `SOURCE_SHA256SUMS.txt` (regenerated).
- Added: `tools/arch_harness_v1.py`, `examples/mips32-v1/arch-harness-v1.json`, `examples/riscv32-v1/arch-harness-v1.json`.
- No commit created.

## Deliverables

| File | Role |
| --- | --- |
| `tools/arch_harness_v1.py` | descriptor-driven deterministic harness: decode matrix + named chain recipes |
| `examples/mips32-v1/arch-harness-v1.json` | MIPS32 descriptor: 35 pinned decode cases, 4 fail-closed rejections, full fixture chain |
| `examples/riscv32-v1/arch-harness-v1.json` | RV32I descriptor: 10 pinned decode cases, 3 rejections, prebuilt IR V1 module chain |

## Harness contract

`python tools/arch_harness_v1.py <descriptor.json> [--json out.json]`

- `decode_matrix.positive`: `{address, word, op, fields}` cases; the harness requires
  the decoder to return exactly the pinned `op` and a superset of the pinned
  `fields`, and to echo the case address. Pins are derived from the documented
  instruction encodings of the guest ISA, not from the decoder.
- `decode_matrix.negative`: `{address, word}` cases that must raise the
  adapter's declared decode error (`DecodeError`, or plain `ValueError` /
  `NotImplementedError` where the adapter declares none) — fail closed, never
  guessed.
- `chains`: recipes executed through the repository's own tools and compared
  against `published` results:
  - `frontend-fixture-chain` — frontend CLI run twice (byte-identical IR /
    sidecar / report required), IR V1 validation, independent machine-code
    reference, Module Image V1 packaging + validation, Core API V1 execution,
    equivalence check (the documented CI sequence);
  - `prebuilt-ir-module` — an existing normalized IR V1 document packaged and
    executed through Module Image V1 + Core API V1 with host bindings.
- Deterministic output: no timestamps, no absolute paths, sorted JSON; exit 2
  on any failure with `OPENRECOMP_ARCH_HARNESS_V1=FAIL: <reason>`.

This harness is the per-stage proof machinery for P1-10 (SM83), P1-20 (Z80)
and P1-30 (6502-family): each stage adds a descriptor under
`examples/<arch>-v1/arch-harness-v1.json` plus a gate entry; the harness itself
does not change.

## Verification

```text
python tools/arch_harness_v1.py examples/mips32-v1/arch-harness-v1.json
PASS decode-matrix positive=35 negative_rejected=4
PASS chain frontend-fixture-chain {"checksum": 1950232098, "memory_word": 19, "operations": 100, "return_v0": 31}
OPENRECOMP_ARCH_HARNESS_V1=PASS

python tools/arch_harness_v1.py examples/riscv32-v1/arch-harness-v1.json
PASS decode-matrix positive=10 negative_rejected=3
PASS chain prebuilt-ir-module {"function_return": 22, "observed_state": 22}
OPENRECOMP_ARCH_HARNESS_V1=PASS
```

Pin provenance:

- MIPS32: all 35 fixture words pinned field-by-field from the documented
  MIPS32 instruction encoding (opcode/rs/rt/rd/funct bit positions); spot
  checks against the established adapter agreed for every sampled encoding
  (I-type rs extraction, SPECIAL functs, B/J targets, malformed-shift and
  div/divu rejections). Negatives: unsupported opcode 0x3F, misaligned
  address, `div` (funct 0x1A), malformed fixed-shift (`rs != 0`).
- RV32I: 10 canonical encodings (addi/lui/jal/sw/beq/lw/jalr/lhu/andi/bgeu)
  pinned from the documented RISC-V RV32I encoding; one initial negative case
  was corrected during development because it was actually a valid `add`
  encoding (0x008000B3), demonstrating the pin review catches author error.
  Negatives: opcode 0x7F, unsupported OP f3=1/f7=0, unsupported LOAD f3=3.

## Regression baseline

Full host-gate suite after adding `arch-harness-mips32-v1` and
`arch-harness-riscv32-v1` (run twice, byte-identical JSON):

```text
python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=20 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

`SOURCE_SHA256SUMS.txt` regenerated with `update_sums.py` (71 entries);
source-integrity gate passes.

## Semantic assumptions

- The harness pins decoder behavior to the *documented* encodings of each ISA
  (public architectural facts). Where a pin disagreed with the adapter during
  development, the pin was re-derived before the adapter was ever suspected;
  no adapter change was needed in this stage.
- Harness recipes reuse the repository's own tools as subprocesses exactly as
  CI does (`cwd=repo root`, `PYTHONPATH=repo root`), so harness evidence and
  CI evidence stay comparable.

## Remaining limitations

- Only two architectures have descriptors today; P1-10+ will add SM83 and
  later Z80/6502-family descriptors (including variable-length instruction
  decoders, which will extend the descriptor with a `bytes` form — see P1-11).
- The harness does not compile native AOT (toolchain-gated by design); Core
  API V1 is the execution reference for harness evidence.

## Verdict

`PASS` — one deterministic, reusable architecture test/evidence harness now
proves decoder coverage, fail-closed rejection, determinism and published
end-to-end results for both established architectures, with zero regressions.
