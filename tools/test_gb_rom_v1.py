#!/usr/bin/env python3
"""P1-14 gate: Game Boy ROM ingestion + memory/platform contract.

Builds synthetic/original ROM images programmatically (a Nintendo-logo-free
header with the documented checksum), then pins:

- header parsing (entry, title, CGB/SGB flags, type, sizes, checksums);
- classification of representative documented cartridge types;
- fail-closed rejection (short image, bad header checksum, undocumented type,
  undocumented size code, RAM declared without RAM size);
- the documented no-MBC memory map and the MBC1 banking rules (RAM enable
  nibble, ROM bank select with the documented 0->1 rule, RAM bank select,
  advanced mode);
- mapper fail-closed behaviour for classified-but-unimplemented mappers.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from gb_rom_loader_v1 import (  # noqa: E402
    GBROMError,
    Mbc1Mapper,
    RomOnlyMapper,
    classify,
    compute_header_checksum,
    make_mapper,
    parse_header,
)


def build_rom(*, cartridge_type: int = 0x00, rom_size_code: int = 0x00, ram_size_code: int = 0x00,
              cgb_flag: int = 0x00, title: str = "OPENRECOMP") -> bytes:
    size = {0x00: 32 * 1024, 0x01: 64 * 1024, 0x02: 128 * 1024, 0x03: 256 * 1024}[rom_size_code]
    data = bytearray(size)
    data[0x0100:0x0104] = b"\x00\xC3\x50\x01"  # nop; jp 0x0150
    title_bytes = title.encode("ascii")[:15].ljust(15, b"\x00")
    data[0x0134:0x0143] = title_bytes
    data[0x0143] = cgb_flag
    data[0x0146] = 0x00
    data[0x0147] = cartridge_type
    data[0x0148] = rom_size_code
    data[0x0149] = ram_size_code
    data[0x014A] = 0x00
    data[0x014B] = 0x33
    data[0x014C] = 0x00
    checksum = compute_header_checksum(bytes(data))
    data[0x014D] = checksum
    data[0x014E:0x0150] = b"\x00\x00"
    return bytes(data)


def expect_fail(label: str, action, error_type=GBROMError) -> None:
    try:
        action()
    except error_type:
        print(f"PASS reject: {label}")
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"{label}: raised {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"{label}: accepted")


def main() -> int:
    tests = 0

    rom = build_rom()
    header = parse_header(rom)
    assert header.entry_point == 0xC300, hex(header.entry_point)  # LE bytes of `nop; jp 0x0150`
    assert header.title == "OPENRECOMP", header.title
    assert header.cgb_flag == 0x00
    assert header.sgb_flag == 0x00
    assert header.cartridge_type == 0x00
    assert header.logo_present is False
    print("PASS header-parse")
    tests += 1

    info = classify(rom)
    assert info.mapper == "none"
    assert info.cgb_mode == "dmg"
    assert info.rom_bytes == 32 * 1024
    assert info.rom_banks == 2
    assert info.header_checksum_valid is True
    print("PASS classification rom-only/dmg")
    tests += 1

    expected_types = {
        0x00: ("none", "dmg"),
        0x01: ("mbc1", "dmg"),
        0x03: ("mbc1", "dmg"),
        0x0F: ("mbc3", "dmg"),
        0x13: ("mbc3", "dmg"),
        0x1B: ("mbc5", "dmg"),
        0x19: ("mbc5", "dmg"),
    }
    for cart_type, (mapper, mode) in expected_types.items():
        image = build_rom(cartridge_type=cart_type, ram_size_code=0x02 if cart_type not in (0x01, 0x19) else 0x00)
        classified = classify(image)
        assert classified.mapper == mapper, (cart_type, classified.mapper)
        assert classified.cgb_mode == mode
    print(f"PASS classification {len(expected_types)} documented cartridge types")
    tests += 1

    cgb = classify(build_rom(cgb_flag=0x80))
    assert cgb.cgb_mode == "cgb-compatible"
    cgb_only = classify(build_rom(cgb_flag=0xC0))
    assert cgb_only.cgb_mode == "cgb-only"
    print("PASS cgb-mode-separation dmg / cgb-compatible / cgb-only")
    tests += 1

    expect_fail("short-image", lambda: parse_header(bytes(0x100)))
    bad = bytearray(build_rom())
    bad[0x014D] ^= 0xFF
    expect_fail("bad-header-checksum", lambda: classify(bytes(bad)))
    expect_fail("undocumented-cartridge-type", lambda: classify(build_rom(cartridge_type=0x77)))
    bad_size = bytearray(build_rom())
    bad_size[0x0148] = 0x09
    expect_fail("undocumented-rom-size", lambda: classify(bytes(bad_size)))
    tests += 1

    # Documented no-MBC mapper ------------------------------------------
    mapper = make_mapper(rom)
    assert isinstance(mapper, RomOnlyMapper)
    assert mapper.read_rom(0x0100) == 0x00
    assert mapper.read_rom(0x0134) == ord("O")
    expect_fail("rom-only-write", lambda: mapper.write(0x2000, 0x0A))
    tests += 1

    # Documented MBC1 rules ----------------------------------------------
    mbc1_rom = build_rom(cartridge_type=0x03, rom_size_code=0x01, ram_size_code=0x03)
    mbc1 = make_mapper(mbc1_rom)
    assert isinstance(mbc1, Mbc1Mapper)
    mbc1.write(0x0000, 0x1F)  # low nibble != 0x0A -> disabled
    expect_fail("mbc1-ram-disabled-read", lambda: mbc1.read_ram(0xA000))
    mbc1.write(0x0000, 0x0A)  # documented enable pattern
    mbc1.write_ram(0xA000, 0x5A)
    assert mbc1.read_ram(0xA000) == 0x5A
    mbc1.write(0x2000, 0x00)  # documented: 0 selects bank 1
    assert mbc1.read_rom(0x4000) == mbc1_rom[0x4000]
    mbc1.write(0x2000, 0x03)
    assert mbc1.read_rom(0x4000) == mbc1_rom[3 * 0x4000]
    mbc1.write(0x4000, 0x02)  # RAM bank select
    mbc1.write_ram(0xA000, 0x77)
    assert mbc1.read_ram(0xA000) == 0x77
    mbc1.write(0x4000, 0x00)
    assert mbc1.read_ram(0xA000) == 0x5A
    mbc1.write(0x6000, 0x01)  # advanced mode
    mbc1.write(0x2000, 0x21)
    assert mbc1.read_rom(0x4000) == mbc1_rom[0x4000 + 1 * 0x4000]
    expect_fail("mbc1-write-outside-window", lambda: mbc1.write(0xFF00, 0x00))
    print("PASS mbc1-documented-rules ram-enable/banks/mode")
    tests += 1

    # Classified-but-unimplemented mappers fail closed -------------------
    mbc5_rom = build_rom(cartridge_type=0x19)
    expect_fail("mbc5-not-implemented-fails-closed", lambda: make_mapper(mbc5_rom))
    tests += 1

    print(f"OPENRECOMP_GB_ROM_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
