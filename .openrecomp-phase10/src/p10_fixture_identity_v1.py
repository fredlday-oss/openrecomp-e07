#!/usr/bin/env python3
"""OpenRecomp Phase-10 private-fixture and disc-image identity V1.

Deterministic, read-only reconnaissance of the private PlayStation fixture
directory:

* discovers the CUE sheet and every BIN it references (never assuming a
  filename);
* validates the CUE track layout (``MODE2/2352`` bounded form);
* reads the ISO9660 primary volume descriptor from the BIN through the
  declared sector format and enumerates the root directory;
* locates ``SYSTEM.CNF`` and verifies the boot target relationship;
* hashes the disc extent of the boot executable and compares it with the
  primary ``SLUS_005.29`` fixture;
* records non-reconstructive metadata only: filenames, sizes, hashes, offsets,
  LBA/byte extents, directory names, header fields, counts and
  classifications.

No payload bytes, sectors, file contents or other reconstructive derived data
are returned to a caller, written to evidence or committed. Nothing is
executed. The module fails closed with stable codes when the disc cannot be
read through the declared format.
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import struct
from dataclasses import dataclass, field
from typing import Any, BinaryIO

FIXTURE_VERSION = "1.0.0"

PRIMARY_EXECUTABLE = "SLUS_005.29"
BOOT_PREFIX = "cdrom:"

SECTOR_SIZE = 2352
USER_DATA_OFFSET = 24
USER_DATA_SIZE = 2048
SYNC_PATTERN = bytes([0x00] + [0xFF] * 10 + [0x00])

PVD_LBA = 16
PVD_MAGIC = b"CD001"
PVD_TYPE_PRIMARY = 1

MAX_DIRECTORY_DEPTH = 4

ERROR_CODES = (
    "FIXTURE_DIRECTORY_MISSING",
    "CUE_MISSING",
    "CUE_AMBIGUOUS",
    "CUE_MALFORMED",
    "CUE_UNSUPPORTED_TRACK",
    "CUE_REFERENCED_BIN_MISSING",
    "EXECUTABLE_MISSING",
    "PVD_UNREADABLE",
    "PVD_NOT_ISO9660",
    "DIRECTORY_UNREADABLE",
    "DIRECTORY_RECORD_INVALID",
    "SYSTEM_CNF_MISSING",
    "SYSTEM_CNF_MALFORMED",
    "BOOT_TARGET_MISSING",
    "BOOT_TARGET_MISMATCH",
)


class FixtureIdentityError(ValueError):
    """Fail-closed fixture/disc identity error with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise AssertionError(f"unknown fixture identity error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise FixtureIdentityError(code, detail)


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class Track:
    number: int
    track_type: str
    index1_msf: tuple[int, int, int]

    def to_document(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "type": self.track_type,
            "index1_msf": list(self.index1_msf),
        }


@dataclass(frozen=True)
class CueSheet:
    path: pathlib.Path
    file_name: str
    file_type: str
    tracks: tuple[Track, ...]
    referenced_bins: tuple[str, ...]
    sha256: str
    size: int

    def to_document(self) -> dict[str, Any]:
        return {
            "cue_sha256": self.sha256,
            "cue_size": self.size,
            "directory_entry": self.path.name,
            "file_entry": self.file_name,
            "file_type": self.file_type,
            "track_count": len(self.tracks),
            "tracks": [track.to_document() for track in self.tracks],
            "referenced_bins": list(self.referenced_bins),
        }


def discover_fixture_directory(root: pathlib.Path) -> pathlib.Path:
    _require(root.is_dir(), "FIXTURE_DIRECTORY_MISSING", str(root.name))
    return root


def parse_cue(path: pathlib.Path) -> CueSheet:
    text = path.read_text(encoding="utf-8", errors="replace")
    files = re.findall(r'^\s*FILE\s+"([^"]+)"\s+(\S+)\s*$', text, re.MULTILINE)
    _require(bool(files), "CUE_MALFORMED", "no FILE entry")
    _require(len(files) == 1, "CUE_UNSUPPORTED_TRACK", f"{len(files)} FILE entries")

    tracks: list[Track] = []
    pending_type: str | None = None
    for line in text.splitlines():
        track_match = re.match(r"^\s*TRACK\s+(\d+)\s+(\S+)\s*$", line)
        if track_match:
            number = int(track_match.group(1))
            track_type = track_match.group(2)
            tracks.append(Track(number, track_type, (0, 0, 0)))
            pending_type = track_type
            continue
        index_match = re.match(r"^\s*INDEX\s+(\d+)\s+(\d+):(\d+):(\d+)\s*$", line)
        if index_match and index_match.group(1) == "01" and tracks:
            tracks[-1] = Track(
                tracks[-1].number,
                pending_type or tracks[-1].track_type,
                (int(index_match.group(2)), int(index_match.group(3)), int(index_match.group(4))),
            )
    _require(bool(tracks), "CUE_MALFORMED", "no TRACK entry")
    for track in tracks:
        _require(track.track_type.upper() == "MODE2/2352", "CUE_UNSUPPORTED_TRACK", track.track_type)
        _require(track.index1_msf == (0, 0, 0), "CUE_UNSUPPORTED_TRACK", str(track.index1_msf))

    return CueSheet(
        path=path,
        file_name=files[0][0],
        file_type=files[0][1].upper(),
        tracks=tuple(tracks),
        referenced_bins=(files[0][0],),
        sha256=sha256_file(path),
        size=path.stat().st_size,
    )


def discover_cue(directory: pathlib.Path) -> CueSheet:
    candidates = sorted(
        entry for entry in directory.iterdir()
        if entry.is_file() and entry.suffix.lower() == ".cue"
    )
    _require(bool(candidates), "CUE_MISSING", "no .cue entry")
    _require(len(candidates) == 1, "CUE_AMBIGUOUS", f"{len(candidates)} .cue entries")
    return parse_cue(candidates[0])


def verify_referenced_bins(directory: pathlib.Path, cue: CueSheet) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for name in cue.referenced_bins:
        path = directory / name
        _require(path.is_file(), "CUE_REFERENCED_BIN_MISSING", name)
        records.append(
            {
                "directory_entry": path.name,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return records


def _read_user_data(handle: BinaryIO, lba: int, count: int = 1) -> bytes:
    handle.seek(lba * SECTOR_SIZE)
    raw = handle.read(SECTOR_SIZE * count)
    _require(len(raw) == SECTOR_SIZE * count, "PVD_UNREADABLE", f"lba={lba}")
    for index in range(count):
        sector = raw[index * SECTOR_SIZE : (index + 1) * SECTOR_SIZE]
        _require(sector[:12] == SYNC_PATTERN, "PVD_UNREADABLE", f"sync lba={lba + index}")
        submode = sector[18]
        form1 = bool(submode & 0x08) and not (submode & 0x20)
        _require(form1, "PVD_UNREADABLE", f"not form 1 data sector lba={lba + index}")
    return b"".join(
        raw[index * SECTOR_SIZE + USER_DATA_OFFSET : index * SECTOR_SIZE + USER_DATA_OFFSET + USER_DATA_SIZE]
        for index in range(count)
    )


@dataclass(frozen=True)
class DirectoryEntry:
    name: str
    extent_lba: int
    size: int
    is_directory: bool

    def to_document(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "extent_lba": self.extent_lba,
            "size": self.size,
            "is_directory": self.is_directory,
        }


def read_volume_descriptor(handle: BinaryIO) -> dict[str, Any]:
    pvd = _read_user_data(handle, PVD_LBA)
    _require(pvd[0] == PVD_TYPE_PRIMARY and pvd[1:6] == PVD_MAGIC, "PVD_NOT_ISO9660", "no primary volume descriptor")
    root = pvd[156:190]
    return {
        "pvd_lba": PVD_LBA,
        "volume_space_size_sectors": struct.unpack("<I", pvd[80:84])[0],
        "system_identifier": pvd[8:40].decode("ascii", "replace").rstrip(),
        "volume_identifier": pvd[40:72].decode("ascii", "replace").rstrip(),
        "root_extent_lba": struct.unpack("<I", root[2:6])[0],
        "root_size": struct.unpack("<I", root[10:14])[0],
    }


def read_directory(handle: BinaryIO, lba: int, size: int) -> list[DirectoryEntry]:
    _require(size % USER_DATA_SIZE == 0 or size > 0, "DIRECTORY_RECORD_INVALID", f"size={size}")
    blocks = max(1, (size + USER_DATA_SIZE - 1) // USER_DATA_SIZE)
    data = _read_user_data(handle, lba, blocks)
    entries: list[DirectoryEntry] = []
    offset = 0
    while offset < len(data):
        length = data[offset]
        if length == 0:
            offset = (offset // USER_DATA_SIZE + 1) * USER_DATA_SIZE
            continue
        _require(offset + length <= len(data), "DIRECTORY_RECORD_INVALID", f"lba={lba} offset={offset}")
        record = data[offset : offset + length]
        name_length = record[32]
        _require(33 + name_length <= length, "DIRECTORY_RECORD_INVALID", f"name at lba={lba}")
        entries.append(
            DirectoryEntry(
                name=record[33 : 33 + name_length].decode("ascii", "replace"),
                extent_lba=struct.unpack("<I", record[2:6])[0],
                size=struct.unpack("<I", record[10:14])[0],
                is_directory=bool(record[25] & 0x02),
            )
        )
        offset += length
    return entries


def find_entry(handle: BinaryIO, volume: dict[str, Any], target: str) -> DirectoryEntry | None:
    wanted = target.upper()
    queue: list[tuple[int, int, int]] = [(volume["root_extent_lba"], volume["root_size"], 0)]
    seen: set[tuple[int, int]] = set()
    while queue:
        lba, size, depth = queue.pop(0)
        if (lba, size) in seen:
            continue
        seen.add((lba, size))
        for entry in read_directory(handle, lba, size):
            if entry.name in ("\x00", "\x01"):
                continue
            base = entry.name.split(";")[0].upper()
            if base == wanted:
                return entry
            if entry.is_directory and depth < MAX_DIRECTORY_DEPTH and base not in (".", ".."):
                queue.append((entry.extent_lba, entry.size, depth + 1))
    return None


def read_extent(handle: BinaryIO, entry: DirectoryEntry) -> bytes:
    blocks = (entry.size + USER_DATA_SIZE - 1) // USER_DATA_SIZE
    data = _read_user_data(handle, entry.extent_lba, blocks)
    return data[: entry.size]


def extent_sha256(handle: BinaryIO, entry: DirectoryEntry) -> str:
    return hashlib.sha256(read_extent(handle, entry)).hexdigest()


def parse_system_cnf(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        fields[key.strip().upper()] = value.strip()
    _require("BOOT" in fields, "SYSTEM_CNF_MALFORMED", "no BOOT field")
    return fields


def boot_target(fields: dict[str, str]) -> str:
    boot = fields["BOOT"]
    lowered = boot.lower()
    _require(lowered.startswith(BOOT_PREFIX), "SYSTEM_CNF_MALFORMED", "BOOT is not cdrom:")
    target = boot[len(BOOT_PREFIX) :].strip()
    target = target.split(";")[0]
    target = target.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    _require(bool(target), "SYSTEM_CNF_MALFORMED", "empty BOOT target")
    return target


def build_identity(directory: pathlib.Path) -> dict[str, Any]:
    """Deterministic, non-reconstructive fixture/disc identity record."""
    directory = discover_fixture_directory(directory)
    cue = discover_cue(directory)
    bins = verify_referenced_bins(directory, cue)

    executable_path = directory / PRIMARY_EXECUTABLE
    _require(executable_path.is_file(), "EXECUTABLE_MISSING", PRIMARY_EXECUTABLE)
    executable = {
        "directory_entry": executable_path.name,
        "size": executable_path.stat().st_size,
        "sha256": sha256_file(executable_path),
    }

    bin_path = directory / bins[0]["directory_entry"]
    with bin_path.open("rb") as handle:
        volume = read_volume_descriptor(handle)
        system_cnf_entry = find_entry(handle, volume, "SYSTEM.CNF")
        _require(system_cnf_entry is not None, "SYSTEM_CNF_MISSING", "SYSTEM.CNF")
        system_cnf_text = read_extent(handle, system_cnf_entry).decode("ascii", "replace")
        fields = parse_system_cnf(system_cnf_text)
        target = boot_target(fields)
        boot_entry = find_entry(handle, volume, target)
        _require(boot_entry is not None, "BOOT_TARGET_MISSING", target)
        boot_sha256 = extent_sha256(handle, boot_entry)

    _require(
        boot_sha256 == executable["sha256"],
        "BOOT_TARGET_MISMATCH",
        f"{target} extent differs from {PRIMARY_EXECUTABLE}",
    )

    return {
        "fixture_version": FIXTURE_VERSION,
        "directory_entry_count": len(sorted(directory.iterdir())),
        "executable": executable,
        "disc": {
            "cue": cue.to_document(),
            "bins": bins,
            "volume": volume,
        },
        "system_cnf": {
            "directory_entry": system_cnf_entry.name,
            "extent_lba": system_cnf_entry.extent_lba,
            "size": system_cnf_entry.size,
            "fields": fields,
            "boot_target": target,
            "boot_extent_lba": boot_entry.extent_lba,
            "boot_extent_size": boot_entry.size,
            "boot_extent_sha256": boot_sha256,
            "matches_primary_executable": True,
        },
    }


def identity_digest(document: dict[str, Any]) -> str:
    import json

    return hashlib.sha256(json.dumps(document, sort_keys=True).encode("utf-8")).hexdigest()
