#!/usr/bin/env python3
"""OpenRecomp Phase-10 immutable-hash analysis cache V1.

The cache is keyed by a canonical provenance document, never by a filename.
A cache entry is only valid when *every* provenance component matches:

* the private executable SHA-256;
* the CUE SHA-256 (the authoritative disc entry point) and every referenced BIN
  SHA-256;
* the PS-X EXE header identity digest;
* the frontend, semantic-model, runtime-composition and disc-model versions;
* the analysis configuration digest.

Anything else - a renamed file, a rebuilt executable, a changed runtime
composition, a changed configuration - produces a different key and therefore a
miss. Values are stored as JSON documents; nothing binary and no guest payload
is ever cached inside the repository (the cache directory is untracked).
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

CACHE_VERSION = "1.0.0"

ERROR_CODES = (
    "PROVENANCE_MISSING_FIELD",
    "PROVENANCE_CONTRADICTION",
    "CACHE_ENTRY_CORRUPT",
    "CACHE_KEY_MISMATCH",
)


class AnalysisCacheError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise AssertionError(f"unknown analysis cache error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


REQUIRED_PROVENANCE_FIELDS = (
    "executable_sha256",
    "cue_sha256",
    "bin_sha256s",
    "exe_identity_digest",
    "frontend_version",
    "semantic_version",
    "runtime_version",
    "disc_model_version",
    "analysis_config_digest",
)


def canonical(document: dict[str, Any]) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def provenance_digest(provenance: dict[str, Any]) -> str:
    """Digest a provenance document, failing closed on missing/odd fields."""
    for field in REQUIRED_PROVENANCE_FIELDS:
        if field not in provenance:
            raise AnalysisCacheError("PROVENANCE_MISSING_FIELD", field)
    for field in ("executable_sha256", "cue_sha256", "exe_identity_digest",
                  "analysis_config_digest"):
        value = provenance[field]
        if not isinstance(value, str) or len(value) != 64:
            raise AnalysisCacheError("PROVENANCE_CONTRADICTION", f"{field}={value!r}")
    bins = provenance["bin_sha256s"]
    if not isinstance(bins, list) or not bins:
        raise AnalysisCacheError("PROVENANCE_CONTRADICTION", "bin_sha256s")
    for entry in bins:
        if not isinstance(entry, str) or len(entry) != 64:
            raise AnalysisCacheError("PROVENANCE_CONTRADICTION", f"bin={entry!r}")
    for field in ("frontend_version", "semantic_version", "runtime_version", "disc_model_version"):
        if not isinstance(provenance[field], str) or not provenance[field]:
            raise AnalysisCacheError("PROVENANCE_CONTRADICTION", f"{field}={provenance[field]!r}")
    return sha256_text(CACHE_VERSION + "\n" + canonical(provenance))


class AnalysisCache:
    """Deterministic provenance-keyed cache over an untracked directory."""

    def __init__(self, root: pathlib.Path) -> None:
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _entry_path(self, key: str) -> pathlib.Path:
        return self.root / f"{key}.json"

    def lookup(self, provenance: dict[str, Any]) -> dict[str, Any] | None:
        """Return the cached document for exactly this provenance, or None."""
        key = provenance_digest(provenance)
        path = self._entry_path(key)
        if not path.is_file():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise AnalysisCacheError("CACHE_ENTRY_CORRUPT", str(exc)) from exc
        if entry.get("key") != key:
            raise AnalysisCacheError("CACHE_KEY_MISMATCH", str(entry.get("key")))
        if entry.get("provenance") != provenance:
            raise AnalysisCacheError("CACHE_KEY_MISMATCH", "provenance mismatch")
        return entry.get("document")

    def store(self, provenance: dict[str, Any], document: dict[str, Any]) -> str:
        key = provenance_digest(provenance)
        payload = {
            "schema": "openrecomp-phase10-analysis-cache-v1",
            "cache_version": CACHE_VERSION,
            "key": key,
            "provenance": provenance,
            "document": document,
        }
        self._entry_path(key).write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return key

    def stored_keys(self) -> tuple[str, ...]:
        return tuple(sorted(path.stem for path in self.root.glob("*.json")))
