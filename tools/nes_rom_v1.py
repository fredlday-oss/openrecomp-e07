#!/usr/bin/env python3
"""NES ROM ingestion + NROM/mapper abstraction (P1-32).

Parses and validates the documented iNES / NES 2.0 cartridge header, classifies
the image (mapper, mirroring, battery, trainer, PRG/CHR sizes) and provides a
fail-closed mapper interface with the NROM (mapper 0) baseline.

All facts follow the publicly documented NESdev "iNES" reference (NES 2.0 is a
more recent extension of the same 16-byte header):

- header (16 bytes): bytes 0-3 = $4E $45 $53 $1A ("NES"), byte 4 = PRG ROM size
  in 16 KiB units, byte 5 = CHR ROM size in 8 KiB units (0 = CHR RAM);
- flags 6 (byte 6): bit 0 nametable arrangement (0 = vertical arrangement /
  "horizontal mirrored"; 1 = horizontal arrangement / "vertically mirrored"),
  bit 1 battery-backed PRG RAM, bit 2 512-byte trainer, bit 3 alternative
  nametable layout (4-screen), bits 7-4 lower nybble of the mapper number;
- flags 7 (byte 7): bit 0 VS Unisystem, bit 1 PlayChoice-10, bits 3-2 NES 2.0
  signature (== %10 means flags 8-15 are NES 2.0), bits 7-4 upper nybble;
- NES 2.0 recommended detection: byte 7 AND $0C == $08 and the declared ROM
  size fits the image; $0C == $04 is archaic iNES; $0C == $00 with bytes 12-15
  zero is iNES. NES 2.0 adds the mapper's highest nybble in flags 8 bits 3-0
  and logarithmic PRG RAM/CHR RAM sizes in flags 8/9/10/11.
- cartridge layout: header, optional 512-byte trainer (stored at $7000-$71FF in
  the ROM image), PRG ROM (16384 * x), CHR ROM (8192 * y);
- NROM (mapper 0): 16 KiB PRG ROM mirrored at $8000-$BFFF/$C000-$FFFF, or
  32 KiB PRG ROM at $8000-$FFFF; 8 KiB CHR ROM (or CHR RAM) at PPU
  $0000-$1FFF; no bank switching; optional battery PRG RAM at $6000-$7FFF.

The loader never interprets copyrighted PRG/CHR contents; local commercial
images remain external verification inputs per `.openrecomp-phase1/ROM_PATHS.md`
(metadata only, never copied into the repository). Unsupported mappers are
classifiable but fail closed at `make_mapper` instead of guessing banking.
"""
from __future__ import annotations

from dataclasses import dataclass

HEADER_SIZE = 16
MAGIC = b"NES\x1a"
TRAINER_SIZE = 512
PRG_BANK_SIZE = 16 * 1024
CHR_BANK_SIZE = 8 * 1024
MIN_ROM_SIZE = HEADER_SIZE

# Documented mapper names for the baseline this loader implements.
MAPPER_NAMES = {
    0: "nrom",
}


class NESROMError(ValueError):
    """Fail-closed NES ROM ingestion error."""


@dataclass(frozen=True)
class INESHeader:
    prg_banks: int
    chr_banks: int
    flags6: int
    flags7: int
    flags8: int
    flags9: int
    flags10: int
    mapper: int
    is_nes2: bool
    nes2_signature: int
    has_trainer: bool
    has_battery: bool
    four_screen: bool
    nametable_arrangement: str
    vs_unisystem: bool
    playchoice: bool
    tv_system: str


@dataclass(frozen=True)
class NESClassification:
    mapper: int
    mapper_name: str
    prg_bytes: int
    chr_bytes: int
    chr_is_ram: bool
    prg_ram_bytes: int
    mirroring: str
    has_battery: bool
    has_trainer: bool
    is_nes2: bool
    trainer_offset: int | None
    prg_offset: int
    chr_offset: int


def _check_image(data) -> bytes:
    if not isinstance(data, (bytes, bytearray)):
        raise NESROMError("ROM image must be bytes")
    if len(data) < MIN_ROM_SIZE:
        raise NESROMError(f"ROM image must be at least {MIN_ROM_SIZE} bytes, got {len(data)}")
    return bytes(data)


