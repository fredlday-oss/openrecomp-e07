/*
 * OpenRecomp Phase 9 - bounded PS1 platform runtime support (OpenRecomp-authored).
 *
 * This translation unit implements the host side of the Phase-9 PS1 platform
 * contract declared by the generated `p9_image_v1` header:
 *
 *   - explicit guest address translation: KSEG0/KSEG1 main-RAM mirrors and the
 *     bounded I/O port window; every other address fails closed;
 *   - a typed platform adapter boundary for the GPU (GP0/GP1), controller,
 *     timer, SPU and CD-ROM ports, recording deterministic typed events and
 *     failing closed on unknown commands/registers;
 *   - deterministic virtual input (fixed button state) and virtual time
 *     (counter read returns the tick then advances);
 *   - interrupt ports are not modelled and fail closed;
 *   - deterministic access counters and event transcripts for the observable
 *     contract.
 *
 * It contains no guest machine code, no BIOS image, no disc image and no
 * console-derived material. The generated program is the only code that
 * executes guest semantics; the guest image is inert data.
 */

/*
 * This body is compiled after the generated `p9_image_v1` contract
 * declarations, which provide P9_IMAGE_SIZE, P9_IMAGE_SHA256, the platform
 * port constants, `struct p9_image_chunk`, `p9_image_chunks`,
 * `p9_image_chunk_count`, `struct p9_region`, `p9_regions` and
 * `p9_region_count`.
 */

#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* OpenRecomp generic runtime ABI V1 failure codes (numeric contract). */
enum {
    P9_RT_OK = 0,
    P9_RT_MEMORY_OUT_OF_RANGE = 1,
    P9_RT_MEMORY_WIDTH_UNSUPPORTED = 2,
    P9_RT_UNKNOWN_HOST_SERVICE = 6,
    P9_RT_UNSUPPORTED_OPERATION = 13
};

/* Platform service identifiers used in the event encoding. */
enum {
    P9_SERVICE_GPU = 1,
    P9_SERVICE_INPUT = 2,
    P9_SERVICE_SPU = 3,
    P9_SERVICE_CDROM = 4
};

enum {
    P9_DIRECTION_READ = 0,
    P9_DIRECTION_WRITE = 1
};

enum {
    P9_EVENT_FLAG_KNOWN = 1u,
    P9_EVENT_FLAG_BLOCKER = 2u
};

#define P9_EVENT_CAPACITY 4096u

int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value);
int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value);
int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);
const char *or_rt_failure_reason(int code);

static unsigned char g_p9_ram[P9_IMAGE_SIZE];
static struct p9_event g_p9_gpu_events[P9_EVENT_CAPACITY];
static struct p9_event g_p9_input_events[P9_EVENT_CAPACITY];
static struct p9_event g_p9_spu_events[P9_EVENT_CAPACITY];
static struct p9_event g_p9_cdrom_events[P9_EVENT_CAPACITY];
static uint32_t g_p9_gpu_count;
static uint32_t g_p9_input_count;
static uint32_t g_p9_spu_count;
static uint32_t g_p9_cdrom_count;
static uint32_t g_p9_ticks;
static uint32_t g_p9_buttons;
static uint64_t g_p9_memory_reads;
static uint64_t g_p9_memory_writes;
static uint64_t g_p9_denied_accesses;
static uint64_t g_p9_host_calls;
static int g_p9_initialized;

void p9_runtime_init(void)
{
    unsigned index;
    if (g_p9_initialized) {
        return;
    }
    memset(g_p9_ram, 0, sizeof(g_p9_ram));
    for (index = 0; index < p9_image_chunk_count; ++index) {
        uint32_t offset = p9_image_chunks[index].offset;
        uint32_t size = p9_image_chunks[index].size;
        if ((uint64_t)offset + (uint64_t)size <= (uint64_t)P9_IMAGE_SIZE) {
            memcpy(&g_p9_ram[offset], p9_image_chunks[index].data, size);
        }
    }
    g_p9_gpu_count = 0;
    g_p9_input_count = 0;
    g_p9_spu_count = 0;
    g_p9_cdrom_count = 0;
    g_p9_ticks = 0;
    g_p9_buttons = 0;
    g_p9_initialized = 1;
}

