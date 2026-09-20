#!/usr/bin/env python3
"""OpenRecomp Phase-9 PS1 executable image and memory-map contract V1.

The contract is built from one validated PS-X EXE image
(:mod:`p9_psx_exe_v1`) and defines an explicit, bounded PS1 guest
address-space model:

* the 2 MiB main-RAM window, cached through KSEG0 (``0x80000000``) and
  uncached through KSEG1 (``0xA0000000``);
* named loaded regions (text, optional BSS, bounded stack) with explicit
  read/write/execute permissions;
* explicit classifications for every other segment the bounded analysis may
  encounter (KUSEG RAM mirror, scratchpad, I/O ports, BIOS, KSEG2), each
  either disabled with a reason or routed to the platform-service boundary;
* a deterministic flat RAM image with the payload mapped at its load address.

There is no silent address masking and no invented mapping: every translation
is an explicit decision and every unsupported access fails closed with a
stable code.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import p9_psx_exe_v1 as psx

CONTRACT_VERSION = "1.0.0"

RAM_KSEG0_BASE = psx.PSX_RAM_KSEG0_BASE
RAM_SIZE = psx.PSX_RAM_SIZE
RAM_KSEG0_END = psx.PSX_RAM_KSEG0_END
RAM_KSEG1_BASE = 0xA0000000
RAM_KSEG1_END = RAM_KSEG1_BASE + RAM_SIZE
RAM_KUSEG_BASE = 0x00000000
RAM_KUSEG_END = RAM_SIZE

SCRATCHPAD_BASE = 0x1F800000
SCRATCHPAD_SIZE = 0x400
IO_BASE = 0x1F801000
IO_SIZE = 0x2000
BIOS_BASE = 0xBFC00000
BIOS_SIZE = 0x80000
KSEG2_BASE = 0xC0000000
KSEG2_END = 0x100000000

#: Explicit bounded stack window below the PS-X EXE initial stack pointer.
STACK_SIZE = 0x4000

PERMISSION_FLAGS = {"r": 1, "w": 2, "x": 4}

TRANSLATION_CODES = (
    "UNSUPPORTED_SEGMENT_KUSEG",
    "UNSUPPORTED_SEGMENT_SCRATCHPAD",
    "UNSUPPORTED_SEGMENT_BIOS",
    "UNSUPPORTED_SEGMENT_KSEG2",
    "PLATFORM_SERVICE_UNCLAIMED",
    "UNMAPPED_ADDRESS",
    "STACK_OVERLAPS_IMAGE",
    "IMAGE_CHUNK_LIMIT",
)

IMAGE_CHUNK_LIMIT = 4096


class MemoryMapError(ValueError):
    """Fail-closed memory-map rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        if code not in TRANSLATION_CODES:
            raise AssertionError(f"unknown memory-map error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Region:
    name: str
    base: int
    size: int
    permissions: str
    kind: str

    def flags(self) -> int:
        return sum(PERMISSION_FLAGS[char] for char in self.permissions if char in PERMISSION_FLAGS)

    def contains(self, address: int, width_bytes: int = 1) -> bool:
        return self.base <= address and address + width_bytes <= self.base + self.size

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "base": f"0x{self.base:08x}",
            "end": f"0x{self.base + self.size:08x}",
            "size": self.size,
            "permissions": self.permissions,
            "flags": self.flags(),
            "kind": self.kind,
        }


@dataclass(frozen=True)
class Translation:
    segment: str
    kind: str
    offset: int
    address: int


def flat_image(image: psx.PsxExeImage) -> bytes:
    """The deterministic 2 MiB flat RAM image for one PS-X EXE."""
    data = bytearray(RAM_SIZE)
    offset = image.header.t_addr - RAM_KSEG0_BASE
    data[offset : offset + len(image.payload)] = image.payload
    return bytes(data)


