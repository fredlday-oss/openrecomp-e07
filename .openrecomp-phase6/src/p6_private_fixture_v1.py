#!/usr/bin/env python3
"""Phase-6 private local compatibility fixture inventory (metadata/hash only).

Reads `D:\\OpenRecomp\\Roms\\phase1\\nes\\primary\\tmnt.nes`
(`PRIVATE_LOCAL_COMPATIBILITY_FIXTURE`) and records metadata, hashes, cartridge
inventory and the MMC1 subset classification. No ROM bytes or ROM-derived
binary copies are returned, stored, echoed or packaged; execution status stays
explicitly blocked until the MMC1 mapper stages land.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT / ".openrecomp-phase6" / "src"),):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p6_ines_v1 as p6_ingestion  # noqa: E402

PRIVATE_ROM = pathlib.Path(r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes")


class PrivateFixtureError(ValueError):
    """Fail-closed private fixture inventory error."""


def inventory(path: pathlib.Path = PRIVATE_ROM) -> dict[str, Any]:
    if not path.is_file():
        raise PrivateFixtureError("private compatibility fixture is not present")
    inventory_doc = p6_ingestion.ingest_path(path, source_label="private_tmnt")
    return {
        "stage": "P6-01",
        "classification": "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE",
        "source_path": str(path),
        "image_sha256": inventory_doc["image_sha256"],
        "image_size": inventory_doc["actual_size"],
        "container": inventory_doc["container"],
        "mapper": inventory_doc["mapper"],
        "submapper": inventory_doc["submapper"],
        "mirroring": inventory_doc["mirroring"],
        "prg_bytes": inventory_doc["prg_bytes"],
        "chr_bytes": inventory_doc["chr_bytes"],
        "chr_is_ram": inventory_doc["chr_is_ram"],
        "battery": inventory_doc["battery"],
        "trainer_bytes": inventory_doc["trainer_bytes"],
        "prg_sha256": inventory_doc["prg_sha256"],
        "chr_sha256": inventory_doc["chr_sha256"],
        "nes2_fields": inventory_doc["nes2_fields"],
        "vectors": inventory_doc["vectors"],
        "vectors_source": inventory_doc["vectors_source"],
        "cartridge_contract": inventory_doc["phase6"],
        "execution_status": "BLOCKED_MMC1_MAPPER_NOT_YET_IMPLEMENTED",
        "public_claim": "none; this analysis must not enter the public package",
    }


__all__ = ["PRIVATE_ROM", "PrivateFixtureError", "inventory"]
