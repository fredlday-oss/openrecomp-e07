/*
 * OpenRecomp Phase 15 - bounded interrupt / peripheral MMIO register model
 * (OpenRecomp-authored).
 *
 * This fragment is appended additively to the composed Phase-14 native runtime
 * and is reached through an anchored pre-dispatch inserted at the head of the
 * frozen Phase-9 `p9_platform_read` / `p9_platform_write` functions. It models
 * only the bounded project-owned register state the live Hercules
 * initialization path observes:
 *
 *   I_STAT  0x1F801070   read returns pending bits; write acknowledges
 *                        (`i_stat &= (value & 0xffff)`)
 *   I_MASK  0x1F801074   read returns the current mask; write stores
 *                        (`i_mask = value & 0xffff`)
 *   SYS_CONTROL / COM_DELAY  0x1F801020   32-bit deterministic register
 *   DPCR    0x1F8010F0   32-bit deterministic register
 *   D2_MADR 0x1F8010A0   32-bit deterministic register
 *   D2_BCR  0x1F8010A4   32-bit deterministic register
 *   D2_CHCR 0x1F8010A8   32-bit deterministic register; a write completes
 *                        synchronously so a following read observes bit 24
 *                        (busy) clear
 *
 * Every modelled register declares its allowed access widths. An unsupported
 * width or an unmodelled address returns `P15_MMIO_UNHANDLED`, so control falls
 * through to the frozen fail-closed platform boundary. No interrupt delivery, no
 * COP0 exception vectoring, no GPU command execution, no rasterization and no
 * asynchronous DMA timing is modelled.
 *
 * The model records a bounded, ordered access transcript of non-reconstructive
 * metadata (address, width, direction, value) for deterministic replay.
 *
 * It contains no guest machine code, no BIOS image, no disc image and no
 * console-derived material.
 */

#ifndef P15_MMIO_UNHANDLED
#define P15_MMIO_UNHANDLED ((int)-1000)
#endif

#define P15_I_STAT       UINT32_C(0x1f801070)
#define P15_I_MASK       UINT32_C(0x1f801074)
#define P15_SYS_CONTROL  UINT32_C(0x1f801020)
#define P15_D2_MADR      UINT32_C(0x1f8010a0)
#define P15_D2_BCR       UINT32_C(0x1f8010a4)
#define P15_D2_CHCR      UINT32_C(0x1f8010a8)
#define P15_DPCR         UINT32_C(0x1f8010f0)
#define P15_DICR         UINT32_C(0x1f8010f4)

/* Documented DMA channel-control start/busy bit (bit 24). */
#define P15_D2_CHCR_BUSY UINT32_C(0x01000000)

#define P15_MMIO_EVENT_CAPACITY 4096u

struct p15_mmio_event {
    uint32_t address;
    uint32_t width_bits;
    uint32_t is_write;
    uint32_t value;
};

static uint32_t g_p15_i_stat;
static uint32_t g_p15_i_mask;
static uint32_t g_p15_sys_control;
static uint32_t g_p15_d2_madr;
static uint32_t g_p15_d2_bcr;
static uint32_t g_p15_d2_chcr;
static uint32_t g_p15_dpcr;
static uint32_t g_p15_dicr;
static struct p15_mmio_event g_p15_events[P15_MMIO_EVENT_CAPACITY];
static uint32_t g_p15_event_count;
static uint64_t g_p15_event_overflow;
static uint64_t g_p15_mmio_reads;
static uint64_t g_p15_mmio_writes;
static uint64_t g_p15_mmio_unsupported;

static void p15_mmio_record(uint32_t address, uint32_t width_bits, uint32_t is_write, uint32_t value)
{
    if (g_p15_event_count < P15_MMIO_EVENT_CAPACITY) {
        g_p15_events[g_p15_event_count].address = address;
        g_p15_events[g_p15_event_count].width_bits = width_bits;
        g_p15_events[g_p15_event_count].is_write = is_write;
        g_p15_events[g_p15_event_count].value = value;
        g_p15_event_count += 1u;
    } else {
        g_p15_event_overflow += 1u;
    }
}

