#!/usr/bin/env python3
"""OpenRecomp Phase-15 emission V1.

Reuses the frozen Phase-14 emission machinery. The additions are the Phase-15
runtime composition (bounded interrupt/peripheral MMIO pre-dispatch), the
optional Phase-15 BIOS service surface and an additive Phase-15 observable layer
on top of the Phase-14 observable driver.
"""

from __future__ import annotations

import hashlib
import pathlib
from typing import Any

import p9_emission_v1 as p9_emission
import p10_emission_v1 as p10_emission
import p12_emission_v1 as p12_emission
import p14_emission_v1 as p14_emission
import p14_semantics_v1 as p14_semantics
from openrecomp.host_emitter import emit_host_translation

import p15_runtime_v1 as p15_runtime
import p15_services_v1 as services

EMISSION_VERSION = "1.0.0"

ROOT = pathlib.Path(__file__).resolve().parents[2]

PROGRAM_NAME = p10_emission.PROGRAM_NAME
IMAGE_NAME = p10_emission.IMAGE_NAME
SUPPORT_NAME = p10_emission.SUPPORT_NAME
DRIVER_NAME = p10_emission.DRIVER_NAME
EMISSION_NAMES = p10_emission.EMISSION_NAMES

DRIVER_DECLARATION_ANCHOR = "uint64_t p14_card_patch_writes(void);\n"
DRIVER_DECLARATION_BLOCK = (
    "uint32_t p15_i_stat(void);\n"
    "uint32_t p15_i_mask(void);\n"
    "uint32_t p15_sys_control(void);\n"
    "uint32_t p15_d2_madr(void);\n"
    "uint32_t p15_d2_bcr(void);\n"
    "uint32_t p15_d2_chcr(void);\n"
    "uint32_t p15_dpcr(void);\n"
    "uint32_t p15_dicr(void);\n"
    "uint64_t p15_setjmp_calls(void);\n"
    "uint64_t p15_96remove_calls(void);\n"
    "uint64_t p15_hook_entry_int_calls(void);\n"
    "uint64_t p15_reset_entry_int_calls(void);\n"
    "uint64_t p15_return_from_exception_calls(void);\n"
    "uint32_t p15_entry_int_hook(void);\n"
    "uint64_t p15_bios_service_failures(void);\n"
    "uint64_t p15_mmio_reads(void);\n"
    "uint64_t p15_mmio_writes(void);\n"
    "uint64_t p15_mmio_unsupported(void);\n"
    "uint32_t p15_mmio_event_count(void);\n"
    "uint64_t p15_mmio_event_overflow(void);\n"
    "uint32_t p15_mmio_event_address(uint32_t index);\n"
    "uint32_t p15_mmio_event_width(uint32_t index);\n"
    "uint32_t p15_mmio_event_is_write(uint32_t index);\n"
    "uint32_t p15_mmio_event_value(uint32_t index);\n"
    "uint64_t p15_mmio_transcript_digest(void);\n"
)

