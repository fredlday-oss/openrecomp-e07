/*
 * OpenRecomp Phase 3 - original port support for the CoreMark MIPS32 fixture.
 *
 * This file is OpenRecomp-authored (not derived from CoreMark).  It provides
 * the platform hooks that the CoreMark barebones port expects:
 *
 *   - the five deterministic seed variables (PERFORMANCE_RUN values),
 *   - the default context count,
 *   - a deterministic synthetic tick source (no wall clock, no hardware),
 *   - the UART byte sink mapped to the P3 memory-mapped output window,
 *   - the P3 exit hook mapped to a P3 memory-mapped status word,
 *   - minimal freestanding memcpy/memset/memmove.
 *
 * P3 memory-mapped I/O contract (byte-order little-endian):
 *   0x10000000  u8   write-only UART byte window (benchmark text output)
 *   0x10000008  u32  write-only exit status word (0 = success)
 *
 * The observability of these windows is defined by the Phase-3 runtime
 * stages; this file only defines the guest-side writes.
 */

#include "coremark.h"

#define P3_UART_ADDR 0x10000000u
#define P3_EXIT_ADDR 0x10000008u
#define P3_UART_ADDR8 ((volatile unsigned char *)P3_UART_ADDR)
#define P3_EXIT_ADDR32 ((volatile ee_u32 *)P3_EXIT_ADDR)

#define P3_CLOCKS_PER_SEC 1000u
#define P3_TICK_STEP 10000u

/* Deterministic PERFORMANCE_RUN seeds (same values as the upstream barebones
 * port for TOTAL_DATA_SIZE == 2000). */
volatile ee_s32 seed1_volatile = 0x0;
volatile ee_s32 seed2_volatile = 0x0;
volatile ee_s32 seed3_volatile = 0x66;
volatile ee_s32 seed4_volatile = ITERATIONS;
volatile ee_s32 seed5_volatile = 0;

ee_u32 default_num_contexts = 1;

/* Deterministic synthetic tick source: every sample advances the tick by a
 * fixed step, so start/stop always differ by exactly 10 seconds at
 * P3_CLOCKS_PER_SEC.  This is intentionally not a hardware clock. */
static CORETIMETYPE p3_tick = 0;

CORETIMETYPE
barebones_clock(void)
{
    p3_tick += P3_TICK_STEP;
    return p3_tick;
}

#define GETMYTIME(_t)        (*_t = barebones_clock())
#define MYTIMEDIFF(fin, ini) ((fin) - (ini))
#define TIMER_RES_DIVIDER    1
#define EE_TICKS_PER_SEC     (P3_CLOCKS_PER_SEC / TIMER_RES_DIVIDER)

static CORETIMETYPE p3_start_time_val, p3_stop_time_val;

void
start_time(void)
{
    GETMYTIME(&p3_start_time_val);
}

void
stop_time(void)
{
    GETMYTIME(&p3_stop_time_val);
}

CORE_TICKS
get_time(void)
{
    CORE_TICKS elapsed = (CORE_TICKS)MYTIMEDIFF(p3_stop_time_val, p3_start_time_val);
    return elapsed;
}

secs_ret
time_in_secs(CORE_TICKS ticks)
{
    secs_ret retval = ((secs_ret)ticks) / (secs_ret)EE_TICKS_PER_SEC;
    return retval;
}

ee_u32 p3_uart_byte_count = 0;

/* 16 KiB runtime stack for the freestanding image (the entry stub sets $sp
 * to the top of this array). */
__attribute__((aligned(16))) ee_u8 p3_stack[16384];

void
p3_uart_send_char(char c)
{
    *P3_UART_ADDR8 = (unsigned char)c;
    p3_uart_byte_count++;
}

void
p3_exit(ee_u32 code)
{
    *P3_EXIT_ADDR32 = code;
    for (;;)
    {
    }
}

void
portable_init(core_portable *p, int *argc, char *argv[])
{
    (void)argc;
    (void)argv;

    if (sizeof(ee_ptr_int) != sizeof(ee_u8 *))
    {
        ee_printf("ERROR! Please define ee_ptr_int to a type that holds a pointer!\n");
    }
    if (sizeof(ee_u32) != 4)
    {
        ee_printf("ERROR! Please define ee_u32 to a 32b unsigned type!\n");
    }
    p->portable_id = 1;
}

void
portable_fini(core_portable *p)
{
    p->portable_id = 0;
}

void *
memcpy(void *dst, const void *src, size_t n)
{
    unsigned char       *d = (unsigned char *)dst;
    const unsigned char *s = (const unsigned char *)src;
    while (n--)
    {
        *d++ = *s++;
    }
    return dst;
}

void *
memmove(void *dst, const void *src, size_t n)
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

void *
memset(void *dst, int value, size_t n)
{
    unsigned char *d = (unsigned char *)dst;
    while (n--)
    {
        *d++ = (unsigned char)value;
    }
    return dst;
}
