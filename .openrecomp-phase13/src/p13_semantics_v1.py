#!/usr/bin/env python3
"""OpenRecomp Phase-13 semantics and service surface V1.

Reuses the frozen Phase-12 semantic-rule builder (which already supports both
``jr`` and ``jalr`` BIOS vector sites) and adds the Phase-13 controlled
synthetic pad-hook rules and service ids. Nothing is inferred from an address or
opcode.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in (".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src"):
    sys.path.insert(0, str(ROOT / extra))

import p12_semantics_v1 as p12_semantics  # noqa: E402

import p13_pad_hook_v1 as pad_hook  # noqa: E402
import p13_services_v1 as services  # noqa: E402

SEMANTICS_VERSION = "3.0.0"

ARCHITECTURE = p12_semantics.ARCHITECTURE


def bios_rules(sites: list[Any]):
    return p12_semantics.bios_rules(sites)


def build_semantics(sites: list[Any]):
    return pad_hook.build_semantics(sites)


def build_service_table(sites: list[Any]):
    return pad_hook.build_service_table(sites)


def build_emitter_config(
    entry_function: str,
    sites: list[Any],
    *,
    instrumentation: Any | None = None,
    guarded_resolved_indirect: bool = False,
):
    return pad_hook.build_emitter_config(
        entry_function,
        sites,
        instrumentation=instrumentation,
        guarded_resolved_indirect=guarded_resolved_indirect,
    )


def semantics_document(sites: list[Any]) -> dict[str, Any]:
    document = pad_hook.semantics_document(sites)
    document["semantics_version"] = SEMANTICS_VERSION
    document["c0_services"] = services.service_surface_document()["c0_services"]
    document["b0_additions"] = services.service_surface_document()["b0_additions"]
    return document
