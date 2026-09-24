/*
 * OpenRecomp Phase 14 - C0 BIOS table and early-card IRQ continuation mediation
 * (OpenRecomp-authored).
 *
 * This fragment is appended after the composed Phase-11/12/13 runtime source and
 * provides the host side of the documented service Phase 14 proves necessary to
 * advance the Hercules initialization frontier past the Phase-13 terminal
 * blocker: the indirect B0 dispatcher call at 0x80026ebc.
 *
 *   - ps1.bios.B0.56 GetC0Table(): no arguments; returns a guest pointer to the
 *     project-owned synthetic C0 jump table in $v0. The table is *not* a
 *     recovered BIOS address: it is a bounded object inside the versioned
 *     synthetic window the Phase-12 model already owns.
 *   - ps1.bios.internal.card_continuation(target): the typed synthetic
 *     continuation identity. It accepts exactly the project-owned synthetic
 *     continuation address derived from the synthetic early-card IRQ handler
 *     object and fails closed on any other value.
 *
 * Synthetic object layout (all offsets inside the Phase-12 window, never
 * authentic BIOS addresses):
 *
 *   C0 table                 base + 0x0800 ; C0[6] at base + 0x0818
 *   exception-handler object base + 0x1800 ; words +0x70 / +0x74 encode the
 *                                            early-card handler address
 *   early-card handler object base + 0x1900 ; patch at +0x28, continuation at
 *                                            +0x3c
 *
 * The guest computes the early-card handler as
 * ``((word[+0x70] & 0xffff) << 16) | (word[+0x74] & 0xffff)`` and copies five
 * words of game-side patch code to ``handler + 0x28``; the function then stores
 * ``handler + 0x3c`` as the BIOS continuation. Phase 14 preserves exactly that
 * guest-visible dataflow instead of bypassing it.
 *
 * There is no interrupt delivery, no callback execution, no I_STAT/I_MASK,
 * JOY or timer access and no BIOS image here. Every unsupported offset, index,
 * pointer or continuation target fails closed with an explicit
 * P9_RT_UNSUPPORTED_OPERATION; there is no generic allow-all BIOS table and no
 * unrestricted synthetic low-memory region.
 */

#define P14_C0_TABLE_OFFSET 0x0800u
#define P14_C0_EXCEPTION_INDEX 6u
#define P14_C0_EXCEPTION_HANDLER_OFFSET 0x1800u
#define P14_C0_EARLY_HANDLER_OFFSET 0x1900u
#define P14_CARD_PATCH_OFFSET (P14_C0_EARLY_HANDLER_OFFSET + 0x28u)
#define P14_CARD_PATCH_BYTES 20u
#define P14_CARD_CONTINUATION_OFFSET (P14_C0_EARLY_HANDLER_OFFSET + 0x3cu)

#define P14_SYNTH_ADDRESS(offset) ((uint32_t)P12_SYNTH_BASE + (uint32_t)(offset))
#define P14_C0_TABLE_ADDRESS P14_SYNTH_ADDRESS(P14_C0_TABLE_OFFSET)
#define P14_C0_EXCEPTION_HANDLER_ADDRESS P14_SYNTH_ADDRESS(P14_C0_EXCEPTION_HANDLER_OFFSET)
#define P14_CARD_HANDLER_ADDRESS P14_SYNTH_ADDRESS(P14_C0_EARLY_HANDLER_OFFSET)
#define P14_CARD_CONTINUATION_ADDRESS P14_SYNTH_ADDRESS(P14_CARD_CONTINUATION_OFFSET)

static uint32_t g_p14_c0_ready;
static uint64_t g_p14_getc0_calls;
static uint64_t g_p14_continuation_calls;
static uint64_t g_p14_continuation_last;
static uint64_t g_p14_continuation_failures;
static uint64_t g_p14_bu_init_calls;
static uint64_t g_p14_abs_calls;
static uint64_t g_p14_puts_calls;
static uint64_t g_p14_mflo_calls;

