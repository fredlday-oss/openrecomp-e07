/*
 * OpenRecomp Phase 10 - Phase-10 MIPS service extension (OpenRecomp-authored).
 *
 * This fragment is spliced into the frozen Phase-9 bounded PS1 platform
 * runtime support translation unit, replacing only its `or_rt_host_call`
 * stub. Everything else in that translation unit (guest address translation,
 * the typed GPU/controller/timer/SPU/CD-ROM port boundary, virtual time and
 * input, counters and the event transcript) is the frozen Phase-9 runtime,
 * unchanged and physically shared: this fragment is compiled in the same
 * translation unit and reuses the Phase-9 static helpers directly.
 *
 * It implements exactly the Phase-10 host services declared by
 * `.openrecomp-phase10/src/p10_mips32_semantics_v1.py`:
 *
 *   - `add.overflow.check`: fail closed on signed 32-bit overflow;
 *   - `lwl`/`lwr`/`swl`/`swr`: the aligned-word partial-word merge exactly as
 *     specified by the frozen Phase-3 MIPS32 semantics model;
 *   - `mult`/`mfhi`: signed 32x32 -> 64 multiplication into runtime HI/LO
 *     state and the HI read.
 *
 * There is no exception delivery, no BIOS handler, no host filesystem
 * substitution and no invented device behaviour. Every memory access goes
 * through the frozen checked `or_rt_memory_read`/`or_rt_memory_write`
 * boundary, so an out-of-range or unmapped aligned word fails closed.
 *
 * Service identities are assigned in canonical sorted order and must match
 * the emitted program's `OR_RT_SERVICE_*` macros.
 */

/* OpenRecomp generic runtime ABI V1 service identities (canonical order). */
#define OR_RT_SERVICE_OPENRECOMP_MIPS_ADD_OVERFLOW_CHECK UINT64_C(1)
#define OR_RT_SERVICE_OPENRECOMP_MIPS_LWL UINT64_C(2)
#define OR_RT_SERVICE_OPENRECOMP_MIPS_LWR UINT64_C(3)
#define OR_RT_SERVICE_OPENRECOMP_MIPS_MFHI UINT64_C(4)
#define OR_RT_SERVICE_OPENRECOMP_MIPS_MULT UINT64_C(5)
#define OR_RT_SERVICE_OPENRECOMP_MIPS_SWL UINT64_C(6)
#define OR_RT_SERVICE_OPENRECOMP_MIPS_SWR UINT64_C(7)

static uint32_t g_p10_hi;
static uint32_t g_p10_lo;
static uint64_t g_p10_service_calls;
static uint64_t g_p10_service_failures;

uint64_t p10_runtime_mips_service_calls(void) { return g_p10_service_calls; }
uint64_t p10_runtime_mips_service_failures(void) { return g_p10_service_failures; }
uint32_t p10_runtime_hi(void) { return g_p10_hi; }
uint32_t p10_runtime_lo(void) { return g_p10_lo; }

static uint32_t p10_effective_word_address(uint64_t base, uint64_t offset)
{
    return (uint32_t)((base + offset) & UINT64_C(0xFFFFFFFF));
}

static int p10_read_word(uint32_t address, uint32_t *out_value)
{
    uint64_t value = 0;
    int status = or_rt_memory_read((uint64_t)address, 32u, &value);
    if (status != P9_RT_OK) {
        return status;
    }
    *out_value = (uint32_t)(value & UINT64_C(0xFFFFFFFF));
    return P9_RT_OK;
}

static int p10_write_word(uint32_t address, uint32_t value)
{
    return or_rt_memory_write((uint64_t)address, 32u, (uint64_t)value);
}

static uint32_t p10_byte(uint32_t value, unsigned index)
{
    return (value >> (8u * index)) & UINT32_C(0xFF);
}

static uint32_t p10_assemble(uint32_t b0, uint32_t b1, uint32_t b2, uint32_t b3)
{
    return (b0 & UINT32_C(0xFF)) | ((b1 & UINT32_C(0xFF)) << 8u)
         | ((b2 & UINT32_C(0xFF)) << 16u) | ((b3 & UINT32_C(0xFF)) << 24u);
}

static int p10_lwl(uint32_t address, uint32_t rt, uint64_t *out_value)
{
    uint32_t aligned = address & ~UINT32_C(3);
    uint32_t old = 0;
    uint32_t d0, d1, d2, d3;
    uint32_t offset = address & UINT32_C(3);
    int status = p10_read_word(aligned, &old);
    if (status != P9_RT_OK) {
        return status;
    }
    d0 = p10_byte(old, 0);
    d1 = p10_byte(old, 1);
    d2 = p10_byte(old, 2);
    d3 = p10_byte(old, 3);
    switch (offset) {
    case 0u:
        *out_value = (uint64_t)((rt & UINT32_C(0x00FFFFFF)) | (d0 << 24u));
        break;
    case 1u:
        *out_value = (uint64_t)((rt & UINT32_C(0x0000FFFF)) | (d1 << 24u) | (d0 << 16u));
        break;
    case 2u:
        *out_value = (uint64_t)((rt & UINT32_C(0x000000FF)) | (d2 << 24u) | (d1 << 16u) | (d0 << 8u));
        break;
    default:
        *out_value = (uint64_t)p10_assemble(d0, d1, d2, d3);
        break;
    }
    return P9_RT_OK;
}

