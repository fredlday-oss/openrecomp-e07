/*
 * OpenRecomp Phase 9 - observable driver for the bounded PS1 fixture
 * (OpenRecomp-authored).
 *
 * The generated `p9_image_v1` contract declarations are prepended by
 * `p9_emission_v1.build_build_set`, providing `P9_IMAGE_SIZE` and
 * `P9_FIXTURE_SHA256`. This driver:
 *
 *   - runs the generated host program through the generic runtime ABI;
 *   - prints the bounded observable record agreed for Phase 9: exit status,
 *     full guest register file at the return boundary, guest RAM digest,
 *     typed platform event counts and digests (GPU, input/timer, SPU,
 *     CD-ROM), and access counters.
 *
 * Digest recipe (identical to the independent reference implementation):
 * FNV-1a 64-bit, offset basis 0xcbf29ce484222325, prime 0x100000001b3, over
 * the canonical 16-byte event encoding
 * [service u8, direction u8, width u8, flags u8, address u32 LE, value u32 LE,
 * reserved u32 = 0].
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

static uint64_t p9_fnv1a64(const unsigned char *data, size_t length)
{
    uint64_t hash = UINT64_C(0xcbf29ce484222325);
    size_t index;
    for (index = 0; index < length; ++index) {
        hash ^= (uint64_t)data[index];
        hash *= UINT64_C(0x100000001b3);
    }
    return hash;
}

static uint64_t p9_event_digest(const struct p9_event *events, uint32_t count)
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

int main(void)
{
    uint64_t index;
    uint64_t registers = UINT64_C(0xcbf29ce484222325);
    uint64_t memory;
    size_t count;

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

    memory = p9_fnv1a64(p9_runtime_memory(), (size_t)P9_IMAGE_SIZE);

    printf("registers=0x%016llx\n", (unsigned long long)registers);
    printf("memory=0x%016llx\n", (unsigned long long)memory);
    printf("gpu_events=%lu\n", (unsigned long)p9_runtime_gpu_event_count());
    printf("gpu=0x%016llx\n",
           (unsigned long long)p9_event_digest(p9_runtime_gpu_events(), p9_runtime_gpu_event_count()));
    printf("input_events=%lu\n", (unsigned long)p9_runtime_input_event_count());
    printf("input=0x%016llx\n",
           (unsigned long long)p9_event_digest(p9_runtime_input_events(), p9_runtime_input_event_count()));
    printf("spu_events=%lu\n", (unsigned long)p9_runtime_spu_event_count());
    printf("spu=0x%016llx\n",
           (unsigned long long)p9_event_digest(p9_runtime_spu_events(), p9_runtime_spu_event_count()));
    printf("cdrom_events=%lu\n", (unsigned long)p9_runtime_cdrom_event_count());
    printf("cdrom=0x%016llx\n",
           (unsigned long long)p9_event_digest(p9_runtime_cdrom_events(), p9_runtime_cdrom_event_count()));
    printf("reads=%llu\n", (unsigned long long)p9_runtime_memory_reads());
    printf("writes=%llu\n", (unsigned long long)p9_runtime_memory_writes());
    printf("denied=%llu\n", (unsigned long long)p9_runtime_denied_accesses());
    printf("host_calls=%llu\n", (unsigned long long)p9_runtime_host_calls());
    return 0;
}
