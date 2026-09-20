#!/usr/bin/env python3
"""OpenRecomp Phase-9 immutable-hash analysis cache V1.

Cache keys follow the frozen `openrecomp-phase9-analysis-cache-v1` contract:

    cache_key = sha256(utf8(canonical_json({
      "schema": "openrecomp-phase9-analysis-cache-v1",
      "product": ...,
      "input_sha256": ...,
      "input_size_bytes": ...,
      "analysis_config": ...,
      "frontend_sha256": {...},
      "semantic_model": {...},
      "producer_sha256": ...
    })))

A cache entry is accepted only when its stored key equals the independently
recomputed key; a matching filename is never sufficient. Stale and corrupted
entries are rejected, never silently reused.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from dataclasses import dataclass
from typing import Any

CACHE_SCHEMA = "openrecomp-phase9-analysis-cache-v1"
ENTRY_SCHEMA = "openrecomp-phase9-analysis-cache-entry-v1"


class CacheError(RuntimeError):
    """Stable cache rejection."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class CacheKeyInputs:
    product: str
    input_sha256: str
    input_size_bytes: int
    analysis_config: dict[str, Any]
    frontend_sha256: dict[str, str]
    semantic_model: dict[str, str]
    producer_sha256: str

    def to_document(self) -> dict[str, Any]:
        return {
            "schema": CACHE_SCHEMA,
            "product": self.product,
            "input_sha256": self.input_sha256,
            "input_size_bytes": self.input_size_bytes,
            "analysis_config": self.analysis_config,
            "frontend_sha256": dict(sorted(self.frontend_sha256.items())),
            "semantic_model": dict(sorted(self.semantic_model.items())),
            "producer_sha256": self.producer_sha256,
        }

    def key(self) -> str:
        canonical = json.dumps(self.to_document(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def product_sha256(product: Any) -> str:
    canonical = json.dumps(product, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AnalysisCache:
    """Filesystem-backed immutable-hash cache (untracked directory)."""

    def __init__(self, directory: pathlib.Path) -> None:
        self.directory = pathlib.Path(directory)

    def path_for(self, key_inputs: CacheKeyInputs) -> pathlib.Path:
        return self.directory / f"{key_inputs.product}-{key_inputs.key()}.json"

    def put(self, key_inputs: CacheKeyInputs, product: Any) -> pathlib.Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        document = {
            "schema": ENTRY_SCHEMA,
            "key": key_inputs.key(),
            "key_inputs": key_inputs.to_document(),
            "product_sha256": product_sha256(product),
            "product": product,
        }
        path = self.path_for(key_inputs)
        path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return path

    def get(self, key_inputs: CacheKeyInputs) -> Any:
        path = self.path_for(key_inputs)
        if not path.is_file():
            raise CacheError("CACHE_MISS", str(path.name))
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise CacheError("CACHE_CORRUPT", str(exc)) from exc
        if document.get("schema") != ENTRY_SCHEMA:
            raise CacheError("CACHE_CORRUPT", "entry schema")
        if document.get("key") != key_inputs.key():
            raise CacheError("CACHE_STALE", "stored key does not match recomputed key")
        if document.get("key_inputs") != key_inputs.to_document():
            raise CacheError("CACHE_STALE", "key inputs do not match")
        product = document.get("product")
        if document.get("product_sha256") != product_sha256(product):
            raise CacheError("CACHE_CORRUPT", "product hash mismatch")
        return product
