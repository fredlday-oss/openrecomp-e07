#!/usr/bin/env python3
"""OpenRecomp Phase-3 architecture-neutral ELF32 ingestion and guest image V1.

P3-02 provides the fail-closed ingestion layer for the audited CoreMark MIPS32
fixture and the deterministic guest section/data image consumed by later
Phase-3 stages.

Design:

* :func:`parse_elf32` performs architecture-neutral structural ingestion of a
  little-endian ELF32 file: identification, header, program header table,
  section header table, section names, file/memory bounds, integer overflow,
  alignment, load segment overlap, allocated-section containment and
  ``SHT_NOBITS`` handling.  ``SHT_NOBITS`` content is never read from the file.
* A :class:`TargetPolicy` adds target-specific validation (machine, ABI, ISA,
  entry policy) so MIPS-specific rules stay out of the neutral parser.
  :func:`ingest` combines both and builds the guest image.
* :class:`GuestImage` is the deterministic sparse bounds-checked memory model:
  file-backed bytes, zero-fill memory, executable code and writable data remain
  distinct, and every access is range checked.
* Every rejection raises :class:`ElfIngestError` or :class:`GuestImageError`
  with a deterministic classification code; no partial image is produced.

This module is OpenRecomp-original, standard-library only, and contains no
console assets, proprietary data or architecture-specific semantics.
"""
from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from typing import Any, Iterator, Sequence

ELF_MAGIC = b"\x7fELF"
ELFCLASS32 = 1
ELFDATA2LSB = 1
EV_CURRENT = 1
ELF32_HEADER_SIZE = 52
ELF32_PROGRAM_HEADER_SIZE = 32
ELF32_SECTION_HEADER_SIZE = 40
ELF32_SYMBOL_SIZE = 16
UINT32_MAX = 0xFFFFFFFF
UINT32_LIMIT = 0x100000000

SHT_NULL = 0
SHT_PROGBITS = 1
SHT_SYMTAB = 2
SHT_STRTAB = 3
SHT_RELA = 4
SHT_HASH = 5
SHT_DYNAMIC = 6
SHT_NOTE = 7
SHT_NOBITS = 8
SHT_REL = 9
SHT_SHLIB = 10
SHT_DYNSYM = 11

SHF_WRITE = 0x1
SHF_ALLOC = 0x2
SHF_EXECINSTR = 0x4
SHF_MERGE = 0x10
SHF_STRINGS = 0x20
SHF_MIPS_GPREL = 0x10000000

PT_NULL = 0
PT_LOAD = 1
PT_DYNAMIC = 2
PT_INTERP = 3
PT_NOTE = 4
PT_SHLIB = 5
PT_PHDR = 6
PT_TLS = 7
PT_GNU_STACK = 0x6474E551
PT_GNU_RELRO = 0x6474E552
PT_MIPS_REGINFO = 0x70000000
PT_MIPS_RTPROC = 0x70000001
PT_MIPS_OPTIONS = 0x70000002
PT_MIPS_ABIFLAGS = 0x70000003

PF_X = 0x1
PF_W = 0x2
PF_R = 0x4

ET_EXEC = 2

FILE_TYPE_NAMES = {
    0: "ET_NONE", 1: "ET_REL", 2: "ET_EXEC", 3: "ET_DYN", 4: "ET_CORE",
}

SECTION_TYPE_NAMES = {
    0: "SHT_NULL", 1: "SHT_PROGBITS", 2: "SHT_SYMTAB", 3: "SHT_STRTAB",
    4: "SHT_RELA", 5: "SHT_HASH", 6: "SHT_DYNAMIC", 7: "SHT_NOTE",
    8: "SHT_NOBITS", 9: "SHT_REL", 10: "SHT_SHLIB", 11: "SHT_DYNSYM",
    0x70000000: "SHT_MIPS_LIBLIST", 0x70000001: "SHT_MIPS_MSYM",
    0x70000002: "SHT_MIPS_CONFLICT", 0x70000003: "SHT_MIPS_GPTAB",
    0x70000004: "SHT_MIPS_UCODE", 0x70000005: "SHT_MIPS_DEBUG",
    0x70000006: "SHT_MIPS_REGINFO", 0x70000007: "SHT_MIPS_PACKAGE",
    0x70000008: "SHT_MIPS_PACKSYM", 0x70000009: "SHT_MIPS_RELD",
    0x70000013: "SHT_MIPS_OPTIONS", 0x7000002A: "SHT_MIPS_ABIFLAGS",
}