static int p15_width_ok(uint32_t width_bits)
{
    return width_bits == 16u || width_bits == 32u;
}

int p15_mmio_read(uint64_t address, uint32_t width_bits, uint64_t *out_value)
{
    uint32_t a = (uint32_t)address;
    uint32_t value = 0u;
    if (a == P15_I_STAT) {
        if (!p15_width_ok(width_bits)) {
            ++g_p15_mmio_unsupported;
            ++g_p9_denied_accesses;
            return P9_RT_MEMORY_WIDTH_UNSUPPORTED;
        }
        value = g_p15_i_stat;
    } else if (a == P15_I_MASK) {
        if (!p15_width_ok(width_bits)) {
            ++g_p15_mmio_unsupported;
            ++g_p9_denied_accesses;
            return P9_RT_MEMORY_WIDTH_UNSUPPORTED;
        }
        value = g_p15_i_mask;
    } else if (a == P15_SYS_CONTROL || a == P15_D2_MADR || a == P15_D2_BCR
               || a == P15_D2_CHCR || a == P15_DPCR || a == P15_DICR) {
        if (width_bits != 32u) {
            ++g_p15_mmio_unsupported;
            ++g_p9_denied_accesses;
            return P9_RT_MEMORY_WIDTH_UNSUPPORTED;
        }
        if (a == P15_SYS_CONTROL) { value = g_p15_sys_control; }
        else if (a == P15_D2_MADR) { value = g_p15_d2_madr; }
        else if (a == P15_D2_BCR) { value = g_p15_d2_bcr; }
        else if (a == P15_D2_CHCR) { value = g_p15_d2_chcr; }
        else if (a == P15_DICR) { value = g_p15_dicr; }
        else { value = g_p15_dpcr; }
    } else {
        return P15_MMIO_UNHANDLED;
    }
    if (width_bits == 16u) {
        value &= UINT32_C(0xffff);
    }
    p15_mmio_record(a, width_bits, 0u, value);
    ++g_p15_mmio_reads;
    if (out_value != NULL) { *out_value = (uint64_t)value; }
    return P9_RT_OK;
}

int p15_mmio_write(uint64_t address, uint32_t width_bits, uint32_t value)
{
    uint32_t a = (uint32_t)address;
    if (a == P15_I_STAT) {
        if (!p15_width_ok(width_bits)) {
            ++g_p15_mmio_unsupported;
            ++g_p9_denied_accesses;
            return P9_RT_MEMORY_WIDTH_UNSUPPORTED;
        }
        g_p15_i_stat &= (value & UINT32_C(0xffff));
    } else if (a == P15_I_MASK) {
        if (!p15_width_ok(width_bits)) {
            ++g_p15_mmio_unsupported;
            ++g_p9_denied_accesses;
            return P9_RT_MEMORY_WIDTH_UNSUPPORTED;
        }
        g_p15_i_mask = value & UINT32_C(0xffff);
    } else if (a == P15_SYS_CONTROL) {
        if (width_bits != 32u) {
            ++g_p15_mmio_unsupported;
            ++g_p9_denied_accesses;
            return P9_RT_MEMORY_WIDTH_UNSUPPORTED;
        }
        g_p15_sys_control = value;
    } else if (a == P15_D2_MADR) {
        if (width_bits != 32u) {
            ++g_p15_mmio_unsupported;
            ++g_p9_denied_accesses;
            return P9_RT_MEMORY_WIDTH_UNSUPPORTED;
        }
        g_p15_d2_madr = value;
    } else if (a == P15_D2_BCR) {
        if (width_bits != 32u) {
            ++g_p15_mmio_unsupported;
            ++g_p9_denied_accesses;
            return P9_RT_MEMORY_WIDTH_UNSUPPORTED;
        }
        g_p15_d2_bcr = value;
    } else if (a == P15_D2_CHCR) {
        if (width_bits != 32u) {
            ++g_p15_mmio_unsupported;
            ++g_p9_denied_accesses;
            return P9_RT_MEMORY_WIDTH_UNSUPPORTED;
        }
        /* Deterministic completion: the start/busy bit is not retained, so a
         * following read observes the channel idle. No data is transferred and
         * no GPU command is executed. */
        g_p15_d2_chcr = value & ~P15_D2_CHCR_BUSY;
    } else if (a == P15_DPCR) {
        if (width_bits != 32u) {
            ++g_p15_mmio_unsupported;
            ++g_p9_denied_accesses;
            return P9_RT_MEMORY_WIDTH_UNSUPPORTED;
        }
        g_p15_dpcr = value;
    } else if (a == P15_DICR) {
        if (width_bits != 32u) {
            ++g_p15_mmio_unsupported;
            ++g_p9_denied_accesses;
            return P9_RT_MEMORY_WIDTH_UNSUPPORTED;
        }
        g_p15_dicr = value;
    } else {
        return P15_MMIO_UNHANDLED;
    }
    p15_mmio_record(a, width_bits, 1u, value);
    ++g_p15_mmio_writes;
    return P9_RT_OK;
}

