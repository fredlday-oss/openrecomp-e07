# P1-10 — SM83 architectural state: registers, flags, PC/SP

VERDICT: `PASS`

## Source revision and working-tree state

- `HEAD = bd5f02fcd21cf42a3d1e24a67c9a285825462b76`, branch `main` (unchanged).
- Modified: `tools/phase1_host_gates_v1.py` (new gate), `SOURCE_SHA256SUMS.txt` (regenerated).
- Added: `adapters/sm83.py` (state model; decoder arrives in P1-11), `tools/test_sm83_state_v1.py`.
- No commit created.

## Deliverables

| File | Role |
| --- | --- |
| `adapters/sm83.py` | documented SM83 architectural state: `ArchitectureInfo`, flag masks, register pairs, IR state-slot table, fail-closed `SM83Error` |
| `tools/test_sm83_state_v1.py` | 8-test deterministic gate + neutral-chain AF-composition proof |

## Documented facts pinned (all public Sharp SM83 / Game Boy hardware documentation)

1. **Registers**: 8-bit A (accumulator), F (flags), B, C, D, E, H, L.
2. **Flags** live in F: bit 7 `Z` (0x80), bit 6 `N` (0x40), bit 5 `H` (0x20), bit 4 `C` (0x10); the low nibble is documented as always zero and must be masked on writes (`FLAG_WRITE_MASK = 0xF0`).
3. **Pairs** are formed high byte first: AF, BC, DE, HL.
4. **SP** is a standalone 16-bit register (no pair).
5. **PC** is 16-bit implicit control flow: no general instruction reads it except through control flow, so it is modelled by structured control flow (blocks/terminators) and is intentionally absent from the state-slot table — the same treatment the MIPS32 frontend applies to its PC.
6. **Address space** is 16 bits. Frozen IR V1 requires `source.address_bits ∈ {32,64}`, so the contract's narrow-address rule applies: guest addresses are carried zero-extended in `i32`, PC/SP/pointer arithmetic wraps at 16 bits inside the frontend (frontend work, P1-13).

## State-slot model (normalized IR V1 boundary)

```text
cpu:a i8   cpu:f i8   cpu:b i8   cpu:c i8   cpu:d i8
cpu:e i8   cpu:h i8   cpu:l i8   cpu:sp i16
```

Slot naming follows the established `gpr:rN` convention. Flag *updates* are computed as `i1` compares and assembled into the `cpu:f` byte by the frontend (P1-12 semantics); the byte-level F register matches hardware PUSH/POP AF behavior.

## Verification

```text
python tools/test_sm83_state_v1.py
OPENRECOMP_SM83_STATE_V1=PASS tests=8
```

- architecture-info: `sm83-gb`, 8-bit, little, documented register tuple, documented calling-convention string.
- flag positions and write mask pinned to the documented values.
- state-slot table equality (9 slots; `cpu:pc` absent).
- pair table AF/BC/DE/HL with high-byte-first halves; each half has an `i8` slot.
- pair composition round-trip on 5 sampled 16-bit values + `pair_of(0x3E,0xB0) == 0x3EB0`.
- fail-closed: pair high byte > 0xFF, negative low byte, split above 16 bits, negative split — all raise `SM83Error`.
- `decode` raises `NotImplementedError` until the P1-11 decoder lands (no silent semantics).
- neutral-chain proof: an AF-composition function built through the shared
  scaffolding (`IRBuilder`, i8 reads, `zext` i8→i16, `shl 8`, `or`, `write_state`)
  validated as IR V1, packaged as Module Image V1 and executed twice through the
  Core API `ReferenceExecutor`:

```text
observed_state  = 0x3EB0   (cpu:a=0x3E, cpu:f=0xB0)
function_return = 0x3EB0
cpu:sp          = 0xFFFE
operations      = 8        (pinned after the first verified run)
```

Full host-gate regression:

```text
python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=21 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

`SOURCE_SHA256SUMS.txt` regenerated with `update_sums.py` (73 entries); integrity gate passes.

## Semantic assumptions

- All register/flag/pair facts come from publicly documented SM83 hardware behavior; no undocumented opcode or behavior was inferred.
- PC is excluded from state slots by design (structured control flow), matching the existing MIPS32 treatment — this is a modelling decision, documented in the adapter.
- 16-bit guest addresses are represented at `address_bits=32` per the frozen IR V1 constraint and the P1-01 contract's narrow-address rule.

## Remaining limitations

- Flag-update semantics (Z/N/H/C computations per instruction) arrive in P1-12.
- The decoder (base table + CB prefix) arrives in P1-11.
- No platform (memory map, I/O) knowledge exists at this stage.

## Verdict

`PASS` — the documented SM83 architectural state model is pinned by an
executable gate and proven to flow through frozen IR V1, Module Image V1 and
Core API V1 deterministically, with no changes to existing paths.