def nonzero_chunks(
    image: bytes, limit: int = IMAGE_CHUNK_LIMIT, gap_merge: int = 16
) -> tuple[tuple[int, bytes], ...]:
    """Deterministic non-zero chunks of a flat image.

    Contiguous non-zero runs separated by fewer than ``gap_merge`` zero bytes
    are merged, so the chunk count is a stable property of the image rather
    than of every zero byte run.
    """
    spans: list[tuple[int, int]] = []
    start = None
    for index, value in enumerate(image):
        if value and start is None:
            start = index
        elif not value and start is not None:
            spans.append((start, index))
            start = None
    if start is not None:
        spans.append((start, len(image)))
    merged: list[tuple[int, int]] = []
    for span_start, span_end in spans:
        if merged and span_start - merged[-1][1] < gap_merge:
            merged[-1] = (merged[-1][0], span_end)
        else:
            merged.append((span_start, span_end))
    if len(merged) > limit:
        raise MemoryMapError("IMAGE_CHUNK_LIMIT", f"{len(merged)} > {limit}")
    return tuple((span_start, image[span_start:span_end]) for span_start, span_end in merged)


def build_contract(image: psx.PsxExeImage) -> dict[str, Any]:
    """Build the explicit bounded address-space contract for one image."""
    header = image.header
    text = Region(
        name="load_text",
        base=header.t_addr,
        size=header.t_size,
        permissions="rwx",
        kind="image",
    )
    regions = [text]
    if header.b_size:
        regions.append(
            Region(
                name="bss",
                base=header.b_addr,
                size=header.b_size,
                permissions="rw",
                kind="bss",
            )
        )
    stack_base = header.s_addr - STACK_SIZE
    if stack_base < RAM_KSEG0_BASE:
        raise MemoryMapError("STACK_OVERLAPS_IMAGE", f"stack_base=0x{stack_base:08x}")
    stack = Region(
        name="stack",
        base=stack_base,
        size=STACK_SIZE,
        permissions="rw",
        kind="stack",
    )
    for region in regions:
        if stack.base < region.base + region.size and region.base < stack.base + stack.size:
            raise MemoryMapError(
                "STACK_OVERLAPS_IMAGE",
                f"stack=0x{stack.base:08x}+{stack.size} overlaps {region.name}=0x{region.base:08x}+{region.size}",
            )
    regions.append(stack)

    image_end = max(header.t_addr + header.t_size, header.b_addr + header.b_size if header.b_size else 0)
    if stack.base > image_end:
        regions.append(
            Region(
                name="ram_free",
                base=image_end,
                size=stack.base - image_end,
                permissions="rw",
                kind="ram-free",
            )
        )
    regions.sort(key=lambda region: region.base)

    flat = flat_image(image)
    contract = {
        "contract_version": CONTRACT_VERSION,
        "endianness": "little",
        "entry": f"0x{header.pc0:08x}",
        "initial_gp": f"0x{header.gp0:08x}",
        "load_address": f"0x{header.t_addr:08x}",
        "text_end": f"0x{image.text_end:08x}",
        "ram": {
            "base": f"0x{RAM_KSEG0_BASE:08x}",
            "size": RAM_SIZE,
            "end": f"0x{RAM_KSEG0_END:08x}",
            "permissions": "rwx",
            "image_sha256": hashlib.sha256(flat).hexdigest(),
            "image_size": len(flat),
        },
        "segments": [
            {
                "name": "kseg0",
                "base": f"0x{RAM_KSEG0_BASE:08x}",
                "size": RAM_SIZE,
                "classification": "ram-cached",
                "translation": "ram",
                "enabled": True,
            },
            {
                "name": "kseg1",
                "base": f"0x{RAM_KSEG1_BASE:08x}",
                "size": RAM_SIZE,
                "classification": "ram-uncached",
                "translation": "ram",
                "enabled": True,
            },
            {
                "name": "kuseg",
                "base": f"0x{RAM_KUSEG_BASE:08x}",
                "size": RAM_SIZE,
                "classification": "ram-user-mirror",
                "translation": "ram",
                "enabled": False,
                "reason": "bounded V1 runs in KSEG0; user-mirror accesses fail closed",
            },
            {
                "name": "scratchpad",
                "base": f"0x{SCRATCHPAD_BASE:08x}",
                "size": SCRATCHPAD_SIZE,
                "classification": "unsupported-not-modelled",
                "translation": "none",
                "enabled": False,
                "reason": "1 KiB scratchpad is not required by the bounded fixture",
            },
            {
                "name": "io",
                "base": f"0x{IO_BASE:08x}",
                "size": IO_SIZE,
                "classification": "platform-service",
                "translation": "service",
                "enabled": False,
                "reason": "mapped by the typed PS1 platform-service boundary, not by RAM",
            },
            {
                "name": "bios",
                "base": f"0x{BIOS_BASE:08x}",
                "size": BIOS_SIZE,
                "classification": "absent-no-bios-image",
                "translation": "none",
                "enabled": False,
                "reason": "no BIOS image is loaded, executed or emulated",
            },
            {
                "name": "kseg2",
                "base": f"0x{KSEG2_BASE:08x}",
                "size": KSEG2_END - KSEG2_BASE,
                "classification": "unsupported-privileged",
                "translation": "none",
                "enabled": False,
                "reason": "kernel-only segment is outside the bounded contract",
            },
        ],
        "regions": [region.as_dict() for region in regions],
        "stack": {
            "pointer": f"0x{header.s_addr:08x}",
            "base": f"0x{stack.base:08x}",
            "size": stack.size,
            "model": "explicit-bounded",
            "reason": "PS-X EXE s_size is zero; the contract uses an explicit bounded window below the initial SP",
        },
        "bss": {
            "present": header.b_size > 0,
            "address": f"0x{header.b_addr:08x}",
            "size": header.b_size,
        },
        "chunks": len(nonzero_chunks(flat)),
    }
    return contract


