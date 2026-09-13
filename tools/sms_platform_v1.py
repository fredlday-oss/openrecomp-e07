#!/usr/bin/env python3
"""Master System ROM ingestion + banking + I/O platform contract (P1-22).

Implements the documented Sega Master System platform surface for
deterministic headless tests:

- flat ROM ingestion with the documented optional header (TMR SEGA at
  $7ff0/$3ff0/$1ff0, little-endian checksum word, product code, version,
  region + size nibbles at $7fff) and fail-closed size rules;
- the documented Sega mapper (16 KiB banks, three slots, $fffc-$ffff
  control registers, fixed first 1 KiB, bank shift, RAM enables,
  "ROM write" enable, ROM mirroring, 315-5235 reset state);
- the documented memory map: RAM at $c000-$dfff mirrored to $e000-$ffff,
  $fff8-$fffb 3D-glasses control and $fffc-$ffff mapper control
  write-through to the RAM mirror (reads return RAM);
- the documented Z80 I/O port map (only A7-A0 decoded): $3e memory
  enables, $3f joystick-port control, $7e/$7f light-phaser/PSG, $be/$bf
  VDP data/control, $dc/$dd controller ports, with the documented mirror
  sets (odd $01-$3f, odd $41-$7f, odd $81-$bf, even $c0-$fe, odd $c1-$ff);
- the documented VDP control-port protocol (two-byte control words, code
  register 00/01/10/11 = VRAM read/write address, register write, CRAM
  write address; data-port read buffer lag; auto-increment wrapping at
  $3fff; status flags read-and-reset; second-byte flag cleared by data
  port and control-port reads);
- a deterministic PSG write surface (latched register protocol; audio
  synthesis deferred) and controller-port surfaces (1 = not pressed).

Facts follow the public SMS Power! development pages (MemoryMap, Mappers,
ROMHeader, ControlPort, PeripheralPorts, RAM) and the official SMS
developer documents, quoted in the P1-22 evidence record.

Deferred (documented, out of Phase 1): cycle-perfect VDP/audio, BIOS ROM,
3D-glasses hardware, light phaser, cartridge RAM (classified, fail closed),
FM unit, TH-pin hardware interaction. Commercial ROM bytes never enter this
repository; the local primary SMS image is an external verification input
(metadata only, per `.openrecomp-phase1/ROM_PATHS.md`).
"""
from __future__ import annotations

from dataclasses import dataclass

ROM_BANK_SIZE = 0x4000
MAX_ROM_SIZE = 0x100000
SYSTEM_RAM_SIZE = 0x2000

HEADER_MARKER = b"TMR SEGA"
HEADER_OFFSETS = (0x7FF0, 0x3FF0, 0x1FF0)

REGION_NAMES = {
    0x3: "sms-japan",
    0x4: "sms-export",
    0x5: "gg-japan",
    0x6: "gg-export",
    0x7: "gg-international",
}

SIZE_CODES = {
    0xA: 8 * 1024,
    0xB: 16 * 1024,
    0xC: 32 * 1024,
    0xD: 48 * 1024,
    0xE: 64 * 1024,
    0xF: 128 * 1024,
    0x0: 256 * 1024,
    0x1: 512 * 1024,
    0x2: 1024 * 1024,
}


class SMSPlatformError(ValueError):
    """Fail-closed SMS platform error."""


@dataclass(frozen=True)
class SmsClassification:
    header_present: bool
    header_offset: int | None
    checksum_stored: int | None
    checksum_valid: bool
    region: str | None
    size_code: int | None
    declared_bytes: int | None
    rom_bytes: int
    rom_banks: int


