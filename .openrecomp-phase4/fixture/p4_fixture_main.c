/*
 * OpenRecomp Phase 4 fixture - interactive entry unit (P4-07).
 * Original work; Apache License 2.0 (repository LICENSE).  See p4_fixture.h.
 *
 * The program reads deterministic input bytes from the input window until
 * 0xff, mixes them into a checksum, emits a fixed-format transcript to the
 * output window, records exit status 0 and halts.  Timing is observed only
 * through the virtual ticks window; no host clock is read.
 */
#include "p4_fixture.h"

static void p4_out_byte(unsigned int value) {
    *(volatile unsigned char *)P4_OUT_ADDR = (unsigned char)(value & 0xffu);
}

static unsigned int p4_in_byte(void) {
    return (unsigned int)(*(volatile unsigned char *)P4_IN_ADDR);
}

static void p4_set_exit(unsigned int code) {
    *(volatile unsigned int *)P4_EXIT_ADDR = code;
}

static unsigned int p4_read_ticks(void) {
    return *(volatile unsigned int *)P4_TICKS_ADDR;
}

static void p4_write_text(const char *text) {
    unsigned int index = 0u;
    while (text[index] != (char)0) {
        p4_out_byte((unsigned int)text[index]);
        index++;
    }
}

static void p4_write_u32(unsigned int value) {
    char buffer[12];
    unsigned int index = 0u;
    if (value == 0u) {
        p4_out_byte('0');
        return;
    }
    while (value > 0u) {
        unsigned int digit = value % 10u;
        buffer[index] = (char)('0' + digit);
        index++;
        value = value / 10u;
    }
    while (index > 0u) {
        index--;
        p4_out_byte((unsigned int)buffer[index]);
    }
}

static void p4_write_hex32(unsigned int value) {
    const char *digits = "0123456789abcdef";
    unsigned int shift = 32u;
    while (shift > 0u) {
        shift -= 4u;
        p4_out_byte((unsigned int)digits[(value >> shift) & 0xfu]);
    }
}

int main(void) {
    unsigned int ticks_start = p4_read_ticks();
    unsigned int input_count = 0u;
    unsigned int input_xor = 0u;
    unsigned int checksum = p4_checksum_seed;
    unsigned int fib_value = p4_fib(10u);
    unsigned int primes_sum = p4_sum_primes();
    unsigned int prime_count = p4_prime_count();
    unsigned int bss_sum = p4_bss_roundtrip(0x5au);
    unsigned int heap_sum = p4_heap_exercise(0x33u);
    unsigned int byte;

    for (;;) {
        byte = p4_in_byte();
        if (byte == 0xffu) {
            break;
        }
        input_count++;
        input_xor ^= byte;
        checksum = p4_checksum_mix(checksum, p4_transform(byte, input_count & 3u));
    }

    checksum = p4_checksum_mix(checksum, fib_value);
    checksum = p4_checksum_mix(checksum, primes_sum);
    checksum = p4_checksum_mix(checksum, prime_count);
    checksum = p4_checksum_mix(checksum, bss_sum);
    checksum = p4_checksum_mix(checksum, heap_sum);

    p4_write_text("P4FIXTURE v1\n");
    p4_write_text("input_bytes=");
    p4_write_u32(input_count);
    p4_out_byte('\n');
    p4_write_text("input_xor=");
    p4_write_u32(input_xor);
    p4_out_byte('\n');
    p4_write_text("fib10=");
    p4_write_u32(fib_value);
    p4_out_byte('\n');
    p4_write_text("prime_count=");
    p4_write_u32(prime_count);
    p4_out_byte('\n');
    p4_write_text("primes_sum=");
    p4_write_u32(primes_sum);
    p4_out_byte('\n');
    p4_write_text("bss_sum=");
    p4_write_u32(bss_sum);
    p4_out_byte('\n');
    p4_write_text("heap_sum=");
    p4_write_u32(heap_sum);
    p4_out_byte('\n');
    p4_write_text("checksum=0x");
    p4_write_hex32(checksum);
    p4_out_byte('\n');
    p4_write_text("ticks_start=");
    p4_write_u32(ticks_start);
    p4_out_byte('\n');
    p4_write_text("ticks_end=");
    p4_write_u32(p4_read_ticks());
    p4_out_byte('\n');

    p4_set_exit(0u);
    for (;;) {
    }
}