def translate(contract: dict[str, Any], address: int) -> Translation:
    """Translate one guest address explicitly (fail closed)."""
    if RAM_KSEG0_BASE <= address < RAM_KSEG0_END:
        return Translation("kseg0", "ram", address - RAM_KSEG0_BASE, address)
    if RAM_KSEG1_BASE <= address < RAM_KSEG1_END:
        return Translation("kseg1", "ram", address - RAM_KSEG1_BASE, address)
    if RAM_KUSEG_BASE <= address < RAM_KUSEG_END:
        raise MemoryMapError("UNSUPPORTED_SEGMENT_KUSEG", f"0x{address:08x}")
    if SCRATCHPAD_BASE <= address < SCRATCHPAD_BASE + SCRATCHPAD_SIZE:
        raise MemoryMapError("UNSUPPORTED_SEGMENT_SCRATCHPAD", f"0x{address:08x}")
    if IO_BASE <= address < IO_BASE + IO_SIZE:
        raise MemoryMapError("PLATFORM_SERVICE_UNCLAIMED", f"0x{address:08x}")
    if BIOS_BASE <= address < BIOS_BASE + BIOS_SIZE:
        raise MemoryMapError("UNSUPPORTED_SEGMENT_BIOS", f"0x{address:08x}")
    if KSEG2_BASE <= address < KSEG2_END:
        raise MemoryMapError("UNSUPPORTED_SEGMENT_KSEG2", f"0x{address:08x}")
    raise MemoryMapError("UNMAPPED_ADDRESS", f"0x{address:08x}")


def region_for(contract: dict[str, Any], address: int, width_bytes: int = 1) -> dict[str, Any] | None:
    for region in contract["regions"]:
        base = int(region["base"], 16)
        if base <= address and address + width_bytes <= base + region["size"]:
            return region
    return None


def read_u32(contract: dict[str, Any], flat: bytes, address: int) -> int:
    """Read one little-endian word through the explicit address translation."""
    translation = translate(contract, address)
    if translation.kind != "ram":
        raise MemoryMapError("UNMAPPED_ADDRESS", f"0x{address:08x} kind={translation.kind}")
    if translation.offset + 4 > len(flat):
        raise MemoryMapError("UNMAPPED_ADDRESS", f"0x{address:08x}")
    return int.from_bytes(flat[translation.offset : translation.offset + 4], "little")


def contract_digest(contract: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(contract, sort_keys=True).encode("utf-8")).hexdigest()