PROGRAM_HEADER_TYPE_NAMES = {
    0: "PT_NULL", 1: "PT_LOAD", 2: "PT_DYNAMIC", 3: "PT_INTERP",
    4: "PT_NOTE", 5: "PT_SHLIB", 6: "PT_PHDR", 7: "PT_TLS",
    0x6474E550: "PT_GNU_EH_FRAME", 0x6474E551: "PT_GNU_STACK",
    0x6474E552: "PT_GNU_RELRO", 0x70000000: "PT_MIPS_REGINFO",
    0x70000001: "PT_MIPS_RTPROC", 0x70000002: "PT_MIPS_OPTIONS",
    0x70000003: "PT_MIPS_ABIFLAGS",
}

UNSUPPORTED_SECTION_TYPES = {
    SHT_REL: "UNSUPPORTED_RELOCATION",
    SHT_RELA: "UNSUPPORTED_RELOCATION",
    SHT_DYNAMIC: "UNSUPPORTED_DYNAMIC",
    SHT_DYNSYM: "UNSUPPORTED_DYNAMIC",
    SHT_HASH: "UNSUPPORTED_DYNAMIC",
    SHT_SHLIB: "UNSUPPORTED_SHLIB",
}

UNSUPPORTED_PROGRAM_HEADER_TYPES = {
    PT_DYNAMIC: "UNSUPPORTED_DYNAMIC",
    PT_INTERP: "UNSUPPORTED_INTERP",
    PT_SHLIB: "UNSUPPORTED_SHLIB",
}

KIND_FILE_BACKED = "FILE_BACKED"
KIND_ZERO_FILL = "ZERO_FILL"


class ElfIngestError(ValueError):
    """Fail-closed ingestion rejection carrying a stable classification code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class GuestImageError(ValueError):
    """Fail-closed guest image access rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")


def evidence_json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def permissions_text(read: bool, write: bool, execute: bool) -> str:
    return ("r" if read else "-") + ("w" if write else "-") + ("x" if execute else "-")


def _require_u32_sum(base: int, size: int, code: str, detail: str) -> int:
    if base > UINT32_MAX or size > UINT32_MAX:
        raise ElfIngestError(code, detail)
    end = base + size
    if end > UINT32_MAX:
        raise ElfIngestError(code, detail)
    return end


@dataclass(frozen=True)
class ElfIdentification:
    elf_class: int
    data_encoding: int
    ident_version: int
    osabi: int
    abi_version: int

    @property
    def class_name(self) -> str:
        return "ELF32" if self.elf_class == ELFCLASS32 else f"ELFCLASS_UNKNOWN({self.elf_class})"

    @property
    def endianness(self) -> str:
        return "little" if self.data_encoding == ELFDATA2LSB else f"ENDIAN_UNKNOWN({self.data_encoding})"

    def describe(self) -> dict[str, Any]:
        return {
            "elf_class": self.elf_class,
            "class_name": self.class_name,
            "data_encoding": self.data_encoding,
            "endianness": self.endianness,
            "ident_version": self.ident_version,
            "osabi": self.osabi,
            "abi_version": self.abi_version,
        }


@dataclass(frozen=True)
class ElfHeader:
    e_type: int
    e_machine: int
    e_version: int
    e_entry: int
    e_phoff: int
    e_shoff: int
    e_flags: int
    e_ehsize: int
    e_phentsize: int
    e_phnum: int
    e_shentsize: int
    e_shnum: int
    e_shstrndx: int

    @property
    def type_name(self) -> str:
        return FILE_TYPE_NAMES.get(self.e_type, f"ET_UNKNOWN({self.e_type})")

    @property
    def program_table_size(self) -> int:
        return self.e_phnum * self.e_phentsize

    @property
    def section_table_size(self) -> int:
        return self.e_shnum * self.e_shentsize


@dataclass(frozen=True)
class ProgramHeader:
    index: int
    p_type: int
    p_offset: int
    p_vaddr: int
    p_paddr: int
    p_filesz: int
    p_memsz: int
    p_flags: int
    p_align: int

    @property
    def type_name(self) -> str:
        return PROGRAM_HEADER_TYPE_NAMES.get(self.p_type, f"PT_UNKNOWN(0x{self.p_type:x})")

    @property
    def read(self) -> bool:
        return bool(self.p_flags & PF_R)

    @property
    def write(self) -> bool:
        return bool(self.p_flags & PF_W)

    @property
    def execute(self) -> bool:
        return bool(self.p_flags & PF_X)

    @property
    def permissions(self) -> str:
        return permissions_text(self.read, self.write, self.execute)

    @property
    def file_end(self) -> int:
        return self.p_offset + self.p_filesz

    @property
    def memory_end(self) -> int:
        return self.p_vaddr + self.p_memsz

    @property
    def zero_fill_size(self) -> int:
        return self.p_memsz - self.p_filesz

    def describe(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "type": self.p_type,
            "type_name": self.type_name,
            "offset": self.p_offset,
            "vaddr": f"0x{self.p_vaddr:08x}",
            "paddr": f"0x{self.p_paddr:08x}",
            "filesz": self.p_filesz,
            "memsz": self.p_memsz,
            "flags": self.p_flags,
            "permissions": self.permissions,
            "align": self.p_align,
        }


