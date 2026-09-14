/* OpenRecomp deterministic host emitter V1 (P2-07). */
/* architecture: mips32-bounded-v1; word_bits: 32; entry: fn_1000 */
/* emitter_version: 1.0.0 */
/* input_sha256: 3d0ab39809b7ab403db462cca779e4958cfdaa3a728428cfb4dc843297b77cbe */
#include <stdint.h>
#include <stddef.h>

/* OpenRecomp generic runtime ABI V1 (P2-08). Architecture-neutral. */
/* runtime_abi_version: openrecomp-generic-runtime-abi 1.0.0 */

enum {
    OR_RT_OK = 0,
    OR_RT_MEMORY_OUT_OF_RANGE = 1,
    OR_RT_MEMORY_WIDTH_UNSUPPORTED = 2,
    OR_RT_MEMORY_ADDRESS_OVERFLOW = 3,
    OR_RT_MEMORY_ENDIANNESS_UNSUPPORTED = 4,
    OR_RT_MEMORY_SEGMENT_OVERLAP = 5,
    OR_RT_UNKNOWN_HOST_SERVICE = 6,
    OR_RT_HOST_SERVICE_FAILED = 7,
    OR_RT_HOST_CALL_ARITY = 8,
    OR_RT_INPUT_INVALID = 9,
    OR_RT_FRAME_INVALID = 10,
    OR_RT_AUDIO_INVALID = 11,
    OR_RT_ABI_VERSION_MISMATCH = 12,
    OR_RT_UNSUPPORTED_OPERATION = 13,
    OR_RT_TRAP = 14,
};

extern int or_rt_memory_read(uint64_t address, uint32_t width_bits, uint64_t *out_value);
extern int or_rt_memory_write(uint64_t address, uint32_t width_bits, uint64_t value);
extern int or_rt_host_call(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value);
extern const char *or_rt_failure_reason(int code);

static uint64_t g_r[11];
static int g_failed;
static const char *g_error = "";

static uint64_t or_mask(unsigned bits) {
    return bits >= 64u ? UINT64_MAX : ((UINT64_C(1) << bits) - UINT64_C(1));
}
static int64_t or_signed(uint64_t value, unsigned bits) {
    uint64_t mask = or_mask(bits);
    value &= mask;
    if (bits >= 64u) return (int64_t)value;
    uint64_t sign = UINT64_C(1) << (bits - 1u);
    if (value & sign) value |= ~mask;
    return (int64_t)value;
}
static uint64_t or_ashr(uint64_t value, uint64_t shift, unsigned bits) {
    uint64_t mask = or_mask(bits);
    value &= mask;
    uint64_t shifted = value >> shift;
    uint64_t sign = bits >= 64u ? (value >> 63u) : (value >> (bits - 1u));
    if (sign) shifted |= (mask ^ (mask >> shift));
    return shifted & mask;
}
static void or_fail(const char *message) {
    if (!g_failed) g_error = message;
    g_failed = 1;
}

static void fn_fn_1000(void);
static void fn_fn_1084(void);
static void fn_fn_10ac(void);
static void fn_fn_10c0(void);

