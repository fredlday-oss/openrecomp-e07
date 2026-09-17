#!/usr/bin/env python3
"""OpenRecomp Phase-3 MIPS32 reachable-instruction semantics V1 (P3-04).

Additive, fail-closed execution semantics for the bounded instruction classes
that P3-01 inventory and P3-03 frontier analysis identified as
``RECOGNIZED_UNSUPPORTED`` on the audited CoreMark image:

    movz, movn, mul, divu, teq, swl, swr, jalr

Relationship to the frozen layers
---------------------------------

* ``adapters.mips32`` (hash-pinned by the Phase-1/Phase-2 manifests) keeps
  owning its own decode + semantics for the instructions it already supports;
  this module never changes or mirrors that contract.
* ``p3_decode_mips32_v1`` keeps owning decode + classification.  This module
  adds *semantics* only and deliberately does not touch the classification
  records, so "decodes" can never silently become "executes correctly".
* ``p3_code_frontier_v1`` keeps owning control-flow recovery.  ``jalr`` is a
  bounded-class semantic here (link register + dynamic target), but its static
  target is never resolved: the P3-03 frontier keeps the site unresolved.

Architecture rules implemented
------------------------------

* 32-bit register file, little-endian memory, HI/LO as separate state.
* ``$zero`` writes are discarded (no architected write to register 0).
* ``movz``/``movn`` write the destination only when the condition holds and
  leave it untouched otherwise.
* ``mul`` returns the low 32 bits of the signed 32x32 product.  MIPS32 leaves
  HI/LO UNPREDICTABLE after ``mul``; this model therefore marks HI/LO
  undefined (instead of inventing a value) and refuses to read them until a
  defining operation writes them.
* ``divu`` is unsigned; LO = quotient, HI = remainder.  MIPS32 leaves the
  result UNPREDICTABLE when the divisor is zero, so that case fails closed.
* ``teq`` raises the architectural Trap condition when its operands are
  equal.  OpenRecomp does not model exception delivery, so a taken trap fails
  closed with the encoded trap code preserved for the frontier record.
* ``swl``/``swr`` store the partial word within the single aligned word
  selected by the effective address, exactly as MIPS32 defines in
  little-endian mode; they never take an alignment exception.
* ``jalr`` latches the target from ``GPR[rs]`` and links to the instruction
  after the delay slot (``address + 8``); an unaligned target is
  architecturally UNPREDICTABLE and fails closed.

The module is OpenRecomp-original, standard-library only, contains no console
assets or copied tables, and is deterministic: no host state, no randomness.
"""
from __future__ import annotations

from typing import Any

MASK32 = 0xFFFFFFFF

SEMANTICS_IMPLEMENTED = "IMPLEMENTED"
SEMANTICS_UNSUPPORTED = "UNSUPPORTED"

# Stable fail-closed rejection codes.
ERROR_UNSUPPORTED_INSTRUCTION = "UNSUPPORTED_INSTRUCTION"
ERROR_INVALID_RECORD = "INVALID_RECORD"
ERROR_INVALID_STATE = "INVALID_STATE"
ERROR_INVALID_MEMORY = "INVALID_MEMORY"
ERROR_MEMORY_FAULT = "MEMORY_FAULT"
ERROR_WRITE_PROTECTED = "WRITE_PROTECTED"
ERROR_DIVIDE_BY_ZERO = "DIVIDE_BY_ZERO"
ERROR_TRAP_TAKEN = "TRAP_TAKEN"
ERROR_UNALIGNED_TARGET = "UNALIGNED_TARGET"
ERROR_HI_LO_UNPREDICTABLE = "HI_LO_UNPREDICTABLE"
ERROR_ENDIANNESS_UNSUPPORTED = "ENDIANNESS_UNSUPPORTED"

IMPLEMENTED_OPS = ("divu", "jalr", "movn", "movz", "mul", "swl", "swr", "teq")
IMPLEMENTED_OP_SET = frozenset(IMPLEMENTED_OPS)

HI_LO_DEFINED = "DEFINED"
HI_LO_UNPREDICTABLE = "UNPREDICTABLE"
HI_LO_UNCHANGED = "UNCHANGED"

ENDIANNESS_LITTLE = "little"


