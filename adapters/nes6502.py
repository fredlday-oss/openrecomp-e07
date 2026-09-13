"""NES 6502 (NMOS 6502) architecture adapter — state model + decoder.

P1-30/P1-31 stage deliverable: the documented architectural state and the
complete official-opcode decoder of the NMOS 6502 used in the Nintendo
Entertainment System (NES, 2A03/2A07).

Every fact below is documented public 6502 behaviour (masswerk 6502
instruction set reference; MOS MCS6500 documentation):

- 8-bit registers: A (accumulator), X, Y (index registers), SP (stack pointer);
- PC (program counter) is a 16-bit implicit control-flow register;
- Flags live in the processor status register (P): bit 7 N (negative),
  bit 6 V (overflow), bit 5 unused (always 1), bit 4 B (break),
  bit 3 D (decimal), bit 2 I (interrupt disable), bit 1 Z (zero),
  bit 0 C (carry). The unused bit is always set. The B flag has no storage;
  it appears only in values pushed to the stack (documented);
- the guest address space is 16 bits (0000..FFFF);
- the documented opcode map contains exactly 151 official opcode values
  using the documented 6502 addressing modes.

The instruction decoder implements the documented 6502 opcode map:
all 151 official encodings plus all documented 6502 addressing modes, from
the public 6502 opcode tables. Every undocumented encoding fails closed with
`NES6502Error` (Phase 1 SCOPE defers unofficial opcodes unless a later stage's
tests require them; they are never guessed).

`decode_full` resolves the stream operands for every addressing mode:
`imm8`, `zp`, `zp,x`, `zp,y`, `abs`, `abs,x`, `abs,y`, `(indirect,x)`,
`(indirect,y)`, signed `rel`, and the wrapped 16-bit `target` for jumps,
calls, branches and the JMP indirect page-boundary behaviour.
"""
from __future__ import annotations

from .interface import ArchitectureInfo

info = ArchitectureInfo(
    "nes6502",
    8,
    "little",
    ("a", "x", "y", "sp", "pc"),
    "NES 2A03/2A07-family 6502: 8-bit A/X/Y/SP, 16-bit PC; flags in P (N/V/unused/B/D/I/Z/C)",
)

# Documented flag bit positions inside P.
FLAG_N = 0x80
FLAG_V = 0x40
FLAG_B = 0x10
FLAG_D = 0x08
FLAG_I = 0x04
FLAG_Z = 0x02
FLAG_C = 0x01

# The unused bit (bit 5) is always set.
FLAG_UNUSED = 0x20

# The 6502 has no architectural register pairs.
REGISTER_PAIRS = ()

# Normalized IR V1 state slots for the architectural register file.
# A/X/Y/SP are 8-bit architectural registers; PC is 16-bit. This is the frozen
# P1-30 architecture-descriptor contract. The processor status register P is a
# separate i8 state slot declared by the frontend (the flags have no register
# pair on the 6502).
STATE_SLOTS = {
    "cpu:a": "i8",
    "cpu:x": "i8",
    "cpu:y": "i8",
    "cpu:sp": "i8",
    "cpu:pc": "i16",  # PC is a state slot in the 6502
}

# Documented 8-bit register operand order used by the ALU.
R8 = ("a", "x", "y", "sp")

# Synthetic test-harness halt convention. The NMOS 6502 has no HALT
# instruction; the undocumented KIL/JAM opcode (0x02) locks the CPU. The
# reference interpreter and the frontend treat a decoded 0x02 byte as a
# deterministic program halt for synthetic fixtures only. It is not a
# documented instruction and `decode` rejects it like any other undocumented
# opcode.
HALT_OPCODE = 0x02


class NES6502Error(ValueError):
    """Fail-closed NES6502 adapter error (unknown encoding, malformed input)."""


