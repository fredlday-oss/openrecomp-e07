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
 *   - `ps1.bios.A0.3f` printf(fmt, arg1, arg2):
 *       bounded documented printf subset (%% %c %s %d %i %u %x %X %o with
 *       flags, width and precision). The host has no console, so the formatted
 *       text is consumed, counted and discarded; the documented return value is
 *       the number of characters that would have been written, and a
 *       non-reconstructive FNV-1a digest of the formatted characters is
 *       recorded. Malformed or unsupported conversions, an over-long format or
 *       string, or more varargs than the declared surface fail closed.
 *
 *   - `ps1.bios.A0.49` GPU_cw(command):
 *       submits exactly one 32-bit command through `or_rt_memory_write` at the
 *       declared GP0 port. The frozen Phase-9 typed boundary performs command
 *       classification, records the ordered event and fails closed for an
 *       unknown command. This service performs no rendering or GPU emulation
 *       and has no return value.
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

static int p11_bios_gpu_cw(uint32_t command)
{
    return or_rt_memory_write((uint64_t)P9_GP0_ADDR, 32u, (uint64_t)command);
}

/* --- documented A0:0x3f printf (bounded, no console) --------------------- */

#define P11_PRINTF_MAX_FORMAT 4096u
#define P11_PRINTF_MAX_OUTPUT 65536u
#define P11_PRINTF_MAX_CONVERSIONS 128u
#define P11_PRINTF_MAX_STRING 4096u
#define P11_PRINTF_MAX_VARARGS 2u

static uint32_t g_p11_printf_calls;
static uint64_t g_p11_printf_chars;
static uint64_t g_p11_printf_digest = UINT64_C(0xcbf29ce484222325);
static uint32_t g_p11_printf_failures;

uint32_t p11_bios_printf_calls(void) { return g_p11_printf_calls; }
uint64_t p11_bios_printf_chars(void) { return g_p11_printf_chars; }
uint64_t p11_bios_printf_digest(void) { return g_p11_printf_digest; }
uint32_t p11_bios_printf_failures(void) { return g_p11_printf_failures; }

static void p11_printf_emit(uint32_t value)
{
    g_p11_printf_digest ^= (uint64_t)(value & UINT32_C(0xFF));
    g_p11_printf_digest *= UINT64_C(0x100000001b3);
    ++g_p11_printf_chars;
}

static void p11_printf_emit_repeat(uint32_t value, uint32_t times)
{
    uint32_t index;
    for (index = 0u; index < times; ++index) {
        p11_printf_emit(value);
    }
}

static int p11_printf_read_byte(uint32_t address, uint32_t *out_value)
{
    uint64_t value = 0;
    int status = or_rt_memory_read((uint64_t)address, 8u, &value);
    if (status != P9_RT_OK) {
        return status;
    }
    *out_value = (uint32_t)(value & UINT64_C(0xFF));
    return P9_RT_OK;
}

static uint32_t p11_printf_digits(uint32_t value, uint32_t base)
{
    uint32_t digits = 1u;
    while (value >= base) {
        value /= base;
        ++digits;
    }
    return digits;
}

static uint32_t p11_printf_digit_char(uint32_t digit, int upper)
{
    if (digit < 10u) {
        return (uint32_t)('0' + digit);
    }
    return (uint32_t)((upper ? 'A' : 'a') + (digit - 10u));
}

static int p11_printf_emit_number(uint32_t value, uint32_t base, int upper,
                                  uint32_t precision, int has_precision)
{
    uint32_t buffer[32];
    uint32_t digits = 0u;
    uint32_t index;
    if (value == 0u) {
        if (!has_precision || precision > 0u) {
            buffer[digits++] = (uint32_t)'0';
        }
    } else {
        while (value != 0u) {
            buffer[digits++] = p11_printf_digit_char(value % base, upper);
            value /= base;
        }
    }
    if (has_precision && precision > digits) {
        uint32_t padding = precision - digits;
        for (index = 0u; index < padding; ++index) {
            p11_printf_emit((uint32_t)'0');
        }
    }
    for (index = 0u; index < digits; ++index) {
        p11_printf_emit(buffer[digits - 1u - index]);
    }
    return P9_RT_OK;
}

