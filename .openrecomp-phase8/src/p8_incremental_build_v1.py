#!/usr/bin/env python3
"""OpenRecomp Phase-8 content-hash incremental native build helper.

Implements the `ACCELERATION_POLICY.md` incremental-build contract:

* an object-cache key is
  `sha256(canonical_json({"source_sha256", "compiler_identity",
  "compile_arguments", "object_name"}))`;
* a cached object is reused only when the key exists, the cached object hash
  still matches the recorded hash, and the recorded source hash matches the
  current source;
* a content-hash mismatch or a corrupted cache entry forces a recompile;
* the official audited path remains the existing deterministic build pipeline
  (`openrecomp.build_pipeline`); this helper only accelerates development
  loops.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
from typing import Any, Mapping

CACHE_SCHEMA = "openrecomp-phase8-object-cache-v1"
CACHE_INDEX = "index.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class IncrementalBuildError(RuntimeError):
    pass


class IncrementalBuilder:
    """Content-hash keyed native object cache and builder."""

    def __init__(self, workspace: pathlib.Path, cache_dir: pathlib.Path, toolchain: Any) -> None:
        self.workspace = pathlib.Path(workspace)
        self.cache_dir = pathlib.Path(cache_dir)
        self.toolchain = toolchain

    def _load_index(self) -> dict[str, Any]:
        path = self.cache_dir / CACHE_INDEX
        if not path.is_file():
            return {"schema": CACHE_SCHEMA, "objects": {}}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") != CACHE_SCHEMA:
            raise IncrementalBuildError("unexpected object-cache schema")
        return payload

    def _save_index(self, index: dict[str, Any]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / CACHE_INDEX).write_text(
            canonical_json(index) + "\n", encoding="utf-8", newline="\n"
        )

    def key_for(self, name: str, text: str, object_name: str) -> str:
        return sha256_bytes(
            canonical_json(
                {
                    "source_sha256": sha256_bytes(text.encode("utf-8")),
                    "compiler_identity": self.toolchain.compiler.identity,
                    "compiler_version": self.toolchain.compiler.version,
                    "compile_arguments": list(self.toolchain.compile_arguments),
                    "object_name": object_name,
                }
            ).encode("utf-8")
        )

    def build(self, files: Mapping[str, str]) -> dict[str, Any]:
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        index = self._load_index()
        objects: list[str] = []
        records: list[dict[str, Any]] = []
        warnings: list[str] = []
        compiled = 0
        reused = 0
        for name, text in files.items():
            object_name = pathlib.Path(name).stem + ".obj"
            object_path = self.workspace / object_name
            key = self.key_for(name, text, object_name)
            source_path = self.workspace / name
            source_path.write_text(text, encoding="utf-8", newline="\n")
            cached = index["objects"].get(key)
            if (
                cached is not None
                and (self.cache_dir / cached["object"]).is_file()
                and sha256_bytes((self.cache_dir / cached["object"]).read_bytes()) == cached["object_sha256"]
            ):
                shutil.copyfile(self.cache_dir / cached["object"], object_path)
                reused += 1
                status = "REUSED"
            else:
                command = self.toolchain.compile_command(name, object_name)
                completed = subprocess.run(
                    [self.toolchain.compiler_executable, *command[1:]],
                    cwd=str(self.workspace),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                if completed.returncode != 0:
                    raise IncrementalBuildError(
                        f"compile failed for {name}: {completed.stderr.strip()[:200]}"
                    )
                warnings.extend(
                    line.strip()
                    for line in (completed.stderr or "").splitlines()
                    if "warning:" in line
                )
                cache_object = f"{key}.obj"
                shutil.copyfile(object_path, self.cache_dir / cache_object)
                index["objects"][key] = {
                    "object": cache_object,
                    "object_sha256": sha256_bytes(object_path.read_bytes()),
                    "source_sha256": sha256_bytes(text.encode("utf-8")),
                    "source_name": name,
                }
                compiled += 1
                status = "COMPILED"
            objects.append(object_name)
            records.append(
                {
                    "source": name,
                    "object": object_name,
                    "key": key,
                    "status": status,
                    "object_sha256": sha256_bytes(object_path.read_bytes()),
                }
            )
        executable_name = "program.exe"
        link_command = self.toolchain.link_command(objects, executable_name)
        completed = subprocess.run(
            [self.toolchain.linker_executable, *link_command[1:]],
            cwd=str(self.workspace),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            raise IncrementalBuildError(f"link failed: {completed.stderr.strip()[:200]}")
        warnings.extend(
            line.strip()
            for line in (completed.stderr or "").splitlines()
            if "warning:" in line
        )
        self._save_index(index)
        executable = self.workspace / executable_name
        return {
            "compiled": compiled,
            "reused": reused,
            "records": records,
            "warnings": warnings,
            "link_command": "<toolchain> " + " ".join(link_command[1:]),
            "executable_sha256": sha256_bytes(executable.read_bytes()),
            "executable_bytes": len(executable.read_bytes()),
            "cache_entries": len(index["objects"]),
        }
