"""Sharp SM83 (Game Boy CPU) architecture adapter — state model.

P1-10 stage deliverable: the documented architectural state of the Sharp
SM83 (a Sharp LR35902-family core used in Game Boy/Game Boy Color).

Every fact below is documented public SM83 behaviour (the widely published
Game Boy hardware documentation family, e.g. "Pan Docs" CPU register and flag
sections):

- 8-bit registers: A (accumulator), F (flags), B, C, D, E, H, L.
- Flags live in F: bit 7 Z (zero), bit 6 N (subtract), bit 5 H (half carry),
  bit 4 C (carry). The low nibble (bits 3..0) is documented as always zero
  and must be masked on writes.
- 16-bit register pairs are formed high byte first: AF, BC, DE, HL.
- SP (stack pointer) is a standalone 16-bit register.
- PC (program counter) is a 16-bit implicit control-flow register: it is not
  part of the general register file, no instruction reads it except through
  control flow, so it is modelled by structured control flow, not by a state
  slot (the same rule the MIPS32 frontend applies to its PC).
- The guest address space is 16 bits (0000..FFFF). Frozen IR V1 requires
  `source.address_bits` of 32 or 64, so per the frontend contract's
  narrow-address rule guest addresses are carried zero-extended in i32 and
  all PC/SP/pointer arithmetic wraps at 16 bits inside the frontend.

The instruction decoder (P1-11) implements the documented SM83 opcode map:
all 256 base encodings plus all 256 CB-prefixed encodings, from the public
SM83 opcode tables. Undocumented opcodes (0xD3, 0xDB, 0xDD, 0xE3, 0xE4, 0xEB,
0xEC, 0xED, 0xF4, 0xFC, 0xFD) fail closed with `SM83Error`; no encoding is
guessed. Operand values that live in the instruction stream (`imm8`, `imm16`
little-endian, signed `rel`, `a8`, `a16`) are declared by `decode` as
`operands` and resolved by `decode_full`, which also performs bounds checks
against the supplied byte stream.
"""
from __future__ import annotations

from .interface import ArchitectureInfo

info = ArchitectureInfo(
    "sm83-gb",
    8,
    "little",
    ("a", "f", "b", "c", "d", "e", "h", "l", "sp", "pc"),
    "Sharp SM83 (Game Boy): 8-bit A/F/B/C/D/E/H/L, 16-bit pairs AF/BC/DE/HL (high byte first), standalone SP; Z/N/H/C in F bits 7..4",
)

# Documented flag bit positions inside F.
FLAG_Z = 0x80
FLAG_N = 0x40
FLAG_H = 0x20
FLAG_C = 0x10
# The low nibble of F is documented as always zero; writes must mask it.
FLAG_WRITE_MASK = 0xF0

# Documented register pairs, high byte first.
REGISTER_PAIRS = ("af", "bc", "de", "hl")

# Normalized IR V1 state slots for the architectural register file.
# PC is intentionally absent (implicit control flow). SP is i16 because it is
# a real architectural register that instructions load, save and transfer.
STATE_SLOTS = {
    "cpu:a": "i8",
    "cpu:f": "i8",
    "cpu:b": "i8",
    "cpu:c": "i8",
    "cpu:d": "i8",
    "cpu:e": "i8",
    "cpu:h": "i8",
    "cpu:l": "i8",
    "cpu:sp": "i16",
}

PAIR_PARTS = {
    "af": ("a", "f"),
    "bc": ("b", "c"),
    "de": ("d", "e"),
    "hl": ("h", "l"),
}

ADDRESS_BITS = 16
ADDRESS_LIMIT = 1 << 16

# Documented 8-bit register operand order used by the ALU/LD/CB tables.
R8 = ("b", "c", "d", "e", "h", "l", "(hl)", "a")
# Documented jump/call/return condition codes (bits of the opcode nibble).
CC = ("nz", "z", "nc", "c")
# ALU operations targeting A, in the documented opcode order.
ALU = ("add", "adc", "sub", "sbc", "and", "xor", "or", "cp")
# CB-page shift/rotate groups, in the documented order.
CB_KINDS = ("rlc", "rrc", "rl", "rr", "sla", "sra", "swap", "srl")
# Documented RST vectors.
RST_VECTORS = (0x00, 0x08, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38)
# The only undocumented base opcodes (public SM83 tables).
UNDOCUMENTED = frozenset(
    {0xD3, 0xDB, 0xDD, 0xE3, 0xE4, 0xEB, 0xEC, 0xED, 0xF4, 0xFC, 0xFD}
)