@dataclass(frozen=True)
class SectionHeader:
    index: int
    name: str
    name_offset: int
    sh_type: int
    sh_flags: int
    sh_addr: int
    sh_offset: int
    sh_size: int
    sh_link: int
    sh_info: int
    sh_addralign: int
    sh_entsize: int

    @property
    def type_name(self) -> str:
        return SECTION_TYPE_NAMES.get(self.sh_type, f"SHT_UNKNOWN(0x{self.sh_type:x})")

    @property
    def file_backed(self) -> bool:
        return self.sh_type != SHT_NOBITS

    @property
    def alloc(self) -> bool:
        return bool(self.sh_flags & SHF_ALLOC)

    @property
    def write(self) -> bool:
        return bool(self.sh_flags & SHF_WRITE)

    @property
    def execute(self) -> bool:
        return bool(self.sh_flags & SHF_EXECINSTR)

    @property
    def permissions(self) -> str:
        return permissions_text(
            self.alloc, self.write and self.alloc, self.execute and self.alloc)

    def describe(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "name_offset": self.name_offset,
            "type": self.sh_type,
            "type_name": self.type_name,
            "flags": self.sh_flags,
            "permissions": self.permissions,
            "alloc": self.alloc,
            "write": self.write,
            "execute": self.execute,
            "file_backed": self.file_backed,
            "addr": f"0x{self.sh_addr:08x}" if self.sh_addr else "0x00000000",
            "offset": self.sh_offset,
            "size": self.sh_size,
            "link": self.sh_link,
            "info": self.sh_info,
            "addralign": self.sh_addralign,
            "entsize": self.sh_entsize,
        }


@dataclass(frozen=True)
class SectionPlacement:
    index: int
    name: str
    kind: str
    vaddr: int
    size: int
    file_offset: int
    file_size: int
    align: int
    read: bool
    write: bool
    execute: bool
    segment_index: int
    section_type: int

    @property
    def memory_end(self) -> int:
        return self.vaddr + self.size

    @property
    def permissions(self) -> str:
        return permissions_text(self.read, self.write, self.execute)

    def describe(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "kind": self.kind,
            "vaddr": f"0x{self.vaddr:08x}",
            "size": self.size,
            "file_offset": self.file_offset,
            "file_size": self.file_size,
            "align": self.align,
            "permissions": self.permissions,
            "segment_index": self.segment_index,
            "section_type": self.section_type,
        }


@dataclass(frozen=True)
class SymbolEntry:
    index: int
    name: str
    name_offset: int
    value: int
    size: int
    info: int
    other: int
    shndx: int

    @property
    def bind(self) -> int:
        return self.info >> 4

    @property
    def sym_type(self) -> int:
        return self.info & 0xF

    @property
    def defined(self) -> bool:
        return self.shndx != 0

    @property
    def is_function(self) -> bool:
        return self.sym_type == 2

    def describe(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "value": f"0x{self.value:08x}",
            "size": self.size,
            "bind": self.bind,
            "type": self.sym_type,
            "shndx": self.shndx,
        }


@dataclass(frozen=True)
class ParsedElf:
    data: bytes
    identification: ElfIdentification
    header: ElfHeader
    program_headers: tuple[ProgramHeader, ...]
    sections: tuple[SectionHeader, ...]
    load_segments: tuple[ProgramHeader, ...]
    section_placements: tuple[SectionPlacement, ...]

    @property
    def size(self) -> int:
        return len(self.data)

    def section(self, name: str) -> SectionHeader | None:
        return next((item for item in self.sections if item.name == name), None)

    def placement(self, name: str) -> SectionPlacement | None:
        return next((item for item in self.section_placements if item.name == name), None)

    def executable_regions(self) -> tuple[ProgramHeader, ...]:
        return tuple(item for item in self.load_segments if item.execute)

    def relocation_section_count(self) -> int:
        return sum(1 for item in self.sections if item.sh_type in (SHT_REL, SHT_RELA))

    def dynamic_section_count(self) -> int:
        return sum(1 for item in self.sections if item.sh_type in (SHT_DYNAMIC, SHT_DYNSYM))

    def symbols(self) -> tuple[SymbolEntry, ...]:
        entries: list[SymbolEntry] = []
        for section in self.sections:
            if section.sh_type != SHT_SYMTAB:
                continue
            if section.sh_size % section.sh_entsize or section.sh_entsize != ELF32_SYMBOL_SIZE:
                raise ElfIngestError(
                    "MALFORMED_SYMTAB",
                    f"section={section.name} entsize={section.sh_entsize} size={section.sh_size}")
            if not 0 < section.sh_link < len(self.sections):
                raise ElfIngestError("MALFORMED_SYMTAB", f"section={section.name} link={section.sh_link}")
            strings_section = self.sections[section.sh_link]
            if strings_section.sh_type != SHT_STRTAB:
                raise ElfIngestError("MALFORMED_SYMTAB", f"section={section.name} string-link-not-strtab")
            strings = self.data[strings_section.sh_offset:strings_section.sh_offset + strings_section.sh_size]
            count = section.sh_size // section.sh_entsize
            for index in range(count):
                offset = section.sh_offset + index * section.sh_entsize
                name_offset, value, size, info, other, shndx = struct.unpack_from(
                    "<IIIBBH", self.data, offset)
                if name_offset >= len(strings):
                    if index == 0 and name_offset == 0:
                        name = ""
                    else:
                        raise ElfIngestError(
                            "MALFORMED_SYMTAB", f"symbol={index} name_offset={name_offset}")
                else:
                    end = strings.find(b"\x00", name_offset)
                    if end < 0:
                        raise ElfIngestError(
                            "MALFORMED_SYMTAB", f"symbol={index} unterminated-name")
                    name = strings[name_offset:end].decode("ascii", errors="replace")
                entries.append(SymbolEntry(
                    index=index, name=name, name_offset=name_offset, value=value,
                    size=size, info=info, other=other, shndx=shndx))
        return tuple(entries)


