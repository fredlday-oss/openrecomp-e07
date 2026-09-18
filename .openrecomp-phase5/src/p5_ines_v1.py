#!/usr/bin/env python3
"""Phase-5 fail-closed iNES / NES 2.0 ingestion and inventory.

Wraps the frozen Phase-1 parser (`tools/nes_rom_v1.py`, used read-only) and
adds the stricter Phase-5 contract:

* exact declared size (truncation and excess trailing bytes both fail closed);
* documented NES 2.0 sub-fields are inventoried but never guessed at:
  extended/exponent size forms and PRG-size MSB declarations fail closed;
* mapper/submapper classification is reported; unsupported mappers remain
  classified but blocked (never guessed);
* reset/NMI/IRQ vectors are extracted only where the CPU mapping is proven
  (mapper 0 NROM); elsewhere the vector status is explicitly unavailable;
* the inventory document contains only metadata, hashes, addresses and derived
  facts - never ROM program bytes.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import nes_rom_v1 as frozen_rom  # noqa: E402

MAGIC = frozen_rom.MAGIC
HEADER_SIZE = frozen_rom.HEADER_SIZE
PRG_BANK_SIZE = frozen_rom.PRG_BANK_SIZE
CHR_BANK_SIZE = frozen_rom.CHR_BANK_SIZE

SUPPORTED_MAPPERS = {0: "nrom"}


class P5IngestionError(ValueError):
    """Fail-closed Phase-5 ingestion error."""


@dataclass(frozen=True)
class P5Inventory:
    """Complete metadata inventory of one iNES image (no program bytes)."""

    container: str
    header_hex: str
    prg_bytes: int
    chr_bytes: int
    chr_is_ram: bool
    trainer_bytes: int
    trainer_offset: int | None
    battery: bool
    four_screen: bool
    mirroring: str
    nametable_arrangement: str
    tv_system: str
    vs_unisystem: bool
    playchoice: bool
    mapper: int
    mapper_name: str
    submapper: int
    prg_ram_bytes: int
    declared_size: int
    actual_size: int
    prg_sha256: str
    chr_sha256: str
    image_sha256: str
    vectors: dict[str, int] | None
    vectors_source: str
    execution_status: str
    unsupported_metadata: tuple[str, ...] = field(default_factory=tuple)
    nes2_fields: dict[str, int] = field(default_factory=dict)

    def to_document(self) -> dict[str, Any]:
        return {
            "container": self.container,
            "header_hex": self.header_hex,
            "prg_bytes": self.prg_bytes,
            "chr_bytes": self.chr_bytes,
            "chr_is_ram": self.chr_is_ram,
            "trainer_bytes": self.trainer_bytes,
            "trainer_offset": self.trainer_offset,
            "battery": self.battery,
            "four_screen": self.four_screen,
            "mirroring": self.mirroring,
            "nametable_arrangement": self.nametable_arrangement,
            "tv_system": self.tv_system,
            "vs_unisystem": self.vs_unisystem,
            "playchoice": self.playchoice,
            "mapper": self.mapper,
            "mapper_name": self.mapper_name,
            "submapper": self.submapper,
            "prg_ram_bytes": self.prg_ram_bytes,
            "declared_size": self.declared_size,
            "actual_size": self.actual_size,
            "prg_sha256": self.prg_sha256,
            "chr_sha256": self.chr_sha256,
            "image_sha256": self.image_sha256,
            "vectors": dict(self.vectors) if self.vectors else None,
            "vectors_source": self.vectors_source,
            "execution_status": self.execution_status,
            "unsupported_metadata": list(self.unsupported_metadata),
            "nes2_fields": dict(self.nes2_fields),
        }

    def fingerprint(self) -> str:
        import json
        return hashlib.sha256(
            (json.dumps(self.to_document(), sort_keys=True) + "\n").encode("utf-8")
        ).hexdigest()


def _check_bytes(data: bytes) -> bytes:
    if not isinstance(data, (bytes, bytearray)):
        raise P5IngestionError("ROM image must be bytes")
    raw = bytes(data)
    if len(raw) < HEADER_SIZE:
        raise P5IngestionError(
            f"ROM image must be at least {HEADER_SIZE} bytes, got {len(raw)}")
    if raw[:4] != MAGIC:
        raise P5IngestionError("bad iNES magic")
    return raw


def _container(header: frozen_rom.INESHeader, raw: bytes) -> str:
    if header.is_nes2:
        return "nes2.0"
    if header.nes2_signature == 0x04:
        return "archaic-ines"
    if header.nes2_signature == 0x00 and raw[12:16] == b"\x00\x00\x00\x00":
        return "ines"
    return "ines-quirky"


def _extended_size_form(raw: bytes, header: frozen_rom.INESHeader) -> bool:
    if not header.is_nes2:
        return False
    if (raw[4] & 0x0F) == 0x0F or (raw[5] & 0x0F) == 0x0F:
        return True
    if (raw[9] & 0x0F) != 0:
        return True
    return False


def ingest(data: bytes, *, source_label: str) -> P5Inventory:
    raw = _check_bytes(data)
    try:
        header = frozen_rom.parse_header(raw)
        classification = frozen_rom.classify(raw)
    except frozen_rom.NESROMError as exc:
        raise P5IngestionError(f"frozen ingestion rejected the image: {exc}") from exc

    if _extended_size_form(raw, header):
        raise P5IngestionError(
            "UNSUPPORTED_NES2_EXTENDED_SIZE: the header declares a NES 2.0 "
            "exponent/extended size form that Phase 5 does not implement")

    prg = raw[classification.prg_offset:classification.prg_offset
              + classification.prg_bytes]
    if classification.chr_is_ram:
        chr_segment = b""
    else:
        chr_segment = raw[classification.chr_offset:classification.chr_offset
                          + classification.chr_bytes]
    required = classification.chr_offset + classification.chr_bytes
    if len(raw) != required:
        raise P5IngestionError(
            f"ROM image size {len(raw)} does not exactly match the declared "
            f"layout ({required} bytes); trailing or missing data fail closed")

    unsupported: list[str] = []
    if header.vs_unisystem:
        unsupported.append("vs_unisystem")
    if header.playchoice:
        unsupported.append("playchoice")
    if header.four_screen:
        unsupported.append("four_screen_nametable_layout")

    container = _container(header, raw)
    nes2_fields: dict[str, int] = {}
    if header.is_nes2:
        nes2_fields = {
            "flags8": raw[8],
            "flags9": raw[9],
            "flags10": raw[10],
            "flags11": raw[11],
            "flags12": raw[12],
            "flags13": raw[13],
            "flags14": raw[14],
            "flags15": raw[15],
            "submapper": (raw[8] >> 4) & 0x0F,
            "prg_rom_size_msb": raw[9] & 0x0F,
            "chr_rom_size_msb": (raw[9] >> 4) & 0x0F,
            "prg_ram_nibble": raw[10] & 0x0F,
            "prg_nvram_nibble": (raw[10] >> 4) & 0x0F,
            "chr_ram_nibble": raw[11] & 0x0F,
            "cpu_ppu_timing": raw[12] & 0x03,
        }

    vectors: dict[str, int] | None = None
    vectors_source = "unavailable_unsupported_mapper"
    if classification.mapper == 0:
        if len(prg) < 6:
            raise P5IngestionError("mapper 0 PRG is too small to contain vectors")
        vectors = {
            "nmi": int.from_bytes(prg[-6:-4], "little"),
            "reset": int.from_bytes(prg[-4:-2], "little"),
            "irq": int.from_bytes(prg[-2:], "little"),
        }
        vectors_source = "nrom_last_16k_mapped_0x8000_to_0xffff"

    if classification.mapper in SUPPORTED_MAPPERS and not unsupported:
        execution_status = "SUPPORTED_NROM"
    elif classification.mapper in SUPPORTED_MAPPERS:
        execution_status = "BLOCKED_UNSUPPORTED_HARDWARE"
    else:
        execution_status = "BLOCKED_UNSUPPORTED_MAPPER"

    return P5Inventory(
        container=container,
        header_hex=raw[:HEADER_SIZE].hex(),
        prg_bytes=classification.prg_bytes,
        chr_bytes=classification.chr_bytes,
        chr_is_ram=classification.chr_is_ram,
        trainer_bytes=frozen_rom.TRAINER_SIZE if classification.has_trainer else 0,
        trainer_offset=classification.trainer_offset,
        battery=classification.has_battery,
        four_screen=header.four_screen,
        mirroring=classification.mirroring,
        nametable_arrangement=header.nametable_arrangement,
        tv_system=header.tv_system,
        vs_unisystem=header.vs_unisystem,
        playchoice=header.playchoice,
        mapper=classification.mapper,
        mapper_name=SUPPORTED_MAPPERS.get(classification.mapper, "unsupported"),
        submapper=nes2_fields.get("submapper", 0),
        prg_ram_bytes=classification.prg_ram_bytes,
        declared_size=required,
        actual_size=len(raw),
        prg_sha256=hashlib.sha256(prg).hexdigest(),
        chr_sha256=hashlib.sha256(chr_segment).hexdigest(),
        image_sha256=hashlib.sha256(raw).hexdigest(),
        vectors=vectors,
        vectors_source=vectors_source,
        execution_status=execution_status,
        unsupported_metadata=tuple(sorted(unsupported)),
        nes2_fields=nes2_fields,
    )


def ingest_path(path: pathlib.Path | str, *, source_label: str) -> P5Inventory:
    location = pathlib.Path(path)
    try:
        data = location.read_bytes()
    except OSError as exc:
        raise P5IngestionError(f"cannot read ROM image: {exc}") from exc
    return ingest(data, source_label=source_label)


__all__ = [
    "P5IngestionError",
    "P5Inventory",
    "SUPPORTED_MAPPERS",
    "ingest",
    "ingest_path",
]
