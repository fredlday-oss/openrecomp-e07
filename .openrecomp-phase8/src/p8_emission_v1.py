#!/usr/bin/env python3
"""OpenRecomp Phase-8 deterministic host-source emission for the real ELF.

The emission set for the bounded fixture is exactly four stable files:

* `program.c` - the existing architecture-neutral host emitter output for the
  frozen neutral structure and the closed P8 MIPS32 rule table;
* `p8_image_v1.c` - the generated guest image contract unit (P8-05);
* `p8_runtime_support.c` - the OpenRecomp-authored bounded runtime support
  body (P8-05), composed with the generated contract declarations;
* `p8_driver.c` - the OpenRecomp-authored observable driver, composed with
  the generated contract declarations and the fixture identity.

Nothing in the emission set contains or executes original MIPS32 machine
code: the guest image is inert data for the runtime memory contract and all
guest semantics are generated C.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import p8_memory_contract_v1 as contract_v1
import p8_mips32_semantics_v1 as semantics
from openrecomp.host_emitter import emit_host_translation

EMISSION_VERSION = "1.0.0"
PROGRAM_NAME = "program.c"
IMAGE_NAME = "p8_image_v1.c"
SUPPORT_NAME = "p8_runtime_support.c"
DRIVER_NAME = "p8_driver.c"
EMISSION_NAMES = (PROGRAM_NAME, IMAGE_NAME, SUPPORT_NAME, DRIVER_NAME)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def emit_program(structure: Any) -> Any:
    """Emit the host translation set for one frozen neutral structure."""
    return emit_host_translation(
        structure.units,
        structure.classification,
        config=semantics.build_emitter_config(structure.discovery.entry_function_id),
    )


def build_build_set(
    structure: Any,
    contract: dict[str, Any],
    image: bytes,
    support_text: str,
    driver_text: str,
    fixture_sha256: str,
) -> dict[str, Any]:
    """Return the deterministic build input set with content hashes."""
    program = emit_program(structure)
    image_unit, support_unit = contract_v1.compose_runtime_sources(contract, image, support_text)
    header = contract_v1.render_image_header(contract)
    driver_unit = header + "\n" + f'#define P8_FIXTURE_SHA256 "{fixture_sha256}"\n' + driver_text
    files = {
        PROGRAM_NAME: program.source_text,
        image_unit[0]: image_unit[1],
        support_unit[0]: support_unit[1],
        DRIVER_NAME: driver_unit,
    }
    if tuple(files) != EMISSION_NAMES:
        raise ValueError(f"emission file set drift: {tuple(files)}")
    return {
        "emission_version": EMISSION_VERSION,
        "program": program,
        "files": files,
        "hashes": {name: sha256_text(text) for name, text in files.items()},
        "program_fingerprint": program.fingerprint(),
    }


def emission_document(build_set: dict[str, Any]) -> dict[str, Any]:
    return {
        "emission_version": build_set["emission_version"],
        "files": [
            {"name": name, "sha256": build_set["hashes"][name], "bytes": len(build_set["files"][name].encode("utf-8"))}
            for name in EMISSION_NAMES
        ],
        "program_fingerprint": build_set["program_fingerprint"],
        "program_functions": [
            translation.function_name for translation in build_set["program"].translations
        ],
    }


def emission_digest(build_set: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(emission_document(build_set), sort_keys=True).encode("utf-8")
    ).hexdigest()
