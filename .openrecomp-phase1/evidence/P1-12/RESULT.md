# P1-12 — SM83 documented instruction semantics

VERDICT: `PASS`

## Source revision and working-tree state

- `HEAD = bd5f02fcd21cf42a3d1e24a67c9a285825462b76`, branch `main` (unchanged).
- Modified: `tools/phase1_host_gates_v1.py` (one gate), `SOURCE_SHA256SUMS.txt` (regenerated).
- Added: `tools/sm83_reference_v1.py`, `tools/test_sm83_semantics_v1.py`.
- No commit created.

## Deliverables

| File | Role |
| --- | --- |
| `tools/sm83_reference_v1.py` | independent SM83 machine-code reference interpreter (the P1-15 differential oracle, mirroring the MIPS32 `oracle/reference` pattern) |
| `tools/test_sm83_semantics_v1.py` | 62-test deterministic gate: hand-derived documented-semantics pins + full-coverage execution |

## Documented semantics implemented (public SM83 documentation only)

- 8-bit ALU with Z/N/H/C: H from bit 3→4 carry, C from bit 7→8; SUB/SBC/CP set N; AND sets H and clears N/C; XOR/OR clear N/H/C; INC/DEC set Z/H, clear N, preserve C.
- 16-bit: ADD HL,rr (H from bit 11, C from bit 15, Z preserved); ADD SP,r8 and LD HL,SP+r8 (Z=0, N=0, H/C from the low-byte addition); INC/DEC rr leave flags untouched.
- Rotates/shifts: RLCA/RRCA/RLA/RRA (Z=N=H=0, C=shifted bit); CB RLC/RRC/RL/RR/SLA/SRA/SRL (Z from result, C=shifted bit); SWAP clears C; BIT sets Z=!bit, H=1, C preserved; RES/SET leave flags.
- DAA with the documented algorithm; **N preserved**, H reset, Z from result, C per rule (a test pin caught an initial N-clobbering bug — fixed before PASS).
- Stack: PUSH high-byte-first, POP AF masks the F low nibble (0xF0), CALL/RET/RST with 16-bit SP wrap; RETI sets IME; EI takes effect after the next instruction; DI immediate (delay pinned by two tests).
- Memory: 64 KiB bounds-checked model; 16-bit reads wrap at 0xFFFF (documented bus behaviour — pinned).
- HALT/STOP terminate (`halted`); undocumented opcodes raise `SM83ReferenceError` fail-closed; step limits enforced; cycles intentionally unmodelled (out of scope, as in the MIPS32 reference).

## Verification

```text
python tools/test_sm83_semantics_v1.py
OPENRECOMP_SM83_SEMANTICS_V1=PASS tests=62
```

62 tests = 54 hand-derived pins (ALU/flag matrix, 16-bit arithmetic, rotates,
shifts, BIT/RES/SET, DAA both directions, flag-only ops, stack round-trips,
control-flow round-trips, EI/DI delay, LDH/LD memory forms, 0xFFFF wrap) +
full-coverage execution of all 245 documented base opcodes and all 256 CB
encodings in a halt-filled memory model + fail-closed rejections
(undocumented opcode, step-limit exceeded).

Full host-gate regression:

```text
python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=24 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

`SOURCE_SHA256SUMS.txt` regenerated (`update_sums.py`); integrity gate passes.

## Semantic assumptions

- Only publicly documented SM83 behavior; the reference is deliberately written independently of the P1-13 lowering so the P1-15 differential proof compares two separately implemented semantic models.
- Interrupt *servicing* (IE/IF, vectors, priority) is platform behaviour and stays out of the CPU reference until P1-14 (EI/DI/IME state is already modelled).

## Verdict

`PASS` — documented SM83 instruction semantics are implemented in an independent reference interpreter and pinned by 62 deterministic tests with full documented-opcode execution coverage.
