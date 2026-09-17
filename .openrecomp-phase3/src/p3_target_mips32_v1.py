#!/usr/bin/env python3
"""OpenRecomp Phase-3 MIPS32 O32 target policy V1 (P3-02).

Target-specific validation for the audited CoreMark fixture profile:

* ELF32 little-endian ``EM_MIPS`` ``ET_EXEC``;
* ``EF_MIPS_ABI_O32`` with ``EF_MIPS_ARCH_32`` (MIPS32 ISA, O32 ABI);
* non-PIC (neither ``EF_MIPS_PIC`` nor ``EF_MIPS_CPIC``);
* file-backed word-aligned ``.text`` with an in-range entry point;
* static/freestanding posture: the neutral parser already rejects dynamic,
  relocation, hash and interpreter forms.

The policy adds no instruction semantics; it only classifies the target
identity of an already structurally ingested image.  Failures raise
:class:`~p3_elf_image_v1.ElfIngestError` with a stable code.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

_SRC_DIR = pathlib.Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from p3_elf_image_v1 import (  # noqa: E402
    KIND_FILE_BACKED,
    ElfIngestError,
    ParsedElf,
    SHT_NOBITS,
    TargetPolicy,
)

EM_MIPS = 8
ET_EXEC = 2
EF_MIPS_NOREORDER = 0x00000001
EF_MIPS_PIC = 0x00000002
EF_MIPS_CPIC = 0x00000004
EF_MIPS_ABI_O32 = 0x00001000
EF_MIPS_ABI_MASK = 0x0000F000
EF_MIPS_ARCH_32 = 0x50000000
EF_MIPS_ARCH_MASK = 0xF0000000

REQUIRED_SECTIONS = (".text", ".rodata", ".data", ".bss")


class Mips32O32Policy(TargetPolicy):
    """Audited MIPS32 O32 soft-float static non-PIC executable policy."""

    name = "mips32-o32-soft-float-static"
    expected_machine = EM_MIPS
    expected_machine_name = "EM_MIPS"

    def validate(self, parsed: ParsedElf) -> dict[str, Any]:
        header = parsed.header
        if header.e_machine != EM_MIPS:
            raise ElfIngestError(
                "UNSUPPORTED_MACHINE",
                f"e_machine={header.e_machine} expected={EM_MIPS}")
        if header.e_type != ET_EXEC:
            raise ElfIngestError(
                "UNSUPPORTED_TYPE", f"e_type={header.e_type} expected={ET_EXEC}")
        flags = header.e_flags
        if flags & EF_MIPS_ABI_MASK != EF_MIPS_ABI_O32:
            raise ElfIngestError(
                "UNSUPPORTED_ABI", f"ef_mips_abi=0x{flags & EF_MIPS_ABI_MASK:08x}")
        if flags & EF_MIPS_ARCH_MASK != EF_MIPS_ARCH_32:
            raise ElfIngestError(
                "UNSUPPORTED_ARCH", f"ef_mips_arch=0x{flags & EF_MIPS_ARCH_MASK:08x}")
        if flags & (EF_MIPS_PIC | EF_MIPS_CPIC):
            raise ElfIngestError(
                "UNSUPPORTED_PIC", f"ef_mips_pic_bits=0x{flags & (EF_MIPS_PIC | EF_MIPS_CPIC):08x}")
        if header.e_entry & 3:
            raise ElfIngestError("ENTRY_MISALIGNED", f"entry=0x{header.e_entry:08x}")

        executable = [
            section for section in parsed.sections
            if section.alloc and section.execute and section.sh_size > 0
        ]
        text = parsed.section(".text")
        if text is None or not (text.alloc and text.execute):
            raise ElfIngestError(
                "MISSING_EXECUTABLE_SECTION",
                f"executable_alloc_sections={[item.name for item in executable]}")

        for section in executable:
            if section.sh_type == SHT_NOBITS:
                raise ElfIngestError(
                    "EXECUTABLE_SECTION_NOBITS", f"section={section.name}")
            if section.sh_size % 4 or section.sh_addr % 4:
                raise ElfIngestError(
                    "EXECUTABLE_SECTION_MISALIGNED",
                    f"section={section.name} addr=0x{section.sh_addr:x} size={section.sh_size}")
        if parsed.placement(text.name) is None \
                or parsed.placement(text.name).kind != KIND_FILE_BACKED:
            raise ElfIngestError("EXECUTABLE_SECTION_NOT_FILE_BACKED", f"section={text.name}")

        entry_region = None
        for segment in parsed.load_segments:
            if segment.execute and segment.p_vaddr <= header.e_entry < segment.p_vaddr + segment.p_filesz:
                entry_region = segment
                break
        if entry_region is None:
            raise ElfIngestError(
                "ENTRY_OUTSIDE_EXECUTABLE",
                f"entry=0x{header.e_entry:08x} executable_filesz_regions="
                f"{[(hex(item.p_vaddr), item.p_filesz) for item in parsed.executable_regions()]}")
        if not (text.sh_addr <= header.e_entry < text.sh_addr + text.sh_size):
            raise ElfIngestError(
                "ENTRY_OUTSIDE_EXECUTABLE",
                f"entry=0x{header.e_entry:08x} text=0x{text.sh_addr:x}+{text.sh_size}")

        return {
            "target": self.name,
            "machine": header.e_machine,
            "machine_name": self.expected_machine_name,
            "type": header.e_type,
            "type_name": header.type_name,
            "abi": "O32",
            "isa": "MIPS32 (EF_MIPS_ARCH_32)",
            "pic": False,
            "endianness": parsed.identification.endianness,
            "elf_class": parsed.identification.class_name,
            "flags": f"0x{header.e_flags:08x}",
            "flags_interpretation": (
                "EF_MIPS_ABI_O32 | EF_MIPS_ARCH_32 | EF_MIPS_NOREORDER (non-PIC)"),
            "entry": f"0x{header.e_entry:08x}",
            "entry_region": entry_region.index,
            "entry_section": text.name,
            "executable_section": text.name,
            "required_sections": list(REQUIRED_SECTIONS),
            "static": True,
            "dynamic": False,
            "relocations": False,
        }


MIPS32_O32 = Mips32O32Policy()


def policy() -> Mips32O32Policy:
    return MIPS32_O32