static void fn_fn_1000(void) {
bb_blk_1000:;
    g_r[3] = ((g_r[0]) + (UINT64_C(1024))) & or_mask(32u);
    g_r[3] = ((g_r[3]) + (UINT64_C(4294967272))) & or_mask(32u);
    {
        const uint64_t or_addr = ((g_r[3]) + (UINT64_C(20))) & or_mask(32u);
        if (or_rt_memory_write(or_addr, 32u, g_r[5]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[6] = ((g_r[0]) + (UINT64_C(0))) & or_mask(32u);
    {
        const uint64_t or_addr = ((g_r[3]) + (UINT64_C(0))) & or_mask(32u);
        if (or_rt_memory_write(or_addr, 32u, g_r[6]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    {
        const uint64_t or_addr = ((g_r[3]) + (UINT64_C(4))) & or_mask(32u);
        if (or_rt_memory_write(or_addr, 32u, g_r[6]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[10] = ((g_r[0]) + (UINT64_C(0))) & or_mask(32u);
    g_r[8] = ((g_r[0]) + (UINT64_C(20))) & or_mask(32u);
    goto bb_blk_1020;
bb_blk_1020:;
    g_r[9] = ((or_signed((g_r[10]), 32u) < or_signed((g_r[8]), 32u))) ? UINT64_C(1) : UINT64_C(0);
    if (((g_r[9]) == (g_r[0]))) goto bb_blk_1064; else goto bb_blk_1028;
bb_blk_1028:;
    g_r[10] = ((g_r[10]) + (UINT64_C(1))) & or_mask(32u);
    g_r[6] = ((g_r[10]) + (g_r[0])) & or_mask(32u);
    fn_fn_1084();
    goto bb_blk_1038;
bb_blk_1038:;
    {
        const uint64_t or_addr = ((g_r[3]) + (UINT64_C(0))) & or_mask(32u);
        uint64_t or_value = UINT64_C(0);
        if (or_rt_memory_read(or_addr, 32u, &or_value) != OR_RT_OK) {
            or_fail("runtime memory read failed");
            return;
        }
        g_r[4] = or_value & or_mask(32u);
    }
    g_r[4] = ((g_r[4]) + (g_r[2])) & or_mask(32u);
    {
        const uint64_t or_addr = ((g_r[3]) + (UINT64_C(0))) & or_mask(32u);
        if (or_rt_memory_write(or_addr, 32u, g_r[4]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    {
        const uint64_t or_addr = ((g_r[3]) + (UINT64_C(4))) & or_mask(32u);
        uint64_t or_value = UINT64_C(0);
        if (or_rt_memory_read(or_addr, 32u, &or_value) != OR_RT_OK) {
            or_fail("runtime memory read failed");
            return;
        }
        g_r[6] = or_value & or_mask(32u);
    }
    g_r[7] = ((g_r[2]) + (g_r[0])) & or_mask(32u);
    fn_fn_10c0();
    goto bb_blk_1054;
bb_blk_1054:;
    {
        const uint64_t or_addr = ((g_r[3]) + (UINT64_C(4))) & or_mask(32u);
        if (or_rt_memory_write(or_addr, 32u, g_r[2]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    goto bb_blk_1020;
bb_blk_1064:;
    {
        const uint64_t or_addr = ((g_r[3]) + (UINT64_C(0))) & or_mask(32u);
        uint64_t or_value = UINT64_C(0);
        if (or_rt_memory_read(or_addr, 32u, &or_value) != OR_RT_OK) {
            or_fail("runtime memory read failed");
            return;
        }
        g_r[6] = or_value & or_mask(32u);
    }
    {
        const uint64_t or_addr = ((g_r[3]) + (UINT64_C(4))) & or_mask(32u);
        uint64_t or_value = UINT64_C(0);
        if (or_rt_memory_read(or_addr, 32u, &or_value) != OR_RT_OK) {
            or_fail("runtime memory read failed");
            return;
        }
        g_r[7] = or_value & or_mask(32u);
    }
    g_r[8] = ((g_r[6]) + (g_r[7])) & or_mask(32u);
    g_r[1] = ((g_r[8]) + (UINT64_C(0))) & or_mask(32u);
    {
        const uint64_t or_addr = ((g_r[3]) + (UINT64_C(20))) & or_mask(32u);
        uint64_t or_value = UINT64_C(0);
        if (or_rt_memory_read(or_addr, 32u, &or_value) != OR_RT_OK) {
            or_fail("runtime memory read failed");
            return;
        }
        g_r[5] = or_value & or_mask(32u);
    }
    g_r[3] = ((g_r[3]) + (UINT64_C(24))) & or_mask(32u);
    return;
}

static void fn_fn_1084(void) {
bb_blk_1084:;
    g_r[3] = ((g_r[3]) + (UINT64_C(4294967288))) & or_mask(32u);
    {
        const uint64_t or_addr = ((g_r[3]) + (UINT64_C(4))) & or_mask(32u);
        if (or_rt_memory_write(or_addr, 32u, g_r[5]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[6] = ((g_r[6]) + (g_r[0])) & or_mask(32u);
    fn_fn_10ac();
    goto bb_blk_1094;
bb_blk_1094:;
    g_r[2] = ((g_r[2]) + (g_r[6])) & or_mask(32u);
    {
        const uint64_t or_addr = ((g_r[3]) + (UINT64_C(4))) & or_mask(32u);
        uint64_t or_value = UINT64_C(0);
        if (or_rt_memory_read(or_addr, 32u, &or_value) != OR_RT_OK) {
            or_fail("runtime memory read failed");
            return;
        }
        g_r[5] = or_value & or_mask(32u);
    }
    g_r[3] = ((g_r[3]) + (UINT64_C(8))) & or_mask(32u);
    return;
}

static void fn_fn_10ac(void) {
bb_blk_10ac:;
    g_r[2] = ((g_r[6]) + (g_r[6])) & or_mask(32u);
    g_r[2] = ((g_r[2]) + (g_r[6])) & or_mask(32u);
    g_r[2] = ((g_r[2]) + (UINT64_C(1))) & or_mask(32u);
    return;
}

static void fn_fn_10c0(void) {
bb_blk_10c0:;
    g_r[2] = ((or_signed((g_r[6]), 32u) < or_signed((g_r[7]), 32u))) ? UINT64_C(1) : UINT64_C(0);
    if (((g_r[2]) != (g_r[0]))) goto bb_blk_10d8; else goto bb_blk_10c8;
bb_blk_10c8:;
    g_r[2] = ((g_r[6]) + (g_r[0])) & or_mask(32u);
    return;
bb_blk_10d8:;
    g_r[2] = ((g_r[7]) + (g_r[0])) & or_mask(32u);
    return;
}

void openrecomp_run(void) {
    for (size_t i = 0; i < 11u; ++i) g_r[i] = UINT64_C(0);
    g_failed = 0;
    g_error = "";
    fn_fn_1000();
}
int openrecomp_failed(void) { return g_failed; }
const char *openrecomp_error(void) { return g_error; }
size_t openrecomp_register_count(void) { return 11u; }
uint64_t openrecomp_register_value(size_t index) {
    return index < 11u ? g_r[index] : UINT64_C(0);
}
