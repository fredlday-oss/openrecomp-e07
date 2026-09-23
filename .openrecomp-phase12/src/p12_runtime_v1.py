#!/usr/bin/env python3
"""OpenRecomp Phase-12 runtime composition V1.

The Phase-12 native runtime is the composed Phase-11 runtime (frozen Phase-9
platform runtime + the five anchored Phase-10 substitutions + the Phase-11 BIOS
layer and optional trace) with an additive Phase-12 layer:

* a forward-declaration and definition block for the synthetic B0 object window
  and the Phase-12 BIOS dispatcher, inserted after the frozen runtime
  prototypes;
* the guest-memory read/write functions routed through the synthetic window
  before main RAM;
* the Phase-11 host-call fallback replaced by the Phase-12 dispatcher, which
  chains to the Phase-11 dispatcher and then handles the B0 services;
* the Phase-12 BIOS fragment appended.

Every substitution is anchored and counted; a missing or ambiguous anchor fails
closed. The frozen Phase-9/10/11 sources remain byte-identical and auditable
through the reused records.
"""

from __future__ import annotations

import hashlib
import pathlib
from typing import Any

import p11_runtime_v1 as p11_runtime
import p12_services_v1 as services

RUNTIME_VERSION = "2.0.0"

ROOT = pathlib.Path(__file__).resolve().parents[2]

BIOS_FRAGMENT_PATH = ROOT / ".openrecomp-phase12" / "runtime" / "p12_bios_extension_v1.c"

DECLARATION_ANCHOR = (
    "int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);\n"
)

DECLARATION_BLOCK = (
    "\n"
    "/* P12 synthetic B0 object window and dispatcher (project-owned). */\n"
    "#define P12_SYNTH_BASE 0x1F000000u\n"
    "#define P12_SYNTH_SIZE 0x2000u\n"
    "static unsigned char g_p12_synth[P12_SYNTH_SIZE];\n"
    "static uint64_t g_p12_synth_reads;\n"
    "static uint64_t g_p12_synth_writes;\n"
    "static int p12_synth_translate(uint64_t address, uint64_t width, uint32_t *out_offset);\n"
    "int p12_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);\n"
)

READ_ANCHOR = (
    "    p9_runtime_init();\n"
    "    if (p9_translate_ram(address, width, &offset)) {\n"
    "        for (index = 0; index < width; ++index) {\n"
    "            value |= (uint64_t)g_p9_ram[offset + index] << (8u * index);\n"
    "        }\n"
)
READ_REPLACEMENT = (
    "    p9_runtime_init();\n"
    "    if (p12_synth_translate(address, width, &offset)) {\n"
    "        for (index = 0; index < width; ++index) {\n"
    "            value |= (uint64_t)g_p12_synth[offset + index] << (8u * index);\n"
    "        }\n"
    "        ++g_p9_memory_reads;\n"
    "        ++g_p12_synth_reads;\n"
    "        if (out_value != NULL) { *out_value = value; }\n"
    "        return P9_RT_OK;\n"
    "    }\n"
    "    if (p9_translate_ram(address, width, &offset)) {\n"
    "        for (index = 0; index < width; ++index) {\n"
    "            value |= (uint64_t)g_p9_ram[offset + index] << (8u * index);\n"
    "        }\n"
)

WRITE_ANCHOR = (
    "    p9_runtime_init();\n"
    "    if (p9_translate_ram(address, width, &offset)) {\n"
    "        for (index = 0; index < width; ++index) {\n"
    "            g_p9_ram[offset + index] = (unsigned char)((value >> (8u * index)) & UINT64_C(0xFF));\n"
    "        }\n"
)
WRITE_REPLACEMENT = (
    "    p9_runtime_init();\n"
    "    if (p12_synth_translate(address, width, &offset)) {\n"
    "        for (index = 0; index < width; ++index) {\n"
    "            g_p12_synth[offset + index] = (unsigned char)((value >> (8u * index)) & UINT64_C(0xFF));\n"
    "        }\n"
    "        ++g_p9_memory_writes;\n"
    "        ++g_p12_synth_writes;\n"
    "        return P9_RT_OK;\n"
    "    }\n"
    "    if (p9_translate_ram(address, width, &offset)) {\n"
    "        for (index = 0; index < width; ++index) {\n"
    "            g_p9_ram[offset + index] = (unsigned char)((value >> (8u * index)) & UINT64_C(0xFF));\n"
    "        }\n"
)

HOST_CALL_FALLBACK_ANCHOR = (
    "    return p11_bios_dispatch(service_id, argc, args, out_value);\n"
    "}\n"
)
HOST_CALL_FALLBACK_REPLACEMENT = (
    "    return p12_bios_dispatch(service_id, argc, args, out_value);\n"
    "}\n"
)

ERROR_CODES = (
    "BIOS_FRAGMENT_MISSING",
    "ANCHOR_MISSING",
    "ANCHOR_AMBIGUOUS",
)


class Phase12RuntimeError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise AssertionError(f"unknown Phase-12 runtime error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(path: pathlib.Path, code: str) -> str:
    if not path.is_file():
        raise Phase12RuntimeError(code, path.name)
    return path.read_text(encoding="utf-8")


def compose_runtime_source(
    sites: list[Any] | None = None,
    *,
    trace: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Compose the Phase-12 runtime source and return it with a provenance record."""
    base, base_record = p11_runtime.compose_runtime_source(sites, trace=trace)
    composed = base

    fragment = _read(BIOS_FRAGMENT_PATH, "BIOS_FRAGMENT_MISSING")
    layer: dict[str, Any] = {"runtime_version": RUNTIME_VERSION, "substitutions": []}

    for name, anchor, replacement in (
        ("synthetic-declarations", DECLARATION_ANCHOR, DECLARATION_ANCHOR + DECLARATION_BLOCK),
        ("synthetic-read", READ_ANCHOR, READ_REPLACEMENT),
        ("synthetic-write", WRITE_ANCHOR, WRITE_REPLACEMENT),
        ("bios-dispatcher-chain", HOST_CALL_FALLBACK_ANCHOR, HOST_CALL_FALLBACK_REPLACEMENT),
    ):
        occurrences = composed.count(anchor)
        if occurrences == 0:
            raise Phase12RuntimeError("ANCHOR_MISSING", name)
        if occurrences != 1:
            raise Phase12RuntimeError("ANCHOR_AMBIGUOUS", f"{name}:{occurrences}")
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
    layer["synthetic_window"] = services.service_surface_document()["synthetic_window"]
    layer["trace_enabled"] = bool(trace)
    return composed, layer
