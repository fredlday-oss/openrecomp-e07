#!/usr/bin/env python3
"""OpenRecomp Phase-3 MIPS32 decode + classification V1 (P3-03).

Additive, fail-closed decode/classification layer for the audited CoreMark
image.  It exists because the frozen bounded adapter (``adapters.mips32``) is
hash-pinned by the Phase-1/Phase-2 manifests and by the P3-01 inventory gate:
extending its ``decode()`` behaviour would change the frozen P3-01 unsupported
inventory and break the frozen regressions.  This module therefore keeps the
adapter untouched and adds a *classification* layer on top:

* words the bounded adapter decodes are ``SUPPORTED`` (semantics and all);
* the inventory-driven P3-01 classes (``movz``, ``movn``, ``mul``, ``div``,
  ``divu``, the trap family incl. ``teq``, ``swl``, ``swr``, ``jalr``) are
  decoded here with correct MIPS32 encodings and operands but are classified
  ``RECOGNIZED_UNSUPPORTED``: decode support never implies semantic support;
* encodings in a known field space that the architecture leaves unassigned are
  ``RESERVED_ENCODING``; anything this table does not name is
  ``UNKNOWN_ENCODING``.  Both are ``INVALID`` for reporting and are never
  interpreted as instructions.

The table intentionally covers the audited MIPS32 integer subset and the P3-01
classes only.  An unnamed encoding is fail-closed ``UNKNOWN_ENCODING`` rather
than guessed; arbitrary-MIPS32 coverage is explicitly not claimed.

This module is OpenRecomp-original, standard-library only, and contains no
console assets, proprietary data or copied tables.
"""
from __future__ import annotations

from typing import Any

from adapters.mips32 import DecodeError as BoundedDecodeError
from adapters.mips32 import decode as bounded_decode

MASK32 = 0xFFFFFFFF

CLASS_SUPPORTED = "SUPPORTED"
CLASS_RECOGNIZED_UNSUPPORTED = "RECOGNIZED_UNSUPPORTED"
CLASS_RESERVED = "RESERVED_ENCODING"
CLASS_UNKNOWN = "UNKNOWN_ENCODING"
CLASS_INVALID = (CLASS_RESERVED, CLASS_UNKNOWN)

SEMANTICS_SUPPORTED = "SUPPORTED"
SEMANTICS_UNSUPPORTED = "UNSUPPORTED"
SEMANTICS_UNDEFINED = "UNDEFINED"

TERM_CONDITIONAL_BRANCH = "conditional-branch"
TERM_JUMP = "jump"
TERM_DIRECT_CALL = "direct-call"
TERM_RETURN = "return"
TERM_INDIRECT_CALL = "indirect-call"
TERM_INDIRECT_JUMP = "indirect-jump"
TERM_UNSUPPORTED_CONTROL = "unsupported-control-transfer"
TERM_EXTERNAL_TRAP = "external-trap"

BRANCH_OPS = frozenset({"beq", "bne", "blez", "bgtz", "bltz", "bgez"})
TRAP_SPECIAL = {0x30: "tge", 0x31: "tgeu", 0x32: "tlt", 0x33: "tltu", 0x34: "teq", 0x36: "tne"}
SPECIAL_TRAPS = frozenset(TRAP_SPECIAL)
TRAP_OPS = frozenset(TRAP_SPECIAL.values())
SPECIAL_SYSCALL = 0x0C
SPECIAL_BREAK = 0x0D

# MIPS32 SPECIAL funct assignments relevant to this audited profile.  Values
# outside this set are reserved for the architecture encoding space.
SPECIAL_ASSIGNED = frozenset({
    0x00, 0x01, 0x02, 0x03, 0x04, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B,
    0x0C, 0x0D, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x18, 0x19, 0x1A, 0x1B,
    0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x2A, 0x2B,
    0x30, 0x31, 0x32, 0x33, 0x34, 0x36,
})
SPECIAL_ASSIGNED_UNSUPPORTED = {
    0x01: "movf/movt", 0x0F: "sync", 0x11: "mthi", 0x13: "mtlo",
    0x20: "add", 0x22: "sub",
}

