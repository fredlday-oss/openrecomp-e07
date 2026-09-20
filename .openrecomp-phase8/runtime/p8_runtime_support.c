/*
 * OpenRecomp Phase 8 - bounded native runtime support for the frozen real
 * MIPS32 ELF fixture (OpenRecomp-authored).
 *
 * This translation unit implements the host side of the P8 memory/runtime
 * contract declared by the generated `p8_image_v1.h`:
 *
 *   - a flat guest image window with explicit region permissions;
 *   - a write-only byte output window at 0x10000000 served through the
 *     `p8_uart_write` generic-runtime host service;
 *   - deterministic access counters and output transcript for the observable
 *     contract;
 *   - fail-closed behaviour for out-of-range, unsupported-width and
 *     read-only writes.
 *
 * It contains no guest machine code and no platform or console-specific
 * behaviour.  The generated program is the only code that executes guest
 * semantics.
 */

/*
 * This body is compiled after the generated `p8_image_v1` contract
 * declarations (see `p8_memory_contract_v1.compose_runtime_sources`), which
 * provide `p8_image`, `p8_regions`, `p8_region_count`, `struct p8_region`,
 * `P8_IMAGE_SIZE`, `P8_OUTPUT_ADDR`, `P8_OUTPUT_WIDTH_BITS` and
 * `P8_REGION_WRITABLE`.
 */

#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* OpenRecomp generic runtime ABI V1 failure codes (numeric contract). */
enum {
    P8_RT_OK = 0,
    P8_RT_MEMORY_OUT_OF_RANGE = 1,
    P8_RT_MEMORY_WIDTH_UNSUPPORTED = 2,
    P8_RT_UNKNOWN_HOST_SERVICE = 6,
    P8_RT_HOST_CALL_ARITY = 8,
    P8_RT_UNSUPPORTED_OPERATION = 13
};

#define P8_TRANSCRIPT_CAPACITY (1u << 20)

/* OpenRecomp generic runtime ABI V1 surface (implemented in this file). */
int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value);
int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value);
int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);
const char *or_rt_failure_reason(int code);

static unsigned char g_p8_memory[P8_IMAGE_SIZE];
static unsigned char g_p8_transcript[P8_TRANSCRIPT_CAPACITY];
static uint64_t g_p8_memory_reads;
static uint64_t g_p8_memory_writes;
static uint64_t g_p8_host_calls;
static uint64_t g_p8_denied_accesses;
static uint64_t g_p8_transcript_length;
static int g_p8_initialized;

void p8_runtime_init(void)
{
    if (!g_p8_initialized) {
        memcpy(g_p8_memory, p8_image, sizeof(g_p8_memory));
        g_p8_initialized = 1;
    }
}

const unsigned char *p8_runtime_memory(void) { return g_p8_memory; }
uint64_t p8_runtime_memory_reads(void) { return g_p8_memory_reads; }
uint64_t p8_runtime_memory_writes(void) { return g_p8_memory_writes; }
uint64_t p8_runtime_host_calls(void) { return g_p8_host_calls; }
uint64_t p8_runtime_denied_accesses(void) { return g_p8_denied_accesses; }
uint64_t p8_runtime_transcript_length(void) { return g_p8_transcript_length; }
const unsigned char *p8_runtime_transcript(void) { return g_p8_transcript; }

static const struct p8_region *p8_region_at(uint64_t address, uint64_t width_bytes)
{
    unsigned index;
    for (index = 0; index < p8_region_count; ++index) {
        uint64_t base = (uint64_t)p8_regions[index].base;
        uint64_t size = (uint64_t)p8_regions[index].size;
        if (base <= address && address + width_bytes <= base + size) {
            return &p8_regions[index];
        }
    }
    return NULL;
}

static int p8_width_bytes(uint32_t width_bits, uint64_t *out_width)
{
    if (width_bits == 8u) { *out_width = 1u; return P8_RT_OK; }
    if (width_bits == 16u) { *out_width = 2u; return P8_RT_OK; }
    if (width_bits == 32u) { *out_width = 4u; return P8_RT_OK; }
    return P8_RT_MEMORY_WIDTH_UNSUPPORTED;
}