class SemanticsError(ValueError):
    """Fail-closed semantics rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def sign16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def signed32(value: int) -> int:
    value &= MASK32
    return value - 0x100000000 if value & 0x80000000 else value


class MachineState:
    """MIPS32 integer state: 32 GPRs plus HI/LO.

    ``hi_lo_defined`` starts true (reset/undefined-reference state is a caller
    decision); ``mul`` sets it false because MIPS32 leaves HI/LO UNPREDICTABLE
    there, and ``read_hi``/``read_lo`` refuse to invent a value while it is
    false.  ``divu`` defines both HI and LO and therefore sets it true.
    """

    def __init__(
        self,
        registers: list[int] | tuple[int, ...] | None = None,
        hi: int = 0,
        lo: int = 0,
        hi_lo_defined: bool = True,
    ) -> None:
        if registers is None:
            registers = [0] * 32
        if len(registers) != 32:
            raise SemanticsError(ERROR_INVALID_STATE, "register file must have 32 entries")
        self.registers = [value & MASK32 for value in registers]
        self.registers[0] = 0
        self.hi = hi & MASK32
        self.lo = lo & MASK32
        self.hi_lo_defined = bool(hi_lo_defined)

    def read_reg(self, index: int) -> int:
        if not isinstance(index, int) or not 0 <= index < 32:
            raise SemanticsError(ERROR_INVALID_STATE, f"register index {index!r}")
        return 0 if index == 0 else self.registers[index]

    def write_reg(self, index: int, value: int) -> bool:
        if not isinstance(index, int) or not 0 <= index < 32:
            raise SemanticsError(ERROR_INVALID_STATE, f"register index {index!r}")
        if index == 0:
            return False
        self.registers[index] = value & MASK32
        return True

    def read_hi(self) -> int:
        if not self.hi_lo_defined:
            raise SemanticsError(ERROR_HI_LO_UNPREDICTABLE, "HI read while UNPREDICTABLE")
        return self.hi

    def read_lo(self) -> int:
        if not self.hi_lo_defined:
            raise SemanticsError(ERROR_HI_LO_UNPREDICTABLE, "LO read while UNPREDICTABLE")
        return self.lo

    def write_hi(self, value: int) -> None:
        self.hi = value & MASK32
        self.hi_lo_defined = True

    def write_lo(self, value: int) -> None:
        self.lo = value & MASK32
        self.hi_lo_defined = True

    def mark_hi_lo_unpredictable(self) -> None:
        self.hi_lo_defined = False

    def snapshot(self) -> dict[str, Any]:
        return {
            "registers": [0] + list(self.registers[1:]),
            "hi": self.hi,
            "lo": self.lo,
            "hi_lo_defined": self.hi_lo_defined,
        }


class BoundedMemory:
    """Deterministic little-endian byte memory with explicit bounds.

    Used for reference vectors and for exercising the audited image windows.
    Bounds and write permission fail closed with stable codes.
    """

    def __init__(
        self,
        base: int = 0,
        size: int = 0x10000,
        writable: bool = True,
        initial: bytes | None = None,
    ) -> None:
        if size < 0 or base < 0 or base + size > 0x100000000:
            raise SemanticsError(ERROR_INVALID_MEMORY, f"base=0x{base:x} size={size}")
        self.base = base
        self.size = size
        self.writable = bool(writable)
        if initial is None:
            initial = bytes(size)
        if len(initial) != size:
            raise SemanticsError(ERROR_INVALID_MEMORY, "initial size mismatch")
        self.bytes = bytearray(initial)

    def _check(self, address: int, size: int) -> int:
        if not isinstance(address, int) or address < 0 or address > MASK32:
            raise SemanticsError(ERROR_MEMORY_FAULT, f"address={address!r}")
        if address < self.base or address + size > self.base + self.size:
            raise SemanticsError(ERROR_MEMORY_FAULT, f"address=0x{address:08x} size={size}")
        return address - self.base

    def read_u32(self, address: int) -> int:
        offset = self._check(address, 4)
        return int.from_bytes(self.bytes[offset:offset + 4], "little")

    def write_u32(self, address: int, value: int) -> None:
        offset = self._check(address, 4)
        if not self.writable:
            raise SemanticsError(ERROR_WRITE_PROTECTED, f"address=0x{address:08x}")
        self.bytes[offset:offset + 4] = (value & MASK32).to_bytes(4, "little")

    def load(self, address: int, payload: bytes) -> None:
        offset = self._check(address, len(payload))
        if not self.writable:
            raise SemanticsError(ERROR_WRITE_PROTECTED, f"address=0x{address:08x}")
        self.bytes[offset:offset + len(payload)] = payload

    def window(self, address: int, size: int) -> bytes:
        offset = self._check(address, size)
        return bytes(self.bytes[offset:offset + size])


def _operand(record: dict[str, Any], name: str) -> int:
    operands = record.get("operands")
    if not isinstance(operands, dict) or name not in operands:
        raise SemanticsError(ERROR_INVALID_RECORD, f"missing operand {name!r}")
    value = operands[name]
    if not isinstance(value, int):
        raise SemanticsError(ERROR_INVALID_RECORD, f"operand {name!r} is not an integer")
    return value


def _require_bounded_record(record: dict[str, Any]) -> str:
    from p3_decode_mips32_v1 import CLASS_RECOGNIZED_UNSUPPORTED

    if not isinstance(record, dict):
        raise SemanticsError(ERROR_INVALID_RECORD, "record is not a mapping")
    op = record.get("op")
    if record.get("decode_class") != CLASS_RECOGNIZED_UNSUPPORTED:
        raise SemanticsError(
            ERROR_INVALID_RECORD,
            f"op={op!r} class={record.get('decode_class')!r} is not a bounded-class record")
    if op not in IMPLEMENTED_OP_SET:
        raise SemanticsError(ERROR_UNSUPPORTED_INSTRUCTION, f"op={op!r}")
    return op


def semantics_status(op: str | None) -> str:
    """Semantic support status for one decoded mnemonic (fail-closed)."""
    return SEMANTICS_IMPLEMENTED if op in IMPLEMENTED_OP_SET else SEMANTICS_UNSUPPORTED


def implementations() -> dict[str, dict[str, Any]]:
    """Canonical per-class implementation table (deterministic copy)."""
    return {
        "movz": {
            "class": "conditional move",
            "encoding": "SPECIAL funct 0x0a, shamt 0 (SPECIAL opcode 0x00)",
            "form": "movz rd, rs, rt",
            "semantics": "if GPR[rt] == 0 then GPR[rd] = GPR[rs] else unchanged",
            "registers": "rd write-only, rs/rt read; rd=0 write discarded",
            "hi_lo_effect": HI_LO_UNCHANGED,
            "memory_effect": "none",
            "control_effect": "fallthrough",
            "fail_closed": [],
            "edge_cases": [
                "condition on the full 32-bit rt value",
                "no write when rt != 0",
                "rd = 0 discards the write architected",
            ],
        },
        "movn": {
            "class": "conditional move",
            "encoding": "SPECIAL funct 0x0b, shamt 0 (SPECIAL opcode 0x00)",
            "form": "movn rd, rs, rt",
            "semantics": "if GPR[rt] != 0 then GPR[rd] = GPR[rs] else unchanged",
            "registers": "rd write-only, rs/rt read; rd=0 write discarded",
            "hi_lo_effect": HI_LO_UNCHANGED,
            "memory_effect": "none",
            "control_effect": "fallthrough",
            "fail_closed": [],
            "edge_cases": [
                "condition on the full 32-bit rt value",
                "no write when rt == 0",
                "rd = 0 discards the write architected",
            ],
        },
        "mul": {
            "class": "integer multiply (SPECIAL2)",
            "encoding": "SPECIAL2 opcode 0x1c, funct 0x02, shamt 0",
            "form": "mul rd, rs, rt",
            "semantics": (
                "signed(GPR[rs]) * signed(GPR[rt]) modulo 2**32 placed in GPR[rd]"
            ),
            "registers": "rd write-only, rs/rt read; rd=0 write discarded",
            "hi_lo_effect": HI_LO_UNPREDICTABLE,
            "memory_effect": "none",
            "control_effect": "fallthrough",
            "fail_closed": [
                "reading HI/LO before a defining operation fails closed with "
                "HI_LO_UNPREDICTABLE",
            ],
            "architectural_note": (
                "MIPS32 leaves HI/LO UNPREDICTABLE after MUL; this model does not "
                "invent a value, marks them undefined and never depends on them"
            ),
            "edge_cases": [
                "32x32 signed product truncated to the low 32 bits",
                "result is not the same as the SHIFT/MULT HI/LO pair",
                "rd = 0 discards the write architected",
            ],
        },
        "divu": {
            "class": "unsigned divide",
            "encoding": "SPECIAL funct 0x1b, rd 0, shamt 0 (SPECIAL opcode 0x00)",
            "form": "divu rs, rt",
            "semantics": "LO = GPR[rs] // GPR[rt]; HI = GPR[rs] % GPR[rt] (unsigned)",
            "registers": "no GPR write; rs/rt read",
            "hi_lo_effect": HI_LO_DEFINED,
            "memory_effect": "none",
            "control_effect": "fallthrough",
            "fail_closed": [
                "divisor zero is architecturally UNPREDICTABLE and fails closed "
                "with DIVIDE_BY_ZERO before any HI/LO write",
            ],
            "edge_cases": [
                "unsigned interpretation of both operands",
                "quotient/remainder pair defines both HI and LO",
            ],
        },
        "teq": {
            "class": "trap-if-equal",
            "encoding": "SPECIAL funct 0x34 (code in bits 15:6)",
            "form": "teq rs, rt",
            "semantics": "if GPR[rs] == GPR[rt] then Trap exception else no effect",
            "registers": "rs/rt read; no GPR write",
            "hi_lo_effect": HI_LO_UNCHANGED,
            "memory_effect": "none",
            "control_effect": "fallthrough when not taken",
            "fail_closed": [
                "taken trap fails closed with TRAP_TAKEN (exception delivery is not "
                "modelled); the encoded trap code is preserved",
            ],
            "edge_cases": [
                "equality on full 32-bit values",
                "non-taken trap has no architected effect",
            ],
        },
        "swl": {
            "class": "store word left (partial store)",
            "encoding": "opcode 0x2a",
            "form": "swl rt, offset(base)",
            "semantics": (
                "little-endian partial store into the aligned word at "
                "(GPR[base] + sign_extend(offset)) & ~3"
            ),
            "registers": "rt read; rs read; no GPR write",
            "hi_lo_effect": HI_LO_UNCHANGED,
            "memory_effect": "1-4 bytes of the aligned word, never crossing word boundaries",
            "control_effect": "fallthrough",
            "fail_closed": [
                "unaligned or unmapped aligned word fails closed with MEMORY_FAULT",
                "read-only target fails closed with WRITE_PROTECTED",
                "big-endian targets fail closed with ENDIANNESS_UNSUPPORTED",
            ],
            "edge_cases": [
                "no alignment exception for the unaligned effective address",
                "effective address wraps modulo 2**32 before the alignment mask",
                "byte count selected by the two low address bits",
            ],
        },
        "swr": {
            "class": "store word right (partial store)",
            "encoding": "opcode 0x2e",
            "form": "swr rt, offset(base)",
            "semantics": (
                "little-endian partial store into the aligned word at "
                "(GPR[base] + sign_extend(offset)) & ~3"
            ),
            "registers": "rt read; rs read; no GPR write",
            "hi_lo_effect": HI_LO_UNCHANGED,
            "memory_effect": "1-4 bytes of the aligned word, never crossing word boundaries",
            "control_effect": "fallthrough",
            "fail_closed": [
                "unaligned or unmapped aligned word fails closed with MEMORY_FAULT",
                "read-only target fails closed with WRITE_PROTECTED",
                "big-endian targets fail closed with ENDIANNESS_UNSUPPORTED",
            ],
            "edge_cases": [
                "no alignment exception for the unaligned effective address",
                "effective address wraps modulo 2**32 before the alignment mask",
                "byte count selected by the two low address bits",
            ],
        },
        "jalr": {
            "class": "jump and link register (indirect call)",
            "encoding": "SPECIAL funct 0x09, rt 0",
            "form": "jalr rd, rs",
            "semantics": (
                "target = GPR[rs] latched before the delay slot; "
                "if rd != 0 then GPR[rd] = address + 8; PC = target"
            ),
            "registers": "rd write-only, rs read; rd=0 stores no link",
            "hi_lo_effect": HI_LO_UNCHANGED,
            "memory_effect": "none",
            "control_effect": "indirect transfer with one delay slot",
            "fail_closed": [
                "unaligned target fails closed with UNALIGNED_TARGET",
                "the static target is never resolved by this module",
            ],
            "edge_cases": [
                "link value is the instruction after the delay slot (address + 8)",
                "target is latched before the delay slot executes",
                "rd = rs keeps the pre-write register value as the target",
            ],
        },
    }


def execute(
    record: dict[str, Any],
    state: MachineState,
    memory: Any,
    endianness: str = ENDIANNESS_LITTLE,
) -> dict[str, Any]:
    """Execute one bounded-class instruction; return a canonical effect record.

    Fails closed with :class:`SemanticsError` for every unsupported,
    malformed, unpredictable or unmodelled condition.  No host state is used.
    """
    if not isinstance(state, MachineState):
        raise SemanticsError(ERROR_INVALID_STATE, "state is not a MachineState")
    op = _require_bounded_record(record)
    if endianness != ENDIANNESS_LITTLE:
        raise SemanticsError(ERROR_ENDIANNESS_UNSUPPORTED, f"endianness={endianness!r}")

    address = record.get("address")
    if not isinstance(address, int) or address < 0 or address > MASK32 or address & 3:
        raise SemanticsError(ERROR_INVALID_RECORD, f"address={address!r}")

    effect: dict[str, Any] = {
        "op": op,
        "address": address,
        "next": "fallthrough",
        "target": None,
        "link_value": None,
        "register_writes": [],
        "register_write_suppressed": False,
        "hi_lo_effect": HI_LO_UNCHANGED,
        "hi": None,
        "lo": None,
        "memory_effects": [],
        "trap_code": None,
    }

    if op in ("movz", "movn"):
        rs = _operand(record, "rs")
        rt = _operand(record, "rt")
        rd = _operand(record, "rd")
        condition = state.read_reg(rt) == 0 if op == "movz" else state.read_reg(rt) != 0
        if condition and rd != 0:
            value = state.read_reg(rs)
            state.write_reg(rd, value)
            effect["register_writes"].append({"register": rd, "value": value})
        elif condition:
            effect["register_write_suppressed"] = True
        return effect

    if op == "mul":
        rs = _operand(record, "rs")
        rt = _operand(record, "rt")
        rd = _operand(record, "rd")
        product = signed32(state.read_reg(rs)) * signed32(state.read_reg(rt))
        value = product & MASK32
        state.mark_hi_lo_unpredictable()
        if rd != 0:
            state.write_reg(rd, value)
            effect["register_writes"].append({"register": rd, "value": value})
        else:
            effect["register_write_suppressed"] = True
        effect["hi_lo_effect"] = HI_LO_UNPREDICTABLE
        return effect

    if op == "divu":
        rs = _operand(record, "rs")
        rt = _operand(record, "rt")
        divisor = state.read_reg(rt)
        if divisor == 0:
            raise SemanticsError(
                ERROR_DIVIDE_BY_ZERO,
                f"0x{address:08x}: divu divisor is zero (architecturally UNPREDICTABLE)")
        dividend = state.read_reg(rs)
        quotient, remainder = divmod(dividend, divisor)
        state.write_lo(quotient)
        state.write_hi(remainder)
        effect["hi_lo_effect"] = HI_LO_DEFINED
        effect["lo"] = quotient
        effect["hi"] = remainder
        return effect

    if op == "teq":
        rs = _operand(record, "rs")
        rt = _operand(record, "rt")
        code = _operand(record, "code")
        if state.read_reg(rs) == state.read_reg(rt):
            raise SemanticsError(
                ERROR_TRAP_TAKEN,
                f"0x{address:08x}: teq trap taken (code={code}); exception delivery "
                "is not modelled")
        effect["trap_code"] = code
        return effect

    if op in ("swl", "swr"):
        rs = _operand(record, "rs")
        rt = _operand(record, "rt")
        imm = _operand(record, "imm")
        value = state.read_reg(rt)
        vaddr = (state.read_reg(rs) + sign16(imm)) & MASK32
        aligned = vaddr & ~3
        byte_offset = vaddr & 3
        old_value = memory.read_u32(aligned)
        shifted = (byte_offset * 8) & 31
        if op == "swl":
            mem_mask = (0xFFFFFF00 << shifted) & MASK32
            new_value = (old_value & mem_mask) | (value >> (24 - shifted))
        else:
            mem_mask = 0x00FFFFFF >> (24 - shifted)
            new_value = (old_value & mem_mask) | ((value << shifted) & MASK32)
        new_value &= MASK32
        memory.write_u32(aligned, new_value)
        effect["memory_effects"].append({
            "address": aligned,
            "old_value": old_value,
            "new_value": new_value,
            "bytes_stored": byte_offset + 1 if op == "swl" else 4 - byte_offset,
        })
        return effect

    if op == "jalr":
        rs = _operand(record, "rs")
        rd = _operand(record, "rd")
        target = state.read_reg(rs)
        if target & 3:
            raise SemanticsError(
                ERROR_UNALIGNED_TARGET,
                f"0x{address:08x}: jalr target 0x{target:08x} is not 4-byte aligned")
        link_value = (address + 8) & MASK32
        if rd != 0:
            state.write_reg(rd, link_value)
            effect["register_writes"].append({"register": rd, "value": link_value})
        else:
            effect["register_write_suppressed"] = True
        effect["next"] = "indirect"
        effect["target"] = target
        effect["link_value"] = link_value
        return effect

    raise SemanticsError(ERROR_UNSUPPORTED_INSTRUCTION, f"op={op!r}")