class GuestRegion:
    """One loaded, bounds-checked region of the deterministic guest image."""

    def __init__(self, index: int, segment: ProgramHeader, file_bytes: bytes) -> None:
        self.index = index
        self.segment_index = segment.index
        self.vaddr = segment.p_vaddr
        self.memsz = segment.p_memsz
        self.filesz = segment.p_filesz
        self.file_offset = segment.p_offset
        self.align = segment.p_align
        self.read = segment.read
        self.write = segment.write
        self.execute = segment.execute
        self.file_bytes = bytes(file_bytes)
        self.initial_bytes = bytes(file_bytes) + b"\x00" * self.zero_fill_size
        self.bytes = bytearray(self.initial_bytes)
        self.file_sha256 = sha256_bytes(self.file_bytes)
        self.content_sha256 = sha256_bytes(self.initial_bytes)

    @property
    def memory_end(self) -> int:
        return self.vaddr + self.memsz

    @property
    def zero_fill_size(self) -> int:
        return self.memsz - self.filesz

    @property
    def permissions(self) -> str:
        return permissions_text(self.read, self.write, self.execute)

    @property
    def kind(self) -> str:
        return KIND_ZERO_FILL if self.filesz == 0 else KIND_FILE_BACKED

    def describe(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "segment_index": self.segment_index,
            "vaddr": f"0x{self.vaddr:08x}",
            "memsz": self.memsz,
            "filesz": self.filesz,
            "file_offset": self.file_offset,
            "permissions": self.permissions,
            "align": self.align,
            "kind": self.kind,
            "zero_fill_size": self.zero_fill_size,
            "file_sha256": self.file_sha256,
            "content_sha256": self.content_sha256,
        }


