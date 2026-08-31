#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "OpenRecompNativeAotHostCoreV1.h"

namespace {

struct ProofHostState {
    uint32_t tick_count;
    uint32_t graphics_calls;
    uint32_t audio_calls;
    uint32_t input_calls;
    uint32_t system_calls;
    uint8_t framebuffer[4u * 4u * 3u];
    uint16_t audio[16u];
};

static int32_t HostCall(
    void *user_data,
    const char *symbol,
    const uint64_t *args,
    uint64_t argc,
    uint64_t *out_value,
    uint32_t *out_has_value)
{
    static const uint32_t inputs[] = {4u, 7u, 1u, 9u, 2u, 6u, 3u, 8u};
    ProofHostState *state = static_cast<ProofHostState *>(user_data);
    if (state == nullptr || symbol == nullptr || out_value == nullptr || out_has_value == nullptr) {
        return 0;
    }
    *out_value = 0;
    *out_has_value = 0;

    if (strcmp(symbol, "host_graphics") == 0) {
        if (argc != 3 || args == nullptr) {
            return 0;
        }
        ++state->graphics_calls;
        const uint64_t x = args[0];
        const uint64_t y = args[1];
        const uint8_t byte = static_cast<uint8_t>(args[2] & UINT64_C(0xff));
        if (x < 4u && y < 4u) {
            const size_t index = static_cast<size_t>((y * 4u + x) * 3u);
            state->framebuffer[index] = byte;
            state->framebuffer[index + 1] = static_cast<uint8_t>(byte ^ 0x55u);
            state->framebuffer[index + 2] = static_cast<uint8_t>(byte ^ 0xaau);
        }
        return 1;
    }

    if (strcmp(symbol, "host_audio") == 0) {
        if (argc != 1 || args == nullptr) {
            return 0;
        }
        ++state->audio_calls;
        const uint32_t sample = static_cast<uint32_t>(args[0]);
        for (uint32_t i = 0; i < 16u; ++i) {
            state->audio[i] = static_cast<uint16_t>((sample + i * 257u) & 0xffffu);
        }
        return 1;
    }

    if (strcmp(symbol, "host_input") == 0) {
        if (argc != 1 || args == nullptr) {
            return 0;
        }
        ++state->input_calls;
        *out_value = inputs[args[0] % 8u];
        *out_has_value = 1;
        return 1;
    }

    if (strcmp(symbol, "host_system") == 0) {
        if (argc != 2 || args == nullptr) {
            return 0;
        }
        ++state->system_calls;
        const uint32_t value =
            static_cast<uint32_t>(args[0]) +
            static_cast<uint32_t>(args[1]) +
            7u +
            state->tick_count;
        ++state->tick_count;
        *out_value = value;
        *out_has_value = 1;
        return 1;
    }

    return 0;
}

static uint32_t ProofChecksum(const ProofHostState &state, uint64_t observed_state)
{
    uint32_t hash =
        static_cast<uint32_t>(observed_state) ^
        state.tick_count ^
        (state.graphics_calls << 4) ^
        (state.audio_calls << 8) ^
        (state.input_calls << 12) ^
        (state.system_calls << 16);

    for (const uint8_t byte : state.framebuffer) {
        hash = (hash * 16777619u) ^ byte;
    }
    for (const uint16_t sample : state.audio) {
        hash = (hash * 16777619u) ^ static_cast<uint32_t>(sample);
    }
    return hash;
}

static int Fail(const char *message)
{
    fprintf(stderr, "OPENRECOMP_UNREAL_NATIVE_AOT_HOST_CORE_V1=FAIL: %s\n", message);
    return 2;
}

}  // namespace

int main(int argc, char **argv)
{
    if (argc != 2) {
        return Fail("usage: unreal_native_aot_host_v1_harness.exe <rv32i-native-aot.dll>");
    }

    HMODULE module = LoadLibraryA(argv[1]);
    if (module == nullptr) {
        return Fail("LoadLibraryA failed");
    }

    const auto query = reinterpret_cast<openrecomp_native_aot_query_fn_v1>(
        GetProcAddress(module, "openrecomp_native_aot_query"));
    if (query == nullptr) {
        FreeLibrary(module);
        return Fail("openrecomp_native_aot_query export missing");
    }

    char error_text[512]{};
    openrecomp_unreal_native_aot_result_v1 rejected{};
    if (openrecomp_unreal_native_aot_execute_v1(
            query,
            nullptr,
            &rejected,
            error_text,
            sizeof(error_text)) != 0) {
        FreeLibrary(module);
        return Fail("host-required module unexpectedly accepted a null host");
    }
    if (strstr(error_text, "requires") == nullptr) {
        FreeLibrary(module);
        return Fail("null-host rejection was not deterministic");
    }
    puts("OPENRECOMP_UNREAL_NATIVE_AOT_HOST_CORE_V1_NULL_HOST_REJECTION=PASS");

    ProofHostState host_state{};
    openrecomp_native_aot_host_v1 host{};
    host.struct_size = OPENRECOMP_NATIVE_AOT_HOST_V1_SIZE;
    host.abi_version = OPENRECOMP_NATIVE_AOT_ABI_V1;
    host.user_data = &host_state;
    host.call = &HostCall;

    openrecomp_unreal_native_aot_result_v1 result{};
    error_text[0] = '\0';
    if (!openrecomp_unreal_native_aot_execute_v1(
            query,
            &host,
            &result,
            error_text,
            sizeof(error_text))) {
        FreeLibrary(module);
        return Fail(error_text[0] != '\0' ? error_text : "host-core execution failed");
    }

    const uint32_t checksum = ProofChecksum(host_state, result.observed_state);
    const bool metadata_ok =
        strcmp(result.module_id, "e07.rv32i.fixture-full.ir-v1") == 0 &&
        strcmp(result.source_architecture, "rv32i") == 0 &&
        strcmp(result.host_contract_version, "0.1.1") == 0 &&
        result.source_address_bits == 32u &&
        result.source_endianness == OPENRECOMP_NATIVE_AOT_ENDIAN_LITTLE &&
        (result.capability_flags & OPENRECOMP_NATIVE_AOT_CAP_HOST_CALLS) != 0;
    if (!metadata_ok) {
        FreeLibrary(module);
        return Fail("module metadata/capability validation failed");
    }
    puts("OPENRECOMP_UNREAL_NATIVE_AOT_HOST_CORE_V1_METADATA=PASS");

    if (result.observed_state != UINT64_C(48) ||
        result.operations != UINT64_C(3866) ||
        checksum != UINT32_C(122010428)) {
        FreeLibrary(module);
        return Fail("observable execution result mismatch");
    }

    if (host_state.graphics_calls == 0 ||
        host_state.audio_calls == 0 ||
        host_state.input_calls == 0 ||
        host_state.system_calls == 0) {
        FreeLibrary(module);
        return Fail("expected E07 host callbacks were not exercised");
    }

    printf("UNREAL_NATIVE_AOT_OBSERVED_STATE=%llu\n", static_cast<unsigned long long>(result.observed_state));
    printf("UNREAL_NATIVE_AOT_CHECKSUM=%u\n", checksum);
    printf("UNREAL_NATIVE_AOT_OPERATIONS=%llu\n", static_cast<unsigned long long>(result.operations));
    puts("OPENRECOMP_UNREAL_NATIVE_AOT_HOST_CORE_V1_CALLBACKS=PASS");
    puts("OPENRECOMP_UNREAL_NATIVE_AOT_HOST_CORE_V1=PASS");

    FreeLibrary(module);
    return 0;
}
