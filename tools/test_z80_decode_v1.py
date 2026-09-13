#!/usr/bin/env python3
"""P1-20 gate: Z80 documented instruction decoder.

Pins the complete documented Zilog Z80 opcode map from the public references
(Zilog Z80 CPU User Manual primary encodings; z80-heaven opcode reference
chart; z80.info index-prefix decoding rules):

- all 256 base opcodes decode;
- the 65 documented ED encodings decode; the remaining 191 fail closed
  (IN F,(C), OUT (C),0, RETN/RETI/IM aliases, ED 76, ...);
- all 248 documented CB encodings decode (SLL CB 30-37 fails closed: Z180
  only, not in the Z80 manual);
- DD/FD index forms: documented IX/IY pair + (IX+d)/(IY+d) forms with the
  displacement after the opcode byte; prefix ignored for instructions that
  do not involve H/L/(HL); IXH/IXL register-split forms fail closed;
- DDCB/FDCB: only the documented (IX+d)/(IY+d) operand forms decode;
  register-operand forms fail closed;
- operand resolution: imm8/imm16 little-endian, signed rel with wrapped
  target, a16 with target, DD/FD signed displacement, IN/OUT port byte;
- truncated streams and out-of-range addresses fail closed;
- decode is deterministic and control-flow classification/targets are
  pinned.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from adapters.z80 import Z80Error, branch_targets, decode, decode_full, is_control_flow  # noqa: E402

# Documented ED encodings (primary encodings from the Zilog manual).
ED_DOCUMENTED = frozenset(
    {0x40, 0x48, 0x50, 0x58, 0x60, 0x68, 0x78}  # IN r,(C)
    | {0x41, 0x49, 0x51, 0x59, 0x61, 0x69, 0x79}  # OUT (C),r
    | {0x42, 0x52, 0x62, 0x72}  # SBC HL,rp
    | {0x4A, 0x5A, 0x6A, 0x7A}  # ADC HL,rp
    | {0x43, 0x53, 0x63, 0x73}  # LD (nn),rp
    | {0x4B, 0x5B, 0x6B, 0x7B}  # LD rp,(nn)
    | {0x44, 0x4C, 0x54, 0x5C, 0x64, 0x6C, 0x74, 0x7C}  # NEG
    | {0x45, 0x4D}  # RETN / RETI
    | {0x46, 0x56, 0x5E}  # IM 0/1/2
    | {0x47, 0x4F, 0x57, 0x5F}  # LD I,A / LD R,A / LD A,I / LD A,R
    | {0x67, 0x6F}  # RRD / RLD
    | {0xA0, 0xA1, 0xA2, 0xA3, 0xA8, 0xA9, 0xAA, 0xAB,
       0xB0, 0xB1, 0xB2, 0xB3, 0xB8, 0xB9, 0xBA, 0xBB}  # block groups
)


def stream(address: int, *bytes_: int) -> bytes:
    image = bytearray(address + len(bytes_))
    image[address:address + len(bytes_)] = bytes(bytes_)
    return bytes(image)


def expect_fail(label: str, action) -> None:
    try:
        action()
    except Z80Error:
        print(f"PASS reject: {label}")
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"{label}: raised {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"{label}: accepted")


def main() -> int:
    tests = 0

    # 1. Base map: all 256 documented ----------------------------------------
    for opcode in range(256):
        insn = decode(0, opcode)
        assert insn["word"] == opcode and insn["op"]
    print("PASS base-opcode decode coverage 256/256")
    tests += 1

    # 2. Representative base pins ----------------------------------------------
    pins = {
        "nop": (0x00, {"op": "nop", "length": 1}),
        "ex-af": (0x08, {"op": "ex_af"}),
        "exx": (0xD9, {"op": "exx"}),
        "ex-sp-hl": (0xE3, {"op": "ex", "dst": "(sp)", "src": "hl"}),
        "ex-de-hl": (0xEB, {"op": "ex", "dst": "de", "src": "hl"}),
        "halt": (0x76, {"op": "halt"}),
        "di": (0xF3, {"op": "di"}),
        "ei": (0xFB, {"op": "ei"}),
        "daa": (0x27, {"op": "daa"}),
        "cpl": (0x2F, {"op": "cpl"}),
        "scf": (0x37, {"op": "scf"}),
        "ccf": (0x3F, {"op": "ccf"}),
        "rlca": (0x07, {"op": "rlca"}),
        "rla": (0x17, {"op": "rla"}),
        "jp-hl": (0xE9, {"op": "jp_ind", "reg": "hl"}),
        "ld-sp-hl": (0xF9, {"op": "ld_sp_r16", "reg": "hl"}),
    }
    for label, (opcode, expected) in pins.items():
        insn = decode(0, opcode)
        for key, value in expected.items():
            if insn.get(key) != value:
                raise AssertionError(f"{label}: {key} = {insn.get(key)!r} != {value!r}")
    print(f"PASS representative base pins {len(pins)}")
    tests += 1

    # 3. Operand resolution ---------------------------------------------------
    insn = decode_full(stream(0, 0x3E, 0x2A), 0)
    assert insn == {"address": 0, "word": 0x3E, "op": "ld", "dst": "a", "length": 2, "imm8": 0x2A}
    insn = decode_full(stream(0, 0x01, 0x34, 0x12), 0)
    assert insn["op"] == "ld" and insn["dst"] == "bc" and insn["imm16"] == 0x1234 and insn["length"] == 3
    insn = decode_full(stream(0, 0x18, 0xFE), 0)  # jr -2 -> wraps to 0
    assert insn["op"] == "jr" and insn["rel"] == -2 and insn["target"] == 0x0000
    insn = decode_full(stream(0, 0x30, 0x05), 0)  # jr nc,+5
    assert insn["cond"] == "nc" and insn["target"] == 0x0007
    insn = decode_full(stream(0, 0x10, 0xFC), 0)  # djnz -4
    assert insn["op"] == "djnz" and insn["target"] == 0xFFFE
    insn = decode_full(stream(0, 0xC3, 0x00, 0xC0), 0)
    assert insn["op"] == "jp" and insn["target"] == 0xC000 and "cond" not in insn
    insn = decode_full(stream(0, 0xFA, 0x00, 0x80), 0)  # jp m,
    assert insn["cond"] == "m" and insn["target"] == 0x8000
    insn = decode_full(stream(0, 0xE4, 0x00, 0x40), 0)  # call po,
    assert insn["op"] == "call" and insn["cond"] == "po"
    insn = decode_full(stream(0, 0xE8, 0x00, 0x00), 0)  # ret pe (no operand bytes)
    assert insn["op"] == "ret" and insn["cond"] == "pe" and insn["length"] == 1
    insn = decode_full(stream(0, 0xF0, 0x00, 0x00), 0)
    assert insn["op"] == "ret" and insn["cond"] == "p" and insn["length"] == 1
    insn = decode_full(stream(0, 0xFF), 0)
    assert insn["op"] == "rst" and insn["vector"] == 0x38 and insn["target"] == 0x38
    insn = decode_full(stream(0, 0xD3, 0x7F), 0)  # out (n),a
    assert insn["op"] == "out" and insn["port_n"] == 0x7F
    insn = decode_full(stream(0, 0xDB, 0xDC), 0)  # in a,(n)
    assert insn["op"] == "in" and insn["port_n"] == 0xDC
    insn = decode_full(stream(0, 0x22, 0x34, 0x12), 0)  # ld (nn),hl
    assert insn["dst"] == "(a16)" and insn["a16"] == 0x1234
    insn = decode_full(stream(0, 0x2A, 0x34, 0x12), 0)  # ld hl,(nn)
    assert insn["dst"] == "hl" and insn["src"] == "(a16)" and insn["a16"] == 0x1234
    insn = decode_full(stream(0, 0x06, 0x55), 0)
    assert insn["dst"] == "b" and insn["imm8"] == 0x55
    insn = decode_full(stream(0, 0x80), 0)  # add a,b
    assert insn["op"] == "add" and insn["r"] == "b"
    insn = decode_full(stream(0, 0x86), 0)  # add a,(hl)
    assert insn["op"] == "add" and insn["r"] == "(hl)"
    insn = decode_full(stream(0, 0xCE, 0x7F), 0)  # adc a,n
    assert insn["op"] == "adc" and insn["imm8"] == 0x7F
    insn = decode_full(stream(0, 0x39), 0)  # add hl,sp
    assert insn["op"] == "add_hl" and insn["pair"] == "sp"
    insn = decode_full(stream(0, 0x23), 0)  # inc hl
    assert insn["op"] == "inc" and insn["r"] == "hl"
    insn = decode_full(stream(0, 0x34), 0)  # inc (hl)
    assert insn["op"] == "inc" and insn["r"] == "(hl)"
    insn = decode_full(stream(0, 0xC5), 0)  # push bc
    assert insn["op"] == "push" and insn["pair"] == "bc"
    insn = decode_full(stream(0, 0xF1), 0)  # pop af
    assert insn["op"] == "pop" and insn["pair"] == "af"
    print("PASS operand resolution (imm8/imm16/rel/target/a16/port_n/cond)")
    tests += 1

    # 4. ED coverage: 65 documented, 191 fail closed ---------------------------
    documented = 0
    for sub in range(256):
        code = stream(0, 0xED, sub, 0x00, 0x00)  # a16 forms need up to 4 bytes
        if sub in ED_DOCUMENTED:
            insn = decode_full(code, 0)
            assert insn["word"] == 0xED and insn["sub"] == sub
            documented += 1
        else:
            expect_fail(f"ed-0x{sub:02x}-undocumented", lambda code=code: decode_full(code, 0))
    assert documented == 65, documented
    print(f"PASS ed-page coverage {documented}/65 documented, {256 - documented} rejected")
    tests += 1

    # 5. ED representative pins -------------------------------------------------
    insn = decode_full(stream(0, 0xED, 0x68), 0)  # in l,(c)
    assert insn["op"] == "in" and insn["dst"] == "l" and insn["src"] == "(c)"
    insn = decode_full(stream(0, 0xED, 0x79), 0)  # out (c),a
    assert insn["op"] == "out" and insn["dst"] == "(c)" and insn["src"] == "a"
    insn = decode_full(stream(0, 0xED, 0x42), 0)  # sbc hl,bc
    assert insn["op"] == "sbc_hl" and insn["pair"] == "bc"
    insn = decode_full(stream(0, 0xED, 0x7A), 0)  # adc hl,sp
    assert insn["op"] == "adc_hl" and insn["pair"] == "sp"
    insn = decode_full(stream(0, 0xED, 0x43, 0x00, 0xC0), 0)  # ld (nn),bc
    assert insn["dst"] == "(a16)" and insn["src"] == "bc" and insn["a16"] == 0xC000 and insn["length"] == 4
    insn = decode_full(stream(0, 0xED, 0x7B, 0x00, 0xC0), 0)  # ld sp,(nn)
    assert insn["dst"] == "sp" and insn["a16"] == 0xC000 and insn["length"] == 4
    insn = decode_full(stream(0, 0xED, 0x44), 0)  # neg
    assert insn["op"] == "neg"
    insn = decode_full(stream(0, 0xED, 0x45), 0)
    assert insn["op"] == "retn"
    insn = decode_full(stream(0, 0xED, 0x4D), 0)
    assert insn["op"] == "reti"
    insn = decode_full(stream(0, 0xED, 0x5E), 0)
    assert insn["op"] == "im" and insn["mode"] == 2
    insn = decode_full(stream(0, 0xED, 0x47), 0)
    assert insn["op"] == "ld" and insn["dst"] == "i" and insn["src"] == "a"
    insn = decode_full(stream(0, 0xED, 0x5F), 0)
    assert insn["op"] == "ld" and insn["dst"] == "a" and insn["src"] == "r"
    insn = decode_full(stream(0, 0xED, 0x67), 0)
    assert insn["op"] == "rrd"
    insn = decode_full(stream(0, 0xED, 0x6F), 0)
    assert insn["op"] == "rld"
    block_ops = {
        0xA0: "ldi", 0xB0: "ldir", 0xA8: "ldd", 0xB8: "lddr",
        0xA1: "cpi", 0xB1: "cpir", 0xA9: "cpd", 0xB9: "cpdr",
        0xA2: "ini", 0xB2: "inir", 0xAA: "ind", 0xBA: "indr",
        0xA3: "outi", 0xB3: "otir", 0xAB: "outd", 0xBB: "otdr",
    }
    for sub, op in block_ops.items():
        insn = decode_full(stream(0, 0xED, sub), 0)
        assert insn["op"] == op and insn["length"] == 2, (sub, insn)
    print(f"PASS ed representative pins incl. {len(block_ops)} block-transfer ops")
    tests += 1

    # 6. CB coverage: 248 documented, SLL rejected -------------------------------
    documented = 0
    for sub in range(256):
        code = stream(0, 0xCB, sub)
        if 0x30 <= sub < 0x38:
            expect_fail(f"cb-0x{sub:02x}-sll-undocumented", lambda code=code: decode_full(code, 0))
        else:
            insn = decode_full(code, 0)
            assert insn["sub"] == sub and insn["r"] in (
                "b", "c", "d", "e", "h", "l", "(hl)", "a"
            )
            documented += 1
    assert documented == 248, documented
    print(f"PASS cb-page coverage {documented}/248 documented, 8 SLL rejected")
    tests += 1

    insn = decode_full(stream(0, 0xCB, 0x19), 0)  # rr c
    assert insn["op"] == "rr" and insn["r"] == "c"
    insn = decode_full(stream(0, 0xCB, 0x26), 0)  # sla (hl)
    assert insn["op"] == "sla" and insn["r"] == "(hl)"
    insn = decode_full(stream(0, 0xCB, 0x38), 0)  # srl b
    assert insn["op"] == "srl" and insn["r"] == "b"
    insn = decode_full(stream(0, 0xCB, 0x7F), 0)  # bit 7,a
    assert insn["op"] == "bit" and insn["n"] == 7 and insn["r"] == "a"
    insn = decode_full(stream(0, 0xCB, 0x9E), 0)  # res 3,(hl)
    assert insn["op"] == "res" and insn["n"] == 3 and insn["r"] == "(hl)"
    insn = decode_full(stream(0, 0xCB, 0xC0), 0)  # set 0,b
    assert insn["op"] == "set" and insn["n"] == 0 and insn["r"] == "b"
    print("PASS cb representative pins")
    tests += 1

    # 7. DD/FD documented index forms --------------------------------------------
    insn = decode_full(stream(0, 0xDD, 0x21, 0x34, 0x12), 0)  # ld ix,nn
    assert insn["op"] == "ld" and insn["dst"] == "ix" and insn["imm16"] == 0x1234 and insn["length"] == 4
    insn = decode_full(stream(0, 0xFD, 0x21, 0x78, 0x56), 0)  # ld iy,nn
    assert insn["dst"] == "iy" and insn["imm16"] == 0x5678
    insn = decode_full(stream(0, 0xDD, 0x36, 0x05, 0x7F), 0)  # ld (ix+5),n
    assert insn["op"] == "ld" and insn["dst"] == "(ix+d)" and insn["base"] == "ix"
    assert insn["d"] == 5 and insn["imm8"] == 0x7F and insn["length"] == 4
    insn = decode_full(stream(0, 0xDD, 0x36, 0xFC, 0x11), 0)  # ld (ix-4),n
    assert insn["d"] == -4 and insn["imm8"] == 0x11
    insn = decode_full(stream(0, 0xFD, 0x66, 0xF8), 0)  # ld h,(iy-8)
    assert insn["op"] == "ld" and insn["dst"] == "h" and insn["src"] == "(iy+d)" and insn["d"] == -8
    insn = decode_full(stream(0, 0xDD, 0x74, 0x02), 0)  # ld (ix+2),h
    assert insn["dst"] == "(ix+d)" and insn["src"] == "h" and insn["d"] == 2
    insn = decode_full(stream(0, 0xDD, 0x86, 0x03), 0)  # add a,(ix+3)
    assert insn["op"] == "add" and insn["r"] == "(ix+d)" and insn["d"] == 3
    insn = decode_full(stream(0, 0xDD, 0x34, 0x7F), 0)  # inc (ix+127)
    assert insn["op"] == "inc" and insn["r"] == "(ix+d)" and insn["d"] == 0x7F
    insn = decode_full(stream(0, 0xDD, 0x23), 0)  # inc ix
    assert insn["op"] == "inc" and insn["r"] == "ix" and insn["length"] == 2
    insn = decode_full(stream(0, 0xDD, 0x2B), 0)  # dec ix
    assert insn["op"] == "dec" and insn["r"] == "ix"
    insn = decode_full(stream(0, 0xDD, 0x29), 0)  # add ix,ix
    assert insn["op"] == "add_r16" and insn["dst"] == "ix" and insn["pair"] == "ix"
    insn = decode_full(stream(0, 0xFD, 0x19), 0)  # add iy,de
    assert insn["dst"] == "iy" and insn["pair"] == "de"
    insn = decode_full(stream(0, 0xDD, 0x22, 0x00, 0xC0), 0)  # ld (nn),ix
    assert insn["dst"] == "(a16)" and insn["src"] == "ix" and insn["a16"] == 0xC000
    insn = decode_full(stream(0, 0xDD, 0x2A, 0x00, 0xC0), 0)  # ld ix,(nn)
    assert insn["dst"] == "ix" and insn["a16"] == 0xC000
    insn = decode_full(stream(0, 0xDD, 0xE1), 0)  # pop ix
    assert insn["op"] == "pop" and insn["pair"] == "ix"
    insn = decode_full(stream(0, 0xDD, 0xE5), 0)  # push ix
    assert insn["op"] == "push" and insn["pair"] == "ix"
    insn = decode_full(stream(0, 0xDD, 0xE3), 0)  # ex (sp),ix
    assert insn["op"] == "ex" and insn["src"] == "ix"
    insn = decode_full(stream(0, 0xDD, 0xE9), 0)  # jp (ix)
    assert insn["op"] == "jp_ind" and insn["reg"] == "ix"
    insn = decode_full(stream(0, 0xDD, 0xF9), 0)  # ld sp,ix
    assert insn["op"] == "ld_sp_r16" and insn["reg"] == "ix"
    print("PASS dd/fd documented index forms (displacement placement included)")
    tests += 1

    # 8. DD/FD prefix-ignore and double-prefix rules ------------------------------
    insn = decode_full(stream(0, 0xDD, 0x04), 0)  # inc b (no HL involvement)
    assert insn["op"] == "inc" and insn["r"] == "b" and insn["prefix_ignored"] and insn["length"] == 2
    insn = decode_full(stream(0, 0xDD, 0x76), 0)  # halt
    assert insn["op"] == "halt" and insn["prefix_ignored"] and insn["length"] == 2
    insn = decode_full(stream(0, 0xDD, 0x00), 0)  # nop
    assert insn["op"] == "nop" and insn["prefix_ignored"]
    insn = decode_full(stream(0, 0xDD, 0xC9), 0)  # ret
    assert insn["op"] == "ret" and insn["prefix_ignored"]
    insn = decode_full(stream(0, 0xDD, 0xDD, 0x21, 0x34, 0x12), 0)  # first DD ignored
    assert insn["op"] == "ld" and insn["dst"] == "ix" and insn["imm16"] == 0x1234 and insn["length"] == 5
    insn = decode_full(stream(0, 0xDD, 0xFD, 0x21, 0x34, 0x12), 0)  # DD ignored, FD wins
    assert insn["dst"] == "iy" and insn["length"] == 5
    insn = decode_full(stream(0, 0xDD, 0xED, 0xB0), 0)  # DD ignored, ED processed
    assert insn["op"] == "ldir" and insn["length"] == 3
    print("PASS dd/fd prefix-ignore + double-prefix rules")
    tests += 1

    # 9. DDCB/FDCB: only (ix+d)/(iy+d) operand forms --------------------------------
    documented = 0
    for sub in range(256):
        code = stream(0, 0xDD, 0xCB, 0x05, sub)
        if sub & 7 == 6 and not (0x30 <= sub < 0x38):
            insn = decode_full(code, 0)
            assert insn["base"] == "ix" and insn["d"] == 5 and insn["r"] == "(ix+d)"
            assert insn["length"] == 4
            documented += 1
        else:
            expect_fail(f"ddcb-0x{sub:02x}-undocumented", lambda code=code: decode_full(code, 0))
    assert documented == 31, documented
    insn = decode_full(stream(0, 0xFD, 0xCB, 0xFE, 0x9E), 0)  # res 3,(iy-2)
    assert insn["op"] == "res" and insn["n"] == 3 and insn["base"] == "iy" and insn["d"] == -2
    insn = decode_full(stream(0, 0xDD, 0xCB, 0x05, 0x7E), 0)  # bit 7,(ix+5)
    assert insn["op"] == "bit" and insn["n"] == 7
    insn = decode_full(stream(0, 0xDD, 0xCB, 0x05, 0x06), 0)  # rlc (ix+5)
    assert insn["op"] == "rlc"
    print(f"PASS ddcb/fdcb coverage {documented}/31 documented, register forms + SLL rejected")
    tests += 1

    # 10. Fail-closed: IXH/IXL register splits ---------------------------------------
    expect_fail("dd-ld-ixh-n", lambda: decode_full(stream(0, 0xDD, 0x26, 0x11), 0))
    expect_fail("dd-ld-ixl-n", lambda: decode_full(stream(0, 0xDD, 0x2E, 0x11), 0))
    expect_fail("dd-ld-h-h", lambda: decode_full(stream(0, 0xDD, 0x64), 0))
    expect_fail("dd-ld-l-h", lambda: decode_full(stream(0, 0xDD, 0x6C), 0))
    expect_fail("dd-inc-h", lambda: decode_full(stream(0, 0xDD, 0x24), 0))
    print("PASS reject: IXH/IXL register-split forms (undocumented)")
    tests += 1

    # 11. Fail-closed: truncated streams and bad addresses --------------------------
    expect_fail("truncated-imm8", lambda: decode_full(stream(0, 0x3E), 0))
    expect_fail("truncated-imm16", lambda: decode_full(stream(0, 0x01, 0x34), 0))
    expect_fail("truncated-a16", lambda: decode_full(stream(0, 0xC3, 0x00), 0))
    expect_fail("truncated-ed", lambda: decode_full(stream(0, 0xED), 0))
    expect_fail("truncated-cb", lambda: decode_full(stream(0, 0xCB), 0))
    expect_fail("truncated-dd", lambda: decode_full(stream(0, 0xDD), 0))
    expect_fail("truncated-dd-disp", lambda: decode_full(stream(0, 0xDD, 0x36, 0x05), 0))
    expect_fail("truncated-ddcb-sub", lambda: decode_full(stream(0, 0xDD, 0xCB, 0x05), 0))
    expect_fail("address-out-of-range", lambda: decode_full(stream(0, 0x00), 0x10000))
    expect_fail("address-above-stream", lambda: decode_full(stream(0, 0x00), 4))
    print("PASS reject: truncated streams + out-of-range addresses")
    tests += 1

    # 12. Control-flow classification + static targets --------------------------------
    assert is_control_flow(decode_full(stream(0, 0xC3, 0x00, 0x01), 0))
    assert is_control_flow(decode_full(stream(0, 0x18, 0x02), 0))
    assert is_control_flow(decode_full(stream(0, 0x10, 0x02), 0))
    assert is_control_flow(decode_full(stream(0, 0xCD, 0x00, 0x01), 0))
    assert is_control_flow(decode_full(stream(0, 0xC9), 0))
    assert is_control_flow(decode_full(stream(0, 0xED, 0x45), 0))
    assert is_control_flow(decode_full(stream(0, 0xED, 0x4D), 0))
    assert is_control_flow(decode_full(stream(0, 0xE9), 0))
    assert is_control_flow(decode_full(stream(0, 0xFF), 0))
    assert not is_control_flow(decode_full(stream(0, 0x3E, 0x01), 0))
    assert branch_targets(decode_full(stream(0, 0xC3, 0x34, 0x12), 0)) == [0x1234]
    assert branch_targets(decode_full(stream(0, 0x18, 0x05), 0)) == [0x0007]
    assert branch_targets(decode_full(stream(0, 0xFF), 0)) == [0x38]
    assert branch_targets(decode_full(stream(0, 0xC9), 0)) == []
    assert branch_targets(decode_full(stream(0, 0xE9), 0)) == []
    print("PASS control-flow classification + static direct targets only")
    tests += 1

    # 13. Determinism ---------------------------------------------------------------
    code = stream(0x100, 0xDD, 0x36, 0x05, 0x7F, 0xED, 0xB0, 0xCB, 0x9E, 0xC3, 0x00, 0x01)
    first = decode_full(code, 0x100)
    second = decode_full(code, 0x100)
    assert first == second
    print("PASS decoder determinism")
    tests += 1

    print(f"OPENRECOMP_Z80_DECODE_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
