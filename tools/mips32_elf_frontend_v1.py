#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mips32_expansion_frontend_v1 import DecodeError, FrontendError, convert

ELF_MAGIC = b"\x7fELF"
ELFCLASS32 = 1
ELFDATA2LSB = 1
EV_CURRENT = 1
ET_EXEC = 2
EM_MIPS = 8
SHT_SYMTAB = 2
SHT_RELA = 4
SHT_NOBITS = 8
SHT_REL = 9
SHF_ALLOC = 0x2
SHF_EXECINSTR = 0x4
STT_FUNC = 2
PROFILE = "expansion-v1"
FRONTEND_VERSION = "1.0.0"
ADAPTER_ID = "openrecomp.mips32-elf-expansion-v1"
MODULE_NAMESPACE = "openrecomp.mips32.elf.expansion-v1"


class MIPS32ELFError(ValueError):
    pass


def _cstr(blob: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(blob):
        return ""
    end = blob.find(b"\0", offset)
    if end < 0:
        end = len(blob)
    return blob[offset:end].decode("utf-8", "replace")


def _checked_slice(blob: bytes, offset: int, size: int, what: str) -> bytes:
    if offset < 0 or size < 0 or offset > len(blob) or size > len(blob) - offset:
        raise MIPS32ELFError(f"{what} out of bounds")
    return blob[offset : offset + size]


def load_mips32_elf(path: str | Path) -> dict:
    path = Path(path)
    blob = path.read_bytes()
    if len(blob) < 52 or blob[:4] != ELF_MAGIC:
        raise MIPS32ELFError("not ELF")
    ident = blob[:16]
    if ident[4] != ELFCLASS32:
        raise MIPS32ELFError("expected ELF32")
    if ident[5] != ELFDATA2LSB:
        raise MIPS32ELFError("expected little-endian ELF")
    if ident[6] != EV_CURRENT:
        raise MIPS32ELFError("unsupported ELF identification version")

    (
        _, e_type, e_machine, e_version, e_entry, e_phoff, e_shoff, e_flags,
        e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx,
    ) = struct.unpack_from("<16sHHIIIIIHHHHHH", blob, 0)

    if e_type != ET_EXEC:
        raise MIPS32ELFError(f"expected ET_EXEC, got {e_type}")
    if e_machine != EM_MIPS:
        raise MIPS32ELFError(f"expected EM_MIPS({EM_MIPS}), got {e_machine}")
    if e_version != EV_CURRENT or e_ehsize < 52:
        raise MIPS32ELFError("bad ELF header version/size")
    if e_shoff == 0 or e_shnum == 0 or e_shentsize < 40:
        raise MIPS32ELFError("missing section table")
    if e_shoff > len(blob) or e_shnum > (len(blob) - e_shoff) // e_shentsize:
        raise MIPS32ELFError("section table out of bounds")
    if e_shstrndx >= e_shnum:
        raise MIPS32ELFError("bad shstrndx")

    raw_sections: list[dict] = []
    for index in range(e_shnum):
        values = struct.unpack_from("<IIIIIIIIII", blob, e_shoff + index * e_shentsize)
        raw_sections.append({
            "index": index, "name_off": values[0], "type": values[1], "flags": values[2],
            "addr": values[3], "offset": values[4], "size": values[5], "link": values[6],
            "info": values[7], "addralign": values[8], "entsize": values[9],
        })

    shstr = raw_sections[e_shstrndx]
    if shstr["type"] == SHT_NOBITS:
        raise MIPS32ELFError("section-name string table cannot be SHT_NOBITS")
    section_names = _checked_slice(blob, shstr["offset"], shstr["size"], "section-name string table")

    sections: list[dict] = []
    for section in raw_sections:
        name = _cstr(section_names, section["name_off"])
        if section["type"] != SHT_NOBITS:
            _checked_slice(blob, section["offset"], section["size"], f"section {name or section['index']}")
        item = dict(section)
        item["name"] = name
        sections.append(item)

    text = next((section for section in sections if section["name"] == ".text"), None)
    if text is None or text["size"] == 0:
        raise MIPS32ELFError("missing .text")
    if text["type"] == SHT_NOBITS:
        raise MIPS32ELFError(".text must be file-backed; SHT_NOBITS rejected")
    if not (text["flags"] & SHF_ALLOC) or not (text["flags"] & SHF_EXECINSTR):
        raise MIPS32ELFError(".text must be allocatable and executable")
    if text["addr"] & 3 or text["size"] & 3 or text["offset"] & 3:
        raise MIPS32ELFError(".text address/offset/size must be 4-byte aligned")
    if not (text["addr"] <= e_entry < text["addr"] + text["size"]) or (e_entry & 3):
        raise MIPS32ELFError("entry outside/alignment-invalid .text")

    for section in sections:
        if section["type"] in {SHT_REL, SHT_RELA} and section["size"]:
            raise MIPS32ELFError(f"relocations are outside MIPS32 ELF ingestion V1: {section['name']}")

    allowed_alloc_metadata = {".reginfo", ".MIPS.abiflags"}
    for section in sections:
        if not (section["flags"] & SHF_ALLOC) or section["size"] == 0 or section["name"] == ".text":
            continue
        if section["name"] not in allowed_alloc_metadata:
            raise MIPS32ELFError(
                f"alloc section outside text-only MIPS32 ELF ingestion V1: {section['name'] or '<unnamed>'}"
            )

    symbols: list[dict] = []
    for section in sections:
        if section["type"] != SHT_SYMTAB:
            continue
        if section["entsize"] < 16 or section["size"] % section["entsize"]:
            raise MIPS32ELFError("malformed symbol table")
        if section["link"] >= len(sections):
            raise MIPS32ELFError("symbol table has invalid string-table link")
        strings_section = sections[section["link"]]
        if strings_section["type"] == SHT_NOBITS:
            raise MIPS32ELFError("symbol string table cannot be SHT_NOBITS")
        strings = _checked_slice(blob, strings_section["offset"], strings_section["size"], "symbol string table")
        count = section["size"] // section["entsize"]
        for index in range(count):
            offset = section["offset"] + index * section["entsize"]
            if offset + 16 > len(blob):
                raise MIPS32ELFError("symbol out of bounds")
            st_name, st_value, st_size, st_info, st_other, st_shndx = struct.unpack_from("<IIIBBH", blob, offset)
            symbols.append({
                "name": _cstr(strings, st_name), "value": st_value, "size": st_size,
                "bind": st_info >> 4, "type": st_info & 0xF, "other": st_other, "shndx": st_shndx,
            })

    functions: list[dict] = []
    seen_addresses: set[int] = set()
    for symbol in symbols:
        if symbol["type"] != STT_FUNC or symbol["shndx"] != text["index"] or not symbol["name"]:
            continue
        address = symbol["value"]
        if address & 3 or not (text["addr"] <= address < text["addr"] + text["size"]):
            raise MIPS32ELFError(f"function symbol {symbol['name']} has invalid .text address")
        if address in seen_addresses:
            raise MIPS32ELFError(f"duplicate function address 0x{address:x}")
        seen_addresses.add(address)
        functions.append({"id": symbol["name"], "address": address, "size": symbol["size"]})
    functions.sort(key=lambda item: item["address"])
    if not functions:
        raise MIPS32ELFError("no static STT_FUNC symbols found in .text")
    if e_entry not in {item["address"] for item in functions}:
        raise MIPS32ELFError("ELF entry point is not a declared STT_FUNC symbol")

    text_bytes = _checked_slice(blob, text["offset"], text["size"], ".text")
    words = {
        text["addr"] + offset: int.from_bytes(text_bytes[offset : offset + 4], "little")
        for offset in range(0, text["size"], 4)
    }

    return {
        "format": "ELF32", "endianness": "little", "architecture": "mips32-le",
        "machine": e_machine, "elf_flags": e_flags, "entry_point": e_entry,
        "input_size": len(blob), "input_sha256": hashlib.sha256(blob).hexdigest(),
        "program_header_offset": e_phoff, "program_header_entry_size": e_phentsize,
        "program_header_count": e_phnum,
        "text": {
            "index": text["index"], "addr": text["addr"], "offset": text["offset"],
            "size": text["size"], "sha256": hashlib.sha256(text_bytes).hexdigest(),
        },
        "functions": functions,
        "sections": [
            {key: section[key] for key in ("index", "name", "type", "flags", "addr", "offset", "size", "addralign")}
            for section in sections
        ],
        "words": words,
    }


def public_elf_metadata(loaded: dict) -> dict:
    return {key: value for key, value in loaded.items() if key != "words"}


def runtime_meta_for_elf(runtime: dict, loaded: dict) -> dict:
    if runtime.get("fixture_version") != FRONTEND_VERSION or runtime.get("profile") != PROFILE:
        raise MIPS32ELFError("runtime sidecar must use expansion-v1 fixture version 1.0.0")
    if runtime.get("architecture") != "mips32-le":
        raise MIPS32ELFError("MIPS32 ELF ingestion V1 requires runtime architecture mips32-le")
    if "entry_address" in runtime and runtime["entry_address"] != loaded["entry_point"]:
        raise MIPS32ELFError("runtime entry_address disagrees with ELF entry point")

    declared = runtime.get("functions")
    if declared:
        expected = [(item.get("id"), item.get("address")) for item in declared]
        actual = [(item["id"], item["address"]) for item in loaded["functions"]]
        if expected != actual:
            raise MIPS32ELFError("runtime function declarations disagree with ELF STT_FUNC symbols")

    merged = dict(runtime)
    merged["architecture"] = "mips32-le"
    merged["entry_address"] = loaded["entry_point"]
    merged["functions"] = [{"id": item["id"], "address": item["address"]} for item in loaded["functions"]]
    return merged


def _write_json(path: str | Path, value: dict) -> None:
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 8:
        print(
            "usage: mips32_elf_frontend_v1.py <input.elf> <runtime.json> <host-contract.json> "
            "<out-ir.json> <out-sidecar.json> <out-report.json> <out-elf-metadata.json>",
            file=sys.stderr,
        )
        return 2
    try:
        loaded = load_mips32_elf(argv[1])
        runtime = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        contract = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
        meta = runtime_meta_for_elf(runtime, loaded)
        ir, sidecar, report = convert(meta, loaded["words"], loaded["input_sha256"], contract)
        ir = dict(ir)
        ir["module_id"] = f"{MODULE_NAMESPACE}.{meta['fixture_id']}"
        ir["source"] = dict(ir["source"])
        ir["source"]["adapter"] = ADAPTER_ID
        report = dict(report)
        report.update({
            "input_format": "ELF32", "elf_machine": loaded["machine"],
            "elf_entry_point": loaded["entry_point"], "elf_text_sha256": loaded["text"]["sha256"],
            "elf_function_count": len(loaded["functions"]), "source_adapter": ADAPTER_ID,
        })
        _write_json(argv[4], ir)
        _write_json(argv[5], sidecar)
        _write_json(argv[6], report)
        _write_json(argv[7], public_elf_metadata(loaded))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, DecodeError, FrontendError, MIPS32ELFError) as exc:
        print(f"OPENRECOMP_MIPS32_ELF_FRONTEND=FAIL: {exc}", file=sys.stderr)
        return 2

    print(f"MIPS32_ELF_SHA256={loaded['input_sha256']}")
    print(f"MIPS32_ELF_ENTRY=0x{loaded['entry_point']:08x}")
    print(f"MIPS32_ELF_FUNCTIONS={len(loaded['functions'])}")
    print("OPENRECOMP_MIPS32_ELF_FRONTEND=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
