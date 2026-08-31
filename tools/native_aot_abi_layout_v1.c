#include "openrecomp/native_aot_abi_v1.h"

#include <stddef.h>
#include <stdio.h>

#if !defined(_WIN32)
#error OPENRECOMP_AOT_WINDOWS_PORTABILITY_V1 requires a Windows target
#endif

#if !defined(_WIN64)
#error OPENRECOMP_AOT_WINDOWS_PORTABILITY_V1 currently proves only Windows x64
#endif

_Static_assert(sizeof(void *) == 8, "Windows x64 pointer width changed");
_Static_assert(sizeof(openrecomp_native_aot_host_v1) == 24, "Native AOT host V1 size changed");
_Static_assert(offsetof(openrecomp_native_aot_host_v1, struct_size) == 0, "host.struct_size offset changed");
_Static_assert(offsetof(openrecomp_native_aot_host_v1, abi_version) == 4, "host.abi_version offset changed");
_Static_assert(offsetof(openrecomp_native_aot_host_v1, user_data) == 8, "host.user_data offset changed");
_Static_assert(offsetof(openrecomp_native_aot_host_v1, call) == 16, "host.call offset changed");

_Static_assert(sizeof(openrecomp_native_aot_api_v1) == 168, "Native AOT API V1 size changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, struct_size) == 0, "api.struct_size offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, abi_version) == 4, "api.abi_version offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, capability_flags) == 8, "api.capability_flags offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, module_id) == 16, "api.module_id offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, module_format_version) == 24, "api.module_format_version offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, ir_version) == 32, "api.ir_version offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, host_contract_version) == 40, "api.host_contract_version offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, source_architecture) == 48, "api.source_architecture offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, source_input_sha256) == 56, "api.source_input_sha256 offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, source_address_bits) == 64, "api.source_address_bits offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, source_endianness) == 68, "api.source_endianness offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, set_host) == 72, "api.set_host offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, run) == 80, "api.run offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, observed_state) == 88, "api.observed_state offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, function_return) == 96, "api.function_return offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, function_has_return) == 104, "api.function_has_return offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, operations) == 112, "api.operations offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, error) == 120, "api.error offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, state_count) == 128, "api.state_count offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, state_name) == 136, "api.state_name offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, state_value) == 144, "api.state_value offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, memory_size) == 152, "api.memory_size offset changed");
_Static_assert(offsetof(openrecomp_native_aot_api_v1, memory_read) == 160, "api.memory_read offset changed");

int main(void) {
    printf("NATIVE_AOT_ABI_V1_HOST_SIZE=%zu\n", sizeof(openrecomp_native_aot_host_v1));
    printf("NATIVE_AOT_ABI_V1_API_SIZE=%zu\n", sizeof(openrecomp_native_aot_api_v1));
    puts("OPENRECOMP_NATIVE_AOT_ABI_V1_WINDOWS_X64_LAYOUT=PASS");
    return 0;
}
