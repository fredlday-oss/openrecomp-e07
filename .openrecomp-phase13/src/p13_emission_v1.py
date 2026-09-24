#!/usr/bin/env python3
"""OpenRecomp Phase-13 emission V1.

Reuses the frozen Phase-12 emission machinery. The additions are the Phase-13
C0 service surface, the Phase-13 runtime composition (C0 interrupt-routine
queue dispatcher) and an additive Phase-13 observable layer on top of the
Phase-12 observable driver.
"""

from __future__ import annotations

import hashlib
import pathlib
from typing import Any

import p9_emission_v1 as p9_emission
import p10_emission_v1 as p10_emission
import p12_emission_v1 as p12_emission
from openrecomp.host_emitter import emit_host_translation

import p13_pad_hook_v1 as pad_hook
import p13_runtime_v1 as p13_runtime
import p13_semantics_v1 as p13_semantics
import p13_services_v1 as services

EMISSION_VERSION = "3.0.0"

ROOT = pathlib.Path(__file__).resolve().parents[2]

PROGRAM_NAME = p10_emission.PROGRAM_NAME
IMAGE_NAME = p10_emission.IMAGE_NAME
SUPPORT_NAME = p10_emission.SUPPORT_NAME
DRIVER_NAME = p10_emission.DRIVER_NAME
EMISSION_NAMES = p10_emission.EMISSION_NAMES

