"""OpenRecomp deterministic release/package assembly V1 (P2-50).

`OpenRecomp Phase 2` stage P2-50 deliverable. This module turns reproducible
P2-09 build outputs into a byte-deterministic distributable package with
explicit provenance:

    verified build outputs (generated source, runtime support source,
    build manifest, executable)
        -> canonical release manifest (sorted keys, no host metadata)
        -> deterministic archive (sorted names, fixed ZIP metadata)
        -> content-policy validation -> SHA-256 release identity

Core rules:

* **deterministic container**: entries are ordered by ascending safe name and
  stored without compression with fixed ZIP metadata (`create_system`,
  `external_attr`, a fixed 1980-01-01 timestamp, no extra fields, no
  directory entries). Two assemblies from byte-identical inputs produce
  byte-identical archives, and a package is only accepted when its archive can
  be re-derived byte-for-byte from the manifest-declared payload.
* **explicit provenance**: the release manifest records the fixture identity
  and fixture input SHA-256, the build manifest SHA-256, the generated-source
  and executable SHA-256 values, the runtime ABI version, the toolchain
  identity and a canonical source-state list (repo-relative file plus SHA-256)
  so an artifact can be traced back to the exact pipeline source state that
  produced it. Provenance fields must agree with the packaged artifacts.
* **content policy**: only allow-listed file categories/extensions may enter a
  package. Absolute paths (Windows drive, UNC, POSIX temp/home), temporary or
  cache markers, private-key material, credential patterns and console image
  magics fail closed. Caches and unrelated build intermediates never match the
  allow-list.
* **fail closed**: unsafe or duplicate entry names, reserved manifest names,
  category/extension mismatches, empty packages, provenance/artifact hash
  disagreements, malformed manifests, forbidden keys, tampered archives,
  reordered entries and non-canonical metadata all raise `ReleasePackageError`.

This module performs no compilation, no guest execution and no equivalence
checking; it packages and verifies already-built P2-09 outputs.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from openrecomp import runtime_abi as _runtime_abi

RELEASE_PACKAGE_SCHEMA = "openrecomp-release-package-v1"
RELEASE_PACKAGE_VERSION = "1.0.0"
RELEASE_PACKAGE_STAGE = "P2-50"
RELEASE_ARCHIVE_FORMAT = "zip"
RELEASE_ARCHIVE_COMPRESSION = "STORED"
RELEASE_ARCHIVE_DATE_TIME = (1980, 1, 1, 0, 0, 0)
RELEASE_ARCHIVE_CREATE_SYSTEM = 0
RELEASE_ARCHIVE_EXTERNAL_ATTR = 0o600 << 16
RELEASE_ARCHIVE_ENTRY_ORDER = "sorted-ascending-name"
RELEASE_MANIFEST_NAME = "release_manifest.json"
RELEASE_CHECKSUMS_NAME = "SHA256SUMS.txt"

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_RELATIVE_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HOST_ABSOLUTE_PATH = re.compile(
    rb"(?<![A-Za-z0-9])[A-Za-z]:[\\/]"
    rb"|(?<![\\])\\\\[A-Za-z0-9_.$-]"
    rb"|file://|/tmp/|/var/tmp/|/home/|/Users/|\\Temp\\|\\AppData\\|\\Users\\"
)
_PRIVATE_KEY = re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_CREDENTIAL = re.compile(rb"(?i)(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*\S")
_ACCESS_KEY = re.compile(rb"AKIA[0-9A-Z]{16}")

_FORBIDDEN_KEYS = frozenset(
    {
        "timestamp",
        "time",
        "datetime",
        "date",
        "mtime",
        "pid",
        "process_id",
        "uuid",
        "guid",
        "hostname",
        "host",
        "username",
        "user",
        "cwd",
        "workdir",
        "working_directory",
        "temp",
        "tmp",
        "tempdir",
        "absolute_path",
        "path",
        "object_id",
        "python_id",
    }
)

_FORBIDDEN_NAME_TOKENS = frozenset(
    {
        "bios",
        "firmware",
        "rom",
        "cartridge",
        "sram",
        "save",
        "savestate",
        "key",
        "keys",
        "secret",
        "secrets",
        "credential",
        "credentials",
        "password",
        "passwd",
        "private",
        "token",
    }
)

_FORBIDDEN_MAGIC = (
    (b"NES\x1a", "iNES container magic"),
    (b"FDS\x1a", "FDS container magic"),
    (b"UNIF", "UNIF container magic"),
)

_MAX_ENTRY_BYTES = 64 * 1024 * 1024
_MAX_RELEASE_MANIFEST_BYTES = 4 * 1024 * 1024


class ReleasePackageError(ValueError):
    """Raised when a deterministic release-package contract is violated."""


class PackageCategory(str, Enum):
    """Allow-listed package payload categories."""

    GENERATED_SOURCE = "GENERATED_SOURCE"
    RUNTIME_SUPPORT_SOURCE = "RUNTIME_SUPPORT_SOURCE"
    BUILD_MANIFEST = "BUILD_MANIFEST"
    EXECUTABLE = "EXECUTABLE"


_ALLOWED_EXTENSIONS = {
    PackageCategory.GENERATED_SOURCE: (".c", ".h"),
    PackageCategory.RUNTIME_SUPPORT_SOURCE: (".c", ".h"),
    PackageCategory.BUILD_MANIFEST: (".json",),
    PackageCategory.EXECUTABLE: (".exe", ".elf"),
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_sha256(value: Any, where: str) -> str:
    if not isinstance(value, str) or not _SHA256.match(value):
        raise ReleasePackageError(f"{where}: {value!r} is not a lowercase sha256 digest")
    return value


def _require_non_empty(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReleasePackageError(f"{where} must be a non-empty string")
    return value


def _require_safe_name(value: Any, where: str) -> str:
    if not isinstance(value, str) or not _SAFE_NAME.match(value):
        raise ReleasePackageError(f"{where}: {value!r} is not a safe relative entry name")
    if ".." in value or "/" in value or "\\" in value or ":" in value:
        raise ReleasePackageError(f"{where}: {value!r} must not contain path components")
    return value


def _require_relative_path(value: Any, where: str) -> str:
    if not isinstance(value, str) or not _RELATIVE_PATH.match(value):
        raise ReleasePackageError(f"{where}: {value!r} is not a safe repo-relative path")
    if ".." in value or value.startswith("/") or "\\" in value or ":" in value:
        raise ReleasePackageError(f"{where}: {value!r} must be a relative posix path")
    return value


def _require_category(name: str, category: Any, where: str) -> PackageCategory:
    if not isinstance(category, PackageCategory):
        raise ReleasePackageError(f"{where}.category must be a PackageCategory")
    lowered = name.lower()
    if not lowered.endswith(_ALLOWED_EXTENSIONS[category]):
        allowed = ", ".join(_ALLOWED_EXTENSIONS[category])
        raise ReleasePackageError(
            f"{where}: {name!r} is not allowed for {category.value} (expected extension {allowed})"
        )
    return category


def _reject_forbidden_keys(value: Any, where: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in _FORBIDDEN_KEYS:
                raise ReleasePackageError(f"{where}: nondeterministic field {key!r} is not permitted")
            _reject_forbidden_keys(item, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_forbidden_keys(item, f"{where}[{index}]")


def _canonical_json(document: Any) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _tokenized(name: str) -> tuple[str, ...]:
    return tuple(token for token in re.split(r"[^a-z0-9]+", name.lower()) if token)


# --- payload entries --------------------------------------------------------
@dataclass(frozen=True)
class PackageEntry:
    """One payload entry that is allowed to enter a release package."""

    name: str
    category: PackageCategory
    content: bytes

    def __post_init__(self) -> None:
        _require_safe_name(self.name, "package entry.name")
        if self.name in (RELEASE_MANIFEST_NAME, RELEASE_CHECKSUMS_NAME):
            raise ReleasePackageError(f"package entry.name {self.name!r} is reserved")
        _require_category(self.name, self.category, "package entry")
        if not isinstance(self.content, (bytes, bytearray)):
            raise ReleasePackageError("package entry.content must be bytes")
        content = bytes(self.content)
        if len(content) > _MAX_ENTRY_BYTES:
            raise ReleasePackageError(f"package entry {self.name!r} exceeds the size limit")
        object.__setattr__(self, "content", content)

    def sha256(self) -> str:
        return _sha256_bytes(self.content)

    def byte_length(self) -> int:
        return len(self.content)

    def to_document(self) -> dict[str, Any]:
        return {
            "byte_length": self.byte_length(),
            "category": self.category.value,
            "name": self.name,
            "sha256": self.sha256(),
        }


# --- provenance -------------------------------------------------------------
@dataclass(frozen=True)
class SourceStateEntry:
    """One pipeline source file (repo-relative) and its SHA-256."""

    file: str
    sha256: str

    def __post_init__(self) -> None:
        _require_relative_path(self.file, "source state.file")
        _require_sha256(self.sha256, "source state.sha256")

    def to_document(self) -> dict[str, Any]:
        return {"file": self.file, "sha256": self.sha256}


def source_state_fingerprint(entries: Sequence[SourceStateEntry]) -> str:
    ordered = sorted(entries, key=lambda item: item.file)
    names = [item.file for item in ordered]
    if len(set(names)) != len(names):
        raise ReleasePackageError("source state must not repeat a file")
    document = []
    for item in ordered:
        _require_sha256(item.sha256, "source state")
        document.append(item.to_document())
    return _sha256_bytes((_canonical_json(document) + "\n").encode("utf-8"))


def collect_source_state(root: str | Path, files: Sequence[str]) -> tuple[SourceStateEntry, ...]:
    """Hash the given repo-relative pipeline files under `root`."""
    base = Path(root)
    entries: list[SourceStateEntry] = []
    for file in files:
        relative = _require_relative_path(file, "source state input")
        path = base / relative
        if not path.is_file():
            raise ReleasePackageError(f"source state file {relative!r} is missing under the source root")
        entries.append(SourceStateEntry(relative, _sha256_bytes(path.read_bytes())))
    return tuple(sorted(entries, key=lambda item: item.file))


def verify_source_state(root: str | Path, entries: Sequence[SourceStateEntry]) -> dict[str, Any]:
    """Fail closed if on-disk pipeline sources disagree with recorded hashes."""
    base = Path(root)
    checked: list[dict[str, str]] = []
    for item in sorted(entries, key=lambda entry: entry.file):
        path = base / item.file
        if not path.is_file():
            raise ReleasePackageError(f"recorded source state file {item.file!r} is missing")
        observed = _sha256_bytes(path.read_bytes())
        if observed != item.sha256:
            raise ReleasePackageError(
                f"source state mismatch for {item.file!r}: recorded {item.sha256}, observed {observed}"
            )
        checked.append({"file": item.file, "sha256": observed})
    return {
        "checked": checked,
        "file_count": len(checked),
        "fingerprint": source_state_fingerprint(entries),
    }


@dataclass(frozen=True)
class ReleaseProvenance:
    """Explicit artifact -> source-state provenance for one release package."""

    fixture_id: str
    fixture_kind: str
    fixture_input_sha256: str
    build_manifest_sha256: str
    executable_sha256: str
    runtime_abi_name: str
    runtime_abi_version: str
    toolchain: Mapping[str, Any]
    source_state: tuple[SourceStateEntry, ...]

    def __post_init__(self) -> None:
        _require_non_empty(self.fixture_id, "provenance.fixture_id")
        _require_non_empty(self.fixture_kind, "provenance.fixture_kind")
        _require_sha256(self.fixture_input_sha256, "provenance.fixture_input_sha256")
        _require_sha256(self.build_manifest_sha256, "provenance.build_manifest_sha256")
        _require_sha256(self.executable_sha256, "provenance.executable_sha256")
        _require_non_empty(self.runtime_abi_name, "provenance.runtime_abi_name")
        _require_non_empty(self.runtime_abi_version, "provenance.runtime_abi_version")
        if self.runtime_abi_version != _runtime_abi.RUNTIME_ABI_VERSION:
            raise ReleasePackageError(
                f"provenance runtime ABI {self.runtime_abi_version!r} does not match "
                f"{_runtime_abi.RUNTIME_ABI_VERSION!r} (ABI_VERSION_MISMATCH)"
            )
        if not isinstance(self.toolchain, Mapping) or not self.toolchain:
            raise ReleasePackageError("provenance.toolchain must be a non-empty mapping")
        if not isinstance(self.source_state, tuple) or not self.source_state:
            raise ReleasePackageError("provenance.source_state must be a non-empty tuple")
        for item in self.source_state:
            if not isinstance(item, SourceStateEntry):
                raise ReleasePackageError("provenance.source_state must contain SourceStateEntry values")
        source_state_fingerprint(self.source_state)

    def fingerprint(self) -> str:
        return source_state_fingerprint(self.source_state)

    def to_document(self) -> dict[str, Any]:
        return {
            "build_manifest_sha256": self.build_manifest_sha256,
            "executable_sha256": self.executable_sha256,
            "fixture_id": self.fixture_id,
            "fixture_input_sha256": self.fixture_input_sha256,
            "fixture_kind": self.fixture_kind,
            "runtime_abi": {"name": self.runtime_abi_name, "version": self.runtime_abi_version},
            "source_state": [item.to_document() for item in sorted(self.source_state, key=lambda entry: entry.file)],
            "source_state_fingerprint": self.fingerprint(),
            "toolchain": dict(self.toolchain),
        }


# --- content policy ---------------------------------------------------------
def content_policy_findings(entries: Sequence[PackageEntry]) -> list[dict[str, str]]:
    """Return deterministic findings for any entry that may not enter a package."""
    findings: list[dict[str, str]] = []
    for entry in entries:
        tokens = set(_tokenized(entry.name))
        for token in sorted(tokens & _FORBIDDEN_NAME_TOKENS):
            findings.append({"name": entry.name, "kind": "forbidden_name_token", "detail": token})
        stripped = entry.name.strip()
        if stripped.startswith(".") or entry.name != stripped:
            findings.append({"name": entry.name, "kind": "hidden_or_padded_name", "detail": entry.name})
        data = entry.content
        for magic, label in _FORBIDDEN_MAGIC:
            if magic in data:
                findings.append({"name": entry.name, "kind": "forbidden_container_magic", "detail": label})
        if _HOST_ABSOLUTE_PATH.search(data):
            findings.append({"name": entry.name, "kind": "host_absolute_or_temp_path", "detail": "path-like needle"})
        if _PRIVATE_KEY.search(data):
            findings.append({"name": entry.name, "kind": "private_key_material", "detail": "PEM private key"})
        if _CREDENTIAL.search(data):
            findings.append({"name": entry.name, "kind": "credential_pattern", "detail": "key/secret assignment"})
        if _ACCESS_KEY.search(data):
            findings.append({"name": entry.name, "kind": "credential_pattern", "detail": "access-key id"})
    return findings


def _scan_needles(package: "ReleasePackage", needles: Sequence[bytes]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for needle in needles:
        if not isinstance(needle, (bytes, bytearray)) or not needle:
            raise ReleasePackageError("forbidden needles must be non-empty bytes")
        for name, data in package.payload_items():
            if bytes(needle) in data:
                findings.append({"name": name, "kind": "host_needle", "detail": bytes(needle).decode("utf-8", "replace")})
        if bytes(needle) in package.archive:
            findings.append({"name": "<archive>", "kind": "host_needle", "detail": bytes(needle).decode("utf-8", "replace")})
    return findings


# --- canonical archive ------------------------------------------------------
@dataclass(frozen=True)
class ArchiveEntryInfo:
    """Metadata observed in a canonical release archive entry."""

    name: str
    byte_length: int
    sha256: str
    date_time: tuple[int, int, int, int, int, int]
    compression: int
    create_system: int
    external_attr: int
    flag_bits: int
    extra: bytes
    comment: bytes
    is_dir: bool

    def to_document(self) -> dict[str, Any]:
        return {
            "byte_length": self.byte_length,
            "comment": self.comment.decode("utf-8", "replace"),
            "compression": self.compression,
            "create_system": self.create_system,
            "date_time": list(self.date_time),
            "external_attr": self.external_attr,
            "extra": self.extra.decode("utf-8", "replace"),
            "flag_bits": self.flag_bits,
            "is_dir": self.is_dir,
            "name": self.name,
            "sha256": self.sha256,
        }


def build_canonical_archive(files: Sequence[tuple[str, bytes]]) -> bytes:
    """Build the byte-deterministic store-only ZIP container for `files`."""
    ordered = sorted(
        ((_require_safe_name(name, "archive entry.name"), bytes(data)) for name, data in files),
        key=lambda item: item[0],
    )
    names = [name for name, _ in ordered]
    if len(set(names)) != len(names):
        raise ReleasePackageError("archive entry names must be unique")
    if not ordered:
        raise ReleasePackageError("a release archive requires at least one entry")
    if sum(len(data) for _, data in ordered) > _MAX_ENTRY_BYTES * 8:
        raise ReleasePackageError("release archive payload exceeds the size limit")
    buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
            for name, data in ordered:
                info = zipfile.ZipInfo(name, date_time=RELEASE_ARCHIVE_DATE_TIME)
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = RELEASE_ARCHIVE_CREATE_SYSTEM
                info.external_attr = RELEASE_ARCHIVE_EXTERNAL_ATTR
                info.internal_attr = 0
                info.comment = b""
                info.extra = b""
                archive.writestr(info, data)
    except (zipfile.LargeZipFile, ValueError) as exc:
        raise ReleasePackageError(f"unable to build a canonical release archive: {exc}") from exc
    return buffer.getvalue()


def read_canonical_archive(data: bytes) -> tuple[tuple[ArchiveEntryInfo, bytes], ...]:
    """Parse an archive and return (info, content) pairs in stored order."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ReleasePackageError("archive data must be non-empty bytes")
    try:
        with zipfile.ZipFile(io.BytesIO(bytes(data))) as archive:
            entries: list[tuple[ArchiveEntryInfo, bytes]] = []
            seen: set[str] = set()
            for info in archive.infolist():
                if info.filename in seen:
                    raise ReleasePackageError(f"archive repeats entry {info.filename!r}")
                seen.add(info.filename)
                content = archive.read(info)
                entries.append(
                    (
                        ArchiveEntryInfo(
                            name=info.filename,
                            byte_length=len(content),
                            sha256=_sha256_bytes(content),
                            date_time=tuple(info.date_time),
                            compression=info.compress_type,
                            create_system=info.create_system,
                            external_attr=info.external_attr,
                            flag_bits=info.flag_bits,
                            extra=bytes(info.extra),
                            comment=bytes(info.comment),
                            is_dir=info.is_dir(),
                        ),
                        content,
                    )
                )
            return tuple(entries)
    except (zipfile.BadZipFile, ValueError) as exc:
        raise ReleasePackageError(f"release archive is not a valid zip container: {exc}") from exc


