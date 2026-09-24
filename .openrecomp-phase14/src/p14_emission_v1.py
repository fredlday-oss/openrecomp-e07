#!/usr/bin/env python3
"""OpenRecomp Phase-14 emission V1.

Reuses the frozen Phase-13 emission machinery. The additions are the Phase-14
BIOS service surface, the Phase-14 runtime composition (C0 / early-card
continuation dispatcher) and an additive Phase-14 observable layer on top of the
Phase-13 observable driver.
"""

from __future__ import annotations

import hashlib
import pathlib
from typing import Any

import p9_emission_v1 as p9_emission
import p10_emission_v1 as p10_emission
import p12_emission_v1 as p12_emission
import p13_emission_v1 as p13_emission
from openrecomp.host_emitter import emit_host_translation

import p14_runtime_v1 as p14_runtime
import p14_semantics_v1 as p14_semantics
import p14_services_v1 as services

EMISSION_VERSION = "4.0.0"

ROOT = pathlib.Path(__file__).resolve().parents[2]

PROGRAM_NAME = p10_emission.PROGRAM_NAME
IMAGE_NAME = p10_emission.IMAGE_NAME
SUPPORT_NAME = p10_emission.SUPPORT_NAME
DRIVER_NAME = p10_emission.DRIVER_NAME
EMISSION_NAMES = p10_emission.EMISSION_NAMES