DRIVER_DECLARATION_ANCHOR = "uint32_t p12_synth_read32(uint32_t offset);\n"
DRIVER_DECLARATION_BLOCK = (
    "uint32_t p13_intrp_chain_count(void);\n"
    "uint32_t p13_intrp_head(uint32_t chain);\n"
    "uint64_t p13_intrp_enq_calls(void);\n"
    "uint64_t p13_intrp_deq_calls(void);\n"
    "uint64_t p13_intrp_registered(void);\n"
    "uint32_t p13_intrp_last_struct(void);\n"
    "uint32_t p13_intrp_last_priority(void);\n"
    "uint32_t p13_intrp_deq_result(void);\n"
    "uint32_t p13_pad_buf1(void);\n"
    "uint32_t p13_pad_siz1(void);\n"
    "uint32_t p13_pad_buf2(void);\n"
    "uint32_t p13_pad_siz2(void);\n"
    "uint32_t p13_pad_enable(void);\n"
    "uint32_t p13_pad_started(void);\n"
    "uint64_t p13_pad_init_calls(void);\n"
    "uint64_t p13_pad_start_calls(void);\n"
    "uint64_t p13_pad_stop_calls(void);\n"
    "uint32_t p13_card_pad_enable(void);\n"
    "uint32_t p13_card_started(void);\n"
    "uint64_t p13_card_init_calls(void);\n"
    "uint64_t p13_card_start_calls(void);\n"
    "uint64_t p13_card_stop_calls(void);\n"
    "uint64_t p13_pad_start_hook_calls(void);\n"
    "uint64_t p13_pad_start_hook_last_target(void);\n"
    "uint64_t p13_pad_stop_hook_calls(void);\n"
    "uint64_t p13_pad_stop_hook_last_target(void);\n"
)
DRIVER_PRINT_ANCHOR = "    return 0;\n}\n"
DRIVER_PRINT_BLOCK = (
    "    printf(\"p13_intrp_enq_calls=%llu\\n\", (unsigned long long)p13_intrp_enq_calls());\n"
    "    printf(\"p13_intrp_deq_calls=%llu\\n\", (unsigned long long)p13_intrp_deq_calls());\n"
    "    printf(\"p13_intrp_registered=%llu\\n\", (unsigned long long)p13_intrp_registered());\n"
    "    printf(\"p13_intrp_last_struct=0x%08x\\n\", (unsigned)p13_intrp_last_struct());\n"
    "    printf(\"p13_intrp_last_priority=%u\\n\", (unsigned)p13_intrp_last_priority());\n"
    "    printf(\"p13_intrp_deq_result=0x%08x\\n\", (unsigned)p13_intrp_deq_result());\n"
    "    {\n"
    "        uint32_t p13_chain;\n"
    "        for (p13_chain = 0u; p13_chain < p13_intrp_chain_count(); ++p13_chain) {\n"
    "            printf(\"p13_intrp_head_%lu=0x%08x\\n\", (unsigned long)p13_chain,\n"
    "                   (unsigned)p13_intrp_head(p13_chain));\n"
    "        }\n"
    "    }\n"
    "    {\n"
    "        const unsigned char *p13_ram = p9_runtime_memory();\n"
    "        uint32_t p13_s = p13_intrp_last_struct() & 0x1fffffu;\n"
    "        uint32_t p13_v;\n"
    "        p13_v = (uint32_t)p13_ram[p13_s + 4u] | ((uint32_t)p13_ram[p13_s + 5u] << 8)\n"
    "              | ((uint32_t)p13_ram[p13_s + 6u] << 16) | ((uint32_t)p13_ram[p13_s + 7u] << 24);\n"
    "        printf(\"p13_intrp_func2=0x%08x\\n\", (unsigned)p13_v);\n"
    "        p13_v = (uint32_t)p13_ram[p13_s + 8u] | ((uint32_t)p13_ram[p13_s + 9u] << 8)\n"
    "              | ((uint32_t)p13_ram[p13_s + 10u] << 16) | ((uint32_t)p13_ram[p13_s + 11u] << 24);\n"
    "        printf(\"p13_intrp_func1=0x%08x\\n\", (unsigned)p13_v);\n"
    "    }\n"
    "    printf(\"p13_pad_buf1=0x%08x\\n\", (unsigned)p13_pad_buf1());\n"
    "    printf(\"p13_pad_siz1=%u\\n\", (unsigned)p13_pad_siz1());\n"
    "    printf(\"p13_pad_buf2=0x%08x\\n\", (unsigned)p13_pad_buf2());\n"
    "    printf(\"p13_pad_siz2=%u\\n\", (unsigned)p13_pad_siz2());\n"
    "    printf(\"p13_pad_enable=%u\\n\", (unsigned)p13_pad_enable());\n"
    "    printf(\"p13_pad_started=%u\\n\", (unsigned)p13_pad_started());\n"
    "    printf(\"p13_pad_init_calls=%llu\\n\", (unsigned long long)p13_pad_init_calls());\n"
    "    printf(\"p13_pad_start_calls=%llu\\n\", (unsigned long long)p13_pad_start_calls());\n"
    "    printf(\"p13_pad_stop_calls=%llu\\n\", (unsigned long long)p13_pad_stop_calls());\n"
    "    printf(\"p13_card_pad_enable=%u\\n\", (unsigned)p13_card_pad_enable());\n"
    "    printf(\"p13_card_started=%u\\n\", (unsigned)p13_card_started());\n"
    "    printf(\"p13_card_init_calls=%llu\\n\", (unsigned long long)p13_card_init_calls());\n"
    "    printf(\"p13_card_start_calls=%llu\\n\", (unsigned long long)p13_card_start_calls());\n"
    "    printf(\"p13_card_stop_calls=%llu\\n\", (unsigned long long)p13_card_stop_calls());\n"
    "    printf(\"p13_pad_start_hook_calls=%llu\\n\", (unsigned long long)p13_pad_start_hook_calls());\n"
    "    printf(\"p13_pad_start_hook_last_target=0x%08llx\\n\", (unsigned long long)p13_pad_start_hook_last_target());\n"
    "    printf(\"p13_pad_stop_hook_calls=%llu\\n\", (unsigned long long)p13_pad_stop_hook_calls());\n"
    "    printf(\"p13_pad_stop_hook_last_target=0x%08llx\\n\", (unsigned long long)p13_pad_stop_hook_last_target());\n"
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def phase13_driver_source() -> tuple[str, str]:
    """The Phase-12 observable driver plus the additive Phase-13 observable layer."""
    text, _ = p12_emission.phase12_driver_source()
    if text.count(DRIVER_DECLARATION_ANCHOR) != 1:
        raise ValueError("p13 driver declaration anchor missing or ambiguous")
    if text.count(DRIVER_PRINT_ANCHOR) != 1:
        raise ValueError("p13 driver print anchor missing or ambiguous")
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
    extra_c0: tuple[int, ...] = (),
    extra_b0: tuple[int, ...] = (),
) -> dict[str, Any]:
    """The Phase-13 BIOS-service emission set (optionally instrumented)."""
    services.install(extra_a0, extra_c0, extra_b0)
    instrumentation = p12_emission.p11_emission_instrumentation() if trace else None
    config = p13_semantics.build_emitter_config(
        structure.discovery.entry_function_id, list(sites),
        instrumentation=instrumentation,
        guarded_resolved_indirect=guarded_resolved_indirect,
    )
    program = emit_host_translation(structure.units, structure.classification, config=config)
    support_text, runtime_record = p13_runtime.compose_runtime_source(
        pad_hook.runtime_sites(list(sites)), trace=trace
    )
    image_unit, support_unit = p9_emission.compose_runtime_sources(contract, flat, support_text)
    header = p9_emission.render_image_header(contract)
    if trace:
        driver_text, driver_hash = phase13_driver_source()
        driver = "phase13-trace"
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
        "semantics": p13_semantics.semantics_document(list(sites)),
        "bios_sites": [site.to_document() for site in sites],
        "service_surface": services.service_surface_document(),
        "instrumentation_checks": {
            "function_entry_hook_calls": program.source_text.count("p11_trace_function(UINT64_C("),
            "block_entry_hook_calls": program.source_text.count("p11_trace_block(UINT64_C("),
            "indirect_failure_hook_calls": program.source_text.count("p11_trace_indirect_failure(UINT64_C("),
        },
    }
