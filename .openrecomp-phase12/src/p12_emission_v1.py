#!/usr/bin/env python3
"""OpenRecomp Phase-12 emission V1.

Reuses the frozen Phase-10/Phase-11 emission machinery. The only additions are
the Phase-12 semantic rule table, the Phase-12 runtime composition (synthetic B0
object window and dispatcher), and an additive Phase-12 observable driver layer
that prints the B0-table / ChangeClearPAD / synthetic-window observables on top
of the Phase-11 trace driver.
"""

from __future__ import annotations

import hashlib
import pathlib
from typing import Any

import p9_emission_v1 as p9_emission
import p10_emission_v1 as p10_emission
from openrecomp.host_emitter import emit_host_translation

import p12_runtime_v1 as p12_runtime
import p12_semantics_v1 as p12_semantics
import p12_services_v1 as services

EMISSION_VERSION = "2.0.0"

ROOT = pathlib.Path(__file__).resolve().parents[2]

PROGRAM_NAME = p10_emission.PROGRAM_NAME
IMAGE_NAME = p10_emission.IMAGE_NAME
SUPPORT_NAME = p10_emission.SUPPORT_NAME
DRIVER_NAME = p10_emission.DRIVER_NAME
EMISSION_NAMES = p10_emission.EMISSION_NAMES

TRACE_DRIVER_PATH = ROOT / ".openrecomp-phase11" / "runtime" / "p11_observable_driver_v1.c"

DRIVER_DECLARATION_ANCHOR = "extern jmp_buf p11_bound_jump;\n"
DRIVER_DECLARATION_BLOCK = (
    "uint32_t p12_bios_table_base(void);\n"
    "uint32_t p12_bios_b0_entry(uint32_t index);\n"
    "uint32_t p12_bios_change_clear_pad(void);\n"
    "uint64_t p12_bios_change_clear_calls(void);\n"
    "uint64_t p12_bios_synth_reads(void);\n"
    "uint64_t p12_bios_synth_writes(void);\n"
    "uint32_t p12_synth_read32(uint32_t offset);\n"
)
DRIVER_PRINT_ANCHOR = "    return 0;\n}\n"
DRIVER_PRINT_BLOCK = (
    "    printf(\"p12_b0_table_base=0x%08x\\n\", (unsigned)p12_bios_table_base());\n"
    "    printf(\"p12_b0_entry_5b=0x%08x\\n\", (unsigned)p12_bios_b0_entry(0x5bu));\n"
    "    printf(\"p12_change_clear_pad=%u\\n\", (unsigned)p12_bios_change_clear_pad());\n"
    "    printf(\"p12_change_clear_calls=%llu\\n\", (unsigned long long)p12_bios_change_clear_calls());\n"
    "    printf(\"p12_synth_reads=%llu\\n\", (unsigned long long)p12_bios_synth_reads());\n"
    "    printf(\"p12_synth_writes=%llu\\n\", (unsigned long long)p12_bios_synth_writes());\n"
    "    {\n"
    "        uint32_t p12_index;\n"
    "        for (p12_index = 0u; p12_index < 11u; ++p12_index) {\n"
    "            printf(\"p12_synth_5b_clear_%lu=0x%08x\\n\", (unsigned long)p12_index,\n"
    "                   (unsigned)p12_synth_read32(0x1594u + 4u * p12_index));\n"
    "        }\n"
    "    }\n"
    "    {\n"
    "        const unsigned char *p12_ram = p9_runtime_memory();\n"
    "        uint32_t p12_v;\n"
    "        p12_v = (uint32_t)p12_ram[0x2ed84] | ((uint32_t)p12_ram[0x2ed85] << 8)\n"
    "              | ((uint32_t)p12_ram[0x2ed86] << 16) | ((uint32_t)p12_ram[0x2ed87] << 24);\n"
    "        printf(\"p12_ram_2ed84=0x%08x\\n\", (unsigned)p12_v);\n"
    "        p12_v = (uint32_t)p12_ram[0x2ed88] | ((uint32_t)p12_ram[0x2ed89] << 8)\n"
    "              | ((uint32_t)p12_ram[0x2ed8a] << 16) | ((uint32_t)p12_ram[0x2ed8b] << 24);\n"
    "        printf(\"p12_ram_2ed88=0x%08x\\n\", (unsigned)p12_v);\n"
    "    }\n"
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def phase12_driver_source() -> tuple[str, str]:
    """The Phase-11 trace driver plus the additive Phase-12 observable layer."""
    text = TRACE_DRIVER_PATH.read_text(encoding="utf-8")
    if text.count(DRIVER_DECLARATION_ANCHOR) != 1:
        raise ValueError("p12 driver declaration anchor missing or ambiguous")
    if text.count(DRIVER_PRINT_ANCHOR) != 1:
        raise ValueError("p12 driver print anchor missing or ambiguous")
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
) -> dict[str, Any]:
    """The Phase-12 BIOS-service emission set (optionally instrumented)."""
    services.install()
    instrumentation = p11_emission_instrumentation() if trace else None
    config = p12_semantics.build_emitter_config(
        structure.discovery.entry_function_id, list(sites),
        instrumentation=instrumentation,
        guarded_resolved_indirect=guarded_resolved_indirect,
    )
    program = emit_host_translation(structure.units, structure.classification, config=config)
    support_text, runtime_record = p12_runtime.compose_runtime_source(list(sites), trace=trace)
    image_unit, support_unit = p9_emission.compose_runtime_sources(contract, flat, support_text)
    header = p9_emission.render_image_header(contract)
    if trace:
        driver_text, driver_hash = phase12_driver_source()
        driver = "phase12-trace"
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
        "semantics": p12_semantics.semantics_document(list(sites)),
        "bios_sites": [site.to_document() for site in sites],
        "service_surface": services.service_surface_document(),
        "instrumentation_checks": {
            "function_entry_hook_calls": program.source_text.count("p11_trace_function(UINT64_C("),
            "block_entry_hook_calls": program.source_text.count("p11_trace_block(UINT64_C("),
            "indirect_failure_hook_calls": program.source_text.count("p11_trace_indirect_failure(UINT64_C("),
        },
    }


def p11_emission_instrumentation():
    import p11_emission_v1 as p11_emission

    return p11_emission.TRACE_INSTRUMENTATION
