#pragma once

#include <stddef.h>
#include <stdint.h>

#include "openrecomp/native_aot_abi_v1.h"

#ifdef __cplusplus
extern "C" {
#endif

#define OPENRECOMP_UNREAL_NATIVE_AOT_TEXT_V1 128u

typedef const openrecomp_native_aot_api_v1 *(*openrecomp_native_aot_query_fn_v1)(
    uint32_t requested_abi,
    uint32_t minimum_api_size);

typedef struct openrecomp_unreal_native_aot_result_v1 {
    uint64_t capability_flags;
    uint64_t observed_state;
    uint64_t function_return;
    uint32_t function_has_return;
    uint64_t operations;
    uint32_t source_address_bits;
    uint32_t source_endianness;
    char module_id[OPENRECOMP_UNREAL_NATIVE_AOT_TEXT_V1];
    char module_format_version[OPENRECOMP_UNREAL_NATIVE_AOT_TEXT_V1];
    char ir_version[OPENRECOMP_UNREAL_NATIVE_AOT_TEXT_V1];
    char host_contract_version[OPENRECOMP_UNREAL_NATIVE_AOT_TEXT_V1];
    char source_architecture[OPENRECOMP_UNREAL_NATIVE_AOT_TEXT_V1];
    char source_input_sha256[OPENRECOMP_UNREAL_NATIVE_AOT_TEXT_V1];
} openrecomp_unreal_native_aot_result_v1;

/*
 * Execute one already-loaded Native AOT ABI V1 module through its query
 * function. The OS/engine owns DLL loading and symbol resolution; this core
 * owns only ABI negotiation, host binding, execution, result capture and
 * fail-closed validation.
 *
 * Returns 1 on success, 0 on failure. When supplied, error_text is always
 * NUL-terminated. The function never falls back to legacy AOT symbols.
 */
int32_t openrecomp_unreal_native_aot_execute_v1(
    openrecomp_native_aot_query_fn_v1 query,
    const openrecomp_native_aot_host_v1 *host,
    openrecomp_unreal_native_aot_result_v1 *out_result,
    char *error_text,
    size_t error_text_size);

#ifdef __cplusplus
}
#endif
