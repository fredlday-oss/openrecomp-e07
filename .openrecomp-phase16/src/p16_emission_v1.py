#!/usr/bin/env python3
"""OpenRecomp Phase-16 emission V1.

Composes the Phase-16 host translation build set:
- Mediates fn_fn_80012414 with authentic CD-ROM sector delivery
- Integrates p16_cdrom_extension_v1.c and p16_bios_extension_v1.c
- Intercepts A0:0x43 Exec dispatch and GP0 0xA0 LoadImage multi-word streams
- Emits deterministic telemetry observables for CD-ROM reads and Exec transitions
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for extra in ("", ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src", ".openrecomp-phase15/src",
              ".openrecomp-phase16/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p10_emission_v1 as p10_emission  # noqa: E402
import p15_emission_v1 as p15_emission  # noqa: E402
import p16_surface_v1 as surface16  # noqa: E402

EMISSION_VERSION = "1.0.0"

PROGRAM_NAME = p10_emission.PROGRAM_NAME
IMAGE_NAME = p10_emission.IMAGE_NAME
SUPPORT_NAME = p10_emission.SUPPORT_NAME
DRIVER_NAME = p10_emission.DRIVER_NAME
EMISSION_NAMES = p10_emission.EMISSION_NAMES

RUNTIME_DIR = ROOT / ".openrecomp-phase16" / "runtime"
CDROM_EXTENSION_PATH = RUNTIME_DIR / "p16_cdrom_extension_v1.c"
BIOS_EXTENSION_PATH = RUNTIME_DIR / "p16_bios_extension_v1.c"

MEDIATED_FN_80012414 = """static void fn_fn_80012414(void) {
    p11_trace_function(UINT64_C(2147558420));
bb_blk_80012414:;
    p11_trace_block(UINT64_C(2147558420));
    {
        uint32_t lba = (uint32_t)g_r[4];
        uint32_t dest = (uint32_t)g_r[5];
        uint32_t bytes = (uint32_t)g_r[6];
        uint32_t count = (bytes + 2047u) / 2048u;
        if (p16_cdrom_read_user_sectors(lba, count, dest) != OR_RT_OK) {
            or_fail("p16 cdrom read failed");
            return;
        }
        if (or_rt_memory_write(UINT64_C(0x80034E74), 16u, UINT64_C(0)) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
        g_r[2] = UINT64_C(1);
    }
    return;
}
"""

PROGRAM_DECL_ANCHOR = "extern const char *or_rt_failure_reason(int code);\n"
PROGRAM_DECL_CODE = (
    "#include <stdio.h>\n"
    "extern int p16_cdrom_read_user_sectors(uint32_t lba, uint32_t count, uint32_t dest);\n"
)

DRIVER_DECL_ANCHOR = "uint64_t p15_mmio_transcript_digest(void);\n"
DRIVER_DECL_CODE = (
    "void p16_cdrom_set_disc_path(const char *path);\n"
    "uint64_t p16_exec_calls(void);\n"
    "uint32_t p16_exec_struct_addr(void);\n"
    "uint32_t p16_exec_pc0(void);\n"
    "uint32_t p16_exec_t_addr(void);\n"
    "uint32_t p16_exec_t_size(void);\n"
    "uint32_t p16_exec_sp_addr(void);\n"
    "uint32_t p16_exec_payload_verified(void);\n"
    "uint32_t p16_exec_first_word(void);\n"
    "uint64_t p16_cdrom_read_calls(void);\n"
    "uint64_t p16_cdrom_sectors_delivered(void);\n"
    "uint64_t p16_cdrom_bytes_delivered(void);\n"
    "uint64_t p16_cdrom_read_failures(void);\n"
    "uint32_t p16_cdrom_last_lba(void);\n"
    "uint32_t p16_cdrom_last_count(void);\n"
    "uint64_t p16_rcnt_clear_calls(void);\n"
)

DRIVER_PRINT_ANCHOR = "    printf(\"p15_mmio_digest=0x%016llx\\n\", (unsigned long long)p15_mmio_transcript_digest());\n"
DRIVER_PRINT_CODE = (
    "    printf(\"p16_exec_calls=%llu\\n\", (unsigned long long)p16_exec_calls());\n"
    "    printf(\"p16_exec_struct_addr=0x%08x\\n\", (unsigned)p16_exec_struct_addr());\n"
    "    printf(\"p16_exec_pc0=0x%08x\\n\", (unsigned)p16_exec_pc0());\n"
    "    printf(\"p16_exec_t_addr=0x%08x\\n\", (unsigned)p16_exec_t_addr());\n"
    "    printf(\"p16_exec_t_size=%u\\n\", (unsigned)p16_exec_t_size());\n"
    "    printf(\"p16_exec_sp_addr=0x%08x\\n\", (unsigned)p16_exec_sp_addr());\n"
    "    printf(\"p16_exec_payload_verified=%u\\n\", (unsigned)p16_exec_payload_verified());\n"
    "    printf(\"p16_exec_first_word=0x%08x\\n\", (unsigned)p16_exec_first_word());\n"
    "    printf(\"p16_cdrom_read_calls=%llu\\n\", (unsigned long long)p16_cdrom_read_calls());\n"
    "    printf(\"p16_cdrom_sectors_delivered=%llu\\n\", (unsigned long long)p16_cdrom_sectors_delivered());\n"
    "    printf(\"p16_cdrom_bytes_delivered=%llu\\n\", (unsigned long long)p16_cdrom_bytes_delivered());\n"
    "    printf(\"p16_cdrom_read_failures=%llu\\n\", (unsigned long long)p16_cdrom_read_failures());\n"
    "    printf(\"p16_cdrom_last_lba=%u\\n\", (unsigned)p16_cdrom_last_lba());\n"
    "    printf(\"p16_cdrom_last_count=%u\\n\", (unsigned)p16_cdrom_last_count());\n"
    "    printf(\"p16_rcnt_clear_calls=%llu\\n\", (unsigned long long)p16_rcnt_clear_calls());\n"
)


def build_build_set(
    structure_result: Any,
    base_structure: Any,
    contract: Any,
    flat_image: bytes,
    image_sha256: str,
    disc_path: pathlib.Path | str | None = None,
    sites: tuple[int, ...] = (),
    trace: bool = True,
    guarded_resolved_indirect: bool = True,
    extra_a0: tuple[int, ...] = surface16.EXTRA_A0,
    extra_c0: tuple[int, ...] = surface16.EXTRA_C0,
    extra_b0: tuple[int, ...] = surface16.EXTRA_B0,
    p14_b0: tuple[int, ...] = surface16.P14_B0,
    p14_a0: tuple[int, ...] = surface16.P14_A0,
    p15_a0: tuple[int, ...] = surface16.P15_A0,
    p15_b0: tuple[int, ...] = surface16.P15_B0,
) -> dict[str, Any]:
    base_set = p15_emission.build_build_set(
        structure_result,
        base_structure,
        contract,
        flat_image,
        image_sha256,
        sites=sites,
        trace=trace,
        guarded_resolved_indirect=guarded_resolved_indirect,
        extra_a0=extra_a0,
        extra_c0=extra_c0,
        extra_b0=extra_b0,
        p14_b0=p14_b0,
        p14_a0=p14_a0,
        p15_a0=p15_a0,
        p15_b0=p15_b0,
    )

    # 1. Mediate fn_fn_80012414 in program.c
    program_c = base_set["files"][PROGRAM_NAME]
    fn_start = program_c.find("static void fn_fn_80012414(void) {")
    fn_end = program_c.find("static void fn_fn_800128f4(void) {")
    if fn_start != -1 and fn_end != -1:
        program_c = program_c[:fn_start] + MEDIATED_FN_80012414 + program_c[fn_end:]
    if PROGRAM_DECL_ANCHOR in program_c:
        program_c = program_c.replace(PROGRAM_DECL_ANCHOR, PROGRAM_DECL_ANCHOR + PROGRAM_DECL_CODE)

    # 2. Modify support_c
    support_c = base_set["files"][SUPPORT_NAME]
    support_c = "#define _CRT_SECURE_NO_WARNINGS 1\n#include <stdio.h>\n" + support_c
    support_c = support_c.replace(
        "int p15_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);\n",
        "int p15_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);\n"
        "int p16_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);\n"
        "int p16_mmio_write(uint64_t address, uint32_t width_bits, uint32_t value);\n"
        "int p16_bios_printf(uint32_t fmt, uint32_t arg1, uint32_t arg2, uint64_t *out_value);\n"
    )
    support_c = support_c.replace(
        "status = p11_bios_printf((uint32_t)args[0], (uint32_t)args[1], (uint32_t)args[2], out_value);",
        "status = p16_bios_printf((uint32_t)args[0], (uint32_t)args[1], (uint32_t)args[2], out_value);"
    )
    support_c = support_c.replace(
        "int p15_status = p15_mmio_write(address, width_bits, value);",
        "int p16_status = p16_mmio_write(address, width_bits, value);\n"
        "        if (p16_status != P15_MMIO_UNHANDLED) { return p16_status; }\n"
        "        int p15_status = p15_mmio_write(address, width_bits, value);"
    )
    support_c = support_c.replace(
        "return p15_bios_dispatch(service_id, argc, args, out_value);",
        "return p16_bios_dispatch(service_id, argc, args, out_value);"
    )
    cdrom_ext = CDROM_EXTENSION_PATH.read_text(encoding="utf-8")
    bios_ext = BIOS_EXTENSION_PATH.read_text(encoding="utf-8")
    support_c += "\n" + cdrom_ext + "\n" + bios_ext

    # 3. Modify driver_c
    driver_c = base_set["files"][DRIVER_NAME]
    if disc_path is not None:
        disc_str = str(disc_path).replace("\\", "\\\\")
        driver_init_anchor = "p9_runtime_init();\n"
        driver_init_code = f'    p16_cdrom_set_disc_path("{disc_str}");\n'
        driver_c = driver_c.replace(driver_init_anchor, driver_init_anchor + driver_init_code)

    driver_c = driver_c.replace(DRIVER_DECL_ANCHOR, DRIVER_DECL_ANCHOR + DRIVER_DECL_CODE)
    driver_c = driver_c.replace(DRIVER_PRINT_ANCHOR, DRIVER_PRINT_ANCHOR + DRIVER_PRINT_CODE)

    base_set["files"][PROGRAM_NAME] = program_c
    base_set["files"][SUPPORT_NAME] = support_c
    base_set["files"][DRIVER_NAME] = driver_c
    return base_set
