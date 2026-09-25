#!/usr/bin/env python3
"""OpenRecomp Phase-17 deterministic, fail-closed ISO 9660 reader V1.

Reads raw 2352-byte CD-ROM sectors (Mode 2 Form 1), validates sync, mode and
subheader duplicates, and exposes only validated user-data sectors.  Directory
record parsing checks both-endian numeric fields, minimum record geometry, and
file-identifier decoding.  All errors raise ``Iso9660Error`` without leaking
private directory contents or fixture data.
"""

from __future__ import annotations

import pathlib
import struct
from dataclasses import dataclass
from typing import BinaryIO

RAW_SECTOR_SIZE = 2352
USER_DATA_OFFSET = 24
USER_DATA_SIZE = 2048

SYNC_PATTERN = bytes([0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
                      0xFF, 0xFF, 0xFF, 0x00])

MIN_DIRECTORY_RECORD_LENGTH = 34
MAX_FILE_ID_LENGTH = 222


class Iso9660Error(Exception):
    """Fail-closed rejection of malformed ISO 9660 metadata."""


@dataclass(frozen=True)
class DirectoryRecord:
    length: int
    extent_lba: int
    data_length: int
    flags: int
    file_id: str

    @classmethod
    def parse(cls, raw: bytes, offset: int, sector_base: int = 0) -> "DirectoryRecord":
        if offset >= len(raw):
            raise Iso9660Error("directory record offset past sector end")
        length = raw[offset]
        if length == 0:
            raise Iso9660Error("zero-length directory record")
        if length < MIN_DIRECTORY_RECORD_LENGTH:
            raise Iso9660Error(f"directory record too short: {length}")
        if offset + length > len(raw):
            raise Iso9660Error(
                f"directory record runs past sector boundary at offset {offset}"
            )
        entry = raw[offset : offset + length]

        # Both-endian numeric fields must agree.
        extent_le = int.from_bytes(entry[2:6], "little")
        extent_be = int.from_bytes(entry[6:10], "big")
        if extent_le != extent_be:
            raise Iso9660Error(
                f"extent LBA endian mismatch at offset {offset}: "
                f"LE={extent_le} BE={extent_be}"
            )
        data_length_le = int.from_bytes(entry[10:14], "little")
        data_length_be = int.from_bytes(entry[14:18], "big")
        if data_length_le != data_length_be:
            raise Iso9660Error(
                f"data length endian mismatch at offset {offset}: "
                f"LE={data_length_le} BE={data_length_be}"
            )
        flags = entry[25]
        fid_len = entry[32]
        if fid_len == 0 or fid_len > MAX_FILE_ID_LENGTH:
            raise Iso9660Error(
                f"invalid file identifier length {fid_len} at offset {offset}"
            )
        if 33 + fid_len > length:
            raise Iso9660Error(
                f"file identifier exceeds record length at offset {offset}"
            )
        fid_bytes = entry[33 : 33 + fid_len]
        try:
            file_id = fid_bytes.decode("ascii")
        except UnicodeDecodeError as exc:
            raise Iso9660Error(
                f"non-ASCII file identifier at offset {offset}"
            ) from exc
        return cls(
            length=length,
            extent_lba=extent_le,
            data_length=data_length_le,
            flags=flags,
            file_id=file_id,
        )


