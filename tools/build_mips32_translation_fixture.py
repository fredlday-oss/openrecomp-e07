#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

EXPECTED_SHA256 = "c9b60aa0df3f95d7d35bbae92c2a99ccc65646bfb3ee44e7c3fc546146ee6e88"


def generate_fixture_bytes() -> bytes:
    ident = b"\x7fELF\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    ehdr = struct.pack("<HHIIIIIHHHHHH", 2, 8, 1, 0x1000, 0x34, 0, 0, 52, 32, 1, 0, 0, 0)
    phdr = struct.pack("<IIIIIIII", 1, 84, 0x1000, 0x1000, 40, 40, 5, 4)
    code = bytes.fromhex("0700022408000324211043000900402421104000020043100a004224140042240800e00300000000")
    elf = ident + ehdr + phdr + code
    digest = hashlib.sha256(elf).hexdigest()
    assert digest == EXPECTED_SHA256, f"SHA mismatch: {digest} != {EXPECTED_SHA256}"
    return elf


def build(target_path: Path | str | None = None) -> Path:
    if target_path is None:
        root = Path(__file__).resolve().parent.parent
        target_path = root / "artifacts" / "mips32_translation_v1" / "TRANSLATION_FIXTURE.elf"
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = generate_fixture_bytes()
    target.write_bytes(data)
    print(f"Wrote {target} ({len(data)} bytes, sha256={EXPECTED_SHA256})")
    return target


if __name__ == "__main__":
    build()