uint32_t p14_c0_table_address(void) { return P14_C0_TABLE_ADDRESS; }
uint32_t p14_c0_exception_handler_address(void) { return P14_C0_EXCEPTION_HANDLER_ADDRESS; }
uint32_t p14_card_handler_address(void) { return P14_CARD_HANDLER_ADDRESS; }
uint32_t p14_card_continuation_address(void) { return P14_CARD_CONTINUATION_ADDRESS; }
uint32_t p14_card_patch_offset(void) { return P14_CARD_PATCH_OFFSET; }
uint32_t p14_c0_ready(void) { return g_p14_c0_ready; }
uint64_t p14_getc0_calls(void) { return g_p14_getc0_calls; }
uint64_t p14_continuation_calls(void) { return g_p14_continuation_calls; }
uint64_t p14_continuation_last(void) { return g_p14_continuation_last; }
uint64_t p14_continuation_failures(void) { return g_p14_continuation_failures; }
uint64_t p14_bu_init_calls(void) { return g_p14_bu_init_calls; }
uint64_t p14_abs_calls(void) { return g_p14_abs_calls; }
uint64_t p14_puts_calls(void) { return g_p14_puts_calls; }
uint64_t p14_mflo_calls(void) { return g_p14_mflo_calls; }

/* Non-reconstructive digest of the 20-byte patched region: FNV-1a over the
 * synthetic patch bytes. The bytes themselves are never reported. */
uint64_t p14_card_patch_fnv(void)
{
    uint64_t hash = UINT64_C(0xcbf29ce484222325);
    uint32_t index;
    for (index = 0u; index < P14_CARD_PATCH_BYTES; ++index) {
        uint32_t offset = P14_CARD_PATCH_OFFSET + index;
        uint32_t word = p12_synth_read32(offset & ~3u);
        unsigned char byte = (unsigned char)((word >> (8u * (offset & 3u))) & 0xFFu);
        hash ^= (uint64_t)byte;
        hash *= UINT64_C(0x100000001b3);
    }
    return hash;
}

/* A byte-accurate non-zero-byte count of the patched region. */
uint64_t p14_card_patch_writes(void)
{
    uint64_t writes = UINT64_C(0);
    uint32_t index;
    for (index = 0u; index < P14_CARD_PATCH_BYTES; ++index) {
        uint32_t offset = P14_CARD_PATCH_OFFSET + index;
        uint32_t word = p12_synth_read32(offset & ~3u);
        if (((word >> (8u * (offset & 3u))) & 0xFFu) != 0u) {
            ++writes;
        }
    }
    return writes;
}

static void p14_c0_table_init(void)
{
    if (g_p14_c0_ready != 0u) {
        return;
    }
    /* Reuse the frozen Phase-12 initializer: it zeroes the bounded window and
     * installs the documented B0 entry 0x5b. Setting its ready flag here makes
     * the later GetB0Table call a no-op, so the C0 surface and the guest patch
     * are not erased. */
    p12_b0_table_init();
    /* C0[6] -> synthetic exception-handler object (project-owned). */
    p12_synth_write32(P14_C0_TABLE_OFFSET + (P14_C0_EXCEPTION_INDEX * 4u),
                      P14_C0_EXCEPTION_HANDLER_ADDRESS);
    /* handler+0x70 / handler+0x74 encode the high / low halves of the synthetic
     * early-card handler address, exactly as the documented guest derivation
     * reconstructs it. */
    p12_synth_write32(P14_C0_EXCEPTION_HANDLER_OFFSET + 0x70u,
                      (P14_CARD_HANDLER_ADDRESS >> 16) & 0xFFFFu);
    p12_synth_write32(P14_C0_EXCEPTION_HANDLER_OFFSET + 0x74u,
                      P14_CARD_HANDLER_ADDRESS & 0xFFFFu);
    g_p14_c0_ready = 1u;
}

