#ifndef OPENRECOMP_NATIVE_AOT_ABI_V1_H
#define OPENRECOMP_NATIVE_AOT_ABI_V1_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32)
#define OPENRECOMP_NATIVE_AOT_EXPORT __declspec(dllexport)
#else
#define OPENRECOMP_NATIVE_AOT_EXPORT __attribute__((visibility("default")))
#endif

#define OPENRECOMP_NATIVE_AOT_ABI_V1 UINT32_C(0x00010000)
#define OPENRECOMP_NATIVE_AOT_ENDIAN_LITTLE UINT32_C(0)
#define OPENRECOMP_NATIVE_AOT_ENDIAN_BIG UINT32_C(1)

#define OPENRECOMP_NATIVE_AOT_CAP_STATE_INSPECTION UINT64_C(0x00000001)
#define OPENRECOMP_NATIVE_AOT_CAP_MEMORY_READ UINT64_C(0x00000002)
#define OPENRECOMP_NATIVE_AOT_CAP_HOST_CALLS UINT64_C(0x00000004)
#define OPENRECOMP_NATIVE_AOT_CAP_DETERMINISTIC_FAULTS UINT64_C(0x00000008)

typedef int32_t (*openrecomp_native_aot_host_call_v1)(
    void *user_data,
    const char *symbol,
    const uint64_t *args,
    uint64_t argc,
    uint64_t *out_value,
    uint32_t *out_has_value);

typedef struct openrecomp_native_aot_host_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    void *user_data;
    openrecomp_native_aot_host_call_v1 call;
} openrecomp_native_aot_host_v1;

typedef int32_t (*openrecomp_native_aot_set_host_v1)(const openrecomp_native_aot_host_v1 *host);
typedef int32_t (*openrecomp_native_aot_run_v1)(void);
typedef uint64_t (*openrecomp_native_aot_u64_v1)(void);
typedef uint32_t (*openrecomp_native_aot_u32_v1)(void);
typedef const char *(*openrecomp_native_aot_error_v1)(void);
typedef uint64_t (*openrecomp_native_aot_state_count_v1)(void);
typedef const char *(*openrecomp_native_aot_state_name_v1)(uint64_t index);
typedef uint64_t (*openrecomp_native_aot_state_value_v1)(uint64_t index);
typedef uint64_t (*openrecomp_native_aot_memory_size_v1)(void);
typedef int32_t (*openrecomp_native_aot_memory_read_v1)(uint64_t address, uint64_t size, uint8_t *out);

typedef struct openrecomp_native_aot_api_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    uint64_t capability_flags;

    const char *module_id;
    const char *module_format_version;
    const char *ir_version;
    const char *host_contract_version;
    const char *source_architecture;
    const char *source_input_sha256;
    uint32_t source_address_bits;
    uint32_t source_endianness;

    openrecomp_native_aot_set_host_v1 set_host;
    openrecomp_native_aot_run_v1 run;
    openrecomp_native_aot_u64_v1 observed_state;
    openrecomp_native_aot_u64_v1 function_return;
    openrecomp_native_aot_u32_v1 function_has_return;
    openrecomp_native_aot_u64_v1 operations;
    openrecomp_native_aot_error_v1 error;
    openrecomp_native_aot_state_count_v1 state_count;
    openrecomp_native_aot_state_name_v1 state_name;
    openrecomp_native_aot_state_value_v1 state_value;
    openrecomp_native_aot_memory_size_v1 memory_size;
    openrecomp_native_aot_memory_read_v1 memory_read;
} openrecomp_native_aot_api_v1;

#define OPENRECOMP_NATIVE_AOT_HOST_V1_SIZE ((uint32_t)sizeof(openrecomp_native_aot_host_v1))
#define OPENRECOMP_NATIVE_AOT_API_V1_SIZE ((uint32_t)sizeof(openrecomp_native_aot_api_v1))

/*
 * The query function is the only stable exported symbol in Native AOT ABI V1.
 * Callers request the exact ABI version they understand and the minimum API
 * structure size they require. Unsupported versions/sizes fail closed with
 * NULL. Returned pointers and strings remain owned by the module.
 */
OPENRECOMP_NATIVE_AOT_EXPORT const openrecomp_native_aot_api_v1 *
openrecomp_native_aot_query(uint32_t requested_abi, uint32_t minimum_api_size);

#ifdef __cplusplus
}
#endif

#endif