def classify(data: bytes) -> SmsClassification:
    if not isinstance(data, (bytes, bytearray)):
        raise SMSPlatformError("ROM image must be bytes")
    if len(data) % ROM_BANK_SIZE != 0:
        raise SMSPlatformError(f"ROM size must be a multiple of {ROM_BANK_SIZE} bytes, got {len(data)}")
    if not (ROM_BANK_SIZE <= len(data) <= MAX_ROM_SIZE):
        raise SMSPlatformError(f"ROM size must be between {ROM_BANK_SIZE} and {MAX_ROM_SIZE} bytes, got {len(data)}")
    header_offset = None
    for offset in HEADER_OFFSETS:
        if len(data) >= offset + 16 and data[offset:offset + 8] == HEADER_MARKER:
            header_offset = offset
            break
    checksum_stored = None
    checksum_valid = False
    region = None
    size_code = None
    declared_bytes = None
    if header_offset is not None:
        checksum_stored = data[header_offset + 0x0A] | (data[header_offset + 0x0B] << 8)
        computed = 0
        for index, byte in enumerate(data):
            if header_offset + 0x0A <= index < header_offset + 0x0C:
                continue
            computed = (computed + byte) & 0xFFFF
        checksum_valid = computed == checksum_stored
        header_byte = data[header_offset + 0x0F]
        region_code = (header_byte >> 4) & 0x0F
        size_code = header_byte & 0x0F
        region = REGION_NAMES.get(region_code, f"unknown-0x{region_code:x}")
        if size_code in SIZE_CODES:
            declared_bytes = SIZE_CODES[size_code]
        elif region_code in REGION_NAMES:
            raise SMSPlatformError(f"undocumented ROM size code 0x{size_code:x} in the header")
    return SmsClassification(
        header_present=header_offset is not None,
        header_offset=header_offset,
        checksum_stored=checksum_stored,
        checksum_valid=checksum_valid,
        region=region,
        size_code=size_code,
        declared_bytes=declared_bytes,
        rom_bytes=len(data),
        rom_banks=len(data) // ROM_BANK_SIZE,
    )


class SmsMapper:
    """The documented Sega mapper (write-through control registers included)."""

    def __init__(self, rom: bytes) -> None:
        info = classify(rom)
        self.rom = bytearray(rom)
        self.banks = info.rom_banks
        self.fffc = 0x00
        self.slot = [0, 1, 2]  # documented 315-5235 power-up reset state

    def _bank(self, slot_index: int) -> int:
        return self.slot[slot_index] % self.banks  # documented ROM mirroring

    def _offset(self, slot_index: int, address: int) -> int:
        return self._bank(slot_index) * ROM_BANK_SIZE + (address & 0x3FFF)

    def write_fffc(self, value: int) -> None:
        self.fffc = value & 0xFF

    def write_bank(self, slot_index: int, value: int) -> None:
        # documented bank shift: (bank + shift) wraps the 8-bit bank space
        shift = (self.fffc & 0x03) * 8
        self.slot[slot_index] = ((value & 0xFF) + shift) % 256

    def read(self, address: int) -> int:
        if address < 0x0400:
            return self.rom[address]  # fixed first 1 KiB (interrupt vectors)
        if address < 0x4000:
            return self.rom[self._offset(0, address)]
        if address < 0x8000:
            return self.rom[self._offset(1, address)]
        if self.fffc & 0x08:
            raise SMSPlatformError("cartridge RAM is mapped to slot 2 but no cartridge RAM is present")
        return self.rom[self._offset(2, address)]

    def write(self, address: int, value: int) -> None:
        if not (self.fffc & 0x80):
            raise SMSPlatformError("ROM write is disabled (documented $fffc bit 7 write protect)")
        if address < 0x0400:
            self.rom[address] = value & 0xFF
        elif address < 0x4000:
            self.rom[self._offset(0, address)] = value & 0xFF
        elif address < 0x8000:
            self.rom[self._offset(1, address)] = value & 0xFF
        elif address < 0xC000:
            if self.fffc & 0x08:
                raise SMSPlatformError("cartridge RAM is mapped to slot 2 but no cartridge RAM is present")
            self.rom[self._offset(2, address)] = value & 0xFF
        else:
            raise SMSPlatformError(f"mapper write outside the cartridge window: 0x{address:x}")


