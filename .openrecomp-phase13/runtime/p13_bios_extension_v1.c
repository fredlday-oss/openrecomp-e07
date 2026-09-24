/*
 * OpenRecomp Phase 13 - C0 BIOS interrupt-routine queue mediation (OpenRecomp-authored).
 *
 * This fragment is appended after the composed Phase-11/Phase-12 runtime source
 * and provides the host side of the two documented C0 services Phase 13 proves
 * necessary to advance the Hercules initialization frontier past the C0:0x03
 * dispatcher at 0x80015f5c:
 *
 *   - ps1.bios.C0.02 SysEnqIntRP(priority, struc): insert the guest handler
 *     element at the head of the documented priority chain and write the
 *     previous head pointer into the element's next field (offset 0).
 *   - ps1.bios.C0.03 SysDeqIntRP(priority, struc): remove the head element from
 *     the priority chain, returning the removed element pointer in $v0 (0 when
 *     the chain is empty or the element is not the head).
 *
 * Documentation basis (public): PSX-SPX Kernel (BIOS) function summary,
 * C(02h) SysEnqIntRP(priority,struc), C(03h) SysDeqIntRP(priority,struc) and the
 * "Priority Chains" section (four chains 0..3; 16-byte element layout: 00h next,
 * 04h second function, 08h first function, 0Ch unused).
 *
 * This is BIOS queue bookkeeping only. There is no interrupt delivery, no
 * callback execution, no I_STAT/I_MASK access and no timer access. Every
 * unsupported priority/index/pointer fails closed with an explicit
 * P9_RT_UNSUPPORTED_OPERATION; there is no generic "ignore unsupported
 * interrupt" fallback. It contains no BIOS image or BIOS-derived code.
 */

#define P13_INTRP_CHAIN_COUNT 4u
#define P13_INTRP_ELEMENT_SIZE 16u
#define P13_INTRP_NEXT_OFFSET 0u
#define P13_INTRP_SECOND_FUNCTION_OFFSET 4u
#define P13_INTRP_FIRST_FUNCTION_OFFSET 8u
#define P13_INTRP_MAX_CHAIN_DEPTH 64u
#define P13_PAD_BUFFER_SIZE 0x22u
#define P13_PAD_BUFFER_SIZE_MAX 0x100u

static uint32_t g_p13_intrp_head[P13_INTRP_CHAIN_COUNT];
static uint64_t g_p13_intrp_enq_calls;
static uint64_t g_p13_intrp_deq_calls;
static uint64_t g_p13_intrp_registered;
static uint32_t g_p13_intrp_last_struct;
static uint32_t g_p13_intrp_last_priority;
static uint32_t g_p13_intrp_deq_result;

uint32_t p13_intrp_chain_count(void)
{
    return (uint32_t)P13_INTRP_CHAIN_COUNT;
}

uint32_t p13_intrp_head(uint32_t chain)
{
    return chain < (uint32_t)P13_INTRP_CHAIN_COUNT ? g_p13_intrp_head[chain] : 0u;
}

uint64_t p13_intrp_enq_calls(void) { return g_p13_intrp_enq_calls; }
uint64_t p13_intrp_deq_calls(void) { return g_p13_intrp_deq_calls; }
uint64_t p13_intrp_registered(void) { return g_p13_intrp_registered; }
uint32_t p13_intrp_last_struct(void) { return g_p13_intrp_last_struct; }
uint32_t p13_intrp_last_priority(void) { return g_p13_intrp_last_priority; }
uint32_t p13_intrp_deq_result(void) { return g_p13_intrp_deq_result; }

static int p13_intrp_read_u32(uint32_t address, uint32_t *out_value)
{
    uint64_t value = UINT64_C(0);
    if (or_rt_memory_read((uint64_t)address, 32u, &value) != P9_RT_OK) {
        return 0;
    }
    *out_value = (uint32_t)value;
    return 1;
}