SPECIAL2_ASSIGNED = frozenset({0x00, 0x01, 0x02, 0x04, 0x05, 0x20, 0x21})
SPECIAL2_ASSIGNED_UNSUPPORTED = {
    0x00: "madd", 0x01: "maddu", 0x04: "msub", 0x05: "msubu",
    0x20: "clz", 0x21: "clo",
}

# REGIMM rt assignments.  Assigned but bounded-adapter-unsupported forms are
# named here; unassigned rt values are reserved encodings.
REGIMM_ASSIGNED = {
    0x00: "bltz", 0x01: "bgez", 0x02: "bltzl", 0x03: "bgezl",
    0x08: "tgei", 0x09: "tgeiu", 0x0A: "tlti", 0x0B: "tltiu",
    0x0C: "teqi", 0x0E: "tnei", 0x10: "bltzal", 0x11: "bgezal",
    0x12: "bltzall", 0x13: "bgezall", 0x1F: "synci",
}
REGIMM_CONTROL_FLOW = {
    0x02: "branch-likely", 0x03: "branch-likely",
    0x10: "branch-and-link", 0x11: "branch-and-link",
    0x12: "branch-likely-and-link", 0x13: "branch-likely-and-link",
}
REGIMM_CONTROL_NAMES = frozenset({
    "bltzl", "bgezl", "bltzal", "bgezal", "bltzall", "bgezall",
})
REGIMM_LINK_NAMES = frozenset({"bltzal", "bgezal", "bltzall", "bgezall"})
REGIMM_TRAPS = frozenset({0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0E})
REGIMM_TRAP_NAMES = frozenset({"tgei", "tgeiu", "tlti", "tltiu", "teqi", "tnei"})


