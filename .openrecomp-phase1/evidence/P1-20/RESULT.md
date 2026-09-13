# P1-20 — Z80 architectural state + decoder

VERDICT: `PASS`

## Source revision and working-tree state

- `HEAD = bd5f02fcd21cf42a3d1e24a67c9a285825462b76`, branch `main` (unchanged).
- Modified: `tools/phase1_host_gates_v1.py` (two gates), `SOURCE_SHA256SUMS.txt`
  (regenerated).
- Added: `adapters/z80.py`, `tools/test_z80_state_v1.py`,
  `tools/test_z80_decode_v1.py`.
- No commit created. No ROM bytes involved.

## Deliverables

| File | Role |
| --- | --- |
| `adapters/z80.py` | documented Z80 state model (full register/shadow file, IX/IY/SP/PC, flags S/Z/H/P/V/N/C with X/Y pinned 0, I/R, IFF1/IFF2/IM) + complete documented decoder (base 256, ED 65, CB 248, DD/FD index forms, DDCB/FDCB (IX+d)/(IY+d) forms) with fail-closed undocumented/truncated handling |
| `tools/test_z80_state_v1.py` | 6-test deterministic state gate `OPENRECOMP_Z80_STATE_V1=PASS` |
| `tools/test_z80_decode_v1.py` | 14-test deterministic decode gate `OPENRECOMP_Z80_DECODE_V1=PASS` |

## Documented facts implemented (public references)

- Zilog Z80 CPU User Manual primary encodings; z80-heaven opcode reference
  chart (fetched and quoted); z80.info DD/FD decoding rules.
- Base map: all 256 opcodes, the documented 8 condition codes
  (nz/z/nc/c/po/pe/p/m), RST vectors, high-byte-first pairs.
- ED page: 65 primary documented encodings (IN r,(C) ×7, OUT (C),r ×7,
  SBC/ADC HL,rp ×4+4, LD (nn),rp / LD rp,(nn) ×4+4, NEG ×8, RETN ED 45,
  RETI ED 4D, IM ED 46/56/5E, LD I,A / LD R,A / LD A,I / LD A,R, RRD, RLD,
  16 block-transfer ops). The 191 remaining ED encodings fail closed
  (IN F,(C), OUT (C),0, the RETN/RETI/IM alias bytes, ED 76, ...).
- CB page: 248 documented encodings (RLC/RRC/RL/RR/SLA/SRA/SRL + BIT/RES/SET
  ×8 operands). CB 30-37 (SLL) fails closed (Z180 only, not in the Z80
  manual).
- DD/FD: documented IX/IY pair forms and (IX+d)/(IY+d) forms with the
  displacement after the opcode byte; DD/FD before an instruction not
  involving H/L/(HL) is ignored (documented); DD/FD followed by another
  DD/ED/FD processes the second prefix; IXH/IXL register-split forms fail
  closed (undocumented in the Zilog manual); DDCB/FDCB decode only the
  documented (IX+d)/(IY+d) operand forms (31 per prefix) and fail closed on
  register-operand forms.
- State: complete shadow set with the documented EXX / EX AF,AF' exchange
  semantics; the undocumented X/Y flag bits are pinned to 0 (documented
  limitation).

## Verification

```text
python tools/test_z80_state_v1.py
OPENRECOMP_Z80_STATE_V1=PASS tests=6

python tools/test_z80_decode_v1.py
OPENRECOMP_Z80_DECODE_V1=PASS tests=14

python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=31 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

## Pinned deterministic results

- base decode coverage 256/256; ED 65/65 documented + 191 rejected;
  CB 248/248 + 8 SLL rejected; DDCB/FDCB 31/31 documented + register forms
  and SLL rejected;
- representative pins for every instruction class (LD forms incl. (nn)
  forms, ALU + immediates, rotates, EX/EXX, DJNZ/JR/JR-cond with wrapped
  targets, JP/CALL/RET conds incl. po/pe/p/m, PUSH/POP, IN/OUT, IM, NEG,
  block ops, CB groups, DD/FD index forms incl. displacement placement
  (LD (IX+5),n = DD 36 05 7F, d=+5, imm8=0x7F; LD H,(IY-8) = FD 66 F8,
  d=-8), double-prefix rules (DD DD 21 = LD IX,nn len 5; DD ED B0 = LDIR),
  prefix-ignore (DD 04 = INC B len 2, no displacement));
- fail-closed: 191 undocumented ED + 8 SLL + 225 DDCB register forms +
  5 IXH/IXL split pins + 10 truncated/out-of-range cases;
- control-flow classification (jp/jr/call/ret/retn/reti/rst/djnz/jp_ind)
  and static direct targets only (indirect jp/ret have none);
- decoder determinism (identical dicts across repeats).

## Semantic assumptions and boundaries

- "Documented" means the Zilog manual primary encodings plus the public
  DD/FD decoding rules. Hardware-valid but manual-absent encodings (ED
  RETN/RETI/IM aliases, IN F,(C), OUT (C),0, SLL, IXH/IXL splits, DDCB
  register forms) fail closed — consistent with the SM83 adapter's
  undocumented-opcode policy and with AGENTS.md.
- X/Y flag bits (F bits 3/5) are undocumented and pinned to 0; no semantics
  guessed. Semantics arrive in P1-21.
- No cycle/timing modelling anywhere (consistent with the SM83 path).

## Remaining limitations

- Instruction semantics, the reference interpreter, control-flow lowering
  and the differential proof are P1-21 work (this stage deliberately stops
  at decode, mirroring the P1-10/P1-11 split).
- Z80 flag semantics for BIT (H set, N cleared, P/V = inverted tested bit)
  etc. are documented in P1-21 with the reference.

## Verdict

`PASS` — the documented Z80 architectural state and the complete documented
opcode map (base + ED + CB + DD/FD + DDCB/FDCB) are pinned by deterministic
coverage gates with fail-closed handling of every undocumented encoding.