class SmsVdp:
    """Deterministic VDP port surface (documented control/data protocol)."""

    VRAM_SIZE = 0x4000
    CRAM_SIZE = 64
    REGISTER_COUNT = 16

    def __init__(self) -> None:
        self.vram = bytearray(self.VRAM_SIZE)
        self.cram = bytearray(self.CRAM_SIZE)
        self.registers = bytearray(self.REGISTER_COUNT)
        self.address = 0
        self.code = 0
        self.latch = 0
        self.buffer = 0
        self.second_pending = False
        self.status_flags = 0  # bit 7 VBlank, 6 sprite overflow, 5 collision
        self.fifth_sprite = 0

    def set_status(self, vblank: bool = False, sprite_overflow: bool = False, collision: bool = False) -> None:
        self.status_flags = (0x80 if vblank else 0) | (0x40 if sprite_overflow else 0) | (0x20 if collision else 0)

    def control_write(self, value: int) -> None:
        if self.second_pending:
            self.second_pending = False
            self.code = (value >> 6) & 0x03
            self.address = ((value & 0x3F) << 8) | self.latch
            if self.code == 0:
                # documented: VRAM read address setup prefetches and increments
                self.buffer = self.vram[self.address]
                self.address = (self.address + 1) & 0x3FFF
            elif self.code == 2:
                # documented register write: first byte = data (A7-A0),
                # register number = address bits 11-8 (second byte bits 3-0)
                self.registers[(self.address >> 8) & 0x0F] = self.latch
        else:
            self.latch = value & 0xFF
            self.second_pending = True

    def data_read(self) -> int:
        self.second_pending = False  # documented: data port access clears the flag
        value = self.buffer
        self.buffer = self.vram[self.address]
        self.address = (self.address + 1) & 0x3FFF
        return value

    def data_write(self, value: int) -> None:
        self.second_pending = False
        if self.code == 0x03:
            self.cram[self.address & (self.CRAM_SIZE - 1)] = value & 0xFF
        else:
            self.vram[self.address] = value & 0xFF
        self.buffer = value & 0xFF
        self.address = (self.address + 1) & 0x3FFF

    def control_read(self) -> int:
        self.second_pending = False
        value = (self.status_flags & 0xE0) | (self.fifth_sprite & 0x1F)
        self.status_flags = 0  # documented: flags reset when read
        return value


class SmsPsg:
    """Documented PSG write surface (audio synthesis deferred)."""

    REGISTER_COUNT = 8

    def __init__(self) -> None:
        self.latch = 0
        self.registers = bytearray(self.REGISTER_COUNT)

    def write(self, value: int) -> None:
        if value & 0x80:
            self.latch = value & 0x7F  # bits 6-4 select the register, 3-0 partial data
        else:
            self.registers[(self.latch >> 4) & (self.REGISTER_COUNT - 1)] = value & 0xFF


class SmsJoysticks:
    """Deterministic controller-port surfaces (1 = not pressed)."""

    def __init__(self) -> None:
        self.port_a = 0xFF  # $dc: B down/up, A TR/TL, A right/left/down/up
        self.port_b = 0xFF  # $dd: TH pins, CONT, reset, B TR/TL/right/left

    def set_port_a(self, value: int) -> None:
        self.port_a = value & 0xFF

    def set_port_b(self, value: int) -> None:
        self.port_b = value & 0xFF


def _decode_port(port: int) -> str:
    """Documented SMS port decode: only A7-A0 are considered; A0 selects
    within each of the four 0x40-wide groups."""
    port &= 0xFF
    if port < 0x40:
        return "3e" if (port & 1) == 0 else "3f"
    if port < 0x80:
        return "7e" if (port & 1) == 0 else "7f"
    if port < 0xC0:
        return "be" if (port & 1) == 0 else "bf"
    return "dc" if (port & 1) == 0 else "dd"


