#!/usr/bin/env python3
"""OpenRecomp Phase-3 deterministic package V1 (P3-10).

Builds a byte-reproducible package of the audited Phase-3 path:

* the Phase-3 control plane and source manifest;
* the Phase-3 source modules and gates;
* the OpenRecomp-authored CoreMark port files;
* the generated host program/support C emitted by P3-07;
* the tracked Phase-3 evidence (control-plane, decode, static-data, structure,
  emission, native execution and reference-equivalence records).

The archive is deterministic: entries are written in sorted order with a fixed
timestamp and stored without compression, and the embedded manifest records
each member's sha256 and size plus a package fingerprint computed over the
canonical manifest with the fingerprint field neutralized.

Content policy (fail closed): no compiled artifacts or guest binaries, no host
absolute paths, no timestamps or process identities, no private-key markers and
no duplicate or unsafe archive names.

This module is OpenRecomp-original, standard-library only, and contains no
console assets, proprietary data or copied tables.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from typing import Any, Iterable

PACKAGE_VERSION = "1.0.0"
MANIFEST_NAME = "PHASE3_PACKAGE_MANIFEST.json"
FIXED_DATE = (1980, 1, 1, 0, 0, 0)
COMPRESSION = zipfile.ZIP_STORED

FORBIDDEN_SUFFIXES = frozenset({
    ".exe", ".obj", ".o", ".a", ".lib", ".dll", ".so", ".dylib", ".elf",
    ".bin", ".nes", ".fds", ".unf", ".gb", ".gbc", ".gba", ".sms", ".z64",
    ".n64", ".iso", ".img", ".rom", ".wad", ".pk3", ".pkg",
})

HOST_PATH_PATTERN = re.compile(
    rb"(?<![A-Za-z0-9])[A-Za-z]:[\\/]"
    rb"|file://|/tmp/|/var/tmp/|/home/|/Users/"
)
TIMESTAMP_PATTERN = re.compile(
    rb"\b(?:19|20)\d\d[-/]\d\d[-/]\d\d\b|\bT\d\d:\d\d:\d\d(?:\.\d+)?Z?\b"
    rb"|\b\d\d:\d\d:\d\d\b"
)
IDENTITY_PATTERN = re.compile(
    rb"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
SENSITIVE_MARKERS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"access_token[ \t]*[:=]", re.I),
    re.compile(rb"refresh_token[ \t]*[:=]", re.I),
)


class PackageError(ValueError):
    """Fail-closed package rejection with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class PackageEntry:
    name: str
    content: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True)
class PackageResult:
    archive: bytes
    manifest: dict[str, Any]
    fingerprint: str
    entry_count: int
    total_bytes: int


def _safe_name(name: str) -> None:
    if not name or name.startswith("/") or "\\" in name:
        raise PackageError("UNSAFE_ARCHIVE_NAME", name)
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise PackageError("UNSAFE_ARCHIVE_NAME", name)


def content_policy_findings(entries: Iterable[PackageEntry]) -> list[str]:
    """Fail-closed content audit.

    Every entry is checked for safe archive names, duplicate names, forbidden
    compiled/guest-artifact suffixes and sensitive markers. Timestamps and UUIDs
    are rejected everywhere. The host-path scan applies to evidence entries:
    source and gate files legitimately contain escape sequences and regular
    expression literals that a naive path scan would misread.
    """
    findings: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        _safe_name(entry.name)
        if entry.name in seen:
            findings.append(f"{entry.name}:duplicate-entry")
        seen.add(entry.name)
        lowered = entry.name.lower()
        for suffix in FORBIDDEN_SUFFIXES:
            if lowered.endswith(suffix):
                findings.append(f"{entry.name}:forbidden-suffix")
                break
        if "/evidence/" in entry.name and HOST_PATH_PATTERN.search(entry.content):
            findings.append(f"{entry.name}:host-path")
        if TIMESTAMP_PATTERN.search(entry.content):
            findings.append(f"{entry.name}:timestamp")
        if IDENTITY_PATTERN.search(entry.content):
            findings.append(f"{entry.name}:uuid")
        for marker in SENSITIVE_MARKERS:
            if marker.search(entry.content):
                findings.append(f"{entry.name}:sensitive-marker")
                break
    return findings


def _manifest(entries: tuple[PackageEntry, ...], extra: dict[str, Any]) -> dict[str, Any]:
    manifest = {
        "package_version": PACKAGE_VERSION,
        "manifest_name": MANIFEST_NAME,
        "entry_count": len(entries),
        "total_bytes": sum(len(entry.content) for entry in entries),
        "entries": [
            {"name": entry.name, "size": len(entry.content), "sha256": entry.sha256}
            for entry in entries
        ],
        "extra": extra,
        "package_fingerprint": None,
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("ascii")
    manifest["package_fingerprint"] = hashlib.sha256(canonical).hexdigest()
    return manifest


def build_package(entries: Iterable[PackageEntry],
                  extra: dict[str, Any] | None = None) -> PackageResult:
    """Build the deterministic archive (fail closed on policy violations)."""
    ordered = tuple(sorted(entries, key=lambda item: item.name))
    if not ordered:
        raise PackageError("EMPTY_PACKAGE")
    findings = content_policy_findings(ordered)
    if findings:
        raise PackageError("CONTENT_POLICY_VIOLATION", ";".join(findings[:8]))
    manifest = _manifest(ordered, dict(extra or {}))
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    members = [(entry.name, entry.content) for entry in ordered]
    members.append((MANIFEST_NAME, manifest_bytes))
    members.sort(key=lambda item: item[0])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=COMPRESSION) as archive:
        for name, content in members:
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)
    archive_bytes = buffer.getvalue()
    return PackageResult(
        archive=archive_bytes,
        manifest=manifest,
        fingerprint=manifest["package_fingerprint"],
        entry_count=len(ordered),
        total_bytes=manifest["total_bytes"],
    )


def read_package(archive_bytes: bytes) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Read a deterministic package back and return (manifest, members)."""
    members: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
        names = archive.namelist()
        if names != sorted(names):
            raise PackageError("ARCHIVE_ORDER", "members are not sorted")
        for name in names:
            info = archive.getinfo(name)
            if info.date_time != FIXED_DATE:
                raise PackageError("ARCHIVE_TIMESTAMP", name)
            members[name] = archive.read(name)
    manifest = json.loads(members[MANIFEST_NAME].decode("utf-8"))
    return manifest, members


def verify_package(archive_bytes: bytes) -> dict[str, Any]:
    """Verify manifest consistency and member hashes of a package."""
    manifest, members = read_package(archive_bytes)
    listed = {item["name"]: item for item in manifest["entries"]}
    if set(listed) | {MANIFEST_NAME} != set(members):
        raise PackageError("MANIFEST_MEMBERSHIP")
    for name, item in listed.items():
        content = members[name]
        if len(content) != item["size"]:
            raise PackageError("MANIFEST_SIZE", name)
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise PackageError("MANIFEST_HASH", name)
    check = dict(manifest)
    check["package_fingerprint"] = None
    canonical = json.dumps(check, sort_keys=True, separators=(",", ":")).encode("ascii")
    if hashlib.sha256(canonical).hexdigest() != manifest["package_fingerprint"]:
        raise PackageError("MANIFEST_FINGERPRINT")
    return manifest


__all__ = [
    "COMPRESSION",
    "FIXED_DATE",
    "MANIFEST_NAME",
    "PACKAGE_VERSION",
    "PackageEntry",
    "PackageError",
    "PackageResult",
    "build_package",
    "content_policy_findings",
    "read_package",
    "verify_package",
]
