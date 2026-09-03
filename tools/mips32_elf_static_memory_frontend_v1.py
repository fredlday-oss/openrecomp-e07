#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mips32_elf_frontend_v1 import (
    ELF_MAGIC,
    ELFCLASS32,
    ELFDATA2LSB,
    EM_MIPS,
    ET_EXEC,
    EV_CURRENT,
    MIPS32ELFError,
    public_elf_metadata,
    load_mips32_elf,
    runtime_meta_for_elf,
)
from tools.mips32_expansion_frontend_v1 import DecodeError, FrontendError, convert

SHT_PROGBITS = 1
SHT_NOBITS = 8
SHF_WRITE = 0x1
SHF_ALLOC = 0x2
SHF_EXECINSTR = 0x4
STATIC_NAMES = (".rodata", ".data", ".bss")
ADAPTER_ID = "openrecomp.mips32-elf-static-memory-v1"
MODULE_NAMESPACE = "openrecomp.mips32.elf.static-memory-v1"


class MIPS32ELFStaticMemoryError(ValueError):
    pass


def _cstr(blob: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(blob):
        return ""
    end = blob.find(b"\0", offset)
    if end < 0:
        end = len(blob)
    return blob[offset:end].decode("utf-8", "replace")


def _slice(blob: bytes, offset: int, size: int, what: str) -> bytes:
    if offset < 0 or size < 0 or offset > len(blob) or size > len(blob) - offset:
        raise MIPS32ELFStaticMemoryError(f"{what} out of bounds")
    return blob[offset:offset + size]


def _pow2_or_zero(value: int) -> bool:
    return value in {0, 1} or (value > 1 and value & (value - 1) == 0)


def _parse_original_sections(blob: bytes, memory_size: int) -> tuple[list[dict], list[dict], bytearray]:
    if len(blob) < 52 or blob[:4] != ELF_MAGIC:
        raise MIPS32ELFStaticMemoryError("not ELF")
    ident = blob[:16]
    if ident[4] != ELFCLASS32 or ident[5] != ELFDATA2LSB or ident[6] != EV_CURRENT:
        raise MIPS32ELFStaticMemoryError("static-memory V1 requires little-endian ELF32")
    (_, e_type, e_machine, e_version, _, _, e_shoff, _, e_ehsize, _, _, e_shentsize, e_shnum, e_shstrndx) = struct.unpack_from(
        "<16sHHIIIIIHHHHHH", blob, 0
    )
    if e_type != ET_EXEC or e_machine != EM_MIPS or e_version != EV_CURRENT or e_ehsize < 52:
        raise MIPS32ELFStaticMemoryError("static-memory V1 requires ET_EXEC EM_MIPS")
    if e_shoff == 0 or e_shnum == 0 or e_shentsize < 40:
        raise MIPS32ELFStaticMemoryError("missing section table")
    if e_shoff > len(blob) or e_shnum > (len(blob) - e_shoff) // e_shentsize:
        raise MIPS32ELFStaticMemoryError("section table out of bounds")
    if e_shstrndx >= e_shnum:
        raise MIPS32ELFStaticMemoryError("bad shstrndx")

    raw: list[dict] = []
    for index in range(e_shnum):
        values = struct.unpack_from("<IIIIIIIIII", blob, e_shoff + index * e_shentsize)
        raw.append({
            "index": index, "name_off": values[0], "type": values[1], "flags": values[2],
            "addr": values[3], "offset": values[4], "size": values[5], "link": values[6],
            "info": values[7], "addralign": values[8], "entsize": values[9],
        })
    shstr = raw[e_shstrndx]
    if shstr["type"] == SHT_NOBITS:
        raise MIPS32ELFStaticMemoryError("section-name table cannot be NOBITS")
    names = _slice(blob, shstr["offset"], shstr["size"], "section-name string table")

    sections: list[dict] = []
    for section in raw:
        item = dict(section)
        item["name"] = _cstr(names, item["name_off"])
        if item["type"] != SHT_NOBITS:
            _slice(blob, item["offset"], item["size"], f"section {item['name'] or item['index']}")
        if not _pow2_or_zero(item["addralign"]):
            raise MIPS32ELFStaticMemoryError(f"invalid section alignment: {item['name']}")
        if item["addralign"] > 1 and item["addr"] % item["addralign"]:
            raise MIPS32ELFStaticMemoryError(f"misaligned guest section: {item['name']}")
        sections.append(item)

    allowed_alloc = {".text", ".reginfo", ".MIPS.abiflags", *STATIC_NAMES}
    for section in sections:
        if section["flags"] & SHF_ALLOC and section["size"] and section["name"] not in allowed_alloc:
            raise MIPS32ELFStaticMemoryError(
                f"alloc section outside static-memory V1: {section['name'] or '<unnamed>'}"
            )

    by_name = {section["name"]: section for section in sections}
    missing = [name for name in STATIC_NAMES if name not in by_name or by_name[name]["size"] == 0]
    if missing:
        raise MIPS32ELFStaticMemoryError("missing required static section(s): " + ", ".join(missing))

    rodata, data, bss = (by_name[name] for name in STATIC_NAMES)
    if rodata["type"] == SHT_NOBITS or not (rodata["flags"] & SHF_ALLOC) or rodata["flags"] & (SHF_WRITE | SHF_EXECINSTR):
        raise MIPS32ELFStaticMemoryError(".rodata must be file-backed allocatable read-only non-executable data")
    if data["type"] == SHT_NOBITS or not (data["flags"] & SHF_ALLOC) or not (data["flags"] & SHF_WRITE) or data["flags"] & SHF_EXECINSTR:
        raise MIPS32ELFStaticMemoryError(".data must be file-backed allocatable writable non-executable data")
    if bss["type"] != SHT_NOBITS or not (bss["flags"] & SHF_ALLOC) or not (bss["flags"] & SHF_WRITE) or bss["flags"] & SHF_EXECINSTR:
        raise MIPS32ELFStaticMemoryError(".bss must be allocatable writable non-executable SHT_NOBITS")

    ranges: list[tuple[int, int, str]] = []
    segments: list[dict] = []
    for section in (rodata, data, bss):
        start = section["addr"]
        end = start + section["size"]
        if end < start or end > memory_size:
            raise MIPS32ELFStaticMemoryError(f"{section['name']} lies outside deterministic guest memory")
        for old_start, old_end, old_name in ranges:
            if max(start, old_start) < min(end, old_end):
                raise MIPS32ELFStaticMemoryError(f"static sections overlap: {old_name} and {section['name']}")
        ranges.append((start, end, section["name"]))
        data_bytes = bytes(section["size"]) if section["type"] == SHT_NOBITS else _slice(
            blob, section["offset"], section["size"], section["name"]
        )
        segments.append({
            "name": section["name"],
            "guest_address": start,
            "size_bytes": section["size"],
            "data_hex": data_bytes.hex(),
            "data_sha256": hashlib.sha256(data_bytes).hexdigest(),
            "zero_fill": section["type"] == SHT_NOBITS,
            "writable": bool(section["flags"] & SHF_WRITE),
            "executable": bool(section["flags"] & SHF_EXECINSTR),
        })

    sanitized = bytearray(blob)
    for section in (rodata, data, bss):
        flags_off = e_shoff + section["index"] * e_shentsize + 8
        struct.pack_into("<I", sanitized, flags_off, section["flags"] & ~SHF_ALLOC)
    compact = [
        {key: section[key] for key in ("index", "name", "type", "flags", "addr", "offset", "size", "addralign")}
        for section in sections
    ]
    return compact, segments, sanitized


def load_mips32_elf_static_memory(path: str | Path, memory_size: int) -> dict:
    path = Path(path)
    blob = path.read_bytes()
    sections, segments, sanitized = _parse_original_sections(blob, memory_size)
    with tempfile.TemporaryDirectory() as td:
        sanitized_path = Path(td) / "text-only-view.elf"
        sanitized_path.write_bytes(sanitized)
        loaded = load_mips32_elf(sanitized_path)
    loaded = dict(loaded)
    loaded["input_size"] = len(blob)
    loaded["input_sha256"] = hashlib.sha256(blob).hexdigest()
    loaded["sections"] = sections
    loaded["memory_segments"] = segments
    return loaded


def public_static_metadata(loaded: dict) -> dict:
    base = public_elf_metadata(loaded)
    base["static_memory_segments"] = [
        {key: segment[key] for key in (
            "name", "guest_address", "size_bytes", "data_sha256", "zero_fill", "writable", "executable"
        )}
        for segment in loaded["memory_segments"]
    ]
    return base


def _write_json(path: str | Path, value: dict) -> None:
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 8:
        print(
            "usage: mips32_elf_static_memory_frontend_v1.py <input.elf> <runtime.json> <host-contract.json> "
            "<out-ir.json> <out-sidecar.json> <out-report.json> <out-elf-metadata.json>",
            file=sys.stderr,
        )
        return 2
    try:
        runtime = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        contract = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
        memory_size = runtime["memory_size_bytes"]
        if contract.get("memory", {}).get("size_bytes") != memory_size:
            raise MIPS32ELFStaticMemoryError("runtime/host memory-size mismatch")
        loaded = load_mips32_elf_static_memory(argv[1], memory_size)
        meta = runtime_meta_for_elf(runtime, loaded)
        ir, sidecar, report = convert(meta, loaded["words"], loaded["input_sha256"], contract)
        ir = dict(ir)
        ir["module_id"] = f"{MODULE_NAMESPACE}.{meta['fixture_id']}"
        ir["source"] = dict(ir["source"])
        ir["source"]["adapter"] = ADAPTER_ID
        sidecar = dict(sidecar)
        sidecar["memory_segments"] = [
            {"name": seg["name"], "guest_address": seg["guest_address"], "data_hex": seg["data_hex"]}
            for seg in loaded["memory_segments"]
        ]
        report = dict(report)
        report.update({
            "input_format": "ELF32",
            "elf_machine": loaded["machine"],
            "elf_entry_point": loaded["entry_point"],
            "elf_text_sha256": loaded["text"]["sha256"],
            "elf_function_count": len(loaded["functions"]),
            "static_memory_segment_count": len(loaded["memory_segments"]),
            "static_memory_bytes": sum(item["size_bytes"] for item in loaded["memory_segments"]),
            "source_adapter": ADAPTER_ID,
        })
        _write_json(argv[4], ir)
        _write_json(argv[5], sidecar)
        _write_json(argv[6], report)
        _write_json(argv[7], public_static_metadata(loaded))
    except (
        OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, DecodeError, FrontendError,
        MIPS32ELFError, MIPS32ELFStaticMemoryError,
    ) as exc:
        print(f"OPENRECOMP_MIPS32_ELF_STATIC_MEMORY_FRONTEND=FAIL: {exc}", file=sys.stderr)
        return 2

    print(f"MIPS32_ELF_STATIC_MEMORY_SHA256={loaded['input_sha256']}")
    print(f"MIPS32_ELF_STATIC_MEMORY_SEGMENTS={len(loaded['memory_segments'])}")
    print("OPENRECOMP_MIPS32_ELF_STATIC_MEMORY_FRONTEND=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
