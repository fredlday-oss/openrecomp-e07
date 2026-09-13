#!/usr/bin/env python3
"""P1-22 gate: Master System ROM/banking/I-O platform contract.

Pins the documented SMS platform surface implemented by
`tools/sms_platform_v1.py` (SMS Power! development pages + official SMS
developer documents) using synthetic ROM images only:

- ROM ingestion: optional TMR SEGA header (all three documented offsets),
  little-endian checksum, region + size nibbles, fail-closed size rules;
- Sega mapper: 16 KiB banks, fixed first 1 KiB, slot registers $fffd-$ffff
  with the documented 315-5235 reset state, $fffc RAM-control bits, bank
  shift, ROM mirroring, "ROM write" enable, fail-closed cartridge-RAM
  access;
- memory map: system RAM mirror, control-register write-through, 3D-glasses
  control byte, port $3e memory enables (RAM/cartridge disable fail closed);
- VDP ports: two-byte control protocol (VRAM read/write address, register
  write, CRAM write), data-port buffer lag, auto-increment wrap, status
  read-and-reset, second-byte flag cleared by data/control-port reads;
- PSG latch protocol surface, controller-port defaults, documented port
  mirrors, and the 8-bit port mask that matches the Z80 reference model.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from sms_platform_v1 import (  # noqa: E402
    ROM_BANK_SIZE,
    SMSPlatformError,
    SmsMachine,
    classify,
)

SIZE_CODES_BY_BANKS = {1: 0xB, 2: 0xC, 3: 0xD, 4: 0xE, 8: 0xF, 16: 0x0, 32: 0x1, 64: 0x2}


def build_rom(
    banks: int,
    *,
    header: bool = True,
    header_offset: int = 0x7FF0,
    region: int = 4,
    size_code: int | None = None,
    checksum_valid: bool = True,
) -> bytes:
    rom = bytearray(banks * ROM_BANK_SIZE)
    for index in range(len(rom)):
        rom[index] = (index >> 8) & 0xFF  # each byte = high byte of its address
    if header:
        if len(rom) < header_offset + 16:
            raise AssertionError("header does not fit")
        rom[header_offset:header_offset + 8] = b"TMR SEGA"
        if size_code is None:
            size_code = SIZE_CODES_BY_BANKS[banks]
        rom[header_offset + 0x0F] = (region << 4) | size_code
        if checksum_valid:
            rom[header_offset + 0x0A] = 0
            rom[header_offset + 0x0B] = 0
            stored = sum(rom) & 0xFFFF
            rom[header_offset + 0x0A] = stored & 0xFF
            rom[header_offset + 0x0B] = stored >> 8
        else:
            rom[header_offset + 0x0A] = 0x00
            rom[header_offset + 0x0B] = 0x00
    return bytes(rom)


def expect_fail(label: str, action) -> None:
    try:
        action()
    except SMSPlatformError:
        print(f"PASS reject: {label}")
        return
    raise AssertionError(f"{label}: accepted")


def main() -> int:
    tests = 0

    # -- ROM ingestion --------------------------------------------------------
    info = classify(build_rom(4, region=4, size_code=0xE))
    assert info.header_present and info.header_offset == 0x7FF0
    assert info.region == "sms-export" and info.size_code == 0xE
    assert info.declared_bytes == 64 * 1024 and info.checksum_valid
    assert info.rom_banks == 4
    print("PASS classify-header-export-64k")
    tests += 1

    info = classify(build_rom(2, header=False))
    assert not info.header_present and info.header_offset is None
    assert info.region is None and not info.checksum_valid and info.rom_banks == 2
    print("PASS classify-headerless")
    tests += 1

    info = classify(build_rom(1, header_offset=0x3FF0))
    assert info.header_present and info.header_offset == 0x3FF0 and info.region == "sms-export"
    print("PASS classify-header-at-3ff0")
    tests += 1

    info = classify(build_rom(4, region=5))
    assert info.region == "gg-japan" and info.checksum_valid
    print("PASS classify-region-nibble")
    tests += 1

    info = classify(build_rom(4, checksum_valid=False))
    assert info.header_present and not info.checksum_valid
    print("PASS classify-checksum-mismatch")
    tests += 1

    expect_fail("size-not-multiple-of-16k", lambda: classify(bytes(0x6000)))
    tests += 1
    expect_fail("size-over-1mib", lambda: classify(bytes(0x200000)))
    tests += 1

    def undocumented_size_code() -> None:
        rom = bytearray(build_rom(4))
        rom[0x7FF0 + 0x0F] = (4 << 4) | 0x3
        classify(bytes(rom))

    expect_fail("undocumented-size-code", undocumented_size_code)
    tests += 1

    # -- Sega mapper ----------------------------------------------------------
    machine = SmsMachine(build_rom(8, header=False))
    assert machine.read_memory(0x0000) == 0x00 and machine.read_memory(0x03FF) == 0x03
    assert machine.read_memory(0x0400) == 0x04  # reset state: slot 0 = bank 0
    assert machine.read_memory(0x4000) == 0x40  # reset state: slot 1 = bank 1
    assert machine.read_memory(0x8000) == 0x80  # reset state: slot 2 = bank 2
    print("PASS mapper-reset-state")
    tests += 1

    machine.write_memory(0xFFFD, 3)
    assert machine.read_memory(0x0400) == 0xC4  # slot 0 -> bank 3
    assert machine.read_memory(0x0000) == 0x00  # first 1 KiB stays fixed
    print("PASS mapper-slot0-bank")
    tests += 1

    machine.write_memory(0xFFFF, 0)
    assert machine.read_memory(0x8000) == 0x00  # slot 2 -> bank 0
    print("PASS mapper-slot2-bank")
    tests += 1

    machine.write_memory(0xFFFC, 0x02)  # bank shift 0x10
    machine.write_memory(0xFFFD, 0x01)
    assert machine.read_memory(0x0400) == 0x44  # bank (1 + 0x10) % 8 = 1
    print("PASS mapper-bank-shift")
    tests += 1

    small = SmsMachine(build_rom(4, header=False))
    small.write_memory(0xFFFE, 0x06)
    assert small.read_memory(0x4000) == 0x80  # bank 6 % 4 = 2 (mirroring)
    print("PASS mapper-bank-mirroring")
    tests += 1

    machine.write_memory(0xFFFF, 0)  # slot 2 = bank 0
    expect_fail("rom-write-protected", lambda: machine.write_memory(0x8000, 0xEE))
    machine.write_memory(0xFFFC, 0x80)  # documented "ROM write" enable
    machine.write_memory(0x8000, 0xEE)
    assert machine.read_memory(0x8000) == 0xEE
    print("PASS mapper-rom-write-enable")
    tests += 1

    machine.write_memory(0xFFFC, 0x08)
    expect_fail("cart-ram-slot2-absent", lambda: machine.read_memory(0x8000))
    machine.write_memory(0xFFFC, 0x10)
    expect_fail("cart-ram-over-ram-absent", lambda: machine.read_memory(0xC000))
    print("PASS mapper-cart-ram-fail-closed")
    tests += 1

    # -- memory map -----------------------------------------------------------
    machine = SmsMachine(build_rom(4, header=False))
    machine.write_memory(0xC000, 0xAB)
    machine.write_memory(0xDFFF, 0xCD)
    assert machine.read_memory(0xC000) == 0xAB and machine.read_memory(0xE000) == 0xAB
    assert machine.read_memory(0xDFFF) == 0xCD and machine.read_memory(0xFFFF) == 0xCD
    print("PASS ram-mirror")
    tests += 1

    machine.write_memory(0xFFFD, 5)
    assert machine.read_memory(0xFFFD) == 5  # documented write-through to RAM
    assert machine.read_memory(0x0400) == 0x44  # slot 0 -> bank 5 % 4 = bank 1
    print("PASS control-register-write-through")
    tests += 1

    machine.write_memory(0xFFF8, 0x0C)
    assert machine.glasses_control == 0x0C and machine.read_memory(0xFFF8) == 0x0C
    print("PASS glasses-control-write-through")
    tests += 1

    machine.port_out(0x3E, 0x10)  # documented: bit 4 disables RAM
    expect_fail("ram-disabled", lambda: machine.read_memory(0xC000))
    machine.port_out(0x3E, 0x00)
    assert machine.read_memory(0xC000) == 0xAB
    machine.port_out(0x3E, 0x02)  # documented: bit 1 disables the cartridge
    expect_fail("cartridge-disabled", lambda: machine.read_memory(0x0000))
    machine.port_out(0x3E, 0x00)
    assert machine.read_memory(0x0000) == 0x00
    print("PASS memory-enables-3e")
    tests += 1

    # -- VDP ------------------------------------------------------------------
    vdp = machine.vdp
    vdp.control_write(0x12)
    vdp.control_write(0x75)  # code 01, address 0x3512 (VRAM write)
    assert vdp.code == 0x01 and vdp.address == 0x3512
    vdp.data_write(0xAB)
    assert vdp.vram[0x3512] == 0xAB and vdp.address == 0x3513
    vdp.data_write(0xCD)
    assert vdp.vram[0x3513] == 0xCD
    print("PASS vdp-vram-write")
    tests += 1

    vdp.control_write(0x9F)
    vdp.control_write(0x81)  # register write: register 1 <- 0x9F
    assert vdp.registers[1] == 0x9F
    vdp.control_write(0x05)
    vdp.control_write(0x8A)
    assert vdp.registers[10] == 0x05
    print("PASS vdp-register-write")
    tests += 1

    vdp.vram[0x0000] = 0x11
    vdp.vram[0x0001] = 0x22
    vdp.control_write(0x00)
    vdp.control_write(0x00)  # code 00, address 0x0000 (VRAM read)
    assert vdp.data_read() == 0x11  # prefetch + documented buffer lag
    assert vdp.data_read() == 0x22
    print("PASS vdp-vram-read-buffer-lag")
    tests += 1

    vdp.control_write(0x00)
    vdp.control_write(0xC0)  # code 11, address 0 (CRAM write)
    vdp.data_write(0x12)
    assert vdp.cram[0] == 0x12 and vdp.vram[0] == 0x11  # VRAM untouched
    vdp.data_write(0x34)
    assert vdp.cram[1] == 0x34
    print("PASS vdp-cram-write")
    tests += 1

    vdp.set_status(vblank=True, sprite_overflow=True)
    assert vdp.control_read() == 0xC0  # 0x80 | 0x40
    assert vdp.control_read() == 0x00  # documented: flags reset on read
    print("PASS vdp-status-read-reset")
    tests += 1

    vdp.control_write(0x34)  # first byte only
    vdp.data_write(0x55)  # documented: clears the second-byte flag
    vdp.control_write(0x56)  # must be treated as a NEW first byte
    vdp.control_write(0x78)  # code 01, address 0x3856
    assert vdp.code == 0x01 and vdp.address == 0x3856
    print("PASS vdp-second-byte-flag-clear")
    tests += 1

    # -- PSG / joysticks / port decode ----------------------------------------
    machine.psg.write(0x90)  # latch: register 1 (0x10 >> 4)
    machine.psg.write(0x0F)
    assert machine.psg.registers[1] == 0x0F
    machine.psg.write(0xC0)  # latch: register 4 (0x40 >> 4)
    machine.psg.write(0x0B)
    assert machine.psg.registers[4] == 0x0B
    print("PASS psg-latch-protocol")
    tests += 1

    machine.port_out(0x7F, 0x90)
    machine.port_out(0x7F, 0x0F)
    assert machine.psg.registers[1] == 0x0F  # PSG on the odd $41-$7f mirrors
    print("PASS psg-port-mirror")
    tests += 1

    assert machine.port_in(0xDC) == 0xFF and machine.port_in(0xDD) == 0xFF
    machine.joysticks.set_port_a(0xFE)
    machine.joysticks.set_port_b(0x7F)
    assert machine.port_in(0xDC) == 0xFE and machine.port_in(0xDD) == 0x7F
    print("PASS joystick-surfaces")
    tests += 1

    assert machine.port_in(0x3F) == 0x0F  # documented input-only default
    machine.port_out(0x01, 0x55)  # odd $01-$3f mirror of port $3f
    assert machine.port_in(0x3F) == 0x55
    machine.port_out(0x02, 0x10)  # even $00-$3e mirror of port $3e
    assert machine.port_in(0x3E) == 0x10
    print("PASS port-3e-3f-mirrors")
    tests += 1

    machine.port_out(0x02, 0x00)
    machine.port_out(0x01BE, 0xAB)  # 8-bit port mask: 0x01BE -> $be data port
    assert machine.vdp.vram[0x3856] == 0xAB
    assert machine.port_in(0x01BF) == 0x00  # 0x01BF -> $bf status
    print("PASS port-8bit-mask")
    tests += 1

    print(f"OPENRECOMP_SMS_PLATFORM_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
