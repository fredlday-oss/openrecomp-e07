#!/usr/bin/env python3
"""OpenRecomp Phase-10 deterministic host-source emission V1.

The Phase-10 emission set reuses the frozen Phase-9 emission machinery for the
guest-image contract, the platform port map and the observable driver, and
substitutes only:

* the generated program, emitted through the existing architecture-neutral host
  emitter with the Phase-10 semantic rule table (the frozen phase-8 rules plus
  the additive Phase-10 rules);
* the runtime support unit, which is the frozen Phase-9 bounded PS1 platform
  runtime with its host-call stub replaced by the Phase-10 service dispatch
  (see `p10_runtime_v1`).

Nothing in the emission set executes original MIPS machine code: the guest
image is inert data and all executed guest semantics are generated C.
"""

from __future__ import annotations

import hashlib
import pathlib
from typing import Any

import p9_emission_v1 as p9_emission
import p10_mips32_semantics_v1 as semantics
import p10_runtime_v1 as p10_runtime
from openrecomp.host_emitter import emit_host_translation

EMISSION_VERSION = "1.0.0"

ROOT = pathlib.Path(__file__).resolve().parents[2]

PROGRAM_NAME = p9_emission.PROGRAM_NAME
IMAGE_NAME = p9_emission.IMAGE_NAME
SUPPORT_NAME = p9_emission.SUPPORT_NAME
DRIVER_NAME = p9_emission.DRIVER_NAME
EMISSION_NAMES = p9_emission.EMISSION_NAMES
PLATFORM_PORTS = p9_emission.PLATFORM_PORTS

DRIVER_SOURCE = ROOT / ".openrecomp-phase9" / "runtime" / "p9_observable_driver.c"
DRIVER_MANIFEST_ENTRY = ".openrecomp-phase9/runtime/p9_observable_driver.c"
PHASE10_DRIVER_SOURCE = ROOT / ".openrecomp-phase10" / "runtime" / "p10_observable_driver_v1.c"

#: Driver selection. `frozen` keeps the Phase-9 observable record (used by the
#: P10-03/P10-05 emission identities); `phase10` adds the bounded-execution
#: counters and the typed platform event transcripts.
DRIVERS = ("frozen", "phase10")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _manifest_hash(relative: str) -> str:
    manifest = ROOT / ".openrecomp-phase9" / "SOURCE_SHA256SUMS.txt"
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, path = line.split(" *", 1)
        if path == relative:
            return digest
    raise RuntimeError(f"manifest entry missing: {relative}")


def driver_source() -> tuple[str, str]:
    """The frozen Phase-9 observable driver, hash-verified against its manifest."""
    text = DRIVER_SOURCE.read_text(encoding="utf-8")
    expected = _manifest_hash(DRIVER_MANIFEST_ENTRY)
    observed = sha256_text(text)
    if observed != expected:
        raise RuntimeError(f"frozen driver hash mismatch: {observed}")
    return text, observed


def runtime_support_text() -> tuple[str, dict[str, Any]]:
    return p10_runtime.compose_runtime_source()


def emit_program(structure: Any) -> Any:
    return emit_host_translation(
        structure.units,
        structure.classification,
        config=semantics.build_emitter_config(structure.discovery.entry_function_id),
    )


def phase10_driver_source() -> tuple[str, str]:
    """The additive Phase-10 observable driver with its content hash."""
    text = PHASE10_DRIVER_SOURCE.read_text(encoding="utf-8")
    return text, sha256_text(text)


def build_build_set(
    structure: Any,
    contract: dict[str, Any],
    flat: bytes,
    fixture_sha256: str,
    *,
    driver: str = "frozen",
) -> dict[str, Any]:
    if driver not in DRIVERS:
        raise ValueError(f"unknown driver selection: {driver}")
    program = emit_program(structure)
    support_text, runtime_record = runtime_support_text()
    image_unit, support_unit = p9_emission.compose_runtime_sources(contract, flat, support_text)
    header = p9_emission.render_image_header(contract)
    if driver == "frozen":
        driver_text, driver_hash = driver_source()
    else:
        driver_text, driver_hash = phase10_driver_source()
    driver_unit = header + "\n" + f'#define P9_FIXTURE_SHA256 "{fixture_sha256}"\n' + driver_text
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
        "runtime_composition": runtime_record,
        "driver": driver,
        "driver_sha256": driver_hash,
        "driver_manifest_sha256": _manifest_hash(DRIVER_MANIFEST_ENTRY) if driver == "frozen" else None,
        "semantics": {
            "rules_total": len(semantics.semantics_rules()),
            "added_ops": list(semantics.ADDED_OPS),
            "service_ids": list(semantics.build_service_table().service_ids),
        },
    }


def emission_document(build_set: dict[str, Any]) -> dict[str, Any]:
    return {
        "emission_version": build_set["emission_version"],
        "files": [
            {
                "name": name,
                "sha256": build_set["hashes"][name],
                "bytes": len(build_set["files"][name].encode("utf-8")),
            }
            for name in EMISSION_NAMES
        ],
        "program_fingerprint": build_set["program_fingerprint"],
        "program_functions": [
            translation.function_name for translation in build_set["program"].translations
        ],
        "platform_ports": {name: f"0x{value:08x}" for name, value in sorted(PLATFORM_PORTS.items())},
        "runtime_composition": build_set["runtime_composition"],
        "driver": build_set["driver"],
        "event_transcript_capacity": p10_runtime.EVENT_CAPACITY,
        "gpu_status_read_stub": f"0x{p10_runtime.GPU_READ_STUB:08x}",
        "phase9_event_transcript_capacity": p10_runtime.PHASE9_EVENT_CAPACITY,
        "driver_sha256": build_set["driver_sha256"],
        "semantics": build_set["semantics"],
    }


def emission_digest(build_set: dict[str, Any]) -> str:
    import json

    return hashlib.sha256(
        json.dumps(emission_document(build_set), sort_keys=True).encode("utf-8")
    ).hexdigest()