static int p14_bios_get_c0_table(uint64_t *out_value)
{
    if (out_value == NULL) {
        ++g_p10_service_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    p14_c0_table_init();
    ++g_p14_getc0_calls;
    *out_value = (uint64_t)P14_C0_TABLE_ADDRESS;
    return P9_RT_OK;
}

static int p14_bios_card_continuation(uint64_t target)
{
    if ((uint32_t)target != P14_CARD_CONTINUATION_ADDRESS) {
        ++g_p10_service_failures;
        ++g_p14_continuation_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    ++g_p14_continuation_calls;
    g_p14_continuation_last = target;
    return P9_RT_OK;
}

/* -- documented follow-on initialization services --------------------------- */

/* A0:0x70 _bu_init(): no arguments; documented memory-card subsystem init. The
 * bounded model records the call and returns 0 in $v0. No card I/O, SIO, DMA,
 * interrupt or device behaviour is modelled. */
static int p14_bios_bu_init(uint64_t *out_value)
{
    ++g_p14_bu_init_calls;
    if (out_value != NULL) {
        *out_value = UINT64_C(0);
    }
    return P9_RT_OK;
}

/* A0:0x30 abs(value): documented integer absolute value; returns |value| in $v0. */
static int p14_bios_abs(uint32_t value, uint64_t *out_value)
{
    int32_t signed_value = (int32_t)value;
    uint32_t magnitude = (uint32_t)(signed_value < 0 ? -signed_value : signed_value);
    if (out_value == NULL) {
        ++g_p10_service_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    ++g_p14_abs_calls;
    *out_value = (uint64_t)magnitude;
    return P9_RT_OK;
}

/* B0:0x3F puts(text): documented string output. The host has no console, so the
 * NUL-terminated string is read through the checked guest-memory boundary within
 * a fixed bound, accounted and discarded. An unterminated string or an
 * out-of-range read fails closed. */
static int p14_bios_puts(uint32_t address)
{
    uint32_t index;
    if (address == 0u) {
        ++g_p10_service_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    for (index = 0u; index < 256u; ++index) {
        uint64_t value = UINT64_C(0);
        if (or_rt_memory_read((uint64_t)(address + index), 8u, &value) != P9_RT_OK) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        if ((value & UINT64_C(0xFF)) == UINT64_C(0)) {
            ++g_p14_puts_calls;
            return P9_RT_OK;
        }
    }
    ++g_p10_service_failures;
    return P9_RT_UNSUPPORTED_OPERATION;
}

int p14_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value)
{
    int status = p13_bios_dispatch(service_id, argc, args, out_value);
    if (status != P9_RT_UNKNOWN_HOST_SERVICE) {
        return status;
    }
#ifdef OR_RT_SERVICE_PS1_BIOS_B0_56
    if (service_id == OR_RT_SERVICE_PS1_BIOS_B0_56) {
        if (argc != 0u) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p14_bios_get_c0_table(out_value);
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_A0_70
    if (service_id == OR_RT_SERVICE_PS1_BIOS_A0_70) {
        if (argc != 0u) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p14_bios_bu_init(out_value);
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_A0_30
    if (service_id == OR_RT_SERVICE_PS1_BIOS_A0_30) {
        if (argc != 1u || args == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p14_bios_abs((uint32_t)args[0], out_value);
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_B0_3F
    if (service_id == OR_RT_SERVICE_PS1_BIOS_B0_3F) {
        if (argc != 1u || args == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p14_bios_puts((uint32_t)args[0]);
    }
#endif
#ifdef OR_RT_SERVICE_PS1_MIPS_MFLO
    if (service_id == OR_RT_SERVICE_PS1_MIPS_MFLO) {
        if (argc != 0u || out_value == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        ++g_p14_mflo_calls;
        *out_value = (uint64_t)p10_runtime_lo();
        return P9_RT_OK;
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_INTERNAL_CARD_CONTINUATION
    if (service_id == OR_RT_SERVICE_PS1_BIOS_INTERNAL_CARD_CONTINUATION) {
        if (argc != 1u || args == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p14_bios_card_continuation(args[0]);
    }
#endif
    return P9_RT_UNKNOWN_HOST_SERVICE;
}
