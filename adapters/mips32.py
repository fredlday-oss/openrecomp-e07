from __future__ import annotations

from .interface import ArchitectureInfo


info = ArchitectureInfo(
    "mips32-le-slice",
    32,
    "little",
    tuple([f"r{i}" for i in range(32)]),
    "bounded o32-style synthetic slice; delay slots lowered by frontend",
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
        if shamt != 0 and funct in {0x08, 0x21, 0x2A, 0x2B}:
            raise DecodeError(f"0x{address:x}: unexpected shamt for SPECIAL instruction")
        if funct == 0x21:
            return {"address": address, "word": word, "op": "addu", "rs": rs, "rt": rt, "rd": rd}
        if funct == 0x2A:
            return {"address": address, "word": word, "op": "slt", "rs": rs, "rt": rt, "rd": rd}
        if funct == 0x2B:
            return {"address": address, "word": word, "op": "sltu", "rs": rs, "rt": rt, "rd": rd}
        if funct == 0x08:
            if rt != 0 or rd != 0 or shamt != 0:
                raise DecodeError(f"0x{address:x}: malformed jr encoding")
            return {"address": address, "word": word, "op": "jr", "rs": rs}
        raise DecodeError(f"0x{address:x}: unsupported SPECIAL funct 0x{funct:02x}")

    if opcode == 0x09:
        return {"address": address, "word": word, "op": "addiu", "rs": rs, "rt": rt, "imm": imm_s}
    if opcode == 0x0D:
        return {"address": address, "word": word, "op": "ori", "rs": rs, "rt": rt, "imm": imm_u}
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
    if opcode == 0x23:
        return {"address": address, "word": word, "op": "lw", "rs": rs, "rt": rt, "imm": imm_s}
    if opcode == 0x2B:
        return {"address": address, "word": word, "op": "sw", "rs": rs, "rt": rt, "imm": imm_s}
    if opcode in {0x02, 0x03}:
        target = ((address + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
        return {"address": address, "word": word, "op": "j" if opcode == 0x02 else "jal", "target": target}

    raise DecodeError(f"0x{address:x}: unsupported opcode 0x{opcode:02x}")


def branch_targets(insn: dict) -> list[int]:
    if insn.get("op") in {"beq", "bne", "j", "jal"}:
        return [insn["target"]]
    return []


def is_control_flow(insn: dict) -> bool:
    return insn.get("op") in {"beq", "bne", "j", "jal", "jr"}
