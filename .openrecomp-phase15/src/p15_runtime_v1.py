#!/usr/bin/env python3
"""OpenRecomp Phase-15 runtime composition V1.

The Phase-15 native runtime is the composed Phase-14 runtime with an additive
Phase-15 layer:

* an anchored pre-dispatch inserted at the head of the frozen Phase-9
  ``p9_platform_read`` / ``p9_platform_write`` functions, so the Phase-15
  bounded interrupt/peripheral MMIO model observes an access before the frozen
  fail-closed platform boundary (an unmodelled address returns
  ``P15_MMIO_UNHANDLED`` and falls through unchanged);
* the Phase-15 MMIO fragment appended.

Every substitution is anchored and counted; a missing or ambiguous anchor fails
closed. The frozen Phase-9/10/11/12/13/14 sources remain byte-identical and
auditable through the reused records.
"""

from __future__ import annotations

import hashlib
import pathlib
from typing import Any

import p14_runtime_v1 as p14_runtime

RUNTIME_VERSION = "1.0.0"

ROOT = pathlib.Path(__file__).resolve().parents[2]

MMIO_FRAGMENT_PATH = ROOT / ".openrecomp-phase15" / "runtime" / "p15_mmio_extension_v1.c"
BIOS_FRAGMENT_PATH = ROOT / ".openrecomp-phase15" / "runtime" / "p15_bios_extension_v1.c"

BIOS_DECLARATION_ANCHOR = (
    "int p14_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);\n"
)
BIOS_DECLARATION_REPLACEMENT = (
    BIOS_DECLARATION_ANCHOR
    + "int p15_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);\n"
)

BIOS_FALLBACK_ANCHOR = (
    "    return p14_bios_dispatch(service_id, argc, args, out_value);\n"
    "}\n"
)
BIOS_FALLBACK_REPLACEMENT = (
    "    return p15_bios_dispatch(service_id, argc, args, out_value);\n"
    "}\n"
)

READ_ANCHOR = (
    "static int p9_platform_read(uint64_t address, uint32_t width_bits, uint64_t *out_value)\n"
    "{\n"
    "    uint32_t value = 0;\n"
)
READ_REPLACEMENT = (
    "#ifndef P15_MMIO_UNHANDLED\n"
    "#define P15_MMIO_UNHANDLED ((int)-1000)\n"
    "#endif\n"
    "int p15_mmio_read(uint64_t address, uint32_t width_bits, uint64_t *out_value);\n"
    "int p15_mmio_write(uint64_t address, uint32_t width_bits, uint32_t value);\n"
    "\n"
    + READ_ANCHOR
    + "    {\n"
    "        int p15_status = p15_mmio_read(address, width_bits, out_value);\n"
    "        if (p15_status != P15_MMIO_UNHANDLED) {\n"
    "            return p15_status;\n"
    "        }\n"
    "    }\n"
)

WRITE_ANCHOR = (
    "static int p9_platform_write(uint64_t address, uint32_t width_bits, uint32_t value)\n"
    "{\n"
    "    if (address == (uint64_t)P9_JOY_DATA) {\n"
)
WRITE_REPLACEMENT = (
    "static int p9_platform_write(uint64_t address, uint32_t width_bits, uint32_t value)\n"
    "{\n"
    "    {\n"
    "        int p15_status = p15_mmio_write(address, width_bits, value);\n"
    "        if (p15_status != P15_MMIO_UNHANDLED) {\n"
    "            return p15_status;\n"
    "        }\n"
    "    }\n"
    "    if (address == (uint64_t)P9_JOY_DATA) {\n"
)

ERROR_CODES = (
    "BIOS_FRAGMENT_MISSING",
    "ANCHOR_MISSING",
    "ANCHOR_AMBIGUOUS",
)


class Phase15RuntimeError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise AssertionError(f"unknown Phase-15 runtime error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(path: pathlib.Path, code: str) -> str:
    if not path.is_file():
        raise Phase15RuntimeError(code, path.name)
    return path.read_text(encoding="utf-8")


def compose_runtime_source(
    sites: list[Any] | None = None,
    *,
    trace: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Compose the Phase-15 runtime source and return it with a provenance record."""
    base, base_record = p14_runtime.compose_runtime_source(sites, trace=trace)
    composed = base

    mmio_fragment = _read(MMIO_FRAGMENT_PATH, "BIOS_FRAGMENT_MISSING")
    bios_fragment = _read(BIOS_FRAGMENT_PATH, "BIOS_FRAGMENT_MISSING")
    layer: dict[str, Any] = {"runtime_version": RUNTIME_VERSION, "substitutions": []}

    for name, anchor, replacement in (
        ("mmio-read-predispatch", READ_ANCHOR, READ_REPLACEMENT),
        ("mmio-write-predispatch", WRITE_ANCHOR, WRITE_REPLACEMENT),
        ("bios-dispatcher-declaration", BIOS_DECLARATION_ANCHOR, BIOS_DECLARATION_REPLACEMENT),
        ("bios-dispatcher-chain", BIOS_FALLBACK_ANCHOR, BIOS_FALLBACK_REPLACEMENT),
    ):
        occurrences = composed.count(anchor)
        if occurrences == 0:
            raise Phase15RuntimeError("ANCHOR_MISSING", name)
        if occurrences != 1:
            raise Phase15RuntimeError("ANCHOR_AMBIGUOUS", f"{name}:{occurrences}")
        layer["substitutions"].append(
            {
                "name": name,
                "anchor_sha256": sha256_text(anchor),
                "substitution_sha256": sha256_text(replacement),
            }
        )
        composed = composed.replace(anchor, replacement)

    layer["mmio_fragment"] = {
        "path": MMIO_FRAGMENT_PATH.relative_to(ROOT).as_posix(),
        "fragment_sha256": sha256_text(mmio_fragment),
    }
    layer["bios_fragment"] = {
        "path": BIOS_FRAGMENT_PATH.relative_to(ROOT).as_posix(),
        "fragment_sha256": sha256_text(bios_fragment),
    }
    composed = (composed.rstrip("\n") + "\n\n" + mmio_fragment.rstrip("\n")
                + "\n\n" + bios_fragment.rstrip("\n") + "\n")

    layer["base"] = base_record
    layer["composed_sha256"] = sha256_text(composed)
    layer["composed_bytes"] = len(composed.encode("utf-8"))
    layer["frozen_source_reused_verbatim"] = True
    layer["trace_enabled"] = bool(trace)
    return composed, layer
