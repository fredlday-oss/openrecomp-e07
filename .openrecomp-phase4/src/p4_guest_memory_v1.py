#!/usr/bin/env python3
"""OpenRecomp Phase-4 guest memory / runtime model V1 (P4-02).

An explicit, architecture-neutral guest memory model for the generated-code
<-> runtime boundary defined by P4-01:

* named regions with a declared kind (``code``, ``rodata``, ``data``,
  ``bss``, ``stack``, ``heap``) and explicit read/write/execute permissions;
* non-overlapping regions with validated bounds, no address-space wrap and no
  writable+executable region (W^X);
* byte-addressed access with widths 8/16/32/64 and explicit little/big
  endianness; unaligned multi-byte access is byte-addressed by default and can
  be restricted to natural alignment per model policy;
* deterministic fail-closed faults: unmapped, permission, alignment, width,
  endianness and address overflow, each mapped to a P2-08 ABI failure code at
  the generated-code boundary;
* deterministic state: a canonical region document and a sha256 fingerprint.

The model core contains no fixture- or platform-specific names.  The frozen
Phase-3 image is provided as a declared instance adapter with pinned identities
(the P3-07 emitted ``g_image`` window and the emitted region table).  Nothing
here is used by, or changes, the frozen Phase-1/Phase-2/Phase-3 emitters or
evidence.
"""
from __future__ import annotations

import hashlib
import pathlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

ROOT = pathlib.Path(__file__).resolve().parents[2]

from openrecomp import runtime_abi as rt
from openrecomp.program_model import canonical_json

ADDRESS_SPACE_BITS = 64
ADDRESS_SPACE_SIZE = 1 << ADDRESS_SPACE_BITS
MAX_ADDRESS = ADDRESS_SPACE_SIZE - 1
WIDTHS = tuple(sorted(rt.RUNTIME_WIDTHS))
ENDIANNESS = tuple(sorted(rt.RUNTIME_ENDIANNESS))
ALIGNMENT_POLICIES = ("allow", "require-natural")

FROZEN_PROGRAM_PATH = ".openrecomp-phase3/evidence/P3-07/coremark_program.c"
FROZEN_PROGRAM_SHA256 = (
    "5199e2f0a11974847966bd7ea6b855e0147c6e762d002ede3f14bc3ee8d9649a")
FROZEN_IMAGE_SHA256 = (
    "3eecfc957c4ed147544d2aa98c6e4f4d7aac41957e531cdfe01c2555ff0a91ae")
FROZEN_IMAGE_WINDOW = 65536
FROZEN_ENTRY = 0x4650
FROZEN_REGION_COUNT = 4
FROZEN_REGION_READABLE = 1
FROZEN_REGION_WRITABLE = 2

_IMAGE_WINDOW_RE = re.compile(r"OR_IMAGE_WINDOW\s+(\d+)u")
_G_IMAGE_RE = re.compile(
    r"static\s+const\s+uint8_t\s+g_image\s*\[\s*OR_IMAGE_WINDOW\s*\]\s*=\s*\{(.*?)\}\s*;",
    re.DOTALL)
_BYTE_RE = re.compile(r"0x([0-9a-fA-F]{2})")
_G_REGIONS_RE = re.compile(
    r"g_or_regions\s*\[\s*OR_REGION_COUNT\s*\]\s*\[\s*3\s*\]\s*=\s*\{(.*?)\}\s*;",
    re.DOTALL)
_G_REGION_ROW_RE = re.compile(
    r"\{\s*(0x[0-9a-fA-F]+)u\s*,\s*(0x[0-9a-fA-F]+)u\s*,\s*([^}]+?)\s*\}")


class GuestMemoryError(ValueError):
    """Raised for an invalid model or a fail-closed guest access fault."""

    def __init__(self, message: str, *, fault: "GuestFault | None" = None) -> None:
        super().__init__(message)
        self.fault = fault


class FaultKind(str, Enum):
    UNMAPPED = "UNMAPPED"
    PERMISSION = "PERMISSION"
    ALIGNMENT = "ALIGNMENT"
    WIDTH = "WIDTH"
    ENDIANNESS = "ENDIANNESS"
    OVERFLOW = "OVERFLOW"


ABI_FAILURE_BY_FAULT = {
    FaultKind.UNMAPPED: "MEMORY_OUT_OF_RANGE",
    FaultKind.PERMISSION: "MEMORY_OUT_OF_RANGE",
    FaultKind.ALIGNMENT: "MEMORY_OUT_OF_RANGE",
    FaultKind.WIDTH: "MEMORY_WIDTH_UNSUPPORTED",
    FaultKind.ENDIANNESS: "MEMORY_ENDIANNESS_UNSUPPORTED",
    FaultKind.OVERFLOW: "MEMORY_ADDRESS_OVERFLOW",
}


