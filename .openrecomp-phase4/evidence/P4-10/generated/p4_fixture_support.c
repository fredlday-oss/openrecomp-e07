/* OpenRecomp Phase-4 fixture runtime support (P4-08). */
/* Implements the runtime side of the generated-code <-> runtime ABI and the
   declared fixture instance services over the generic runtime contracts. */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>

enum {
    OR_RT_OK = 0,
    OR_RT_MEMORY_OUT_OF_RANGE = 1,
    OR_RT_MEMORY_WIDTH_UNSUPPORTED = 2,
    OR_RT_MEMORY_ADDRESS_OVERFLOW = 3,
    OR_RT_MEMORY_ENDIANNESS_UNSUPPORTED = 4,
    OR_RT_MEMORY_SEGMENT_OVERLAP = 5,
    OR_RT_UNKNOWN_HOST_SERVICE = 6,
    OR_RT_HOST_SERVICE_FAILED = 7,
    OR_RT_HOST_CALL_ARITY = 8,
    OR_RT_INPUT_INVALID = 9,
    OR_RT_FRAME_INVALID = 10,
    OR_RT_AUDIO_INVALID = 11,
    OR_RT_ABI_VERSION_MISMATCH = 12,
    OR_RT_UNSUPPORTED_OPERATION = 13,
    OR_RT_TRAP = 14,
};

#define OR_RT_SERVICE_FIXTURE_EXIT UINT64_C(1)
#define OR_RT_SERVICE_FIXTURE_IN UINT64_C(2)
#define OR_RT_SERVICE_FIXTURE_OUT UINT64_C(3)
#define OR_RT_SERVICE_FIXTURE_TICKS UINT64_C(4)

extern int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value);
extern int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value);
extern int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);
extern const char *or_rt_failure_reason(int code);

void openrecomp_run(void);
int openrecomp_failed(void);
const char *openrecomp_error(void);
uint64_t openrecomp_steps(void);
uint32_t openrecomp_pc(void);
uint32_t openrecomp_hi(void);
uint32_t openrecomp_lo(void);
size_t openrecomp_register_count(void);
uint32_t openrecomp_register_value(size_t index);
const uint8_t *openrecomp_image(void);
uint32_t openrecomp_image_size(void);
uint32_t openrecomp_region_count(void);
void openrecomp_region(uint32_t index, uint32_t *start, uint32_t *end, uint32_t *flags);

#define OR_IMAGE_WINDOW 65536u
#define OR_OUTPUT_CAPACITY 65536u
#define OR_INPUT_CAPACITY 64u
#define OR_INPUT_PLAN_LENGTH 5u
#define OR_REGION_READABLE 1u
#define OR_REGION_WRITABLE 2u

static uint8_t g_mem[OR_IMAGE_WINDOW];
static uint8_t g_output[OR_OUTPUT_CAPACITY];
static uint32_t g_output_len;
static uint8_t g_input[OR_INPUT_CAPACITY];
static uint32_t g_input_len;
static uint32_t g_input_pos;
static uint32_t g_exit_status;
static uint32_t g_exit_written;

static const uint8_t g_input_plan[OR_INPUT_CAPACITY] = {
    0x05, 0x12, 0xab, 0x34, 0xff,
};

static uint32_t or_region_flags(uint32_t address, uint32_t size, uint32_t *out_flags) {
    uint32_t index;
    uint32_t end = address + size;
    if (end < address) { return 0u; }
    for (index = 0u; index < openrecomp_region_count(); ++index) {
        uint32_t start = 0u, limit = 0u, flags = 0u;
        openrecomp_region(index, &start, &limit, &flags);
        if (address >= start && end <= limit) {
            if (out_flags) { *out_flags = flags; }
            return 1u;
        }
    }
    return 0u;
}

int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value) {
    uint32_t start;
    uint32_t size;
    uint32_t flags = 0u;
    uint32_t value = 0u;
    uint32_t index;
    if (out_value == 0) { return OR_RT_MEMORY_WIDTH_UNSUPPORTED; }
    if (width_bits != 8u && width_bits != 16u && width_bits != 32u) {
        return OR_RT_MEMORY_WIDTH_UNSUPPORTED;
    }
    if (address > 0xffffffffu) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    start = (uint32_t)address;
    size = width_bits / 8u;
    if (!or_region_flags(start, size, &flags)) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    if (!(flags & OR_REGION_READABLE)) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    for (index = 0u; index < size; ++index) {
        value |= (uint32_t)g_mem[start + index] << (8u * index);
    }
    *out_value = (uint64_t)value;
    return OR_RT_OK;
}

int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value) {
    uint32_t start;
    uint32_t size;
    uint32_t flags = 0u;
    uint32_t index;
    if (width_bits != 8u && width_bits != 16u && width_bits != 32u) {
        return OR_RT_MEMORY_WIDTH_UNSUPPORTED;
    }
    if (address > 0xffffffffu) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    start = (uint32_t)address;
    size = width_bits / 8u;
    if (!or_region_flags(start, size, &flags)) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    if (!(flags & OR_REGION_WRITABLE)) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    for (index = 0u; index < size; ++index) {
        g_mem[start + index] = (uint8_t)((value >> (8u * index)) & 0xffu);
    }
    return OR_RT_OK;
}