static int p13_intrp_write_u32(uint32_t address, uint32_t value)
{
    return or_rt_memory_write((uint64_t)address, 32u, (uint64_t)value) == P9_RT_OK;
}

static int p13_intrp_element_supported(uint32_t address)
{
    uint32_t probe = 0u;
    if (address == 0u || (address & 3u) != 0u) {
        return 0;
    }
    /* The element must lie in mapped guest memory; the documented next field is
     * read to prove it (and to bound the model to real guest state). */
    return p13_intrp_read_u32(address + (uint32_t)P13_INTRP_NEXT_OFFSET, &probe);
}

int p13_bios_sys_enq_intrp(uint32_t priority, uint32_t struc, uint64_t *out_value)
{
    uint32_t node;
    uint32_t next;
    uint32_t depth;
    if (priority >= (uint32_t)P13_INTRP_CHAIN_COUNT || !p13_intrp_element_supported(struc)) {
        ++g_p10_service_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    node = g_p13_intrp_head[priority];
    for (depth = 0u; depth < (uint32_t)P13_INTRP_MAX_CHAIN_DEPTH; ++depth) {
        if (node == 0u) {
            break;
        }
        if (node == struc) {
            /* Refuse a duplicate registration rather than creating a cycle. */
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        if (!p13_intrp_read_u32(node + (uint32_t)P13_INTRP_NEXT_OFFSET, &next)) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        node = next;
    }
    if (node != 0u) {
        /* The chain is malformed or exceeds the bounded depth. */
        ++g_p10_service_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    /* Documented insertion: new element at the head; BIOS writes the previous
     * head pointer into the element's next field. */
    if (!p13_intrp_write_u32(struc + (uint32_t)P13_INTRP_NEXT_OFFSET, g_p13_intrp_head[priority])) {
        ++g_p10_service_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    g_p13_intrp_head[priority] = struc;
    ++g_p13_intrp_registered;
    ++g_p13_intrp_enq_calls;
    g_p13_intrp_last_struct = struc;
    g_p13_intrp_last_priority = priority;
    if (out_value != NULL) {
        *out_value = UINT64_C(0);
    }
    return P9_RT_OK;
}

int p13_bios_sys_deq_intrp(uint32_t priority, uint32_t struc, uint64_t *out_value)
{
    uint32_t next = 0u;
    if (priority >= (uint32_t)P13_INTRP_CHAIN_COUNT || !p13_intrp_element_supported(struc)) {
        ++g_p10_service_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    ++g_p13_intrp_deq_calls;
    g_p13_intrp_last_struct = struc;
    g_p13_intrp_last_priority = priority;
    if (g_p13_intrp_head[priority] != struc) {
        /* Documented behaviour: only the first element in a chain can be
         * removed; an empty chain or a non-head element returns 0. */
        g_p13_intrp_deq_result = 0u;
        if (out_value != NULL) {
            *out_value = UINT64_C(0);
        }
        return P9_RT_OK;
    }
    if (!p13_intrp_read_u32(struc + (uint32_t)P13_INTRP_NEXT_OFFSET, &next)) {
        ++g_p10_service_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    g_p13_intrp_head[priority] = next;
    if (g_p13_intrp_registered > UINT64_C(0)) {
        --g_p13_intrp_registered;
    }
    g_p13_intrp_deq_result = struc;
    if (out_value != NULL) {
        *out_value = (uint64_t)struc;
    }
    return P9_RT_OK;
}

/* -- documented joypad buffer bookkeeping (B0:0x12/0x13/0x14) --------------- */

static uint32_t g_p13_pad_buf1;
static uint32_t g_p13_pad_siz1;
static uint32_t g_p13_pad_buf2;
static uint32_t g_p13_pad_siz2;
static uint32_t g_p13_pad_enable;
static uint32_t g_p13_pad_started;
static uint64_t g_p13_pad_init_calls;
static uint64_t g_p13_pad_start_calls;
static uint64_t g_p13_pad_stop_calls;

uint32_t p13_pad_buf1(void) { return g_p13_pad_buf1; }
uint32_t p13_pad_siz1(void) { return g_p13_pad_siz1; }
uint32_t p13_pad_buf2(void) { return g_p13_pad_buf2; }
uint32_t p13_pad_siz2(void) { return g_p13_pad_siz2; }
uint32_t p13_pad_enable(void) { return g_p13_pad_enable; }
uint32_t p13_pad_started(void) { return g_p13_pad_started; }
uint64_t p13_pad_init_calls(void) { return g_p13_pad_init_calls; }
uint64_t p13_pad_start_calls(void) { return g_p13_pad_start_calls; }
uint64_t p13_pad_stop_calls(void) { return g_p13_pad_stop_calls; }

int p13_bios_init_pad2(uint32_t buf1, uint32_t siz1, uint32_t buf2, uint32_t siz2)
{
    uint32_t index;
    if (buf1 == 0u || buf2 == 0u || siz1 == 0u || siz2 == 0u
        || siz1 > (uint32_t)P13_PAD_BUFFER_SIZE_MAX
        || siz2 > (uint32_t)P13_PAD_BUFFER_SIZE_MAX) {
        ++g_p10_service_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    for (index = 0u; index < siz1; ++index) {
        if (or_rt_memory_write((uint64_t)(buf1 + index), 8u, UINT64_C(0)) != P9_RT_OK) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
    }
    for (index = 0u; index < siz2; ++index) {
        if (or_rt_memory_write((uint64_t)(buf2 + index), 8u, UINT64_C(0)) != P9_RT_OK) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
    }
    g_p13_pad_buf1 = buf1;
    g_p13_pad_siz1 = siz1;
    g_p13_pad_buf2 = buf2;
    g_p13_pad_siz2 = siz2;
    g_p13_pad_enable = 1u;
    ++g_p13_pad_init_calls;
    return P9_RT_OK;
}

int p13_bios_start_pad2(void)
{
    g_p13_pad_started = 1u;
    ++g_p13_pad_start_calls;
    return P9_RT_OK;
}

int p13_bios_stop_pad2(void)
{
    g_p13_pad_started = 0u;
    ++g_p13_pad_stop_calls;
    return P9_RT_OK;
}

/* -- documented memory-card bookkeeping (B0:0x4A/0x4B/0x4C) ------------------ */

static uint32_t g_p13_card_pad_enable;
static uint32_t g_p13_card_started;
static uint64_t g_p13_card_init_calls;
static uint64_t g_p13_card_start_calls;
static uint64_t g_p13_card_stop_calls;

uint32_t p13_card_pad_enable(void) { return g_p13_card_pad_enable; }
uint32_t p13_card_started(void) { return g_p13_card_started; }
uint64_t p13_card_init_calls(void) { return g_p13_card_init_calls; }
uint64_t p13_card_start_calls(void) { return g_p13_card_start_calls; }
uint64_t p13_card_stop_calls(void) { return g_p13_card_stop_calls; }

int p13_bios_init_card2(uint32_t pad_enable)
{
    if (pad_enable > 1u) {
        ++g_p10_service_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    g_p13_card_pad_enable = pad_enable;
    ++g_p13_card_init_calls;
    return P9_RT_OK;
}

int p13_bios_start_card2(void)
{
    g_p13_card_started = 1u;
    ++g_p13_card_start_calls;
    return P9_RT_OK;
}

int p13_bios_stop_card2(void)
{
    g_p13_card_started = 0u;
    ++g_p13_card_stop_calls;
    return P9_RT_OK;
}

/* -- controlled synthetic pad hook targets (tail-call mediation) ------------- */

#define P13_PAD_START_HOOK_TARGET 0x1F001884u
#define P13_PAD_STOP_HOOK_TARGET 0x1F001894u

static uint64_t g_p13_pad_start_hook_calls;
static uint64_t g_p13_pad_start_hook_last_target;
static uint64_t g_p13_pad_stop_hook_calls;
static uint64_t g_p13_pad_stop_hook_last_target;

uint64_t p13_pad_start_hook_calls(void) { return g_p13_pad_start_hook_calls; }
uint64_t p13_pad_start_hook_last_target(void) { return g_p13_pad_start_hook_last_target; }
uint64_t p13_pad_stop_hook_calls(void) { return g_p13_pad_stop_hook_calls; }
uint64_t p13_pad_stop_hook_last_target(void) { return g_p13_pad_stop_hook_last_target; }

static int p13_bios_pad_start_hook(uint64_t target)
{
    if ((uint32_t)target != (uint32_t)P13_PAD_START_HOOK_TARGET) {
        ++g_p10_service_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    ++g_p13_pad_start_hook_calls;
    g_p13_pad_start_hook_last_target = target;
    return P9_RT_OK;
}

static int p13_bios_pad_stop_hook(uint64_t target)
{
    if ((uint32_t)target != (uint32_t)P13_PAD_STOP_HOOK_TARGET) {
        ++g_p10_service_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    ++g_p13_pad_stop_hook_calls;
    g_p13_pad_stop_hook_last_target = target;
    return P9_RT_OK;
}

int p13_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value)
{
    int status = p12_bios_dispatch(service_id, argc, args, out_value);
    if (status != P9_RT_UNKNOWN_HOST_SERVICE) {
        return status;
    }
#ifdef OR_RT_SERVICE_PS1_BIOS_C0_02
    if (service_id == OR_RT_SERVICE_PS1_BIOS_C0_02) {
        if (argc != 2u || args == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p13_bios_sys_enq_intrp((uint32_t)args[0], (uint32_t)args[1], out_value);
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_C0_03
    if (service_id == OR_RT_SERVICE_PS1_BIOS_C0_03) {
        if (argc != 2u || args == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p13_bios_sys_deq_intrp((uint32_t)args[0], (uint32_t)args[1], out_value);
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_B0_12
    if (service_id == OR_RT_SERVICE_PS1_BIOS_B0_12) {
        if (argc != 4u || args == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p13_bios_init_pad2((uint32_t)args[0], (uint32_t)args[1],
                                  (uint32_t)args[2], (uint32_t)args[3]);
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_B0_13
    if (service_id == OR_RT_SERVICE_PS1_BIOS_B0_13) {
        if (argc != 0u) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p13_bios_start_pad2();
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_B0_14
    if (service_id == OR_RT_SERVICE_PS1_BIOS_B0_14) {
        if (argc != 0u) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p13_bios_stop_pad2();
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_B0_4A
    if (service_id == OR_RT_SERVICE_PS1_BIOS_B0_4A) {
        if (argc != 1u || args == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p13_bios_init_card2((uint32_t)args[0]);
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_B0_4B
    if (service_id == OR_RT_SERVICE_PS1_BIOS_B0_4B) {
        if (argc != 0u) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p13_bios_start_card2();
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_B0_4C
    if (service_id == OR_RT_SERVICE_PS1_BIOS_B0_4C) {
        if (argc != 0u) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p13_bios_stop_card2();
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_INTERNAL_PAD_START_HOOK
    if (service_id == OR_RT_SERVICE_PS1_BIOS_INTERNAL_PAD_START_HOOK) {
        if (argc != 1u || args == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p13_bios_pad_start_hook(args[0]);
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_INTERNAL_PAD_STOP_HOOK
    if (service_id == OR_RT_SERVICE_PS1_BIOS_INTERNAL_PAD_STOP_HOOK) {
        if (argc != 1u || args == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p13_bios_pad_stop_hook(args[0]);
    }
#endif
    return P9_RT_UNKNOWN_HOST_SERVICE;
}
