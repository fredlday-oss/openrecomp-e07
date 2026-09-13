# OPENRECOMP Phase 1 — P1-31 Evidence

Stage: `P1-31` — NES 6502-family semantics + interrupts/control flow + IR/lowering

Revision: working tree at HEAD `bd5f02f` (no commit created; additive untracked files).

## Scope delivered

- Completed the NMOS 6502 official-opcode decoder in `adapters/nes6502.py`
  (table-driven): exactly **151 official opcodes** (`OFFICIAL`), full operand
  resolution in `decode_full` for every documented addressing mode
  (imm, zp, zp,X, zp,Y, abs, abs,X, abs,Y, (ind,X), (ind),Y, JMP (ind), rel).
  `UNDOCUMENTED` is now the exact complement (105 undocumented encodings), all
  fail closed. The adapter public API, flags, `STATE_SLOTS` (P1-30 contract)
  and `REGISTER_PAIRS` are preserved.
- Independent reference interpreter `tools/nes6502_reference_v1.py` with the
  documented NES 6502 semantics:
  - load/store/transfer/stack, logical, BIT, ADC/SBC, CMP/CPX/CPY,
    INC/DEC/INX/INY/DEX/DEY, ASL/LSR/ROL/ROR, flag ops, NOP;
  - documented N/Z/C/V flag rules; INC/DEC and shifts preserve C where
    documented; BIT drives N/V from the operand;
  - **NES 2A03 has no decimal mode** (D exists but has no effect on ADC/SBC);
    sourced from NESdev "CPU" ("lacks the MOS6502's decimal mode") and
    "Status flags" ("On the NES, decimal mode is disabled and so this flag has
    no effect"). Decimal arithmetic is deliberately NOT implemented.
  - B flag has no storage: PHP/BRK push B=1, IRQ/NMI/RTI/PLP ignore B, the
    unused bit is always pushed as 1 (NESdev "Status flags").
  - JMP (indirect) applies the documented NMOS page-boundary bug.
  - BRK/RTI, JSR/RTS return-address rules, and reset/IRQ/NMI entry
    (I masking, vectors 0xFFFA/0xFFFC/0xFFFE, SP=0xFD on reset).
- Control flow + IR V1 lowering `tools/nes6502_frontend_v1.py`:
  - static leaders for JMP abs, JSR and all eight conditional branches;
  - `jmp (indirect)` with the page-boundary bug, `rts`/`rti`/`brk` as
    `indirect_jump` terminators; BRK pushes PC+2 and P|B, sets I, vectors
    through 0xFFFE; RTI/PLP strip B and force the unused bit;
  - `extra_leaders` for externally-known dynamic indirect targets; declared
    `data_ranges` are excluded from decoding;
  - synthetic halt on the undocumented KIL/JAM byte 0x02
    (`adapters.nes6502.HALT_OPCODE`), documented as a test-harness convention
    only (no real KIL semantics claimed).

## Files changed (this stage)

Added:
- `tools/nes6502_reference_v1.py`
- `tools/test_nes6502_semantics_v1.py`
- `tools/nes6502_frontend_v1.py`
- `tools/test_nes6502_lowering_v1.py`

Modified:
- `adapters/nes6502.py` (completed/table-driven decoder; P1-30 tests preserved)
- `tools/phase1_host_gates_v1.py` (registered `nes6502-semantics-v1`,
  `nes6502-lowering-v1`)
- `SOURCE_SHA256SUMS.txt` (regenerated with `python update_sums.py`)

## Verification commands and results

```text
python tools/test_nes6502_state_v1.py
OPENRECOMP_NES6502_STATE_V1=PASS tests=10

python tools/test_nes6502_decode_v1.py
OPENRECOMP_NES6502_DECODE_V1=PASS

python tools/test_nes6502_semantics_v1.py
OPENRECOMP_NES6502_SEMANTICS_V1=PASS tests=102
(151/151 official opcodes execute; undocumented fail closed; every documented
addressing mode, branch, JMP-indirect page bug, JSR/RTS, BRK/RTI, reset/IRQ/NMI
pinned; ADC/SBC proven binary with D set)

python tools/test_nes6502_lowering_v1.py
OPENRECOMP_NES6502_LOWERING_V1=PASS tests=12
(differential reference == Core API on A/X/Y/SP/P/PC + full 64 KiB memory:
ALU/memory/stack/branch/jsr-rts fixture; indirect modes + JMP-indirect page bug;
BRK/RTI; 137/137 non-control official opcodes lowered; 15 control-flow forms;
fail-closed rejections)

python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=40 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

Both new gates are byte-identical across two consecutive runs (verified by
output hash). No pre-existing gate was weakened or removed.

## Semantic assumptions / documented sources

- Official-opcode set and addressing modes: masswerk "6502 Instruction Set"
  (standard set, 151 encodings) fetched and used as the table source.
- NES 2A03 decimal mode: NESdev "CPU" and "Status flags".
- B-flag push/ignore behaviour and bit-5-always-1: NESdev "Status flags".
- JMP-indirect NMOS page bug: masswerk address-mode notes.
- Undocumented opcodes remain fail closed (Phase 1 SCOPE defers them unless a
  later stage's tests require them).

## Limitations / deferred

- Cycle counts are not modelled (SCOPE defers cycle-perfect behavior).
- Unofficial opcodes (including KIL/JAM beyond the harness halt convention)
  fail closed.
- Interrupt *timing* (I-flag delay, hijacking) is deferred; entry mechanics
  are modelled.

## Verdict

`PASS`