# --- release manifest -------------------------------------------------------
def validate_release_manifest(document: Any) -> dict[str, Any]:
    """Fail closed unless `document` is a canonical release manifest object."""
    if not isinstance(document, Mapping):
        raise ReleasePackageError("release manifest must be a JSON object")
    _reject_forbidden_keys(document, "release manifest")
    expected = {
        "archive",
        "entries",
        "fixture_id",
        "manifest_version",
        "provenance",
        "runtime_abi",
        "schema",
        "stage",
    }
    unknown = sorted(set(document) - expected)
    if unknown:
        raise ReleasePackageError(f"release manifest has unsupported key(s): {', '.join(unknown)}")
    missing = sorted(expected - set(document))
    if missing:
        raise ReleasePackageError(f"release manifest is missing key(s): {', '.join(missing)}")
    if document["schema"] != RELEASE_PACKAGE_SCHEMA:
        raise ReleasePackageError(f"unsupported release manifest schema {document['schema']!r}")
    if document["manifest_version"] != RELEASE_PACKAGE_VERSION:
        raise ReleasePackageError(f"unsupported release manifest version {document['manifest_version']!r}")
    if document["stage"] != RELEASE_PACKAGE_STAGE:
        raise ReleasePackageError(f"unsupported release manifest stage {document['stage']!r}")
    _require_non_empty(document["fixture_id"], "release manifest.fixture_id")
    abi = document["runtime_abi"]
    if not isinstance(abi, Mapping) or set(abi) != {"name", "version"}:
        raise ReleasePackageError("release manifest.runtime_abi is malformed")
    _require_non_empty(abi["name"], "release manifest.runtime_abi.name")
    _require_non_empty(abi["version"], "release manifest.runtime_abi.version")
    archive = document["archive"]
    if not isinstance(archive, Mapping) or set(archive) != {"compression", "entry_order", "format", "metadata"}:
        raise ReleasePackageError("release manifest.archive is malformed")
    if (
        archive["format"] != RELEASE_ARCHIVE_FORMAT
        or archive["compression"] != RELEASE_ARCHIVE_COMPRESSION
        or archive["entry_order"] != RELEASE_ARCHIVE_ENTRY_ORDER
    ):
        raise ReleasePackageError("release manifest.archive metadata is not the fixed canonical form")
    entries = document["entries"]
    if not isinstance(entries, list) or not entries:
        raise ReleasePackageError("release manifest.entries must be a non-empty list")
    names: list[str] = []
    for index, item in enumerate(entries):
        if not isinstance(item, Mapping) or set(item) != {"byte_length", "category", "name", "sha256"}:
            raise ReleasePackageError(f"release manifest.entries[{index}] is malformed")
        name = _require_safe_name(item["name"], f"release manifest.entries[{index}].name")
        try:
            category = PackageCategory(item["category"])
        except ValueError as exc:
            raise ReleasePackageError(f"release manifest.entries[{index}].category is unsupported") from exc
        _require_category(name, category, f"release manifest.entries[{index}]")
        _require_sha256(item["sha256"], f"release manifest.entries[{index}].sha256")
        byte_length = item["byte_length"]
        if isinstance(byte_length, bool) or not isinstance(byte_length, int) or byte_length < 0:
            raise ReleasePackageError(f"release manifest.entries[{index}].byte_length is invalid")
        names.append(name)
    if len(set(names)) != len(names):
        raise ReleasePackageError("release manifest entry names must be unique")
    provenance = document["provenance"]
    if not isinstance(provenance, Mapping):
        raise ReleasePackageError("release manifest.provenance must be an object")
    _reject_forbidden_keys(provenance, "release manifest.provenance")
    _require_sha256(provenance.get("build_manifest_sha256"), "provenance.build_manifest_sha256")
    _require_sha256(provenance.get("executable_sha256"), "provenance.executable_sha256")
    _require_sha256(provenance.get("fixture_input_sha256"), "provenance.fixture_input_sha256")
    _require_non_empty(provenance.get("fixture_id"), "provenance.fixture_id")
    _require_non_empty(provenance.get("fixture_kind"), "provenance.fixture_kind")
    _require_sha256(provenance.get("source_state_fingerprint"), "provenance.source_state_fingerprint")
    state = provenance.get("source_state")
    if not isinstance(state, list) or not state:
        raise ReleasePackageError("release manifest.provenance.source_state must be a non-empty list")
    paths: list[str] = []
    for index, item in enumerate(state):
        if not isinstance(item, Mapping) or set(item) != {"file", "sha256"}:
            raise ReleasePackageError(f"release manifest.provenance.source_state[{index}] is malformed")
        paths.append(_require_relative_path(item["file"], f"source_state[{index}].file"))
        _require_sha256(item["sha256"], f"source_state[{index}].sha256")
    if len(set(paths)) != len(paths):
        raise ReleasePackageError("release manifest source-state files must be unique")
    return dict(document)