static int p10_lwr(uint32_t address, uint32_t rt, uint64_t *out_value)
{
    uint32_t aligned = address & ~UINT32_C(3);
    uint32_t old = 0;
    uint32_t d0, d1, d2, d3;
    uint32_t offset = address & UINT32_C(3);
    int status = p10_read_word(aligned, &old);
    if (status != P9_RT_OK) {
        return status;
    }
    d0 = p10_byte(old, 0);
    d1 = p10_byte(old, 1);
    d2 = p10_byte(old, 2);
    d3 = p10_byte(old, 3);
    switch (offset) {
    case 0u:
        *out_value = (uint64_t)p10_assemble(d0, d1, d2, d3);
        break;
    case 1u:
        *out_value = (uint64_t)((rt & UINT32_C(0xFF000000)) | d1 | (d2 << 8u) | (d3 << 16u));
        break;
    case 2u:
        *out_value = (uint64_t)((rt & UINT32_C(0xFFFF0000)) | d2 | (d3 << 8u));
        break;
    default:
        *out_value = (uint64_t)((rt & UINT32_C(0xFFFFFF00)) | d3);
        break;
    }
    return P9_RT_OK;
}

static int p10_partial_store(uint32_t service_id, uint32_t address, uint32_t rt)
{
    uint32_t aligned = address & ~UINT32_C(3);
    uint32_t old = 0;
    uint32_t merged;
    uint32_t offset = address & UINT32_C(3);
    int status = p10_read_word(aligned, &old);
    if (status != P9_RT_OK) {
        return status;
    }
    merged = old;
    if (service_id == OR_RT_SERVICE_OPENRECOMP_MIPS_SWL) {
        if (offset == 0u) {
            merged = (old & UINT32_C(0xFFFFFF00)) | (p10_byte(rt, 3));
        } else if (offset == 1u) {
            merged = (old & UINT32_C(0xFFFF0000)) | (p10_byte(rt, 3) << 8u) | p10_byte(rt, 2);
        } else if (offset == 2u) {
            merged = (old & UINT32_C(0xFF000000)) | (p10_byte(rt, 3) << 16u)
                   | (p10_byte(rt, 2) << 8u) | p10_byte(rt, 1);
        } else {
            merged = p10_assemble(p10_byte(rt, 0), p10_byte(rt, 1), p10_byte(rt, 2), p10_byte(rt, 3));
        }
    } else {
        if (offset == 0u) {
            merged = p10_assemble(p10_byte(rt, 0), p10_byte(rt, 1), p10_byte(rt, 2), p10_byte(rt, 3));
        } else if (offset == 1u) {
            merged = (old & UINT32_C(0x000000FF)) | (p10_byte(rt, 0) << 8u)
                   | (p10_byte(rt, 1) << 16u) | (p10_byte(rt, 2) << 24u);
        } else if (offset == 2u) {
            merged = (old & UINT32_C(0x0000FFFF)) | (p10_byte(rt, 0) << 16u) | (p10_byte(rt, 1) << 24u);
        } else {
            merged = (old & UINT32_C(0x00FFFFFF)) | (p10_byte(rt, 0) << 24u);
        }
    }
    return p10_write_word(aligned, merged);
}

int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value)
{
    int status = P9_RT_OK;
    ++g_p9_host_calls;
    ++g_p10_service_calls;
    if (service_id == OR_RT_SERVICE_OPENRECOMP_MIPS_ADD_OVERFLOW_CHECK) {
        int64_t sum;
        if (argc != 2u || args == NULL) {
            status = P9_RT_UNSUPPORTED_OPERATION;
        } else {
            sum = (int64_t)(int32_t)(uint32_t)args[0] + (int64_t)(int32_t)(uint32_t)args[1];
            if (sum != (int64_t)(int32_t)sum) {
                /* Signed overflow: fail closed instead of inventing exception delivery. */
                status = P9_RT_UNSUPPORTED_OPERATION;
            }
        }
        if (status != P9_RT_OK) {
            ++g_p10_service_failures;
        }
        return status;
    }
    if (service_id == OR_RT_SERVICE_OPENRECOMP_MIPS_MULT) {
        int64_t product;
        if (argc != 2u || args == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        product = (int64_t)(int32_t)(uint32_t)args[0] * (int64_t)(int32_t)(uint32_t)args[1];
        g_p10_hi = (uint32_t)((uint64_t)product >> 32u);
        g_p10_lo = (uint32_t)((uint64_t)product & UINT64_C(0xFFFFFFFF));
        return P9_RT_OK;
    }
    if (service_id == OR_RT_SERVICE_OPENRECOMP_MIPS_MFHI) {
        if (out_value != NULL) {
            *out_value = (uint64_t)g_p10_hi;
        }
        return P9_RT_OK;
    }
    if (service_id == OR_RT_SERVICE_OPENRECOMP_MIPS_LWL
        || service_id == OR_RT_SERVICE_OPENRECOMP_MIPS_LWR) {
        uint32_t address;
        if (argc != 3u || args == NULL || out_value == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        address = p10_effective_word_address(args[0], args[1]);
        if (service_id == OR_RT_SERVICE_OPENRECOMP_MIPS_LWL) {
            status = p10_lwl(address, (uint32_t)args[2], out_value);
        } else {
            status = p10_lwr(address, (uint32_t)args[2], out_value);
        }
        if (status != P9_RT_OK) {
            ++g_p10_service_failures;
        }
        return status;
    }
    if (service_id == OR_RT_SERVICE_OPENRECOMP_MIPS_SWL
        || service_id == OR_RT_SERVICE_OPENRECOMP_MIPS_SWR) {
        uint32_t address;
        if (argc != 3u || args == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        address = p10_effective_word_address(args[0], args[1]);
        status = p10_partial_store((uint32_t)service_id, address, (uint32_t)args[2]);
        if (status != P9_RT_OK) {
            ++g_p10_service_failures;
        }
        return status;
    }
    return P9_RT_UNKNOWN_HOST_SERVICE;
}
