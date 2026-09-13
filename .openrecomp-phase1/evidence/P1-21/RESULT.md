# P1-21 — Z80 semantics + control flow + IR/lowering

VERDICT: `PASS`

## Source revision and working-tree state

- `HEAD = bd5f02fcd21cf42a3d1e24a67c9a285825462b76`, branch `main` (unchanged).
- No commit created.
- Completed and repaired the WIP P1-21 files already in the working tree
  (`tools/z80_reference_v1.py`, `tools/z80_frontend_v1.py`,
  `tools/test_z80_semantics_v1.py`, `tools/test_z80_lowering_v1.py`).

## Files changed

| File | Change |
| --- | --- |
| `tools/test_z80_lowering_v1.py` | Fixed the "call" terminator fixture (its target byte was one past the declared region) and mirrored the proven SM83 terminator pattern (`region_start = 0x0000` + HALT at the RST vector so RST/popped-return targets are decodable leaders); added differential proof #3 (block-I/O). |
| `tools/z80_reference_v1.py` | Corrected the block-I/O family (INI/IND/INIR/INDR, OUTI/OUTD/OTIR/OTDR) to the documented flag model; fixed the OUTD/OTDR direction bug (`op[2] == "d"` is false for "outd"). |
| `tools/z80_frontend_v1.py` | Same block-I/O corrections in the lowering; port addresses now mask to 8 bits (matching the reference's 256-byte deterministic port model). |
| `tools/test_z80_semantics_v1.py` | Added 7 pinned block-I/O + port-mask pins (79 -> 86 tests). |
| `tools/phase1_host_gates_v1.py` | Registered gates `z80-semantics-v1` and `z80-lowering-v1` (area "z80"). |
| `SOURCE_SHA256SUMS.txt` | Regenerated via `python update_sums.py`. |

## Deliverables

| File | Role |
| --- | --- |
| `tools/z80_reference_v1.py` | Independent machine-code reference for every documented encoding (base/ED/CB/DD-FD/DDCB-FDCB) with documented flag rules; deterministic 256-byte port model; fail-closed on undocumented opcodes and step-limit runaway. |
| `tools/z80_frontend_v1.py` | Control-flow classification + normalized IR V1 lowering on the shared scaffold: static targets become jump/branch, `ret/retn/reti/jp (hl)/(ix)/(iy)` become `indirect_jump` with the block-leader candidate set, repeating block ops become self-looping helper blocks with the documented repeat conditions, HALT terminates, fail-closed region rules. |
| `tools/test_z80_semantics_v1.py` | `OPENRECOMP_Z80_SEMANTICS_V1=PASS tests=86` |
| `tools/test_z80_lowering_v1.py` | `OPENRECOMP_Z80_LOWERING_V1=PASS tests=14` |

## Documented facts implemented (public references)

- Zilog Z80 CPU User Manual primary flag rules; z80-heaven secondary
  documentation for block-transfer details (fetched this session:
  `z80-heaven.wikidot.com/instructions-set:{ini,ind,outi,outd}`).
- 8-bit ALU: H between bits 3/4, C out of bit 7, P/V = overflow for the
  add/sub family and INC/DEC, even parity for logicals/rotates/IN/RLD/RRD.
- 16-bit ADD HL,rp: H from bit 11, C from bit 15, S/Z/P/V preserved, N
  cleared; ADC/SBC HL set the full flag set.
- DAA post-add/post-subtract; NEG; BIT (H=1, N=0, P/V=Z, S/C unchanged);
  CB rotates/shifts; RLCA/RRCA/RLA/RRA touch only H/N/C.
- Block ops: LDI/LDD/LDIR/LDDR (H=0, N=0, P/V=BC!=0); CPI/CPD/CPIR/CPDR
  (S/Z/H/N from CP, P/V=BC!=0, C preserved); repeating forms iterate
  internally without advancing PC.
- Block-I/O family (documented): only B decrements (C register preserved),
  Z = (B==0 after decrement), P/V = (B!=0), N set by the -d variants and
  reset by the -i variants, C flag and S/H preserved (Zilog marks S/H/N/C
  unknown; z80-heaven documents the deterministic bits adopted here).
- IN/OUT port model: deterministic 256-byte port space, addresses mask to
  8 bits; IN r,(C) sets S/Z/P/V (parity), H=0, N=0, C preserved; LD A,I/R
  set P/V = IFF2; EI one-instruction delay; RETN copies IFF2 into IFF1.
- Control flow: 8 documented conditions on the documented F bits; RST
  pushes the return address and jumps to the vector; JP (HL)/(IX)/(IY) are
  indirect jumps; HALT stops execution.

## Repair notes (semantic corrections, all source-backed)

1. The block-I/O flags were computed from undocumented sums (B+C / L+B)
   and Z was taken from the data byte for the IN family. Both reference and
   frontend now implement the documented model above.
2. OUTD/OTDR incremented HL (`op[2] == "d"` is false for "outd"); both
   implementations now use the family-correct direction. New pins
   (`outd-n-set`, `otir-internal-repeat`) lock this in.
3. The frontend port model did not mask port addresses to 8 bits while the
   reference does; now identical (differential #3 exercises BC > 0xFF).
4. The "call" terminator fixture in `test_z80_lowering_v1.py` targeted a
   byte outside its declared region (a WIP bug, never a passing test);
   the fixture now includes the target HALT byte, and the SM83-proven
   region-extension pattern covers RST/ret targets.

## Verification (all deterministic, run twice where noted)

```text
python tools/test_z80_semantics_v1.py
OPENRECOMP_Z80_SEMANTICS_V1=PASS tests=86
(run twice: output sha256 D5211D00C447987D3BEA5027791ADEB141EDBFBAFD848BC5780FCBD1603D002D)

python tools/test_z80_lowering_v1.py
OPENRECOMP_Z80_LOWERING_V1=PASS tests=14
(differential proofs: reference == Core API on identical final CPU state,
 full 64 KiB guest memory and the 256-byte port model; run twice: output
 sha256 DB1C6B5958DEBF577738069247E8B26898A6BBC1B165D290F1EAD43DE611C0C5)

python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=33 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

Differential pins (frozen regression targets):

- fixture 1: a=0x07 f=0x42 hl=0xd233 sp=0xff00 ix=0xc800 halted=1 blocks=8
- fixture 2: LDIR + OUT/IN (C): port 0x40 = 0x5A, D000-D003 = 11 22 33 44
- fixture 3: OUT (C),A with BC=0x0140 (8-bit mask) + INIR x3 + OTIR x2:
  f=0x40, b=0x00, c=0x37 (preserved), hl=0xd002, C000-C002 = 5A 5A 5A,
  port 0x37 = 0x22

## Semantic assumptions / limitations

- Interrupt *dispatch* is platform work (P1-22); the reference models
  DI/EI/IM/RETN and IFF1/IFF2 only.
- R is only changed by LD R,A (no M1-fetch refresh increments); cycle
  counts are intentionally not modelled.
- S/H/C-flag and other Zilog-"unknown" bits follow the deterministic
  z80-heaven secondary documentation where it exists and are preserved
  where both sources leave them undefined.
- The port model is a deterministic 256-byte space (SMS port decode in
  P1-22); port addresses mask to 8 bits.

## Next

P1-22 (Master System ROM/banking/I-O platform contract), then P1-23
(SMS deterministic headless proof), P1-24 (Z80/SMS regression + audit).