class GuestImage:
    """Sparse deterministic guest memory: file-backed bytes plus zero-fill.

    ``content_sha256``/``file_sha256`` always describe the pristine load-time
    image; ``write`` mutates accessibility state but never the recorded
    load-time identity.
    """

    def __init__(
        self,
        regions: Sequence[GuestRegion],
        placements: Sequence[SectionPlacement],
    ) -> None:
        self.regions = tuple(regions)
        self.placements = tuple(placements)
        self._by_addr = {region.vaddr: region for region in self.regions}

    def region_at(self, addr: int) -> GuestRegion | None:
        region = self._by_addr.get(addr)
        if region is not None:
            return region
        for candidate in self.regions:
            if candidate.vaddr <= addr < candidate.memory_end:
                return candidate
        return None

    def placement(self, name: str) -> SectionPlacement | None:
        return next((item for item in self.placements if item.name == name), None)

    def is_mapped(self, addr: int, size: int = 1) -> bool:
        if size < 0 or addr < 0 or addr > UINT32_MAX:
            return False
        if size == 0:
            return addr <= UINT32_MAX
        if addr + size > UINT32_LIMIT:
            return False
        position = addr
        remaining = size
        while remaining:
            region = self.region_at(position)
            if region is None:
                return False
            step = min(remaining, region.memory_end - position)
            position += step
            remaining -= step
        return True

    def _walk(self, addr: int, size: int) -> Iterator[tuple[GuestRegion, int, int]]:
        if not isinstance(size, int) or size < 0:
            raise GuestImageError("INVALID_SIZE", f"size={size!r}")
        if addr < 0 or addr > UINT32_MAX:
            raise GuestImageError("RANGE_OVERFLOW", f"addr=0x{addr:x}")
        if size and addr + size > UINT32_LIMIT:
            raise GuestImageError("RANGE_OVERFLOW", f"addr=0x{addr:x} size={size}")
        position = addr
        remaining = size
        while remaining:
            region = self.region_at(position)
            if region is None:
                raise GuestImageError("UNMAPPED_ADDRESS", f"addr=0x{position:08x}")
            offset = position - region.vaddr
            step = min(remaining, region.memsz - offset)
            yield region, offset, step
            position += step
            remaining -= step

    def read(self, addr: int, size: int) -> bytes:
        chunks = bytearray()
        for region, offset, step in self._walk(addr, size):
            chunks += region.bytes[offset:offset + step]
        return bytes(chunks)

    def read_u32(self, addr: int) -> int:
        return struct.unpack("<I", self.read(addr, 4))[0]

    def write(self, addr: int, payload: bytes) -> None:
        position = addr
        for region, offset, step in self._walk(addr, len(payload)):
            if not region.write:
                raise GuestImageError("READONLY_VIOLATION", f"addr=0x{position:08x}")
            region.bytes[offset:offset + step] = payload[position - addr:position - addr + step]
            position += step

    def zero_fill_ranges(self) -> tuple[tuple[int, int], ...]:
        ranges: list[tuple[int, int]] = []
        for region in self.regions:
            if region.zero_fill_size:
                ranges.append((region.vaddr + region.filesz, region.zero_fill_size))
        return tuple(ranges)

    def _concat(self, predicate) -> bytes:
        chunks = bytearray()
        for region in sorted(self.regions, key=lambda item: item.vaddr):
            if not predicate(region):
                continue
            chunks += region.initial_bytes
        return bytes(chunks)

    def file_backed_sha256(self) -> str:
        chunks = bytearray()
        for region in sorted(self.regions, key=lambda item: item.vaddr):
            chunks += region.file_bytes
        return sha256_bytes(bytes(chunks))

    def zero_extended_sha256(self) -> str:
        return sha256_bytes(self._concat(lambda region: True))

    def executable_sha256(self) -> str:
        return sha256_bytes(self._concat(lambda region: region.execute))

    def readonly_sha256(self) -> str:
        return sha256_bytes(self._concat(
            lambda region: region.read and not region.write and not region.execute))

    def writable_initialized_sha256(self) -> str:
        chunks = bytearray()
        for region in sorted(self.regions, key=lambda item: item.vaddr):
            if region.write:
                chunks += region.file_bytes
        return sha256_bytes(bytes(chunks))

    def zero_fill_sha256(self) -> str:
        chunks = bytearray()
        for region in sorted(self.regions, key=lambda item: item.vaddr):
            chunks += b"\x00" * region.zero_fill_size
        return sha256_bytes(bytes(chunks))

    def section_bytes(self, name: str) -> bytes:
        placement = self.placement(name)
        if placement is None:
            raise GuestImageError("UNKNOWN_SECTION", name)
        return self.read(placement.vaddr, placement.size)

    def describe(self, source_sha256: str, source_size: int, entry: int) -> dict[str, Any]:
        bss_placements = [item for item in self.placements if item.kind == KIND_ZERO_FILL]
        zero_fill_description = [
            {"name": item.name, "vaddr": f"0x{item.vaddr:08x}", "size": item.size}
            for item in sorted(bss_placements, key=lambda item: item.vaddr)
        ]
        payload: dict[str, Any] = {
            "source_sha256": source_sha256,
            "source_size": source_size,
            "entry": f"0x{entry:08x}",
            "regions": [
                region.describe()
                for region in sorted(self.regions, key=lambda item: item.vaddr)
            ],
            "sections": [
                item.describe()
                for item in sorted(self.placements, key=lambda item: item.vaddr)
            ],
            "hashes": {
                "file_backed_sha256": self.file_backed_sha256(),
                "zero_extended_sha256": self.zero_extended_sha256(),
                "executable_sha256": self.executable_sha256(),
                "readonly_sha256": self.readonly_sha256(),
                "writable_initialized_sha256": self.writable_initialized_sha256(),
                "zero_fill_sha256": self.zero_fill_sha256(),
                "bss_zero_fill_sha256": sha256_bytes(
                    b"".join(self.section_bytes(item.name) for item in sorted(
                        bss_placements, key=lambda item: item.vaddr))),
                "bss_description_sha256": sha256_bytes(
                    canonical_json_bytes(zero_fill_description)),
            },
            "zero_fill": {
                "description": zero_fill_description,
                "total_bytes": sum(item.size for item in bss_placements),
            },
        }
        payload["image_sha256"] = sha256_bytes(canonical_json_bytes(payload))
        return payload


class TargetPolicy:
    """Target-specific validation hook applied after structural ingestion."""

    name = "abstract"

    def validate(self, parsed: ParsedElf) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class IngestedElf:
    parsed: ParsedElf
    image: GuestImage
    identity: dict[str, Any]


