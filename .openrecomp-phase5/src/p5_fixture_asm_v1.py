#!/usr/bin/env python3
"""Deterministic 6502 assembler for the original Phase-5 public NES fixture.

This is an original, minimal two-pass assembler written from the publicly
documented MOS/NMOS 6502 encoding tables. It exists so the Phase-5 public
fixture can be authored and rebuilt reproducibly without any third-party
toolchain, and so the fixture's exact instruction bytes can be cross-checked
against the frozen OpenRecomp NES6502 decoder (`adapters.nes6502`).

Supported surface (deliberately bounded, fail-closed on everything else):

* labels (`name:`), expressions `symbol+N` / `symbol-N`, `$hhhh` hex and
  decimal literals, `.org`, `.byte`, `.word`, `.res`;
* addressing forms: implied, accumulator (`asl a`), immediate (`#expr`,
  `#<expr`, `#>expr`), zero page (`$hh`), zero page,X/Y, absolute, absolute
  X/Y, `(expr,X)`, `(expr),Y`, `jmp (expr)` and relative branches.
* every unsupported mnemonic, unsupported addressing mode, out-of-range value,
  duplicate label or unresolved symbol raises `AssemblyError` (no guessing).

The assembler is intentionally independent of `adapters/nes6502.py`; the
fixture builder cross-checks both directions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


class AssemblyError(ValueError):
    """Fail-closed assembler error."""


ACCUMULATOR_OPS = {"asl", "lsr", "rol", "ror"}
BRANCH_OPS = {"bcc", "bcs", "beq", "bmi", "bne", "bpl", "bvc", "bvs"}

IMPLIED = {
    "brk": 0x00,
    "clc": 0x18,
    "cld": 0xD8,
    "cli": 0x58,
    "clv": 0xB8,
    "dex": 0xCA,
    "dey": 0x88,
    "inx": 0xE8,
    "iny": 0xC8,
    "nop": 0xEA,
    "pha": 0x48,
    "php": 0x08,
    "pla": 0x68,
    "plp": 0x28,
    "rti": 0x40,
    "rts": 0x60,
    "sec": 0x38,
    "sed": 0xF8,
    "sei": 0x78,
    "tax": 0xAA,
    "tay": 0xA8,
    "tsx": 0xBA,
    "txa": 0x8A,
    "txs": 0x9A,
    "tya": 0x98,
}

ACCUMULATOR = {
    "asl": 0x0A,
    "lsr": 0x4A,
    "rol": 0x2A,
    "ror": 0x6A,
}

# (mnemonic, mode) -> opcode
OPCODES = {
    ("adc", "imm"): 0x69, ("adc", "zp"): 0x65, ("adc", "zpx"): 0x75,
    ("adc", "abs"): 0x6D, ("adc", "absx"): 0x7D, ("adc", "absy"): 0x79,
    ("adc", "indx"): 0x61, ("adc", "indy"): 0x71,
    ("and", "imm"): 0x29, ("and", "zp"): 0x25, ("and", "zpx"): 0x35,
    ("and", "abs"): 0x2D, ("and", "absx"): 0x3D, ("and", "absy"): 0x39,
    ("and", "indx"): 0x21, ("and", "indy"): 0x31,
    ("asl", "zp"): 0x06, ("asl", "zpx"): 0x16, ("asl", "abs"): 0x0E,
    ("asl", "absx"): 0x1E,
    ("bit", "zp"): 0x24, ("bit", "abs"): 0x2C,
    ("bcc", "rel"): 0x90, ("bcs", "rel"): 0xB0, ("beq", "rel"): 0xF0,
    ("bmi", "rel"): 0x30, ("bne", "rel"): 0xD0, ("bpl", "rel"): 0x10,
    ("bvc", "rel"): 0x50, ("bvs", "rel"): 0x70,
    ("cmp", "imm"): 0xC9, ("cmp", "zp"): 0xC5, ("cmp", "zpx"): 0xD5,
    ("cmp", "abs"): 0xCD, ("cmp", "absx"): 0xDD, ("cmp", "absy"): 0xD9,
    ("cmp", "indx"): 0xC1, ("cmp", "indy"): 0xD1,
    ("cpx", "imm"): 0xE0, ("cpx", "zp"): 0xE4, ("cpx", "abs"): 0xEC,
    ("cpy", "imm"): 0xC0, ("cpy", "zp"): 0xC4, ("cpy", "abs"): 0xCC,
    ("dec", "zp"): 0xC6, ("dec", "zpx"): 0xD6, ("dec", "abs"): 0xCE,
    ("dec", "absx"): 0xDE,
    ("eor", "imm"): 0x49, ("eor", "zp"): 0x45, ("eor", "zpx"): 0x55,
    ("eor", "abs"): 0x4D, ("eor", "absx"): 0x5D, ("eor", "absy"): 0x59,
    ("eor", "indx"): 0x41, ("eor", "indy"): 0x51,
    ("inc", "zp"): 0xE6, ("inc", "zpx"): 0xF6, ("inc", "abs"): 0xEE,
    ("inc", "absx"): 0xFE,
    ("jmp", "abs"): 0x4C, ("jmp", "ind"): 0x6C,
    ("jsr", "abs"): 0x20,
    ("lda", "imm"): 0xA9, ("lda", "zp"): 0xA5, ("lda", "zpx"): 0xB5,
    ("lda", "abs"): 0xAD, ("lda", "absx"): 0xBD, ("lda", "absy"): 0xB9,
    ("lda", "indx"): 0xA1, ("lda", "indy"): 0xB1,
    ("ldx", "imm"): 0xA2, ("ldx", "zp"): 0xA6, ("ldx", "zpy"): 0xB6,
    ("ldx", "abs"): 0xAE, ("ldx", "absy"): 0xBE,
    ("ldy", "imm"): 0xA0, ("ldy", "zp"): 0xA4, ("ldy", "zpx"): 0xB4,
    ("ldy", "abs"): 0xAC, ("ldy", "absx"): 0xBC,
    ("lsr", "zp"): 0x46, ("lsr", "zpx"): 0x56, ("lsr", "abs"): 0x4E,
    ("lsr", "absx"): 0x5E,
    ("ora", "imm"): 0x09, ("ora", "zp"): 0x05, ("ora", "zpx"): 0x15,
    ("ora", "abs"): 0x0D, ("ora", "absx"): 0x1D, ("ora", "absy"): 0x19,
    ("ora", "indx"): 0x01, ("ora", "indy"): 0x11,
    ("rol", "zp"): 0x26, ("rol", "zpx"): 0x36, ("rol", "abs"): 0x2E,
    ("rol", "absx"): 0x3E,
    ("ror", "zp"): 0x66, ("ror", "zpx"): 0x76, ("ror", "abs"): 0x6E,
    ("ror", "absx"): 0x7E,
    ("sbc", "imm"): 0xE9, ("sbc", "zp"): 0xE5, ("sbc", "zpx"): 0xF5,
    ("sbc", "abs"): 0xED, ("sbc", "absx"): 0xFD, ("sbc", "absy"): 0xF9,
    ("sbc", "indx"): 0xE1, ("sbc", "indy"): 0xF1,
    ("sta", "zp"): 0x85, ("sta", "zpx"): 0x95, ("sta", "abs"): 0x8D,
    ("sta", "absx"): 0x9D, ("sta", "absy"): 0x99, ("sta", "indx"): 0x81,
    ("sta", "indy"): 0x91,
    ("stx", "zp"): 0x86, ("stx", "zpy"): 0x96, ("stx", "abs"): 0x8E,
    ("sty", "zp"): 0x84, ("sty", "zpx"): 0x94, ("sty", "abs"): 0x8C,
}

MODE_SIZES = {
    "imp": 1, "acc": 1, "imm": 2, "zp": 2, "zpx": 2, "zpy": 2,
    "abs": 3, "absx": 3, "absy": 3, "ind": 3, "indx": 2, "indy": 2,
    "rel": 2,
}

_HEX = re.compile(r"^\$([0-9A-Fa-f]+)$")
_DEC = re.compile(r"^[0-9]+$")
_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DIRECTIVE = re.compile(r"^\.([A-Za-z]+)\s*(.*)$")


@dataclass(frozen=True)
class AssembledInstruction:
    address: int
    mnemonic: str
    mode: str
    bytes: bytes


@dataclass
class AssemblyResult:
    image: bytes
    origin: int
    end: int
    labels: dict[str, int] = field(default_factory=dict)
    instructions: list[AssembledInstruction] = field(default_factory=list)
    data_spans: list[tuple[int, int]] = field(default_factory=list)


def _parse_number(token: str) -> int:
    token = token.strip()
    match = _HEX.match(token)
    if match:
        return int(match.group(1), 16)
    if _DEC.match(token):
        return int(token, 10)
    raise AssemblyError(f"unrecognised numeric literal {token!r}")


def _evaluate(expression: str, labels: dict[str, int], required: bool) -> int:
    text = expression.strip()
    if not text:
        raise AssemblyError("empty expression")
    match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*([+-])\s*(\$[0-9A-Fa-f]+|[0-9]+)$", text)
    if match:
        name, operator, value = match.groups()
        if name not in labels:
            if required:
                raise AssemblyError(f"unresolved symbol {name!r}")
            return 0
        delta = _parse_number(value)
        return labels[name] + delta if operator == "+" else labels[name] - delta
    if _SYMBOL.match(text):
        if text not in labels:
            if required:
                raise AssemblyError(f"unresolved symbol {text!r}")
            return 0
        return labels[text]
    return _parse_number(text)


def _split_operand(operand: str) -> tuple[str, str]:
    text = operand.strip()
    if not text:
        return "imp", ""
    lowered = text.lower()
    if lowered == "a":
        return "acc", ""
    if lowered in ACCUMULATOR_OPS:
        return "acc", ""
    if text.startswith("#"):
        return "imm", text[1:].strip()
    if text.startswith("(") and text.endswith(")"):
        inner = text[1:-1].strip()
        if inner.lower().endswith(",x"):
            return "indx", inner[:-2].strip()
        if not inner:
            raise AssemblyError(f"malformed indirect operand {operand!r}")
        return "ind", inner
    if text.startswith("(") and text.lower().endswith("),y"):
        inner = text[1:-3].strip()
        if not inner:
            raise AssemblyError(f"malformed (zp),Y operand {operand!r}")
        return "indy", inner
    if "," in text:
        base, index = text.rsplit(",", 1)
        index = index.strip().lower()
        if index not in ("x", "y"):
            raise AssemblyError(f"unsupported index register in {operand!r}")
        base = base.strip()
        hex_match = _HEX.match(base)
        if hex_match and len(hex_match.group(1)) <= 2:
            return ("zpx" if index == "x" else "zpy"), base
        return ("absx" if index == "x" else "absy"), base
    hex_match = _HEX.match(text)
    if hex_match and len(hex_match.group(1)) <= 2:
        return "zp", text
    return "abs", text


def _strip_comment(line: str) -> str:
    result = []
    for char in line:
        if char == ";":
            break
        result.append(char)
    return "".join(result).rstrip()


def _tokenize_line(line: str) -> tuple[str | None, str, str]:
    text = _strip_comment(line).strip()
    if not text:
        return None, "", ""
    label = None
    if ":" in text:
        head, rest = text.split(":", 1)
        head = head.strip()
        if not _SYMBOL.match(head):
            raise AssemblyError(f"malformed label {head!r}")
        label = head
        text = rest.strip()
    if not text:
        return label, "", ""
    match = _DIRECTIVE.match(text)
    if match:
        return label, "." + match.group(1).lower(), match.group(2).strip()
    parts = text.split(None, 1)
    mnemonic = parts[0].lower()
    operand = parts[1].strip() if len(parts) > 1 else ""
    return label, mnemonic, operand


def assemble(source: str, *, origin: int | None = None) -> AssemblyResult:
    lines = source.splitlines()
    labels: dict[str, int] = {}
    program_origin = origin
    sizes: list[tuple[int, str, str, str]] = []
    address = origin if origin is not None else 0

    for line_number, line in enumerate(lines, start=1):
        try:
            label, mnemonic, operand = _tokenize_line(line)
        except AssemblyError as exc:
            raise AssemblyError(f"line {line_number}: {exc}") from exc
        if label is not None:
            if label in labels:
                raise AssemblyError(f"line {line_number}: duplicate label {label!r}")
            labels[label] = address
        if not mnemonic:
            continue
        if mnemonic == ".org":
            value = _parse_number(operand)
            if program_origin is None:
                program_origin = value
            elif value < program_origin:
                raise AssemblyError(
                    f"line {line_number}: .org 0x{value:04x} precedes origin 0x{program_origin:04x}")
            if value < address:
                raise AssemblyError(
                    f"line {line_number}: .org 0x{value:04x} overlaps emitted bytes "
                    f"(current address 0x{address:04x})")
            address = value
            continue
        if mnemonic == ".equ":
            parts = [part.strip() for part in operand.split(",", 1)]
            if len(parts) != 2 or not _SYMBOL.match(parts[0]):
                raise AssemblyError(
                    f"line {line_number}: .equ requires NAME, value")
            if parts[0] in labels:
                raise AssemblyError(
                    f"line {line_number}: duplicate symbol {parts[0]!r}")
            labels[parts[0]] = _parse_number(parts[1])
            continue
        if mnemonic == ".byte":
            items = [item.strip() for item in operand.split(",") if item.strip()]
            if not items:
                raise AssemblyError(f"line {line_number}: .byte requires values")
            sizes.append((address, ".byte", "raw", ",".join(items)))
            address += len(items)
            continue
        if mnemonic == ".word":
            items = [item.strip() for item in operand.split(",") if item.strip()]
            if not items:
                raise AssemblyError(f"line {line_number}: .word requires values")
            sizes.append((address, ".word", "raw", ",".join(items)))
            address += 2 * len(items)
            continue
        if mnemonic == ".res":
            items = [item.strip() for item in operand.split(",") if item.strip()]
            if not items:
                raise AssemblyError(f"line {line_number}: .res requires a count")
            count = _parse_number(items[0])
            sizes.append((address, ".res", "raw", ",".join(items)))
            address += count
            continue
        if mnemonic in IMPLIED:
            sizes.append((address, mnemonic, "imp", ""))
            address += MODE_SIZES["imp"]
            continue
        if mnemonic in ACCUMULATOR_OPS:
            mode, _rest = _split_operand(operand)
            if mode == "acc":
                sizes.append((address, mnemonic, "acc", ""))
                address += MODE_SIZES["acc"]
                continue
            if mode == "imp":
                raise AssemblyError(
                    f"line {line_number}: {mnemonic} requires an operand or 'a'")
        try:
            mode, rest = _split_operand(operand)
        except AssemblyError as exc:
            raise AssemblyError(f"line {line_number}: {exc}") from exc
        if mnemonic in BRANCH_OPS:
            sizes.append((address, mnemonic, "rel", operand))
            address += MODE_SIZES["rel"]
            continue
        if (mnemonic, mode) not in OPCODES:
            raise AssemblyError(
                f"line {line_number}: unsupported {mnemonic} addressing mode {mode} "
                f"({operand!r})")
        sizes.append((address, mnemonic, mode, rest))
        address += MODE_SIZES[mode]

    if program_origin is None:
        raise AssemblyError("no .org directive and no origin given")
    end = address
    image = bytearray(end - program_origin)
    instructions: list[AssembledInstruction] = []
    data_spans: list[tuple[int, int]] = []
    cursor = program_origin
    label_pass = dict(labels)

    for address, mnemonic, mode, operand in sizes:
        offset = address - program_origin
        if mnemonic == ".byte":
            items = [item.strip() for item in operand.split(",") if item.strip()]
            for index, item in enumerate(items):
                value = _evaluate(item, label_pass, required=True)
                if not 0 <= value <= 0xFF:
                    raise AssemblyError(f"byte value out of range at 0x{address:04x}")
                image[offset + index] = value
            data_spans.append((address, address + len(items)))
            cursor = address + len(items)
            continue
        if mnemonic == ".word":
            items = [item.strip() for item in operand.split(",") if item.strip()]
            for index, item in enumerate(items):
                value = _evaluate(item, label_pass, required=True)
                if not 0 <= value <= 0xFFFF:
                    raise AssemblyError(f"word value out of range at 0x{address:04x}")
                image[offset + 2 * index] = value & 0xFF
                image[offset + 2 * index + 1] = (value >> 8) & 0xFF
            data_spans.append((address, address + 2 * len(items)))
            cursor = address + 2 * len(items)
            continue
        if mnemonic == ".res":
            items = [item.strip() for item in operand.split(",") if item.strip()]
            count = _parse_number(items[0])
            fill = _parse_number(items[1]) & 0xFF if len(items) > 1 else 0
            for index in range(count):
                image[offset + index] = fill
            data_spans.append((address, address + count))
            cursor = address + count
            continue
        if mnemonic in IMPLIED:
            image[offset] = IMPLIED[mnemonic]
            instructions.append(AssembledInstruction(address, mnemonic, "imp", bytes([IMPLIED[mnemonic]])))
            cursor = address + 1
            continue
        if mode == "acc":
            image[offset] = ACCUMULATOR[mnemonic]
            instructions.append(AssembledInstruction(address, mnemonic, "acc", bytes([ACCUMULATOR[mnemonic]])))
            cursor = address + 1
            continue
        if mnemonic in BRANCH_OPS:
            target = _evaluate(operand, label_pass, required=True)
            delta = target - (address + 2)
            if not -128 <= delta <= 127:
                raise AssemblyError(
                    f"branch out of range at 0x{address:04x}: target 0x{target:04x}")
            opcode = OPCODES[(mnemonic, "rel")]
            image[offset] = opcode
            image[offset + 1] = delta & 0xFF
            instructions.append(AssembledInstruction(
                address, mnemonic, "rel", bytes([opcode, delta & 0xFF])))
            cursor = address + 2
            continue
        opcode = OPCODES[(mnemonic, mode)]
        if mode == "imp":
            payload = b""
        elif mode == "imm":
            immediate = operand.strip()
            if immediate.startswith("<"):
                value = _evaluate(immediate[1:], label_pass, required=True) & 0xFF
            elif immediate.startswith(">"):
                value = (_evaluate(immediate[1:], label_pass, required=True) >> 8) & 0xFF
            else:
                value = _evaluate(immediate, label_pass, required=True)
            if not 0 <= value <= 0xFF:
                raise AssemblyError(f"immediate out of range at 0x{address:04x}")
            payload = bytes([value])
        elif mode in ("zp", "zpx", "zpy", "indx", "indy"):
            value = _evaluate(operand, label_pass, required=True)
            if not 0 <= value <= 0xFF:
                raise AssemblyError(f"zero-page value out of range at 0x{address:04x}")
            payload = bytes([value])
        elif mode in ("abs", "absx", "absy", "ind"):
            value = _evaluate(operand, label_pass, required=True)
            if not 0 <= value <= 0xFFFF:
                raise AssemblyError(f"absolute value out of range at 0x{address:04x}")
            payload = bytes([value & 0xFF, (value >> 8) & 0xFF])
        else:
            raise AssemblyError(f"unhandled mode {mode!r}")
        image[offset] = opcode
        image[offset + 1:offset + 1 + len(payload)] = payload
        instructions.append(AssembledInstruction(
            address, mnemonic, mode, bytes([opcode]) + payload))
        cursor = address + 1 + len(payload)

    if cursor != end:
        raise AssemblyError(f"internal size mismatch: cursor 0x{cursor:04x} end 0x{end:04x}")
    return AssemblyResult(
        image=bytes(image),
        origin=program_origin,
        end=end,
        labels=dict(sorted(labels.items())),
        instructions=instructions,
        data_spans=data_spans,
    )


__all__ = [
    "ACCUMULATOR_OPS",
    "AssemblyError",
    "AssemblyResult",
    "AssembledInstruction",
    "IMPLIED",
    "MODE_SIZES",
    "OPCODES",
    "assemble",
]
