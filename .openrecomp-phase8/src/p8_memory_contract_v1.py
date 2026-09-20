#!/usr/bin/env python3
"""OpenRecomp Phase-8 static memory and runtime contract for the real ELF.

The contract reuses the existing Phase-3 guest-image ingestion (sparse regions,
zero-fill, section roles) and the existing generic runtime ABI (P2-08) surface,
and adds only the bounded host-side memory/runtime contract the frozen fixture
requires:

* a flat guest image window derived from the ingested `PT_LOAD` regions;
* an explicit region table with read/write/execute permissions;
* a write-only byte output window at ``0x10000000`` mapped to the
  ``p8_uart_write`` host service;
* termination by returning to the host boundary (address 0), with the guest
  status value in ``$v0``.

The module renders the deterministic generated image translation unit used by
the native runtime support, and provides an independently written Python memory
model used to differentially verify the native support implementation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from openrecomp import runtime_abi as rt_abi

CONTRACT_VERSION = "1.0.0"

OUTPUT_ADDRESS = 0x10000000
OUTPUT_WIDTH_BITS = 8
OUTPUT_SERVICE = "p8_uart_write"
SUPPORTED_WIDTHS = (8, 16, 32)

RT_OK = 0
RT_OUT_OF_RANGE = 1
RT_WIDTH_UNSUPPORTED = 2
RT_UNKNOWN_HOST_SERVICE = 6
RT_UNSUPPORTED_OPERATION = 13

PERMISSION_FLAGS = {"r": 1, "w": 2, "x": 4}


@dataclass(frozen=True)
class Region:
    name: str
    base: int
    size: int
    permissions: str
    kind: str

    def flags(self) -> int:
        return sum(PERMISSION_FLAGS[char] for char in self.permissions if char in PERMISSION_FLAGS)

    def contains(self, address: int, width_bytes: int) -> bool:
        return self.base <= address and address + width_bytes <= self.base + self.size


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def flat_image(ingested: Any) -> bytes:
    """The exact flat guest image: file-backed region bytes plus zero fill."""
    size = 0
    for region in ingested.image.regions:
        size = max(size, region.vaddr + region.memsz)
    image = bytearray(size)
    for region in ingested.image.regions:
        content = region.initial_bytes
        image[region.vaddr : region.vaddr + len(content)] = content
    return bytes(image)


def build_contract(ingested: Any) -> dict[str, Any]:
    image = flat_image(ingested)
    regions = []
    for region in sorted(ingested.image.regions, key=lambda item: item.vaddr):
        regions.append(
            Region(
                name=f"load_{region.index}",
                base=region.vaddr,
                size=region.memsz,
                permissions=region.permissions,
                kind=region.kind,
            )
        )
    sections = []
    for placement in sorted(ingested.image.placements, key=lambda item: item.vaddr):
        sections.append(
            Region(
                name=placement.name,
                base=placement.vaddr,
                size=placement.size,
                permissions=placement.permissions,
                kind=placement.kind,
            )
        )
    symbols = {}
    for symbol in ingested.parsed.symbols():
        if symbol.name:
            symbols[symbol.name] = {"value": symbol.value, "size": symbol.size}
    stack_symbol = symbols.get("p8_stack")
    if stack_symbol is None:
        raise ValueError("contract requires the p8_stack symbol")
    stack = {
        "symbol": "p8_stack",
        "base": stack_symbol["value"],
        "size": stack_symbol["size"],
        "top": stack_symbol["value"] + stack_symbol["size"],
    }
    return {
        "contract_version": CONTRACT_VERSION,
        "endianness": ingested.identity["endianness"],
        "entry": ingested.identity["entry"],
        "image_size": len(image),
        "image_sha256": sha256_bytes(image),
        "regions": [
            {
                "name": region.name,
                "base": region.base,
                "size": region.size,
                "permissions": region.permissions,
                "flags": region.flags(),
                "kind": region.kind,
            }
            for region in regions
        ],
        "sections": [
            {
                "name": section.name,
                "base": section.base,
                "size": section.size,
                "permissions": section.permissions,
                "kind": section.kind,
                "sha256": sha256_bytes(ingested.image.section_bytes(section.name)),
            }
            for section in sections
        ],
        "stack": stack,
        "output_window": {
            "address": OUTPUT_ADDRESS,
            "width_bits": OUTPUT_WIDTH_BITS,
            "access": "write-only",
            "service": OUTPUT_SERVICE,
        },
        "termination": {"kind": "guest-return-to-host", "sentinel": 0, "status_register": 2},
        "host_services": [{"id": OUTPUT_SERVICE, "arg_count": 1}],
        "kernel_emulation": "not-required",
        "static": ingested.identity["static"],
        "dynamic": ingested.identity["dynamic"],
        "relocations": ingested.identity["relocations"],
    }


def region_for(contract: dict[str, Any], address: int, width_bytes: int) -> dict[str, Any] | None:
    for region in contract["regions"]:
        if region["base"] <= address and address + width_bytes <= region["base"] + region["size"]:
            return region
    return None


# --- independent Python memory model -----------------------------------------
class PythonMemoryModel:
    """Independently written model of the bounded runtime memory contract."""

    def __init__(self, contract: dict[str, Any], image: bytes) -> None:
        self.contract = contract
        self._runtime = rt_abi.RuntimeMemory(len(image))
        self._runtime.write_bytes(0, image)
        self._permissions = {
            (region["base"], region["size"]): region["permissions"] for region in contract["regions"]
        }
        self.transcript: list[int] = []

    def read(self, address: int, width_bits: int) -> tuple[int, int]:
        if width_bits not in SUPPORTED_WIDTHS:
            return RT_WIDTH_UNSUPPORTED, 0
        width_bytes = width_bits // 8
        if address == OUTPUT_ADDRESS:
            return RT_OUT_OF_RANGE, 0
        if address + width_bytes > len(self._runtime.snapshot()):
            return RT_OUT_OF_RANGE, 0
        value = int.from_bytes(self._runtime.snapshot()[address : address + width_bytes], "little")
        return RT_OK, value

    def write(self, address: int, width_bits: int, value: int) -> int:
        if width_bits not in SUPPORTED_WIDTHS:
            return RT_WIDTH_UNSUPPORTED
        width_bytes = width_bits // 8
        if address == OUTPUT_ADDRESS:
            if width_bits != OUTPUT_WIDTH_BITS:
                return RT_WIDTH_UNSUPPORTED
            self.transcript.append(value & 0xFF)
            return RT_OK
        if address + width_bytes > len(self._runtime.snapshot()):
            return RT_OUT_OF_RANGE
        permissions = None
        for (base, size), perms in self._permissions.items():
            if base <= address and address + width_bytes <= base + size:
                permissions = perms
                break
        if permissions is None or "w" not in permissions:
            return RT_UNSUPPORTED_OPERATION
        data = bytearray(self._runtime.snapshot())
        data[address : address + width_bytes] = (value & ((1 << width_bits) - 1)).to_bytes(width_bytes, "little")
        self._runtime = rt_abi.RuntimeMemory(len(data))
        self._runtime.write_bytes(0, bytes(data))
        return RT_OK

    def image(self) -> bytes:
        return self._runtime.snapshot()


# --- deterministic generated image translation unit --------------------------
def render_image_header(contract: dict[str, Any]) -> str:
    lines = [
        "/* OpenRecomp Phase 8 generated guest image contract (do not edit). */",
        "#ifndef OPENRECOMP_P8_IMAGE_V1_H",
        "#define OPENRECOMP_P8_IMAGE_V1_H",
        "",
        "#include <stddef.h>",
        "#include <stdint.h>",
        "",
        f"#define P8_IMAGE_SIZE {contract['image_size']}u",
        f'#define P8_IMAGE_SHA256 "{contract["image_sha256"]}"',
        f"#define P8_OUTPUT_ADDR UINT64_C({OUTPUT_ADDRESS})",
        f"#define P8_OUTPUT_WIDTH_BITS {OUTPUT_WIDTH_BITS}u",
        f"#define P8_STACK_BASE UINT64_C({contract['stack']['base']})",
        f"#define P8_STACK_SIZE {contract['stack']['size']}u",
        "",
        "enum { P8_REGION_READABLE = 1u, P8_REGION_WRITABLE = 2u, P8_REGION_EXECUTABLE = 4u };",
        "",
        "struct p8_region {",
        "    uint32_t base;",
        "    uint32_t size;",
        "    unsigned flags;",
        "    const char *name;",
        "};",
        "",
        "extern const unsigned char p8_image[P8_IMAGE_SIZE];",
        "extern const struct p8_region p8_regions[];",
        f"extern const unsigned p8_region_count;",
        "",
        "#endif",
        "",
    ]
    return "\n".join(lines)


def render_image_source(contract: dict[str, Any], image: bytes) -> str:
    lines = [
        "/* OpenRecomp Phase 8 generated guest image (do not edit). */",
        "/* Compiled after the generated contract header text in the same unit. */",
        "",
        "const unsigned char p8_image[P8_IMAGE_SIZE] = {",
    ]
    for offset in range(0, len(image), 16):
        chunk = image[offset : offset + 16]
        lines.append("    " + " ".join(f"0x{byte:02x}," for byte in chunk))
    lines.append("};")
    lines.append("")
    lines.append("const struct p8_region p8_regions[] = {")
    for region in contract["regions"]:
        lines.append(
            f'    {{ UINT32_C({region["base"]}), UINT32_C({region["size"]}), {region["flags"]}u, "{region["name"]}" }},'
        )
    lines.append("};")
    lines.append("")
    lines.append("const unsigned p8_region_count = sizeof(p8_regions) / sizeof(p8_regions[0]);")
    lines.append("")
    return "\n".join(lines)


def contract_digest(contract: dict[str, Any]) -> str:
    return sha256_bytes(json.dumps(contract, sort_keys=True).encode("utf-8"))


def compose_runtime_sources(
    contract: dict[str, Any], image: bytes, support_text: str
) -> tuple[tuple[str, str], tuple[str, str]]:
    """Return the two deterministic runtime translation units for a build.

    The build boundary only accepts flat source files, so the generated
    contract declarations are prepended to both the image unit and the
    OpenRecomp-authored runtime support body.
    """
    header = render_image_header(contract)
    image_unit = header + "\n" + render_image_source(contract, image)
    support_unit = header + "\n" + support_text
    return ("p8_image_v1.c", image_unit), ("p8_runtime_support.c", support_unit)