def parse_header(data: bytes) -> INESHeader:
    raw = _check_image(data)
    if raw[:4] != MAGIC:
        raise NESROMError(f"bad iNES magic: expected {MAGIC!r}")
    prg_banks = raw[4]
    chr_banks = raw[5]
    flags6 = raw[6]
    flags7 = raw[7]
    flags8 = raw[8]
    flags9 = raw[9]
    flags10 = raw[10]

    nes2_signature = flags7 & 0x0C
    is_nes2 = nes2_signature == 0x08
    mapper = (flags7 & 0xF0) | (flags6 >> 4)
    if is_nes2:
        mapper |= (flags8 & 0x0F) << 8

    has_trainer = bool(flags6 & 0x04)
    has_battery = bool(flags6 & 0x02)
    four_screen = bool(flags6 & 0x08)
    # Documented nametable arrangement: bit 0 = 0 is "vertical arrangement"
    # (conventionally horizontal mirroring); bit 0 = 1 is "horizontal
    # arrangement" (conventionally vertical mirroring).
    nametable_arrangement = "horizontal" if (flags6 & 0x01) else "vertical"
    if four_screen:
        mirroring = "four-screen"
    elif nametable_arrangement == "horizontal":
        mirroring = "vertical"
    else:
        mirroring = "horizontal"
    vs_unisystem = bool(flags7 & 0x01)
    playchoice = bool(flags7 & 0x02)
    tv_system = "pal" if (flags9 & 0x01) else "ntsc"

    return INESHeader(
        prg_banks=prg_banks,
        chr_banks=chr_banks,
        flags6=flags6,
        flags7=flags7,
        flags8=flags8,
        flags9=flags9,
        flags10=flags10,
        mapper=mapper,
        is_nes2=is_nes2,
        nes2_signature=nes2_signature,
        has_trainer=has_trainer,
        has_battery=has_battery,
        four_screen=four_screen,
        nametable_arrangement=nametable_arrangement,
        vs_unisystem=vs_unisystem,
        playchoice=playchoice,
        tv_system=tv_system,
    )


def _prg_ram_bytes(header: INESHeader) -> int:
    if header.is_nes2:
        # NES 2.0 flags 10 low nybble: PRG-RAM size as 64 << n bytes; the high
        # nybble is battery-backed PRG-NVRAM. 0 means none.
        ram = 64 << (header.flags10 & 0x0F) if (header.flags10 & 0x0F) else 0
        nvram = 64 << ((header.flags10 >> 4) & 0x0F) if ((header.flags10 >> 4) & 0x0F) else 0
        return ram + nvram
    # iNES flags 8: PRG RAM in 8 KiB units; value 0 infers 8 KiB "for
    # compatibility" (NESdev iNES Flags 8). Only materialise it when the
    # battery bit or a nonzero size declares persistent/PRG RAM.
    declared = header.flags8 * 8192
    if declared == 0 and header.has_battery:
        return 8192
    return declared


def classify(data: bytes) -> NESClassification:
    raw = _check_image(data)
    header = parse_header(raw)
    if header.prg_banks == 0:
        raise NESROMError("header declares zero PRG ROM banks")
    prg_bytes = header.prg_banks * PRG_BANK_SIZE
    chr_bytes = header.chr_banks * CHR_BANK_SIZE
    trainer_len = TRAINER_SIZE if header.has_trainer else 0
    prg_offset = HEADER_SIZE + trainer_len
    chr_offset = prg_offset + prg_bytes
    required = chr_offset + chr_bytes
    if len(raw) < required:
        raise NESROMError(
            f"ROM image is {len(raw)} bytes but the header declares {required} "
            "(16 header + trainer + PRG + CHR)"
        )
    return NESClassification(
        mapper=header.mapper,
        mapper_name=MAPPER_NAMES.get(header.mapper, "unsupported"),
        prg_bytes=prg_bytes,
        chr_bytes=chr_bytes,
        chr_is_ram=chr_bytes == 0,
        prg_ram_bytes=_prg_ram_bytes(header),
        mirroring=("four-screen" if header.four_screen else ("vertical" if header.nametable_arrangement == "horizontal" else "horizontal")),
        has_battery=header.has_battery,
        has_trainer=header.has_trainer,
        is_nes2=header.is_nes2,
        trainer_offset=HEADER_SIZE if header.has_trainer else None,
        prg_offset=prg_offset,
        chr_offset=chr_offset,
    )