/* ---- Phase-15 observables (non-reconstructive; driver only) ---------------- */

uint32_t p15_i_stat(void) { return g_p15_i_stat; }
uint32_t p15_i_mask(void) { return g_p15_i_mask; }
uint32_t p15_sys_control(void) { return g_p15_sys_control; }
uint32_t p15_d2_madr(void) { return g_p15_d2_madr; }
uint32_t p15_d2_bcr(void) { return g_p15_d2_bcr; }
uint32_t p15_d2_chcr(void) { return g_p15_d2_chcr; }
uint32_t p15_dpcr(void) { return g_p15_dpcr; }
uint32_t p15_dicr(void) { return g_p15_dicr; }
uint64_t p15_mmio_reads(void) { return g_p15_mmio_reads; }
uint64_t p15_mmio_writes(void) { return g_p15_mmio_writes; }
uint64_t p15_mmio_unsupported(void) { return g_p15_mmio_unsupported; }
uint32_t p15_mmio_event_count(void) { return g_p15_event_count; }
uint64_t p15_mmio_event_overflow(void) { return g_p15_event_overflow; }
uint32_t p15_mmio_event_address(uint32_t index)
{
    return index < g_p15_event_count ? g_p15_events[index].address : 0u;
}
uint32_t p15_mmio_event_width(uint32_t index)
{
    return index < g_p15_event_count ? g_p15_events[index].width_bits : 0u;
}
uint32_t p15_mmio_event_is_write(uint32_t index)
{
    return index < g_p15_event_count ? g_p15_events[index].is_write : 0u;
}
uint32_t p15_mmio_event_value(uint32_t index)
{
    return index < g_p15_event_count ? g_p15_events[index].value : 0u;
}
uint64_t p15_mmio_transcript_digest(void)
{
    uint64_t hash = UINT64_C(0xcbf29ce484222325);
    uint32_t index;
    for (index = 0u; index < g_p15_event_count; ++index) {
        unsigned char encoded[16];
        unsigned byte;
        uint32_t address = g_p15_events[index].address;
        uint32_t value = g_p15_events[index].value;
        encoded[0] = (unsigned char)(g_p15_events[index].width_bits & 0xffu);
        encoded[1] = (unsigned char)(g_p15_events[index].is_write & 0xffu);
        encoded[2] = 0u;
        encoded[3] = 0u;
        for (byte = 0u; byte < 4u; ++byte) {
            encoded[4 + byte] = (unsigned char)((address >> (8u * byte)) & 0xffu);
            encoded[8 + byte] = (unsigned char)((value >> (8u * byte)) & 0xffu);
            encoded[12 + byte] = 0u;
        }
        for (byte = 0u; byte < 16u; ++byte) {
            hash ^= (uint64_t)encoded[byte];
            hash *= UINT64_C(0x100000001b3);
        }
    }
    return hash;
}