int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args,
                    uint64_t *out_value) {
    if (service_id == (uint64_t)OR_RT_SERVICE_FIXTURE_EXIT) {
        if (argc != 1u || args == 0) { return OR_RT_HOST_CALL_ARITY; }
        if (g_exit_written) { return OR_RT_HOST_SERVICE_FAILED; }
        g_exit_status = (uint32_t)(args[0] & 0xffffffffu);
        g_exit_written = 1u;
        return OR_RT_OK;
    }
    if (service_id == (uint64_t)OR_RT_SERVICE_FIXTURE_IN) {
        if (argc != 0u) { return OR_RT_HOST_CALL_ARITY; }
        if (out_value == 0) { return OR_RT_HOST_SERVICE_FAILED; }
        if (g_input_pos >= g_input_len) { *out_value = UINT64_C(0xffffffff); return OR_RT_OK; }
        *out_value = (uint64_t)g_input[g_input_pos];
        g_input_pos += 1u;
        return OR_RT_OK;
    }
    if (service_id == (uint64_t)OR_RT_SERVICE_FIXTURE_OUT) {
        if (argc != 1u || args == 0) { return OR_RT_HOST_CALL_ARITY; }
        if (g_output_len >= OR_OUTPUT_CAPACITY) { return OR_RT_UNSUPPORTED_OPERATION; }
        g_output[g_output_len] = (uint8_t)(args[0] & 0xffu);
        g_output_len += 1u;
        return OR_RT_OK;
    }
    if (service_id == (uint64_t)OR_RT_SERVICE_FIXTURE_TICKS) {
        if (argc != 0u) { return OR_RT_HOST_CALL_ARITY; }
        if (out_value == 0) { return OR_RT_HOST_SERVICE_FAILED; }
        *out_value = openrecomp_steps();
        return OR_RT_OK;
    }
    return OR_RT_UNKNOWN_HOST_SERVICE;
}

static const char *or_failure_reasons[] = {
    "",
    "MEMORY_OUT_OF_RANGE",
    "MEMORY_WIDTH_UNSUPPORTED",
    "MEMORY_ADDRESS_OVERFLOW",
    "MEMORY_ENDIANNESS_UNSUPPORTED",
    "MEMORY_SEGMENT_OVERLAP",
    "UNKNOWN_HOST_SERVICE",
    "HOST_SERVICE_FAILED",
    "HOST_CALL_ARITY",
    "INPUT_INVALID",
    "FRAME_INVALID",
    "AUDIO_INVALID",
    "ABI_VERSION_MISMATCH",
    "UNSUPPORTED_OPERATION",
    "TRAP",
};

const char *or_rt_failure_reason(int code) {
    if (code < 0 || (size_t)code >= sizeof(or_failure_reasons) / sizeof(or_failure_reasons[0])) {
        return "runtime failure";
    }
    return or_failure_reasons[code];
}

static uint64_t or_fnv1a64(uint64_t state, const uint8_t *data, size_t size) {
    size_t index;
    for (index = 0; index < size; ++index) {
        state ^= (uint64_t)data[index];
        state *= UINT64_C(0x100000001b3);
    }
    return state;
}

static uint64_t or_hash_u32(uint64_t state, uint32_t value) {
    uint8_t bytes[4];
    uint32_t index;
    for (index = 0u; index < 4u; ++index) {
        bytes[index] = (uint8_t)((value >> (8u * index)) & 0xffu);
    }
    return or_fnv1a64(state, bytes, sizeof(bytes));
}

static uint64_t or_state_hash(void) {
    uint64_t state = UINT64_C(0xcbf29ce484222325);
    uint32_t status = g_exit_written ? g_exit_status : 0xffffffffu;
    state = or_fnv1a64(state, (const uint8_t *)"OROBS1", 6u);
    state = or_hash_u32(state, OR_IMAGE_WINDOW);
    state = or_fnv1a64(state, g_mem, OR_IMAGE_WINDOW);
    state = or_hash_u32(state, 32u);
    for (uint32_t index = 0u; index < 32u; ++index) {
        state = or_hash_u32(state, openrecomp_register_value((size_t)index));
    }
    state = or_hash_u32(state, 2u);
    state = or_hash_u32(state, openrecomp_hi());
    state = or_hash_u32(state, openrecomp_lo());
    state = or_hash_u32(state, openrecomp_pc());
    {
        uint64_t steps = openrecomp_steps();
        uint8_t bytes[8];
        for (uint32_t index = 0u; index < 8u; ++index) {
            bytes[index] = (uint8_t)((steps >> (8u * index)) & 0xffu);
        }
        state = or_fnv1a64(state, bytes, sizeof(bytes));
    }
    state = or_hash_u32(state, status);
    state = or_hash_u32(state, g_output_len);
    state = or_fnv1a64(state, g_output, (size_t)g_output_len);
    return state;
}

int main(void) {
    const uint8_t *image = openrecomp_image();
    uint32_t index;
    uint32_t count = openrecomp_image_size();
    if (count > OR_IMAGE_WINDOW) { count = OR_IMAGE_WINDOW; }
    for (index = 0u; index < count; ++index) {
        g_mem[index] = image[index];
    }
    g_input_len = OR_INPUT_PLAN_LENGTH;
    for (index = 0u; index < OR_INPUT_PLAN_LENGTH; ++index) {
        g_input[index] = g_input_plan[index];
    }
    openrecomp_run();
    printf("exit_status=%u\n", (unsigned)(g_exit_written ? g_exit_status : 0xffffffffu));
    printf("steps=%llu\n", (unsigned long long)openrecomp_steps());
    printf("pc=0x%08x\n", (unsigned)openrecomp_pc());
    printf("failed=%d\n", openrecomp_failed());
    printf("failure=%s\n", openrecomp_error());
    printf("output_bytes=%u\n", (unsigned)g_output_len);
    printf("output_hex=");
    for (index = 0u; index < g_output_len; ++index) {
        printf("%02x", (unsigned)g_output[index]);
    }
    printf("\n");
    printf("state_fnv1a64=0x%016llx\n", (unsigned long long)or_state_hash());
    return 0;
}