class Mapper:
    """Documented NES cartridge read/write surface (fail closed)."""

    def cpu_read(self, address: int) -> int:
        raise NotImplementedError

    def cpu_write(self, address: int, value: int) -> None:
        raise NotImplementedError

    def ppu_read(self, address: int) -> int:
        raise NotImplementedError

    def ppu_write(self, address: int, value: int) -> None:
        raise NotImplementedError


class NromMapper(Mapper):
    """Documented NROM (mapper 0): no bank switching."""

    def __init__(self, prg: bytes, chr_data: bytes | None, prg_ram_bytes: int) -> None:
        if len(prg) not in (PRG_BANK_SIZE, 2 * PRG_BANK_SIZE):
            raise NESROMError(f"NROM PRG ROM must be 16 or 32 KiB, got {len(prg)}")
        self.prg = bytes(prg)
        self.chr_ram = chr_data is None
        self.chr = bytearray(CHR_BANK_SIZE) if self.chr_ram else bytes(chr_data)
        if not self.chr_ram and len(self.chr) != CHR_BANK_SIZE:
            raise NESROMError(f"NROM CHR ROM must be 8 KiB, got {len(self.chr)}")
        self.prg_ram = bytearray(prg_ram_bytes) if prg_ram_bytes else None

    def cpu_read(self, address: int) -> int:
        if 0x6000 <= address < 0x8000:
            if self.prg_ram is None:
                raise NESROMError(f"NROM PRG RAM read at 0x{address:04x} but no PRG RAM is present")
            return self.prg_ram[address - 0x6000]
        if 0x8000 <= address <= 0xFFFF:
            offset = address - 0x8000
            if len(self.prg) == PRG_BANK_SIZE:
                offset &= 0x3FFF  # documented 16 KiB mirroring
            return self.prg[offset]
        raise NESROMError(f"NROM CPU read outside the cartridge window: 0x{address:04x}")

    def cpu_write(self, address: int, value: int) -> None:
        if 0x6000 <= address < 0x8000:
            if self.prg_ram is None:
                raise NESROMError(f"NROM PRG RAM write at 0x{address:04x} but no PRG RAM is present")
            self.prg_ram[address - 0x6000] = value & 0xFF
            return
        if 0x8000 <= address <= 0xFFFF:
            # Documented: NROM has no mapper registers; writes are ignored.
            return
        raise NESROMError(f"NROM CPU write outside the cartridge window: 0x{address:04x}")

    def ppu_read(self, address: int) -> int:
        if 0x0000 <= address < 0x2000:
            return self.chr[address]
        raise NESROMError(f"NROM PPU read outside CHR space: 0x{address:04x}")

    def ppu_write(self, address: int, value: int) -> None:
        if not (0x0000 <= address < 0x2000):
            raise NESROMError(f"NROM PPU write outside CHR space: 0x{address:04x}")
        if self.chr_ram:
            self.chr[address] = value & 0xFF
        else:
            raise NESROMError("NROM CHR ROM is not writable")


def make_mapper(data: bytes) -> Mapper:
    raw = _check_image(data)
    info = classify(raw)
    if info.mapper != 0:
        raise NESROMError(
            f"mapper {info.mapper} ({info.mapper_name}) is classified but not implemented; "
            "fail closed instead of guessing banking behaviour"
        )
    prg = raw[info.prg_offset:info.prg_offset + info.prg_bytes]
    chr_data = None if info.chr_is_ram else raw[info.chr_offset:info.chr_offset + info.chr_bytes]
    return NromMapper(prg, chr_data, info.prg_ram_bytes)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: nes_rom_v1.py <rom.nes>", file=sys.stderr)
        return 2
    try:
        data = __import__("pathlib").Path(argv[1]).read_bytes()
        info = classify(data)
    except (OSError, NESROMError) as exc:
        print(f"OPENRECOMP_NES_ROM_V1=FAIL: {exc}", file=sys.stderr)
        return 2
    print(f"NES_ROM_MAPPER={info.mapper}")
    print(f"NES_ROM_MAPPER_NAME={info.mapper_name}")
    print(f"NES_ROM_PRG_BYTES={info.prg_bytes}")
    print(f"NES_ROM_CHR_BYTES={info.chr_bytes}")
    print(f"NES_ROM_MIRRORING={info.mirroring}")
    print(f"NES_ROM_NES2={int(info.is_nes2)}")
    print("OPENRECOMP_NES_ROM_V1=PASS")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv))
