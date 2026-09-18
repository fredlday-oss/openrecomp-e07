/*
 * OpenRecomp Phase 4 fixture - data and computation unit (P4-07).
 * Original work; Apache License 2.0 (repository LICENSE).  See p4_fixture.h.
 */
#include "p4_fixture.h"

const unsigned int p4_primes[16] = {
    2u, 3u, 5u, 7u, 11u, 13u, 17u, 19u, 23u, 29u, 31u, 37u, 41u, 43u, 47u, 53u
};

unsigned int p4_transform_counts[4] = { 1u, 2u, 3u, 4u };
unsigned int p4_checksum_seed = 0x811c9dc5u;

unsigned char p4_bss_scratch[256];
unsigned char p4_stack[8192];

unsigned int p4_prime_count(void) {
    return 16u;
}

unsigned int p4_sum_primes(void) {
    unsigned int sum = 0u;
    unsigned int index;
    for (index = 0u; index < 16u; index++) {
        sum += p4_primes[index];
    }
    return sum;
}

unsigned int p4_fib(unsigned int n) {
    unsigned int left;
    unsigned int right;
    if (n < 2u) {
        return n;
    }
    left = p4_fib(n - 1u);
    right = p4_fib(n - 2u);
    return left + right;
}

unsigned int p4_transform(unsigned int value, unsigned int selector) {
    unsigned int index = selector & 3u;
    if (index == 0u) {
        return value + p4_transform_counts[0];
    }
    if (index == 1u) {
        return value ^ (value >> 1);
    }
    if (index == 2u) {
        return (value * 3u) + p4_transform_counts[2];
    }
    return value - p4_transform_counts[3];
}

unsigned int p4_bss_roundtrip(unsigned int seed) {
    unsigned int index;
    unsigned int sum = 0u;
    for (index = 0u; index < 256u; index++) {
        p4_bss_scratch[index] = (unsigned char)((seed + index * 7u) & 0xffu);
    }
    for (index = 0u; index < 256u; index++) {
        sum = (sum << 1) ^ (unsigned int)p4_bss_scratch[index];
    }
    return sum;
}

unsigned int p4_checksum_mix(unsigned int state, unsigned int value) {
    unsigned int index;
    unsigned int current = state;
    for (index = 0u; index < 4u; index++) {
        current ^= (value >> (index * 8u)) & 0xffu;
        current *= 16777619u;
    }
    return current;
}

unsigned int p4_heap_exercise(unsigned int seed) {
    static unsigned char arena[1024];
    static unsigned int arena_top = 0u;
    unsigned int base;
    unsigned int index;
    unsigned int sum = 0u;
    base = arena_top;
    if (base + 64u > 1024u) {
        base = 0u;
    }
    for (index = 0u; index < 64u; index++) {
        arena[base + index] = (unsigned char)((seed + index * 5u) & 0xffu);
    }
    for (index = 0u; index < 64u; index++) {
        sum = (sum << 1) ^ (unsigned int)arena[base + index];
    }
    arena_top = base + 64u;
    return sum;
}
