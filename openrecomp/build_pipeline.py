"""OpenRecomp deterministic build pipeline V1 (P2-09).

`OpenRecomp Phase 2` stage P2-09 deliverable. This module turns deterministic
P2-07/P2-08 generated host source into reproducible native build artifacts with
explicit provenance:

    structural input -> generated host source -> build manifest
        -> compiler invocation -> object artifact -> link -> executable
        -> artifact hashes -> reproducibility evidence

Core rules:

* **explicit provenance**: a `BuildManifest` records the schema/version, stage,
  source fixture identity, generated-source names and SHA-256 values, runtime
  ABI version, exact compiler/linker identity and version/target, ordered
  compile/link arguments, canonical ordered inputs/outputs, artifact hashes,
  build status and a reproducibility classification. Success of two builds is
  never by itself treated as reproducibility.
* **deterministic serialization**: the manifest is canonical JSON (sorted keys,
  fixed separators) and two equivalent independent runs produce byte-identical
  manifests when their artifacts match. No wall-clock timestamp, temporary
  directory, absolute path, process id, random UUID or Python object identity is
  recorded. The manifest validator rejects those fields outright.
* **independent runs**: at least two builds are performed in isolated, distinct
  directories. Generated source is regenerated for every run; artifacts are
  never copied between runs.
* **fail closed**: source hash mismatches, ABI mismatches, unsupported or
  explicitly missing compilers, duplicate output names, unsafe/absolute output
  names, malformed manifests, failed compilation/link, missing artifacts,
  artifact-hash mismatches and over-strong reproducibility claims all raise
  `BuildError`. A reproducibility claim may never exceed the artifact equality
  actually observed.
* **toolchain-honest**: the toolchain is detected, never assumed. `/Brepro`
  (supported by the detected `clang-cl` + `lld-link`) is passed directly to the
  compiler and linker; no binary post-processing is used and no timestamp is
  zeroed outside the toolchain.

This module does **not** implement guest execution, equivalence checking or the
P2-10 tiny MIPS32 end-to-end proof.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from openrecomp import runtime_abi

BUILD_MANIFEST_SCHEMA = "openrecomp-build-manifest-v1"
BUILD_MANIFEST_VERSION = "1.0.0"
BUILD_PIPELINE_VERSION = "1.0.0"
BUILD_STAGE = "P2-09"

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
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
_MAX_MANIFEST_BYTES = 4 * 1024 * 1024


class BuildError(ValueError):
    """Raised when a deterministic build contract is violated."""


class BuildStatus(str, Enum):
    OK = "OK"
    TOOLCHAIN_UNAVAILABLE = "TOOLCHAIN_UNAVAILABLE"
    COMPILE_FAILED = "COMPILE_FAILED"
    LINK_FAILED = "LINK_FAILED"
    ARTIFACT_MISSING = "ARTIFACT_MISSING"


class BuildArtifactKind(str, Enum):
    GENERATED_SOURCE = "GENERATED_SOURCE"
    RUNTIME_SUPPORT_SOURCE = "RUNTIME_SUPPORT_SOURCE"
    OBJECT = "OBJECT"
    EXECUTABLE = "EXECUTABLE"


class BuildReproducibility(str, Enum):
    """Ordered from weakest to strongest evidence-backed claim."""

    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    TOOLCHAIN_UNAVAILABLE = "TOOLCHAIN_UNAVAILABLE"
    FUNCTIONALLY_REBUILT_BUT_BINARY_DIFFERS = "FUNCTIONALLY_REBUILT_BUT_BINARY_DIFFERS"
    SOURCE_REPRODUCIBLE = "SOURCE_REPRODUCIBLE"
    MANIFEST_REPRODUCIBLE = "MANIFEST_REPRODUCIBLE"
    OBJECT_REPRODUCIBLE = "OBJECT_REPRODUCIBLE"
    EXECUTABLE_REPRODUCIBLE = "EXECUTABLE_REPRODUCIBLE"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _require_safe_name(value: Any, where: str) -> str:
    if not isinstance(value, str) or not _SAFE_NAME.match(value):
        raise BuildError(f"{where}: {value!r} is not a safe relative artifact name")
    if ".." in value or "/" in value or "\\" in value or ":" in value:
        raise BuildError(f"{where}: {value!r} must not contain path components")
    return value


def _require_sha256(value: Any, where: str) -> str:
    if not isinstance(value, str) or not _SHA256.match(value):
        raise BuildError(f"{where}: {value!r} is not a lowercase sha256 digest")
    return value


# --- inputs / outputs -------------------------------------------------------
@dataclass(frozen=True)
class BuildSource:
    """One deterministic source input for the build (name is a relative path)."""

    name: str
    kind: BuildArtifactKind
    content: bytes

    def __post_init__(self) -> None:
        _require_safe_name(self.name, "build source.name")
        if not isinstance(self.kind, BuildArtifactKind):
            raise BuildError("build source.kind must be a BuildArtifactKind")
        if self.kind not in (BuildArtifactKind.GENERATED_SOURCE, BuildArtifactKind.RUNTIME_SUPPORT_SOURCE):
            raise BuildError(f"build source.kind {self.kind.value} is not a source kind")
        if not isinstance(self.content, (bytes, bytearray)):
            raise BuildError("build source.content must be bytes")
        object.__setattr__(self, "content", bytes(self.content))

    def sha256(self) -> str:
        return _sha256_bytes(self.content)

    def to_document(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind.value, "sha256": self.sha256()}


@dataclass(frozen=True)
class BuildInput:
    """A recorded source input: name, kind and SHA-256 (no content, no path)."""

    name: str
    kind: BuildArtifactKind
    sha256: str

    def __post_init__(self) -> None:
        _require_safe_name(self.name, "build input.name")
        if not isinstance(self.kind, BuildArtifactKind):
            raise BuildError("build input.kind must be a BuildArtifactKind")
        _require_sha256(self.sha256, "build input.sha256")

    def to_document(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind.value, "sha256": self.sha256}


@dataclass(frozen=True)
class BuildArtifact:
    """A recorded build output: name, kind, SHA-256 and presence."""

    name: str
    kind: BuildArtifactKind
    sha256: str | None
    present: bool

    def __post_init__(self) -> None:
        _require_safe_name(self.name, "build artifact.name")
        if not isinstance(self.kind, BuildArtifactKind):
            raise BuildError("build artifact.kind must be a BuildArtifactKind")
        if not isinstance(self.present, bool):
            raise BuildError("build artifact.present must be a boolean")
        if self.sha256 is not None:
            _require_sha256(self.sha256, "build artifact.sha256")
        if self.present and self.sha256 is None:
            raise BuildError(f"present build artifact {self.name} must record a sha256")

    def to_document(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind.value, "present": self.present, "sha256": self.sha256}


@dataclass(frozen=True)
class ToolchainIdentity:
    identity: str
    version: str
    target: str

    def __post_init__(self) -> None:
        for value, label in ((self.identity, "toolchain.identity"), (self.version, "toolchain.version"), (self.target, "toolchain.target")):
            if not isinstance(value, str) or not value:
                raise BuildError(f"{label} must be a non-empty string")

    def to_document(self) -> dict[str, Any]:
        return {"identity": self.identity, "target": self.target, "version": self.version}


@dataclass(frozen=True)
class BuildToolchain:
    """A detected toolchain with explicit, ordered compile/link arguments."""

    compiler: ToolchainIdentity
    linker: ToolchainIdentity
    compiler_executable: str
    linker_executable: str
    compile_arguments: tuple[str, ...]
    link_arguments: tuple[str, ...]

    def compile_command(self, source: str, object_name: str) -> tuple[str, ...]:
        _require_safe_name(source, "compile source")
        _require_safe_name(object_name, "compile object")
        return (self.compiler.identity, *self.compile_arguments, f"/Fo:{object_name}", source)

    def link_command(self, objects: Sequence[str], executable_name: str) -> tuple[str, ...]:
        _require_safe_name(executable_name, "link executable")
        for obj in objects:
            _require_safe_name(obj, "link object")
        return (self.linker.identity, *self.link_arguments, f"/OUT:{executable_name}", *objects)

    def to_document(self) -> dict[str, Any]:
        return {"compiler": self.compiler.to_document(), "linker": self.linker.to_document()}


# --- configuration ----------------------------------------------------------
@dataclass(frozen=True)
class BuildConfig:
    """Explicit, deterministic build configuration."""

    fixture_id: str
    runtime_abi_version: str = runtime_abi.RUNTIME_ABI_VERSION
    compiler: str | None = None
    run_count: int = 2
    reproducible: bool = True
    smoke_test: bool = True
    expected_smoke_output: str | None = None
    expected_source_hashes: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.fixture_id, str) or not self.fixture_id:
            raise BuildError("config.fixture_id must be a non-empty string")
        if not isinstance(self.runtime_abi_version, str) or not self.runtime_abi_version:
            raise BuildError("config.runtime_abi_version must be a non-empty string")
        if self.runtime_abi_version != runtime_abi.RUNTIME_ABI_VERSION:
            raise BuildError(
                f"config.runtime_abi_version {self.runtime_abi_version!r} does not match the runtime ABI "
                f"{runtime_abi.RUNTIME_ABI_VERSION!r} (ABI_VERSION_MISMATCH)"
            )
        if isinstance(self.run_count, bool) or not isinstance(self.run_count, int) or self.run_count < 1:
            raise BuildError("config.run_count must be a positive integer")
        if self.reproducible and self.run_count < 2:
            raise BuildError("config contradiction: reproducible builds require run_count >= 2")
        if self.compiler is not None and (not isinstance(self.compiler, str) or not self.compiler):
            raise BuildError("config.compiler must be a non-empty string or null")
        if self.expected_smoke_output is not None and not isinstance(self.expected_smoke_output, str):
            raise BuildError("config.expected_smoke_output must be a string or null")
        if self.smoke_test and self.expected_smoke_output is None:
            raise BuildError("config contradiction: smoke_test requires an expected_smoke_output")
        if not isinstance(self.expected_source_hashes, tuple):
            raise BuildError("config.expected_source_hashes must be a tuple")
        for name, digest in self.expected_source_hashes:
            _require_safe_name(name, "config.expected_source_hashes name")
            _require_sha256(digest, "config.expected_source_hashes digest")
        if len(set(name for name, _ in self.expected_source_hashes)) != len(self.expected_source_hashes):
            raise BuildError("config.expected_source_hashes must not repeat a name")

    def to_document(self) -> dict[str, Any]:
        return {
            "expected_smoke_output": self.expected_smoke_output,
            "expected_source_hashes": [list(item) for item in self.expected_source_hashes],
            "fixture_id": self.fixture_id,
            "reproducible": self.reproducible,
            "run_count": self.run_count,
            "runtime_abi_version": self.runtime_abi_version,
            "smoke_test": self.smoke_test,
        }


# --- manifest ---------------------------------------------------------------
@dataclass(frozen=True)
class BuildManifest:
    """A deterministic, machine-readable record of one build."""

    fixture_id: str
    runtime_abi_name: str
    runtime_abi_version: str
    toolchain: BuildToolchain
    inputs: tuple[BuildInput, ...]
    compile_commands: tuple[tuple[str, ...], ...]
    link_command: tuple[str, ...]
    outputs: tuple[BuildArtifact, ...]
    build_status: BuildStatus
    reproducibility: BuildReproducibility
    config: BuildConfig

    def __post_init__(self) -> None:
        if not isinstance(self.build_status, BuildStatus):
            raise BuildError("manifest.build_status must be a BuildStatus")
        if not isinstance(self.reproducibility, BuildReproducibility):
            raise BuildError("manifest.reproducibility must be a BuildReproducibility")
        if not self.inputs:
            raise BuildError("manifest must record at least one input")
        names = [item.name for item in self.inputs] + [item.name for item in self.outputs]
        if len(set(names)) != len(names):
            raise BuildError("manifest input/output names must be unique")
        if len(self.compile_commands) != len(self.inputs):
            raise BuildError("manifest must record one compile command per input")

    # -- documents ------------------------------------------------------------
    def to_document(self) -> dict[str, Any]:
        return {
            "schema": BUILD_MANIFEST_SCHEMA,
            "manifest_version": BUILD_MANIFEST_VERSION,
            "pipeline_version": BUILD_PIPELINE_VERSION,
            "stage": BUILD_STAGE,
            "fixture_id": self.fixture_id,
            "runtime_abi": {"name": self.runtime_abi_name, "version": self.runtime_abi_version},
            "toolchain": self.toolchain.to_document(),
            "inputs": [item.to_document() for item in self.inputs],
            "compile_commands": [list(command) for command in self.compile_commands],
            "link_command": list(self.link_command),
            "outputs": [item.to_document() for item in self.outputs],
            "build_status": self.build_status.value,
            "reproducibility": self.reproducibility.value,
            "deterministic_config": self.config.to_document(),
        }

    def serialize(self) -> bytes:
        return (_canonical_json(self.to_document()) + "\n").encode("utf-8")

    def fingerprint(self) -> str:
        return _sha256_bytes(self.serialize())

    def inputs_document(self) -> dict[str, Any]:
        """The manifest document without artifact-dependent output fields."""
        document = self.to_document()
        for key in ("outputs", "build_status", "reproducibility"):
            document.pop(key, None)
        return document

    def inputs_fingerprint(self) -> str:
        return _sha256_bytes((_canonical_json(self.inputs_document()) + "\n").encode("utf-8"))

    def artifact_map(self, kind: BuildArtifactKind | None = None) -> dict[str, str]:
        return {
            item.name: item.sha256
            for item in self.outputs
            if item.sha256 is not None and (kind is None or item.kind is kind)
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, toolchain: BuildToolchain | None = None, config: BuildConfig | None = None) -> "BuildManifest":
        if not isinstance(document, Mapping):
            raise BuildError("build manifest must be a JSON object")
        _reject_forbidden_keys(document, "manifest")
        expected = {
            "schema", "manifest_version", "pipeline_version", "stage", "fixture_id",
            "runtime_abi", "toolchain", "inputs", "compile_commands", "link_command",
            "outputs", "build_status", "reproducibility", "deterministic_config",
        }
        unknown = sorted(set(document) - expected)
        if unknown:
            raise BuildError(f"manifest has unsupported key(s): {', '.join(unknown)}")
        missing = sorted(expected - set(document))
        if missing:
            raise BuildError(f"manifest is missing key(s): {', '.join(missing)}")
        if document["schema"] != BUILD_MANIFEST_SCHEMA:
            raise BuildError(f"unsupported manifest schema {document['schema']!r}")
        if document["manifest_version"] != BUILD_MANIFEST_VERSION:
            raise BuildError(f"unsupported manifest version {document['manifest_version']!r}")
        if document["stage"] != BUILD_STAGE:
            raise BuildError(f"unsupported manifest stage {document['stage']!r}")
        abi = document["runtime_abi"]
        if not isinstance(abi, Mapping) or "name" not in abi or "version" not in abi:
            raise BuildError("manifest.runtime_abi is malformed")
        if abi["version"] != runtime_abi.RUNTIME_ABI_VERSION:
            raise BuildError(
                f"manifest runtime ABI {abi['version']!r} does not match {runtime_abi.RUNTIME_ABI_VERSION!r}"
            )
        if not isinstance(document["inputs"], list) or not document["inputs"]:
            raise BuildError("manifest.inputs must be a non-empty list")
        if not isinstance(document["outputs"], list):
            raise BuildError("manifest.outputs must be a list")
        inputs = tuple(_input_from_document(item, index) for index, item in enumerate(document["inputs"]))
        outputs = tuple(_artifact_from_document(item, index) for index, item in enumerate(document["outputs"]))
        commands = document["compile_commands"]
        if not isinstance(commands, list) or not all(isinstance(cmd, list) and all(isinstance(a, str) for a in cmd) for cmd in commands):
            raise BuildError("manifest.compile_commands must be a list of argument lists")
        link = document["link_command"]
        if not isinstance(link, list) or not all(isinstance(a, str) for a in link):
            raise BuildError("manifest.link_command must be an argument list")
        try:
            status = BuildStatus(document["build_status"])
        except ValueError as exc:
            raise BuildError(f"unsupported build status {document['build_status']!r}") from exc
        try:
            reproducibility = BuildReproducibility(document["reproducibility"])
        except ValueError as exc:
            raise BuildError(f"unsupported reproducibility {document['reproducibility']!r}") from exc
        if toolchain is None:
            toolchain = _toolchain_from_document(document["toolchain"])
        resolved_config = config or BuildConfig(
            fixture_id=document["fixture_id"],
            runtime_abi_version=abi["version"],
            run_count=document["deterministic_config"].get("run_count", 2),
            reproducible=document["deterministic_config"].get("reproducible", True),
            smoke_test=document["deterministic_config"].get("smoke_test", False),
            expected_smoke_output=document["deterministic_config"].get("expected_smoke_output"),
            expected_source_hashes=tuple(
                (item[0], item[1]) for item in document["deterministic_config"].get("expected_source_hashes", [])
            ),
        )
        return cls(
            fixture_id=document["fixture_id"],
            runtime_abi_name=abi["name"],
            runtime_abi_version=abi["version"],
            toolchain=toolchain,
            inputs=inputs,
            compile_commands=tuple(tuple(cmd) for cmd in commands),
            link_command=tuple(link),
            outputs=outputs,
            build_status=status,
            reproducibility=reproducibility,
            config=resolved_config,
        )

    @classmethod
    def deserialize(cls, data: bytes | str, *, toolchain: BuildToolchain | None = None, config: BuildConfig | None = None) -> "BuildManifest":
        if isinstance(data, (bytes, bytearray)) and len(data) > _MAX_MANIFEST_BYTES:
            raise BuildError("manifest is too large")
        try:
            document = json.loads(data)
        except (ValueError, UnicodeDecodeError) as exc:
            raise BuildError(f"invalid manifest JSON: {exc}") from exc
        return cls.from_document(document, toolchain=toolchain, config=config)


def _canonical_json(document: Any) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _reject_forbidden_keys(value: Any, where: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(key, str) and key.lower() in _FORBIDDEN_KEYS:
                raise BuildError(f"{where}: nondeterministic field {key!r} is not permitted")
            _reject_forbidden_keys(item, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_forbidden_keys(item, f"{where}[{index}]")


def _input_from_document(document: Any, index: int) -> BuildInput:
    if not isinstance(document, Mapping):
        raise BuildError(f"manifest.inputs[{index}] must be an object")
    if set(document) != {"name", "kind", "sha256"}:
        raise BuildError(f"manifest.inputs[{index}] has unsupported keys")
    try:
        kind = BuildArtifactKind(document["kind"])
    except ValueError as exc:
        raise BuildError(f"manifest.inputs[{index}].kind is unsupported") from exc
    return BuildInput(name=document["name"], kind=kind, sha256=document["sha256"])


def _artifact_from_document(document: Any, index: int) -> BuildArtifact:
    if not isinstance(document, Mapping):
        raise BuildError(f"manifest.outputs[{index}] must be an object")
    if set(document) != {"name", "kind", "present", "sha256"}:
        raise BuildError(f"manifest.outputs[{index}] has unsupported keys")
    try:
        kind = BuildArtifactKind(document["kind"])
    except ValueError as exc:
        raise BuildError(f"manifest.outputs[{index}].kind is unsupported") from exc
    return BuildArtifact(
        name=document["name"], kind=kind, sha256=document["sha256"], present=document["present"]
    )


def _toolchain_from_document(document: Any) -> BuildToolchain:
    if not isinstance(document, Mapping) or "compiler" not in document or "linker" not in document:
        raise BuildError("manifest.toolchain is malformed")
    compiler = document["compiler"]
    linker = document["linker"]
    for label, item in (("compiler", compiler), ("linker", linker)):
        if not isinstance(item, Mapping) or set(item) != {"identity", "target", "version"}:
            raise BuildError(f"manifest.toolchain.{label} is malformed")
    return BuildToolchain(
        compiler=ToolchainIdentity(compiler["identity"], compiler["version"], compiler["target"]),
        linker=ToolchainIdentity(linker["identity"], linker["version"], linker["target"]),
        compiler_executable=compiler["identity"],
        linker_executable=linker["identity"],
        compile_arguments=(),
        link_arguments=(),
    )


# --- toolchain discovery ----------------------------------------------------
def _toolchain_version(executable: str) -> str:
    completed = subprocess.run([executable, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise BuildError(f"unable to query toolchain version: {executable}")
    for line in (completed.stdout or "").splitlines():
        line = line.strip()
        if line:
            return line
    raise BuildError(f"toolchain {executable} produced no version output")


def _toolchain_target(executable: str) -> str:
    completed = subprocess.run([executable, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in (completed.stdout or "").splitlines():
        line = line.strip()
        if line.lower().startswith("target:"):
            return line.split(":", 1)[1].strip()
    raise BuildError(f"toolchain {executable} did not report a target")


def _normalized_exe_name(path: str) -> str:
    name = Path(path).name
    stem, dot, suffix = name.rpartition(".")
    return f"{stem}.{suffix.lower()}" if dot else name


def discover_toolchain(preferred: str | None = None, *, raise_on_missing: bool = False) -> BuildToolchain | None:
    """Detect a supported toolchain. `clang-cl` + `lld-link` is preferred."""
    names = [preferred] if preferred else ["clang-cl"]
    for name in names:
        compiler_path = shutil.which(name)
        if compiler_path is None:
            if raise_on_missing:
                raise BuildError(f"requested compiler {name!r} was not found (unsupported compiler)")
            return None
        linker_path = shutil.which("lld-link")
        if linker_path is None:
            if raise_on_missing:
                raise BuildError("lld-link is required for the reproducible clang-cl profile but was not found")
            return None
        compiler_version = _toolchain_version(compiler_path)
        target = _toolchain_target(compiler_path)
        linker_version = _toolchain_version(linker_path)
        compiler = ToolchainIdentity(identity=_normalized_exe_name(compiler_path), version=compiler_version, target=target)
        linker = ToolchainIdentity(identity=_normalized_exe_name(linker_path), version=linker_version, target=target)
        return BuildToolchain(
            compiler=compiler,
            linker=linker,
            compiler_executable=compiler_path,
            linker_executable=linker_path,
            compile_arguments=("/c", "/Brepro", "/Od", "/std:c11", "/nologo"),
            link_arguments=("/Brepro", "/nologo"),
        )
    return None


# --- one build run ----------------------------------------------------------
@dataclass(frozen=True)
class BuildRun:
    """The outcome of one isolated build run."""

    index: int
    manifest: BuildManifest
    smoke_stdout: str | None
    smoke_returncode: int | None
    compiler_stderr: str

    def to_document(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "manifest_sha256": self.manifest.fingerprint(),
            "manifest": self.manifest.to_document(),
            "smoke_stdout": self.smoke_stdout,
            "smoke_returncode": self.smoke_returncode,
        }


def _validated_sources(
    provider: Callable[[], str],
    support_sources: Sequence[BuildSource],
    expected_source_hashes: Sequence[tuple[str, str]] = (),
) -> list[BuildSource]:
    text = provider()
    if not isinstance(text, str) or not text:
        raise BuildError("generated source provider must return a non-empty string")
    sources = [BuildSource("generated.c", BuildArtifactKind.GENERATED_SOURCE, text.encode("utf-8"))]
    for source in support_sources:
        if not isinstance(source, BuildSource):
            raise BuildError("support_sources must contain BuildSource instances")
        sources.append(source)
    sources.sort(key=lambda item: item.name)
    names = [item.name for item in sources]
    if len(set(names)) != len(names):
        raise BuildError("duplicate source/output names are not permitted")
    by_name = {item.name: item for item in sources}
    for name, expected in expected_source_hashes:
        actual = by_name.get(name)
        if actual is None:
            raise BuildError(f"expected source {name!r} was not supplied")
        if actual.sha256() != expected:
            raise BuildError(
                f"source hash mismatch for {name!r}: declared {expected}, observed {actual.sha256()}"
            )
    return sources


def _run_build(
    run_index: int,
    run_dir: Path,
    sources: Sequence[BuildSource],
    config: BuildConfig,
    toolchain: BuildToolchain,
) -> BuildRun:
    run_dir.mkdir(parents=True, exist_ok=True)
    for source in sources:
        (run_dir / source.name).write_bytes(source.content)

    inputs = tuple(BuildInput(item.name, item.kind, item.sha256()) for item in sources)
    object_names: dict[str, str] = {}
    compile_commands: list[tuple[str, ...]] = []
    for source in sources:
        object_name = Path(source.name).stem + ".obj"
        _require_safe_name(object_name, "object name")
        if object_name in object_names.values():
            raise BuildError(f"duplicate output path {object_name!r}")
        object_names[source.name] = object_name
        command = toolchain.compile_command(source.name, object_name)
        compile_commands.append(command)
        completed = subprocess.run(
            [toolchain.compiler_executable, *command[1:]],
            cwd=str(run_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or "").strip()
            manifest = _manifest(
                inputs, compile_commands, config, toolchain, BuildStatus.COMPILE_FAILED, (), ()
            )
            return BuildRun(run_index, manifest, None, None, stderr)

    executable_name = "program.exe"
    if executable_name in object_names.values():
        raise BuildError(f"duplicate output path {executable_name!r}")
    object_order = [object_names[item.name] for item in sources]
    link_command = toolchain.link_command(object_order, executable_name)
    completed = subprocess.run(
        [toolchain.linker_executable, *link_command[1:]],
        cwd=str(run_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    outputs: list[BuildArtifact] = []
    for object_name in object_order:
        path = run_dir / object_name
        outputs.append(
            BuildArtifact(object_name, BuildArtifactKind.OBJECT, _sha256_file(path) if path.exists() else None, path.exists())
        )
    if completed.returncode != 0:
        manifest = _manifest(
            inputs, compile_commands, config, toolchain, BuildStatus.LINK_FAILED, outputs, link_command
        )
        return BuildRun(run_index, manifest, None, None, (completed.stderr or "").strip())
    executable_path = run_dir / executable_name
    if not executable_path.exists():
        manifest = _manifest(
            inputs, compile_commands, config, toolchain, BuildStatus.ARTIFACT_MISSING, outputs, link_command
        )
        return BuildRun(run_index, manifest, None, None, "linked executable is missing")
    outputs.append(BuildArtifact(executable_name, BuildArtifactKind.EXECUTABLE, _sha256_file(executable_path), True))

    smoke_stdout = None
    smoke_returncode = None
    if config.smoke_test:
        ran = subprocess.run([str(executable_path)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        smoke_stdout = (ran.stdout or "").strip()
        smoke_returncode = ran.returncode

    manifest = _manifest(
        inputs, compile_commands, config, toolchain, BuildStatus.OK, outputs, link_command
    )
    return BuildRun(run_index, manifest, smoke_stdout, smoke_returncode, "")


def _manifest(
    inputs: tuple[BuildInput, ...],
    compile_commands: Sequence[tuple[str, ...]],
    config: BuildConfig,
    toolchain: BuildToolchain,
    status: BuildStatus,
    outputs: Sequence[BuildArtifact],
    link_command: Sequence[str],
) -> BuildManifest:
    ordered_outputs = tuple(
        sorted(outputs, key=lambda item: (item.kind is not BuildArtifactKind.OBJECT, item.name))
    )
    return BuildManifest(
        fixture_id=config.fixture_id,
        runtime_abi_name=runtime_abi.RUNTIME_ABI_NAME,
        runtime_abi_version=config.runtime_abi_version,
        toolchain=toolchain,
        inputs=inputs,
        compile_commands=tuple(compile_commands),
        link_command=tuple(link_command),
        outputs=ordered_outputs,
        build_status=status,
        reproducibility=BuildReproducibility.NOT_ESTABLISHED,
        config=config,
    )


# --- comparison -------------------------------------------------------------
@dataclass(frozen=True)
class BuildComparison:
    """The reproducibility comparison of two or more independent build runs."""

    runs: tuple[BuildRun, ...]
    source_reproducible: bool
    manifest_reproducible: bool
    object_reproducible: bool | None
    executable_reproducible: bool | None
    classification: BuildReproducibility
    toolchain_available: bool

    def __post_init__(self) -> None:
        if len(self.runs) < 1:
            raise BuildError("a comparison requires at least one run")
        expected = _classify(
            self.toolchain_available,
            [run.manifest.build_status for run in self.runs],
            self.source_reproducible,
            self.manifest_reproducible,
            self.object_reproducible,
            self.executable_reproducible,
        )
        if self.classification is not expected:
            raise BuildError(
                f"unsupported reproducibility claim {self.classification.value}; observed evidence supports "
                f"{expected.value} (claims must never exceed evidence)"
            )

    def to_document(self) -> dict[str, Any]:
        return {
            "classification": self.classification.value,
            "executable_reproducible": self.executable_reproducible,
            "manifest_reproducible": self.manifest_reproducible,
            "object_reproducible": self.object_reproducible,
            "run_count": len(self.runs),
            "runs": [run.to_document() for run in self.runs],
            "source_reproducible": self.source_reproducible,
            "toolchain_available": self.toolchain_available,
        }

    def serialize(self) -> bytes:
        return (_canonical_json(self.to_document()) + "\n").encode("utf-8")

    def fingerprint(self) -> str:
        return _sha256_bytes(self.serialize())


def _classify(
    toolchain_available: bool,
    statuses: Sequence[BuildStatus],
    source_ok: bool,
    manifest_ok: bool,
    object_ok: bool | None,
    executable_ok: bool | None,
) -> BuildReproducibility:
    if not toolchain_available:
        return BuildReproducibility.TOOLCHAIN_UNAVAILABLE
    if not statuses or any(status is not BuildStatus.OK for status in statuses):
        return BuildReproducibility.NOT_ESTABLISHED
    if executable_ok:
        return BuildReproducibility.EXECUTABLE_REPRODUCIBLE
    if object_ok:
        return BuildReproducibility.OBJECT_REPRODUCIBLE
    if manifest_ok:
        return BuildReproducibility.MANIFEST_REPRODUCIBLE
    if source_ok:
        return BuildReproducibility.SOURCE_REPRODUCIBLE
    return BuildReproducibility.FUNCTIONALLY_REBUILT_BUT_BINARY_DIFFERS


def compare_runs(
    runs: Sequence[BuildRun],
    *,
    toolchain_available: bool,
) -> BuildComparison:
    if len(runs) < 2:
        raise BuildError("reproducibility comparison requires at least two independent runs")
    reference = runs[0].manifest
    source_ok = _all_equal([run.manifest.inputs_document()["inputs"] for run in runs])
    manifest_ok = _all_equal([run.manifest.inputs_fingerprint() for run in runs])
    built = all(run.manifest.build_status is BuildStatus.OK for run in runs)
    object_ok: bool | None = None
    executable_ok: bool | None = None
    if built:
        object_ok = all(
            run.manifest.artifact_map(BuildArtifactKind.OBJECT) == reference.artifact_map(BuildArtifactKind.OBJECT)
            for run in runs
        )
        executable_ok = all(
            run.manifest.artifact_map(BuildArtifactKind.EXECUTABLE) == reference.artifact_map(BuildArtifactKind.EXECUTABLE)
            for run in runs
        )
    classification = _classify(
        toolchain_available,
        [run.manifest.build_status for run in runs],
        source_ok,
        manifest_ok,
        object_ok,
        executable_ok,
    )
    annotated_runs = tuple(
        replace(run, manifest=replace(run.manifest, reproducibility=classification)) for run in runs
    )
    return BuildComparison(
        runs=annotated_runs,
        source_reproducible=source_ok,
        manifest_reproducible=manifest_ok,
        object_reproducible=object_ok,
        executable_reproducible=executable_ok,
        classification=classification,
        toolchain_available=toolchain_available,
    )


def _all_equal(values: Sequence[Any]) -> bool:
    first = values[0]
    return all(value == first for value in values[1:])


# --- entry points -----------------------------------------------------------
def build_generated_host(
    generated_source: Callable[[], str] | str,
    *,
    support_sources: Sequence[BuildSource] = (),
    config: BuildConfig,
    workspace: str | os.PathLike[str] | None = None,
    keep_workspace: bool = False,
) -> BuildComparison:
    """Build deterministic generated host source in isolated directories.

    `generated_source` is either a fixed string or a zero-argument callable that
    regenerates the source for every run (the former is required for a genuine
    independent-reproducibility result).
    """
    if not isinstance(config, BuildConfig):
        raise BuildError("build_generated_host requires a BuildConfig")
    provider = generated_source if callable(generated_source) else (lambda: generated_source)

    explicit = config.compiler is not None
    toolchain = discover_toolchain(config.compiler, raise_on_missing=explicit)

    own_workspace = None
    if workspace is None:
        own_workspace = tempfile.mkdtemp(prefix="openrecomp-p209-")
        workspace = own_workspace
    root = Path(workspace)
    root.mkdir(parents=True, exist_ok=True)
    try:
        run_dirs = [root / f"run{index + 1}" for index in range(config.run_count)]
        for run_dir in run_dirs:
            if run_dir.exists():
                raise BuildError(f"build directory {run_dir.name!r} already exists; isolated runs must be distinct")

        if toolchain is None:
            runs: list[BuildRun] = []
            for index, run_dir in enumerate(run_dirs):
                run_dir.mkdir(parents=True)
                sources = _validated_sources(provider, support_sources, config.expected_source_hashes)
                for source in sources:
                    (run_dir / source.name).write_bytes(source.content)
                inputs = tuple(BuildInput(item.name, item.kind, item.sha256()) for item in sources)
                commands = tuple(
                    ("clang-cl", "/c", "/Brepro", "/Od", "/std:c11", "/nologo", f"/Fo:{Path(item.name).stem}.obj", item.name)
                    for item in sources
                )
                absent_toolchain = BuildToolchain(
                    compiler=ToolchainIdentity("unavailable", "unavailable", "unavailable"),
                    linker=ToolchainIdentity("unavailable", "unavailable", "unavailable"),
                    compiler_executable="unavailable",
                    linker_executable="unavailable",
                    compile_arguments=(),
                    link_arguments=(),
                )
                manifest = _manifest(
                    inputs, commands, config, absent_toolchain, BuildStatus.TOOLCHAIN_UNAVAILABLE, (), ()
                )
                runs.append(BuildRun(index, manifest, None, None, ""))
            return compare_runs(runs, toolchain_available=False)

        runs = []
        for index, run_dir in enumerate(run_dirs):
            if run_dir.exists():
                raise BuildError(f"build directory {run_dir.name!r} already exists")
            sources = _validated_sources(provider, support_sources, config.expected_source_hashes)
            runs.append(_run_build(index, run_dir, sources, config, toolchain))
        comparison = compare_runs(runs, toolchain_available=True)
        if config.smoke_test and comparison.runs and comparison.runs[0].manifest.build_status is BuildStatus.OK:
            _verify_smoke(comparison.runs, config)
        return comparison
    finally:
        if own_workspace is not None and not keep_workspace:
            shutil.rmtree(own_workspace, ignore_errors=True)


def build_generated_host_from(
    emit: Callable[[], Any],
    *,
    support_sources: Sequence[BuildSource] = (),
    config: BuildConfig,
    workspace: str | os.PathLike[str] | None = None,
    keep_workspace: bool = False,
) -> BuildComparison:
    """Build from a P2-07/P2-08 emitter callable returning a host translation set."""

    def provider() -> str:
        result = emit()
        text = getattr(result, "source_text", None)
        if not isinstance(text, str) or not text:
            raise BuildError("emit callable must return a host translation set with source_text")
        return text

    return build_generated_host(
        provider,
        support_sources=support_sources,
        config=config,
        workspace=workspace,
        keep_workspace=keep_workspace,
    )


def verify_artifact_hashes(manifest: BuildManifest, observed: Mapping[str, str]) -> None:
    """Fail closed if rebuilt artifacts disagree with the manifest's claims."""
    if not isinstance(manifest, BuildManifest):
        raise BuildError("verify_artifact_hashes requires a BuildManifest")
    for artifact in manifest.outputs:
        if artifact.name not in observed:
            raise BuildError(f"claimed artifact {artifact.name!r} was not produced")
        actual = observed[artifact.name]
        _require_sha256(actual, f"observed artifact {artifact.name}")
        if artifact.sha256 is not None and actual != artifact.sha256:
            raise BuildError(
                f"artifact hash mismatch for {artifact.name!r}: claimed {artifact.sha256}, observed {actual}"
            )


def _verify_smoke(runs: Sequence[BuildRun], config: BuildConfig) -> None:
    for run in runs:
        if run.smoke_returncode != 0:
            raise BuildError(f"build run {run.index + 1}: execution smoke test exited with {run.smoke_returncode}")
        if config.expected_smoke_output is not None and run.smoke_stdout != config.expected_smoke_output:
            raise BuildError(
                f"build run {run.index + 1}: execution smoke test observed {run.smoke_stdout!r}, "
                f"expected {config.expected_smoke_output!r}"
            )


__all__ = [
    "BUILD_MANIFEST_SCHEMA",
    "BUILD_MANIFEST_VERSION",
    "BUILD_PIPELINE_VERSION",
    "BUILD_STAGE",
    "BuildArtifact",
    "BuildArtifactKind",
    "BuildComparison",
    "BuildConfig",
    "BuildError",
    "BuildInput",
    "BuildManifest",
    "BuildReproducibility",
    "BuildRun",
    "BuildSource",
    "BuildStatus",
    "BuildToolchain",
    "ToolchainIdentity",
    "build_generated_host",
    "build_generated_host_from",
    "compare_runs",
    "discover_toolchain",
    "verify_artifact_hashes",
]
