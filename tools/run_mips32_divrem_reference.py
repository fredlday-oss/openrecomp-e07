#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_mips32_expansion_reference import MASK32, ReferenceError, ReferenceMachine, load_hex

MIN_I32 = -(1 << 31)


def _signed32(value: int) -> int:
    value &= MASK32
    return value - (1 << 32) if value & 0x80000000 else value


class DivRemReferenceMachine(ReferenceMachine):
    def __init__(self, words: dict[int, int], meta: dict):
        legacy_meta = dict(meta); legacy_meta["profile"] = "expansion-v1"
        super().__init__(words, legacy_meta); self.meta = meta

    def _execute_simple(self, address: int, word: int) -> None:
        opcode = (word >> 26) & 0x3F; funct = word & 0x3F
        if opcode != 0 or funct not in {0x1A, 0x1B}:
            return super()._execute_simple(address, word)
        self._step()
        rs = (word >> 21) & 0x1F; rt = (word >> 16) & 0x1F; rd = (word >> 11) & 0x1F; shamt = (word >> 6) & 0x1F
        if rd != 0 or shamt != 0:
            raise ReferenceError(f"0x{address:x}: malformed div/divu")
        lhs = self.read(rs); rhs = self.read(rt)
        if rhs == 0:
            raise ReferenceError(f"0x{address:x}: MIPS32 divide-by-zero is outside the bounded defined domain")
        if funct == 0x1B:
            self.lo = (lhs // rhs) & MASK32; self.hi = (lhs % rhs) & MASK32; return
        a = _signed32(lhs); b = _signed32(rhs)
        if a == MIN_I32 and b == -1:
            raise ReferenceError(f"0x{address:x}: MIPS32 signed division overflow is outside the bounded defined domain")
        q = abs(a) // abs(b)
        if (a < 0) != (b < 0): q = -q
        self.lo = q & MASK32; self.hi = (a - q * b) & MASK32


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: run_mips32_divrem_reference.py <fixture.hex> <fixture.json> <out-result.json>", file=sys.stderr); return 2
    try:
        words, source_hash = load_hex(argv[1]); meta = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        if meta.get("profile") != "divrem-v1" or meta.get("divrem_domain") != "defined-mips32-operands-only":
            raise ReferenceError("reference requires bounded divrem-v1 profile")
        machine = DivRemReferenceMachine(words, meta); machine.run(); result = machine.result(source_hash)
        Path(argv[3]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, UnicodeDecodeError, ValueError, KeyError, json.JSONDecodeError, ReferenceError) as exc:
        print(f"OPENRECOMP_MIPS32_DIVREM_REFERENCE=FAIL: {exc}", file=sys.stderr); return 2
    print(f"MIPS32_DIVREM_REFERENCE_V0={result['return_v0']}"); print(f"MIPS32_DIVREM_REFERENCE_CHECKSUM={result['checksum']}"); print("OPENRECOMP_MIPS32_DIVREM_REFERENCE=PASS"); return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
