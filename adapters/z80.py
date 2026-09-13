"""Zilog Z80 architecture adapter — documented state model + decoder (P1-20).

Targets the Z80 as used in the Sega Master System (SMS). Only behaviour
documented in the public Z80 references (Zilog Z80 CPU User Manual primary
encodings; the z80-heaven opcode reference chart; z80.info index-prefix
decoding rules) is implemented:

State:

- 8-bit registers A, F, B, C, D, E, H, L plus the complete shadow set
  (A', F', B', C', D', E', H', L') exchanged by EXX / EX AF,AF';
- 16-bit registers: IX, IY (index), SP (stack), PC (implicit control flow);
- flags in F: bit 7 S (sign), bit 6 Z (zero), bit 5 Y, bit 4 H (half carry),
  bit 3 X, bit 2 P/V (parity/overflow), bit 1 N (subtract), bit 0 C (carry).
  X/Y (bits 3/5) are undocumented and pinned to 0 in this model (documented
  limitation; no semantics guessed);
- I (interrupt vector high byte), R (refresh), IFF1/IFF2 interrupt flip-flops,
  interrupt mode IM 0/1/2.

Decoder:

- all 256 base opcodes (the documented primary map);
- ED prefix: IN r,(C)/OUT (C),r, SBC/ADC HL,rp, LD (nn),rp / LD rp,(nn), NEG,
  RETN (ED 45), RETI (ED 4D), IM 0/1/2 (ED 46/56/5E), LD I,A / LD R,A /
  LD A,I / LD A,R, RRD, RLD, and the eight block-transfer groups
  (LDI/LDIR/LDD/LDDR, CPI/CPIR/CPD/CPDR, INI/INIR/IND/INDR,
  OUTI/OTIR/OUTD/OTDR). Undocumented ED encodings (e.g. IN F,(C), OUT (C),0,
  the RETN/RETI/IM alias bytes, ED 76) fail closed;
- CB prefix: RLC/RRC/RL/RR/SLA/SRA/SRL, BIT/RES/SET on all registers and
  (HL). CB 30-37 (SLL) is not part of the Z80 manual (Z180 only) and fails
  closed;
- DD/FD prefixes: documented IX/IY forms — LD IX,nn, ADD IX,rp, INC/DEC IX,
  LD IX,(nn) / LD (nn),IX, LD (IX+d),n, LD r,(IX+d) / LD (IX+d),r, ALU
  A,(IX+d), INC/DEC (IX+d), EX (SP),IX, PUSH/POP IX, JP (IX), LD SP,IX, and
  the DDCB/FDCB (IX+d)/(IY+d) bit-group forms. The displacement byte sits
  after the opcode byte (after the CB byte for DDCB/FDCB). DD/FD before an
  instruction that does not involve H/L/(HL) is ignored (documented).
  IXH/IXL register-split forms (undocumented in the Zilog manual) and
  DDCB/FDCB register-operand forms fail closed;
- every stream read is bounds-checked; truncated instructions and
  undocumented encodings raise `Z80Error` (fail closed).

The Z80 instruction set is a strict superset of the SM83 set, but this
adapter is written independently (no SM83 table reuse) so the P1-21
differential proof keeps two separately written semantic models.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .interface import ArchitectureInfo

info = ArchitectureInfo(
    "z80-sms",
    8,
    "little",
    ("a", "f", "b", "c", "d", "e", "h", "l"),
    "Zilog Z80 (Sega Master System core): AF/BC/DE/HL pairs, IX/IY index, "
    "full shadow set via EXX/EX AF,AF'; flags S/Z/Y/H/X/P/V/N/C in F",
)

# Documented flag bit positions inside F.
FLAG_C = 0x01
FLAG_N = 0x02
FLAG_PV = 0x04
FLAG_X = 0x08  # undocumented; pinned to 0 in this model
FLAG_H = 0x10
FLAG_Y = 0x20  # undocumented; pinned to 0 in this model
FLAG_Z = 0x40
FLAG_S = 0x80

# The documented register order used by the ALU/LD/CB tables.
R8 = ("b", "c", "d", "e", "h", "l", "(hl)", "a")
ALU = ("add", "adc", "sub", "sbc", "and", "xor", "or", "cp")
# Documented condition codes (8 Z80 conditions; JR uses only the first 4).
CC = ("nz", "z", "nc", "c", "po", "pe", "p", "m")
# 16-bit register pairs for ADD/ADC/SBC (and LD SP,HL).
RP = ("bc", "de", "hl", "sp")
# Push/pop order (documented: PUSH qq = 0xC5 + 0x10*q).
RP2 = ("bc", "de", "hl", "af")
RST_VECTORS = (0x00, 0x08, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38)

ADDRESS_LIMIT = 1 << 16

# CB-group operations in the documented order of the (sub >> 3) field.
CB_KINDS = ("rlc", "rrc", "rl", "rr", "sla", "sra", "sll", "srl")
# The undocumented CB group index (SLL).
CB_UNDOCUMENTED_KIND = 6

# The undocumented DD/FD register-split forms and ED aliases are rejected by
# dedicated checks inside the decoders (documented below each site).


class Z80Error(ValueError):
    """Fail-closed Z80 adapter error (unknown encoding, malformed input)."""


@dataclass
class Z80State:
    """Documented Z80 architectural register file."""

    a: int = 0
    f: int = 0
    b: int = 0
    c: int = 0
    d: int = 0
    e: int = 0
    h: int = 0
    l: int = 0
    a2: int = 0
    f2: int = 0
    b2: int = 0
    c2: int = 0
    d2: int = 0
    e2: int = 0
    h2: int = 0
    l2: int = 0
    ix: int = 0
    iy: int = 0
    sp: int = 0
    pc: int = 0
    i: int = 0
    r: int = 0
    iff1: bool = False
    iff2: bool = False
    im: int = 0
    halted: bool = False

    def snapshot(self) -> dict:
        return {
            "a": self.a, "f": self.f, "b": self.b, "c": self.c,
            "d": self.d, "e": self.e, "h": self.h, "l": self.l,
            "a2": self.a2, "f2": self.f2, "b2": self.b2, "c2": self.c2,
            "d2": self.d2, "e2": self.e2, "h2": self.h2, "l2": self.l2,
            "ix": self.ix, "iy": self.iy, "sp": self.sp, "pc": self.pc,
            "i": self.i, "r": self.r,
            "iff1": int(self.iff1), "iff2": int(self.iff2),
            "im": self.im, "halted": int(self.halted),
        }


def _check_address(address: int) -> None:
    if isinstance(address, bool) or not isinstance(address, int) or not (0 <= address < ADDRESS_LIMIT):
        raise Z80Error(f"Z80 instruction address 0x{address:x} is outside the 16-bit address space")


def _check_word(word: int) -> None:
    if isinstance(word, bool) or not isinstance(word, int) or not (0 <= word <= 0xFF):
        raise Z80Error(f"Z80 opcode 0x{word:x} is outside the 8-bit width")


def pair_of(high: int, low: int) -> int:
    """Compose a documented 16-bit register pair (high byte first)."""
    if not (0 <= high <= 0xFF and 0 <= low <= 0xFF):
        raise Z80Error(f"pair bytes 0x{high:x}/0x{low:x} are outside the 8-bit width")
    return (high << 8) | low


def pair_halves(value: int) -> tuple[int, int]:
    """Split a 16-bit pair into (high, low) bytes."""
    if isinstance(value, bool) or not isinstance(value, int) or not (0 <= value <= 0xFFFF):
        raise Z80Error(f"pair value 0x{value:x} is outside the 16-bit register width")
    return (value >> 8) & 0xFF, value & 0xFF


def get_pair(state: Z80State, name: str) -> int:
    parts = {"af": ("a", "f"), "bc": ("b", "c"), "de": ("d", "e"), "hl": ("h", "l")}[name]
    return pair_of(getattr(state, parts[0]), getattr(state, parts[1]))


def set_pair(state: Z80State, name: str, value: int) -> None:
    high, low = pair_halves(value)
    parts = {"af": ("a", "f"), "bc": ("b", "c"), "de": ("d", "e"), "hl": ("h", "l")}[name]
    setattr(state, parts[0], high)
    setattr(state, parts[1], low)


def exchange_all(state: Z80State) -> None:
    """EXX: exchange BC/DE/HL with the shadow set (documented)."""
    state.b, state.b2 = state.b2, state.b
    state.c, state.c2 = state.c2, state.c
    state.d, state.d2 = state.d2, state.d
    state.e, state.e2 = state.e2, state.e
    state.h, state.h2 = state.h2, state.h
    state.l, state.l2 = state.l2, state.l


def exchange_af(state: Z80State) -> None:
    """EX AF,AF': exchange AF with the shadow set (documented)."""
    state.a, state.a2 = state.a2, state.a
    state.f, state.f2 = state.f2, state.f


