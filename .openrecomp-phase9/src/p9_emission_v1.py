#!/usr/bin/env python3
"""OpenRecomp Phase-9 deterministic host-source emission for the PS1 fixture.

The emission set for the bounded public fixture is exactly four stable files:

* `program.c` - the existing architecture-neutral host emitter output for the
  PS1 neutral structure and the frozen Phase-8 rule table;
* `p9_image_v1.c` - the generated guest-image contract unit: the bounded
  2 MiB RAM window as inert zero-initialized data plus deterministic
  non-zero chunks (the loaded payload), the explicit region table and the
  platform port map;
* `p9_runtime_support.c` - the OpenRecomp-authored bounded PS1 platform
  runtime support body, composed with the generated contract declarations;
* `p9_driver.c` - the OpenRecomp-authored observable driver, composed with
  the generated contract declarations and the fixture identity.

Nothing in the emission set executes original MIPS32 machine code: the guest
image is inert data and all executed guest semantics are generated C.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import p9_cdrom_boundary_v1 as cdrom
import p9_gpu_boundary_v1 as gpu
import p9_input_timer_v1 as input_timer
import p9_memory_map_v1 as memory_map
import p9_semantics_v1 as semantics
import p9_spu_boundary_v1 as spu
from openrecomp.host_emitter import emit_host_translation

EMISSION_VERSION = "1.0.0"
PROGRAM_NAME = "program.c"
IMAGE_NAME = "p9_image_v1.c"
SUPPORT_NAME = "p9_runtime_support.c"
DRIVER_NAME = "p9_driver.c"
EMISSION_NAMES = (PROGRAM_NAME, IMAGE_NAME, SUPPORT_NAME, DRIVER_NAME)

PLATFORM_PORTS = {
    "P9_RAM_KSEG0_BASE": memory_map.RAM_KSEG0_BASE,
    "P9_RAM_KSEG1_BASE": memory_map.RAM_KSEG1_BASE,
    "P9_IO_BASE": memory_map.IO_BASE,
    "P9_IO_SIZE": memory_map.IO_SIZE,
    "P9_GP0_ADDR": gpu.GP0_WRITE,
    "P9_GP1_ADDR": gpu.GP1_WRITE,
    "P9_GP0_READ": gpu.GP0_READ,
    "P9_GP1_READ": gpu.GP1_READ,
    "P9_JOY_DATA": input_timer.JOY_DATA,
    "P9_JOY_STAT": input_timer.JOY_STAT,
    "P9_JOY_MODE": input_timer.JOY_MODE,
    "P9_JOY_CTRL": input_timer.JOY_CTRL,
    "P9_JOY_BAUD": input_timer.JOY_BAUD,
    "P9_TIMER0_COUNTER": input_timer.TIMER_PORTS["timer0"][0],
    "P9_TIMER0_MODE": input_timer.TIMER_PORTS["timer0"][1],
    "P9_TIMER0_TARGET": input_timer.TIMER_PORTS["timer0"][2],
    "P9_TIMER1_COUNTER": input_timer.TIMER_PORTS["timer1"][0],
    "P9_TIMER1_MODE": input_timer.TIMER_PORTS["timer1"][1],
    "P9_TIMER1_TARGET": input_timer.TIMER_PORTS["timer1"][2],
    "P9_TIMER2_COUNTER": input_timer.TIMER_PORTS["timer2"][0],
    "P9_TIMER2_MODE": input_timer.TIMER_PORTS["timer2"][1],
    "P9_TIMER2_TARGET": input_timer.TIMER_PORTS["timer2"][2],
    "P9_I_STAT": input_timer.I_STAT,
    "P9_I_MASK": input_timer.I_MASK,
    "P9_SPU_BASE": spu.SPU_BASE,
    "P9_SPU_CONTROL_BASE": spu.CONTROL_BASE,
    "P9_SPU_TRANSFER_BASE": spu.TRANSFER_BASE,
    "P9_SPU_CD_AUDIO_BASE": spu.CD_AUDIO_BASE,
    "P9_CDROM_BASE": cdrom.CDROM_BASE,
    "P9_CDROM_INDEX_STATUS": cdrom.INDEX_STATUS,
    "P9_CDROM_COMMAND": cdrom.COMMAND,
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def emit_program(structure: Any) -> Any:
    """Emit the host translation set for one PS1 neutral structure."""
    return emit_host_translation(
        structure.units,
        structure.classification,
        config=semantics.build_emitter_config(
            structure.discovery.entry_function_id,
            services=semantics.runtime_services(),
        ),
    )


def render_image_header(contract: dict[str, Any]) -> str:
    lines = [
        "/* OpenRecomp Phase 9 generated PS1 image contract (do not edit). */",
        "#ifndef OPENRECOMP_P9_IMAGE_V1_H",
        "#define OPENRECOMP_P9_IMAGE_V1_H",
        "",
        "#include <stddef.h>",
        "#include <stdint.h>",
        "",
        f"#define P9_IMAGE_SIZE {contract['ram']['image_size']}u",
        f'#define P9_IMAGE_SHA256 "{contract["ram"]["image_sha256"]}"',
        f"#define P9_ENTRY UINT32_C({int(contract['entry'], 16)})",
        f"#define P9_STACK_POINTER UINT32_C({int(contract['stack']['pointer'], 16)})",
        "",
    ]
    for name, value in sorted(PLATFORM_PORTS.items()):
        lines.append(f"#define {name} UINT32_C(0x{value:08x})")
    lines.extend(
        [
            "",
            "enum { P9_REGION_READABLE = 1u, P9_REGION_WRITABLE = 2u, P9_REGION_EXECUTABLE = 4u };",
            "",
            "struct p9_region {",
            "    uint32_t base;",
            "    uint32_t size;",
            "    unsigned flags;",
            "    const char *name;",
            "};",
            "",
            "struct p9_image_chunk {",
            "    uint32_t offset;",
            "    uint32_t size;",
            "    const unsigned char *data;",
            "};",
            "",
            "struct p9_event {",
            "    uint32_t service;",
            "    uint32_t direction;",
            "    uint32_t width_bits;",
            "    uint32_t flags;",
            "    uint32_t address;",
            "    uint32_t value;",
            "};",
            "",
            "extern const struct p9_image_chunk p9_image_chunks[];",
            "extern const unsigned p9_image_chunk_count;",
            "extern const struct p9_region p9_regions[];",
            "extern const unsigned p9_region_count;",
            "",
            "#endif",
            "",
        ]
    )
    return "\n".join(lines)


def render_image_source(contract: dict[str, Any], flat: bytes) -> str:
    chunks = memory_map.nonzero_chunks(flat)
    lines = [
        "/* OpenRecomp Phase 9 generated PS1 guest image (do not edit). */",
        "/* The 2 MiB RAM window is zero-initialized; these chunks are inert data. */",
        "",
    ]
    for index, (offset, data) in enumerate(chunks):
        lines.append(f"static const unsigned char p9_chunk_data_{index}[] = {{")
        for start in range(0, len(data), 16):
            piece = data[start : start + 16]
            lines.append("    " + " ".join(f"0x{byte:02x}," for byte in piece))
        lines.append("};")
        lines.append("")
    lines.append("const struct p9_image_chunk p9_image_chunks[] = {")
    for index, (offset, data) in enumerate(chunks):
        lines.append(f"    {{ UINT32_C({offset}), UINT32_C({len(data)}), p9_chunk_data_{index} }},")
    lines.append("};")
    lines.append("")
    lines.append("const unsigned p9_image_chunk_count = sizeof(p9_image_chunks) / sizeof(p9_image_chunks[0]);")
    lines.append("")
    lines.append("const struct p9_region p9_regions[] = {")
    for region in contract["regions"]:
        lines.append(
            f'    {{ UINT32_C({int(region["base"], 16)}), UINT32_C({region["size"]}), {region["flags"]}u, "{region["name"]}" }},'
        )
    lines.append("};")
    lines.append("")
    lines.append("const unsigned p9_region_count = sizeof(p9_regions) / sizeof(p9_regions[0]);")
    lines.append("")
    return "\n".join(lines)


def compose_runtime_sources(
    contract: dict[str, Any], flat: bytes, support_text: str
) -> tuple[tuple[str, str], tuple[str, str]]:
    header = render_image_header(contract)
    image_unit = header + "\n" + render_image_source(contract, flat)
    support_unit = header + "\n" + support_text
    return (IMAGE_NAME, image_unit), (SUPPORT_NAME, support_unit)


def build_build_set(
    structure: Any,
    contract: dict[str, Any],
    flat: bytes,
    support_text: str,
    driver_text: str,
    fixture_sha256: str,
) -> dict[str, Any]:
    """Return the deterministic build input set with content hashes."""
    program = emit_program(structure)
    image_unit, support_unit = compose_runtime_sources(contract, flat, support_text)
    header = render_image_header(contract)
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
    }


def emission_digest(build_set: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(emission_document(build_set), sort_keys=True).encode("utf-8")
    ).hexdigest()