const unsigned char *p9_runtime_memory(void) { return g_p9_ram; }
uint64_t p9_runtime_memory_reads(void) { return g_p9_memory_reads; }
uint64_t p9_runtime_memory_writes(void) { return g_p9_memory_writes; }
uint64_t p9_runtime_denied_accesses(void) { return g_p9_denied_accesses; }
uint64_t p9_runtime_host_calls(void) { return g_p9_host_calls; }
uint32_t p9_runtime_gpu_event_count(void) { return g_p9_gpu_count; }
uint32_t p9_runtime_input_event_count(void) { return g_p9_input_count; }
uint32_t p9_runtime_spu_event_count(void) { return g_p9_spu_count; }
uint32_t p9_runtime_cdrom_event_count(void) { return g_p9_cdrom_count; }
const struct p9_event *p9_runtime_gpu_events(void) { return g_p9_gpu_events; }
const struct p9_event *p9_runtime_input_events(void) { return g_p9_input_events; }
const struct p9_event *p9_runtime_spu_events(void) { return g_p9_spu_events; }
const struct p9_event *p9_runtime_cdrom_events(void) { return g_p9_cdrom_events; }

static int p9_width_bytes(uint32_t width_bits, uint64_t *out_width)
{
    if (width_bits == 8u) { *out_width = 1u; return P9_RT_OK; }
    if (width_bits == 16u) { *out_width = 2u; return P9_RT_OK; }
    if (width_bits == 32u) { *out_width = 4u; return P9_RT_OK; }
    return P9_RT_MEMORY_WIDTH_UNSUPPORTED;
}

static int p9_translate_ram(uint64_t address, uint64_t width, uint32_t *out_offset)
{
    if (address >= (uint64_t)P9_RAM_KSEG0_BASE
        && address + width <= (uint64_t)P9_RAM_KSEG0_BASE + (uint64_t)P9_IMAGE_SIZE) {
        *out_offset = (uint32_t)(address - (uint64_t)P9_RAM_KSEG0_BASE);
        return 1;
    }
    if (address >= (uint64_t)P9_RAM_KSEG1_BASE
        && address + width <= (uint64_t)P9_RAM_KSEG1_BASE + (uint64_t)P9_IMAGE_SIZE) {
        *out_offset = (uint32_t)(address - (uint64_t)P9_RAM_KSEG1_BASE);
        return 1;
    }
    return 0;
}

static int p9_in_io(uint64_t address, uint64_t width)
{
    return address >= (uint64_t)P9_IO_BASE
        && address + width <= (uint64_t)P9_IO_BASE + (uint64_t)P9_IO_SIZE;
}

static void p9_record(struct p9_event *events, uint32_t *count, uint32_t service,
                      uint32_t direction, uint32_t width_bits, uint32_t flags,
                      uint32_t address, uint32_t value)
{
    if (*count < P9_EVENT_CAPACITY) {
        events[*count].service = service;
        events[*count].direction = direction;
        events[*count].width_bits = width_bits;
        events[*count].flags = flags;
        events[*count].address = address;
        events[*count].value = value;
        *count += 1;
    }
}

/* Documented coarse GP0/GP1 command-class predicates (classification only). */
static int p9_gp0_known(uint32_t command)
{
    if (command == 0x00u || command == 0x01u || command == 0x02u) return 1;
    if (command >= 0x20u && command <= 0x3Fu) return 1;
    if (command >= 0x40u && command <= 0x5Fu) return 1;
    if (command >= 0x60u && command <= 0x7Fu) return 1;
    if (command >= 0x80u && command <= 0x9Fu) return 1;
    if (command >= 0xA0u && command <= 0xBFu) return 1;
    if (command >= 0xC0u && command <= 0xDFu) return 1;
    if (command >= 0xE0u && command <= 0xE7u) return 1;
    return 0;
}