# --- package ----------------------------------------------------------------
@dataclass(frozen=True)
class ReleasePackage:
    """A deterministic release package: payload plus canonical manifest files."""

    fixture_id: str
    entries: tuple[PackageEntry, ...]
    release_manifest: bytes
    checksums: bytes
    archive: bytes

    def payload_items(self) -> tuple[tuple[str, bytes], ...]:
        return tuple((entry.name, entry.content) for entry in self.entries)

    def archive_sha256(self) -> str:
        return _sha256_bytes(self.archive)

    def manifest_document(self) -> dict[str, Any]:
        if not isinstance(self.release_manifest, (bytes, bytearray)) or not self.release_manifest:
            raise ReleasePackageError("release manifest must be non-empty bytes")
        if len(self.release_manifest) > _MAX_RELEASE_MANIFEST_BYTES:
            raise ReleasePackageError("release manifest exceeds the size limit")
        try:
            document = json.loads(bytes(self.release_manifest).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ReleasePackageError(f"release manifest is not valid canonical JSON: {exc}") from exc
        validated = validate_release_manifest(document)
        if bytes(self.release_manifest) != (_canonical_json(validated) + "\n").encode("utf-8"):
            raise ReleasePackageError("release manifest is not in canonical serialized form")
        return validated

    def entry_map(self) -> dict[str, str]:
        return {entry.name: entry.sha256() for entry in self.entries}


def _checksums_file(entries: Sequence[PackageEntry], manifest_bytes: bytes) -> bytes:
    lines = [(entry.name, entry.sha256()) for entry in entries]
    lines.append((RELEASE_MANIFEST_NAME, _sha256_bytes(manifest_bytes)))
    lines.sort(key=lambda item: item[0])
    return ("\n".join(f"{digest} *{name}" for name, digest in lines) + "\n").encode("utf-8")


def _cross_check_provenance(entries: Sequence[PackageEntry], provenance: ReleaseProvenance) -> None:
    manifests = [entry for entry in entries if entry.name == "build_manifest.json"]
    if len(manifests) != 1:
        raise ReleasePackageError("a release package requires exactly one build_manifest.json payload")
    if manifests[0].sha256() != provenance.build_manifest_sha256:
        raise ReleasePackageError(
            "provenance.build_manifest_sha256 does not match the packaged build manifest"
        )
    generated = [entry for entry in entries if entry.category is PackageCategory.GENERATED_SOURCE]
    if len(generated) != 1:
        raise ReleasePackageError("a release package requires exactly one GENERATED_SOURCE payload")
    executables = [entry for entry in entries if entry.category is PackageCategory.EXECUTABLE]
    if len(executables) != 1:
        raise ReleasePackageError("a release package requires exactly one EXECUTABLE payload")
    if executables[0].sha256() != provenance.executable_sha256:
        raise ReleasePackageError("provenance.executable_sha256 does not match the packaged executable")


def assemble_release_package(
    *,
    fixture_id: str,
    provenance: ReleaseProvenance,
    entries: Sequence[PackageEntry],
) -> ReleasePackage:
    """Assemble a byte-deterministic release package from verified build outputs."""
    _require_non_empty(fixture_id, "fixture_id")
    if not isinstance(provenance, ReleaseProvenance):
        raise ReleasePackageError("assemble_release_package requires a ReleaseProvenance")
    if provenance.fixture_id != fixture_id:
        raise ReleasePackageError(
            f"provenance.fixture_id {provenance.fixture_id!r} does not match {fixture_id!r}"
        )
    if provenance.runtime_abi_version != _runtime_abi.RUNTIME_ABI_VERSION:
        raise ReleasePackageError("provenance runtime ABI version mismatch")
    ordered = tuple(sorted(entries, key=lambda entry: entry.name))
    if not ordered:
        raise ReleasePackageError("a release package requires at least one payload entry")
    names = [entry.name for entry in ordered]
    if len(set(names)) != len(names):
        raise ReleasePackageError("package entry names must be unique")
    for reserved in (RELEASE_MANIFEST_NAME, RELEASE_CHECKSUMS_NAME):
        if reserved in names:
            raise ReleasePackageError(f"package entry.name {reserved!r} is reserved")
    findings = content_policy_findings(ordered)
    if findings:
        raise ReleasePackageError(f"release package content policy violation: {findings[0]}")
    _cross_check_provenance(ordered, provenance)

    manifest_document = {
        "archive": {
            "compression": RELEASE_ARCHIVE_COMPRESSION,
            "entry_order": RELEASE_ARCHIVE_ENTRY_ORDER,
            "format": RELEASE_ARCHIVE_FORMAT,
            "metadata": "fixed-date-time-1980-01-01T00:00:00/no-extra/no-directories",
        },
        "entries": [entry.to_document() for entry in ordered],
        "fixture_id": fixture_id,
        "manifest_version": RELEASE_PACKAGE_VERSION,
        "provenance": provenance.to_document(),
        "runtime_abi": {"name": provenance.runtime_abi_name, "version": provenance.runtime_abi_version},
        "schema": RELEASE_PACKAGE_SCHEMA,
        "stage": RELEASE_PACKAGE_STAGE,
    }
    validate_release_manifest(manifest_document)
    manifest_bytes = (_canonical_json(manifest_document) + "\n").encode("utf-8")
    checksums = _checksums_file(ordered, manifest_bytes)
    archive = build_canonical_archive(
        [*((entry.name, entry.content) for entry in ordered), (RELEASE_MANIFEST_NAME, manifest_bytes), (RELEASE_CHECKSUMS_NAME, checksums)]
    )
    package = ReleasePackage(
        fixture_id=fixture_id,
        entries=ordered,
        release_manifest=manifest_bytes,
        checksums=checksums,
        archive=archive,
    )
    verify_release_package(package, expected_entries=ordered, provenance=provenance)
    return package


def verify_release_package(
    package: ReleasePackage,
    *,
    expected_entries: Sequence[PackageEntry] | None = None,
    provenance: ReleaseProvenance | None = None,
    forbidden_needles: Sequence[bytes] = (),
) -> dict[str, Any]:
    """Fail closed unless the package is canonical, self-consistent and traceable."""
    if not isinstance(package, ReleasePackage):
        raise ReleasePackageError("verify_release_package requires a ReleasePackage")
    document = package.manifest_document()
    if document["fixture_id"] != package.fixture_id:
        raise ReleasePackageError("release manifest fixture_id does not match the package")
    if provenance is not None:
        if not isinstance(provenance, ReleaseProvenance):
            raise ReleasePackageError("provenance must be a ReleaseProvenance")
        if document["provenance"] != provenance.to_document():
            raise ReleasePackageError("release manifest provenance does not match the supplied provenance")
        if document["fixture_id"] != provenance.fixture_id:
            raise ReleasePackageError("provenance fixture_id does not match the release manifest")
    declared = {entry["name"]: entry for entry in document["entries"]}
    if len(declared) != len(package.entries):
        raise ReleasePackageError("release manifest entry count does not match the package")
    if [entry["name"] for entry in document["entries"]] != sorted(declared):
        raise ReleasePackageError("release manifest entries are not in canonical sorted order")
    for entry in package.entries:
        item = declared.get(entry.name)
        if item is None:
            raise ReleasePackageError(f"payload entry {entry.name!r} is not declared in the release manifest")
        if item != entry.to_document():
            raise ReleasePackageError(f"release manifest entry {entry.name!r} does not match the payload")

    parsed = read_canonical_archive(package.archive)
    expected_names = sorted([entry.name for entry in package.entries] + [RELEASE_MANIFEST_NAME, RELEASE_CHECKSUMS_NAME])
    observed_names = [info.name for info, _ in parsed]
    if observed_names != expected_names:
        raise ReleasePackageError(
            f"archive entries are not the canonical set/order: observed {observed_names}, expected {expected_names}"
        )
    for info, content in parsed:
        if info.is_dir:
            raise ReleasePackageError(f"archive entry {info.name!r} is a directory")
        if info.date_time != RELEASE_ARCHIVE_DATE_TIME:
            raise ReleasePackageError(f"archive entry {info.name!r} has a non-fixed timestamp")
        if info.compression != zipfile.ZIP_STORED:
            raise ReleasePackageError(f"archive entry {info.name!r} is not stored uncompressed")
        if info.create_system != RELEASE_ARCHIVE_CREATE_SYSTEM or info.external_attr != RELEASE_ARCHIVE_EXTERNAL_ATTR:
            raise ReleasePackageError(f"archive entry {info.name!r} has non-fixed host metadata")
        if info.extra or info.comment or info.flag_bits:
            raise ReleasePackageError(f"archive entry {info.name!r} carries extra/flag metadata")
    payload = {info.name: content for info, content in parsed}
    for entry in package.entries:
        if payload.get(entry.name) != entry.content:
            raise ReleasePackageError(f"archive payload {entry.name!r} does not match the declared entry")
    if payload[RELEASE_MANIFEST_NAME] != package.release_manifest:
        raise ReleasePackageError("archive release manifest does not match the package manifest")
    if payload[RELEASE_CHECKSUMS_NAME] != package.checksums:
        raise ReleasePackageError("archive checksums file does not match the package checksums")
    expected_checksums = _checksums_file(package.entries, package.release_manifest)
    if package.checksums != expected_checksums:
        raise ReleasePackageError("checksums file is not the canonical checksum file for this package")
    rebuilt = build_canonical_archive([(info.name, content) for info, content in parsed])
    if rebuilt != package.archive:
        raise ReleasePackageError("archive is not in canonical byte form")

    if expected_entries is not None:
        expected_map = {entry.name: entry.sha256() for entry in expected_entries}
        if package.entry_map() != expected_map:
            raise ReleasePackageError("package payload does not match the expected entry set")
    if provenance is not None:
        _cross_check_provenance(package.entries, provenance)
    findings = content_policy_findings(package.entries)
    if findings:
        raise ReleasePackageError(f"release package content policy violation: {findings[0]}")
    needle_findings = _scan_needles(package, forbidden_needles)
    if needle_findings:
        raise ReleasePackageError(f"release package leaks a forbidden needle: {needle_findings[0]}")

    return {
        "archive_entry_count": len(parsed),
        "archive_sha256": package.archive_sha256(),
        "entries": [entry.to_document() for entry in package.entries],
        "fixture_id": package.fixture_id,
        "payload_entry_count": len(package.entries),
        "release_manifest_sha256": _sha256_bytes(package.release_manifest),
        "source_state_fingerprint": document["provenance"]["source_state_fingerprint"],
    }


def analyze_release_package(package: ReleasePackage) -> dict[str, Any]:
    """Return deterministic metadata for evidence (archive layout and metadata)."""
    if not isinstance(package, ReleasePackage):
        raise ReleasePackageError("analyze_release_package requires a ReleasePackage")
    parsed = read_canonical_archive(package.archive)
    return {
        "archive_byte_length": len(package.archive),
        "archive_sha256": package.archive_sha256(),
        "checksums_sha256": _sha256_bytes(package.checksums),
        "entries": [info.to_document() for info, _ in parsed],
        "release_manifest_sha256": _sha256_bytes(package.release_manifest),
    }


__all__ = [
    "RELEASE_ARCHIVE_COMPRESSION",
    "RELEASE_ARCHIVE_CREATE_SYSTEM",
    "RELEASE_ARCHIVE_DATE_TIME",
    "RELEASE_ARCHIVE_ENTRY_ORDER",
    "RELEASE_ARCHIVE_EXTERNAL_ATTR",
    "RELEASE_ARCHIVE_FORMAT",
    "RELEASE_CHECKSUMS_NAME",
    "RELEASE_MANIFEST_NAME",
    "RELEASE_PACKAGE_SCHEMA",
    "RELEASE_PACKAGE_STAGE",
    "RELEASE_PACKAGE_VERSION",
    "ArchiveEntryInfo",
    "PackageCategory",
    "PackageEntry",
    "ReleasePackage",
    "ReleasePackageError",
    "ReleaseProvenance",
    "SourceStateEntry",
    "analyze_release_package",
    "assemble_release_package",
    "build_canonical_archive",
    "collect_source_state",
    "content_policy_findings",
    "read_canonical_archive",
    "source_state_fingerprint",
    "validate_release_manifest",
    "verify_release_package",
    "verify_source_state",
]
