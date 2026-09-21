/*
 * OpenRecomp Phase 11 - additive observable driver with the opt-in execution
 * trace (OpenRecomp-authored).
 *
 * Derived from the Phase-10 additive observable driver: it prints the same
 * bounded observables (fixture identity, registers and register digest, guest
 * RAM digest, per-device event counts and digests, memory-access counters, the
 * bounded-execution budget counters and the non-RAM access log) and adds the
 * Phase-11 execution-trace observables:
 *
 *   - total block and function entry events and the ordered block-stream digest;
 *   - the first window of block entries and the trailing ring window;
 *   - per-block and per-function entry counts (address/count pairs only);
 *   - the first fail-closed indirect site with its address, message, enclosing
 *     function and its position in the block stream.
 *
 * It prints no per-event device streams: the counts and digests are the
 * comparable observables. It contains no guest machine code, no BIOS image, no
 * guest payload bytes and no console-derived material.
 */

#include <setjmp.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

void openrecomp_run(void);
int openrecomp_failed(void);
const char *openrecomp_error(void);
size_t openrecomp_register_count(void);
uint64_t openrecomp_register_value(size_t index);

void p9_runtime_init(void);
const unsigned char *p9_runtime_memory(void);
uint64_t p9_runtime_memory_reads(void);
uint64_t p9_runtime_memory_writes(void);
uint64_t p9_runtime_denied_accesses(void);
uint64_t p9_runtime_host_calls(void);
uint32_t p9_runtime_gpu_event_count(void);
uint32_t p9_runtime_input_event_count(void);
uint32_t p9_runtime_spu_event_count(void);
uint32_t p9_runtime_cdrom_event_count(void);
const struct p9_event *p9_runtime_gpu_events(void);
const struct p9_event *p9_runtime_input_events(void);
const struct p9_event *p9_runtime_spu_events(void);
const struct p9_event *p9_runtime_cdrom_events(void);

uint64_t p10_runtime_access_budget(void);
uint64_t p10_runtime_access_count(void);
uint64_t p10_runtime_budget_denials(void);
uint64_t p10_runtime_mips_service_calls(void);
uint64_t p10_runtime_mips_service_failures(void);
void p10_runtime_set_access_budget(uint64_t budget);
uint32_t p10_runtime_nonram_count(void);
uint64_t p10_runtime_nonram_overflow(void);
uint32_t p10_runtime_nonram_address(uint32_t index);
uint32_t p10_runtime_nonram_width(uint32_t index);
uint32_t p10_runtime_nonram_is_write(uint32_t index);
uint32_t p10_runtime_nonram_reason(uint32_t index);
uint64_t p10_runtime_nonram_observations(uint32_t index);

uint64_t p11_trace_block_events(void);
uint64_t p11_trace_function_events(void);
uint64_t p11_trace_block_digest(void);
uint32_t p11_trace_ring_count(void);
uint32_t p11_trace_ring_capacity(void);
uint32_t p11_trace_ring_address(uint32_t position);
uint32_t p11_trace_first_count(void);
uint32_t p11_trace_first_address(uint32_t position);
uint32_t p11_trace_table_capacity(void);
uint32_t p11_trace_block_used(void);
uint64_t p11_trace_block_overflow(void);
uint32_t p11_trace_block_key(uint32_t index);
uint64_t p11_trace_block_count(uint32_t index);
uint32_t p11_trace_function_used(void);
uint64_t p11_trace_function_overflow(void);
uint32_t p11_trace_function_key(uint32_t index);
uint64_t p11_trace_function_count(uint32_t index);
uint32_t p11_trace_failure_site(void);
uint32_t p11_trace_failure_function(void);
uint64_t p11_trace_failure_source(void);
const char *p11_trace_failure_message(void);
uint64_t p11_trace_failure_count(void);
uint64_t p11_trace_failure_block_index(void);
uint32_t p11_trace_current_function(void);
uint32_t p11_trace_failure_before_count(void);
uint32_t p11_trace_failure_before_address(uint32_t position);
uint32_t p11_trace_failure_after_count(void);
uint32_t p11_trace_failure_after_address(uint32_t position);

extern jmp_buf p11_bound_jump;
void p11_bound_arm(uint64_t budget);
void p11_bound_disarm(void);
uint64_t p11_bound_budget(void);
uint64_t p11_bound_denials(void);
int p11_bound_reached(void);

#define P11_TRACE_LAST_PRINT_LIMIT 512u

static uint64_t p10_fnv1a64(const unsigned char *data, size_t length)
{
    uint64_t hash = UINT64_C(0xcbf29ce484222325);
    size_t index;
    for (index = 0; index < length; ++index) {
        hash ^= (uint64_t)data[index];
        hash *= UINT64_C(0x100000001b3);
    }
    return hash;
}

