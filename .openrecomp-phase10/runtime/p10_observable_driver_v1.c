/*
 * OpenRecomp Phase 10 - additive observable driver (OpenRecomp-authored).
 *
 * This driver is a Phase-10 addition: it is written from scratch and does not
 * modify the frozen Phase-9 driver. It prints the same bounded observables as
 * the Phase-9 driver (so the records stay comparable) plus, additively:
 *
 *   - the phase-10 bounded-execution counters (access budget, access count,
 *     budget denials, MIPS host-service calls and failures);
 *   - the first bounded number of typed platform events per device
 *     (service, direction, width, address, value) so GPU/controller/SPU/CD-ROM
 *     command classes can be classified from real execution rather than
 *     guessed.
 *
 * It contains no guest machine code, no BIOS image and no console-derived
 * material.
 */

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

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

#define P10_EVENT_PRINT_LIMIT 64u
#define P10_GPU_EVENT_PRINT_LIMIT 4096u

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

static void p10_print_events(const char *name, const struct p9_event *events, uint32_t count)
{
    uint32_t index;
    uint32_t limit = P10_EVENT_PRINT_LIMIT;
    if (name[0] == 'g' && name[1] == 'p' && name[2] == 'u') {
        limit = P10_GPU_EVENT_PRINT_LIMIT;
    }
    for (index = 0; index < count && index < limit; ++index) {
        printf("ev_%s_%u=%u,%u,%u,%u,0x%08x,0x%08x\n", name, index,
               (unsigned)events[index].service, (unsigned)events[index].direction,
               (unsigned)events[index].width_bits, (unsigned)events[index].flags,
               (unsigned)events[index].address, (unsigned)events[index].value);
    }
}

int main(void)
{
    uint64_t index;
    uint64_t registers = UINT64_C(0xcbf29ce484222325);
    uint64_t memory;
    size_t count;
    uint32_t gpu_count;
    uint32_t input_count;
    uint32_t spu_count;
    uint32_t cdrom_count;

    p9_runtime_init();
    openrecomp_run();

    printf("fixture=%s\n", P9_FIXTURE_SHA256);
    printf("failed=%d\n", openrecomp_failed());
    printf("error=%s\n", openrecomp_error());
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
    printf("printed_event_limit=%u\n", (unsigned)P10_EVENT_PRINT_LIMIT);
    printf("printed_gpu_event_limit=%u\n", (unsigned)P10_GPU_EVENT_PRINT_LIMIT);

    p10_print_events("gpu", p9_runtime_gpu_events(), gpu_count);
    p10_print_events("input", p9_runtime_input_events(), input_count);
    p10_print_events("spu", p9_runtime_spu_events(), spu_count);
    p10_print_events("cdrom", p9_runtime_cdrom_events(), cdrom_count);
    return 0;
}
