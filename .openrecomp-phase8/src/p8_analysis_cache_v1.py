#!/usr/bin/env python3
"""OpenRecomp Phase-8 immutable-hash analysis cache (ACCELERATION_POLICY).

Cache keys follow the frozen `openrecomp-phase8-analysis-cache-v1` contract:
the key is the SHA-256 of the canonical key-input document.  A cache hit is
accepted only when the entry's recorded key inputs recompute to the requested
key; a filename or product-name match is never sufficient, and a stale entry
is rejected and reported instead of silently reused.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

CACHE_SCHEMA = "openrecomp-phase8-analysis-cache-v1"
ENTRY_SCHEMA = "openrecomp-phase8-analysis-cache-entry-v1"


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_key(
    *,
    product: str,
    input_sha256: str,
    input_size_bytes: int,
    analysis_config: Any,
    frontend_sha256: dict[str, str],
    semantic_model: dict[str, str],
    producer_sha256: str,
) -> str:
    document = {
        "schema": CACHE_SCHEMA,
        "product": product,
        "input_sha256": input_sha256,
        "input_size_bytes": input_size_bytes,
        "analysis_config": analysis_config,
        "frontend_sha256": frontend_sha256,
        "semantic_model": semantic_model,
        "producer_sha256": producer_sha256,
    }
    return hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()


class AnalysisCache:
    """Immutable-hash analysis cache with mandatory key verification."""

    def __init__(self, root: pathlib.Path, namespace: str) -> None:
        self.root = pathlib.Path(root) / namespace
        self.hits = 0
        self.misses = 0
        self.stale = 0

    def _entry_path(self, product: str, key: str) -> pathlib.Path:
        return self.root / product / f"{key}.json"

    def put(self, key_inputs: dict[str, Any], payload: Any) -> str:
        key = compute_key(**key_inputs)
        entry = {
            "schema": ENTRY_SCHEMA,
            "key": key,
            "key_inputs": key_inputs,
            "payload": payload,
        }
        path = self._entry_path(key_inputs["product"], key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(canonical_json(entry) + "\n", encoding="utf-8", newline="\n")
        return key

    def get(self, key_inputs: dict[str, Any]) -> Any | None:
        requested = compute_key(**key_inputs)
        path = self._entry_path(key_inputs["product"], requested)
        if not path.is_file():
            self.misses += 1
            return None
        entry = json.loads(path.read_text(encoding="utf-8"))
        if entry.get("schema") != ENTRY_SCHEMA or entry.get("key") != requested:
            self.stale += 1
            return None
        try:
            recomputed = compute_key(**entry["key_inputs"])
        except (KeyError, TypeError):
            self.stale += 1
            return None
        if recomputed != requested:
            self.stale += 1
            return None
        self.hits += 1
        return entry["payload"]

    def stats(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses, "stale": self.stale}
