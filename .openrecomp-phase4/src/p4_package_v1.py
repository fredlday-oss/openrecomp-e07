#!/usr/bin/env python3
"""OpenRecomp Phase-4 reproducible package builder (P4-10).

Builds a deterministic ZIP package of the audited Phase-4 tree:

* control plane, Phase-4 sources, contracts, ports, fixture, gates, generated
  host translation sources and the tracked stage evidence `P4-00` .. `P4-09`;
* a fail-closed content policy: text only (UTF-8, LF), no host paths,
  timestamps, UUIDs, sensitive markers or compiled/guest binaries;
* deterministic archive metadata (sorted members, fixed timestamps,
  fixed compression) so two builds from the same tree state are
  byte-identical;
* a member manifest with per-file sizes and sha256 plus a canonical package
  fingerprint;
* the package manifest is excluded from its own member set (no circular
  hashing), and the package itself is excluded from the package.

The packaging is deliberately reproducibility-bounded: external toolchains
(the zig distribution, the LLVM/clang-cl host toolchain) are not shipped;
they are pinned by recorded identity in the stage evidence and rebuilt from
source distribution archives.
"""
from __future__ import annotations

import hashlib
import io
import json
import pathlib
import re
import zipfile
from dataclasses import dataclass
from typing import Any

PACKAGE_VERSION = "1.0.0"
PACKAGE_NAME = "phase4_package_v1.zip"
MEMBERS_ROOT = "phase4_package_v1"
MANIFEST_NAME = "P4_PACKAGE_MANIFEST.json"
FIXED_DATE_TIME = (1980, 1, 1, 0, 0, 0)

BINARY_SUFFIXES = frozenset({
    ".exe", ".obj", ".o", ".elf", ".so", ".dll", ".zip", ".7z", ".tar", ".gz",
    ".png", ".jpg", ".jpeg", ".gif", ".wav", ".mp3", ".bin", ".pyc",
})
TEXT_SUFFIXES = frozenset({
    ".md", ".py", ".c", ".h", ".s", ".S", ".ld", ".json", ".txt", ".cmd",
})
# Host-specific command records are excluded by design (they legitimately
# contain the local toolchain path); the record remains tracked in the
# repository and its identities are pinned by the P4-07 stage evidence.
HOST_SPECIFIC_EXCLUSIONS = frozenset({
    f"{MEMBERS_ROOT}/evidence/P4-07/build.json",
})
# Gate sources and the package builder legitimately contain the policy's own
# detection patterns (regular-expression needles and negative-test literals)
# and are therefore exempt from the metadata and sensitive-marker scans only;
# they are still UTF-8/LF checked and hashed.  All product members (control
# plane, runtime sources, contracts, ports, fixture, generated sources and
# stage evidence) remain fully scanned.
POLICY_EXEMPT_PREFIXES = (f"{MEMBERS_ROOT}/gates/",)
POLICY_EXEMPT_MEMBERS = frozenset({
    f"{MEMBERS_ROOT}/src/p4_package_v1.py",
})


def is_policy_exempt(name: str) -> bool:
    return name in POLICY_EXEMPT_MEMBERS or name.startswith(POLICY_EXEMPT_PREFIXES)
