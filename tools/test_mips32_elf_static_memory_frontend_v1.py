#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import struct
import tempfile
from pathlib import Path

from mips32_elf_frontend_v1 import MIPS32ELFError, load_mips32_elf
from mips32_elf_static_memory_frontend_v1 import (
    MIPS32ELFStaticMemoryError,
    load_mips32_elf_static_memory,
)

TEXT_ADDR = 0x1000
RO_ADDR = 0x2000
DATA_ADDR = 0x3000
BSS_ADDR = 0x3004
MEMORY_SIZE = 0x40000


def _align(value: int, alignment: int = 4) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def make_static_elf() -> tuple[bytearray, dict[str, int]]:
    text = b"".join(word.to_bytes(4, "little") for word in (0x24021234, 0x03E00008, 0x00000000))
    rodata = bytes.fromhex("44332211")
    data = bytes.fromhex("04030201")
    strtab = b"\0static_memory_main\0"
    shstr = b"\0.text\0.rodata\0.data\0.bss\0.symtab\0.strtab\0.shstrtab\0"
    names = {name: shstr.index(name.encode()) for name in (".text", ".rodata", ".data", ".bss", ".symtab", ".strtab", ".shstrtab")}

    header_size = 52
    text_off = _align(header_size)
    ro_off = _align(text_off + len(text))
    data_off = _align(ro_off + len(rodata))
    symtab_off = _align(data_off + len(data))
    symtab = b"\0" * 16 + struct.pack("<IIIBBH", 1, TEXT_ADDR, len(text), (1 << 4) | 2, 0, 1)
    strtab_off = _align(symtab_off + len(symtab))
    shstr_off = _align(strtab_off + len(strtab))
    shoff = _align(shstr_off + len(shstr))
    shnum = 8
    blob = bytearray(shoff + shnum * 40)

    ident = bytearray(16)
    ident[:4] = b"\x7fELF"
    ident[4] = ident[5] = ident[6] = 1
    struct.pack_into(
        "<16sHHIIIIIHHHHHH", blob, 0, bytes(ident), 2, 8, 1, TEXT_ADDR, 0, shoff, 0,
        52, 0, 0, 40, shnum, 7,
    )
    blob[text_off:text_off + len(text)] = text
    blob[ro_off:ro_off + len(rodata)] = rodata
    blob[data_off:data_off + len(data)] = data
    blob[symtab_off:symtab_off + len(symtab)] = symtab
    blob[strtab_off:strtab_off + len(strtab)] = strtab
    blob[shstr_off:shstr_off + len(shstr)] = shstr

    def sh(index: int, name: str | None, stype: int, flags: int, addr: int, off: int, size: int,
           link: int = 0, info: int = 0, align: int = 1, entsize: int = 0) -> None:
        struct.pack_into(
            "<IIIIIIIIII", blob, shoff + index * 40,
            0 if name is None else names[name], stype, flags, addr, off, size, link, info, align, entsize,
        )

    sh(0, None, 0, 0, 0, 0, 0)
    sh(1, ".text", 1, 0x2 | 0x4, TEXT_ADDR, text_off, len(text), align=4)
    sh(2, ".rodata", 1, 0x2, RO_ADDR, ro_off, len(rodata), align=4)
    sh(3, ".data", 1, 0x1 | 0x2, DATA_ADDR, data_off, len(data), align=4)
    sh(4, ".bss", 8, 0x1 | 0x2, BSS_ADDR, 0, 4, align=4)
    sh(5, ".symtab", 2, 0, 0, symtab_off, len(symtab), link=6, info=1, align=4, entsize=16)
    sh(6, ".strtab", 3, 0, 0, strtab_off, len(strtab))
    sh(7, ".shstrtab", 3, 0, 0, shstr_off, len(shstr))
    return blob, {"shoff": shoff}


def _load(blob: bytearray) -> dict:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "static.elf"
        path.write_bytes(blob)
        return load_mips32_elf_static_memory(path, MEMORY_SIZE)


def _reject(blob: bytearray, needle: str) -> None:
    try:
        _load(blob)
    except MIPS32ELFStaticMemoryError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected rejection containing {needle!r}")


def test_valid_static_memory() -> None:
    blob, _ = make_static_elf()
    loaded = _load(blob)
    assert loaded["input_sha256"] == hashlib.sha256(blob).hexdigest()
    segments = {item["name"]: item for item in loaded["memory_segments"]}
    assert segments[".rodata"]["data_hex"] == "44332211"
    assert segments[".data"]["data_hex"] == "04030201"
    assert segments[".bss"]["data_hex"] == "00000000"
    assert segments[".bss"]["zero_fill"] is True


def test_text_only_gate_still_rejects_static_alloc() -> None:
    blob, _ = make_static_elf()
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "static.elf"
        path.write_bytes(blob)
        try:
            load_mips32_elf(path)
        except MIPS32ELFError as exc:
            assert "alloc section outside text-only" in str(exc)
        else:
            raise AssertionError("text-only ELF gate silently widened")


def test_rodata_must_be_read_only() -> None:
    blob, info = make_static_elf()
    struct.pack_into("<I", blob, info["shoff"] + 2 * 40 + 8, 0x1 | 0x2)
    _reject(blob, ".rodata must be")


def test_data_must_be_writable() -> None:
    blob, info = make_static_elf()
    struct.pack_into("<I", blob, info["shoff"] + 3 * 40 + 8, 0x2)
    _reject(blob, ".data must be")


def test_bss_must_be_nobits() -> None:
    blob, info = make_static_elf()
    struct.pack_into("<I", blob, info["shoff"] + 4 * 40 + 4, 1)
    _reject(blob, ".bss must be")


def test_static_section_out_of_memory() -> None:
    blob, info = make_static_elf()
    struct.pack_into("<I", blob, info["shoff"] + 4 * 40 + 12, MEMORY_SIZE)
    _reject(blob, "outside deterministic guest memory")


def test_static_sections_must_not_overlap() -> None:
    blob, info = make_static_elf()
    struct.pack_into("<I", blob, info["shoff"] + 4 * 40 + 12, DATA_ADDR)
    _reject(blob, "static sections overlap")


def main() -> int:
    tests = (
        test_valid_static_memory,
        test_text_only_gate_still_rejects_static_alloc,
        test_rodata_must_be_read_only,
        test_data_must_be_writable,
        test_bss_must_be_nobits,
        test_static_section_out_of_memory,
        test_static_sections_must_not_overlap,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"OPENRECOMP_MIPS32_ELF_STATIC_MEMORY_TESTS=PASS count={len(tests)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