def _base(address: int, word: int) -> dict:
    """Decode one base opcode byte (stream operands declared, not resolved)."""
    _check_address(address)
    _check_word(word)

    insn: dict = {"address": address, "word": word, "op": "", "length": 1}
    if word == 0x00:
        insn.update(op="nop")
    elif word == 0x08:
        insn.update(op="ex_af")
    elif word == 0xD9:
        insn.update(op="exx")
    elif word == 0xE3:
        insn.update(op="ex", dst="(sp)", src="hl")
    elif word == 0xEB:
        insn.update(op="ex", dst="de", src="hl")
    elif word == 0x27:
        insn.update(op="daa")
    elif word == 0x2F:
        insn.update(op="cpl")
    elif word == 0x37:
        insn.update(op="scf")
    elif word == 0x3F:
        insn.update(op="ccf")
    elif word == 0x07:
        insn.update(op="rlca")
    elif word == 0x0F:
        insn.update(op="rrca")
    elif word == 0x17:
        insn.update(op="rla")
    elif word == 0x1F:
        insn.update(op="rra")
    elif word == 0x76:
        insn.update(op="halt")
    elif word == 0xF3:
        insn.update(op="di")
    elif word == 0xFB:
        insn.update(op="ei")
    elif word == 0xE9:
        insn.update(op="jp_ind", reg="hl")
    elif word == 0xF9:
        insn.update(op="ld_sp_r16", reg="hl")
    elif word == 0xCB:
        insn.update(op="cb-prefix")
    elif word == 0xDD:
        insn.update(op="dd-prefix")
    elif word == 0xED:
        insn.update(op="ed-prefix")
    elif word == 0xFD:
        insn.update(op="fd-prefix")
    elif word in (0x01, 0x11, 0x21, 0x31):
        pair = RP[(word >> 4) & 3]
        insn.update(op="ld", dst=pair, length=3, operands=["imm16"])
    elif word == 0x22:
        insn.update(op="ld", dst="(a16)", src="hl", length=3, operands=["a16"])
    elif word == 0x2A:
        insn.update(op="ld", dst="hl", src="(a16)", length=3, operands=["a16"])
    elif word == 0x32:
        insn.update(op="ld", dst="(a16)", src="a", length=3, operands=["a16"])
    elif word == 0x3A:
        insn.update(op="ld", dst="a", src="(a16)", length=3, operands=["a16"])
    elif word == 0x02:
        insn.update(op="ld", dst="(bc)", src="a")
    elif word == 0x12:
        insn.update(op="ld", dst="(de)", src="a")
    elif word == 0x0A:
        insn.update(op="ld", dst="a", src="(bc)")
    elif word == 0x1A:
        insn.update(op="ld", dst="a", src="(de)")
    elif word in (0x03, 0x13, 0x23, 0x33):
        insn.update(op="inc", r=RP[(word >> 4) & 3])
    elif word in (0x0B, 0x1B, 0x2B, 0x3B):
        insn.update(op="dec", r=RP[(word >> 4) & 3])
    elif word in (0x09, 0x19, 0x29, 0x39):
        insn.update(op="add_hl", pair=RP[(word >> 4) & 3])
    elif word in (0x04, 0x0C, 0x14, 0x1C, 0x24, 0x2C, 0x34, 0x3C):
        insn.update(op="inc", r=R8[(word >> 3) & 7])
    elif word in (0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D):
        insn.update(op="dec", r=R8[(word >> 3) & 7])
    elif word in (0x06, 0x0E, 0x16, 0x1E, 0x26, 0x2E, 0x36, 0x3E):
        insn.update(op="ld", dst=R8[(word >> 3) & 7], length=2, operands=["imm8"])
    elif word == 0x10:
        insn.update(op="djnz", length=2, operands=["rel"])
    elif word in (0x18, 0x20, 0x28, 0x30, 0x38):
        if word == 0x18:
            insn.update(op="jr", length=2, operands=["rel"])
        else:
            cond = CC[(word >> 3) & 3]
            insn.update(op="jr", cond=cond, length=2, operands=["rel"])
    elif word in (0xC3, 0xC2, 0xCA, 0xD2, 0xDA, 0xE2, 0xEA, 0xF2, 0xFA):
        if word == 0xC3:
            insn.update(op="jp", length=3, operands=["a16"])
        else:
            insn.update(op="jp", cond=CC[(word >> 3) & 7], length=3, operands=["a16"])
    elif word in (0xCD, 0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC):
        if word == 0xCD:
            insn.update(op="call", length=3, operands=["a16"])
        else:
            insn.update(op="call", cond=CC[(word >> 3) & 7], length=3, operands=["a16"])
    elif word in (0xC9, 0xC0, 0xC8, 0xD0, 0xD8, 0xE0, 0xE8, 0xF0, 0xF8):
        if word == 0xC9:
            insn.update(op="ret")
        else:
            insn.update(op="ret", cond=CC[(word >> 3) & 7])
    elif word in (0xC1, 0xD1, 0xE1, 0xF1):
        insn.update(op="pop", pair=RP2[(word >> 4) & 3])
    elif word in (0xC5, 0xD5, 0xE5, 0xF5):
        insn.update(op="push", pair=RP2[(word >> 4) & 3])
    elif word in (0xC6, 0xCE, 0xD6, 0xDE, 0xE6, 0xEE, 0xF6, 0xFE):
        insn.update(op=ALU[(word >> 3) & 7], length=2, operands=["imm8"])
    elif word in (0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF):
        insn.update(op="rst", vector=RST_VECTORS[(word >> 3) & 7])
    elif word in (0xD3, 0xDB):
        if word == 0xD3:
            insn.update(op="out", src="a", length=2, operands=["port_n"])
        else:
            insn.update(op="in", dst="a", length=2, operands=["port_n"])
    elif 0x40 <= word <= 0x7F:
        insn.update(op="ld", dst=R8[(word >> 3) & 7], src=R8[word & 7])
    elif 0x80 <= word <= 0xBF:
        insn.update(op=ALU[(word >> 3) & 7], r=R8[word & 7])
    else:
        raise Z80Error(f"0x{address:x}: undocumented Z80 opcode 0x{word:02x}")
    return insn


