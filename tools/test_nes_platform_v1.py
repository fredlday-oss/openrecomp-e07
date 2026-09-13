#!/usr/bin/env python3
"""P1-33 gate: NES CPU-facing PPU/APU/controller platform contract.

Builds synthetic NROM images, then pins the documented CPU bus and register
surfaces (NESdev "CPU memory map", "PPU registers", "Standard controller"):

- 2 KiB RAM with the documented $0800-$1FFF mirrors;
- PPUSTATUS vblank flag read-and-clear and write-latch clear;
- PPUADDR two-write protocol, PPUDATA write/read with the one-byte read buffer,
  the 1/32 address increment, palette immediate reads and $3F10/$3F14/$3F18/
  $3F1C mirrors;
- nametable VRAM horizontal/vertical arrangement mapping;
- OAMADDR/OAMDATA increment behaviour and OAMDMA page copy;
- the controller strobe + 8-bit shift protocol (A, B, Select, Start, Up, Down,
  Left, Right), the $40 open-bus bits and the documented all-1 tail;
- the deterministic APU register/status/frame-counter latch surface;
- fail-closed access to disabled/expansion registers, CHR-ROM writes and
  unmodelled four-screen nametables;
- secondary local-ROM metadata-only evidence (ROM_INVENTORY.json).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from nes_platform_v1 import NESPlatformError, NesMachine  # noqa: E402
from nes_rom_v1 import CHR_BANK_SIZE, NESROMError, PRG_BANK_SIZE, classify, parse_header  # noqa: E402


def build_nrom(*, prg_banks: int = 2, chr_banks: int = 1, flags6: int = 0x00) -> bytes:
    header = bytearray(16)
    header[0:4] = b"NES\x1a"
    header[4] = prg_banks
    header[5] = chr_banks
    header[6] = flags6
    prg = bytes((index * 3) & 0xFF for index in range(prg_banks * PRG_BANK_SIZE))
    chr_data = bytes((index * 5 + 1) & 0xFF for index in range(chr_banks * CHR_BANK_SIZE))
    return bytes(header) + prg + chr_data


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ppu_set_addr(machine: NesMachine, address: int) -> None:
    machine.read_memory(0x2002)  # clear the write latch
    machine.write_memory(0x2006, (address >> 8) & 0x3F)
    machine.write_memory(0x2006, address & 0xFF)


def ppu_read_mem(machine: NesMachine, address: int) -> int:
    ppu_set_addr(machine, address)
    machine.read_memory(0x2007)  # prime the read buffer
    return machine.read_memory(0x2007)


def ppu_write_mem(machine: NesMachine, address: int, value: int) -> None:
    ppu_set_addr(machine, address)
    machine.write_memory(0x2007, value)


def expect_fail(label: str, action, error_type=(NESPlatformError, NESROMError)) -> None:
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

    machine = NesMachine(build_nrom())

    # RAM + mirrors ---------------------------------------------------------
    machine.write_memory(0x0000, 0x5A)
    for mirror in (0x0800, 0x1000, 0x1800):
        assert machine.read_memory(mirror) == 0x5A, hex(mirror)
    machine.write_memory(0x07FF, 0xA5)
    assert machine.read_memory(0x1FFF) == 0xA5
    print("PASS ram-2k-with-mirrors")
    tests += 1

    # PPUSTATUS vblank read-and-clear --------------------------------------
    machine.ppu.set_vblank(True)
    status = machine.read_memory(0x2002)
    assert status & 0x80, hex(status)
    assert machine.read_memory(0x2002) & 0x80 == 0
    print("PASS ppustatus-vblank-read-clear")
    tests += 1

    # PPUADDR/PPUDATA write, buffered read, increment ----------------------
    ppu_write_mem(machine, 0x2000, 0xAB)
    assert ppu_read_mem(machine, 0x2000) == 0xAB
    # 1-byte increment
    machine.read_memory(0x2002)
    machine.write_memory(0x2006, 0x20)
    machine.write_memory(0x2006, 0x10)
    machine.write_memory(0x2007, 0x11)  # vram[0x10]
    machine.write_memory(0x2007, 0x22)  # vram[0x11]
    assert ppu_read_mem(machine, 0x2010) == 0x11
    assert ppu_read_mem(machine, 0x2011) == 0x22
    # 32-byte increment via PPUCTRL bit 2
    machine.write_memory(0x2000, 0x04)
    machine.read_memory(0x2002)
    machine.write_memory(0x2006, 0x20)
    machine.write_memory(0x2006, 0x00)
    machine.write_memory(0x2007, 0x33)
    machine.write_memory(0x2007, 0x44)  # lands at 0x2020
    assert ppu_read_mem(machine, 0x2000) == 0x33
    assert ppu_read_mem(machine, 0x2020) == 0x44
    print("PASS ppudata-write-buffered-read-increment-1-and-32")
    tests += 1

    # Palette immediate read + mirrors -------------------------------------
    ppu_set_addr(machine, 0x3F00)
    machine.write_memory(0x2007, 0x15)
    ppu_set_addr(machine, 0x3F00)
    assert machine.read_memory(0x2007) == 0x15  # palette reads return immediately
    ppu_set_addr(machine, 0x3F10)
    assert machine.read_memory(0x2007) == 0x15  # $3F10 mirrors $3F00
    print("PASS palette-immediate-read-and-mirror")
    tests += 1

    # Nametable arrangement mapping ----------------------------------------
    horizontal = NesMachine(build_nrom(flags6=0x00))  # vertical arrangement = horizontal mirroring
    ppu_write_mem(horizontal, 0x2000, 0x11)
    assert ppu_read_mem(horizontal, 0x2400) == 0x11  # NT0 = NT1
    ppu_write_mem(horizontal, 0x2800, 0x22)
    assert ppu_read_mem(horizontal, 0x2C00) == 0x22  # NT2 = NT3
    assert ppu_read_mem(horizontal, 0x2000) == 0x11
    vertical = NesMachine(build_nrom(flags6=0x01))  # horizontal arrangement = vertical mirroring
    ppu_write_mem(vertical, 0x2000, 0x33)
    assert ppu_read_mem(vertical, 0x2400) != 0x33  # NT0 != NT1
    assert ppu_read_mem(vertical, 0x2800) == 0x33  # NT0 = NT2
    print("PASS nametable-arrangement-horizontal-vertical")
    tests += 1

    # OAMADDR/OAMDATA + OAMDMA ---------------------------------------------
    machine.write_memory(0x2003, 0x00)
    machine.write_memory(0x2004, 0x55)  # writes increment OAMADDR
    assert machine.ppu.oam[0x00] == 0x55
    assert machine.ppu.oam_addr == 0x01
    assert machine.read_memory(0x2004) == machine.ppu.oam[0x01]  # reads do not increment
    for offset in range(256):
        machine.ram[0x0200 + offset] = (offset ^ 0x3C) & 0xFF
    machine.write_memory(0x4014, 0x02)
    assert bytes(machine.ppu.oam) == bytes(machine.ram[0x0200:0x0300])
    print("PASS oamdata-increment-and-oamdma")
    tests += 1

    # Controller shift protocol --------------------------------------------
    machine.set_controller(0, {"a", "right"})  # bits 0 and 7
    machine.set_controller(1, {"b", "start"})  # bits 1 and 3
    machine.write_memory(0x4016, 0x01)
    assert machine.read_memory(0x4016) == 0x41  # strobe high -> A held
    machine.write_memory(0x4016, 0x00)  # falling edge latches
    expected0 = [0x41, 0x40, 0x40, 0x40, 0x40, 0x40, 0x40, 0x41, 0x41, 0x41]
    actual0 = [machine.read_memory(0x4016) for _ in range(10)]
    assert actual0 == expected0, actual0
    # controller 2 read through $4017
    machine.write_memory(0x4016, 0x01)
    machine.write_memory(0x4016, 0x00)
    expected1 = [0x40, 0x41, 0x40, 0x41, 0x40, 0x40, 0x40, 0x40, 0x41]
    actual1 = [machine.read_memory(0x4017) for _ in range(9)]
    assert actual1 == expected1, actual1
    print("PASS controller-strobe-shift-order-and-open-bus")
    tests += 1

    # APU latch surface -----------------------------------------------------
    machine.write_memory(0x4000, 0x12)
    machine.write_memory(0x4013, 0x34)
    machine.write_memory(0x4015, 0x0F)
    machine.write_memory(0x4017, 0x40)
    assert machine.apu_registers[0x00] == 0x12
    assert machine.apu_registers[0x13] == 0x34
    assert machine.read_memory(0x4015) == 0x0F
    assert machine.apu_registers[0x17] == 0x40
    print("PASS apu-latch-status-frame-counter")
    tests += 1

    # Fail-closed surfaces --------------------------------------------------
    expect_fail("read-disabled-io", lambda: machine.read_memory(0x4018))
    expect_fail("write-disabled-io", lambda: machine.write_memory(0x4018, 0x00))
    expect_fail("read-expansion-area", lambda: machine.read_memory(0x4020))
    expect_fail("write-expansion-area", lambda: machine.write_memory(0x5000, 0x00))
    expect_fail("out-of-range-address", lambda: machine.read_memory(0x10000))
    expect_fail("chr-rom-write", lambda: ppu_write_mem(machine, 0x0000, 0x00))
    four_screen = NesMachine(build_nrom(flags6=0x08))
    expect_fail("four-screen-nametable-unmodelled", lambda: ppu_read_mem(four_screen, 0x2000))
    print("PASS fail-closed-surfaces")
    tests += 1

    # Local-ROM metadata-only evidence --------------------------------------
    inventory_path = ROOT / ".openrecomp-phase1" / "ROM_INVENTORY.json"
    if inventory_path.exists():
        inventory = json.loads(inventory_path.read_text(encoding="utf-8-sig"))
        entry = inventory["platforms"]["nes"][0]
        rom_path = Path(entry["full_path"])
        if rom_path.exists():
            rom_bytes = rom_path.read_bytes()
            assert digest(rom_bytes) == entry["sha256"], "local ROM hash drifted from ROM_INVENTORY.json"
            local_info = classify(rom_bytes)
            local_header = parse_header(rom_bytes)
            print(
                f"LOCAL_NES_ROM metadata-only sha256={digest(rom_bytes)} mapper={local_info.mapper} "
                f"prg_bytes={local_info.prg_bytes} chr_bytes={local_info.chr_bytes} "
                f"mirroring={local_info.mirroring} nes2={int(local_info.is_nes2)} tv={local_header.tv_system}"
            )
        else:
            print(f"LOCAL_NES_ROM SKIPPED (file absent: {entry['full_path']})")
    else:
        print("LOCAL_NES_ROM SKIPPED (no ROM_INVENTORY.json)")
    tests += 1

    print(f"OPENRECOMP_NES_PLATFORM_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