class DecodeClassificationError(ValueError):
    """Fail-closed classification rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _sign16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _operands(instruction: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in instruction.items()
        if key not in {"address", "word", "op"}
    }


def _record(
    address: int,
    word: int,
    decode_class: str,
    op: str | None,
    semantics: str,
    operands: dict[str, Any] | None = None,
    reason: str | None = None,
    control_flow: bool = False,
    terminator: str | None = None,
    delay_slot: bool = False,
    target: int | None = None,
    link: bool = False,
    trap: bool = False,
    exception_transfer: bool = False,
) -> dict[str, Any]:
    return {
        "address": address,
        "word": word,
        "decode_class": decode_class,
        "op": op,
        "semantics": semantics,
        "operands": operands if operands is not None else {},
        "reason": reason,
        "control_flow": control_flow,
        "terminator": terminator,
        "delay_slot": delay_slot,
        "target": target,
        "link": link,
        "trap": trap,
        "exception_transfer": exception_transfer,
    }


def _branch_target(address: int, imm_s: int) -> int:
    return (address + 4 + (imm_s << 2)) & MASK32


def _decode_extension(address: int, word: int) -> dict[str, Any] | None:
    opcode = (word >> 26) & 0x3F
    rs = (word >> 21) & 0x1F
    rt = (word >> 16) & 0x1F
    rd = (word >> 11) & 0x1F
    shamt = (word >> 6) & 0x1F
    funct = word & 0x3F
    imm_u = word & 0xFFFF
    imm_s = _sign16(imm_u)

    if opcode == 0:
        if funct in (0x0A, 0x0B) and shamt == 0:
            return {"op": "movz" if funct == 0x0A else "movn", "rs": rs, "rt": rt, "rd": rd}
        if funct == 0x09 and rt == 0 and shamt == 0:
            instruction = {"op": "jalr", "rs": rs, "rd": rd}
            return instruction
        if funct in (0x1A, 0x1B) and rd == 0 and shamt == 0:
            return {"op": "div" if funct == 0x1A else "divu", "rs": rs, "rt": rt}
        if funct in SPECIAL_TRAPS:
            return {"op": TRAP_SPECIAL[funct], "rs": rs, "rt": rt, "code": (word >> 6) & 0x3FF}
        if funct in (SPECIAL_SYSCALL, SPECIAL_BREAK):
            return {"op": "syscall" if funct == SPECIAL_SYSCALL else "break",
                    "code": (word >> 6) & 0xFFFFF}
        if funct in SPECIAL_ASSIGNED_UNSUPPORTED:
            return {"op": SPECIAL_ASSIGNED_UNSUPPORTED[funct], "rs": rs, "rt": rt, "rd": rd, "shamt": shamt}
        return None

    if opcode == 0x1C and funct == 0x02 and shamt == 0:
        return {"op": "mul", "rs": rs, "rt": rt, "rd": rd}
    if opcode == 0x1C and funct in SPECIAL2_ASSIGNED_UNSUPPORTED:
        return {"op": SPECIAL2_ASSIGNED_UNSUPPORTED[funct], "raw_encoding_only": True}
    if opcode == 0x2A:
        return {"op": "swl", "rs": rs, "rt": rt, "imm": imm_s}
    if opcode == 0x2E:
        return {"op": "swr", "rs": rs, "rt": rt, "imm": imm_s}
    if opcode == 0x22:
        return {"op": "lwl", "rs": rs, "rt": rt, "imm": imm_s}
    if opcode == 0x26:
        return {"op": "lwr", "rs": rs, "rt": rt, "imm": imm_s}
    if opcode == 0x08:
        return {"op": "addi", "rs": rs, "rt": rt, "imm": imm_s}

    if opcode == 0x01:
        name = REGIMM_ASSIGNED.get(rt)
        if name is None or rt in (0x00, 0x01):
            return None
        operands: dict[str, Any] = {"rs": rs}
        if rt in REGIMM_CONTROL_FLOW or rt in REGIMM_TRAPS:
            operands["target"] = _branch_target(address, imm_s)
        return {"op": name, "imm": imm_s, **operands}
    return None


def _classify_reserved(word: int) -> dict[str, Any] | None:
    opcode = (word >> 26) & 0x3F
    rt = (word >> 16) & 0x1F
    funct = word & 0x3F
    if opcode == 0 and funct not in SPECIAL_ASSIGNED:
        return {"reason": f"reserved SPECIAL funct 0x{funct:02x}",
                "result": {"funct": funct}}
    if opcode == 0x1C and funct not in SPECIAL2_ASSIGNED:
        return {"reason": f"reserved SPECIAL2 funct 0x{funct:02x}",
                "result": {"funct": funct}}
    if opcode == 0x01 and rt not in REGIMM_ASSIGNED:
        return {"reason": f"reserved REGIMM rt 0x{rt:02x}",
                "result": {"rt": rt}}
    return None


def _classify_extension(address: int, word: int, instruction: dict[str, Any]) -> dict[str, Any]:
    op = instruction["op"]
    if op in BRANCH_OPS:
        raise AssertionError("bounded adapter must own branch decoding")
    if op in ("movz", "movn"):
        return _record(address, word, CLASS_RECOGNIZED_UNSUPPORTED, op,
                       SEMANTICS_UNSUPPORTED, _operands(instruction))
    if op in ("div", "divu"):
        return _record(address, word, CLASS_RECOGNIZED_UNSUPPORTED, op,
                       SEMANTICS_UNSUPPORTED, _operands(instruction),
                       exception_transfer=True)
    if op in TRAP_OPS:
        return _record(address, word, CLASS_RECOGNIZED_UNSUPPORTED, op,
                       SEMANTICS_UNSUPPORTED, _operands(instruction),
                       trap=True, exception_transfer=True)
    if op in ("syscall", "break"):
        return _record(address, word, CLASS_RECOGNIZED_UNSUPPORTED, op,
                       SEMANTICS_UNSUPPORTED, _operands(instruction),
                       control_flow=True, terminator=TERM_EXTERNAL_TRAP,
                       trap=True, exception_transfer=True)
    if op == "jalr":
        link = instruction["rd"] == 31
        return _record(address, word, CLASS_RECOGNIZED_UNSUPPORTED, op,
                       SEMANTICS_UNSUPPORTED, _operands(instruction),
                       control_flow=True,
                       terminator=TERM_INDIRECT_CALL if link else TERM_INDIRECT_JUMP,
                       delay_slot=True, link=link)
    if op in ("swl", "swr", "lwl", "lwr", "addi", "mul"):
        return _record(address, word, CLASS_RECOGNIZED_UNSUPPORTED, op,
                       SEMANTICS_UNSUPPORTED, _operands(instruction))
    if op in SPECIAL2_ASSIGNED_UNSUPPORTED.values():
        return _record(address, word, CLASS_RECOGNIZED_UNSUPPORTED, op,
                       SEMANTICS_UNSUPPORTED, _operands(instruction))
    if op in SPECIAL_ASSIGNED_UNSUPPORTED.values():
        return _record(address, word, CLASS_RECOGNIZED_UNSUPPORTED, op,
                       SEMANTICS_UNSUPPORTED, _operands(instruction))
    if op in REGIMM_ASSIGNED.values():
        terminator = None
        control_flow = False
        delay_slot = False
        link = False
        if op in REGIMM_CONTROL_NAMES:
            control_flow = True
            terminator = TERM_UNSUPPORTED_CONTROL
            delay_slot = True
            link = op in REGIMM_LINK_NAMES
        trap = op in REGIMM_TRAP_NAMES
        return _record(address, word, CLASS_RECOGNIZED_UNSUPPORTED, op,
                       SEMANTICS_UNSUPPORTED, _operands(instruction),
                       control_flow=control_flow, terminator=terminator,
                       delay_slot=delay_slot, link=link, trap=trap,
                       exception_transfer=trap)
    raise AssertionError(f"unhandled extension instruction {op}")


def classify(address: int, word: int) -> dict[str, Any]:
    """Classify one 32-bit word at one 4-byte-aligned address (fail closed)."""
    if not isinstance(address, int) or address < 0 or address > MASK32 or address & 3:
        raise DecodeClassificationError(
            "INVALID_ADDRESS", f"address={address!r}")
    if not isinstance(word, int) or word < 0 or word > MASK32:
        raise DecodeClassificationError("INVALID_WORD", f"word={word!r}")

    try:
        instruction = bounded_decode(address, word)
    except BoundedDecodeError:
        instruction = None

    if instruction is not None:
        op = instruction["op"]
        control_flow = False
        terminator = None
        delay_slot = False
        target = None
        link = False
        if op in BRANCH_OPS:
            control_flow = True
            terminator = TERM_CONDITIONAL_BRANCH
            delay_slot = True
            target = instruction["target"]
        elif op == "j":
            control_flow = True
            terminator = TERM_JUMP
            delay_slot = True
            target = instruction["target"]
        elif op == "jal":
            control_flow = True
            terminator = TERM_DIRECT_CALL
            delay_slot = True
            target = instruction["target"]
            link = True
        elif op == "jr":
            control_flow = True
            terminator = TERM_RETURN if instruction["rs"] == 31 else TERM_INDIRECT_JUMP
            delay_slot = True
        return _record(address, word, CLASS_SUPPORTED, op, SEMANTICS_SUPPORTED,
                       _operands(instruction), control_flow=control_flow,
                       terminator=terminator, delay_slot=delay_slot,
                       target=target, link=link)

    extension = _decode_extension(address, word)
    if extension is not None:
        return _classify_extension(address, word, extension)

    reserved = _classify_reserved(word)
    encoding = {
        "opcode": (word >> 26) & 0x3F,
        "rs": (word >> 21) & 0x1F,
        "rt": (word >> 16) & 0x1F,
        "rd": (word >> 11) & 0x1F,
        "shamt": (word >> 6) & 0x1F,
        "funct": word & 0x3F,
    }
    if reserved is not None:
        return _record(address, word, CLASS_RESERVED, None, SEMANTICS_UNDEFINED,
                       encoding, reason=reserved["reason"])

    return _record(address, word, CLASS_UNKNOWN, None, SEMANTICS_UNDEFINED,
                   encoding, reason="encoding outside the classified table")


def semantics_supported(record: dict[str, Any]) -> bool:
    return record["semantics"] == SEMANTICS_SUPPORTED


def is_invalid(record: dict[str, Any]) -> bool:
    return record["decode_class"] in CLASS_INVALID