int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value)
{
    uint64_t width_bytes = 0;
    uint64_t value = 0;
    uint64_t index;
    int status = p8_width_bytes(width_bits, &width_bytes);
    if (status != P8_RT_OK) {
        ++g_p8_denied_accesses;
        return status;
    }
    p8_runtime_init();
    if (address == P8_OUTPUT_ADDR) {
        ++g_p8_denied_accesses;
        return P8_RT_MEMORY_OUT_OF_RANGE;
    }
    if (address + width_bytes > (uint64_t)P8_IMAGE_SIZE) {
        ++g_p8_denied_accesses;
        return P8_RT_MEMORY_OUT_OF_RANGE;
    }
    for (index = 0; index < width_bytes; ++index) {
        value |= (uint64_t)g_p8_memory[address + index] << (8u * index);
    }
    ++g_p8_memory_reads;
    if (out_value != NULL) { *out_value = value; }
    return P8_RT_OK;
}

int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value)
{
    uint64_t width_bytes = 0;
    const struct p8_region *region;
    uint64_t index;
    int status = p8_width_bytes(width_bits, &width_bytes);
    if (status != P8_RT_OK) {
        ++g_p8_denied_accesses;
        return status;
    }
    p8_runtime_init();
    if (address == P8_OUTPUT_ADDR) {
        uint64_t args[1];
        uint64_t result = 0;
        if (width_bits != P8_OUTPUT_WIDTH_BITS) {
            ++g_p8_denied_accesses;
            return P8_RT_MEMORY_WIDTH_UNSUPPORTED;
        }
        args[0] = value & UINT64_C(0xFF);
        status = or_rt_host_call(UINT64_C(1), 1u, args, &result);
        if (status != P8_RT_OK) {
            ++g_p8_denied_accesses;
        }
        return status;
    }
    if (address + width_bytes > (uint64_t)P8_IMAGE_SIZE) {
        ++g_p8_denied_accesses;
        return P8_RT_MEMORY_OUT_OF_RANGE;
    }
    region = p8_region_at(address, width_bytes);
    if (region == NULL || (region->flags & P8_REGION_WRITABLE) == 0u) {
        ++g_p8_denied_accesses;
        return P8_RT_UNSUPPORTED_OPERATION;
    }
    for (index = 0; index < width_bytes; ++index) {
        g_p8_memory[address + index] = (unsigned char)((value >> (8u * index)) & UINT64_C(0xFF));
    }
    ++g_p8_memory_writes;
    return P8_RT_OK;
}

int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value)
{
    ++g_p8_host_calls;
    if (service_id == UINT64_C(1)) {
        if (argc != 1u || args == NULL) {
            return P8_RT_HOST_CALL_ARITY;
        }
        if (g_p8_transcript_length < P8_TRANSCRIPT_CAPACITY) {
            g_p8_transcript[g_p8_transcript_length++] = (unsigned char)(args[0] & UINT64_C(0xFF));
        } else {
            return P8_RT_UNSUPPORTED_OPERATION;
        }
        if (out_value != NULL) { *out_value = UINT64_C(0); }
        return P8_RT_OK;
    }
    return P8_RT_UNKNOWN_HOST_SERVICE;
}

const char *or_rt_failure_reason(int code)
{
    switch (code) {
    case P8_RT_OK: return "ok";
    case P8_RT_MEMORY_OUT_OF_RANGE: return "memory out of range";
    case P8_RT_MEMORY_WIDTH_UNSUPPORTED: return "memory width unsupported";
    case P8_RT_UNKNOWN_HOST_SERVICE: return "unknown host service";
    case P8_RT_HOST_CALL_ARITY: return "host call arity";
    case P8_RT_UNSUPPORTED_OPERATION: return "unsupported operation";
    default: return "runtime failure";
    }
}
