#!/usr/bin/env python3
"""OpenRecomp Phase-13 runtime composition V1.

The Phase-13 native runtime is the composed Phase-12 runtime with an additive
Phase-13 layer:

* a forward declaration of the Phase-13 BIOS dispatcher inserted after the
  Phase-12 dispatcher declaration;
* the Phase-12 host-call fallback replaced by the Phase-13 dispatcher call, so
  the Phase-13 dispatcher chains the Phase-12 and Phase-11 dispatchers;
* the Phase-13 C0 interrupt-routine queue fragment appended.

Every substitution is anchored and counted; a missing or ambiguous anchor fails
closed. The frozen Phase-9/10/11/12 sources remain byte-identical and auditable
through the reused records.
"""

from __future__ import annotations

import hashlib
import pathlib
from typing import Any

import p12_runtime_v1 as p12_runtime

RUNTIME_VERSION = "3.0.0"

ROOT = pathlib.Path(__file__).resolve().parents[2]

BIOS_FRAGMENT_PATH = ROOT / ".openrecomp-phase13" / "runtime" / "p13_bios_extension_v1.c"

DECLARATION_ANCHOR = (
    "int p12_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);\n"
)
DECLARATION_REPLACEMENT = (
    DECLARATION_ANCHOR
    + "int p13_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);\n"
)

HOST_CALL_FALLBACK_ANCHOR = (
    "    return p12_bios_dispatch(service_id, argc, args, out_value);\n"
    "}\n"
)
HOST_CALL_FALLBACK_REPLACEMENT = (
    "    return p13_bios_dispatch(service_id, argc, args, out_value);\n"
    "}\n"
)

ERROR_CODES = (
    "BIOS_FRAGMENT_MISSING",
    "ANCHOR_MISSING",
    "ANCHOR_AMBIGUOUS",
)


class Phase13RuntimeError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise AssertionError(f"unknown Phase-13 runtime error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(path: pathlib.Path, code: str) -> str:
    if not path.is_file():
        raise Phase13RuntimeError(code, path.name)
    return path.read_text(encoding="utf-8")


def compose_runtime_source(
    sites: list[Any] | None = None,
    *,
    trace: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Compose the Phase-13 runtime source and return it with a provenance record."""
    base, base_record = p12_runtime.compose_runtime_source(sites, trace=trace)
    composed = base

    fragment = _read(BIOS_FRAGMENT_PATH, "BIOS_FRAGMENT_MISSING")
    layer: dict[str, Any] = {"runtime_version": RUNTIME_VERSION, "substitutions": []}

    for name, anchor, replacement in (
        ("c0-dispatcher-declaration", DECLARATION_ANCHOR, DECLARATION_REPLACEMENT),
        ("c0-dispatcher-chain", HOST_CALL_FALLBACK_ANCHOR, HOST_CALL_FALLBACK_REPLACEMENT),
    ):
        occurrences = composed.count(anchor)
        if occurrences == 0:
            raise Phase13RuntimeError("ANCHOR_MISSING", name)
        if occurrences != 1:
            raise Phase13RuntimeError("ANCHOR_AMBIGUOUS", f"{name}:{occurrences}")
        layer["substitutions"].append(
            {
                "name": name,
                "anchor_sha256": sha256_text(anchor),
                "substitution_sha256": sha256_text(replacement),
            }
        )
        composed = composed.replace(anchor, replacement)

    layer["bios_fragment"] = {
        "path": BIOS_FRAGMENT_PATH.relative_to(ROOT).as_posix(),
        "fragment_sha256": sha256_text(fragment),
    }
    composed = composed.rstrip("\n") + "\n\n" + fragment.rstrip("\n") + "\n"

    layer["base"] = base_record
    layer["composed_sha256"] = sha256_text(composed)
    layer["composed_bytes"] = len(composed.encode("utf-8"))
    layer["frozen_source_reused_verbatim"] = True
    layer["trace_enabled"] = bool(trace)
    return composed, layer