def _ed(address: int, sub: int) -> dict:
    """Decode an ED-prefixed second byte (documented primary encodings only)."""
    _check_word(sub)
    insn: dict = {"address": address, "sub": sub, "op": "", "length": 2}
    r16 = None
    if sub in (0x40, 0x48, 0x50, 0x58, 0x60, 0x68, 0x78):
        regs = ("b", "c", "d", "e", "h", "l", None, "a")
        reg = regs[(sub >> 3) & 7]
        if reg is None:
            raise Z80Error(f"0x{address:x}: undocumented ED 0x{sub:02x} (IN F,(C))")
        insn.update(op="in", dst=reg, src="(c)")
    elif sub in (0x41, 0x49, 0x51, 0x59, 0x61, 0x69, 0x79):
        regs = ("b", "c", "d", "e", "h", "l", None, "a")
        reg = regs[(sub >> 3) & 7]
        if reg is None:
            raise Z80Error(f"0x{address:x}: undocumented ED 0x{sub:02x} (OUT (C),0)")
        insn.update(op="out", dst="(c)", src=reg)
    elif sub in (0x42, 0x52, 0x62, 0x72):
        insn.update(op="sbc_hl", pair=RP[(sub >> 4) & 3])
    elif sub in (0x4A, 0x5A, 0x6A, 0x7A):
        insn.update(op="adc_hl", pair=RP[(sub >> 4) & 3])
    elif sub in (0x43, 0x53, 0x63, 0x73):
        insn.update(op="ld", dst="(a16)", src=RP[(sub >> 4) & 3], length=4, operands=["a16"])
    elif sub in (0x4B, 0x5B, 0x6B, 0x7B):
        insn.update(op="ld", dst=RP[(sub >> 4) & 3], src="(a16)", length=4, operands=["a16"])
    elif sub in (0x44, 0x4C, 0x54, 0x5C, 0x64, 0x6C, 0x74, 0x7C):
        insn.update(op="neg")
    elif sub == 0x45:
        insn.update(op="retn")
    elif sub == 0x4D:
        insn.update(op="reti")
    elif sub == 0x46:
        insn.update(op="im", mode=0)
    elif sub == 0x56:
        insn.update(op="im", mode=1)
    elif sub == 0x5E:
        insn.update(op="im", mode=2)
    elif sub == 0x47:
        insn.update(op="ld", dst="i", src="a")
    elif sub == 0x4F:
        insn.update(op="ld", dst="r", src="a")
    elif sub == 0x57:
        insn.update(op="ld", dst="a", src="i")
    elif sub == 0x5F:
        insn.update(op="ld", dst="a", src="r")
    elif sub == 0x67:
        insn.update(op="rrd")
    elif sub == 0x6F:
        insn.update(op="rld")
    elif sub in (0xA0, 0xA1, 0xA2, 0xA3, 0xA8, 0xA9, 0xAA, 0xAB,
                 0xB0, 0xB1, 0xB2, 0xB3, 0xB8, 0xB9, 0xBA, 0xBB):
        ops = {
            0xA0: "ldi", 0xB0: "ldir", 0xA8: "ldd", 0xB8: "lddr",
            0xA1: "cpi", 0xB1: "cpir", 0xA9: "cpd", 0xB9: "cpdr",
            0xA2: "ini", 0xB2: "inir", 0xAA: "ind", 0xBA: "indr",
            0xA3: "outi", 0xB3: "otir", 0xAB: "outd", 0xBB: "otdr",
        }
        insn.update(op=ops[sub])
    else:
        raise Z80Error(f"0x{address:x}: undocumented ED opcode 0x{sub:02x}")
    return insn