def _parse_identification(data: bytes) -> ElfIdentification:
    return ElfIdentification(
        elf_class=data[4],
        data_encoding=data[5],
        ident_version=data[6],
        osabi=data[7],
        abi_version=data[8],
    )


def _read_section_table(parsed: ParsedElf) -> tuple[SectionHeader, ...]:
    header = parsed.header
    chunks = parsed.data
    names_section = parsed.sections[header.e_shstrndx]
    names = chunks[names_section.sh_offset:names_section.sh_offset + names_section.sh_size]
    if not names or names[0] != 0:
        raise ElfIngestError("MALFORMED_SECTION_NAME_TABLE", "missing leading NUL")
    resolved: list[SectionHeader] = []
    for raw in parsed.sections:
        name_offset = raw.name_offset
        if name_offset >= len(names):
            raise ElfIngestError(
                "MALFORMED_SECTION_NAME_TABLE",
                f"section={raw.index} name_offset={name_offset}")
        end = names.find(b"\x00", name_offset)
        if end < 0:
            raise ElfIngestError(
                "MALFORMED_SECTION_NAME_TABLE",
                f"section={raw.index} unterminated name")
        try:
            name = names[name_offset:end].decode("ascii")
        except UnicodeDecodeError:
            raise ElfIngestError(
                "MALFORMED_SECTION_NAME_TABLE",
                f"section={raw.index} non-ascii name") from None
        resolved.append(SectionHeader(
            index=raw.index, name=name, name_offset=raw.name_offset,
            sh_type=raw.sh_type, sh_flags=raw.sh_flags, sh_addr=raw.sh_addr,
            sh_offset=raw.sh_offset, sh_size=raw.sh_size, sh_link=raw.sh_link,
            sh_info=raw.sh_info, sh_addralign=raw.sh_addralign,
            sh_entsize=raw.sh_entsize))
    return tuple(resolved)


def _validate_allocated_sections(
    data: bytes,
    sections: Sequence[SectionHeader],
    load_segments: Sequence[ProgramHeader],
) -> tuple[SectionPlacement, ...]:
    placements: list[SectionPlacement] = []
    for section in sections:
        if not section.alloc or section.sh_size == 0:
            continue
        if section.sh_addr > UINT32_MAX - section.sh_size:
            raise ElfIngestError(
                "SECTION_MEMORY_OVERFLOW", f"section={section.name}")
        if section.sh_addralign > 1:
            if not is_power_of_two(section.sh_addralign):
                raise ElfIngestError(
                    "IMPOSSIBLE_SECTION_ALIGNMENT",
                    f"section={section.name} align={section.sh_addralign}")
            if section.sh_addr % section.sh_addralign:
                raise ElfIngestError(
                    "IMPOSSIBLE_SECTION_ALIGNMENT",
                    f"section={section.name} addr=0x{section.sh_addr:x} align={section.sh_addralign}")
        zero_fill = section.sh_type == SHT_NOBITS
        candidates = [
            segment for segment in load_segments
            if segment.p_vaddr <= section.sh_addr
            and section.sh_addr + section.sh_size
            <= segment.p_vaddr + (segment.p_memsz if zero_fill else segment.p_filesz)
        ]
        if len(candidates) != 1:
            raise ElfIngestError(
                "SECTION_LOAD_MISMATCH", f"section={section.name} vaddr=0x{section.sh_addr:x}")
        segment = candidates[0]
        if zero_fill:
            if section.sh_addr < segment.p_vaddr + segment.p_filesz:
                raise ElfIngestError(
                    "NOBITS_OUTSIDE_ZERO_FILL", f"section={section.name}")
            file_offset = 0
            file_size = 0
        else:
            if section.sh_offset < segment.p_offset \
                    or section.sh_offset + section.sh_size > segment.p_offset + segment.p_filesz:
                raise ElfIngestError(
                    "SECTION_LOAD_MISMATCH", f"section={section.name} file-range")
            if section.sh_addr - segment.p_vaddr != section.sh_offset - segment.p_offset:
                raise ElfIngestError(
                    "SECTION_LOAD_MISMATCH", f"section={section.name} offset-congruence")
            file_offset = section.sh_offset
            file_size = section.sh_size
        placements.append(SectionPlacement(
            index=section.index,
            name=section.name,
            kind=KIND_ZERO_FILL if zero_fill else KIND_FILE_BACKED,
            vaddr=section.sh_addr,
            size=section.sh_size,
            file_offset=file_offset,
            file_size=file_size,
            align=section.sh_addralign,
            read=section.alloc,
            write=section.write and section.alloc,
            execute=section.execute and section.alloc,
            segment_index=segment.index,
            section_type=section.sh_type,
        ))
    ordered = sorted(placements, key=lambda item: (item.vaddr, item.index))
    for first, second in zip(ordered, ordered[1:]):
        if first.memory_end > second.vaddr:
            raise ElfIngestError(
                "OVERLAPPING_ALLOC_SECTIONS",
                f"{first.name}@0x{first.vaddr:x}+{first.size} {second.name}@0x{second.vaddr:x}")
    return tuple(placements)


