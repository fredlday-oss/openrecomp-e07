/*
 * OpenRecomp Phase 15 - documented BIOS service mediation (OpenRecomp-authored).
 *
 * This fragment is appended after the composed Phase-14 runtime source and
 * provides the additive Phase-15 BIOS dispatcher layer. It chains to the frozen
 * Phase-14 dispatcher for every service it does not own.
 *
 * The Phase-15 additions are the documented services the live initialization
 * path reaches:
 *
 *   A(13h) setjmp(buf): the documented incomplete POSIX setjmp. On a direct
 *   call it returns 0 in $v0.
 *   A(72h) _96_remove(): documented CD-ROM subsystem deinitialization.
 *   B(17h) ReturnFromException(), B(18h) ResetEntryInt(), B(19h)
 *   HookEntryInt(addr): documented entry-interrupt/exception bookkeeping.
 *
 * Bounded project model: interrupt and exception *delivery* is not modelled, so
 * HookEntryInt validates and records the handler pointer, ResetEntryInt clears
 * it, ReturnFromException records the call (no exception is ever pending in the
 * bounded path, so no context is restored), and _96_remove records the call.
 * The A(14h) longjmp companion is unreachable in this fixture, so the setjmp
 * jump buffer is never read and the buffer store is elided; the model never
 * fabricates saved register state.
 *
 * Any malformed invocation fails closed with P9_RT_UNSUPPORTED_OPERATION, and
 * any service not owned by Phase 15 falls through to the frozen Phase-14
 * dispatcher.
 *
 * It contains no guest machine code, no BIOS image, no disc image and no
 * console-derived material.
 */

static uint32_t g_p15_entry_int_hook;
static uint64_t g_p15_setjmp_calls;
static uint64_t g_p15_96remove_calls;
static uint64_t g_p15_hook_entry_int_calls;
static uint64_t g_p15_reset_entry_int_calls;
static uint64_t g_p15_return_from_exception_calls;
static uint64_t g_p15_bios_service_failures;
static uint64_t g_p15_enter_critical_calls;
static uint64_t g_p15_exit_critical_calls;
static uint64_t g_p15_critical_syscall_failures;
static uint32_t g_p15_cpu_interrupt_enabled = 1u;

uint32_t p15_entry_int_hook(void) { return g_p15_entry_int_hook; }
uint64_t p15_setjmp_calls(void) { return g_p15_setjmp_calls; }
uint64_t p15_96remove_calls(void) { return g_p15_96remove_calls; }
uint64_t p15_hook_entry_int_calls(void) { return g_p15_hook_entry_int_calls; }
uint64_t p15_reset_entry_int_calls(void) { return g_p15_reset_entry_int_calls; }
uint64_t p15_return_from_exception_calls(void) { return g_p15_return_from_exception_calls; }
uint64_t p15_bios_service_failures(void) { return g_p15_bios_service_failures; }
uint64_t p15_enter_critical_calls(void) { return g_p15_enter_critical_calls; }
uint64_t p15_exit_critical_calls(void) { return g_p15_exit_critical_calls; }
uint64_t p15_critical_syscall_failures(void) { return g_p15_critical_syscall_failures; }
uint32_t p15_cpu_interrupt_enabled(void) { return g_p15_cpu_interrupt_enabled; }

/* Exact execution-reached PS1 syscall selectors 1/2. Interrupt delivery is
 * absent from the bounded initialization model, so the only observable state
 * is the logical CPU interrupt-enable flag and the prior-state enter result.
 * Every other selector fails closed; no generic exception dispatch exists. */
int p15_critical_syscall(uint32_t selector, uint64_t *out_value)
{
    if (out_value == NULL) {
        ++g_p15_critical_syscall_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    if (selector == 1u) {
        *out_value = g_p15_cpu_interrupt_enabled != 0u ? UINT64_C(1) : UINT64_C(0);
        g_p15_cpu_interrupt_enabled = 0u;
        ++g_p15_enter_critical_calls;
        return P9_RT_OK;
    }
    if (selector == 2u) {
        g_p15_cpu_interrupt_enabled = 1u;
        *out_value = UINT64_C(0);
        ++g_p15_exit_critical_calls;
        return P9_RT_OK;
    }
    ++g_p15_critical_syscall_failures;
    return P9_RT_UNSUPPORTED_OPERATION;
}

/* A0:0x13 setjmp(buf): documented direct-call return of 0. The jump buffer is
 * not persisted because the A(14h) longjmp companion is unreachable in this
 * fixture and the buffer is never read. */
static int p15_bios_setjmp(uint64_t *out_value)
{
    if (out_value == NULL) {
        ++g_p15_bios_service_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    ++g_p15_setjmp_calls;
    *out_value = UINT64_C(0);
    return P9_RT_OK;
}

/* A0:0x72 _96_remove(): documented CD-ROM subsystem deinit; no observable
 * effect without interrupt delivery. */
static int p15_bios_96_remove(void)
{
    ++g_p15_96remove_calls;
    return P9_RT_OK;
}

/* B0:0x19 HookEntryInt(addr): validate and record the user entry-interrupt
 * handler pointer. The handler is never executed because no interrupt or
 * exception is delivered. */
static int p15_bios_hook_entry_int(uint32_t address)
{
    uint32_t offset = 0u;
    if (address == 0u || !p9_translate_ram((uint64_t)address, 4u, &offset)) {
        ++g_p15_bios_service_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    g_p15_entry_int_hook = address;
    ++g_p15_hook_entry_int_calls;
    return P9_RT_OK;
}

/* B0:0x18 ResetEntryInt(): clear the recorded entry-interrupt handler. */
static int p15_bios_reset_entry_int(void)
{
    g_p15_entry_int_hook = 0u;
    ++g_p15_reset_entry_int_calls;
    return P9_RT_OK;
}

/* B0:0x17 ReturnFromException(): record the call. No exception is pending in
 * the bounded path, so control continues normally. */
static int p15_bios_return_from_exception(void)
{
    ++g_p15_return_from_exception_calls;
    return P9_RT_OK;
}

int p15_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value)
{
    int status = p14_bios_dispatch(service_id, argc, args, out_value);
    if (status != P9_RT_UNKNOWN_HOST_SERVICE) {
        return status;
    }
#ifdef OR_RT_SERVICE_PS1_BIOS_A0_13
    if (service_id == OR_RT_SERVICE_PS1_BIOS_A0_13) {
        if (argc != 1u || args == NULL) {
            ++g_p15_bios_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p15_bios_setjmp(out_value);
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_A0_72
    if (service_id == OR_RT_SERVICE_PS1_BIOS_A0_72) {
        if (argc != 0u) {
            ++g_p15_bios_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p15_bios_96_remove();
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_B0_19
    if (service_id == OR_RT_SERVICE_PS1_BIOS_B0_19) {
        if (argc != 1u || args == NULL) {
            ++g_p15_bios_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p15_bios_hook_entry_int((uint32_t)args[0]);
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_B0_18
    if (service_id == OR_RT_SERVICE_PS1_BIOS_B0_18) {
        if (argc != 0u) {
            ++g_p15_bios_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p15_bios_reset_entry_int();
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_B0_17
    if (service_id == OR_RT_SERVICE_PS1_BIOS_B0_17) {
        if (argc != 0u) {
            ++g_p15_bios_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p15_bios_return_from_exception();
    }
#endif
    return P9_RT_UNKNOWN_HOST_SERVICE;
}
