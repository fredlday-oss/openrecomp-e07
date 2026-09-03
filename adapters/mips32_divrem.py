from __future__ import annotations

from .mips32 import DecodeError, decode as decode_v1


def decode(address: int, word: int) -> dict:
    opcode = (word >> 26) & 0x3F; funct = word & 0x3F
    if opcode != 0 or funct not in {0x1A, 0x1B}:
        return decode_v1(address, word)
    if address < 0 or address & 3:
        raise DecodeError(f"misaligned MIPS32 instruction address 0x{address:x}")
    if word < 0 or word > 0xFFFFFFFF:
        raise DecodeError("MIPS32 word is outside 32-bit range")
    rs = (word >> 21) & 0x1F; rt = (word >> 16) & 0x1F; rd = (word >> 11) & 0x1F; shamt = (word >> 6) & 0x1F
    if rd != 0 or shamt != 0:
        raise DecodeError(f"0x{address:x}: malformed div/divu encoding")
    return {"address": address, "word": word, "op": "div" if funct == 0x1A else "divu", "rs": rs, "rt": rt}
