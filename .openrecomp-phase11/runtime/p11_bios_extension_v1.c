/*
 * OpenRecomp Phase 11 - typed BIOS vector service extension (OpenRecomp-authored).
 *
 * This fragment is appended to the composed Phase-10 runtime support translation
 * unit and provides the host side of the documented BIOS vector services that
 * Phase 11 proved necessary. It contains no BIOS image, no BIOS-derived code and
 * no console-derived material: each service is a documented, typed host-side
 * contract implemented through the frozen checked guest memory boundary.
 *
 * Implemented services (documented A0 table subset):
 *
 *   - `ps1.bios.A0.2b` memset(dst, fillbyte, len):
 *       fills len bytes at dst with (fillbyte & 0xff); refuses (returns 0) when
 *       dst == 0, len == 0 or len > 0x7fffffff; otherwise returns dst.
 *       Every byte is written through `or_rt_memory_write`, so out-of-range
 *       destinations fail closed and every access is counted by the
 *       deterministic bounded-execution budget.
 *
 * Unknown service ids, unknown vector indices and wrong arities fail closed
 * with an explicit unresolved record. The dispatch is reached only from the
 * generated code's declared host call for a site that was proven to be that
 * exact vector service; nothing is inferred at runtime.
 */

/* P11_BIOS_SERVICE_IDS_BEGIN */
/* P11_BIOS_SERVICE_IDS_END */

static int p11_bios_memset(uint32_t dst, uint32_t fill_byte, uint32_t length, uint64_t *out_value)
{
    uint32_t index;
    if (out_value != NULL) {
        *out_value = UINT64_C(0);
    }
    if (dst == 0u || length == 0u || length > UINT32_C(0x7FFFFFFF)) {
        return P9_RT_OK;
    }
    for (index = 0u; index < length; ++index) {
        int status = or_rt_memory_write((uint64_t)(uint32_t)(dst + index), 8u,
                                        (uint64_t)(fill_byte & UINT32_C(0xFF)));
        if (status != P9_RT_OK) {
            return status;
        }
    }
    if (out_value != NULL) {
        *out_value = (uint64_t)dst;
    }
    return P9_RT_OK;
}

int p11_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value)
{
    if (service_id == OR_RT_SERVICE_PS1_BIOS_A0_2B) {
        int status;
        if (argc != 3u || args == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        status = p11_bios_memset((uint32_t)args[0], (uint32_t)args[1], (uint32_t)args[2], out_value);
        if (status != P9_RT_OK) {
            ++g_p10_service_failures;
        }
        return status;
    }
    return P9_RT_UNKNOWN_HOST_SERVICE;
}
