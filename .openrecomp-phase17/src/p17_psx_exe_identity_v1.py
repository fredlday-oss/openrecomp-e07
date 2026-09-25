#!/usr/bin/env python3
"""Phase-17 PS-X EXE identity wrapper around the frozen Phase-9 parser.

This module does not reimplement the PS-X EXE parser.  It imports the frozen
Phase-9 ``ingest`` function unchanged, exposes a thin ``PsxExeIdentity`` record,
and provides fail-closed helpers for the authentic Hercules TITLE identity.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

# Keep the frozen Phase-9 parser read-only and make this Phase-17 wrapper
# importable when callers expose only the Phase-17 source directory.
ROOT = pathlib.Path(__file__).resolve().parents[2]
PHASE9_SRC = ROOT / ".openrecomp-phase9" / "src"
if str(PHASE9_SRC) not in sys.path:
    sys.path.insert(0, str(PHASE9_SRC))

import p9_psx_exe_v1 as p9


class PsxExeIdentityError(Exception):
    pass


class PsxExeIdentity:
    def __init__(self, image: p9.PsxExeImage) -> None:
        self._image = image
        self.header = image.header

    @property
    def magic(self) -> bytes:
        return p9.MAGIC

    @property
    def pc0(self) -> int:
        return self.header.pc0

    @property
    def gp0(self) -> int:
        return self.header.gp0

    @property
    def t_addr(self) -> int:
        return self.header.t_addr

    @property
    def t_size(self) -> int:
        return self.header.t_size

    @property
    def d_addr(self) -> int:
        return self.header.d_addr

    @property
    def d_size(self) -> int:
        return self.header.d_size

    @property
    def b_addr(self) -> int:
        return self.header.b_addr

    @property
    def b_size(self) -> int:
        return self.header.b_size

    @property
    def s_addr(self) -> int:
        return self.header.s_addr

    @property
    def s_size(self) -> int:
        return self.header.s_size

    @property
    def text_end(self) -> int:
        return self.header.t_addr + self.header.t_size

    @property
    def payload(self) -> bytes:
        return self._image.payload

    @property
    def file_sha256(self) -> str:
        return self._image.file_sha256

    @property
    def payload_sha256(self) -> str:
        return self._image.payload_sha256

    @property
    def file_size(self) -> int:
        return self._image.file_size

    def reserved_summary(self) -> dict[str, int | None]:
        reserved = self.header.reserved
        nonzero_offsets = [i for i, b in enumerate(reserved) if b != 0]
        return {
            "nonzero_count": len(nonzero_offsets),
            "first_relative_offset": nonzero_offsets[0] if nonzero_offsets else None,
            "last_relative_offset": nonzero_offsets[-1] if nonzero_offsets else None,
        }

    def as_report(self) -> dict[str, Any]:
        h = self.header
        return {
            "magic": self.magic.decode("ascii"),
            "pc0": f"0x{h.pc0:08x}",
            "gp0": f"0x{h.gp0:08x}",
            "t_addr": f"0x{h.t_addr:08x}",
            "t_size": h.t_size,
            "d_addr": f"0x{h.d_addr:08x}",
            "d_size": h.d_size,
            "b_addr": f"0x{h.b_addr:08x}",
            "b_size": h.b_size,
            "s_addr": f"0x{h.s_addr:08x}",
            "s_size": h.s_size,
            "reserved_summary": self.reserved_summary(),
        }


def ingest_file(path: pathlib.Path) -> PsxExeIdentity:
    data = path.read_bytes()
    return PsxExeIdentity(p9.ingest(data))


def ingest_bytes(data: bytes) -> PsxExeIdentity:
    return PsxExeIdentity(p9.ingest(data))