DRIVER_PRINT_ANCHOR = "    return 0;\n}\n"
DRIVER_PRINT_BLOCK = (
    "    printf(\"p15_i_stat=0x%08x\\n\", (unsigned)p15_i_stat());\n"
    "    printf(\"p15_i_mask=0x%08x\\n\", (unsigned)p15_i_mask());\n"
    "    printf(\"p15_sys_control=0x%08x\\n\", (unsigned)p15_sys_control());\n"
    "    printf(\"p15_d2_madr=0x%08x\\n\", (unsigned)p15_d2_madr());\n"
    "    printf(\"p15_d2_bcr=0x%08x\\n\", (unsigned)p15_d2_bcr());\n"
    "    printf(\"p15_d2_chcr=0x%08x\\n\", (unsigned)p15_d2_chcr());\n"
    "    printf(\"p15_dpcr=0x%08x\\n\", (unsigned)p15_dpcr());\n"
    "    printf(\"p15_dicr=0x%08x\\n\", (unsigned)p15_dicr());\n"
    "    printf(\"p15_setjmp_calls=%llu\\n\", (unsigned long long)p15_setjmp_calls());\n"
    "    printf(\"p15_96remove_calls=%llu\\n\", (unsigned long long)p15_96remove_calls());\n"
    "    printf(\"p15_hook_entry_int_calls=%llu\\n\", (unsigned long long)p15_hook_entry_int_calls());\n"
    "    printf(\"p15_reset_entry_int_calls=%llu\\n\", (unsigned long long)p15_reset_entry_int_calls());\n"
    "    printf(\"p15_return_from_exception_calls=%llu\\n\", (unsigned long long)p15_return_from_exception_calls());\n"
    "    printf(\"p15_entry_int_hook=0x%08x\\n\", (unsigned)p15_entry_int_hook());\n"
    "    printf(\"p15_bios_service_failures=%llu\\n\", (unsigned long long)p15_bios_service_failures());\n"
    "    printf(\"p15_mmio_reads=%llu\\n\", (unsigned long long)p15_mmio_reads());\n"
    "    printf(\"p15_mmio_writes=%llu\\n\", (unsigned long long)p15_mmio_writes());\n"
    "    printf(\"p15_mmio_unsupported=%llu\\n\", (unsigned long long)p15_mmio_unsupported());\n"
    "    printf(\"p15_mmio_events=%lu\\n\", (unsigned long)p15_mmio_event_count());\n"
    "    printf(\"p15_mmio_overflow=%llu\\n\", (unsigned long long)p15_mmio_event_overflow());\n"
    "    {\n"
    "        uint32_t p15_i;\n"
    "        for (p15_i = 0u; p15_i < p15_mmio_event_count(); ++p15_i) {\n"
    "            printf(\"p15_mmio_%lu=0x%08x,%u,%u,0x%08x\\n\", (unsigned long)p15_i,\n"
    "                   (unsigned)p15_mmio_event_address(p15_i),\n"
    "                   (unsigned)p15_mmio_event_width(p15_i),\n"
    "                   (unsigned)p15_mmio_event_is_write(p15_i),\n"
    "                   (unsigned)p15_mmio_event_value(p15_i));\n"
    "        }\n"
    "    }\n"
    "    printf(\"p15_mmio_digest=0x%016llx\\n\", (unsigned long long)p15_mmio_transcript_digest());\n"
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def phase15_driver_source() -> tuple[str, str]:
    """The Phase-14 observable driver plus the additive Phase-15 observable layer."""
    text, _ = p14_emission.phase14_driver_source()
    if text.count(DRIVER_DECLARATION_ANCHOR) != 1:
        raise ValueError("p15 driver declaration anchor missing or ambiguous")
    if text.count(DRIVER_PRINT_ANCHOR) != 1:
        raise ValueError("p15 driver print anchor missing or ambiguous")
    text = text.replace(
        DRIVER_DECLARATION_ANCHOR,
        DRIVER_DECLARATION_ANCHOR + DRIVER_DECLARATION_BLOCK,
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
    p15_a0: tuple[int, ...] = (),
    p15_b0: tuple[int, ...] = (),
) -> dict[str, Any]:
    """The Phase-15 MMIO-service emission set (optionally instrumented)."""
    services.install(
        extra_a0, extra_c0, extra_b0, p14_b0=p14_b0, p14_a0=p14_a0,
        p15_a0=p15_a0, p15_b0=p15_b0,
    )
    instrumentation = p12_emission.p11_emission_instrumentation() if trace else None
    config = p14_semantics.build_emitter_config(
        structure.discovery.entry_function_id, list(sites),
        instrumentation=instrumentation,
        guarded_resolved_indirect=guarded_resolved_indirect,
    )
    program = emit_host_translation(structure.units, structure.classification, config=config)
    support_text, runtime_record = p15_runtime.compose_runtime_source(
        p14_semantics.runtime_sites(list(sites)), trace=trace
    )
    image_unit, support_unit = p9_emission.compose_runtime_sources(contract, flat, support_text)
    header = p9_emission.render_image_header(contract)
    if trace:
        driver_text, driver_hash = phase15_driver_source()
        driver = "phase15-trace"
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
