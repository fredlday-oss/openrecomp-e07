#!/usr/bin/env python3
"""OpenRecomp Phase-16 TITLE fixture mapping and disc provenance V1."""

from __future__ import annotations

import dataclasses
import hashlib
import pathlib
import struct
from typing import Any

from p16_contracts_v1 import (
    FIXTURE_BIN_SHA256,
    FIXTURE_CUE_SHA256,
    FIXTURE_SLUS_SHA256,
    TITLE_ENTRY_PC,
    TITLE_ISO_PATH,
    TITLE_PAYLOAD_SECTORS,
    TITLE_PAYLOAD_SHA256,
    TITLE_PAYLOAD_SIZE,
    TITLE_PAYLOAD_START_LBA,
    TITLE_SP_ADDR,
    TITLE_START_LBA,
    TITLE_TEXT_ADDR,
    TITLE_TOTAL_SECTORS,
)

TITLE_FILE_SHA256 = "39013ea19589015872a211c23d8c23ae8ecee7bc5093d996f51cf206775f1b68"
TITLE_FILE_SIZE = 288768


@dataclasses.dataclass(frozen=True)
class TitleMapping:
    iso_path: str = TITLE_ISO_PATH
    start_lba: int = TITLE_START_LBA
    total_sectors: int = TITLE_TOTAL_SECTORS
    file_size: int = TITLE_FILE_SIZE
    file_sha256: str = TITLE_FILE_SHA256
    payload_start_lba: int = TITLE_PAYLOAD_START_LBA
    payload_sectors: int = TITLE_PAYLOAD_SECTORS
    payload_size: int = TITLE_PAYLOAD_SIZE
    payload_sha256: str = TITLE_PAYLOAD_SHA256
    t_addr: int = TITLE_TEXT_ADDR
    t_size: int = TITLE_PAYLOAD_SIZE
    entry_pc: int = TITLE_ENTRY_PC
    sp_addr: int = TITLE_SP_ADDR

    def extract_header_and_payload(self, bin_path: pathlib.Path) -> tuple[bytes, bytes]:
        """Extract header sector (LBA 88) and 140 payload sectors (LBA 89..228)."""
        with bin_path.open("rb") as f:
            f.seek(self.start_lba * 2352 + 24)
            header = f.read(2048)
            payload_parts = []
            for lba in range(self.payload_start_lba, self.payload_start_lba + self.payload_sectors):
                f.seek(lba * 2352 + 24)
                payload_parts.append(f.read(2048))
        return header, b"".join(payload_parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "openrecomp-phase16-title-mapping-v1",
            "iso9660_path": self.iso_path,
            "starting_lba": self.start_lba,
            "total_sectors": self.total_sectors,
            "file_size": self.file_size,
            "file_sha256": self.file_sha256,
            "payload_start_lba": self.payload_start_lba,
            "payload_sectors": self.payload_sectors,
            "payload_size": self.payload_size,
            "payload_sha256": self.payload_sha256,
            "psx_exe_header": {
                "t_addr": f"0x{self.t_addr:08x}",
                "t_size": self.t_size,
                "entry_pc": f"0x{self.entry_pc:08x}",
                "sp_addr": f"0x{self.sp_addr:08x}",
            },
            "historical_recon_discrepancy": {
                "historical_claim": "0x27bdffd8 at 0x800380a0 (TITLE_PAYLOAD_IDENTITY.json)",
                "fixture_reality": "0x3c028008 at 0x800380a0 (lui v0, 0x8008); 0x27bdffd8 resides at 0x80038ab4",
                "status": "RECONCILED_AND_PROVEN",
            },
        }


MAPPING = TitleMapping()