@dataclass(frozen=True)
class Iso9660Image:
    bin_path: pathlib.Path
    pvd_lba: int
    root_lba: int
    root_data_length: int
    total_sectors: int

    @classmethod
    def open(cls, bin_path: pathlib.Path) -> "Iso9660Image":
        if not bin_path.is_file():
            raise Iso9660Error("disc image not found")
        file_size = bin_path.stat().st_size
        if file_size == 0 or file_size % RAW_SECTOR_SIZE != 0:
            raise Iso9660Error("disc size is not a multiple of 2352 bytes")
        total_sectors = file_size // RAW_SECTOR_SIZE
        if total_sectors <= 16:
            raise Iso9660Error("disc has no Primary Volume Descriptor")

        pvd = cls._read_raw_sector_data(bin_path, 16)
        if len(pvd) != USER_DATA_SIZE:
            raise Iso9660Error("PVD user-data sector too short")
        if pvd[0] != 1 or pvd[1:6] != b"CD001" or pvd[6] != 1:
            raise Iso9660Error("invalid PVD standard identifier")

        root_dir = pvd[156 : 156 + MIN_DIRECTORY_RECORD_LENGTH]
        if len(root_dir) < MIN_DIRECTORY_RECORD_LENGTH:
            raise Iso9660Error("PVD root directory record truncated")
        try:
            root_rec = DirectoryRecord.parse(root_dir, 0)
        except Iso9660Error as exc:
            raise Iso9660Error(f"invalid PVD root directory record: {exc}") from exc
        if (root_rec.flags & 0x02) == 0:
            raise Iso9660Error("PVD root record is not a directory")

        return cls(
            bin_path=bin_path,
            pvd_lba=16,
            root_lba=root_rec.extent_lba,
            root_data_length=root_rec.data_length,
            total_sectors=total_sectors,
        )

    @classmethod
    def _read_raw_sector(cls, bin_path: pathlib.Path, lba: int,
                         handle: BinaryIO | None = None) -> bytes:
        f = handle
        close_needed = False
        if f is None:
            f = bin_path.open("rb")
            close_needed = True
        try:
            f.seek(lba * RAW_SECTOR_SIZE)
            raw = f.read(RAW_SECTOR_SIZE)
            if len(raw) != RAW_SECTOR_SIZE:
                raise Iso9660Error(
                    f"short raw sector read at LBA {lba}: got {len(raw)} bytes"
                )
            return raw
        finally:
            if close_needed:
                f.close()

    @classmethod
    def _read_raw_sector_data(cls, bin_path: pathlib.Path, lba: int,
                              handle: BinaryIO | None = None) -> bytes:
        raw = cls._read_raw_sector(bin_path, lba, handle)
        if raw[:12] != SYNC_PATTERN:
            raise Iso9660Error(f"invalid sync pattern at LBA {lba}")
        if raw[15] != 2:
            raise Iso9660Error(
                f"unsupported sector mode at LBA {lba}: {raw[15]}"
            )
        sub = raw[16:24]
        # Mode 2 Form 1: submode byte bit 5 (0x20) must be 0.
        if (sub[2] & 0x20) != 0:
            raise Iso9660Error(
                f"sector at LBA {lba} is not Mode 2 Form 1 (submode=0x{sub[2]:02x})"
            )
        # Duplicate subheader bytes must match.
        if sub[0:4] != sub[4:8]:
            raise Iso9660Error(
                f"subheader duplicate mismatch at LBA {lba}"
            )
        return raw[USER_DATA_OFFSET : USER_DATA_OFFSET + USER_DATA_SIZE]

    def _read_user_data(self, lba: int, count: int = 1) -> bytes:
        if lba < 0 or lba + count > self.total_sectors:
            raise Iso9660Error(
                f"LBA range [{lba}, {lba + count}) out of bounds (total {self.total_sectors})"
            )
        chunks: list[bytes] = []
        with self.bin_path.open("rb") as f:
            for i in range(count):
                chunks.append(self._read_raw_sector_data(self.bin_path, lba + i, f))
        return b"".join(chunks)

    def list_directory(self, lba: int, data_length: int) -> list[DirectoryRecord]:
        if data_length == 0:
            raise Iso9660Error("directory data length is zero")
        sectors_needed = (data_length + USER_DATA_SIZE - 1) // USER_DATA_SIZE
        raw = self._read_user_data(lba, sectors_needed)
        raw = raw[:data_length]
        records: list[DirectoryRecord] = []
        offset = 0
        while offset < len(raw):
            if raw[offset] == 0:
                # Padding to end of logical sector.
                sector_index = offset // USER_DATA_SIZE
                next_boundary = (sector_index + 1) * USER_DATA_SIZE
                offset = min(next_boundary, len(raw))
                continue
            try:
                rec = DirectoryRecord.parse(raw, offset)
            except Iso9660Error as exc:
                raise Iso9660Error(
                    f"directory at LBA {lba} offset {offset}: {exc}"
                ) from exc
            records.append(rec)
            offset += rec.length
            # Pad to even boundary per ISO 9660.
            if rec.length % 2 == 1:
                offset += 1
        return records

    def find_file(self, iso_path: str) -> DirectoryRecord:
        """Mechanically locate an ISO 9660 file path of the form '\\A\\B.;1'.

        The leading backslash is treated as the root directory.  Directory
        names are matched case-sensitively against the ISO 9660 file
        identifier (without version suffix for directories; with version
        suffix for files).
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
                # Skip '.' and '..' entries.
                if rec.file_id in ("\x00", "\x01"):
                    continue
                if index == len(parts) - 1:
                    # Final component: files carry a version suffix.
                    if rec.file_id == part or rec.file_id.rsplit(";", 1)[0] == part:
                        match = rec
                        break
                else:
                    # Intermediate component: directories have no version suffix.
                    if rec.file_id == part:
                        match = rec
                        break
            if match is None:
                raise Iso9660Error(f"path component not found: {part!r}")
            if index == len(parts) - 1:
                if (match.flags & 0x02) != 0:
                    raise Iso9660Error(
                        f"final path component is a directory: {part!r}"
                    )
                return match
            if (match.flags & 0x02) == 0:
                raise Iso9660Error(
                    f"intermediate path component is not a directory: {part!r}"
                )
            current_lba = match.extent_lba
            current_len = match.data_length
        raise Iso9660Error("unreachable")

    def extract_file(self, record: DirectoryRecord) -> bytes:
        """Extract ``record.data_length`` bytes from the validated disc image."""
        if record.data_length < 0:
            raise Iso9660Error("negative data length")
        if record.extent_lba < 0:
            raise Iso9660Error("negative extent LBA")
        sectors_needed = (record.data_length + USER_DATA_SIZE - 1) // USER_DATA_SIZE
        raw = self._read_user_data(record.extent_lba, sectors_needed)
        data = raw[: record.data_length]
        if len(data) != record.data_length:
            raise Iso9660Error(
                f"extracted {len(data)} bytes, expected {record.data_length}"
            )
        return data
