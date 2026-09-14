/* OpenRecomp deterministic host emitter V1 (P2-07). */
/* architecture: mips32-bounded-v1; word_bits: 32; entry: fn_1000 */
/* emitter_version: 1.0.0 */
/* input_sha256: 141d86bc73ec55afe2bea9186c93e11e717aad814153d61ac26fe77821b122b1 */
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

static uint64_t g_r[6];
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
static void fn_fn_1088(void);

static void fn_fn_1000(void) {
bb_blk_1000:;
    g_r[2] = ((g_r[0]) + (UINT64_C(256))) & or_mask(32u);
    g_r[2] = ((g_r[2]) + (UINT64_C(4294967288))) & or_mask(32u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(4))) & or_mask(32u);
        if (or_rt_memory_write(or_addr, 32u, g_r[3]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[4] = ((g_r[0]) + (UINT64_C(21))) & or_mask(32u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(32u);
        if (or_rt_memory_write(or_addr, 32u, g_r[4]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    fn_fn_1088();
    goto bb_blk_1018;
bb_blk_1018:;
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(32u);
        uint64_t or_value = UINT64_C(0);
        if (or_rt_memory_read(or_addr, 32u, &or_value) != OR_RT_OK) {
            or_fail("runtime memory read failed");
            return;
        }
        g_r[5] = or_value & or_mask(32u);
    }
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(4))) & or_mask(32u);
        uint64_t or_value = UINT64_C(0);
        if (or_rt_memory_read(or_addr, 32u, &or_value) != OR_RT_OK) {
            or_fail("runtime memory read failed");
            return;
        }
        g_r[3] = or_value & or_mask(32u);
    }
    g_r[5] = ((g_r[5]) + (g_r[1])) & or_mask(32u);
    g_r[2] = ((g_r[2]) + (UINT64_C(8))) & or_mask(32u);
    return;
}

static void fn_fn_1088(void) {
bb_blk_1088:;
    g_r[1] = ((g_r[0]) + (UINT64_C(21))) & or_mask(32u);
    return;
}

void openrecomp_run(void) {
    for (size_t i = 0; i < 6u; ++i) g_r[i] = UINT64_C(0);
    g_failed = 0;
    g_error = "";
    fn_fn_1000();
}
int openrecomp_failed(void) { return g_failed; }
const char *openrecomp_error(void) { return g_error; }
size_t openrecomp_register_count(void) { return 6u; }
uint64_t openrecomp_register_value(size_t index) {
    return index < 6u ? g_r[index] : UINT64_C(0);
}
