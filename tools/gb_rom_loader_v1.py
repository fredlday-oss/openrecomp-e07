#!/usr/bin/env python3
"""Game Boy ROM ingestion + memory/platform contract (P1-14).

Parses and validates the documented Game Boy cartridge header, classifies the
cartridge (mapper, RAM, battery, CGB mode) and provides the documented memory
map plus a fail-closed mapper interface.

All facts follow the publicly documented Game Boy hardware behaviour
("Pan Docs" cartridge header and MBC sections):

- header at 0x0100..0x014F: entry point, title, CGB flag (0x80 = CGB-capable,
  0xC0 = CGB-only), SGB flag, cartridge type, ROM/RAM size codes, destination,
  licensee, mask-ROM version, header checksum, global checksum;
- header checksum: x = 0; for i in 0x0134..0x014C: x = x - byte[i] - 1;
  byte[0x014D] must equal x & 0xFF;
- documented cartridge-type -> mapper table (ROM ONLY, MBC1/2/3/5, MMM01,
  HuC1/3, MBC6/7, POCKET CAMERA, TAMA5, ...);
- documented ROM/RAM size codes;
- memory map: ROM 0x0000-0x7FFF (banked at 0x4000-0x7FFF), VRAM 0x8000-0x9FFF,
  cartridge RAM 0xA000-0xBFFF, WRAM 0xC000-0xDFFF with the documented echo at
  0xE000-0xFDFF, OAM 0xFE00-0xFE9F, I/O 0xFF00-0xFF7F, HRAM 0xFF80-0xFFFE,
  IE at 0xFFFF;
- MBC1 banking: RAM enable 0x0000-0x1FFF (low nibble 0x0A), ROM bank
  0x2000-0x3FFF (5 bits, 0 selects bank 1), RAM bank 0x4000-0x5FFF (2 bits),
  banking mode 0x6000-0x7FFF (0 = simple, 1 = advanced).

The loader never verifies the Nintendo logo contents (proprietary material);
it records presence only. Battery-backed persistence is out of scope and
recorded in the classification. All inputs here are synthetic/original; local
commercial ROMs remain external verification inputs per
`.openrecomp-phase1/ROM_PATHS.md`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

HEADER_OFFSET = 0x0100
HEADER_SIZE = 0x50
MIN_ROM_SIZE = 0x150

ROM_BANK_SIZE = 0x4000
RAM_BANK_SIZE = 0x2000

# Documented cartridge-type -> (mapper, has_ram, has_battery, extra)
CARTRIDGE_TYPES = {
    0x00: ("none", False, False, ""),
    0x01: ("mbc1", False, False, ""),
    0x02: ("mbc1", True, False, ""),
    0x03: ("mbc1", True, True, ""),
    0x05: ("mbc2", False, False, ""),
    0x06: ("mbc2", False, True, ""),
    0x08: ("none", True, False, ""),
    0x09: ("none", True, True, ""),
    0x0B: ("mmm01", False, False, ""),
    0x0C: ("mmm01", True, False, ""),
    0x0D: ("mmm01", True, True, ""),
    0x0F: ("mbc3", False, True, "timer"),
    0x10: ("mbc3", True, True, "timer"),
    0x11: ("mbc3", False, False, ""),
    0x12: ("mbc3", True, False, ""),
    0x13: ("mbc3", True, True, ""),
    0x19: ("mbc5", False, False, ""),
    0x1A: ("mbc5", True, False, ""),
    0x1B: ("mbc5", True, True, ""),
    0x1C: ("mbc5", False, False, "rumble"),
    0x1D: ("mbc5", True, False, "rumble"),
    0x1E: ("mbc5", True, True, "rumble"),
    0x20: ("mbc6", True, True, ""),
    0x22: ("mbc7", True, True, "sensor+rumble"),
    0xFC: ("camera", True, True, ""),
    0xFD: ("tama5", False, False, ""),
    0xFE: ("huc3", True, True, ""),
    0xFF: ("huc1", True, True, ""),
}

ROM_SIZE_CODES = {
    0x00: (32 * 1024, 2),
    0x01: (64 * 1024, 4),
    0x02: (128 * 1024, 8),
    0x03: (256 * 1024, 16),
    0x04: (512 * 1024, 32),
    0x05: (1024 * 1024, 64),
    0x06: (2 * 1024 * 1024, 128),
    0x07: (4 * 1024 * 1024, 256),
    0x08: (8 * 1024 * 1024, 512),
    0x52: (1152 * 1024, 72),
    0x53: (1280 * 1024, 80),
    0x54: (1536 * 1024, 96),
}

RAM_SIZE_CODES = {
    0x00: (0, 0),
    0x01: (2 * 1024, 1),
    0x02: (8 * 1024, 1),
    0x03: (32 * 1024, 4),
    0x04: (128 * 1024, 16),
    0x05: (64 * 1024, 8),
}


class GBROMError(ValueError):
    """Fail-closed Game Boy ROM ingestion error."""


@dataclass(frozen=True)
class GBHeader:
    entry_point: int
    title: str
    cgb_flag: int
    sgb_flag: int
    cartridge_type: int
    rom_size_code: int
    ram_size_code: int
    destination_code: int
    old_licensee: int
    mask_rom_version: int
    header_checksum: int
    global_checksum: int
    logo_present: bool


@dataclass(frozen=True)
class GBClassification:
    mapper: str
    has_ram: bool
    has_battery: bool
    extra: str
    cgb_mode: str
    rom_bytes: int
    rom_banks: int
    ram_bytes: int
    ram_banks: int
    header_checksum_valid: bool


def parse_header(data: bytes) -> GBHeader:
    if not isinstance(data, (bytes, bytearray)) or len(data) < MIN_ROM_SIZE:
        raise GBROMError(f"ROM image must be at least {MIN_ROM_SIZE:#x} bytes, got {len(data) if data else 0}")
    header = data[HEADER_OFFSET:HEADER_OFFSET + HEADER_SIZE]
    title_bytes = bytes(header[0x34:0x43]).rstrip(b"\x00")
    try:
        title = title_bytes.decode("ascii")
    except UnicodeDecodeError as exc:
        raise GBROMError("title is not ASCII") from exc
    return GBHeader(
        entry_point=(header[0x00] | (header[0x01] << 8)),
        title=title,
        cgb_flag=header[0x43],
        sgb_flag=header[0x46],
        cartridge_type=header[0x47],
        rom_size_code=header[0x48],
        ram_size_code=header[0x49],
        destination_code=header[0x4A],
        old_licensee=header[0x4B],
        mask_rom_version=header[0x4C],
        header_checksum=header[0x4D],
        global_checksum=(header[0x4E] << 8) | header[0x4F],
        logo_present=any(header[0x04:0x34]),
    )


def compute_header_checksum(data: bytes) -> int:
    if len(data) < HEADER_OFFSET + 0x4E:
        raise GBROMError("ROM image too short to compute the header checksum")
    value = 0
    for byte in data[0x0134:0x014D]:
        value = (value - byte - 1) & 0xFF
    return value


def classify(data: bytes) -> GBClassification:
    header = parse_header(data)
    if header.cartridge_type not in CARTRIDGE_TYPES:
        raise GBROMError(f"undocumented cartridge type 0x{header.cartridge_type:02X}")
    mapper, has_ram, has_battery, extra = CARTRIDGE_TYPES[header.cartridge_type]
    if header.rom_size_code not in ROM_SIZE_CODES:
        raise GBROMError(f"undocumented ROM size code 0x{header.rom_size_code:02X}")
    if header.ram_size_code not in RAM_SIZE_CODES:
        raise GBROMError(f"undocumented RAM size code 0x{header.ram_size_code:02X}")
    rom_bytes, rom_banks = ROM_SIZE_CODES[header.rom_size_code]
    if len(data) < rom_bytes:
        raise GBROMError(f"ROM image is {len(data)} bytes, header declares {rom_bytes}")
    ram_bytes, ram_banks = RAM_SIZE_CODES[header.ram_size_code]
    if has_ram and ram_bytes == 0:
        raise GBROMError("cartridge type declares RAM but the RAM size code declares none")
    checksum_valid = compute_header_checksum(data) == header.header_checksum
    if not checksum_valid:
        raise GBROMError("header checksum mismatch (documented 0x0134..0x014C accumulation)")
    if header.cgb_flag == 0x80:
        cgb_mode = "cgb-compatible"
    elif header.cgb_flag == 0xC0:
        cgb_mode = "cgb-only"
    else:
        cgb_mode = "dmg"
    return GBClassification(
        mapper=mapper,
        has_ram=has_ram,
        has_battery=has_battery,
        extra=extra,
        cgb_mode=cgb_mode,
        rom_bytes=rom_bytes,
        rom_banks=rom_banks,
        ram_bytes=ram_bytes,
        ram_banks=ram_banks,
        header_checksum_valid=checksum_valid,
    )


class Mapper:
    """Documented cartridge read/write surface (fail closed)."""

    def read_rom(self, address: int) -> int:
        raise NotImplementedError

    def write(self, address: int, value: int) -> None:
        raise NotImplementedError

    def read_ram(self, address: int) -> int:
        raise GBROMError("this cartridge has no RAM")

    def write_ram(self, address: int, value: int) -> None:
        raise GBROMError("this cartridge has no RAM")


class RomOnlyMapper(Mapper):
    def __init__(self, rom: bytes) -> None:
        self.rom = bytes(rom)

    def read_rom(self, address: int) -> int:
        if not (0 <= address < len(self.rom)):
            raise GBROMError(f"ROM read out of range: 0x{address:x}")
        return self.rom[address]

    def write(self, address: int, value: int) -> None:
        raise GBROMError(f"ROM-only cartridge: write to 0x{address:x} is not mappable")


class Mbc1Mapper(Mapper):
    """Documented MBC1 behaviour (no RTC; battery persistence out of scope)."""

    def __init__(self, rom: bytes, ram_banks: int) -> None:
        self.rom = bytes(rom)
        self.ram = bytearray(ram_banks * RAM_BANK_SIZE) if ram_banks else bytearray()
        self.ram_enabled = False
        self.rom_bank = 1  # documented: bank register 0 selects bank 1
        self.ram_bank = 0
        self.advanced_mode = False

    def read_rom(self, address: int) -> int:
        if not (0 <= address < len(self.rom)):
            raise GBROMError(f"ROM read out of range: 0x{address:x}")
        if address < 0x4000:
            return self.rom[address]
        bank = self.rom_bank if not self.advanced_mode else self.rom_bank & 0x1F
        offset = address - 0x4000 + bank * 0x4000
        if offset >= len(self.rom):
            raise GBROMError(f"ROM bank {bank} is outside the image (advanced-mode read 0x{address:x})")
        return self.rom[offset]

    def write(self, address: int, value: int) -> None:
        if 0x0000 <= address < 0x2000:
            self.ram_enabled = (value & 0x0F) == 0x0A
        elif 0x2000 <= address < 0x4000:
            bank = value & 0x1F
            self.rom_bank = 1 if bank == 0 else bank
        elif 0x4000 <= address < 0x6000:
            self.ram_bank = value & 0x03
        elif 0x6000 <= address < 0x8000:
            self.advanced_mode = bool(value & 0x01)
        else:
            raise GBROMError(f"MBC1 write outside the documented 0x0000-0x7FFF window: 0x{address:x}")

    def read_ram(self, address: int) -> int:
        if not self.ram_enabled:
            raise GBROMError("MBC1 RAM is disabled")
        offset = address - 0xA000 + self.ram_bank * RAM_BANK_SIZE
        if not (0 <= offset < len(self.ram)):
            raise GBROMError(f"cartridge RAM read out of range: 0x{address:x}")
        return self.ram[offset]

    def write_ram(self, address: int, value: int) -> None:
        if not self.ram_enabled:
            raise GBROMError("MBC1 RAM is disabled")
        offset = address - 0xA000 + self.ram_bank * RAM_BANK_SIZE
        if not (0 <= offset < len(self.ram)):
            raise GBROMError(f"cartridge RAM write out of range: 0x{address:x}")
        self.ram[offset] = value & 0xFF


def make_mapper(data: bytes) -> Mapper:
    info = classify(data)
    if info.mapper == "none":
        if info.has_ram:
            raise GBROMError("ROM+RAM without a mapper is not mappable by this loader yet")
        return RomOnlyMapper(data)
    if info.mapper == "mbc1":
        return Mbc1Mapper(data, info.ram_banks)
    raise GBROMError(
        f"mapper '{info.mapper}' ({info.extra or 'no extras'}) is classified but not implemented; "
        "fail closed instead of guessing banking behaviour"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: gb_rom_loader_v1.py <rom.gb>", file=sys.stderr)
        return 2
    try:
        data = __import__("pathlib").Path(argv[1]).read_bytes()
        info = classify(data)
    except (OSError, GBROMError) as exc:
        print(f"OPENRECOMP_GB_ROM_V1=FAIL: {exc}", file=sys.stderr)
        return 2
    print(f"GB_ROM_MAPPER={info.mapper}")
    print(f"GB_ROM_CGB_MODE={info.cgb_mode}")
    print(f"GB_ROM_BANKS={info.rom_banks}")
    print(f"GB_ROM_RAM_BANKS={info.ram_banks}")
    print(f"GB_ROM_HEADER_CHECKSUM_VALID={int(info.header_checksum_valid)}")
    print("OPENRECOMP_GB_ROM_V1=PASS")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv))
