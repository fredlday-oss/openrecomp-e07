#!/usr/bin/env python3
"""OpenRecomp Phase-16 deterministic CD-ROM sector reader V1.

Provides a bounds-checked, fail-closed sector delivery primitive for Track 01
of the Hercules Mode 2 / 2352 disc image.
"""

from __future__ import annotations

import pathlib
from typing import BinaryIO

RAW_SECTOR_SIZE = 2352
USER_DATA_OFFSET = 24
USER_DATA_SIZE = 2048
SYNC_PATTERN = bytes([0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00])

# Disc bounds
MAX_DISC_SECTORS = 174087  # 409,452,624 bytes / 2352 bytes per sector


class CdromReadError(ValueError):
    """Raised when sector read fails validation."""


class CdromSectorSource:
    def __init__(self, bin_path: pathlib.Path) -> None:
        self.bin_path = bin_path
        if not bin_path.is_file():
            raise CdromReadError(f"Disc file not found: {bin_path}")
        self.file_size = bin_path.stat().st_size
        if self.file_size % RAW_SECTOR_SIZE != 0:
            raise CdromReadError(f"Disc size not multiple of 2352: {self.file_size}")
        self.total_sectors = self.file_size // RAW_SECTOR_SIZE

    def read_raw_sector(self, lba: int, handle: BinaryIO | None = None) -> bytes:
        if lba < 0 or lba >= self.total_sectors:
            raise CdromReadError(f"LBA out of bounds: {lba} (max {self.total_sectors - 1})")

        f = handle
        close_needed = False
        if f is None:
            f = self.bin_path.open("rb")
            close_needed = True

        try:
            f.seek(lba * RAW_SECTOR_SIZE)
            raw = f.read(RAW_SECTOR_SIZE)
            if len(raw) != RAW_SECTOR_SIZE:
                raise CdromReadError(f"Short read at LBA {lba}: got {len(raw)} bytes")
            if raw[:12] != SYNC_PATTERN:
                raise CdromReadError(f"Invalid sync pattern at LBA {lba}: {raw[:12].hex()}")
            return raw
        finally:
            if close_needed:
                f.close()

    def read_user_sector(self, lba: int, handle: BinaryIO | None = None) -> bytes:
        raw = self.read_raw_sector(lba, handle)
        # Mode 2 Form 1: user data is at offset 24..2072
        return raw[USER_DATA_OFFSET : USER_DATA_OFFSET + USER_DATA_SIZE]

    def read_user_sectors(self, start_lba: int, count: int) -> bytes:
        if count <= 0:
            raise CdromReadError(f"Invalid sector count: {count}")
        if start_lba < 0 or start_lba + count > self.total_sectors:
            raise CdromReadError(f"LBA range out of bounds: [{start_lba}, {start_lba + count})")

        chunks = []
        with self.bin_path.open("rb") as f:
            for lba in range(start_lba, start_lba + count):
                chunks.append(self.read_user_sector(lba, f))
        return b"".join(chunks)
