#!/usr/bin/env python3
"""P17-04 authenticated TITLE block emitter.

This stage emits a deterministic, non-reconstructive guest-block manifest and
C inventory.  The inventory carries block identity and source provenance only;
it never embeds TITLE words or substitutes host-authored guest semantics.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
TITLE_DECODE = ROOT / ".openrecomp-phase17/evidence/P17-02/title_decode.json"
TITLE_FILE_SHA256 = "39013ea19589015872a211c23d8c23ae8ecee7bc5093d996f51cf206775f1b68"
TITLE_PAYLOAD_SHA256 = "fe1925b5dd7c7190802dbe37b162759467fdbbf95b707edb9c6bb1626b961ccc"
TITLE_TEXT_START = 0x80038098
TITLE_ENTRY = 0x800380A0
TITLE_FILE_OFFSET_BASE = 0x800


class TitleEmissionError(ValueError):
    pass


def canonical_digest(document: dict[str, Any]) -> str:
    body = {key: value for key, value in document.items() if key != "projection_digest"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def load_projection(path: pathlib.Path = TITLE_DECODE) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TitleEmissionError("P17-02 projection unavailable or malformed") from exc
    if not isinstance(document, dict):
        raise TitleEmissionError("P17-02 projection is not an object")
    if document.get("schema") != "openrecomp-phase17-title-decode-v1":
        raise TitleEmissionError("unexpected authenticated decode schema")
    if document.get("projection_digest") != canonical_digest(document):
        raise TitleEmissionError("authenticated decode projection digest mismatch")
    provenance = document.get("provenance")
    if not isinstance(provenance, dict):
        raise TitleEmissionError("authenticated provenance missing")
    if provenance.get("title_file_sha256") != TITLE_FILE_SHA256 or provenance.get("title_payload_sha256") != TITLE_PAYLOAD_SHA256:
        raise TitleEmissionError("authenticated TITLE identity mismatch")
    if provenance.get("guest_entry_pc") != f"0x{TITLE_ENTRY:08x}":
        raise TitleEmissionError("authenticated TITLE entry mismatch")
    if document.get("evidence_class") != "PRIVATE_FIXTURE_BOUNDED":
        raise TitleEmissionError("unbounded evidence class")
    blocks = document.get("basic_blocks", {}).get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise TitleEmissionError("authenticated block records missing")
    return document


def _source_record(pc: int) -> dict[str, Any]:
    payload_offset = pc - TITLE_TEXT_START
    if payload_offset < 0 or payload_offset % 4:
        raise TitleEmissionError(f"invalid authenticated source PC: 0x{pc:08x}")
    return {
        "guest_pc": f"0x{pc:08x}",
        "payload_offset": payload_offset,
        "file_offset": TITLE_FILE_OFFSET_BASE + payload_offset,
        "title_file_sha256": TITLE_FILE_SHA256,
        "title_payload_sha256": TITLE_PAYLOAD_SHA256,
    }


def emit_projection(document: dict[str, Any]) -> dict[str, Any]:
    blocks = document["basic_blocks"]["blocks"]
    emitted: list[dict[str, Any]] = []
    seen: set[int] = set()
    entry_block = None
    for index, block in enumerate(sorted(blocks, key=lambda item: item["start"])):
        try:
            start = int(block["start"], 16)
            end = int(block["range"]["end"], 16)
            count = int(block["instruction_count"])
        except (KeyError, TypeError, ValueError) as exc:
            raise TitleEmissionError("malformed authenticated block record") from exc
        if count < 1 or end != start + 4 * (count - 1):
            raise TitleEmissionError(f"non-contiguous authenticated block: 0x{start:08x}")
        pcs = tuple(start + 4 * offset for offset in range(count))
        if seen.intersection(pcs):
            raise TitleEmissionError(f"overlapping authenticated blocks: 0x{start:08x}")
        seen.update(pcs)
        source = [_source_record(pc) for pc in pcs]
        source_digest = hashlib.sha256(json.dumps(source, sort_keys=True).encode("utf-8")).hexdigest()
        emitted_block = {
            "emitted_block": f"title_block_{index:05d}",
            "guest_start": f"0x{start:08x}",
            "guest_end": f"0x{end:08x}",
            "instruction_count": count,
            "source_provenance_digest": source_digest,
            "source_provenance_count": len(source),
            "successors": block.get("successors", []),
            "terminator": block.get("terminator"),
        }
        if start <= TITLE_ENTRY <= end:
            entry_block = emitted_block["emitted_block"]
        emitted.append(emitted_block)
    if entry_block is None:
        raise TitleEmissionError("authenticated TITLE entry has no emitted block")
    manifest = {
        "schema": "openrecomp-phase17-title-emission-v1",
        "stage": "P17-04",
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "emission_kind": "AUTHENTICATED_BLOCK_INVENTORY_NO_RAW_WORDS",
        "source": {
            "p17_02_projection_digest": document["projection_digest"],
            "title_file_sha256": TITLE_FILE_SHA256,
            "title_payload_sha256": TITLE_PAYLOAD_SHA256,
            "entry_pc": f"0x{TITLE_ENTRY:08x}",
        },
        "active_build": {
            "phase17_emitter": "p17_title_emit_v1.py",
            "phase16_hand_authored_title_guest_flow": "EXCLUDED",
            "phase16_guest_flow_imports": [],
            "execution": "DEFERRED_TO_P17_05_AND_P17_06",
        },
        "entry_block": entry_block,
        "block_count": len(emitted),
        "emitted_blocks": emitted,
    }
    manifest["emission_digest"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return manifest


def c_inventory(manifest: dict[str, Any]) -> str:
    lines = [
        "/* Generated by P17-04 from authenticated block records; no TITLE words. */",
        "#include <stdint.h>",
        "struct or_title_emitted_block { uint32_t start; uint32_t end; uint32_t count; };",
        "static const struct or_title_emitted_block or_title_emitted_blocks[] = {",
    ]
    for block in manifest["emitted_blocks"]:
        lines.append(
            f"    {{ 0x{int(block['guest_start'], 16):08x}u, 0x{int(block['guest_end'], 16):08x}u, {block['instruction_count']}u }},"
        )
    lines.extend(["};", f"const uint32_t or_title_emitted_block_count = {len(manifest['emitted_blocks'])}u;", ""])
    return "\n".join(lines)