DRIVER_DECLARATION_ANCHOR = "uint32_t p13_intrp_chain_count(void);\n"
DRIVER_DECLARATION_BLOCK = (
    "uint32_t p14_c0_table_address(void);\n"
    "uint32_t p14_c0_exception_handler_address(void);\n"
    "uint32_t p14_card_handler_address(void);\n"
    "uint32_t p14_card_continuation_address(void);\n"
    "uint32_t p14_card_patch_offset(void);\n"
    "uint32_t p14_c0_ready(void);\n"
    "uint64_t p14_getc0_calls(void);\n"
    "uint64_t p14_continuation_calls(void);\n"
    "uint64_t p14_continuation_last(void);\n"
    "uint64_t p14_continuation_failures(void);\n"
    "uint64_t p14_bu_init_calls(void);\n"
    "uint64_t p14_abs_calls(void);\n"
    "uint64_t p14_puts_calls(void);\n"
    "uint64_t p14_mflo_calls(void);\n"
    "uint64_t p14_card_patch_fnv(void);\n"
    "uint64_t p14_card_patch_writes(void);\n"
)
DRIVER_PRINT_ANCHOR = "    return 0;\n}\n"
DRIVER_PRINT_BLOCK = (
    "    printf(\"p14_c0_ready=%u\\n\", (unsigned)p14_c0_ready());\n"
    "    printf(\"p14_getc0_calls=%llu\\n\", (unsigned long long)p14_getc0_calls());\n"
    "    printf(\"p14_c0_table_address=0x%08x\\n\", (unsigned)p14_c0_table_address());\n"
    "    printf(\"p14_c0_exception_handler_address=0x%08x\\n\", (unsigned)p14_c0_exception_handler_address());\n"
    "    printf(\"p14_card_handler_address=0x%08x\\n\", (unsigned)p14_card_handler_address());\n"
    "    printf(\"p14_card_continuation_address=0x%08x\\n\", (unsigned)p14_card_continuation_address());\n"
    "    printf(\"p14_card_patch_offset=0x%08x\\n\", (unsigned)p14_card_patch_offset());\n"
    "    printf(\"p14_card_patch_fnv=0x%016llx\\n\", (unsigned long long)p14_card_patch_fnv());\n"
    "    printf(\"p14_card_patch_writes=%llu\\n\", (unsigned long long)p14_card_patch_writes());\n"
    "    printf(\"p14_bu_init_calls=%llu\\n\", (unsigned long long)p14_bu_init_calls());\n"
    "    printf(\"p14_abs_calls=%llu\\n\", (unsigned long long)p14_abs_calls());\n"
    "    printf(\"p14_puts_calls=%llu\\n\", (unsigned long long)p14_puts_calls());\n"
    "    printf(\"p14_mflo_calls=%llu\\n\", (unsigned long long)p14_mflo_calls());\n"
    "    printf(\"p14_continuation_calls=%llu\\n\", (unsigned long long)p14_continuation_calls());\n"
    "    printf(\"p14_continuation_last=0x%08llx\\n\", (unsigned long long)p14_continuation_last());\n"
    "    printf(\"p14_continuation_failures=%llu\\n\", (unsigned long long)p14_continuation_failures());\n"
    "    {\n"
    "        const unsigned char *p14_ram = p9_runtime_memory();\n"
    "        uint32_t p14_off = 0x2ed90u;\n"
    "        uint32_t p14_v = (uint32_t)p14_ram[p14_off]\n"
    "            | ((uint32_t)p14_ram[p14_off + 1u] << 8)\n"
    "            | ((uint32_t)p14_ram[p14_off + 2u] << 16)\n"
    "            | ((uint32_t)p14_ram[p14_off + 3u] << 24);\n"
    "        printf(\"p14_ram_2ed90=0x%08x\\n\", (unsigned)p14_v);\n"
    "    }\n"
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def phase14_driver_source() -> tuple[str, str]:
    """The Phase-13 observable driver plus the additive Phase-14 observable layer."""
    text, _ = p13_emission.phase13_driver_source()
    if text.count(DRIVER_DECLARATION_ANCHOR) != 1:
        raise ValueError("p14 driver declaration anchor missing or ambiguous")
    if text.count(DRIVER_PRINT_ANCHOR) != 1:
        raise ValueError("p14 driver print anchor missing or ambiguous")
    text = text.replace(
        DRIVER_DECLARATION_ANCHOR,
        DRIVER_DECLARATION_BLOCK + DRIVER_DECLARATION_ANCHOR,
    )
    text = text.replace(DRIVER_PRINT_ANCHOR, DRIVER_PRINT_BLOCK + DRIVER_PRINT_ANCHOR)
    return text, sha256_text(text)


def build_build_set(
    structure: Any,
    base_structure: Any,
    contract: dict[str, Any],
    flat: bytes,
    fixture_sha256: str,
    *,
    sites: list[Any],
    trace: bool,
    guarded_resolved_indirect: bool = False,
    extra_a0: tuple[int, ...] = (),
    extra_c0: tuple[int, ...] = (0x02, 0x03),
    extra_b0: tuple[int, ...] = (0x12, 0x13, 0x14, 0x4A, 0x4B, 0x4C),
    p14_b0: tuple[int, ...] = (),
    p14_a0: tuple[int, ...] = (),
) -> dict[str, Any]:
    """The Phase-14 BIOS-service emission set (optionally instrumented)."""
    services.install(extra_a0, extra_c0, extra_b0, p14_b0=p14_b0, p14_a0=p14_a0)
    instrumentation = p12_emission.p11_emission_instrumentation() if trace else None
    config = p14_semantics.build_emitter_config(
        structure.discovery.entry_function_id, list(sites),
        instrumentation=instrumentation,
        guarded_resolved_indirect=guarded_resolved_indirect,
    )
    program = emit_host_translation(structure.units, structure.classification, config=config)
    support_text, runtime_record = p14_runtime.compose_runtime_source(
        p14_semantics.runtime_sites(list(sites)), trace=trace
    )
    image_unit, support_unit = p9_emission.compose_runtime_sources(contract, flat, support_text)
    header = p9_emission.render_image_header(contract)
    if trace:
        driver_text, driver_hash = phase14_driver_source()
        driver = "phase14-trace"
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
        "base_program_fingerprint": None,
        "base_hashes": None,
        "base_error": None,
        "runtime_composition": runtime_record,
        "trace": runtime_record.get("base", {}).get("trace_fragment"),
        "driver": driver,
        "driver_sha256": driver_hash,
        "semantics": p14_semantics.semantics_document(list(sites)),
        "bios_sites": [site.to_document() for site in sites],
        "service_surface": services.service_surface_document(),
        "instrumentation_checks": {
            "function_entry_hook_calls": program.source_text.count("p11_trace_function(UINT64_C("),
            "block_entry_hook_calls": program.source_text.count("p11_trace_block(UINT64_C("),
            "indirect_failure_hook_calls": program.source_text.count("p11_trace_indirect_failure(UINT64_C("),
        },
    }
