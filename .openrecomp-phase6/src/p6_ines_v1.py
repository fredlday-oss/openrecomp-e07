#!/usr/bin/env python3
"""Phase-6 fail-closed iNES/NES 2.0 ingestion with MMC1 classification.

Wraps the frozen Phase-5 ingestion (`p5_ines_v1`, imported read-only) and adds
the Phase-6 MMC1 contract:

* mapper-1 images are classified against the supported MMC1 subset in
  `p6_mmc1_spec_v1` (never guessed);
* reset/NMI/IRQ vectors are extracted only for supported MMC1 images, from the
  documented power-on fixed-last-bank frame (last 16 KiB PRG bank mapped at
  $C000-$FFFF); unsupported variants report vectors as unavailable;
* all Phase-5 fail-closed container checks (exact size, extended-size forms,
  unsupported hardware metadata) remain in force;
* the inventory document contains only metadata, hashes, addresses and derived
  facts - never ROM program bytes.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT / ".openrecomp-phase5" / "src"), str(ROOT / "tools"),
              str(ROOT / ".openrecomp-phase6" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p5_ines_v1 as phase5_ingestion  # noqa: E402
import p6_mmc1_spec_v1 as mmc1_spec  # noqa: E402

HEADER_SIZE = 16


class P6IngestionError(ValueError):
    """Fail-closed Phase-6 ingestion error."""


def ingest(data: bytes, *, source_label: str) -> dict[str, Any]:
    if not isinstance(data, (bytes, bytearray)):
        raise P6IngestionError("ROM image must be bytes")
    raw = bytes(data)
    try:
        base = phase5_ingestion.ingest(raw, source_label=source_label).to_document()
    except phase5_ingestion.P5IngestionError as exc:
        raise P6IngestionError(f"phase5 ingestion rejected the image: {exc}") from exc

    classification = mmc1_spec.classify(base)

    vectors: dict[str, int] | None = None
    if classification["status"] == "SUPPORTED_MMC1":
        prg_offset = HEADER_SIZE + int(base["trainer_bytes"])
        prg_end = prg_offset + int(base["prg_bytes"])
        prg = raw[prg_offset:prg_end]
        if len(prg) != int(base["prg_bytes"]) or len(prg) < 0x4000:
            raise P6IngestionError("MMC1 PRG segment is truncated")
        last_bank = prg[-0x4000:]
        vectors = {
            "nmi": int.from_bytes(last_bank[0x3FFA:0x3FFC], "little"),
            "reset": int.from_bytes(last_bank[0x3FFC:0x3FFE], "little"),
            "irq": int.from_bytes(last_bank[0x3FFE:0x4000], "little"),
        }
        vectors_source = "mmc1_power_on_fixed_last_bank"
    elif classification["mapper"] == mmc1_spec.MAPPER:
        vectors_source = "unavailable_unsupported_mmc1_variant"
    else:
        vectors_source = "unavailable_unsupported_mapper"

    document = dict(base)
    document["vectors"] = vectors
    document["vectors_source"] = vectors_source
    document["phase6"] = classification
    document["source_label"] = source_label
    document["container_declared_size"] = int(base["declared_size"])
    return document


def ingest_path(path: pathlib.Path | str, *, source_label: str) -> dict[str, Any]:
    location = pathlib.Path(path)
    try:
        data = location.read_bytes()
    except OSError as exc:
        raise P6IngestionError(f"cannot read ROM image: {exc}") from exc
    return ingest(data, source_label=source_label)


def fingerprint(document: dict[str, Any]) -> str:
    import hashlib
    import json
    stable = {key: value for key, value in document.items() if key != "source_label"}
    return hashlib.sha256(
        (json.dumps(stable, sort_keys=True) + "\n").encode("utf-8")
    ).hexdigest()


__all__ = [
    "P6IngestionError",
    "fingerprint",
    "ingest",
    "ingest_path",
]
