#!/usr/bin/env python3
"""P1-32 gate: NES ROM ingestion + NROM/mapper abstraction.

Builds synthetic/original iNES and NES 2.0 images programmatically, then pins:

- header parsing (magic, PRG/CHR bank counts, flags, mapper, mirroring, NES 2.0
  detection, trainer/battery flags, TV system);
- classification of NROM images (PRG/CHR sizes, CHR RAM when CHR size 0);
- the documented NROM (mapper 0) behaviour: 32 KiB PRG identity mapping,
  16 KiB mirroring at $8000/$C000, 8 KiB CHR access, ignored $8000+ writes,
  PRG RAM at $6000-$7FFF only when declared;
- trainer offset handling (512 bytes before PRG);
- NES 2.0 highest-nybble mapper extension and logarithmic PRG RAM;
- fail-closed rejection (short image, bad magic, zero PRG banks, truncated
  image, unsupported mapper at `make_mapper`);
- secondary local-ROM metadata-only evidence (ROM_INVENTORY.json): header
  fields/hashes only, never ROM bytes.
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

from nes_rom_v1 import (  # noqa: E402
    CHR_BANK_SIZE,
    HEADER_SIZE,
    NESROMError,
    NromMapper,
    PRG_BANK_SIZE,
    TRAINER_SIZE,
    classify,
    make_mapper,
    parse_header,
)


def build_ines(
    *,
    prg_banks: int = 2,
    chr_banks: int = 1,
    flags6: int = 0x00,
    flags7: int = 0x00,
    flags8: int = 0x00,
    flags9: int = 0x00,
    flags10: int = 0x00,
    trainer: bool = False,
) -> bytes:
    header = bytearray(HEADER_SIZE)
    header[0:4] = b"NES\x1a"
    header[4] = prg_banks
    header[5] = chr_banks
    header[6] = flags6
    header[7] = flags7
    header[8] = flags8
    header[9] = flags9
    header[10] = flags10
    prg = bytes(((index & 0xFF) ^ ((index >> 8) & 0xFF)) for index in range(prg_banks * PRG_BANK_SIZE))
    chr_data = bytes((index * 7 + 3) & 0xFF for index in range(chr_banks * CHR_BANK_SIZE))
    return bytes(header) + (bytes(TRAINER_SIZE) if trainer else b"") + prg + chr_data


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expect_fail(label: str, action, error_type=NESROMError) -> None:
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

    rom = build_ines(prg_banks=2, chr_banks=1, flags6=0x00)
    header = parse_header(rom)
    assert header.prg_banks == 2 and header.chr_banks == 1
    assert header.mapper == 0
    assert header.is_nes2 is False
    assert header.has_trainer is False and header.has_battery is False
    assert header.four_screen is False
    assert header.nametable_arrangement == "vertical"  # bit 0 clear
    assert header.tv_system == "ntsc"
    print("PASS header-parse iNES")
    tests += 1

    info = classify(rom)
    assert info.mapper == 0 and info.mapper_name == "nrom"
    assert info.prg_bytes == 2 * PRG_BANK_SIZE
    assert info.chr_bytes == CHR_BANK_SIZE and info.chr_is_ram is False
    assert info.prg_ram_bytes == 0
    assert info.mirroring == "horizontal"
    print("PASS classification nrom 32K-prg/8K-chr")
    tests += 1

    # Mirroring / four-screen from flags 6
    assert classify(build_ines(flags6=0x01)).mirroring == "vertical"
    assert classify(build_ines(flags6=0x08)).mirroring == "four-screen"
    print("PASS mirroring horizontal/vertical/four-screen")
    tests += 1

    # NROM 32 KiB identity mapping + ignored writes ------------------------
    mapper = make_mapper(build_ines(prg_banks=2, chr_banks=1))
    assert isinstance(mapper, NromMapper)
    assert mapper.cpu_read(0x8000) == 0x00
    assert mapper.cpu_read(0xC000) == 0x40  # distinct from $8000 for 32 KiB
    mapper.cpu_write(0x8000, 0x55)  # documented: NROM ignores PRG writes
    assert mapper.cpu_read(0x8000) == 0x00
    assert mapper.ppu_read(0x0000) == 0x03
    print("PASS nrom-32k-identity-and-ignored-writes")
    tests += 1

    # NROM 16 KiB mirroring at $8000/$C000 ---------------------------------
    small = make_mapper(build_ines(prg_banks=1, chr_banks=1))
    assert small.cpu_read(0x8000) == small.cpu_read(0xC000)
    assert small.cpu_read(0xC001) == small.cpu_read(0x8001)
    print("PASS nrom-16k-mirroring")
    tests += 1

    # CHR RAM when CHR size 0 ----------------------------------------------
    chr_ram = make_mapper(build_ines(prg_banks=2, chr_banks=0))
    assert classify(build_ines(prg_banks=2, chr_banks=0)).chr_is_ram is True
    chr_ram.ppu_write(0x0123, 0xAB)
    assert chr_ram.ppu_read(0x0123) == 0xAB
    chr_rom = make_mapper(build_ines(prg_banks=2, chr_banks=1))
    expect_fail("chr-rom-write", lambda: chr_rom.ppu_write(0x0000, 0x00))
    print("PASS chr-ram-writable-chr-rom-fail-closed")
    tests += 1

    # Trainer offset --------------------------------------------------------
    trained = build_ines(prg_banks=1, chr_banks=1, flags6=0x04, trainer=True)
    trained_info = classify(trained)
    assert trained_info.has_trainer is True
    assert trained_info.trainer_offset == HEADER_SIZE
    assert trained_info.prg_offset == HEADER_SIZE + TRAINER_SIZE
    assert parse_header(trained).has_trainer is True
    print("PASS trainer-offset")
    tests += 1

    # Battery PRG RAM -------------------------------------------------------
    rammed = make_mapper(build_ines(prg_banks=2, chr_banks=1, flags6=0x02))
    assert classify(build_ines(prg_banks=2, chr_banks=1, flags6=0x02)).prg_ram_bytes == 8192
    rammed.cpu_write(0x6000, 0x5A)
    assert rammed.cpu_read(0x6000) == 0x5A
    no_ram = make_mapper(build_ines(prg_banks=2, chr_banks=1))
    expect_fail("prg-ram-absent-read", lambda: no_ram.cpu_read(0x6000))
    expect_fail("prg-ram-absent-write", lambda: no_ram.cpu_write(0x6000, 0x00))
    print("PASS prg-ram-declared-vs-absent")
    tests += 1

    # Mapper interface fail-closed windows ---------------------------------
    expect_fail("cpu-read-outside-cartridge", lambda: mapper.cpu_read(0x2000))
    expect_fail("cpu-write-outside-cartridge", lambda: mapper.cpu_write(0x2000, 0x00))
    expect_fail("ppu-read-outside-chr", lambda: mapper.ppu_read(0x2000))
    print("PASS mapper-window-fail-closed")
    tests += 1

    # NES 2.0 detection + mapper high nybble + PRG RAM ---------------------
    nes2 = build_ines(prg_banks=1, chr_banks=1, flags7=0x08, flags8=0x01, flags10=0x05)
    nes2_header = parse_header(nes2)
    assert nes2_header.is_nes2 is True
    assert nes2_header.nes2_signature == 0x08
    assert nes2_header.mapper == 0x100  # highest nybble from flags 8
    nes2_info = classify(nes2)
    assert nes2_info.is_nes2 is True
    assert nes2_info.prg_ram_bytes == 64 << 5
    print("PASS nes2.0-detection-mapper-high-nybble-prg-ram")
    tests += 1

    # Fail-closed ingestion -------------------------------------------------
    expect_fail("short-image", lambda: parse_header(bytes(8)))
    expect_fail("bad-magic", lambda: parse_header(b"SNE\x1a" + bytes(12)))
    expect_fail("zero-prg-banks", lambda: classify(build_ines(prg_banks=0)))
    truncated = build_ines(prg_banks=2, chr_banks=1)[:-16]
    expect_fail("truncated-declared-size", lambda: classify(truncated))
    expect_fail("declared-trainer-missing", lambda: classify(build_ines(prg_banks=1, chr_banks=1, flags6=0x04)))
    expect_fail("unsupported-mapper-fails-closed", lambda: make_mapper(build_ines(flags6=0x10)))
    print("PASS fail-closed-ingestion")
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
            assert len(rom_bytes) == entry["bytes"]
            local_header = parse_header(rom_bytes)
            local = classify(rom_bytes)
            print(
                f"LOCAL_NES_ROM metadata-only sha256={digest(rom_bytes)} bytes={len(rom_bytes)} "
                f"mapper={local.mapper} mapper_name={local.mapper_name} prg_bytes={local.prg_bytes} "
                f"chr_bytes={local.chr_bytes} mirroring={local.mirroring} trainer={int(local.has_trainer)} "
                f"battery={int(local.has_battery)} nes2={int(local.is_nes2)} tv={local_header.tv_system}"
            )
        else:
            print(f"LOCAL_NES_ROM SKIPPED (file absent: {entry['full_path']})")
    else:
        print("LOCAL_NES_ROM SKIPPED (no ROM_INVENTORY.json)")
    tests += 1

    print(f"OPENRECOMP_NES_ROM_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