def _cb_sub(address: int, sub: int) -> dict:
    """Decode a CB-page opcode byte into op/operand fields."""
    _check_word(sub)
    r = R8[sub & 7]
    if sub < 0x40:
        kind = CB_KINDS[(sub >> 3) & 7]
        if kind == "sll":
            raise Z80Error(f"0x{address:x}: CB 0x{sub:02x} is SLL (undocumented on the Z80; Z180 only)")
        return {"op": kind, "r": r}
    n = (sub >> 3) & 7
    if sub < 0x80:
        return {"op": "bit", "n": n, "r": r}
    if sub < 0xC0:
        return {"op": "res", "n": n, "r": r}
    return {"op": "set", "n": n, "r": r}


def _signed_byte(value: int) -> int:
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def _index_form(base_insn: dict, prefix: str) -> dict | None:
    """Documented DD/FD substitution for one base opcode.

    Returns the rewritten instruction, or None when the prefix is ignored
    (the instruction does not involve H/L/(HL)). Undocumented IXH/IXL
    register-split forms raise `Z80Error` (fail closed).
    """
    op = base_insn["op"]
    if op in ("ld",):
        dst = base_insn.get("dst")
        src = base_insn.get("src")
        if dst == "hl" and "imm16" in base_insn.get("operands", []):
            base_insn["dst"] = prefix
            return base_insn
        if dst == "hl" and src == "(a16)":
            base_insn["dst"] = prefix
            return base_insn
        if dst == "(a16)" and src == "hl":
            base_insn["src"] = prefix
            return base_insn
        if dst == "(hl)":
            base_insn["dst"] = f"({prefix}+d)"
            base_insn["base"] = prefix
            return base_insn
        if src == "(hl)":
            base_insn["src"] = f"({prefix}+d)"
            base_insn["base"] = prefix
            return base_insn
        if dst in ("h", "l") or src in ("h", "l"):
            raise Z80Error(
                f"0x{base_insn['address']:x}: {prefix.upper()} register-split form "
                f"(IXH/IXL) is undocumented on the Z80 (fail closed)"
            )
        return None  # prefix ignored (documented)
    if op in ("inc", "dec"):
        r = base_insn.get("r")
        if r == "hl":
            base_insn["r"] = prefix
            return base_insn
        if r == "(hl)":
            base_insn["r"] = f"({prefix}+d)"
            base_insn["base"] = prefix
            return base_insn
        if r in ("h", "l"):
            raise Z80Error(
                f"0x{base_insn['address']:x}: {prefix.upper()} register-split form "
                f"(IXH/IXL) is undocumented on the Z80 (fail closed)"
            )
        return None  # prefix ignored (documented)
    if op == "add_hl":
        base_insn["op"] = "add_r16"
        base_insn["dst"] = prefix
        pair = base_insn.get("pair")
        base_insn["pair"] = prefix if pair == "hl" else pair  # documented: HL -> IX/IY
        return base_insn
    if op in ("add", "adc", "sub", "sbc", "and", "xor", "or", "cp"):
        if base_insn.get("r") == "(hl)":
            base_insn["r"] = f"({prefix}+d)"
            base_insn["base"] = prefix
            return base_insn
        return None  # prefix ignored (documented)
    if op == "ex" and base_insn.get("dst") == "(sp)" and base_insn.get("src") == "hl":
        base_insn["src"] = prefix
        return base_insn
    if op == "push" and base_insn.get("pair") == "hl":
        base_insn["pair"] = prefix
        return base_insn
    if op == "pop" and base_insn.get("pair") == "hl":
        base_insn["pair"] = prefix
        return base_insn
    if op == "jp_ind" and base_insn.get("reg") == "hl":
        base_insn["reg"] = prefix
        return base_insn
    if op == "ld_sp_r16" and base_insn.get("reg") == "hl":
        base_insn["reg"] = prefix
        return base_insn
    return None  # prefix ignored (documented)


