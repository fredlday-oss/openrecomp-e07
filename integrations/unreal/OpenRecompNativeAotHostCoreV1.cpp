#include "OpenRecompNativeAotHostCoreV1.h"

#include <string.h>

namespace {

static void CopyText(char *dst, size_t dst_size, const char *src)
{
    if (dst == nullptr || dst_size == 0) {
        return;
    }
    dst[0] = '\0';
    if (src == nullptr) {
        return;
    }
    const size_t src_len = strlen(src);
    const size_t copy_len = src_len < (dst_size - 1) ? src_len : (dst_size - 1);
    if (copy_len != 0) {
        memcpy(dst, src, copy_len);
    }
    dst[copy_len] = '\0';
}

static int32_t Fail(char *error_text, size_t error_text_size, const char *message)
{
    CopyText(error_text, error_text_size, message);
    return 0;
}

static int RequiredPointersPresent(const openrecomp_native_aot_api_v1 *api)
{
    return api != nullptr &&
           api->set_host != nullptr &&
           api->run != nullptr &&
           api->observed_state != nullptr &&
           api->function_return != nullptr &&
           api->function_has_return != nullptr &&
           api->operations != nullptr &&
           api->error != nullptr &&
           api->state_count != nullptr &&
           api->state_name != nullptr &&
           api->state_value != nullptr &&
           api->memory_size != nullptr &&
           api->memory_read != nullptr;
}

static int RequiredMetadataPresent(const openrecomp_native_aot_api_v1 *api)
{
    return api != nullptr &&
           api->module_id != nullptr &&
           api->module_format_version != nullptr &&
           api->ir_version != nullptr &&
           api->host_contract_version != nullptr &&
           api->source_architecture != nullptr &&
           api->source_input_sha256 != nullptr;
}

}  // namespace

extern "C" int32_t openrecomp_unreal_native_aot_execute_v1(
    openrecomp_native_aot_query_fn_v1 query,
    const openrecomp_native_aot_host_v1 *host,
    openrecomp_unreal_native_aot_result_v1 *out_result,
    char *error_text,
    size_t error_text_size)
{
    if (error_text != nullptr && error_text_size != 0) {
        error_text[0] = '\0';
    }
    if (out_result == nullptr) {
        return Fail(error_text, error_text_size, "result pointer is null");
    }
    memset(out_result, 0, sizeof(*out_result));

    if (query == nullptr) {
        return Fail(error_text, error_text_size, "Native AOT ABI V1 query symbol is missing");
    }

    const openrecomp_native_aot_api_v1 *api = query(
        OPENRECOMP_NATIVE_AOT_ABI_V1,
        OPENRECOMP_NATIVE_AOT_API_V1_SIZE);
    if (api == nullptr) {
        return Fail(error_text, error_text_size, "Native AOT ABI V1 query rejected version/size");
    }
    if (api->abi_version != OPENRECOMP_NATIVE_AOT_ABI_V1) {
        return Fail(error_text, error_text_size, "Native AOT ABI V1 version mismatch");
    }
    if (api->struct_size != OPENRECOMP_NATIVE_AOT_API_V1_SIZE) {
        return Fail(error_text, error_text_size, "Native AOT ABI V1 structure size mismatch");
    }
    if (!RequiredPointersPresent(api)) {
        return Fail(error_text, error_text_size, "Native AOT ABI V1 function table is incomplete");
    }
    if (!RequiredMetadataPresent(api)) {
        return Fail(error_text, error_text_size, "Native AOT ABI V1 metadata is incomplete");
    }

    const int requires_host =
        (api->capability_flags & OPENRECOMP_NATIVE_AOT_CAP_HOST_CALLS) != 0;
    int host_bound = 0;

    if (requires_host) {
        if (host == nullptr) {
            return Fail(error_text, error_text_size, "module requires a Native AOT ABI V1 host binding");
        }
        if (host->struct_size != OPENRECOMP_NATIVE_AOT_HOST_V1_SIZE ||
            host->abi_version != OPENRECOMP_NATIVE_AOT_ABI_V1 ||
            host->call == nullptr) {
            return Fail(error_text, error_text_size, "Native AOT ABI V1 host binding is malformed");
        }
        if (!api->set_host(host)) {
            return Fail(error_text, error_text_size, "module rejected Native AOT ABI V1 host binding");
        }
        host_bound = 1;
    } else if (host != nullptr) {
        if (host->struct_size != OPENRECOMP_NATIVE_AOT_HOST_V1_SIZE ||
            host->abi_version != OPENRECOMP_NATIVE_AOT_ABI_V1 ||
            host->call == nullptr) {
            return Fail(error_text, error_text_size, "Native AOT ABI V1 host binding is malformed");
        }
        if (!api->set_host(host)) {
            return Fail(error_text, error_text_size, "module rejected optional Native AOT ABI V1 host binding");
        }
        host_bound = 1;
    }

    if (!api->run()) {
        const char *module_error = api->error();
        if (host_bound) {
            (void)api->set_host(nullptr);
        }
        return Fail(
            error_text,
            error_text_size,
            module_error != nullptr ? module_error : "Native AOT module execution failed");
    }

    out_result->capability_flags = api->capability_flags;
    out_result->observed_state = api->observed_state();
    out_result->function_has_return = api->function_has_return();
    out_result->function_return =
        out_result->function_has_return != 0 ? api->function_return() : UINT64_C(0);
    out_result->operations = api->operations();
    out_result->source_address_bits = api->source_address_bits;
    out_result->source_endianness = api->source_endianness;

    CopyText(out_result->module_id, sizeof(out_result->module_id), api->module_id);
    CopyText(
        out_result->module_format_version,
        sizeof(out_result->module_format_version),
        api->module_format_version);
    CopyText(out_result->ir_version, sizeof(out_result->ir_version), api->ir_version);
    CopyText(
        out_result->host_contract_version,
        sizeof(out_result->host_contract_version),
        api->host_contract_version);
    CopyText(
        out_result->source_architecture,
        sizeof(out_result->source_architecture),
        api->source_architecture);
    CopyText(
        out_result->source_input_sha256,
        sizeof(out_result->source_input_sha256),
        api->source_input_sha256);

    if (host_bound && !api->set_host(nullptr)) {
        memset(out_result, 0, sizeof(*out_result));
        return Fail(error_text, error_text_size, "module rejected Native AOT ABI V1 host unbind");
    }

    return 1;
}