class SmsMachine:
    """Documented SMS memory map + I/O ports over the Sega mapper."""

    def __init__(self, rom: bytes) -> None:
        self.classification = classify(rom)
        self.mapper = SmsMapper(rom)
        self.ram = bytearray(SYSTEM_RAM_SIZE)
        self.memory_enables = 0x00  # documented default: everything enabled
        self.port_3f = 0x0F  # documented default: TH/TR input-only state
        self.glasses_control = 0
        self.vdp = SmsVdp()
        self.psg = SmsPsg()
        self.joysticks = SmsJoysticks()
        self.gun_vertical = 0xFF  # light phaser unconnected
        self.gun_horizontal = 0xFF
        self.port_trace = bytearray(256)  # flat last-write view of the port space

    # -- memory -----------------------------------------------------------
    def read_memory(self, address: int) -> int:
        if address < 0xC000:
            if self.memory_enables & 0x02:
                raise SMSPlatformError("the cartridge slot is disabled (port $3e bit 1)")
            return self.mapper.read(address & 0xFFFF)
        if self.memory_enables & 0x10:
            raise SMSPlatformError("system RAM is disabled (port $3e bit 4)")
        if self.mapper.fffc & 0x10:
            raise SMSPlatformError("cartridge RAM is mapped over $c000-$ffff but no cartridge RAM is present")
        return self.ram[(address - 0xC000) & 0x1FFF]

    def write_memory(self, address: int, value: int) -> None:
        value &= 0xFF
        if address < 0xC000:
            if self.memory_enables & 0x02:
                raise SMSPlatformError("the cartridge slot is disabled (port $3e bit 1)")
            self.mapper.write(address & 0xFFFF, value)
            return
        if self.memory_enables & 0x10:
            raise SMSPlatformError("system RAM is disabled (port $3e bit 4)")
        if self.mapper.fffc & 0x10:
            raise SMSPlatformError("cartridge RAM is mapped over $c000-$ffff but no cartridge RAM is present")
        address &= 0xFFFF
        if 0xFFF8 <= address <= 0xFFFB:
            self.glasses_control = value
        elif address == 0xFFFC:
            self.mapper.write_fffc(value)
        elif address == 0xFFFD:
            self.mapper.write_bank(0, value)
        elif address == 0xFFFE:
            self.mapper.write_bank(1, value)
        elif address == 0xFFFF:
            self.mapper.write_bank(2, value)
        # documented: control registers overlap the RAM mirror; writes affect
        # both the device and RAM, reads return the RAM copy
        self.ram[(address - 0xC000) & 0x1FFF] = value

    # -- I/O ports ---------------------------------------------------------
    def port_out(self, address: int, value: int) -> None:
        device = _decode_port(address)
        value &= 0xFF
        self.port_trace[address & 0xFF] = value  # flat view (CPU-visible port space)
        if device == "3e":
            self.memory_enables = value
        elif device == "3f":
            self.port_3f = value
        elif device == "7f":
            self.psg.write(value)
        elif device == "be":
            self.vdp.data_write(value)
        elif device == "bf":
            self.vdp.control_write(value)
        # $7e/$dc/$dd are documented input surfaces; writes are ignored

    def port_in(self, address: int) -> int:
        device = _decode_port(address)
        if device == "3e":
            return self.memory_enables
        if device == "3f":
            return self.port_3f
        if device == "7e":
            return self.gun_vertical
        if device == "7f":
            return self.gun_horizontal
        if device == "be":
            return self.vdp.data_read()
        if device == "bf":
            return self.vdp.control_read()
        if device == "dc":
            return self.joysticks.port_a
        return self.joysticks.port_b


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: sms_platform_v1.py <rom.sms>", file=__import__("sys").stderr)
        return 2
    try:
        data = __import__("pathlib").Path(argv[1]).read_bytes()
        info = classify(data)
    except (OSError, SMSPlatformError) as exc:
        print(f"OPENRECOMP_SMS_PLATFORM_V1=FAIL: {exc}", file=__import__("sys").stderr)
        return 2
    print(f"SMS_ROM_HEADER_PRESENT={int(info.header_present)}")
    print(f"SMS_ROM_REGION={info.region}")
    print(f"SMS_ROM_BANKS={info.rom_banks}")
    print(f"SMS_ROM_CHECKSUM_VALID={int(info.checksum_valid)}")
    print("OPENRECOMP_SMS_PLATFORM_V1=PASS")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv))