def decode(address: int, word: int) -> dict:
    """Decode one instruction byte.

    For the base map this is the opcode byte itself; prefix bytes decode as
    `cb-prefix`/`dd-prefix`/`ed-prefix`/`fd-prefix` (the following bytes are
    resolved by `decode_full`). Stream-resident operands are declared under
    `operands`, never guessed here.
    """
    return _base(address, word)


def decode_full(code, address: int) -> dict:
    """Decode a complete instruction from a byte stream.

    `code` is a bytes-like object of guest memory. Reads are bounds-checked;
    truncated instructions and undocumented encodings raise `Z80Error`
    (fail closed). Operand values are resolved here: `imm8`, `imm16`
    (documented little-endian), signed `rel` (target wrapped at 16 bits),
    `a16` (with `target`), the DD/FD signed displacement `d` and the
    IN/OUT port byte `port_n`.
    """
    _check_address(address)
    if address >= len(code):
        raise Z80Error(f"0x{address:x}: instruction byte is outside the supplied stream")

    cursor = address
    prefix = None
    while True:
        if cursor >= len(code):
            raise Z80Error(f"0x{address:x}: prefix without an instruction byte")
        word = code[cursor]
        if word in (0xDD, 0xFD):
            prefix = "ix" if word == 0xDD else "iy"
            cursor += 1
            continue
        break

    if prefix is not None and word in (0xDD, 0xED, 0xFD):
        # Documented: the first DD/FD is ignored, the next prefix is processed.
        inner = decode_full(code, cursor)
        inner["address"] = address
        inner["length"] += cursor - address
        inner["prefix_ignored"] = True
        return inner

    insn: dict
    if prefix is not None and word == 0xCB:
        # DDCB/FDCB: DD CB <d> <sub> — only the documented (IX+d)/(IY+d)
        # operand forms; register-operand forms are undocumented (fail closed).
        cursor += 1
        if cursor >= len(code):
            raise Z80Error(f"0x{address:x}: {prefix.upper()}CB without a displacement byte")
        d_byte = code[cursor]
        cursor += 1
        if cursor >= len(code):
            raise Z80Error(f"0x{address:x}: {prefix.upper()}CB without an opcode byte")
        sub = code[cursor]
        if (sub & 7) != 6:
            raise Z80Error(
                f"0x{address:x}: {prefix.upper()}CB register-operand form 0x{sub:02x} is undocumented (fail closed)"
            )
        sub_insn = _cb_sub(address, sub)
        insn = {
            "address": address,
            "word": word,
            "sub": sub,
            "base": prefix,
            "d": _signed_byte(d_byte),
            "length": cursor - address + 1,
        }
        insn.update(sub_insn)
        insn["r"] = f"({prefix}+d)"
        return insn

    if word == 0xED:
        cursor += 1
        if cursor >= len(code):
            raise Z80Error(f"0x{address:x}: ED prefix without a second byte")
        sub = code[cursor]
        insn = _ed(address, sub)
        insn["word"] = word
        insn["length"] += cursor - address - 1
    elif word == 0xCB:
        cursor += 1
        if cursor >= len(code):
            raise Z80Error(f"0x{address:x}: CB prefix without a second byte")
        sub = code[cursor]
        insn = {"address": address, "word": word, "sub": sub, "length": cursor - address + 1}
        insn.update(_cb_sub(address, sub))
    else:
        insn = _base(address, word)
        if prefix is not None:
            rewritten = _index_form(insn, prefix)
            if rewritten is None:
                insn["prefix_ignored"] = True
                insn["prefix"] = prefix
        insn["length"] += cursor - address

    operands = set(insn.pop("operands", []) or [])
    length = insn.get("length", 1)
    has_disp = insn.get("base") is not None and "d" not in insn
    if has_disp:
        # The documented DD/FD displacement byte sits after the opcode byte,
        # before any trailing operands.
        length += 1
        insn["length"] = length
    if length > 1:
        end = address + length
        if end > len(code):
            raise Z80Error(f"0x{address:x}: {insn['op']} operands run past the supplied stream")

    if "imm8" in operands:
        insn["imm8"] = code[address + length - 1]
    if "port_n" in operands:
        insn["port_n"] = code[address + length - 1]
    if "imm16" in operands:
        insn["imm16"] = code[address + length - 2] | (code[address + length - 1] << 8)
    if "a16" in operands:
        insn["a16"] = code[address + length - 2] | (code[address + length - 1] << 8)
        insn["target"] = insn["a16"]
    if "rel" in operands:
        rel = _signed_byte(code[address + length - 1])
        insn["rel"] = rel
        insn["target"] = (address + length + rel) & 0xFFFF
    if has_disp:
        insn["d"] = _signed_byte(code[cursor + 1])
    if insn["op"] == "rst":
        insn["target"] = insn["vector"]
    return insn


def is_control_flow(insn: dict) -> bool:
    """Documented Z80 control-flow mnemonics (structured PC transfer)."""
    return insn.get("op") in {"jp", "jr", "call", "ret", "retn", "reti", "rst", "djnz", "jp_ind"}


def branch_targets(insn: dict) -> list[int]:
    """Static direct targets only; `jp (hl)/(ix)/(iy)` and `ret*` have none statically."""
    target = insn.get("target")
    if isinstance(target, int):
        return [target]
    return []