HOST_PATH_PATTERN = re.compile(
    rb"(?<![A-Za-z0-9])[A-Za-z]:[\\/][A-Za-z0-9_.$~]"
    rb"|\\\\[A-Za-z0-9_$][A-Za-z0-9_.$-]*\\\\[A-Za-z0-9_$]"
    rb"|file://|/tmp/|/var/tmp/|/home/|/Users/|\\Temp\\|\\AppData\\|\\Users\\"
)
TIMESTAMP_PATTERN = re.compile(
    rb"\b(?:19|20)\d\d[-/]\d\d[-/]\d\d\b|T\d\d:\d\d:\d\d(?:\.\d+)?Z?\b"
)
IDENTITY_PATTERN = re.compile(
    rb"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
SENSITIVE_PATTERNS = (
    re.compile(rb"AUTH_PASSWORD[ \t]*=", re.I),
    re.compile(rb"access_token[ \t]*[:=]", re.I),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


class PackageError(ValueError):
    """Raised when the package cannot be built or violates its policy."""


@dataclass(frozen=True)
class Member:
    name: str
    data: bytes
    sha256: str
    size: int

    def to_document(self) -> dict[str, Any]:
        return {"name": self.name, "sha256": self.sha256, "size": self.size}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PackageError(message)


def _is_text(path: str) -> bool:
    suffix = pathlib.PurePosixPath(path).suffix
    if suffix in BINARY_SUFFIXES:
        return False
    return suffix in TEXT_SUFFIXES or suffix == ""


def collect_members(root: pathlib.Path) -> list[Member]:
    """Collect the audited Phase-4 member set deterministically."""
    root = root.resolve()
    control = root / ".openrecomp-phase4"
    paths: list[tuple[str, pathlib.Path]] = []
    for name in ("CONTROL_POLICY.md", "EVIDENCE_SCHEMA.md", "HANDOFF.md",
                 "SCOPE.md", "SOURCE_SHA256SUMS.txt", "STAGE_QUEUE.md", "STATE.md"):
        path = control / name
        if path.is_file():
            paths.append((f"{MEMBERS_ROOT}/control/{name}", path))
    for directory in ("src", "contracts", "ports", "fixture"):
        base = control / directory
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                relative = path.relative_to(base).as_posix()
                paths.append((f"{MEMBERS_ROOT}/{directory}/{relative}", path))
    evidence = control / "evidence"
    if evidence.is_dir():
        for path in sorted(evidence.rglob("*")):
            if path.is_file():
                relative = path.relative_to(evidence.parent).as_posix()
                paths.append((f"{MEMBERS_ROOT}/{relative}", path))
    for gate in sorted((root / "tools").glob("test_phase4_*.py")):
        paths.append((f"{MEMBERS_ROOT}/gates/{gate.name}", gate))
    generated = control / "evidence" / "P4-10" / "generated"
    if generated.is_dir():
        for path in sorted(generated.rglob("*")):
            if path.is_file():
                relative = path.relative_to(generated.parent).as_posix()
                paths.append((f"{MEMBERS_ROOT}/{relative}", path))

    members: list[Member] = []
    seen: set[str] = set()
    for name, path in sorted(paths, key=lambda item: item[0]):
        _require(name not in seen, f"duplicate package member {name}")
        seen.add(name)
        if name in HOST_SPECIFIC_EXCLUSIONS:
            continue
        data = path.read_bytes()
        if not _is_text(name):
            raise PackageError(f"binary or unsupported member rejected: {name}")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PackageError(f"member is not UTF-8: {name}") from exc
        _require("\r" not in text, f"member is not LF-normalized: {name}")
        if not is_policy_exempt(name):
            for pattern in (HOST_PATH_PATTERN, TIMESTAMP_PATTERN, IDENTITY_PATTERN):
                if pattern.search(data):
                    raise PackageError(f"member contains forbidden metadata: {name}")
            for pattern in SENSITIVE_PATTERNS:
                if pattern.search(data):
                    raise PackageError(f"member contains a sensitive marker: {name}")
        members.append(Member(name=name, data=data,
                              sha256=hashlib.sha256(data).hexdigest(),
                              size=len(data)))
    _require(members, "no package members collected")
    return members


def member_manifest(members: list[Member]) -> dict[str, Any]:
    document = {
        "package": MEMBERS_ROOT,
        "package_version": PACKAGE_VERSION,
        "member_count": len(members),
        "members": [member.to_document() for member in members],
    }
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    document["fingerprint"] = hashlib.sha256(payload).hexdigest()
    return document


def build_package(root: pathlib.Path) -> tuple[bytes, dict[str, Any]]:
    members = collect_members(root)
    manifest = member_manifest(members)
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_name = f"{MEMBERS_ROOT}/{MANIFEST_NAME}"
    entries = [(member.name, member.data) for member in members]
    entries.append((manifest_name, manifest_bytes))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for name, data in sorted(entries, key=lambda item: item[0]):
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE_TIME)
            info.external_attr = 0o644 << 16
            info.create_system = 0
            archive.writestr(info, data)
    return buffer.getvalue(), manifest


def verify_package(data: bytes) -> dict[str, Any]:
    """Verify archive determinism properties and member hashes."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        _require(names == sorted(names), "archive members are not sorted")
        for info in archive.infolist():
            _require(info.date_time == FIXED_DATE_TIME, "non-deterministic timestamp")
            _require(info.compress_type in (zipfile.ZIP_DEFLATED, zipfile.ZIP_STORED),
                     "unexpected compression")
        manifest_name = f"{MEMBERS_ROOT}/{MANIFEST_NAME}"
        _require(manifest_name in names, "package manifest missing")
        manifest = json.loads(archive.read(manifest_name).decode("utf-8"))
        _require(manifest["member_count"] == len(names) - 1, "member count mismatch")
        for member in manifest["members"]:
            payload = archive.read(member["name"])
            _require(hashlib.sha256(payload).hexdigest() == member["sha256"],
                     f"member hash mismatch: {member['name']}")
            _require(len(payload) == member["size"], f"member size mismatch: {member['name']}")
        document = {
            "member_count": manifest["member_count"],
            "fingerprint": manifest["fingerprint"],
            "members": [member["name"] for member in manifest["members"]],
            "archive_members": list(names),
        }
        return document


def package_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
