/*
 * OpenRecomp Phase 12 - synthetic B0 BIOS object mediation (OpenRecomp-authored).
 *
 * This fragment is appended after the composed Phase-10/Phase-11 runtime source
 * and provides the host side of the two documented B0 services Phase 12 proves
 * necessary, plus the synthetic project-owned guest data window that models the
 * BIOS-resident B0 jump-table object.
 *
 * It contains no BIOS image, no BIOS-derived code and no console material. The
 * synthetic window is implementation-defined: it is never a recovered BIOS
 * address, and unknown B0 table entries stay zero and fail closed when
 * dereferenced.
 *
 * Services:
 *   - ps1.bios.B0.57 GetB0Table: no arguments; returns the synthetic B0 table
 *     base in $v0.
 *   - ps1.bios.B0.5b ChangeClearPAD(mode): records the documented pad/card
 *     clear auto-acknowledge mode (0 or 1); any other mode or arity fails
 *     closed. No SIO, interrupt, DMA or device behaviour is modelled.
 */

static void p12_synth_write32(uint32_t offset, uint32_t value)
{
    g_p12_synth[offset + 0u] = (unsigned char)(value & 0xFFu);
    g_p12_synth[offset + 1u] = (unsigned char)((value >> 8u) & 0xFFu);
    g_p12_synth[offset + 2u] = (unsigned char)((value >> 16u) & 0xFFu);
    g_p12_synth[offset + 3u] = (unsigned char)((value >> 24u) & 0xFFu);
}

uint32_t p12_synth_read32(uint32_t offset)
{
    return (uint32_t)g_p12_synth[offset + 0u]
        | ((uint32_t)g_p12_synth[offset + 1u] << 8u)
        | ((uint32_t)g_p12_synth[offset + 2u] << 16u)
        | ((uint32_t)g_p12_synth[offset + 3u] << 24u);
}

static int p12_synth_translate(uint64_t address, uint64_t width, uint32_t *out_offset)
{
    if (address >= (uint64_t)P12_SYNTH_BASE
        && address + width <= (uint64_t)P12_SYNTH_BASE + (uint64_t)P12_SYNTH_SIZE) {
        *out_offset = (uint32_t)(address - (uint64_t)P12_SYNTH_BASE);
        return 1;
    }
    return 0;
}

static uint32_t g_p12_b0_table_ready;
static uint32_t g_p12_change_clear_pad;
static uint64_t g_p12_change_clear_calls;
static uint64_t g_p12_cache_flushes;

static void p12_b0_table_init(void)
{
    uint32_t index;
    if (g_p12_b0_table_ready != 0u) {
        return;
    }
    for (index = 0u; index < (uint32_t)P12_SYNTH_SIZE; ++index) {
        g_p12_synth[index] = 0u;
    }
    /* B0 entry 0x5b models the BIOS-resident ChangeClearPAD function object. */
    p12_synth_write32(0x16cu, (uint32_t)(P12_SYNTH_BASE + 0x1000u));
    g_p12_b0_table_ready = 1u;
}

uint32_t p12_bios_table_base(void) { return (uint32_t)P12_SYNTH_BASE; }
uint32_t p12_bios_b0_entry(uint32_t index) { return p12_synth_read32(index * 4u); }
uint32_t p12_bios_change_clear_pad(void) { return g_p12_change_clear_pad; }
uint64_t p12_bios_change_clear_calls(void) { return g_p12_change_clear_calls; }
uint64_t p12_bios_cache_flushes(void) { return g_p12_cache_flushes; }
uint64_t p12_bios_synth_reads(void) { return g_p12_synth_reads; }
uint64_t p12_bios_synth_writes(void) { return g_p12_synth_writes; }

static int p12_bios_get_b0_table(uint64_t *out_value)
{
    if (out_value == NULL) {
        ++g_p10_service_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    p12_b0_table_init();
    *out_value = (uint64_t)P12_SYNTH_BASE;
    return P9_RT_OK;
}

static int p12_bios_set_change_clear_pad(uint32_t mode)
{
    if (mode > 1u) {
        ++g_p10_service_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    g_p12_change_clear_pad = mode;
    ++g_p12_change_clear_calls;
    return P9_RT_OK;
}

static int p12_bios_flush_cache(void)
{
    ++g_p12_cache_flushes;
    return P9_RT_OK;
}

int p12_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value)
{
    int status = p11_bios_dispatch(service_id, argc, args, out_value);
    if (status != P9_RT_UNKNOWN_HOST_SERVICE) {
        return status;
    }
#ifdef OR_RT_SERVICE_PS1_BIOS_B0_57
    if (service_id == OR_RT_SERVICE_PS1_BIOS_B0_57) {
        if (argc != 0u) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p12_bios_get_b0_table(out_value);
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_B0_5B
    if (service_id == OR_RT_SERVICE_PS1_BIOS_B0_5B) {
        if (argc != 1u || args == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p12_bios_set_change_clear_pad((uint32_t)args[0]);
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_A0_44
    if (service_id == OR_RT_SERVICE_PS1_BIOS_A0_44) {
        if (argc != 0u) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p12_bios_flush_cache();
    }
#endif
    return P9_RT_UNKNOWN_HOST_SERVICE;
}
