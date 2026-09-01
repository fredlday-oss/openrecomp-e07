from __future__ import annotations

from .interface import ArchitectureInfo


# `info.endianness` is the legacy vertical-slice default. Expansion V1 source
# profiles carry mips32-le/mips32-be endianness explicitly per fixture.
info = ArchitectureInfo(
    "mips32-bounded-v1",
    32,
    "little",
    tuple([f"r{i}" for i in range(32)]),
    "bounded synthetic subset; Expansion V1 endianness is fixture-defined",
)


class DecodeError(ValueError):
    pass


def _sign16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def decode(address: int, word: int) -> dict:
    if address < 0 or address & 3:
        raise DecodeError(f"misaligned MIPS32 instruction address 0x{address:x}")
    if word < 0 or word > 0xFFFFFFFF:
        raise DecodeError("MIPS32 word is outside 32-bit range")

    if word == 0:
        return {"address": address, "word": word, "op": "nop"}

    opcode = (word >> 26) & 0x3F
    rs = (word >> 21) & 0x1F
    rt = (word >> 16) & 0x1F
    rd = (word >> 11) & 0x1F
    shamt = (word >> 6) & 0x1F
    funct = word & 0x3F
    imm_u = word & 0xFFFF
    imm_s = _sign16(imm_u)

    if opcode == 0:
        if funct in {0x00, 0x02, 0x03}:
            if rs != 0:
                raise DecodeError(f"0x{address:x}: malformed fixed-shift encoding")
            return {
                "address": address,
                "word": word,
                "op": {0x00: "sll", 0x02: "srl", 0x03: "sra"}[funct],
                "rt": rt,
                "rd": rd,
                "shamt": shamt,
            }
        if funct in {0x04, 0x06, 0x07}:
            if shamt != 0:
                raise DecodeError(f"0x{address:x}: malformed variable-shift encoding")
            return {
                "address": address,
                "word": word,
                "op": {0x04: "sllv", 0x06: "srlv", 0x07: "srav"}[funct],
                "rs": rs,
                "rt": rt,
                "rd": rd,
            }
        if funct == 0x08:
            if rt != 0 or rd != 0 or shamt != 0:
                raise DecodeError(f"0x{address:x}: malformed jr encoding")
            return {"address": address, "word": word, "op": "jr", "rs": rs}
        if funct in {0x10, 0x12}:
            if rs != 0 or rt != 0 or shamt != 0:
                raise DecodeError(f"0x{address:x}: malformed mfhi/mflo encoding")
            return {
                "address": address,
                "word": word,
                "op": "mfhi" if funct == 0x10 else "mflo",
                "rd": rd,
            }
        if funct in {0x18, 0x19}:
            if rd != 0 or shamt != 0:
                raise DecodeError(f"0x{address:x}: malformed mult/multu encoding")
            return {
                "address": address,
                "word": word,
                "op": "mult" if funct == 0x18 else "multu",
                "rs": rs,
                "rt": rt,
            }
        if funct in {0x1A, 0x1B}:
            raise DecodeError(f"0x{address:x}: div/divu require a future normalized IR contract")
        if funct in {0x21, 0x23, 0x24, 0x25, 0x26, 0x27, 0x2A, 0x2B}:
            if shamt != 0:
                raise DecodeError(f"0x{address:x}: unexpected shamt for SPECIAL instruction")
            return {
                "address": address,
                "word": word,
                "op": {
                    0x21: "addu",
                    0x23: "subu",
                    0x24: "and",
                    0x25: "or",
                    0x26: "xor",
                    0x27: "nor",
                    0x2A: "slt",
                    0x2B: "sltu",
                }[funct],
                "rs": rs,
                "rt": rt,
                "rd": rd,
            }
        raise DecodeError(f"0x{address:x}: unsupported SPECIAL funct 0x{funct:02x}")

    if opcode == 0x01:
        if rt not in {0, 1}:
            raise DecodeError(f"0x{address:x}: unsupported REGIMM rt 0x{rt:02x}")
        target = (address + 4 + (imm_s << 2)) & 0xFFFFFFFF
        return {
            "address": address,
            "word": word,
            "op": "bltz" if rt == 0 else "bgez",
            "rs": rs,
            "target": target,
        }
    if opcode == 0x09:
        return {"address": address, "word": word, "op": "addiu", "rs": rs, "rt": rt, "imm": imm_s}
    if opcode in {0x0A, 0x0B}:
        return {
            "address": address,
            "word": word,
            "op": "slti" if opcode == 0x0A else "sltiu",
            "rs": rs,
            "rt": rt,
            "imm": imm_s,
        }
    if opcode in {0x0C, 0x0D, 0x0E}:
        return {
            "address": address,
            "word": word,
            "op": {0x0C: "andi", 0x0D: "ori", 0x0E: "xori"}[opcode],
            "rs": rs,
            "rt": rt,
            "imm": imm_u,
        }
    if opcode == 0x0F:
        if rs != 0:
            raise DecodeError(f"0x{address:x}: malformed lui encoding")
        return {"address": address, "word": word, "op": "lui", "rt": rt, "imm": imm_u}
    if opcode in {0x04, 0x05}:
        target = (address + 4 + (imm_s << 2)) & 0xFFFFFFFF
        return {
            "address": address,
            "word": word,
            "op": "beq" if opcode == 0x04 else "bne",
            "rs": rs,
            "rt": rt,
            "target": target,
        }
    if opcode in {0x06, 0x07}:
        if rt != 0:
            raise DecodeError(f"0x{address:x}: malformed blez/bgtz encoding")
        target = (address + 4 + (imm_s << 2)) & 0xFFFFFFFF
        return {
            "address": address,
            "word": word,
            "op": "blez" if opcode == 0x06 else "bgtz",
            "rs": rs,
            "target": target,
        }
    if opcode in {0x20, 0x21, 0x23, 0x24, 0x25}:
        return {
            "address": address,
            "word": word,
            "op": {0x20: "lb", 0x21: "lh", 0x23: "lw", 0x24: "lbu", 0x25: "lhu"}[opcode],
            "rs": rs,
            "rt": rt,
            "imm": imm_s,
        }
    if opcode in {0x28, 0x29, 0x2B}:
        return {
            "address": address,
            "word": word,
            "op": {0x28: "sb", 0x29: "sh", 0x2B: "sw"}[opcode],
            "rs": rs,
            "rt": rt,
            "imm": imm_s,
        }
    if opcode in {0x02, 0x03}:
        target = ((address + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
        return {"address": address, "word": word, "op": "j" if opcode == 0x02 else "jal", "target": target}

    raise DecodeError(f"0x{address:x}: unsupported opcode 0x{opcode:02x}")


def branch_targets(insn: dict) -> list[int]:
    if insn.get("op") in {"beq", "bne", "blez", "bgtz", "bltz", "bgez", "j", "jal"}:
        return [insn["target"]]
    return []


def is_control_flow(insn: dict) -> bool:
    return insn.get("op") in {"beq", "bne", "blez", "bgtz", "bltz", "bgez", "j", "jal", "jr"}
