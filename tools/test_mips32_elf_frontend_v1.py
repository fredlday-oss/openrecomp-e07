#!/usr/bin/env python3
from __future__ import annotations

import struct
import tempfile
from pathlib import Path

from mips32_elf_frontend_v1 import EM_MIPS, MIPS32ELFError, load_mips32_elf, runtime_meta_for_elf

TEXT_ADDR = 0x1000
TEXT_WORDS = (0x24081234, 0x03E00008, 0x00000000)


def _align(value: int, alignment: int = 4) -> int:
    return (value + alignment - 1) & ~(alignment - 1)


def make_elf() -> tuple[bytearray, dict[str, int]]:
    text = b"".join(word.to_bytes(4, "little") for word in TEXT_WORDS)
    strtab = b"\0logic_shift_main\0"
    shstr = b"\0.text\0.symtab\0.strtab\0.shstrtab\0"
    name_text = shstr.index(b".text")
    name_symtab = shstr.index(b".symtab")
    name_strtab = shstr.index(b".strtab")
    name_shstrtab = shstr.index(b".shstrtab")

    header_size = 52
    text_off = _align(header_size)
    symtab_off = _align(text_off + len(text))
    symtab = b"\0" * 16 + struct.pack(
        "<IIIBBH", 1, TEXT_ADDR, len(text), (1 << 4) | 2, 0, 1
    )
    strtab_off = _align(symtab_off + len(symtab))
    shstr_off = _align(strtab_off + len(strtab))
    shoff = _align(shstr_off + len(shstr))
    shnum = 5
    size = shoff + shnum * 40
    blob = bytearray(size)

    ident = bytearray(16)
    ident[:4] = b"\x7fELF"
    ident[4] = 1
    ident[5] = 1
    ident[6] = 1
    struct.pack_into(
        "<16sHHIIIIIHHHHHH",
        blob,
        0,
        bytes(ident),
        2,
        EM_MIPS,
        1,
        TEXT_ADDR,
        0,
        shoff,
        0,
        52,
        0,
        0,
        40,
        shnum,
        4,
    )
    blob[text_off : text_off + len(text)] = text
    blob[symtab_off : symtab_off + len(symtab)] = symtab
    blob[strtab_off : strtab_off + len(strtab)] = strtab
    blob[shstr_off : shstr_off + len(shstr)] = shstr

    def sh(index: int, name: int, stype: int, flags: int, addr: int, off: int, length: int,
           link: int = 0, info: int = 0, align: int = 1, entsize: int = 0) -> None:
        struct.pack_into(
            "<IIIIIIIIII", blob, shoff + index * 40,
            name, stype, flags, addr, off, length, link, info, align, entsize,
        )

    sh(0, 0, 0, 0, 0, 0, 0)
    sh(1, name_text, 1, 0x2 | 0x4, TEXT_ADDR, text_off, len(text), align=4)
    sh(2, name_symtab, 2, 0, 0, symtab_off, len(symtab), link=3, info=1, align=4, entsize=16)
    sh(3, name_strtab, 3, 0, 0, strtab_off, len(strtab))
    sh(4, name_shstrtab, 3, 0, 0, shstr_off, len(shstr))

    return blob, {
        "shoff": shoff,
        "symtab_off": symtab_off,
        "text_off": text_off,
    }


def expect_reject(blob: bytearray, needle: str) -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "bad.elf"
        path.write_bytes(blob)
        try:
            load_mips32_elf(path)
        except MIPS32ELFError as exc:
            assert needle in str(exc), (needle, str(exc))
        else:
            raise AssertionError(f"expected rejection containing {needle!r}")


def test_valid() -> None:
    blob, _ = make_elf()
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "valid.elf"
        path.write_bytes(blob)
        loaded = load_mips32_elf(path)
    assert loaded["architecture"] == "mips32-le"
    assert loaded["machine"] == EM_MIPS
    assert loaded["entry_point"] == TEXT_ADDR
    assert loaded["words"] == {
        TEXT_ADDR: TEXT_WORDS[0],
        TEXT_ADDR + 4: TEXT_WORDS[1],
        TEXT_ADDR + 8: TEXT_WORDS[2],
    }
    assert [(item["id"], item["address"]) for item in loaded["functions"]] == [
        ("logic_shift_main", TEXT_ADDR)
    ]


def test_wrong_machine() -> None:
    blob, _ = make_elf()
    struct.pack_into("<H", blob, 18, 243)
    expect_reject(blob, "expected EM_MIPS")


def test_big_endian() -> None:
    blob, _ = make_elf()
    blob[5] = 2
    expect_reject(blob, "expected little-endian ELF")


def test_entry_outside_text() -> None:
    blob, _ = make_elf()
    struct.pack_into("<I", blob, 24, TEXT_ADDR + 0x100)
    expect_reject(blob, "entry outside")


def test_text_nobits() -> None:
    blob, offsets = make_elf()
    struct.pack_into("<I", blob, offsets["shoff"] + 40 + 4, 8)
    expect_reject(blob, ".text must be file-backed")


def test_no_function_symbol() -> None:
    blob, offsets = make_elf()
    blob[offsets["symtab_off"] + 16 + 12] = (1 << 4) | 0
    expect_reject(blob, "no static STT_FUNC")


def test_runtime_must_agree_with_elf() -> None:
    blob, _ = make_elf()
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "valid.elf"
        path.write_bytes(blob)
        loaded = load_mips32_elf(path)
    runtime = {
        "fixture_version": "1.0.0",
        "profile": "expansion-v1",
        "fixture_id": "elf-test",
        "architecture": "mips32-le",
        "entry_address": TEXT_ADDR,
        "functions": [{"id": "logic_shift_main", "address": TEXT_ADDR}],
        "memory_size_bytes": 262144,
        "initial_state": {"gpr:r29": 196608, "gpr:r31": 0},
        "observe_state_slot": "gpr:r2",
        "observable_memory": {"address": 8192, "size_bytes": 4},
        "max_operations": 20000,
        "max_reference_steps": 2000,
    }
    merged = runtime_meta_for_elf(runtime, loaded)
    assert merged["entry_address"] == TEXT_ADDR
    bad = dict(runtime)
    bad["entry_address"] = TEXT_ADDR + 4
    try:
        runtime_meta_for_elf(bad, loaded)
    except MIPS32ELFError as exc:
        assert "entry_address disagrees" in str(exc)
    else:
        raise AssertionError("runtime/ELF entry mismatch was accepted")


def main() -> int:
    tests = (
        test_valid,
        test_wrong_machine,
        test_big_endian,
        test_entry_outside_text,
        test_text_nobits,
        test_no_function_symbol,
        test_runtime_must_agree_with_elf,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"OPENRECOMP_MIPS32_ELF_FRONTEND_TESTS=PASS count={len(tests)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
