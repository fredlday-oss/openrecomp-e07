#!/usr/bin/env python3
"""OpenRecomp Phase-10 private Hercules frontier reproduction V1.

Reproduces the frozen Phase-9 private frontier through the unchanged Phase-9
path (PS-X EXE ingestion -> PS1 memory contract -> frozen Phase-3 decode/
frontier -> frozen Phase-8 neutral-structure bridge) and records only
non-reconstructive metadata.

The inherited Phase-9 frontier is:

* 4068 reachable words;
* first unresolved blocker ``break`` at ``0x80013390`` (external trap);
* structural failure ``CONTROL_WITHOUT_DELAY_SLOT``;
* bounded execution ``NOT_ATTEMPTED_BLOCKED_BY_FIRST_UNRESOLVED``.

This module adds no capability and never fabricates structure for private code.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

import p9_image_bridge_v1 as bridge
import p9_memory_map_v1 as memory_map
import p9_psx_exe_v1 as psx

FRONTIER_VERSION = "1.0.0"

INHERITED = {
    "reachable_words": 4068,
    "reachable_supported_words": 3972,
    "reachable_unsupported_words": 96,
    "reachable_invalid_words": 0,
    "exception_site_count": 3,
    "first_blocker_site": "0x80013390",
    "first_blocker_kind": "external-trap",
    "first_blocker_op": "break",
    "structure_error_code": "CONTROL_WITHOUT_DELAY_SLOT",
    "bios_candidates": 3,
    "bios_unknown": 19,
    "io_accesses": 0,
    "bounded_execution_status": "NOT_ATTEMPTED_BLOCKED_BY_FIRST_UNRESOLVED",
}


def load_image(fixture_path: pathlib.Path) -> tuple[psx.PsxExeImage, dict[str, Any], bytes]:
    image = psx.ingest(fixture_path.read_bytes())
    contract = memory_map.build_contract(image)
    flat = memory_map.flat_image(image)
    return image, contract, flat


def analyze(image: psx.PsxExeImage, contract: dict[str, Any], flat: bytes) -> Any:
    return bridge.analyze(image, contract, flat)


def reproduce(fixture_path: pathlib.Path) -> dict[str, Any]:
    """Run the frozen pipeline and compare against the inherited frontier."""
    image, contract, flat = load_image(fixture_path)
    pipeline = analyze(image, contract, flat)
    summary = pipeline.summary
    blocker = pipeline.first_blocker or {}
    structure_error = pipeline.structure_error or {}
    observed = {
        "reachable_words": summary.get("reachable_words"),
        "reachable_supported_words": summary.get("reachable_supported_words"),
        "reachable_unsupported_words": summary.get("reachable_unsupported_words"),
        "reachable_invalid_words": summary.get("reachable_invalid_words"),
        "exception_site_count": summary.get("exception_site_count"),
        "first_blocker_site": blocker.get("site_hex"),
        "first_blocker_kind": blocker.get("kind"),
        "first_blocker_op": blocker.get("op"),
        "structure_error_code": structure_error.get("code"),
    }
    mismatches = {
        key: {"inherited": INHERITED[key], "observed": value}
        for key, value in sorted(observed.items())
        if INHERITED[key] != value
    }
    return {
        "frontier_version": FRONTIER_VERSION,
        "reproduced": not mismatches,
        "mismatches": mismatches,
        "observed": observed,
        "identity": image.identity(),
        "contract_digest": memory_map.contract_digest(contract),
        "pipeline_digest": pipeline.digest(),
        "summary": summary,
        "structure_error": pipeline.structure_error,
        "first_blocker": pipeline.first_blocker,
        "structure_available": pipeline.structure_summary is not None,
        "bounded_execution": {
            "status": INHERITED["bounded_execution_status"],
            "native_execution_of_private_code": False,
            "private_code_committed": False,
        },
    }


def digest(document: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode("utf-8")).hexdigest()
