#!/usr/bin/env python3
"""P1-11 gate: documented SM83 base + CB-prefixed decoder.

Verifies `adapters/sm83.py`:

- full coverage: every one of the 256 base opcodes decodes, except exactly the
  11 undocumented opcodes, which fail closed with `SM83Error`;
- full CB coverage: all 256 CB-page encodings decode to the documented
  operation class (RLC/RRC/RL/RR/SLA/SRA/SWAP/SRL, BIT/RES/SET with the
  documented operand order B,C,D,E,H,L,(HL),A);
- representative pins for every documented operand mode;
- stream-resident operand resolution (`imm8`, little-endian `imm16`, signed
  `rel` with wrapped 16-bit targets, `a8`, `a16`, STOP padding) with
  bounds-checked fail-closed behaviour on truncated streams;
- control-flow classification and static branch targets.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters import sm83  # noqa: E402
from adapters.sm83 import SM83Error  # noqa: E402

R8 = ("b", "c", "d", "e", "h", "l", "(hl)", "a")
CC = ("nz", "z", "nc", "c")
ALU = ("add", "adc", "sub", "sbc", "and", "xor", "or", "cp")
CB_KINDS = ("rlc", "rrc", "rl", "rr", "sla", "sra", "swap", "srl")
UNDOCUMENTED = frozenset(
    {0xD3, 0xDB, 0xDD, 0xE3, 0xE4, 0xEB, 0xEC, 0xED, 0xF4, 0xFC, 0xFD}
)


def expect_fail(label: str, action, error_type=SM83Error) -> None:
    try:
        action()
    except error_type:
        print(f"PASS reject: {label}")
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"{label}: raised {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"{label}: accepted")


def main() -> int:
    tests = 0

    # 1. full base-opcode coverage --------------------------------------
    undocumented_hit = []
    for opcode in range(256):
        try:
            decoded = sm83.decode(0x0100, opcode)
            assert decoded["address"] == 0x0100
            assert decoded["word"] == opcode
            assert isinstance(decoded["op"], str) and decoded["op"]
            assert decoded["length"] in (1, 2, 3)
            if opcode in UNDOCUMENTED:
                raise AssertionError(f"undocumented opcode 0x{opcode:02X} was accepted")
        except SM83Error:
            if opcode not in UNDOCUMENTED:
                raise AssertionError(f"documented opcode 0x{opcode:02X} was rejected")
            undocumented_hit.append(opcode)
        else:
            if opcode == 0xCB:
                assert decoded["op"] == "cb-prefix", decoded
    if set(undocumented_hit) != UNDOCUMENTED:
        raise AssertionError(f"rejected set {sorted(undocumented_hit)} != undocumented set")
    print("PASS base-opcode coverage 256/256 documented decoded, 11 undocumented rejected")
    tests += 1

    # 2. full CB coverage ------------------------------------------------
    for sub in range(256):
        decoded = sm83.decode_full(bytes([0xCB, sub]), 0x0000)
        r = R8[sub & 7]
        if sub < 0x40:
            assert decoded["op"] == CB_KINDS[(sub >> 3) & 7] and decoded["r"] == r, (sub, decoded)
        elif sub < 0x80:
            assert decoded["op"] == "bit" and decoded["n"] == (sub >> 3) & 7 and decoded["r"] == r
        elif sub < 0xC0:
            assert decoded["op"] == "res" and decoded["n"] == (sub >> 3) & 7 and decoded["r"] == r
        else:
            assert decoded["op"] == "set" and decoded["n"] == (sub >> 3) & 7 and decoded["r"] == r
        assert decoded["length"] == 2
    print("PASS cb-page coverage 256/256 documented encodings")
    tests += 1

    # 3. representative base pins ---------------------------------------
    pins = [
        (0x00, {"op": "nop", "length": 1}),
        (0x07, {"op": "rlca", "length": 1}),
        (0x0F, {"op": "rrca", "length": 1}),
        (0x17, {"op": "rla", "length": 1}),
        (0x1F, {"op": "rra", "length": 1}),
        (0x27, {"op": "daa", "length": 1}),
        (0x2F, {"op": "cpl", "length": 1}),
        (0x37, {"op": "scf", "length": 1}),
        (0x3F, {"op": "ccf", "length": 1}),
        (0x76, {"op": "halt", "length": 1}),
        (0x10, {"op": "stop", "length": 2, "operands": ["padding"]}),
        (0xF3, {"op": "di", "length": 1}),
        (0xFB, {"op": "ei", "length": 1}),
        (0xE9, {"op": "jp_hl", "length": 1}),
        (0xF9, {"op": "ld_sp_hl", "length": 1}),
        (0xCB, {"op": "cb-prefix", "length": 1}),
        (0x01, {"op": "ld", "dst": "bc", "length": 3, "operands": ["imm16"]}),
        (0x11, {"op": "ld", "dst": "de", "length": 3, "operands": ["imm16"]}),
        (0x21, {"op": "ld", "dst": "hl", "length": 3, "operands": ["imm16"]}),
        (0x31, {"op": "ld", "dst": "sp", "length": 3, "operands": ["imm16"]}),
        (0x08, {"op": "ld", "dst": "(a16)", "src": "sp", "length": 3, "operands": ["a16"]}),
        (0xEA, {"op": "ld", "dst": "(a16)", "src": "a", "length": 3, "operands": ["a16"]}),
        (0xFA, {"op": "ld", "dst": "a", "src": "(a16)", "length": 3, "operands": ["a16"]}),
        (0x02, {"op": "ld", "dst": "(bc)", "src": "a", "length": 1}),
        (0x0A, {"op": "ld", "dst": "a", "src": "(bc)", "length": 1}),
        (0x12, {"op": "ld", "dst": "(de)", "src": "a", "length": 1}),
        (0x1A, {"op": "ld", "dst": "a", "src": "(de)", "length": 1}),
        (0x22, {"op": "ld", "dst": "(hl+)", "src": "a", "length": 1}),
        (0x2A, {"op": "ld", "dst": "a", "src": "(hl+)", "length": 1}),
        (0x32, {"op": "ld", "dst": "(hl-)", "src": "a", "length": 1}),
        (0x3A, {"op": "ld", "dst": "a", "src": "(hl-)", "length": 1}),
        (0x06, {"op": "ld", "dst": "b", "length": 2, "operands": ["imm8"]}),
        (0x3E, {"op": "ld", "dst": "a", "length": 2, "operands": ["imm8"]}),
        (0x36, {"op": "ld", "dst": "(hl)", "length": 2, "operands": ["imm8"]}),
        (0x40, {"op": "ld", "dst": "b", "src": "b", "length": 1}),
        (0x72, {"op": "ld", "dst": "(hl)", "src": "d", "length": 1}),
        (0x7F, {"op": "ld", "dst": "a", "src": "a", "length": 1}),
        (0x80, {"op": "add", "r": "b", "length": 1}),
        (0x86, {"op": "add", "r": "(hl)", "length": 1}),
        (0x8F, {"op": "adc", "r": "a", "length": 1}),
        (0xBF, {"op": "cp", "r": "a", "length": 1}),
        (0xC6, {"op": "add", "length": 2, "operands": ["imm8"]}),
        (0xFE, {"op": "cp", "length": 2, "operands": ["imm8"]}),
        (0x03, {"op": "inc", "r": "bc", "length": 1}),
        (0x0B, {"op": "dec", "r": "bc", "length": 1}),
        (0x33, {"op": "inc", "r": "sp", "length": 1}),
        (0x3B, {"op": "dec", "r": "sp", "length": 1}),
        (0x04, {"op": "inc", "r": "b", "length": 1}),
        (0x0D, {"op": "dec", "r": "c", "length": 1}),
        (0x34, {"op": "inc", "r": "(hl)", "length": 1}),
        (0x3C, {"op": "inc", "r": "a", "length": 1}),
        (0x09, {"op": "add_hl", "pair": "bc", "length": 1}),
        (0x19, {"op": "add_hl", "pair": "de", "length": 1}),
        (0x29, {"op": "add_hl", "pair": "hl", "length": 1}),
        (0x39, {"op": "add_hl", "pair": "sp", "length": 1}),
        (0x18, {"op": "jr", "length": 2, "operands": ["rel"]}),
        (0x20, {"op": "jr", "cond": "nz", "length": 2, "operands": ["rel"]}),
        (0x28, {"op": "jr", "cond": "z", "length": 2, "operands": ["rel"]}),
        (0x30, {"op": "jr", "cond": "nc", "length": 2, "operands": ["rel"]}),
        (0x38, {"op": "jr", "cond": "c", "length": 2, "operands": ["rel"]}),
        (0xC3, {"op": "jp", "length": 3, "operands": ["a16"]}),
        (0xC2, {"op": "jp", "cond": "nz", "length": 3, "operands": ["a16"]}),
        (0xDA, {"op": "jp", "cond": "c", "length": 3, "operands": ["a16"]}),
        (0xCD, {"op": "call", "length": 3, "operands": ["a16"]}),
        (0xD4, {"op": "call", "cond": "nc", "length": 3, "operands": ["a16"]}),
        (0xC9, {"op": "ret", "length": 1}),
        (0xD9, {"op": "reti", "length": 1}),
        (0xC0, {"op": "ret", "cond": "nz", "length": 1}),
        (0xD8, {"op": "ret", "cond": "c", "length": 1}),
        (0xC1, {"op": "pop", "pair": "bc", "length": 1}),
        (0xF1, {"op": "pop", "pair": "af", "length": 1}),
        (0xC5, {"op": "push", "pair": "bc", "length": 1}),
        (0xF5, {"op": "push", "pair": "af", "length": 1}),
        (0xE0, {"op": "ldh", "dir": "store", "length": 2, "operands": ["a8"]}),
        (0xF0, {"op": "ldh", "dir": "load", "length": 2, "operands": ["a8"]}),
        (0xE2, {"op": "ldh", "dir": "store", "via": "c", "length": 1}),
        (0xF2, {"op": "ldh", "dir": "load", "via": "c", "length": 1}),
        (0xE8, {"op": "add_sp", "length": 2, "operands": ["rel"]}),
        (0xF8, {"op": "ld_hl_sp", "length": 2, "operands": ["rel"]}),
        (0xC7, {"op": "rst", "vector": 0x00, "length": 1}),
        (0xCF, {"op": "rst", "vector": 0x08, "length": 1}),
        (0xD7, {"op": "rst", "vector": 0x10, "length": 1}),
        (0xDF, {"op": "rst", "vector": 0x18, "length": 1}),
        (0xE7, {"op": "rst", "vector": 0x20, "length": 1}),
        (0xEF, {"op": "rst", "vector": 0x28, "length": 1}),
        (0xF7, {"op": "rst", "vector": 0x30, "length": 1}),
        (0xFF, {"op": "rst", "vector": 0x38, "length": 1}),
    ]
    for opcode, expected in pins:
        decoded = sm83.decode(0x0100, opcode)
        for key, value in expected.items():
            if decoded.get(key) != value:
                raise AssertionError(f"0x{opcode:02X}: {key} {decoded.get(key)!r} != {value!r} ({decoded})")
    print(f"PASS representative base pins {len(pins)}")
    tests += 1

    # 4. decode_full operand resolution ---------------------------------
    stream_cases = [
        (bytes([0x3E, 0x2A]), 0x0000, {"op": "ld", "dst": "a", "imm8": 0x2A, "length": 2}),
        (bytes([0x21, 0x34, 0x12]), 0x0000, {"op": "ld", "dst": "hl", "imm16": 0x1234, "length": 3}),
        (bytes([0x18, 0xFE]), 0x0000, {"op": "jr", "rel": -2, "target": 0x0000, "length": 2}),
        (bytes([0x20, 0x05]), 0x0000, {"op": "jr", "cond": "nz", "rel": 5, "target": 0x0007, "length": 2}),
        (bytes([0xC3, 0x00, 0x80]), 0x0000, {"op": "jp", "target": 0x8000, "length": 3}),
        (bytes([0xCD, 0x50, 0x01]), 0x0000, {"op": "call", "target": 0x0150, "length": 3}),
        (bytes([0xE0, 0x80]), 0x0000, {"op": "ldh", "dir": "store", "a8": 0x80, "length": 2}),
        (bytes([0xE8, 0x02]), 0x0000, {"op": "add_sp", "rel": 2, "length": 2}),
        (bytes([0xF8, 0xFB]), 0x0000, {"op": "ld_hl_sp", "rel": -5, "length": 2}),
        (bytes([0x10, 0x00]), 0x0000, {"op": "stop", "padding": 0, "length": 2}),
        (bytes([0xCB, 0x37]), 0x0000, {"op": "swap", "r": "a", "length": 2}),
        (bytes([0xCB, 0x46]), 0x0000, {"op": "bit", "n": 0, "r": "(hl)", "length": 2}),
        (bytes([0xCB, 0xFE]), 0x0000, {"op": "set", "n": 7, "r": "(hl)", "length": 2}),
        (bytes([0xC7]), 0x0000, {"op": "rst", "vector": 0x00, "target": 0x00, "length": 1}),
        (bytes(0x0100) + bytes([0x18, 0xFE]), 0x0100, {"op": "jr", "rel": -2, "target": 0x0100, "length": 2}),
        (bytes(0x0100) + bytes([0x18, 0xFE, 0x11]), 0x0101, {"op": "cp", "imm8": 0x11, "length": 2}),
    ]
    for stream, address, expected in stream_cases:
        decoded = sm83.decode_full(stream, address)
        for key, value in expected.items():
            if decoded.get(key) != value:
                raise AssertionError(f"stream {stream.hex()}@{address:#x}: {key} {decoded.get(key)!r} != {value!r}")
    print(f"PASS decode_full operand resolution {len(stream_cases)}")
    tests += 1

    # 5. fail-closed stream/address/word handling -----------------------
    expect_fail("imm8-at-end-of-stream", lambda: sm83.decode_full(bytes([0x3E]), 0x0000))
    expect_fail("imm16-truncated", lambda: sm83.decode_full(bytes([0x21, 0x00]), 0x0000))
    expect_fail("cb-prefix-at-end", lambda: sm83.decode_full(bytes([0xCB]), 0x0000))
    expect_fail("stop-padding-at-end", lambda: sm83.decode_full(bytes([0x10]), 0x0000))
    expect_fail("byte-beyond-stream", lambda: sm83.decode_full(bytes([0x00]), 0x0001))
    expect_fail("address-above-16-bits", lambda: sm83.decode(0x10000, 0x00))
    expect_fail("word-above-8-bits", lambda: sm83.decode(0x0100, 0x100))
    tests += 1

    # 6. control-flow classification and static targets -----------------
    control = ("jp", "jr", "call", "ret", "reti", "rst", "jp_hl")
    for opcode in range(256):
        try:
            decoded = sm83.decode(0x0100, opcode)
        except SM83Error:
            continue
        assert sm83.is_control_flow(decoded) == (decoded["op"] in control), (opcode, decoded["op"])
    for sub in range(256):
        decoded = sm83.decode_full(bytes([0xCB, sub]), 0x0000)
        assert not sm83.is_control_flow(decoded), (sub, decoded["op"])

    assert sm83.branch_targets({"op": "nop"}) == []
    assert sm83.branch_targets(sm83.decode_full(bytes([0xC3, 0x00, 0x80]), 0x0000)) == [0x8000]
    assert sm83.branch_targets(sm83.decode_full(bytes([0x20, 0x05]), 0x0000)) == [0x0007]
    assert sm83.branch_targets(sm83.decode_full(bytes([0xE9]), 0x0000)) == []
    assert sm83.branch_targets(sm83.decode_full(bytes([0xC9]), 0x0000)) == []
    print("PASS control-flow classification + static branch targets")
    tests += 1

    # 7. determinism -----------------------------------------------------
    for opcode in (0x00, 0x3E, 0x76, 0xCB, 0xFF, 0xD3):
        try:
            first = sm83.decode(0x0100, opcode)
        except SM83Error:
            continue
        assert first == sm83.decode(0x0100, opcode)
    stream = bytes([0x21, 0x34, 0x12, 0xCB, 0x37])
    assert sm83.decode_full(stream, 0x0000) == sm83.decode_full(stream, 0x0000)
    print("PASS decoder determinism")
    tests += 1

    print(f"OPENRECOMP_SM83_DECODE_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