class SM83Error(ValueError):
    """Fail-closed SM83 adapter error (unknown encoding, malformed input)."""


def pair_of(high: int, low: int) -> int:
    """Compose a documented 16-bit register pair (high byte first)."""
    _check_byte(high, "pair high byte")
    _check_byte(low, "pair low byte")
    return (high << 8) | low


def pair_halves(value: int) -> tuple[int, int]:
    """Split a 16-bit pair into (high, low) bytes."""
    if isinstance(value, bool) or not isinstance(value, int) or not (0 <= value <= 0xFFFF):
        raise SM83Error(f"pair value 0x{value:x} is outside the 16-bit register width")
    return (value >> 8) & 0xFF, value & 0xFF


def _check_byte(value: int, where: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not (0 <= value <= 0xFF):
        raise SM83Error(f"{where} 0x{value:x} is outside the 8-bit register width")


def _base(address: int, word: int) -> dict:
    """Decode one base opcode byte (stream operands declared, not resolved)."""
    if isinstance(address, bool) or not isinstance(address, int) or not (0 <= address < ADDRESS_LIMIT):
        raise SM83Error(f"SM83 instruction address 0x{address:x} is outside the 16-bit address space")
    if isinstance(word, bool) or not isinstance(word, int) or not (0 <= word <= 0xFF):
        raise SM83Error(f"SM83 opcode 0x{word:x} is outside the 8-bit width")

    insn: dict = {"address": address, "word": word, "op": "", "length": 1}
    if word in UNDOCUMENTED:
        raise SM83Error(f"0x{address:x}: undocumented SM83 opcode 0x{word:02x}")

    if word == 0x00:
        insn.update(op="nop")
    elif word == 0x07:
        insn.update(op="rlca")
    elif word == 0x0F:
        insn.update(op="rrca")
    elif word == 0x17:
        insn.update(op="rla")
    elif word == 0x1F:
        insn.update(op="rra")
    elif word == 0x27:
        insn.update(op="daa")
    elif word == 0x2F:
        insn.update(op="cpl")
    elif word == 0x37:
        insn.update(op="scf")
    elif word == 0x3F:
        insn.update(op="ccf")
    elif word == 0x76:
        insn.update(op="halt")
    elif word == 0xF3:
        insn.update(op="di")
    elif word == 0xFB:
        insn.update(op="ei")
    elif word == 0xE9:
        insn.update(op="jp_hl")
    elif word == 0xF9:
        insn.update(op="ld_sp_hl")
    elif word == 0xCB:
        insn.update(op="cb-prefix")
    elif word == 0x10:
        insn.update(op="stop", length=2, operands=["padding"])
    elif word in (0x01, 0x11, 0x21, 0x31):
        pair = {0x01: "bc", 0x11: "de", 0x21: "hl", 0x31: "sp"}[word]
        insn.update(op="ld", dst=pair, length=3, operands=["imm16"])
    elif word == 0x08:
        insn.update(op="ld", dst="(a16)", src="sp", length=3, operands=["a16"])
    elif word == 0xEA:
        insn.update(op="ld", dst="(a16)", src="a", length=3, operands=["a16"])
    elif word == 0xFA:
        insn.update(op="ld", dst="a", src="(a16)", length=3, operands=["a16"])
    elif word in (0xC3, 0xC2, 0xCA, 0xD2, 0xDA):
        if word == 0xC3:
            insn.update(op="jp", length=3, operands=["a16"])
        else:
            cond = CC[{0xC2: 0, 0xCA: 1, 0xD2: 2, 0xDA: 3}[word]]
            insn.update(op="jp", cond=cond, length=3, operands=["a16"])
    elif word in (0xCD, 0xC4, 0xCC, 0xD4, 0xDC):
        if word == 0xCD:
            insn.update(op="call", length=3, operands=["a16"])
        else:
            cond = CC[{0xC4: 0, 0xCC: 1, 0xD4: 2, 0xDC: 3}[word]]
            insn.update(op="call", cond=cond, length=3, operands=["a16"])
    elif word in (0xC9, 0xD9, 0xC0, 0xC8, 0xD0, 0xD8):
        if word == 0xC9:
            insn.update(op="ret")
        elif word == 0xD9:
            insn.update(op="reti")
        else:
            cond = CC[{0xC0: 0, 0xC8: 1, 0xD0: 2, 0xD8: 3}[word]]
            insn.update(op="ret", cond=cond)
    elif word in (0xC1, 0xD1, 0xE1, 0xF1):
        pair = {0xC1: "bc", 0xD1: "de", 0xE1: "hl", 0xF1: "af"}[word]
        insn.update(op="pop", pair=pair)
    elif word in (0xC5, 0xD5, 0xE5, 0xF5):
        pair = {0xC5: "bc", 0xD5: "de", 0xE5: "hl", 0xF5: "af"}[word]
        insn.update(op="push", pair=pair)
    elif word in (0x18, 0x20, 0x28, 0x30, 0x38):
        if word == 0x18:
            insn.update(op="jr", length=2, operands=["rel"])
        else:
            cond = CC[{0x20: 0, 0x28: 1, 0x30: 2, 0x38: 3}[word]]
            insn.update(op="jr", cond=cond, length=2, operands=["rel"])
    elif word == 0xE8:
        insn.update(op="add_sp", length=2, operands=["rel"])
    elif word == 0xF8:
        insn.update(op="ld_hl_sp", length=2, operands=["rel"])
    elif word in (0xE0, 0xF0):
        insn.update(op="ldh", dir="store" if word == 0xE0 else "load", length=2, operands=["a8"])
    elif word == 0xE2:
        insn.update(op="ldh", dir="store", via="c")
    elif word == 0xF2:
        insn.update(op="ldh", dir="load", via="c")
    elif word in (0x06, 0x0E, 0x16, 0x1E, 0x26, 0x2E, 0x3E, 0x36):
        if word == 0x36:
            insn.update(op="ld", dst="(hl)", length=2, operands=["imm8"])
        else:
            dst = {0x06: "b", 0x0E: "c", 0x16: "d", 0x1E: "e", 0x26: "h", 0x2E: "l", 0x3E: "a"}[word]
            insn.update(op="ld", dst=dst, length=2, operands=["imm8"])
    elif word in (0x02, 0x12, 0x0A, 0x1A):
        if word == 0x02:
            insn.update(op="ld", dst="(bc)", src="a")
        elif word == 0x12:
            insn.update(op="ld", dst="(de)", src="a")
        elif word == 0x0A:
            insn.update(op="ld", dst="a", src="(bc)")
        else:
            insn.update(op="ld", dst="a", src="(de)")
    elif word == 0x22:
        insn.update(op="ld", dst="(hl+)", src="a")
    elif word == 0x2A:
        insn.update(op="ld", dst="a", src="(hl+)")
    elif word == 0x32:
        insn.update(op="ld", dst="(hl-)", src="a")
    elif word == 0x3A:
        insn.update(op="ld", dst="a", src="(hl-)")
    elif word in (0x09, 0x19, 0x29, 0x39):
        pair = {0x09: "bc", 0x19: "de", 0x29: "hl", 0x39: "sp"}[word]
        insn.update(op="add_hl", pair=pair)
    elif word in (0x03, 0x0B, 0x13, 0x1B, 0x23, 0x2B, 0x33, 0x3B):
        r = {0x03: "bc", 0x0B: "bc", 0x13: "de", 0x1B: "de", 0x23: "hl", 0x2B: "hl", 0x33: "sp", 0x3B: "sp"}[word]
        insn.update(op="inc" if word in (0x03, 0x13, 0x23, 0x33) else "dec", r=r)
    elif word in (0x04, 0x0C, 0x14, 0x1C, 0x24, 0x2C, 0x34, 0x3C):
        r = ("b", "c", "d", "e", "h", "l", "(hl)", "a")[(word >> 3) & 7]
        insn.update(op="inc", r=r)
    elif word in (0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D):
        r = ("b", "c", "d", "e", "h", "l", "(hl)", "a")[(word >> 3) & 7]
        insn.update(op="dec", r=r)
    elif 0x40 <= word <= 0x7F:
        insn.update(op="ld", dst=R8[(word >> 3) & 7], src=R8[word & 7])
    elif 0x80 <= word <= 0xBF:
        insn.update(op=ALU[(word >> 3) & 7], r=R8[word & 7])
    elif word in (0xC6, 0xCE, 0xD6, 0xDE, 0xE6, 0xEE, 0xF6, 0xFE):
        insn.update(op=ALU[(word >> 3) & 7], length=2, operands=["imm8"])
    elif word in (0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF):
        insn.update(op="rst", vector=RST_VECTORS[(word >> 3) & 7])
    else:
        raise SM83Error(f"0x{address:x}: undocumented SM83 opcode 0x{word:02x}")
    return insn


def _cb_sub(sub: int) -> dict:
    """Decode a CB-page second byte into op/operand fields."""
    r = R8[sub & 7]
    if sub < 0x40:
        return {"op": CB_KINDS[(sub >> 3) & 7], "r": r}
    n = (sub >> 3) & 7
    if sub < 0x80:
        return {"op": "bit", "n": n, "r": r}
    if sub < 0xC0:
        return {"op": "res", "n": n, "r": r}
    return {"op": "set", "n": n, "r": r}


def decode(address: int, word: int) -> dict:
    """Decode one instruction byte.

    For the base map this is the opcode byte itself; for 0xCB it is the
    prefix (the second byte is resolved by `decode_full`). Stream-resident
    operands are declared under `operands`, never guessed here.
    """
    return _base(address, word)


def decode_full(code, address: int) -> dict:
    """Decode a complete instruction from a byte stream.

    `code` is a bytes-like object of guest memory. Reads are bounds-checked;
    an instruction whose operands run past the end of the stream raises
    `SM83Error` (fail closed). Operand values are resolved here:
    `imm8`, `imm16` (documented little-endian), signed `rel`, `a8`, `a16`,
    and the wrapped 16-bit `target` for jumps/calls/restarts.
    """
    if not isinstance(address, int) or isinstance(address, bool) or not (0 <= address < ADDRESS_LIMIT):
        raise SM83Error(f"SM83 instruction address 0x{address:x} is outside the 16-bit address space")
    if address >= len(code):
        raise SM83Error(f"0x{address:x}: instruction byte is outside the supplied stream")
    word = code[address]
    insn = _base(address, word)
    operands = set(insn.pop("operands", []) or [])

    if insn["op"] == "cb-prefix":
        if address + 1 >= len(code):
            raise SM83Error(f"0x{address:x}: CB prefix without a second byte")
        sub = code[address + 1]
        insn = {"address": address, "word": word, "sub": sub, "length": 2}
        insn.update(_cb_sub(sub))
        return insn

    if insn["length"] > 1:
        end = address + insn["length"]
        if end > len(code):
            raise SM83Error(f"0x{address:x}: {insn['op']} operands run past the supplied stream")

    if "padding" in operands:
        insn["padding"] = code[address + 1]
    if "imm8" in operands:
        insn["imm8"] = code[address + 1]
    if "a8" in operands:
        insn["a8"] = code[address + 1]
    if "rel" in operands:
        rel = code[address + 1]
        rel = rel - 0x100 if rel & 0x80 else rel
        insn["rel"] = rel
        insn["target"] = (address + insn["length"] + rel) & 0xFFFF
    if "imm16" in operands:
        insn["imm16"] = code[address + 1] | (code[address + 2] << 8)
    if "a16" in operands:
        insn["a16"] = code[address + 1] | (code[address + 2] << 8)
        insn["target"] = insn["a16"]
    if insn["op"] == "rst":
        insn["target"] = insn["vector"]
    return insn


def is_control_flow(insn: dict) -> bool:
    """Documented SM83 control-flow mnemonics (structured PC transfer)."""
    return insn.get("op") in {"jp", "jr", "call", "ret", "reti", "rst", "jp_hl"}


def branch_targets(insn: dict) -> list[int]:
    """Static direct targets only; `jp (hl)` and `ret*` have none statically."""
    target = insn.get("target")
    if isinstance(target, int):
        return [target]
    return []
