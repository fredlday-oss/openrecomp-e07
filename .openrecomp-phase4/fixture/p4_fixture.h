/*
 * OpenRecomp Phase 4 - interactive legally-clean fixture (P4-07).
 *
 * Original work authored for OpenRecomp, licensed under the repository
 * Apache License 2.0 (see LICENSE at the repository root).  No third-party,
 * console, commercial or generated-asset material is used.
 *
 * The fixture is a deterministic, interactive freestanding MIPS32 program
 * compiled from source with the recorded toolchain and flags.  It exercises:
 *   - code: multiple translation units, recursion, loops, branches;
 *   - static/global data: const tables, initialised globals, zero-fill;
 *   - stack: recursive call depth;
 *   - heap-like arena: a bounded static bump allocator;
 *   - runtime services: byte output, byte input, virtual ticks, exit;
 *   - deterministic input: a bounded input plan terminated by 0xff;
 *   - observable output: a fixed-format transcript and a state checksum.
 *
 * MMIO interaction windows (volatile, byte-addressed):
 *   0x20000000  output byte (low 8 bits written)
 *   0x20000004  input byte  (low 8 bits read)
 *   0x20000008  exit status (32-bit write terminates the run)
 *   0x2000000c  virtual ticks (32-bit read; never a host clock)
 */
#ifndef P4_FIXTURE_H
#define P4_FIXTURE_H

#define P4_OUT_ADDR 0x20000000u
#define P4_IN_ADDR 0x20000004u
#define P4_EXIT_ADDR 0x20000008u
#define P4_TICKS_ADDR 0x2000000cu

extern unsigned int p4_checksum_seed;
extern unsigned int p4_transform_counts[4];
extern unsigned char p4_bss_scratch[256];

unsigned int p4_fib(unsigned int n);
unsigned int p4_transform(unsigned int value, unsigned int selector);
unsigned int p4_sum_primes(void);
unsigned int p4_prime_count(void);
unsigned int p4_bss_roundtrip(unsigned int seed);
unsigned int p4_checksum_mix(unsigned int state, unsigned int value);
unsigned int p4_heap_exercise(unsigned int seed);

#endif
