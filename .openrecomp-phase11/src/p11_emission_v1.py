#!/usr/bin/env python3
"""OpenRecomp Phase-11 trace emission V1.

The Phase-11 trace emission set reuses the frozen Phase-10 emission machinery
and adds exactly one opt-in capability: a bounded, deterministic execution
trace produced by the additive host-emitter instrumentation hooks.

Composition:

* the guest image unit, the platform port map and the runtime composition are
  exactly the Phase-10 emission (the frozen Phase-9 bounded PS1 platform
  runtime plus the five anchored Phase-10 substitutions);
* the runtime support unit additionally carries the appended Phase-11 trace
  fragment (`.openrecomp-phase11/runtime/p11_trace_v1.c`), which defines the
  instrumentation hooks and stores only guest addresses, counts and digests;
* the generated program is emitted by the same architecture-neutral host
  emitter with the same Phase-10 semantic rule table, with the opt-in
  instrumentation configuration enabled;
* the observable driver is the additive Phase-11 driver, which prints the same
  core observables plus the trace.

The uninstrumented Phase-10 program identity is always computed as well, so a
gate can prove that instrumentation changes no guest semantics. Nothing in the
emission set executes original MIPS machine code: the guest image is inert data
and all executed guest semantics are generated C.
"""

from __future__ import annotations

import dataclasses
import hashlib
import pathlib
from typing import Any

import p9_emission_v1 as p9_emission
import p10_emission_v1 as p10_emission
import p10_mips32_semantics_v1 as semantics
from openrecomp.host_emitter import HostInstrumentation, emit_host_translation

EMISSION_VERSION = "1.1.0"

ROOT = pathlib.Path(__file__).resolve().parents[2]

PROGRAM_NAME = p10_emission.PROGRAM_NAME
IMAGE_NAME = p10_emission.IMAGE_NAME
SUPPORT_NAME = p10_emission.SUPPORT_NAME
DRIVER_NAME = p10_emission.DRIVER_NAME
EMISSION_NAMES = p10_emission.EMISSION_NAMES

TRACE_FRAGMENT_PATH = ROOT / ".openrecomp-phase11" / "runtime" / "p11_trace_v1.c"
TRACE_DRIVER_PATH = ROOT / ".openrecomp-phase11" / "runtime" / "p11_observable_driver_v1.c"

TRACE_INSTRUMENTATION = HostInstrumentation(
    function_entry_hook="p11_trace_function",
    block_entry_hook="p11_trace_block",
    indirect_failure_hook="p11_trace_indirect_failure",
)

TRACE_CONFIGURATION = {
    "hooks": TRACE_INSTRUMENTATION.to_document(),
    "block_first_capacity": 256,
    "block_ring_capacity": 4096,
    "table_capacity": 8192,
    "last_window_print_limit": 512,
    "guest_semantics_unchanged": "the generated code still calls or_fail at every fail-closed site",
}

ERROR_CODES = (
    "TRACE_FRAGMENT_MISSING",
    "TRACE_DRIVER_MISSING",
    "TRACE_ANCHOR_MISSING",
    "TRACE_ANCHOR_AMBIGUOUS",
)


