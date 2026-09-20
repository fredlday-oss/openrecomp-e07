/*
 * OpenRecomp Phase 8 - original port support for the real MIPS32 fixture.
 *
 * This file is OpenRecomp-authored.  It provides the bounded freestanding
 * contract of the fixture:
 *
 *   0x10000000  u8   write-only output byte window (guest side only here)
 *   16 KiB static stack for the entry stub
 *   freestanding memcpy/memmove/memset
 *
 * The guest program terminates by returning from p8_main; the host observes
 * the register file at that boundary.  No wall clock, heap or libc is used.
 */

#define P8_OUT_ADDR 0x10000000u
#define P8_OUT_ADDR8 ((volatile unsigned char *)P8_OUT_ADDR)

__attribute__((aligned(16))) unsigned char p8_stack[16384];

void p8_out_byte(char c)
{
    *P8_OUT_ADDR8 = (unsigned char)c;
}

void *memcpy(void *dst, const void *src, unsigned long n)
{
    unsigned char       *d = (unsigned char *)dst;
    const unsigned char *s = (const unsigned char *)src;
    while (n--)
    {
        *d++ = *s++;
    }
    return dst;
}

void *memmove(void *dst, const void *src, unsigned long n)
{
    unsigned char       *d = (unsigned char *)dst;
    const unsigned char *s = (const unsigned char *)src;
    if (d < s)
    {
        while (n--)
        {
            *d++ = *s++;
        }
    }
    else if (d > s)
    {
        d += n;
        s += n;
        while (n--)
        {
            *--d = *--s;
        }
    }
    return dst;
}

void *memset(void *dst, int value, unsigned long n)
{
    unsigned char *d = (unsigned char *)dst;
    while (n--)
    {
        *d++ = (unsigned char)value;
    }
    return dst;
}
