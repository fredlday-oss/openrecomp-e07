/*
 * OpenRecomp Phase 8 - observable driver for the bounded real MIPS32 fixture
 * (OpenRecomp-authored).
 *
 * The generated `p8_image_v1` contract declarations are prepended by
 * `p8_emission_v1.build_build_set`, providing `P8_IMAGE_SIZE` and
 * `P8_FIXTURE_SHA256`.  This driver:
 *
 *   - runs the generated host program through the generic runtime ABI;
 *   - prints the bounded observable record agreed for Phase 8
 *     (exit status, full guest register file at the return boundary, guest
 *     memory digest, output transcript digest and length, access counts).
 *
 * Digest recipe (identical to the independent reference implementation):
 * FNV-1a 64-bit, offset basis 0xcbf29ce484222325, prime 0x100000001b3.
 */

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

void openrecomp_run(void);
int openrecomp_failed(void);
const char *openrecomp_error(void);
size_t openrecomp_register_count(void);
uint64_t openrecomp_register_value(size_t index);

void p8_runtime_init(void);
const unsigned char *p8_runtime_memory(void);
uint64_t p8_runtime_memory_reads(void);
uint64_t p8_runtime_memory_writes(void);
uint64_t p8_runtime_host_calls(void);
uint64_t p8_runtime_denied_accesses(void);
uint64_t p8_runtime_transcript_length(void);
const unsigned char *p8_runtime_transcript(void);

static uint64_t p8_fnv1a64(const unsigned char *data, size_t length)
{
    uint64_t hash = UINT64_C(0xcbf29ce484222325);
    size_t index;
    for (index = 0; index < length; ++index) {
        hash ^= (uint64_t)data[index];
        hash *= UINT64_C(0x100000001b3);
    }
    return hash;
}

int main(void)
{
    uint64_t index;
    uint64_t registers = UINT64_C(0xcbf29ce484222325);
    uint64_t memory;
    uint64_t transcript;
    size_t count;

    p8_runtime_init();
    openrecomp_run();

    printf("fixture=%s\n", P8_FIXTURE_SHA256);
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

    memory = p8_fnv1a64(p8_runtime_memory(), (size_t)P8_IMAGE_SIZE);
    transcript = p8_fnv1a64(p8_runtime_transcript(), (size_t)p8_runtime_transcript_length());

    printf("registers=0x%016llx\n", (unsigned long long)registers);
    printf("memory=0x%016llx\n", (unsigned long long)memory);
    printf("transcript_len=%llu\n", (unsigned long long)p8_runtime_transcript_length());
    printf("transcript=0x%016llx\n", (unsigned long long)transcript);
    printf("reads=%llu\n", (unsigned long long)p8_runtime_memory_reads());
    printf("writes=%llu\n", (unsigned long long)p8_runtime_memory_writes());
    printf("host_calls=%llu\n", (unsigned long long)p8_runtime_host_calls());
    printf("denied=%llu\n", (unsigned long long)p8_runtime_denied_accesses());
    return 0;
}