def parse_elf32(data: bytes) -> ParsedElf:
    """Structurally ingest a little-endian ELF32 image (no machine policy)."""
    total = len(data)
    if total < 16 or data[:4] != ELF_MAGIC:
        raise ElfIngestError("INVALID_MAGIC", f"size={total}")
    identification = _parse_identification(data)
    if identification.elf_class != ELFCLASS32:
        raise ElfIngestError("UNSUPPORTED_CLASS", f"class={identification.elf_class}")
    if identification.data_encoding != ELFDATA2LSB:
        raise ElfIngestError(
            "UNSUPPORTED_ENDIANNESS", f"data_encoding={identification.data_encoding}")
    if identification.ident_version != EV_CURRENT:
        raise ElfIngestError(
            "UNSUPPORTED_IDENT_VERSION", f"ident_version={identification.ident_version}")
    if total < ELF32_HEADER_SIZE:
        raise ElfIngestError("TRUNCATED_ELF_HEADER", f"size={total}")

    fields = struct.unpack_from("<HHIIIIIHHHHHH", data, 0x10)
    header = ElfHeader(*fields)
    if header.e_version != EV_CURRENT:
        raise ElfIngestError("UNSUPPORTED_VERSION", f"e_version={header.e_version}")
    if header.e_ehsize != ELF32_HEADER_SIZE:
        raise ElfIngestError("UNSUPPORTED_HEADER_SIZE", f"e_ehsize={header.e_ehsize}")

    if header.e_phnum:
        if header.e_phentsize != ELF32_PROGRAM_HEADER_SIZE:
            raise ElfIngestError(
                "INVALID_PROGRAM_TABLE_SIZE", f"e_phentsize={header.e_phentsize}")
        _require_u32_sum(
            header.e_phoff, header.program_table_size, "PROGRAM_TABLE_OVERFLOW",
            f"phoff={header.e_phoff} phnum={header.e_phnum}")
        if header.e_phoff > total or header.program_table_size > total - header.e_phoff:
            raise ElfIngestError(
                "PROGRAM_TABLE_OUT_OF_BOUNDS",
                f"phoff={header.e_phoff} size={header.program_table_size} file={total}")

    program_headers: list[ProgramHeader] = []
    for index in range(header.e_phnum):
        offset = header.e_phoff + index * header.e_phentsize
        values = struct.unpack_from("<IIIIIIII", data, offset)
        program_headers.append(ProgramHeader(index, *values))

    for program in program_headers:
        code = UNSUPPORTED_PROGRAM_HEADER_TYPES.get(program.p_type)
        if code is not None:
            raise ElfIngestError(code, f"program_header={program.index}")

    load_segments: list[ProgramHeader] = []
    for program in program_headers:
        if program.p_type != PT_LOAD:
            continue
        if program.p_memsz == 0:
            continue
        if program.p_filesz > program.p_memsz:
            raise ElfIngestError(
                "INVALID_SEGMENT_SIZE",
                f"program_header={program.index} filesz={program.p_filesz} memsz={program.p_memsz}")
        if program.execute and program.p_memsz > program.p_filesz:
            raise ElfIngestError(
                "NOBITS_EXEC_TRAP", f"program_header={program.index}")
        _require_u32_sum(
            program.p_offset, program.p_filesz, "SEGMENT_RANGE_OVERFLOW",
            f"program_header={program.index}")
        _require_u32_sum(
            program.p_vaddr, program.p_memsz, "SEGMENT_MEMORY_OVERFLOW",
            f"program_header={program.index}")
        if program.p_offset > total or program.p_filesz > total - program.p_offset:
            raise ElfIngestError(
                "SEGMENT_FILE_RANGE_OUT_OF_BOUNDS", f"program_header={program.index}")
        if program.p_align > 1:
            if not is_power_of_two(program.p_align):
                raise ElfIngestError(
                    "IMPOSSIBLE_SEGMENT_ALIGNMENT",
                    f"program_header={program.index} align={program.p_align}")
            if program.p_vaddr % program.p_align != program.p_offset % program.p_align:
                raise ElfIngestError(
                    "IMPOSSIBLE_SEGMENT_ALIGNMENT",
                    f"program_header={program.index} vaddr-offset-congruence")
        load_segments.append(program)

    if not load_segments:
        raise ElfIngestError("NO_LOADABLE_SEGMENTS", "no non-empty PT_LOAD segments")

    load_segments.sort(key=lambda item: (item.p_vaddr, item.index))
    for first, second in zip(load_segments, load_segments[1:]):
        if first.memory_end > second.p_vaddr:
            raise ElfIngestError(
                "OVERLAPPING_LOAD_RANGES",
                f"program_header={first.index} program_header={second.index}")
    file_ordered = sorted(load_segments, key=lambda item: (item.p_offset, item.index))
    for first, second in zip(file_ordered, file_ordered[1:]):
        if first.file_end > second.p_offset:
            raise ElfIngestError(
                "OVERLAPPING_LOAD_FILE_RANGES",
                f"program_header={first.index} program_header={second.index}")

    if header.e_shnum == 0 or header.e_shoff == 0:
        raise ElfIngestError("MISSING_SECTION_TABLE", "no section header table")
    if header.e_shentsize != ELF32_SECTION_HEADER_SIZE:
        raise ElfIngestError(
            "INVALID_SECTION_TABLE_SIZE", f"e_shentsize={header.e_shentsize}")
    _require_u32_sum(
        header.e_shoff, header.section_table_size, "SECTION_TABLE_OVERFLOW",
        f"shoff={header.e_shoff} shnum={header.e_shnum}")
    if header.e_shoff > total or header.section_table_size > total - header.e_shoff:
        raise ElfIngestError(
            "SECTION_TABLE_OUT_OF_BOUNDS",
            f"shoff={header.e_shoff} size={header.section_table_size} file={total}")

    raw_sections: list[SectionHeader] = []
    for index in range(header.e_shnum):
        offset = header.e_shoff + index * header.e_shentsize
        values = struct.unpack_from("<IIIIIIIIII", data, offset)
        raw_sections.append(SectionHeader(
            index=index, name="", name_offset=values[0], sh_type=values[1],
            sh_flags=values[2], sh_addr=values[3], sh_offset=values[4],
            sh_size=values[5], sh_link=values[6], sh_info=values[7],
            sh_addralign=values[8], sh_entsize=values[9]))

    if raw_sections[0].sh_type != SHT_NULL or raw_sections[0].sh_size != 0:
        raise ElfIngestError("MALFORMED_SECTION_ZERO", "section 0 must be SHT_NULL with size 0")
    if header.e_shstrndx == 0 or header.e_shstrndx >= header.e_shnum:
        raise ElfIngestError(
            "MALFORMED_SECTION_NAME_TABLE", f"e_shstrndx={header.e_shstrndx} shnum={header.e_shnum}")
    names_section = raw_sections[header.e_shstrndx]
    if names_section.sh_type != SHT_STRTAB or names_section.sh_size == 0:
        raise ElfIngestError(
            "MALFORMED_SECTION_NAME_TABLE",
            f"shstrndx={header.e_shstrndx} type=0x{names_section.sh_type:x}")
    if names_section.sh_offset > total or names_section.sh_size > total - names_section.sh_offset:
        raise ElfIngestError("SECTION_OUT_OF_BOUNDS", "section-name-table")

    for section in raw_sections:
        code = UNSUPPORTED_SECTION_TYPES.get(section.sh_type)
        if code is not None:
            raise ElfIngestError(code, f"section={section.index}")
        if section.sh_type == SHT_NOBITS or section.sh_size == 0:
            continue
        _require_u32_sum(
            section.sh_offset, section.sh_size, "SECTION_RANGE_OVERFLOW",
            f"section={section.index}")
        if section.sh_offset > total or section.sh_size > total - section.sh_offset:
            raise ElfIngestError(
                "SECTION_OUT_OF_BOUNDS", f"section={section.index}")

    preliminary = ParsedElf(
        data=data,
        identification=identification,
        header=header,
        program_headers=tuple(program_headers),
        sections=tuple(raw_sections),
        load_segments=tuple(load_segments),
        section_placements=(),
    )
    sections = _read_section_table(preliminary)
    placements = _validate_allocated_sections(data, sections, load_segments)
    return ParsedElf(
        data=data,
        identification=identification,
        header=header,
        program_headers=tuple(program_headers),
        sections=sections,
        load_segments=tuple(load_segments),
        section_placements=placements,
    )


def build_image(parsed: ParsedElf) -> GuestImage:
    regions: list[GuestRegion] = []
    for index, segment in enumerate(parsed.load_segments):
        file_bytes = parsed.data[segment.p_offset:segment.p_offset + segment.p_filesz]
        if len(file_bytes) != segment.p_filesz:
            raise ElfIngestError(
                "SEGMENT_FILE_RANGE_OUT_OF_BOUNDS", f"program_header={segment.index}")
        regions.append(GuestRegion(index, segment, file_bytes))
    return GuestImage(regions, parsed.section_placements)


def ingest(data: bytes, policy: TargetPolicy) -> IngestedElf:
    parsed = parse_elf32(data)
    identity = policy.validate(parsed)
    image = build_image(parsed)
    return IngestedElf(parsed=parsed, image=image, identity=identity)
