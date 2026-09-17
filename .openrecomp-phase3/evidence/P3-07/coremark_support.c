/* OpenRecomp Phase-3 CoreMark host runtime support (P3-07/P3-08). */
/* host_emit_version: 1.0.0 */
/* guest_image_sha256: db5967f4f14fd9befc33c9d82e1cfc44b1409a4e2dfa2053e4fb1a4c7923b845 */
/* Observable contract (re-implemented independently by the P3-09
   reference): after openrecomp_run(), report exit_status, steps, pc, hi,
   lo, uart_bytes, uart_hex and state_fnv1a64 (FNV-1a 64 over the flat
   image bytes, the 32 registers little-endian, hi, lo, pc, steps,
   exit_status, uart_len and the uart bytes, in that order). */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>

/* OpenRecomp generic runtime ABI V1 (P2-08). Architecture-neutral. */
/* runtime_abi_version: openrecomp-generic-runtime-abi 1.0.0 */

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

#define OR_RT_SERVICE_P3_EXIT UINT64_C(1)
#define OR_RT_SERVICE_P3_UART_WRITE UINT64_C(2)

extern int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value);
extern int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value);
extern int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);
extern const char *or_rt_failure_reason(int code);

#define OR_IMAGE_WINDOW 65536u
#define OR_UART_CAPACITY 1048576u
#define OR_REGION_READABLE 1u
#define OR_REGION_WRITABLE 2u

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

static uint8_t g_mem[OR_IMAGE_WINDOW];
static uint8_t g_uart[OR_UART_CAPACITY];
static uint32_t g_uart_len;
static uint32_t g_exit_status;
static uint32_t g_exit_written;

static uint32_t or_region_flags(uint32_t address, uint32_t size, uint32_t *out_flags) {
    uint32_t end = address + size;
    if (end < address) { return 0u; }
    for (uint32_t index = 0; index < openrecomp_region_count(); ++index) {
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
    if (out_value == 0) { return OR_RT_MEMORY_WIDTH_UNSUPPORTED; }
    if (width_bits != 8u && width_bits != 16u && width_bits != 32u) {
        return OR_RT_MEMORY_WIDTH_UNSUPPORTED;
    }
    if (address > 0xffffffffu) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    uint32_t start = (uint32_t)address;
    uint32_t size = width_bits / 8u;
    uint32_t flags = 0u;
    if (!or_region_flags(start, size, &flags)) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    if (!(flags & OR_REGION_READABLE)) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    uint32_t value = 0u;
    for (uint32_t index = 0; index < size; ++index) {
        value |= (uint32_t)g_mem[start + index] << (8u * index);
    }
    *out_value = (uint64_t)value;
    return OR_RT_OK;
}

int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value) {
    if (width_bits != 8u && width_bits != 16u && width_bits != 32u) {
        return OR_RT_MEMORY_WIDTH_UNSUPPORTED;
    }
    if (address > 0xffffffffu) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    uint32_t start = (uint32_t)address;
    uint32_t size = width_bits / 8u;
    uint32_t flags = 0u;
    if (!or_region_flags(start, size, &flags)) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    if (!(flags & OR_REGION_WRITABLE)) { return OR_RT_MEMORY_OUT_OF_RANGE; }
    for (uint32_t index = 0; index < size; ++index) {
        g_mem[start + index] = (uint8_t)((value >> (8u * index)) & 0xffu);
    }
    return OR_RT_OK;
}

int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value) {
    (void)out_value;
    if (service_id == OR_RT_SERVICE_P3_UART_WRITE) {
        if (argc != 1u || args == 0) { return OR_RT_HOST_CALL_ARITY; }
        if (g_uart_len >= OR_UART_CAPACITY) { return OR_RT_HOST_SERVICE_FAILED; }
        g_uart[g_uart_len++] = (uint8_t)(args[0] & 0xffu);
        return OR_RT_OK;
    }
    if (service_id == OR_RT_SERVICE_P3_EXIT) {
        if (argc != 1u || args == 0) { return OR_RT_HOST_CALL_ARITY; }
        if (g_exit_written) { return OR_RT_HOST_SERVICE_FAILED; }
        g_exit_status = (uint32_t)(args[0] & 0xffffffffu);
        g_exit_written = 1u;
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

static uint64_t or_fnv1a64(uint64_t hash, const uint8_t *data, size_t size) {
    for (size_t index = 0; index < size; ++index) {
        hash ^= (uint64_t)data[index];
        hash *= UINT64_C(0x100000001b3);
    }
    return hash;
}

static uint64_t or_hash_u32(uint64_t hash, uint32_t value) {
    uint8_t bytes[4];
    for (uint32_t index = 0; index < 4u; ++index) {
        bytes[index] = (uint8_t)((value >> (8u * index)) & 0xffu);
    }
    return or_fnv1a64(hash, bytes, sizeof(bytes));
}

static uint64_t or_state_hash(void) {
    uint64_t hash = UINT64_C(0xcbf29ce484222325);
    hash = or_fnv1a64(hash, g_mem, sizeof(g_mem));
    for (uint32_t index = 0; index < openrecomp_register_count(); ++index) {
        hash = or_hash_u32(hash, openrecomp_register_value(index));
    }
    hash = or_hash_u32(hash, openrecomp_hi());
    hash = or_hash_u32(hash, openrecomp_lo());
    hash = or_hash_u32(hash, openrecomp_pc());
    hash = or_hash_u32(hash, (uint32_t)openrecomp_steps());
    hash = or_hash_u32(hash, g_exit_status);
    hash = or_hash_u32(hash, g_uart_len);
    hash = or_fnv1a64(hash, g_uart, (size_t)g_uart_len);
    return hash;
}

int main(void) {
    const uint8_t *image = openrecomp_image();
    for (uint32_t index = 0; index < openrecomp_image_size(); ++index) {
        g_mem[index] = image[index];
    }
    openrecomp_run();
    printf("exit_status=%u\n", (unsigned)g_exit_status);
    printf("steps=%llu\n", (unsigned long long)openrecomp_steps());
    printf("pc=0x%08x\n", (unsigned)openrecomp_pc());
    printf("hi=0x%08x\n", (unsigned)openrecomp_hi());
    printf("lo=0x%08x\n", (unsigned)openrecomp_lo());
    printf("uart_bytes=%u\n", (unsigned)g_uart_len);
    printf("uart_hex=");
    for (uint32_t index = 0; index < g_uart_len; ++index) {
        printf("%02x", (unsigned)g_uart[index]);
    }
    printf("\n");
    printf("state_fnv1a64=0x%016llx\n", (unsigned long long)or_state_hash());
    printf("failed=%d\n", openrecomp_failed());
    printf("failure=%s\n", openrecomp_error());
    return 0;
}


