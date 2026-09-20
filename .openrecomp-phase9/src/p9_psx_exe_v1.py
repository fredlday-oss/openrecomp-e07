#!/usr/bin/env python3
"""OpenRecomp Phase-9 PS-X EXE ingestion V1.

Deterministic, fail-closed parsing and validation of the PS-X EXE container
format used by the bounded Phase-9 fixtures:

    offset 0x000  char[8]  magic "PS-X EXE"
    offset 0x008  u32      zero1 (must be 0)
    offset 0x00C  u32      zero2 (must be 0)
    offset 0x010  u32      pc0    initial program counter
    offset 0x014  u32      gp0    initial global pointer
    offset 0x018  u32      t_addr text load address
    offset 0x01C  u32      t_size text size in bytes
    offset 0x020  u32      d_addr data load address
    offset 0x024  u32      d_size data size in bytes
    offset 0x028  u32      b_addr bss address
    offset 0x02C  u32      b_size bss size in bytes
    offset 0x030  u32      s_addr initial stack pointer
    offset 0x034  u32      s_size stack size
    offset 0x038  ...      reserved (0x7C8 bytes)
    offset 0x800  ...      executable payload (t_size bytes)

The module is deliberately closed: only the bounded V1 form is accepted, and
every deviation is rejected with a stable code and no guessed recovery. It
never executes payload bytes and never writes them anywhere. The identity
record it produces contains only metadata (hashes, sizes, addresses, offsets,
counts and classifications), never executable content.

Address-space notes
-------------------

The bounded V1 form requires the text load address and entry point to lie in
the PS1 main-RAM KSEG0 window ``0x80000000 .. 0x80200000`` (2 MiB). This is an
explicit form restriction, not a general PS1 memory model; the full PS1
address-space contract is defined separately at P9-02.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from typing import Any

FORMAT_VERSION = "1.0.0"

MAGIC = b"PS-X EXE"
HEADER_SIZE = 0x800
RESERVED_OFFSET = 0x38
RESERVED_SIZE = HEADER_SIZE - RESERVED_OFFSET

PSX_RAM_KSEG0_BASE = 0x80000000
PSX_RAM_SIZE = 0x00200000
PSX_RAM_KSEG0_END = PSX_RAM_KSEG0_BASE + PSX_RAM_SIZE

FIELD_OFFSETS = {
    "zero1": 0x08,
    "zero2": 0x0C,
    "pc0": 0x10,
    "gp0": 0x14,
    "t_addr": 0x18,
    "t_size": 0x1C,
    "d_addr": 0x20,
    "d_size": 0x24,
    "b_addr": 0x28,
    "b_size": 0x2C,
    "s_addr": 0x30,
    "s_size": 0x34,
}

#: Closed set of fail-closed rejection codes.
ERROR_CODES = (
    "INPUT_TOO_SMALL",
    "BAD_MAGIC",
    "NONZERO_RESERVED_HEADER_FIELD",
    "EMPTY_PAYLOAD",
    "MISALIGNED_PAYLOAD_SIZE",
    "TRUNCATED_PAYLOAD",
    "UNSUPPORTED_TRAILING_DATA",
    "MISALIGNED_LOAD_ADDRESS",
    "LOAD_ADDRESS_OUTSIDE_RAM",
    "PAYLOAD_EXCEEDS_RAM",
    "MISALIGNED_ENTRY",
    "ENTRY_OUTSIDE_PAYLOAD",
    "UNSUPPORTED_DATA_SECTION",
    "MISALIGNED_DATA_ADDRESS",
    "DATA_OUTSIDE_RAM",
    "DATA_EXCEEDS_RAM",
    "MISALIGNED_BSS_ADDRESS",
    "BSS_OUTSIDE_RAM",
    "BSS_EXCEEDS_RAM",
    "MISALIGNED_STACK",
    "STACK_OUTSIDE_RAM",
    "MISALIGNED_GP",
    "READ_OUTSIDE_PAYLOAD",
)


class PsxExeError(ValueError):
    """Fail-closed PS-X EXE ingestion rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise AssertionError(f"unknown PS-X EXE error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class PsxExeHeader:
    """Validated PS-X EXE header fields."""

    zero1: int
    zero2: int
    pc0: int
    gp0: int
    t_addr: int
    t_size: int
    d_addr: int
    d_size: int
    b_addr: int
    b_size: int
    s_addr: int
    s_size: int
    reserved: bytes = field(repr=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "zero1": self.zero1,
            "zero2": self.zero2,
            "pc0": self.pc0,
            "gp0": self.gp0,
            "t_addr": self.t_addr,
            "t_size": self.t_size,
            "d_addr": self.d_addr,
            "d_size": self.d_size,
            "b_addr": self.b_addr,
            "b_size": self.b_size,
            "s_addr": self.s_addr,
            "s_size": self.s_size,
        }


@dataclass(frozen=True)
class PsxExeImage:
    """A validated PS-X EXE image.

    ``payload`` holds the executable bytes in memory for the analysis
    pipeline. It is never committed, printed or serialized by this module.
    """

    header: PsxExeHeader
    payload: bytes = field(repr=False)
    file_sha256: str
    payload_sha256: str
    file_size: int

    @property
    def entry(self) -> int:
        return self.header.pc0

    @property
    def load_address(self) -> int:
        return self.header.t_addr

    @property
    def text_end(self) -> int:
        return self.header.t_addr + self.header.t_size

    @property
    def bss_end(self) -> int:
        return self.header.b_addr + self.header.b_size

    def read_u32(self, address: int) -> int:
        """Read one little-endian word from the loaded text payload."""
        offset = address - self.header.t_addr
        if offset < 0 or offset + 4 > len(self.payload):
            raise PsxExeError(
                "READ_OUTSIDE_PAYLOAD",
                f"read 0x{address:08x} outside 0x{self.header.t_addr:08x}+{self.header.t_size}",
            )
        return struct.unpack_from("<I", self.payload, offset)[0]

    def identity(self) -> dict[str, Any]:
        """Non-reconstructive identity record (no payload bytes)."""
        reserved = self.header.reserved
        nonzero = [index for index, value in enumerate(reserved) if value]
        header = self.header.as_dict()
        return {
            "format": "PS-X EXE",
            "format_version": FORMAT_VERSION,
            "magic": MAGIC.decode("ascii"),
            "header_size": HEADER_SIZE,
            "file_size": self.file_size,
            "file_sha256": self.file_sha256,
            "payload_size": len(self.payload),
            "payload_sha256": self.payload_sha256,
            "entry_pc": f"0x{self.header.pc0:08x}",
            "initial_gp": f"0x{self.header.gp0:08x}",
            "load_address": f"0x{self.header.t_addr:08x}",
            "text_end": f"0x{self.text_end:08x}",
            "stack_pointer": f"0x{self.header.s_addr:08x}",
            "header_fields": {key: f"0x{value:08x}" for key, value in sorted(header.items())},
            "data_section": {
                "present": self.header.d_size > 0,
                "address": f"0x{self.header.d_addr:08x}",
                "size": self.header.d_size,
            },
            "bss_section": {
                "present": self.header.b_size > 0,
                "address": f"0x{self.header.b_addr:08x}",
                "size": self.header.b_size,
            },
            "stack": {
                "pointer": f"0x{self.header.s_addr:08x}",
                "size": self.header.s_size,
            },
            "ram_span": {
                "start": f"0x{self.header.t_addr:08x}",
                "end": f"0x{max(self.text_end, self.bss_end if self.header.b_size else self.text_end):08x}",
            },
            "reserved": {
                "offset": f"0x{RESERVED_OFFSET:02x}",
                "size": RESERVED_SIZE,
                "sha256": hashlib.sha256(reserved).hexdigest(),
                "nonzero_bytes": len(nonzero),
                "first_nonzero_offset": (
                    f"0x{RESERVED_OFFSET + nonzero[0]:02x}" if nonzero else None
                ),
                "last_nonzero_offset": (
                    f"0x{RESERVED_OFFSET + nonzero[-1]:02x}" if nonzero else None
                ),
            },
            "address_space": {
                "ram_kseg0_base": f"0x{PSX_RAM_KSEG0_BASE:08x}",
                "ram_size": PSX_RAM_SIZE,
                "ram_kseg0_end": f"0x{PSX_RAM_KSEG0_END:08x}",
            },
        }


def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise PsxExeError(code, detail)


def parse_header(data: bytes) -> PsxExeHeader:
    """Parse and structurally validate the header (no payload checks)."""
    _require(len(data) >= HEADER_SIZE, "INPUT_TOO_SMALL", f"{len(data)} bytes")
    _require(data[:8] == MAGIC, "BAD_MAGIC", repr(data[:8]))
    fields = {
        name: struct.unpack_from("<I", data, offset)[0]
        for name, offset in sorted(FIELD_OFFSETS.items())
    }
    _require(fields["zero1"] == 0, "NONZERO_RESERVED_HEADER_FIELD", f"zero1=0x{fields['zero1']:08x}")
    _require(fields["zero2"] == 0, "NONZERO_RESERVED_HEADER_FIELD", f"zero2=0x{fields['zero2']:08x}")
    return PsxExeHeader(
        **fields,
        reserved=bytes(data[RESERVED_OFFSET:HEADER_SIZE]),
    )


def ingest(data: bytes) -> PsxExeImage:
    """Parse, validate and load one bounded-form PS-X EXE image."""
    header = parse_header(data)

    _require(header.t_size > 0, "EMPTY_PAYLOAD", f"t_size={header.t_size}")
    _require(header.t_size % 4 == 0, "MISALIGNED_PAYLOAD_SIZE", f"t_size={header.t_size}")
    available = len(data) - HEADER_SIZE
    _require(header.t_size <= available, "TRUNCATED_PAYLOAD", f"t_size={header.t_size} available={available}")
    _require(
        header.t_size == available,
        "UNSUPPORTED_TRAILING_DATA",
        f"t_size={header.t_size} trailing={available - header.t_size}",
    )

    _require(header.t_addr % 4 == 0, "MISALIGNED_LOAD_ADDRESS", f"t_addr=0x{header.t_addr:08x}")
    _require(
        PSX_RAM_KSEG0_BASE <= header.t_addr < PSX_RAM_KSEG0_END,
        "LOAD_ADDRESS_OUTSIDE_RAM",
        f"t_addr=0x{header.t_addr:08x}",
    )
    _require(
        header.t_addr + header.t_size <= PSX_RAM_KSEG0_END,
        "PAYLOAD_EXCEEDS_RAM",
        f"end=0x{header.t_addr + header.t_size:08x}",
    )

    _require(header.pc0 % 4 == 0, "MISALIGNED_ENTRY", f"pc0=0x{header.pc0:08x}")
    _require(
        header.t_addr <= header.pc0 < header.t_addr + header.t_size,
        "ENTRY_OUTSIDE_PAYLOAD",
        f"pc0=0x{header.pc0:08x} text=0x{header.t_addr:08x}+{header.t_size}",
    )

    _require(header.d_size == 0, "UNSUPPORTED_DATA_SECTION", f"d_size={header.d_size}")

    if header.b_size > 0:
        _require(header.b_addr % 4 == 0, "MISALIGNED_BSS_ADDRESS", f"b_addr=0x{header.b_addr:08x}")
        _require(
            PSX_RAM_KSEG0_BASE <= header.b_addr < PSX_RAM_KSEG0_END,
            "BSS_OUTSIDE_RAM",
            f"b_addr=0x{header.b_addr:08x}",
        )
        _require(
            header.b_addr + header.b_size <= PSX_RAM_KSEG0_END,
            "BSS_EXCEEDS_RAM",
            f"end=0x{header.b_addr + header.b_size:08x}",
        )

    _require(header.s_addr % 8 == 0, "MISALIGNED_STACK", f"s_addr=0x{header.s_addr:08x}")
    _require(
        PSX_RAM_KSEG0_BASE < header.s_addr <= PSX_RAM_KSEG0_END,
        "STACK_OUTSIDE_RAM",
        f"s_addr=0x{header.s_addr:08x}",
    )
    _require(header.gp0 % 4 == 0, "MISALIGNED_GP", f"gp0=0x{header.gp0:08x}")

    payload = bytes(data[HEADER_SIZE : HEADER_SIZE + header.t_size])
    return PsxExeImage(
        header=header,
        payload=payload,
        file_sha256=hashlib.sha256(data).hexdigest(),
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        file_size=len(data),
    )