def _check_byte(value: int, where: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not (0 <= value <= 0xFF):
        raise NES6502Error(f"{where} 0x{value:x} is outside the 8-bit register width")


def _check_address(address: int, where: str = "") -> None:
    if isinstance(address, bool) or not isinstance(address, int) or not (0 <= address <= 0xFFFF):
        raise NES6502Error(f"6502 instruction address 0x{address:x} is outside the 16-bit address space")


# Documented official-opcode table (masswerk "standard set", 151 encodings).
# Each entry is `opcode mnemonic mode kind` where mode is one of
# impl/acc/imm/zp/zpx/zpy/abs/absx/absy/ind/indx/indy/rel and kind is one of
# impl (no operand), acc (accumulator), read (src), write (dst), rmw
# (read-modify-write dst) or ctrl (control flow).
_OPCODE_TABLE = """
00 brk impl ctrl
01 ora indx read
05 ora zp read
06 asl zp rmw
08 php impl impl
09 ora imm read
0a asl acc acc
0d ora abs read
0e asl abs rmw
10 bpl rel ctrl
11 ora indy read
15 ora zpx read
16 asl zpx rmw
18 clc impl impl
19 ora absy read
1d ora absx read
1e asl absx rmw
20 jsr abs ctrl
21 and indx read
24 bit zp read
25 and zp read
26 rol zp rmw
28 plp impl impl
29 and imm read
2a rol acc acc
2c bit abs read
2d and abs read
2e rol abs rmw
30 bmi rel ctrl
31 and indy read
35 and zpx read
36 rol zpx rmw
38 sec impl impl
39 and absy read
3d and absx read
3e rol absx rmw
40 rti impl ctrl
41 eor indx read
45 eor zp read
46 lsr zp rmw
48 pha impl impl
49 eor imm read
4a lsr acc acc
4c jmp abs ctrl
4d eor abs read
4e lsr abs rmw
50 bvc rel ctrl
51 eor indy read
55 eor zpx read
56 lsr zpx rmw
58 cli impl impl
59 eor absy read
5d eor absx read
5e lsr absx rmw
60 rts impl ctrl
61 adc indx read
65 adc zp read
66 ror zp rmw
68 pla impl impl
69 adc imm read
6a ror acc acc
6c jmp ind ctrl
6d adc abs read
6e ror abs rmw
70 bvs rel ctrl
71 adc indy read
75 adc zpx read
76 ror zpx rmw
78 sei impl impl
79 adc absy read
7d adc absx read
7e ror absx rmw
81 sta indx write
84 sty zp write
85 sta zp write
86 stx zp write
88 dey impl impl
8a txa impl impl
8c sty abs write
8d sta abs write
8e stx abs write
90 bcc rel ctrl
91 sta indy write
94 sty zpx write
95 sta zpx write
96 stx zpy write
98 tya impl impl
99 sta absy write
9a txs impl impl
9d sta absx write
a0 ldy imm read
a1 lda indx read
a2 ldx imm read
a4 ldy zp read
a5 lda zp read
a6 ldx zp read
a8 tay impl impl
a9 lda imm read
aa tax impl impl
ac ldy abs read
ad lda abs read
ae ldx abs read
b0 bcs rel ctrl
b1 lda indy read
b4 ldy zpx read
b5 lda zpx read
b6 ldx zpy read
b8 clv impl impl
b9 lda absy read
ba tsx impl impl
bc ldy absx read
bd lda absx read
be ldx absy read
c0 cpy imm read
c1 cmp indx read
c4 cpy zp read
c5 cmp zp read
c6 dec zp rmw
c8 iny impl impl
c9 cmp imm read
ca dex impl impl
cc cpy abs read
cd cmp abs read
ce dec abs rmw
d0 bne rel ctrl
d1 cmp indy read
d5 cmp zpx read
d6 dec zpx rmw
d8 cld impl impl
d9 cmp absy read
dd cmp absx read
de dec absx rmw
e0 cpx imm read
e1 sbc indx read
e4 cpx zp read
e5 sbc zp read
e6 inc zp rmw
e8 inx impl impl
e9 sbc imm read
ea nop impl impl
ec cpx abs read
ed sbc abs read
ee inc abs rmw
f0 beq rel ctrl
f1 sbc indy read
f5 sbc zpx read
f6 inc zpx rmw
f8 sed impl impl
f9 sbc absy read
fd sbc absx read
fe inc absx rmw
"""


def _parse_table() -> dict[int, tuple[str, str, str]]:
    table: dict[int, tuple[str, str, str]] = {}
    for raw in _OPCODE_TABLE.splitlines():
        line = raw.strip()
        if not line:
            continue
        opcode_hex, mnemonic, mode, kind = line.split()
        opcode = int(opcode_hex, 16)
        if opcode in table:
            raise NES6502Error(f"duplicate opcode in table: 0x{opcode:02x}")
        table[opcode] = (mnemonic, mode, kind)
    return table


OPCODES: dict[int, tuple[str, str, str]] = _parse_table()

# Official opcode values (documented set).
OFFICIAL = frozenset(OPCODES)

# The remaining (undocumented) base opcodes, from the public 6502 tables.
UNDOCUMENTED = frozenset(set(range(0x100)) - OFFICIAL)

# Addressing-mode length in bytes (documented).
MODE_LENGTH = {
    "impl": 1,
    "acc": 1,
    "imm": 2,
    "zp": 2,
    "zpx": 2,
    "zpy": 2,
    "abs": 3,
    "absx": 3,
    "absy": 3,
    "ind": 3,
    "indx": 2,
    "indy": 2,
    "rel": 2,
}

# Stream operand kind(s) declared for each addressing mode (resolved by
# `decode_full`, never guessed by `decode`).
MODE_OPERANDS = {
    "imm": ("imm8",),
    "zp": ("zp",),
    "zpx": ("zp,x",),
    "zpy": ("zp,y",),
    "abs": ("abs",),
    "absx": ("abs,x",),
    "absy": ("abs,y",),
    "ind": ("indirect",),
    "indx": ("indirect,x",),
    "indy": ("indirect,y",),
    "rel": ("rel",),
}

# Documented operand string carried on `src`/`dst` for each address mode.
MODE_SRCSTR = {
    "imm": "imm",
    "zp": "zp",
    "zpx": "zp,x",
    "zpy": "zp,y",
    "abs": "abs",
    "absx": "abs,x",
    "absy": "abs,y",
    "ind": "(indirect)",
    "indx": "(indirect,x)",
    "indy": "(indirect,y)",
}

# Documented conditional-branch opcodes and their tested flag.
BRANCHES = {
    0x10: ("bpl", FLAG_N, False),
    0x30: ("bmi", FLAG_N, True),
    0x50: ("bvc", FLAG_V, False),
    0x70: ("bvs", FLAG_V, True),
    0x90: ("bcc", FLAG_C, False),
    0xB0: ("bcs", FLAG_C, True),
    0xD0: ("bne", FLAG_Z, False),
    0xF0: ("beq", FLAG_Z, True),
}


def _base(address: int, word: int) -> dict:
    """Decode one base opcode byte (stream operands declared, not resolved)."""
    _check_address(address)
    if isinstance(word, bool) or not isinstance(word, int) or not (0 <= word <= 0xFF):
        raise NES6502Error(f"6502 opcode 0x{word:x} is outside the 8-bit width")

    entry = OPCODES.get(word)
    if entry is None:
        raise NES6502Error(f"0x{address:x}: undocumented 6502 opcode 0x{word:02x}")

    mnemonic, mode, kind = entry
    insn: dict = {"address": address, "word": word, "op": mnemonic, "length": MODE_LENGTH[mode]}

    if kind == "impl":
        pass
    elif kind == "acc":
        insn["dst"] = "a"
    elif kind == "ctrl":
        if mode == "rel":
            insn["operands"] = ["rel"]
        elif mnemonic == "jsr":
            insn["operands"] = ["a16"]
        elif mnemonic == "jmp" and mode == "ind":
            insn["operands"] = ["indirect"]
            insn["dst"] = "(indirect)"
        elif mnemonic == "jmp":
            insn["operands"] = ["abs"]
            insn["dst"] = "abs"
        # brk/rti/rts are implied control transfers.
    else:
        insn["operands"] = list(MODE_OPERANDS[mode])
        insn["src" if kind == "read" else "dst"] = MODE_SRCSTR[mode]

    return insn


def decode(address: int, word: int) -> dict:
    """Decode one instruction byte.

    Stream-resident operands are declared under `operands`, never guessed here.
    """
    return _base(address, word)


def jmp_indirect_target(memory, pointer: int) -> int:
    """Documented NMOS 6502 JMP ($nnnn) page-boundary behaviour.

    When the low byte of the pointer is 0xFF the high byte is fetched from the
    same page (0xnn00), not the next page (documented NMOS bug). `memory` must
    be indexable over the full 16-bit guest address space.
    """
    _check_address(pointer)
    lo = memory[pointer]
    hi_address = (pointer & 0xFF00) | ((pointer + 1) & 0x00FF)
    return (memory[hi_address] << 8) | lo


def decode_full(code, address: int) -> dict:
    """Decode a complete instruction from a byte stream.

    `code` is a bytes-like object of guest memory. Reads are bounds-checked;
    an instruction whose operands run past the end of the stream raises
    `NES6502Error` (fail closed). Operand values are resolved here:
    `imm8`, the zero-page and absolute operand forms, signed `rel`, and the
    wrapped 16-bit `target` for branches, `jmp`/`jsr`.
    """
    _check_address(address)
    if address >= len(code):
        raise NES6502Error(f"0x{address:x}: instruction byte is outside the supplied stream")
    word = code[address]
    insn = _base(address, word)
    operands = set(insn.pop("operands", []) or [])

    if insn["length"] > 1:
        end = address + insn["length"]
        if end > len(code):
            raise NES6502Error(f"0x{address:x}: {insn['op']} operands run past the supplied stream")

    if "rel" in operands:
        rel = code[address + 1]
        rel = rel - 0x100 if rel & 0x80 else rel
        insn["rel"] = rel
        insn["target"] = (address + insn["length"] + rel) & 0xFFFF
    elif "imm8" in operands:
        insn["imm8"] = code[address + 1]
    elif "a16" in operands:
        insn["a16"] = code[address + 1] | (code[address + 2] << 8)
        insn["target"] = insn["a16"]
    elif "zp" in operands:
        insn["zp"] = code[address + 1]
    elif "zp,x" in operands:
        insn["zp,x"] = code[address + 1]
    elif "zp,y" in operands:
        insn["zp,y"] = code[address + 1]
    elif "abs" in operands:
        insn["abs"] = code[address + 1] | (code[address + 2] << 8)
        if insn["op"] == "jmp":
            insn["target"] = insn["abs"]
    elif "abs,x" in operands:
        insn["abs,x"] = code[address + 1] | (code[address + 2] << 8)
    elif "abs,y" in operands:
        insn["abs,y"] = code[address + 1] | (code[address + 2] << 8)
    elif "indirect" in operands:
        # The pointer is a runtime value resolved against full guest memory by
        # the executor (it may lie outside the supplied instruction stream).
        insn["indirect"] = code[address + 1] | (code[address + 2] << 8)
    elif "indirect,x" in operands:
        insn["indirect,x"] = code[address + 1]
    elif "indirect,y" in operands:
        insn["indirect,y"] = code[address + 1]

    return insn


# Documented control-flow mnemonics (structured PC transfer).
CONTROL_FLOW = frozenset(
    {"jmp", "jsr", "brk", "rti", "rts", "bpl", "bmi", "bvc", "bvs", "bcc", "bcs", "bne", "beq"}
)


def is_control_flow(insn: dict) -> bool:
    """True for documented 6502 control-flow mnemonics."""
    return insn.get("op") in CONTROL_FLOW


def is_branch(insn: dict) -> bool:
    """True for the eight documented conditional branches."""
    return insn.get("op") in {name for name, _flag, _taken in BRANCHES.values()}


def branch_targets(insn: dict) -> list[int]:
    """Static direct targets only (`jmp abs` and `jsr` have static targets).

    Indirect `jmp` and `rts`/`rti` targets are dynamic and are reported by the
    frontend as indirect control flow, never guessed here.
    """
    if insn.get("op") in ("jmp", "jsr") and isinstance(insn.get("target"), int):
        return [insn["target"]]
    return []