static int p9_gp1_known(uint32_t command)
{
    if (command <= 0x08u) return 1;
    if (command == 0x10u) return 1;
    return 0;
}

static int p9_cdrom_command_known(uint32_t command)
{
    return command <= 0x1Fu;
}

static int p9_spu_known(uint64_t address)
{
    if (address >= (uint64_t)P9_SPU_BASE && address < (uint64_t)P9_SPU_BASE + 0x180u) return 1;
    if (address >= (uint64_t)P9_SPU_CONTROL_BASE && address < (uint64_t)P9_SPU_CONTROL_BASE + 0x40u) return 1;
    if (address >= (uint64_t)P9_SPU_TRANSFER_BASE && address < (uint64_t)P9_SPU_TRANSFER_BASE + 0x10u) return 1;
    if (address >= (uint64_t)P9_SPU_CD_AUDIO_BASE && address < (uint64_t)P9_SPU_CD_AUDIO_BASE + 0x10u) return 1;
    return 0;
}

static int p9_platform_read(uint64_t address, uint32_t width_bits, uint64_t *out_value)
{
    uint32_t value = 0;
    if (address == (uint64_t)P9_JOY_DATA) {
        value = g_p9_buttons & 0xFFFFu;
        p9_record(g_p9_input_events, &g_p9_input_count, P9_SERVICE_INPUT,
                  P9_DIRECTION_READ, width_bits, P9_EVENT_FLAG_KNOWN,
                  (uint32_t)address, value);
        if (out_value != NULL) { *out_value = value; }
        return P9_RT_OK;
    }
    if (address == (uint64_t)P9_JOY_STAT) {
        value = 1u;
        p9_record(g_p9_input_events, &g_p9_input_count, P9_SERVICE_INPUT,
                  P9_DIRECTION_READ, width_bits, P9_EVENT_FLAG_KNOWN,
                  (uint32_t)address, value);
        if (out_value != NULL) { *out_value = value; }
        return P9_RT_OK;
    }
    if (address == (uint64_t)P9_TIMER0_COUNTER || address == (uint64_t)P9_TIMER1_COUNTER
        || address == (uint64_t)P9_TIMER2_COUNTER) {
        value = g_p9_ticks & 0xFFFFu;
        g_p9_ticks += 1u;
        p9_record(g_p9_input_events, &g_p9_input_count, P9_SERVICE_INPUT,
                  P9_DIRECTION_READ, width_bits, P9_EVENT_FLAG_KNOWN,
                  (uint32_t)address, value);
        if (out_value != NULL) { *out_value = value; }
        return P9_RT_OK;
    }
    if (address == (uint64_t)P9_JOY_MODE || address == (uint64_t)P9_JOY_CTRL
        || address == (uint64_t)P9_JOY_BAUD || address == (uint64_t)P9_TIMER0_MODE
        || address == (uint64_t)P9_TIMER1_MODE || address == (uint64_t)P9_TIMER2_MODE
        || address == (uint64_t)P9_TIMER0_TARGET || address == (uint64_t)P9_TIMER1_TARGET
        || address == (uint64_t)P9_TIMER2_TARGET) {
        p9_record(g_p9_input_events, &g_p9_input_count, P9_SERVICE_INPUT,
                  P9_DIRECTION_READ, width_bits, P9_EVENT_FLAG_KNOWN,
                  (uint32_t)address, 0u);
        if (out_value != NULL) { *out_value = 0; }
        return P9_RT_OK;
    }
    if (address == (uint64_t)P9_I_STAT || address == (uint64_t)P9_I_MASK) {
        p9_record(g_p9_input_events, &g_p9_input_count, P9_SERVICE_INPUT,
                  P9_DIRECTION_READ, width_bits, P9_EVENT_FLAG_BLOCKER,
                  (uint32_t)address, 0u);
        ++g_p9_denied_accesses;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    if (address == (uint64_t)P9_GP0_READ || address == (uint64_t)P9_GP1_READ) {
        value = 0u;
        p9_record(g_p9_gpu_events, &g_p9_gpu_count, P9_SERVICE_GPU,
                  P9_DIRECTION_READ, width_bits, P9_EVENT_FLAG_KNOWN,
                  (uint32_t)address, value);
        if (out_value != NULL) { *out_value = value; }
        return P9_RT_OK;
    }
    if (p9_spu_known(address)) {
        p9_record(g_p9_spu_events, &g_p9_spu_count, P9_SERVICE_SPU,
                  P9_DIRECTION_READ, width_bits, P9_EVENT_FLAG_KNOWN,
                  (uint32_t)address, 0u);
        if (out_value != NULL) { *out_value = 0; }
        return P9_RT_OK;
    }
    if (address >= (uint64_t)P9_CDROM_BASE && address < (uint64_t)P9_CDROM_BASE + 4u) {
        value = (address == (uint64_t)P9_CDROM_INDEX_STATUS) ? 0u : 0u;
        p9_record(g_p9_cdrom_events, &g_p9_cdrom_count, P9_SERVICE_CDROM,
                  P9_DIRECTION_READ, width_bits, P9_EVENT_FLAG_KNOWN,
                  (uint32_t)address, value);
        if (out_value != NULL) { *out_value = value; }
        return P9_RT_OK;
    }
    ++g_p9_denied_accesses;
    return P9_RT_UNSUPPORTED_OPERATION;
}

static int p9_platform_write(uint64_t address, uint32_t width_bits, uint32_t value)
{
    if (address == (uint64_t)P9_JOY_DATA) {
        g_p9_buttons = value & 0xFFFFu;
        p9_record(g_p9_input_events, &g_p9_input_count, P9_SERVICE_INPUT,
                  P9_DIRECTION_WRITE, width_bits, P9_EVENT_FLAG_KNOWN,
                  (uint32_t)address, value);
        return P9_RT_OK;
    }
    if (address == (uint64_t)P9_JOY_MODE || address == (uint64_t)P9_JOY_CTRL
        || address == (uint64_t)P9_JOY_BAUD || address == (uint64_t)P9_TIMER0_MODE
        || address == (uint64_t)P9_TIMER1_MODE || address == (uint64_t)P9_TIMER2_MODE
        || address == (uint64_t)P9_TIMER0_TARGET || address == (uint64_t)P9_TIMER1_TARGET
        || address == (uint64_t)P9_TIMER2_TARGET) {
        p9_record(g_p9_input_events, &g_p9_input_count, P9_SERVICE_INPUT,
                  P9_DIRECTION_WRITE, width_bits, P9_EVENT_FLAG_KNOWN,
                  (uint32_t)address, value);
        return P9_RT_OK;
    }
    if (address == (uint64_t)P9_I_STAT || address == (uint64_t)P9_I_MASK) {
        p9_record(g_p9_input_events, &g_p9_input_count, P9_SERVICE_INPUT,
                  P9_DIRECTION_WRITE, width_bits, P9_EVENT_FLAG_BLOCKER,
                  (uint32_t)address, value);
        ++g_p9_denied_accesses;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    if (address == (uint64_t)P9_GP0_ADDR || address == (uint64_t)P9_GP1_ADDR) {
        uint32_t command = (value >> 24) & 0xFFu;
        int known = (address == (uint64_t)P9_GP0_ADDR) ? p9_gp0_known(command)
                                                       : p9_gp1_known(command);
        p9_record(g_p9_gpu_events, &g_p9_gpu_count, P9_SERVICE_GPU,
                  P9_DIRECTION_WRITE, width_bits,
                  known ? P9_EVENT_FLAG_KNOWN : P9_EVENT_FLAG_BLOCKER,
                  (uint32_t)address, value);
        if (!known) {
            ++g_p9_denied_accesses;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return P9_RT_OK;
    }
    if (p9_spu_known(address)) {
        p9_record(g_p9_spu_events, &g_p9_spu_count, P9_SERVICE_SPU,
                  P9_DIRECTION_WRITE, width_bits, P9_EVENT_FLAG_KNOWN,
                  (uint32_t)address, value);
        return P9_RT_OK;
    }
    if (address >= (uint64_t)P9_CDROM_BASE && address < (uint64_t)P9_CDROM_BASE + 4u) {
        if (address == (uint64_t)P9_CDROM_COMMAND && !p9_cdrom_command_known(value & 0xFFu)) {
            p9_record(g_p9_cdrom_events, &g_p9_cdrom_count, P9_SERVICE_CDROM,
                      P9_DIRECTION_WRITE, width_bits, P9_EVENT_FLAG_BLOCKER,
                      (uint32_t)address, value);
            ++g_p9_denied_accesses;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        p9_record(g_p9_cdrom_events, &g_p9_cdrom_count, P9_SERVICE_CDROM,
                  P9_DIRECTION_WRITE, width_bits, P9_EVENT_FLAG_KNOWN,
                  (uint32_t)address, value);
        return P9_RT_OK;
    }
    ++g_p9_denied_accesses;
    return P9_RT_UNSUPPORTED_OPERATION;
}

int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value)
{
    uint64_t width = 0;
    uint32_t offset = 0;
    uint64_t value = 0;
    uint64_t index;
    int status = p9_width_bytes(width_bits, &width);
    if (status != P9_RT_OK) {
        ++g_p9_denied_accesses;
        return status;
    }
    p9_runtime_init();
    if (p9_translate_ram(address, width, &offset)) {
        for (index = 0; index < width; ++index) {
            value |= (uint64_t)g_p9_ram[offset + index] << (8u * index);
        }
        ++g_p9_memory_reads;
        if (out_value != NULL) { *out_value = value; }
        return P9_RT_OK;
    }
    if (p9_in_io(address, width)) {
        return p9_platform_read(address, width_bits, out_value);
    }
    ++g_p9_denied_accesses;
    return P9_RT_MEMORY_OUT_OF_RANGE;
}

int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value)
{
    uint64_t width = 0;
    uint32_t offset = 0;
    uint64_t index;
    int status = p9_width_bytes(width_bits, &width);
    if (status != P9_RT_OK) {
        ++g_p9_denied_accesses;
        return status;
    }
    p9_runtime_init();
    if (p9_translate_ram(address, width, &offset)) {
        for (index = 0; index < width; ++index) {
            g_p9_ram[offset + index] = (unsigned char)((value >> (8u * index)) & UINT64_C(0xFF));
        }
        ++g_p9_memory_writes;
        return P9_RT_OK;
    }
    if (p9_in_io(address, width)) {
        return p9_platform_write(address, width_bits, (uint32_t)(value & UINT64_C(0xFFFFFFFF)));
    }
    ++g_p9_denied_accesses;
    return P9_RT_MEMORY_OUT_OF_RANGE;
}

int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value)
{
    (void)service_id;
    (void)argc;
    (void)args;
    (void)out_value;
    ++g_p9_host_calls;
    return P9_RT_UNKNOWN_HOST_SERVICE;
}

const char *or_rt_failure_reason(int code)
{
    switch (code) {
    case P9_RT_OK: return "ok";
    case P9_RT_MEMORY_OUT_OF_RANGE: return "memory out of range";
    case P9_RT_MEMORY_WIDTH_UNSUPPORTED: return "memory width unsupported";
    case P9_RT_UNKNOWN_HOST_SERVICE: return "unknown host service";
    case P9_RT_UNSUPPORTED_OPERATION: return "unsupported operation";
    default: return "runtime failure";
    }
}
