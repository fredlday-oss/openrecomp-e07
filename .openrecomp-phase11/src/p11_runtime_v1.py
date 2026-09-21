#!/usr/bin/env python3
"""OpenRecomp Phase-11 runtime composition V1.

The Phase-11 native runtime is the composed Phase-10 runtime (the frozen
Phase-9 bounded PS1 platform runtime plus the five anchored Phase-10
substitutions) with an additive Phase-11 layer:

* a forward declaration of the Phase-11 BIOS dispatcher inserted before the
  Phase-10 ``or_rt_host_call`` definition;
* the Phase-10 host-call fallback return replaced by the Phase-11 BIOS
  dispatcher call;
* the Phase-11 BIOS service fragment appended (with the service-id macros
  generated from the Phase-11 service table, so the runtime and the emitter
  cannot drift);
* optionally the Phase-11 execution-trace fragment appended.

Every substitution is anchored, counted and hash-recorded; a missing or
ambiguous anchor fails closed. The frozen Phase-9 source and the Phase-10
substitutions remain byte-identical and auditable through the reused Phase-10
composition record.
"""

from __future__ import annotations

import hashlib
import pathlib
from typing import Any

import p10_runtime_v1 as p10_runtime
import p11_bios_v1 as bios
import p11_semantics_v1 as semantics

RUNTIME_VERSION = "1.1.0"

ROOT = pathlib.Path(__file__).resolve().parents[2]

BIOS_FRAGMENT_PATH = ROOT / ".openrecomp-phase11" / "runtime" / "p11_bios_extension_v1.c"
TRACE_FRAGMENT_PATH = ROOT / ".openrecomp-phase11" / "runtime" / "p11_trace_v1.c"

HOST_CALL_DEFINITION_ANCHOR = (
    "int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value)\n"
    "{\n"
    "    int status = P9_RT_OK;"
)
HOST_CALL_FALLBACK_ANCHOR = (
    "    return P9_RT_UNKNOWN_HOST_SERVICE;\n"
    "}\n"
)
SERVICE_ID_BLOCK_ANCHOR = (
    "/* P11_BIOS_SERVICE_IDS_BEGIN */\n"
    "/* P11_BIOS_SERVICE_IDS_END */\n"
)

HOST_CALL_DECLARATION_REPLACEMENT = (
    "int p11_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);\n\n"
    + HOST_CALL_DEFINITION_ANCHOR
)
HOST_CALL_FALLBACK_REPLACEMENT = (
    "    return p11_bios_dispatch(service_id, argc, args, out_value);\n}\n"
)

ERROR_CODES = (
    "BIOS_FRAGMENT_MISSING",
    "TRACE_FRAGMENT_MISSING",
    "ANCHOR_MISSING",
    "ANCHOR_AMBIGUOUS",
    "SERVICE_ID_BLOCK_MISSING",
    "SERVICE_TABLE_EMPTY",
)


class Phase11RuntimeError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise AssertionError(f"unknown Phase-11 runtime error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(path: pathlib.Path, code: str) -> str:
    if not path.is_file():
        raise Phase11RuntimeError(code, path.name)
    return path.read_text(encoding="utf-8")


def service_id_macros(service_ids: list[str]) -> tuple[str, dict[str, int]]:
    """Generate the runtime service-id macros from the declared service surface.

    Numeric ids follow the canonical sorted order of the service table, exactly
    as the generic runtime ABI assigns them; the generated macros are the single
    source of truth for the native dispatcher.
    """
    if not service_ids:
        raise Phase11RuntimeError("SERVICE_TABLE_EMPTY", "no BIOS service ids")
    lines: list[str] = []
    ids: dict[str, int] = {}
    table = semantics.build_service_table([])
    declared = list(table.service_ids)
    for service_id in service_ids:
        if service_id not in declared:
            declared.append(service_id)
    declared = sorted(set(declared))
    for position, service_id in enumerate(declared, start=1):
        if service_id not in service_ids:
            continue
        macro = "OR_RT_SERVICE_" + "".join(
            character.upper() if character.isalnum() else "_" for character in service_id
        )
        lines.append(f"#define {macro} UINT64_C({position})")
        ids[service_id] = position
    return "\n".join(lines) + "\n", ids


def _inject_service_ids(fragment: str, service_ids: list[str]) -> tuple[str, dict[str, Any]]:
    if SERVICE_ID_BLOCK_ANCHOR not in fragment:
        raise Phase11RuntimeError("SERVICE_ID_BLOCK_MISSING", "service id block")
    block, ids = service_id_macros(service_ids)
    text = fragment.replace(SERVICE_ID_BLOCK_ANCHOR, block)
    return text, {
        "service_ids": sorted(ids),
        "service_numeric_ids": dict(sorted(ids.items())),
        "block_sha256": sha256_text(block),
    }


def compose_runtime_source(
    sites: list[bios.BiosVectorSite] | None = None,
    *,
    trace: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Compose the Phase-11 runtime source and return it with a provenance record."""
    base, base_record = p10_runtime.compose_runtime_source()
    composed = base
    layer: dict[str, Any] = {"runtime_version": RUNTIME_VERSION, "substitutions": []}

    resolved = list(sites or [])
    service_ids = sorted({site.service_id for site in resolved if site.service_id})

    if resolved:
        fragment = _read(BIOS_FRAGMENT_PATH, "BIOS_FRAGMENT_MISSING")
        fragment, id_record = _inject_service_ids(fragment, service_ids)

        for name, anchor, replacement in (
            ("bios-dispatcher-declaration", HOST_CALL_DEFINITION_ANCHOR, HOST_CALL_DECLARATION_REPLACEMENT),
            ("bios-dispatcher-fallback", HOST_CALL_FALLBACK_ANCHOR, HOST_CALL_FALLBACK_REPLACEMENT),
        ):
            occurrences = composed.count(anchor)
            if occurrences == 0:
                raise Phase11RuntimeError("ANCHOR_MISSING", name)
            if occurrences != 1:
                raise Phase11RuntimeError("ANCHOR_AMBIGUOUS", f"{name}:{occurrences}")
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
            **id_record,
        }
        composed = composed.rstrip("\n") + "\n\n" + fragment.rstrip("\n") + "\n"

    if trace:
        trace_fragment = _read(TRACE_FRAGMENT_PATH, "TRACE_FRAGMENT_MISSING")
        if "p11_trace_block" in composed:
            raise Phase11RuntimeError("ANCHOR_AMBIGUOUS", "trace hook already present")
        layer["trace_fragment"] = {
            "path": TRACE_FRAGMENT_PATH.relative_to(ROOT).as_posix(),
            "fragment_sha256": sha256_text(trace_fragment),
        }
        composed = composed.rstrip("\n") + "\n\n" + trace_fragment.rstrip("\n") + "\n"

    layer["base"] = base_record
    layer["composed_sha256"] = sha256_text(composed)
    layer["composed_bytes"] = len(composed.encode("utf-8"))
    layer["frozen_source_reused_verbatim"] = True
    layer["bios_service_count"] = len(service_ids)
    layer["trace_enabled"] = bool(trace)
    return composed, layer