class RegionKind(str, Enum):
    CODE = "code"
    RODATA = "rodata"
    DATA = "data"
    BSS = "bss"
    STACK = "stack"
    HEAP = "heap"


_KIND_DEFAULTS: dict[RegionKind, dict[str, bool]] = {
    RegionKind.CODE: {"readable": True, "writable": False, "executable": True},
    RegionKind.RODATA: {"readable": True, "writable": False, "executable": False},
    RegionKind.DATA: {"readable": True, "writable": True, "executable": False},
    RegionKind.BSS: {"readable": True, "writable": True, "executable": False},
    RegionKind.STACK: {"readable": True, "writable": True, "executable": False},
    RegionKind.HEAP: {"readable": True, "writable": True, "executable": False},
}
_NO_FILE_DATA_KINDS = (RegionKind.BSS, RegionKind.STACK, RegionKind.HEAP)


def _require_uint(value: Any, where: str, *, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GuestMemoryError(f"{where} must be a non-negative integer, got {value!r}")
    if maximum is not None and value > maximum:
        raise GuestMemoryError(f"{where} exceeds {maximum}, got {value!r}")
    return value


@dataclass(frozen=True)
class GuestFault:
    kind: FaultKind
    address: int
    width_bits: int | None
    region: str | None
    detail: str

    @property
    def abi_failure(self) -> str:
        return ABI_FAILURE_BY_FAULT[self.kind]

    def to_document(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "address": self.address,
            "width_bits": self.width_bits,
            "region": self.region,
            "abi_failure": self.abi_failure,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class GuestAccess:
    ok: bool
    value: int | None = None
    fault: GuestFault | None = None

    def require(self) -> int | None:
        if not self.ok:
            raise GuestMemoryError(self.fault.detail, fault=self.fault)
        return self.value


@dataclass(frozen=True)
class GuestRegion:
    name: str
    start: int
    size: int
    kind: RegionKind
    readable: bool
    writable: bool
    executable: bool
    file_data: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise GuestMemoryError("region name must be a non-empty string")
        _require_uint(self.start, f"region {self.name}.start", maximum=MAX_ADDRESS)
        _require_uint(self.size, f"region {self.name}.size")
        if self.size == 0:
            raise GuestMemoryError(f"region {self.name}.size must be positive")
        if self.start + self.size > ADDRESS_SPACE_SIZE:
            raise GuestMemoryError(f"region {self.name} wraps the address space")
        if not isinstance(self.kind, RegionKind):
            raise GuestMemoryError(f"region {self.name}.kind must be a RegionKind")
        for field_name in ("readable", "writable", "executable"):
            if not isinstance(getattr(self, field_name), bool):
                raise GuestMemoryError(f"region {self.name}.{field_name} must be a bool")
        if self.writable and self.executable:
            raise GuestMemoryError(f"region {self.name} must not be writable and executable")
        if self.kind is RegionKind.CODE and not self.executable:
            raise GuestMemoryError(f"code region {self.name} must be executable")
        if not isinstance(self.file_data, (bytes, bytearray)):
            raise GuestMemoryError(f"region {self.name}.file_data must be bytes")
        if len(self.file_data) > self.size:
            raise GuestMemoryError(f"region {self.name}.file_data exceeds the region size")
        if self.kind in _NO_FILE_DATA_KINDS and len(self.file_data) != 0:
            raise GuestMemoryError(f"{self.kind.value} region {self.name} must not carry file data")

    @property
    def end(self) -> int:
        return self.start + self.size

    def contains(self, address: int, length: int = 1) -> bool:
        return self.start <= address and address + length <= self.end

    def permissions_document(self) -> dict[str, bool]:
        return {
            "readable": self.readable,
            "writable": self.writable,
            "executable": self.executable,
        }

    def to_document(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start": self.start,
            "size": self.size,
            "end": self.end,
            "kind": self.kind.value,
            "permissions": self.permissions_document(),
            "file_bytes": len(self.file_data),
            "file_sha256": hashlib.sha256(self.file_data).hexdigest(),
        }


def region(
    name: str,
    start: int,
    size: int,
    kind: RegionKind,
    *,
    readable: bool | None = None,
    writable: bool | None = None,
    executable: bool | None = None,
    file_data: bytes = b"",
) -> GuestRegion:
    defaults = _KIND_DEFAULTS[kind]
    return GuestRegion(
        name=name,
        start=start,
        size=size,
        kind=kind,
        readable=defaults["readable"] if readable is None else readable,
        writable=defaults["writable"] if writable is None else writable,
        executable=defaults["executable"] if executable is None else executable,
        file_data=bytes(file_data),
    )


class GuestMemoryModel:
    """A bounded guest address space split into explicit permissioned regions."""

    def __init__(
        self,
        regions: Iterable[GuestRegion],
        *,
        endianness: str = "little",
        alignment: str = "allow",
    ) -> None:
        if endianness not in ENDIANNESS:
            raise GuestMemoryError(f"unsupported endianness {endianness!r}")
        if alignment not in ALIGNMENT_POLICIES:
            raise GuestMemoryError(f"unsupported alignment policy {alignment!r}")
        ordered = sorted(regions, key=lambda item: item.start)
        if not ordered:
            raise GuestMemoryError("the guest memory model needs at least one region")
        names: set[str] = set()
        previous_end = 0
        storage: list[bytearray] = []
        for item in ordered:
            if not isinstance(item, GuestRegion):
                raise GuestMemoryError("regions must be GuestRegion instances")
            if item.name in names:
                raise GuestMemoryError(f"duplicate region name {item.name!r}")
            names.add(item.name)
            if item.start < previous_end:
                raise GuestMemoryError(
                    f"regions overlap at 0x{item.start:x} ({item.name!r})")
            previous_end = item.end
            data = bytearray(item.size)
            data[0:len(item.file_data)] = item.file_data
            storage.append(data)
        self._regions = tuple(ordered)
        self._storage = tuple(storage)
        self._endianness = endianness
        self._alignment = alignment

    @property
    def regions(self) -> tuple[GuestRegion, ...]:
        return self._regions

    @property
    def endianness(self) -> str:
        return self._endianness

    @property
    def alignment(self) -> str:
        return self._alignment

    def region_at(self, address: int) -> GuestRegion | None:
        if isinstance(address, bool) or not isinstance(address, int):
            return None
        for item in self._regions:
            if item.contains(address):
                return item
        return None

    def _fault(self, kind: FaultKind, address: int, width_bits: int | None,
               region_name: str | None, detail: str) -> GuestMemoryError:
        return GuestMemoryError(
            detail,
            fault=GuestFault(kind=kind, address=address, width_bits=width_bits,
                             region=region_name, detail=detail))

    def _check(self, address: int, width_bits: int,
               endianness: str | None) -> tuple[GuestRegion, bytearray, str]:
        if isinstance(width_bits, bool) or not isinstance(width_bits, int) or width_bits not in WIDTHS:
            raise self._fault(FaultKind.WIDTH, address if isinstance(address, int) else 0,
                              width_bits, None, f"unsupported access width {width_bits!r}")
        order = self._endianness if endianness is None else endianness
        if order not in ENDIANNESS:
            raise self._fault(FaultKind.ENDIANNESS, address if isinstance(address, int) else 0,
                              width_bits, None, f"unsupported endianness {order!r}")
        if isinstance(address, bool) or not isinstance(address, int) or address < 0:
            raise self._fault(FaultKind.UNMAPPED, 0, width_bits, None,
                              f"address {address!r} is not a non-negative integer")
        if address > MAX_ADDRESS:
            raise self._fault(FaultKind.OVERFLOW, address, width_bits, None,
                              f"address 0x{address:x} exceeds the address space")
        length = width_bits // 8
        if address > MAX_ADDRESS - length + 1:
            raise self._fault(FaultKind.OVERFLOW, address, width_bits, None,
                              f"address 0x{address:x} + {length} wraps the address space")
        if self._alignment == "require-natural" and length > 1 and address % length != 0:
            raise self._fault(FaultKind.ALIGNMENT, address, width_bits, None,
                              f"address 0x{address:x} is not naturally aligned for {width_bits} bits")
        for item, data in zip(self._regions, self._storage):
            if item.contains(address):
                if not item.contains(address, length):
                    raise self._fault(
                        FaultKind.UNMAPPED, address, width_bits, item.name,
                        f"access of {length} byte(s) at 0x{address:x} leaves region {item.name!r}")
                return item, data, order
        raise self._fault(FaultKind.UNMAPPED, address, width_bits, None,
                          f"address 0x{address:x} is not mapped")

    def try_read(self, address: int, width_bits: int, *,
                 endianness: str | None = None) -> GuestAccess:
        try:
            return GuestAccess(ok=True, value=self.read(address, width_bits,
                                                        endianness=endianness))
        except GuestMemoryError as exc:
            return GuestAccess(ok=False, fault=exc.fault)

    def read(self, address: int, width_bits: int, *,
             endianness: str | None = None) -> int:
        item, data, order = self._check(address, width_bits, endianness)
        if not item.readable:
            raise self._fault(FaultKind.PERMISSION, address, width_bits, item.name,
                              f"region {item.name!r} is not readable")
        length = width_bits // 8
        offset = address - item.start
        return int.from_bytes(data[offset:offset + length], order)

    def write(self, address: int, value: int, width_bits: int, *,
              endianness: str | None = None) -> None:
        item, data, order = self._check(address, width_bits, endianness)
        if not item.writable:
            raise self._fault(FaultKind.PERMISSION, address, width_bits, item.name,
                              f"region {item.name!r} is not writable")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise self._fault(FaultKind.UNMAPPED, address, width_bits, item.name,
                              f"write value {value!r} is not a non-negative integer")
        length = width_bits // 8
        offset = address - item.start
        masked = value & ((1 << width_bits) - 1)
        data[offset:offset + length] = masked.to_bytes(length, order)

    def try_write(self, address: int, value: int, width_bits: int, *,
                  endianness: str | None = None) -> GuestAccess:
        try:
            self.write(address, value, width_bits, endianness=endianness)
            return GuestAccess(ok=True)
        except GuestMemoryError as exc:
            return GuestAccess(ok=False, fault=exc.fault)

    def fetch(self, address: int, width_bits: int = 32) -> int:
        item, data, order = self._check(address, width_bits, None)
        if not item.executable:
            raise self._fault(FaultKind.PERMISSION, address, width_bits, item.name,
                              f"region {item.name!r} is not executable")
        length = width_bits // 8
        offset = address - item.start
        return int.from_bytes(data[offset:offset + length], order)

    def read_bytes(self, address: int, length: int) -> bytes:
        _require_uint(length, "read_bytes.length")
        if length == 0:
            return b""
        item, data, _ = self._check(address, 8, None)
        if not item.readable:
            raise self._fault(FaultKind.PERMISSION, address, 8, item.name,
                              f"region {item.name!r} is not readable")
        if not item.contains(address, length):
            raise self._fault(FaultKind.UNMAPPED, address, length * 8, item.name,
                              f"{length} byte(s) at 0x{address:x} are not wholly mapped")
        offset = address - item.start
        return bytes(data[offset:offset + length])

    def write_bytes(self, address: int, payload: bytes) -> None:
        if not isinstance(payload, (bytes, bytearray)):
            raise GuestMemoryError("write_bytes requires bytes")
        if not payload:
            return
        item, data, _ = self._check(address, 8, None)
        if not item.writable:
            raise self._fault(FaultKind.PERMISSION, address, 8, item.name,
                              f"region {item.name!r} is not writable")
        if not item.contains(address, len(payload)):
            raise self._fault(FaultKind.UNMAPPED, address, len(payload) * 8, item.name,
                              f"{len(payload)} byte(s) at 0x{address:x} are not wholly mapped")
        offset = address - item.start
        data[offset:offset + len(payload)] = payload

    def snapshot(self) -> dict[str, bytes]:
        return {item.name: bytes(data)
                for item, data in zip(self._regions, self._storage)}

    def to_document(self) -> dict[str, Any]:
        region_hashes = [
            {"name": item.name, "sha256": hashlib.sha256(data).hexdigest()}
            for item, data in zip(self._regions, self._storage)
        ]
        return {
            "address_space_bits": ADDRESS_SPACE_BITS,
            "endianness": self._endianness,
            "alignment": self._alignment,
            "regions": [item.to_document() for item in self._regions],
            "region_hashes": region_hashes,
            "mapped_bytes": sum(item.size for item in self._regions),
            "fingerprint": self.fingerprint(),
        }

    def fingerprint(self) -> str:
        payload = {
            "endianness": self._endianness,
            "alignment": self._alignment,
            "regions": [item.to_document() for item in self._regions],
            "region_hashes": [
                hashlib.sha256(data).hexdigest()
                for data in self._storage
            ],
        }
        return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


class AbiMemoryService:
    """Adapts a guest memory model to the P4-01 ABI memory services.

    Every fault kind maps to a P2-08 failure code; the mapping is total and is
    validated against the contract failure-code list at construction.
    """

    def __init__(
        self,
        model: GuestMemoryModel,
        *,
        failure_codes: tuple[str, ...] = rt.RUNTIME_FAILURE_CODES,
        widths: tuple[int, ...] = WIDTHS,
    ) -> None:
        if not isinstance(model, GuestMemoryModel):
            raise GuestMemoryError("AbiMemoryService requires a GuestMemoryModel")
        if not set(widths) <= set(WIDTHS):
            raise GuestMemoryError("AbiMemoryService widths must be a subset of the ABI widths")
        for kind in FaultKind:
            code = ABI_FAILURE_BY_FAULT[kind]
            if code not in failure_codes:
                raise GuestMemoryError(f"fault {kind.value} maps to unknown failure code {code!r}")
        self._model = model
        self._codes = {code: index + 1 for index, code in enumerate(failure_codes)}
        self._widths = tuple(widths)

    @property
    def model(self) -> GuestMemoryModel:
        return self._model

    def status_for_fault(self, fault: GuestFault) -> int:
        return self._codes[fault.abi_failure]

    def read(self, address: int, width_bits: int) -> tuple[int, int | None]:
        if width_bits not in self._widths:
            return self._codes["MEMORY_WIDTH_UNSUPPORTED"], None
        result = self._model.try_read(address, width_bits)
        if not result.ok:
            return self.status_for_fault(result.fault), None
        return 0, result.value

    def write(self, address: int, value: int, width_bits: int) -> int:
        if width_bits not in self._widths:
            return self._codes["MEMORY_WIDTH_UNSUPPORTED"]
        result = self._model.try_write(address, value, width_bits)
        if not result.ok:
            return self.status_for_fault(result.fault)
        return 0

    def fetch(self, address: int, width_bits: int = 32) -> tuple[int, int | None]:
        try:
            return 0, self._model.fetch(address, width_bits)
        except GuestMemoryError as exc:
            return self.status_for_fault(exc.fault), None


# ---------------------------------------------------------------------------
# Frozen Phase-3 instance adapter
# ---------------------------------------------------------------------------
def parse_g_image(program_text: str) -> bytes:
    window_match = _IMAGE_WINDOW_RE.search(program_text)
    if window_match is None:
        raise GuestMemoryError("generated program does not declare OR_IMAGE_WINDOW")
    window = int(window_match.group(1))
    match = _G_IMAGE_RE.search(program_text)
    if match is None:
        raise GuestMemoryError("generated program does not define g_image")
    payload = bytes(int(token, 16) for token in _BYTE_RE.findall(match.group(1)))
    if len(payload) != window:
        raise GuestMemoryError(
            f"g_image declares {window} bytes but contains {len(payload)}")
    return payload


def parse_emitted_regions(program_text: str) -> tuple[tuple[int, int, int], ...]:
    match = _G_REGIONS_RE.search(program_text)
    if match is None:
        raise GuestMemoryError("generated program does not define g_or_regions")
    rows: list[tuple[int, int, int]] = []
    for row in _G_REGION_ROW_RE.finditer(match.group(1)):
        start = int(row.group(1), 16)
        end = int(row.group(2), 16)
        flags = 0
        if "OR_REGION_READABLE" in row.group(3):
            flags |= FROZEN_REGION_READABLE
        if "OR_REGION_WRITABLE" in row.group(3):
            flags |= FROZEN_REGION_WRITABLE
        rows.append((start, end, flags))
    if len(rows) != FROZEN_REGION_COUNT:
        raise GuestMemoryError(
            f"g_or_regions declares {len(rows)} regions, expected {FROZEN_REGION_COUNT}")
    return tuple(rows)


def frozen_phase3_memory() -> tuple[GuestMemoryModel, bytes]:
    """Build the declared memory model of the frozen Phase-3 image."""
    text = (ROOT / FROZEN_PROGRAM_PATH).read_text(encoding="utf-8")
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != FROZEN_PROGRAM_SHA256:
        raise GuestMemoryError("frozen generated program sha256 mismatch")
    image = parse_g_image(text)
    if hashlib.sha256(image).hexdigest() != FROZEN_IMAGE_SHA256:
        raise GuestMemoryError("frozen guest image sha256 mismatch")
    if len(image) != FROZEN_IMAGE_WINDOW:
        raise GuestMemoryError("frozen guest image window mismatch")
    model = GuestMemoryModel(
        (
            region("elf_image_headers", 0x0, 308, RegionKind.RODATA,
                   file_data=image[0x0:0x134]),
            region("text", 0x1000, 13948, RegionKind.CODE,
                   file_data=image[0x1000:0x467C]),
            region("rodata", 0x4680, 1912, RegionKind.RODATA,
                   file_data=image[0x4680:0x4DF8]),
            region("data", 0x4E00, 40, RegionKind.DATA,
                   file_data=image[0x4E00:0x4E28]),
            region("bss_zero_fill", 0x4E28, 18424, RegionKind.BSS),
        ),
        endianness="little",
        alignment="allow",
    )
    return model, image