static uint64_t p10_event_digest(const struct p9_event *events, uint32_t count)
{
    uint64_t hash = UINT64_C(0xcbf29ce484222325);
    uint32_t index;
    for (index = 0; index < count; ++index) {
        unsigned char encoded[16];
        unsigned byte;
        uint32_t address = events[index].address;
        uint32_t value = events[index].value;
        encoded[0] = (unsigned char)(events[index].service & 0xFFu);
        encoded[1] = (unsigned char)(events[index].direction & 0xFFu);
        encoded[2] = (unsigned char)(events[index].width_bits & 0xFFu);
        encoded[3] = (unsigned char)(events[index].flags & 0xFFu);
        for (byte = 0; byte < 4u; ++byte) {
            encoded[4 + byte] = (unsigned char)((address >> (8u * byte)) & 0xFFu);
            encoded[8 + byte] = (unsigned char)((value >> (8u * byte)) & 0xFFu);
            encoded[12 + byte] = 0u;
        }
        for (byte = 0; byte < 16u; ++byte) {
            hash ^= (uint64_t)encoded[byte];
            hash *= UINT64_C(0x100000001b3);
        }
    }
    return hash;
}

int main(int argc, char **argv)
{
    uint64_t index;
    uint64_t block_budget = p11_bound_budget();
    /* Optional deterministic bounded-execution budgets: the values are part of
     * the recorded invocation, never read from the environment. */
    if (argc > 1) {
        p10_runtime_set_access_budget((uint64_t)strtoull(argv[1], NULL, 10));
    }
    if (argc > 2) {
        block_budget = (uint64_t)strtoull(argv[2], NULL, 10);
    }
    uint64_t registers = UINT64_C(0xcbf29ce484222325);
    uint64_t memory;
    size_t count;
    uint32_t gpu_count;
    uint32_t input_count;
    uint32_t spu_count;
    uint32_t cdrom_count;

    p9_runtime_init();
    p11_bound_arm(block_budget);
    if (setjmp(p11_bound_jump) == 0) {
        openrecomp_run();
        p11_bound_disarm();
    }

    printf("fixture=%s\n", P9_FIXTURE_SHA256);
    printf("failed=%d\n", openrecomp_failed());
    printf("error=%s\n", openrecomp_error());
    printf("bound_budget=%llu\n", (unsigned long long)p11_bound_budget());
    printf("bound_reached=%d\n", p11_bound_reached());
    printf("bound_denials=%llu\n", (unsigned long long)p11_bound_denials());
    printf("exit_status=0x%08llx\n",
           (unsigned long long)(openrecomp_register_value(2) & UINT64_C(0xFFFFFFFF)));

    count = openrecomp_register_count();
    for (index = 0; index < count; ++index) {
        uint64_t value = openrecomp_register_value(index) & UINT64_C(0xFFFFFFFF);
        unsigned byte;
        printf("r%02llu=0x%08llx\n", (unsigned long long)index, (unsigned long long)value);
        for (byte = 0; byte < 4u; ++byte) {
            registers ^= (value >> (8u * byte)) & UINT64_C(0xFF);
            registers *= UINT64_C(0x100000001b3);
        }
    }

    memory = p10_fnv1a64(p9_runtime_memory(), (size_t)P9_IMAGE_SIZE);
    gpu_count = p9_runtime_gpu_event_count();
    input_count = p9_runtime_input_event_count();
    spu_count = p9_runtime_spu_event_count();
    cdrom_count = p9_runtime_cdrom_event_count();

    printf("registers=0x%016llx\n", (unsigned long long)registers);
    printf("memory=0x%016llx\n", (unsigned long long)memory);
    printf("gpu_events=%lu\n", (unsigned long)gpu_count);
    printf("gpu=0x%016llx\n", (unsigned long long)p10_event_digest(p9_runtime_gpu_events(), gpu_count));
    printf("input_events=%lu\n", (unsigned long)input_count);
    printf("input=0x%016llx\n", (unsigned long long)p10_event_digest(p9_runtime_input_events(), input_count));
    printf("spu_events=%lu\n", (unsigned long)spu_count);
    printf("spu=0x%016llx\n", (unsigned long long)p10_event_digest(p9_runtime_spu_events(), spu_count));
    printf("cdrom_events=%lu\n", (unsigned long)cdrom_count);
    printf("cdrom=0x%016llx\n", (unsigned long long)p10_event_digest(p9_runtime_cdrom_events(), cdrom_count));
    printf("reads=%llu\n", (unsigned long long)p9_runtime_memory_reads());
    printf("writes=%llu\n", (unsigned long long)p9_runtime_memory_writes());
    printf("denied=%llu\n", (unsigned long long)p9_runtime_denied_accesses());
    printf("host_calls=%llu\n", (unsigned long long)p9_runtime_host_calls());
    printf("p10_access_budget=%llu\n", (unsigned long long)p10_runtime_access_budget());
    printf("p10_access_count=%llu\n", (unsigned long long)p10_runtime_access_count());
    printf("p10_budget_denials=%llu\n", (unsigned long long)p10_runtime_budget_denials());
    printf("p10_service_calls=%llu\n", (unsigned long long)p10_runtime_mips_service_calls());
    printf("p10_service_failures=%llu\n", (unsigned long long)p10_runtime_mips_service_failures());

    {
        uint32_t nonram = p10_runtime_nonram_count();
        printf("nonram_signatures=%lu\n", (unsigned long)nonram);
        printf("nonram_overflow=%llu\n", (unsigned long long)p10_runtime_nonram_overflow());
        for (index = 0; index < nonram; ++index) {
            printf("nonram_%llu=0x%08x,%u,%u,%u,%llu\n", (unsigned long long)index,
                   (unsigned)p10_runtime_nonram_address((uint32_t)index),
                   (unsigned)p10_runtime_nonram_width((uint32_t)index),
                   (unsigned)p10_runtime_nonram_is_write((uint32_t)index),
                   (unsigned)p10_runtime_nonram_reason((uint32_t)index),
                   (unsigned long long)p10_runtime_nonram_observations((uint32_t)index));
        }
    }

    printf("trace_block_events=%llu\n", (unsigned long long)p11_trace_block_events());
    printf("trace_function_events=%llu\n", (unsigned long long)p11_trace_function_events());
    printf("trace_block_digest=0x%016llx\n", (unsigned long long)p11_trace_block_digest());
    printf("trace_distinct_blocks=%lu\n", (unsigned long)p11_trace_block_used());
    printf("trace_block_overflow=%llu\n", (unsigned long long)p11_trace_block_overflow());
    printf("trace_distinct_functions=%lu\n", (unsigned long)p11_trace_function_used());
    printf("trace_function_overflow=%llu\n", (unsigned long long)p11_trace_function_overflow());
    printf("trace_ring_count=%lu\n", (unsigned long)p11_trace_ring_count());
    printf("trace_ring_capacity=%lu\n", (unsigned long)p11_trace_ring_capacity());
    printf("trace_first_count=%lu\n", (unsigned long)p11_trace_first_count());
    printf("trace_failure_count=%llu\n", (unsigned long long)p11_trace_failure_count());
    printf("trace_failure_site=0x%08x\n", (unsigned)p11_trace_failure_site());
    printf("trace_failure_function=0x%08x\n", (unsigned)p11_trace_failure_function());
    printf("trace_failure_source=0x%08llx\n", (unsigned long long)p11_trace_failure_source());
    printf("trace_failure_message=%s\n", p11_trace_failure_message());
    printf("trace_failure_block_index=%llu\n", (unsigned long long)p11_trace_failure_block_index());
    printf("trace_current_function=0x%08x\n", (unsigned)p11_trace_current_function());
    printf("trace_failure_before_count=%lu\n", (unsigned long)p11_trace_failure_before_count());
    {
        uint32_t position;
        for (position = 0; position < p11_trace_failure_before_count(); ++position) {
            printf("trace_before_%lu=0x%08x\n", (unsigned long)position,
                   (unsigned)p11_trace_failure_before_address(position));
        }
    }
    printf("trace_failure_after_count=%lu\n", (unsigned long)p11_trace_failure_after_count());
    {
        uint32_t position;
        for (position = 0; position < p11_trace_failure_after_count(); ++position) {
            printf("trace_after_%lu=0x%08x\n", (unsigned long)position,
                   (unsigned)p11_trace_failure_after_address(position));
        }
    }

    {
        uint32_t first = p11_trace_first_count();
        uint32_t position;
        for (position = 0; position < first; ++position) {
            printf("trace_first_%lu=0x%08x\n", (unsigned long)position,
                   (unsigned)p11_trace_first_address(position));
        }
        {
            uint32_t ring = p11_trace_ring_count();
            uint32_t limit = ring < P11_TRACE_LAST_PRINT_LIMIT ? ring : P11_TRACE_LAST_PRINT_LIMIT;
            uint32_t start = ring - limit;
            for (position = 0; position < limit; ++position) {
                printf("trace_last_%lu=0x%08x\n", (unsigned long)position,
                       (unsigned)p11_trace_ring_address(start + position));
            }
        }
    }

    {
        uint32_t capacity = p11_trace_table_capacity();
        uint32_t slot;
        for (slot = 0; slot < capacity; ++slot) {
            uint64_t value = p11_trace_block_count(slot);
            if (value != UINT64_C(0)) {
                printf("trace_block_%lu=0x%08x,%llu\n", (unsigned long)slot,
                       (unsigned)p11_trace_block_key(slot), (unsigned long long)value);
            }
        }
        for (slot = 0; slot < capacity; ++slot) {
            uint64_t value = p11_trace_function_count(slot);
            if (value != UINT64_C(0)) {
                printf("trace_function_%lu=0x%08x,%llu\n", (unsigned long)slot,
                       (unsigned)p11_trace_function_key(slot), (unsigned long long)value);
            }
        }
    }
    return 0;
}
