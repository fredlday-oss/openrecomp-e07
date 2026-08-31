#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openrecomp import ModuleImage


class NativeABIError(ValueError):
    pass


def cstr(value: str) -> str:
    if any(ord(ch) > 0x7F for ch in value):
        raise NativeABIError("Native AOT ABI V1 metadata must be ASCII")
    return json.dumps(value)


def generate(module: ModuleImage) -> str:
    ir = module.ir
    source = ir["source"]
    host_calls = bool(ir["required_host_symbols"])
    capabilities = (
        "OPENRECOMP_NATIVE_AOT_CAP_STATE_INSPECTION | "
        "OPENRECOMP_NATIVE_AOT_CAP_MEMORY_READ | "
        "OPENRECOMP_NATIVE_AOT_CAP_DETERMINISTIC_FAULTS"
    )
    if host_calls:
        capabilities += " | OPENRECOMP_NATIVE_AOT_CAP_HOST_CALLS"

    endianness = (
        "OPENRECOMP_NATIVE_AOT_ENDIAN_BIG"
        if source["endianness"] == "big"
        else "OPENRECOMP_NATIVE_AOT_ENDIAN_LITTLE"
    )

    return "\n".join(
        [
            "/* OpenRecomp Native AOT ABI V1 adapter. Generated deterministically. */",
            '#include "openrecomp/native_aot_abi_v1.h"',
            "#include <stddef.h>",
            "#include <stdint.h>",
            "#include <string.h>",
            "",
            "typedef int (*openrecomp_private_host_callback)(const char *, const uint64_t *, size_t, uint64_t *, int *);",
            "void openrecomp_set_host_callback(openrecomp_private_host_callback callback);",
            "int openrecomp_run(void);",
            "uint64_t openrecomp_observed_state(void);",
            "uint64_t openrecomp_function_return(void);",
            "int openrecomp_function_has_return(void);",
            "uint64_t openrecomp_operations(void);",
            "const char *openrecomp_error(void);",
            "size_t openrecomp_state_count(void);",
            "const char *openrecomp_state_name(size_t index);",
            "uint64_t openrecomp_state_value(size_t index);",
            "size_t openrecomp_memory_size(void);",
            "int openrecomp_memory_read(uint64_t address, size_t size, uint8_t *out);",
            "",
            "static openrecomp_native_aot_host_v1 g_abi_host;",
            "static uint32_t g_abi_host_bound;",
            "",
            "static int or_abi_host_bridge(const char *symbol, const uint64_t *args, size_t argc, uint64_t *out_value, int *out_has_value) {",
            "    uint32_t has_value = 0;",
            "    int32_t ok;",
            "    if (!g_abi_host_bound || !g_abi_host.call || !out_value || !out_has_value) return 0;",
            "    ok = g_abi_host.call(g_abi_host.user_data, symbol, args, (uint64_t)argc, out_value, &has_value);",
            "    *out_has_value = has_value ? 1 : 0;",
            "    return ok ? 1 : 0;",
            "}",
            "",
            "static int32_t or_abi_set_host(const openrecomp_native_aot_host_v1 *host) {",
            "    if (!host) {",
            "        memset(&g_abi_host, 0, sizeof(g_abi_host));",
            "        g_abi_host_bound = 0;",
            "        openrecomp_set_host_callback((openrecomp_private_host_callback)0);",
            "        return 1;",
            "    }",
            "    if (host->struct_size != OPENRECOMP_NATIVE_AOT_HOST_V1_SIZE) return 0;",
            "    if (host->abi_version != OPENRECOMP_NATIVE_AOT_ABI_V1) return 0;",
            "    if (!host->call) return 0;",
            "    g_abi_host = *host;",
            "    g_abi_host_bound = 1;",
            "    openrecomp_set_host_callback(or_abi_host_bridge);",
            "    return 1;",
            "}",
            "",
            "static int32_t or_abi_run(void) { return openrecomp_run() ? 1 : 0; }",
            "static uint64_t or_abi_observed_state(void) { return openrecomp_observed_state(); }",
            "static uint64_t or_abi_function_return(void) { return openrecomp_function_return(); }",
            "static uint32_t or_abi_function_has_return(void) { return openrecomp_function_has_return() ? UINT32_C(1) : UINT32_C(0); }",
            "static uint64_t or_abi_operations(void) { return openrecomp_operations(); }",
            "static const char *or_abi_error(void) { return openrecomp_error(); }",
            "static uint64_t or_abi_state_count(void) { return (uint64_t)openrecomp_state_count(); }",
            "static const char *or_abi_state_name(uint64_t index) {",
            "    if (index > (uint64_t)SIZE_MAX) return (const char *)0;",
            "    return openrecomp_state_name((size_t)index);",
            "}",
            "static uint64_t or_abi_state_value(uint64_t index) {",
            "    if (index > (uint64_t)SIZE_MAX) return UINT64_C(0);",
            "    return openrecomp_state_value((size_t)index);",
            "}",
            "static uint64_t or_abi_memory_size(void) { return (uint64_t)openrecomp_memory_size(); }",
            "static int32_t or_abi_memory_read(uint64_t address, uint64_t size, uint8_t *out) {",
            "    if (size > (uint64_t)SIZE_MAX) return 0;",
            "    return openrecomp_memory_read(address, (size_t)size, out) ? 1 : 0;",
            "}",
            "",
            "static const openrecomp_native_aot_api_v1 g_openrecomp_native_aot_api_v1 = {",
            "    OPENRECOMP_NATIVE_AOT_API_V1_SIZE,",
            "    OPENRECOMP_NATIVE_AOT_ABI_V1,",
            f"    {capabilities},",
            f"    {cstr(module.manifest['module_id'])},",
            f"    {cstr(module.manifest['module_format_version'])},",
            f"    {cstr(ir['ir_version'])},",
            f"    {cstr(module.host_contract['contract_version'])},",
            f"    {cstr(source['architecture'])},",
            f"    {cstr(source['input_sha256'])},",
            f"    UINT32_C({source['address_bits']}),",
            f"    {endianness},",
            "    or_abi_set_host,",
            "    or_abi_run,",
            "    or_abi_observed_state,",
            "    or_abi_function_return,",
            "    or_abi_function_has_return,",
            "    or_abi_operations,",
            "    or_abi_error,",
            "    or_abi_state_count,",
            "    or_abi_state_name,",
            "    or_abi_state_value,",
            "    or_abi_memory_size,",
            "    or_abi_memory_read,",
            "};",
            "",
            "OPENRECOMP_NATIVE_AOT_EXPORT const openrecomp_native_aot_api_v1 *",
            "openrecomp_native_aot_query(uint32_t requested_abi, uint32_t minimum_api_size) {",
            "    if (requested_abi != OPENRECOMP_NATIVE_AOT_ABI_V1) return (const openrecomp_native_aot_api_v1 *)0;",
            "    if (minimum_api_size != OPENRECOMP_NATIVE_AOT_API_V1_SIZE) return (const openrecomp_native_aot_api_v1 *)0;",
            "    return &g_openrecomp_native_aot_api_v1;",
            "}",
            "",
        ]
    )


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print("usage: native_aot_abi_v1.py <module.json> <ir.json> <host-contract.json> <out.c>", file=sys.stderr)
        return 2
    try:
        module = ModuleImage.from_files(argv[1], argv[2], argv[3])
        Path(argv[4]).write_text(generate(module), encoding="utf-8", newline="\n")
    except (OSError, KeyError, ValueError, NativeABIError) as exc:
        print(f"OPENRECOMP_NATIVE_AOT_ABI_V1_GENERATE=FAIL: {exc}", file=sys.stderr)
        return 2
    print("OPENRECOMP_NATIVE_AOT_ABI_V1_GENERATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