static int p11_bios_printf(uint32_t fmt, uint32_t arg1, uint32_t arg2, uint64_t *out_value)
{
    uint32_t args[P11_PRINTF_MAX_VARARGS];
    uint32_t used = 0u;
    uint32_t conversions = 0u;
    uint32_t scanned = 0u;
    uint32_t address = fmt;
    uint64_t call_start = g_p11_printf_chars;
    int status;
    args[0] = arg1;
    args[1] = arg2;
    if (out_value != NULL) {
        *out_value = UINT64_C(0);
    }
    if (fmt == 0u) {
        ++g_p11_printf_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    for (;;) {
        uint32_t ch = 0u;
        int left = 0;
        int zero_pad = 0;
        int plus = 0;
        int space = 0;
        int alternate = 0;
        uint32_t width = 0u;
        uint32_t precision = 0u;
        int has_precision = 0;
        uint32_t value = 0u;
        uint32_t body = 0u;
        uint32_t prefix = 0u;
        uint32_t pad_char = (uint32_t)' ';
        uint32_t pad = 0u;

        if (++scanned > P11_PRINTF_MAX_FORMAT) {
            ++g_p11_printf_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        status = p11_printf_read_byte(address, &ch);
        if (status != P9_RT_OK) {
            ++g_p11_printf_failures;
            return status;
        }
        ++address;
        if (ch == 0u) {
            break;
        }
        if (ch != (uint32_t)'%') {
            p11_printf_emit(ch);
            continue;
        }
        if (++conversions > P11_PRINTF_MAX_CONVERSIONS) {
            ++g_p11_printf_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        for (;;) {
            status = p11_printf_read_byte(address, &ch);
            if (status != P9_RT_OK) {
                ++g_p11_printf_failures;
                return status;
            }
            ++address;
            if (ch == (uint32_t)'-') { left = 1; continue; }
            if (ch == (uint32_t)'0') { zero_pad = 1; continue; }
            if (ch == (uint32_t)'+') { plus = 1; continue; }
            if (ch == (uint32_t)' ') { space = 1; continue; }
            if (ch == (uint32_t)'#') { alternate = 1; continue; }
            break;
        }
        while (ch >= (uint32_t)'0' && ch <= (uint32_t)'9') {
            if (width > 999u) {
                ++g_p11_printf_failures;
                return P9_RT_UNSUPPORTED_OPERATION;
            }
            width = width * 10u + (ch - (uint32_t)'0');
            status = p11_printf_read_byte(address, &ch);
            if (status != P9_RT_OK) {
                ++g_p11_printf_failures;
                return status;
            }
            ++address;
        }
        if (ch == (uint32_t)'.') {
            has_precision = 1;
            status = p11_printf_read_byte(address, &ch);
            if (status != P9_RT_OK) {
                ++g_p11_printf_failures;
                return status;
            }
            ++address;
            while (ch >= (uint32_t)'0' && ch <= (uint32_t)'9') {
                if (precision > 999u) {
                    ++g_p11_printf_failures;
                    return P9_RT_UNSUPPORTED_OPERATION;
                }
                precision = precision * 10u + (ch - (uint32_t)'0');
                status = p11_printf_read_byte(address, &ch);
                if (status != P9_RT_OK) {
                    ++g_p11_printf_failures;
                    return status;
                }
                ++address;
            }
        }
        if (ch == (uint32_t)'%') {
            if (left || zero_pad || plus || space || alternate || width != 0u || has_precision) {
                ++g_p11_printf_failures;
                return P9_RT_UNSUPPORTED_OPERATION;
            }
            p11_printf_emit((uint32_t)'%');
            continue;
        }
        if (ch == (uint32_t)'c' || ch == (uint32_t)'s' || ch == (uint32_t)'d'
            || ch == (uint32_t)'i' || ch == (uint32_t)'u' || ch == (uint32_t)'x'
            || ch == (uint32_t)'X' || ch == (uint32_t)'o') {
            if (used >= P11_PRINTF_MAX_VARARGS) {
                ++g_p11_printf_failures;
                return P9_RT_UNSUPPORTED_OPERATION;
            }
            value = args[used++];
        } else {
            ++g_p11_printf_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        if (ch == (uint32_t)'c') {
            if (has_precision) {
                ++g_p11_printf_failures;
                return P9_RT_UNSUPPORTED_OPERATION;
            }
            body = 1u;
            pad = width > body ? width - body : 0u;
            if (!left) {
                p11_printf_emit_repeat(pad_char, pad);
            }
            p11_printf_emit(value & UINT32_C(0xFF));
            if (left) {
                p11_printf_emit_repeat(pad_char, pad);
            }
            continue;
        }
        if (ch == (uint32_t)'s') {
            uint32_t string_address = value;
            uint32_t length = 0u;
            uint32_t index;
            if (string_address == 0u) {
                ++g_p11_printf_failures;
                return P9_RT_UNSUPPORTED_OPERATION;
            }
            for (;;) {
                uint32_t byte = 0u;
                if (length >= P11_PRINTF_MAX_STRING) {
                    ++g_p11_printf_failures;
                    return P9_RT_UNSUPPORTED_OPERATION;
                }
                status = p11_printf_read_byte(string_address + length, &byte);
                if (status != P9_RT_OK) {
                    ++g_p11_printf_failures;
                    return status;
                }
                if (byte == 0u) {
                    break;
                }
                ++length;
            }
            if (has_precision && precision < length) {
                length = precision;
            }
            pad = width > length ? width - length : 0u;
            if (!left) {
                p11_printf_emit_repeat(pad_char, pad);
            }
            for (index = 0u; index < length; ++index) {
                uint32_t byte = 0u;
                status = p11_printf_read_byte(string_address + index, &byte);
                if (status != P9_RT_OK) {
                    ++g_p11_printf_failures;
                    return status;
                }
                p11_printf_emit(byte);
            }
            if (left) {
                p11_printf_emit_repeat(pad_char, pad);
            }
            continue;
        }
        /* numeric conversions */
        {
            uint32_t base = 10u;
            int upper = 0;
            int negative = 0;
            uint32_t hex_prefix = 0u;
            if (ch == (uint32_t)'x' || ch == (uint32_t)'X') {
                base = 16u;
                upper = ch == (uint32_t)'X';
            } else if (ch == (uint32_t)'o') {
                base = 8u;
            }
            if (ch == (uint32_t)'d' || ch == (uint32_t)'i') {
                int32_t signed_value = (int32_t)value;
                if (signed_value < 0) {
                    negative = 1;
                    value = (uint32_t)(-(int64_t)signed_value);
                }
            } else {
                if (plus || space) {
                    ++g_p11_printf_failures;
                    return P9_RT_UNSUPPORTED_OPERATION;
                }
            }
            if (negative) {
                prefix = (uint32_t)'-';
            } else if (plus) {
                prefix = (uint32_t)'+';
            } else if (space) {
                prefix = (uint32_t)' ';
            }
            if (alternate && base == 16u && value != 0u) {
                hex_prefix = 2u;
            }
            body = p11_printf_digits(value, base);
            if (has_precision && precision > body) {
                body = precision;
            }
            {
                uint32_t total = body + hex_prefix + (prefix != 0u ? 1u : 0u);
                pad = width > total ? width - total : 0u;
            }
            if (!left) {
                if (zero_pad && !has_precision) {
                    if (prefix != 0u) {
                        p11_printf_emit(prefix);
                        prefix = 0u;
                    }
                    if (hex_prefix != 0u) {
                        p11_printf_emit((uint32_t)'0');
                        p11_printf_emit(upper ? (uint32_t)'X' : (uint32_t)'x');
                        hex_prefix = 0u;
                    }
                    p11_printf_emit_repeat((uint32_t)'0', pad);
                    pad = 0u;
                } else {
                    p11_printf_emit_repeat(pad_char, pad);
                    pad = 0u;
                }
            }
            if (prefix != 0u) {
                p11_printf_emit(prefix);
            }
            if (hex_prefix != 0u) {
                p11_printf_emit((uint32_t)'0');
                p11_printf_emit(upper ? (uint32_t)'X' : (uint32_t)'x');
            }
            status = p11_printf_emit_number(value, base, upper, precision, has_precision);
            if (status != P9_RT_OK) {
                ++g_p11_printf_failures;
                return status;
            }
            if (left) {
                p11_printf_emit_repeat(pad_char, pad);
            }
            continue;
        }
    }
    if (g_p11_printf_chars - call_start > (uint64_t)P11_PRINTF_MAX_OUTPUT) {
        ++g_p11_printf_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    ++g_p11_printf_calls;
    if (out_value != NULL) {
        *out_value = g_p11_printf_chars - call_start;
    }
    return P9_RT_OK;
}

int p11_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value)
{
#ifdef OR_RT_SERVICE_PS1_BIOS_A0_2B
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
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_A0_3F
    if (service_id == OR_RT_SERVICE_PS1_BIOS_A0_3F) {
        int status;
        if (argc != 3u || args == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        status = p11_bios_printf((uint32_t)args[0], (uint32_t)args[1], (uint32_t)args[2], out_value);
        if (status != P9_RT_OK) {
            ++g_p10_service_failures;
        }
        return status;
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_A0_49
    if (service_id == OR_RT_SERVICE_PS1_BIOS_A0_49) {
        int status;
        if (argc != 1u || args == NULL) {
            ++g_p10_service_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        status = p11_bios_gpu_cw((uint32_t)args[0]);
        if (status != P9_RT_OK) {
            ++g_p10_service_failures;
        }
        return status;
    }
#endif
    return P9_RT_UNKNOWN_HOST_SERVICE;
}
