#!/usr/bin/env python3
"""OpenRecomp Phase-17 minimal ISO 9660 directory-record reader V1."""

from __future__ import annotations

import pathlib
import struct
from dataclasses import dataclass

SECTOR_SIZE = 2352
USER_DATA_OFFSET = 24
USER_DATA_SIZE = 2048


class Iso9660Error(Exception):
    pass


@dataclass(frozen=True)
class DirectoryRecord:
    length: int
    extent_lba: int
    data_length: int
    flags: int
    file_id: str

    @classmethod
    def parse(cls, raw: bytes, offset: int) -> "DirectoryRecord | None":
        length = raw[offset]
        if length == 0:
            return None
        if offset + length > len(raw):
            raise Iso9660Error(f"directory record runs past sector boundary at offset {offset}")
        entry = raw[offset : offset + length]
        extent_lba = int.from_bytes(entry[2:6], "little")
        data_length = int.from_bytes(entry[10:14], "little")
        flags = entry[25]
        fid_len = entry[32]
        if 33 + fid_len > length:
            raise Iso9660Error(f"invalid file identifier length {fid_len} at offset {offset}")
        fid_bytes = entry[33 : 33 + fid_len]
        file_id = fid_bytes.decode("ascii", errors="replace")
        return cls(length=length, extent_lba=extent_lba, data_length=data_length,
                   flags=flags, file_id=file_id)


@dataclass(frozen=True)
class PathTableEntry:
    name: str
    parent: int
    lba: int


@dataclass(frozen=True)
class Iso9660Image:
    bin_path: pathlib.Path
    pvd_lba: int
    root_lba: int
    root_data_length: int

    @classmethod
    def open(cls, bin_path: pathlib.Path) -> "Iso9660Image":
        with bin_path.open("rb") as f:
            f.seek(16 * SECTOR_SIZE + USER_DATA_OFFSET)
            pvd = f.read(USER_DATA_SIZE)
        if len(pvd) < 2048:
            raise Iso9660Error("PVD too short")
        if pvd[0] != 1 or pvd[1:6] != b"CD001" or pvd[6] != 1:
            raise Iso9660Error("invalid PVD standard identifier")
        root_dir = pvd[156 : 156 + 34]
        root_lba = int.from_bytes(root_dir[2:6], "little")
        root_data_length = int.from_bytes(root_dir[10:14], "little")
        return cls(bin_path=bin_path, pvd_lba=16, root_lba=root_lba,
                   root_data_length=root_data_length)

    def _read_user_data(self, lba: int, count: int = 1) -> bytes:
        with self.bin_path.open("rb") as f:
            f.seek(lba * SECTOR_SIZE + USER_DATA_OFFSET)
            return b"".join(f.read(USER_DATA_SIZE) for _ in range(count))

    def list_directory(self, lba: int, data_length: int) -> list[DirectoryRecord]:
        sectors_needed = (data_length + USER_DATA_SIZE - 1) // USER_DATA_SIZE
        raw = self._read_user_data(lba, sectors_needed)
        raw = raw[:data_length]
        records: list[DirectoryRecord] = []
        offset = 0
        while offset < len(raw):
            if raw[offset] == 0:
                offset += 1
                continue
            rec = DirectoryRecord.parse(raw, offset)
            if rec is None:
                offset += 1
                continue
            records.append(rec)
            offset += rec.length
        return records

    def find_file(self, iso_path: str) -> DirectoryRecord:
        """Mechanically locate an ISO 9660 file path of the form '\\A\\B.;1'.

        The leading backslash is treated as the root directory.  Directory
        names are matched case-sensitively against the ISO 9660 file
        identifier (including the version suffix for files).
        """
        parts = [p for p in iso_path.replace("/", "\\").split("\\") if p]
        if not parts:
            raise Iso9660Error("empty ISO path")
        current_lba = self.root_lba
        current_len = self.root_data_length
        for index, part in enumerate(parts):
            records = self.list_directory(current_lba, current_len)
            match: DirectoryRecord | None = None
            for rec in records:
                if rec.file_id == part or rec.file_id.rsplit(";", 1)[0] == part.rsplit(";", 1)[0]:
                    match = rec
                    break
            if match is None:
                found = [rec.file_id for rec in records]
                raise Iso9660Error(f"path component not found: {part!r} (found {found})")
            if index == len(parts) - 1:
                if (match.flags & 0x02) != 0:
                    raise Iso9660Error(f"final path component is a directory: {part!r}")
                return match
            if (match.flags & 0x02) == 0:
                raise Iso9660Error(f"intermediate path component is not a directory: {part!r}")
            current_lba = match.extent_lba
            current_len = match.data_length
        raise Iso9660Error("unreachable")


@dataclass(frozen=True)
class PsxExeHeader:
    magic: bytes
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
    reserved_region: bytes

    @classmethod
    def parse(cls, header: bytes) -> "PsxExeHeader":
        if len(header) < 2048:
            raise ValueError("PS-X EXE header too short")
        if header[:8] != b"PS-X EXE":
            raise ValueError(f"bad PS-X EXE magic: {header[:8]!r}")
        (pc0, gp0, t_addr, t_size, d_addr, d_size, b_addr, b_size, s_addr, s_size) = \
            struct.unpack("<10I", header[16:56])
        return cls(
            magic=header[:8],
            pc0=pc0,
            gp0=gp0,
            t_addr=t_addr,
            t_size=t_size,
            d_addr=d_addr,
            d_size=d_size,
            b_addr=b_addr,
            b_size=b_size,
            s_addr=s_addr,
            s_size=s_size,
            reserved_region=header[56:1968],
        )

    def reserved_summary(self) -> dict[str, int | None]:
        nonzero_offsets = [i for i, b in enumerate(self.reserved_region) if b != 0]
        return {
            "nonzero_count": len(nonzero_offsets),
            "first_relative_offset": nonzero_offsets[0] if nonzero_offsets else None,
            "last_relative_offset": nonzero_offsets[-1] if nonzero_offsets else None,
        }