class TraceEmissionError(ValueError):
    """Fail-closed trace emission error with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        if code not in ERROR_CODES:
            raise AssertionError(f"unknown trace emission error code: {code}")
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def trace_fragment_source() -> tuple[str, str]:
    if not TRACE_FRAGMENT_PATH.is_file():
        raise TraceEmissionError("TRACE_FRAGMENT_MISSING", TRACE_FRAGMENT_PATH.name)
    text = TRACE_FRAGMENT_PATH.read_text(encoding="utf-8")
    return text, sha256_text(text)


def trace_driver_source() -> tuple[str, str]:
    if not TRACE_DRIVER_PATH.is_file():
        raise TraceEmissionError("TRACE_DRIVER_MISSING", TRACE_DRIVER_PATH.name)
    text = TRACE_DRIVER_PATH.read_text(encoding="utf-8")
    return text, sha256_text(text)


def instrumented_program(structure: Any) -> Any:
    """Emit the guest program with the opt-in trace instrumentation enabled."""
    config = dataclasses.replace(
        semantics.build_emitter_config(structure.discovery.entry_function_id),
        instrumentation=TRACE_INSTRUMENTATION,
    )
    return emit_host_translation(structure.units, structure.classification, config=config)


def compose_trace_support(base_support: str) -> tuple[str, dict[str, Any]]:
    """Append the Phase-11 trace fragment to the frozen Phase-10 runtime source."""
    fragment, fragment_hash = trace_fragment_source()
    anchor = (
        "int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value)\n"
        "{\n"
        "    int status = P9_RT_OK;"
    )
    count = base_support.count(anchor)
    if count == 0:
        raise TraceEmissionError("TRACE_ANCHOR_MISSING", "or_rt_host_call definition")
    if count != 1:
        raise TraceEmissionError("TRACE_ANCHOR_AMBIGUOUS", str(count))
    if "p11_trace_block" in base_support:
        raise TraceEmissionError("TRACE_ANCHOR_AMBIGUOUS", "trace hook already present")
    composed = base_support.rstrip("\n") + "\n\n" + fragment.rstrip("\n") + "\n"
    record = {
        "base_sha256": sha256_text(base_support),
        "fragment_path": TRACE_FRAGMENT_PATH.relative_to(ROOT).as_posix(),
        "fragment_sha256": fragment_hash,
        "composed_sha256": sha256_text(composed),
        "composed_bytes": len(composed.encode("utf-8")),
        "appended_verbatim": True,
    }
    return composed, record


def build_trace_build_set(
    structure: Any,
    contract: dict[str, Any],
    flat: bytes,
    fixture_sha256: str,
) -> dict[str, Any]:
    """The Phase-11 trace emission set plus the uninstrumented comparison identity."""
    base = p10_emission.build_build_set(structure, contract, flat, fixture_sha256, driver="phase10")
    program = instrumented_program(structure)
    support_text, trace_record = compose_trace_support(base["files"][SUPPORT_NAME])
    driver_text, driver_hash = trace_driver_source()
    header = p9_emission.render_image_header(contract)
    driver_unit = header + "\n" + f'#define P9_FIXTURE_SHA256 "{fixture_sha256}"\n' + driver_text
    files = {
        PROGRAM_NAME: program.source_text,
        IMAGE_NAME: base["files"][IMAGE_NAME],
        SUPPORT_NAME: support_text,
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
        "base_program_fingerprint": base["program_fingerprint"],
        "base_hashes": base["hashes"],
        "runtime_composition": base["runtime_composition"],
        "trace": trace_record,
        "trace_configuration": TRACE_CONFIGURATION,
        "trace_instrumentation": TRACE_INSTRUMENTATION.to_document(),
        "driver": "phase11-trace",
        "driver_sha256": driver_hash,
        "semantics": base["semantics"],
        "instrumentation_checks": {
            "function_entry_hook_calls": program.source_text.count("p11_trace_function(UINT64_C("),
            "block_entry_hook_calls": program.source_text.count("p11_trace_block(UINT64_C("),
            "indirect_failure_hook_calls": program.source_text.count("p11_trace_indirect_failure(UINT64_C("),
        },
    }


def uninstrumented_build_set(
    structure: Any,
    contract: dict[str, Any],
    flat: bytes,
    fixture_sha256: str,
) -> dict[str, Any]:
    """The Phase-10 comparison emission set (byte-identical to the frozen identity)."""
    return p10_emission.build_build_set(structure, contract, flat, fixture_sha256, driver="phase10")


def build_bios_build_set(
    structure: Any,
    base_structure: Any,
    contract: dict[str, Any],
    flat: bytes,
    fixture_sha256: str,
    *,
    sites: Any,
    trace: bool,
    guarded_resolved_indirect: bool = False,
) -> dict[str, Any]:
    """The Phase-11 BIOS-service emission set (optionally instrumented).

    The runtime support unit is the composed Phase-10 runtime plus the Phase-11
    BIOS layer (and the trace fragment when instrumented); the program is
    emitted with the Phase-11 semantic rules that carry the explicit BIOS host
    calls; the driver is the Phase-11 trace driver when instrumented and the
    frozen Phase-10 driver otherwise. ``base_structure`` is the frozen
    Phase-10 structure (no BIOS overlay), used only for the uninstrumented
    comparison identity.
    """
    import p11_runtime_v1 as p11_runtime
    import p11_semantics_v1 as p11_semantics

    base = None
    base_error = None
    try:
        base = p10_emission.build_build_set(base_structure, contract, flat, fixture_sha256, driver="phase10")
    except Exception as exc:  # the frozen Phase-10 rule table may not cover a newly added op
        base_error = f"{type(exc).__name__}: {exc}"
    instrumentation = TRACE_INSTRUMENTATION if trace else None
    config = p11_semantics.build_emitter_config(
        structure.discovery.entry_function_id, list(sites), instrumentation=instrumentation,
        guarded_resolved_indirect=guarded_resolved_indirect,
    )
    program = emit_host_translation(structure.units, structure.classification, config=config)
    support_text, runtime_record = p11_runtime.compose_runtime_source(list(sites), trace=trace)
    image_unit, support_unit = p9_emission.compose_runtime_sources(contract, flat, support_text)
    header = p9_emission.render_image_header(contract)
    if trace:
        driver_text, driver_hash = trace_driver_source()
        driver = "phase11-trace"
    else:
        driver_text, driver_hash = p10_emission.phase10_driver_source()
        driver = "phase10"
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
        "base_program_fingerprint": None if base is None else base["program_fingerprint"],
        "base_hashes": None if base is None else base["hashes"],
        "base_error": base_error,
        "runtime_composition": runtime_record,
        "trace": runtime_record.get("trace_fragment"),
        "trace_configuration": TRACE_CONFIGURATION if trace else None,
        "trace_instrumentation": TRACE_INSTRUMENTATION.to_document() if trace else None,
        "driver": driver,
        "driver_sha256": driver_hash,
        "semantics": p11_semantics.semantics_document(list(sites)),
        "bios_sites": [site.to_document() for site in sites],
        "instrumentation_checks": {
            "function_entry_hook_calls": program.source_text.count("p11_trace_function(UINT64_C("),
            "block_entry_hook_calls": program.source_text.count("p11_trace_block(UINT64_C("),
            "indirect_failure_hook_calls": program.source_text.count("p11_trace_indirect_failure(UINT64_C("),
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
        "base_program_fingerprint": build_set["base_program_fingerprint"],
        "base_hashes": dict(sorted(build_set["base_hashes"].items())),
        "runtime_composition": build_set["runtime_composition"],
        "trace": build_set["trace"],
        "trace_configuration": build_set["trace_configuration"],
        "trace_instrumentation": build_set["trace_instrumentation"],
        "instrumentation_checks": build_set["instrumentation_checks"],
        "driver": build_set["driver"],
        "driver_sha256": build_set["driver_sha256"],
        "semantics": build_set["semantics"],
    }


def emission_digest(build_set: dict[str, Any]) -> str:
    import json

    return hashlib.sha256(
        json.dumps(emission_document(build_set), sort_keys=True).encode("utf-8")
    ).hexdigest()
