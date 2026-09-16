/* OpenRecomp deterministic host emitter V1 (P2-07). */
/* architecture: nes6502; word_bits: 16; entry: fn_8000 */
/* emitter_version: 1.0.0 */
/* input_sha256: 951b62e7194ad4e6f7409589da14e94601d1622564cd4d1a287585ac9a010bea */
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

static uint64_t g_r[7];
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

static void fn_fn_8000(void);
static void fn_fn_8018(void);

static void fn_fn_8000(void) {
bb_blk_8000:;
    g_r[5] = (UINT64_C(3)) & or_mask(16u);
    g_r[6] = (((g_r[5]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[5]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    goto bb_blk_8002;
bb_blk_8002:;
    g_r[1] = (UINT64_C(0)) & or_mask(16u);
    g_r[4] = ((g_r[0]) + (UINT64_C(5))) & or_mask(16u);
    g_r[4] = ((g_r[4]) + (g_r[1])) & or_mask(16u);
    g_r[0] = ((g_r[4]) & (UINT64_C(255))) & or_mask(16u);
    if ((UINT64_C(8)) >= 16u) { or_fail("shift count is not normalized"); return; }
    g_r[1] = ((g_r[4]) >> (UINT64_C(8))) & or_mask(16u);
    g_r[1] = ((g_r[1]) & (UINT64_C(1))) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = ((UINT64_C(1024)) + (g_r[5])) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[5] = ((g_r[5]) - (UINT64_C(1))) & or_mask(16u);
    g_r[5] = ((g_r[5]) & (UINT64_C(255))) & or_mask(16u);
    g_r[6] = (((g_r[5]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[5]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    if (((g_r[6]) == (UINT64_C(0)))) goto bb_blk_8002; else goto bb_blk_800b;
bb_blk_800b:;
    fn_fn_8018();
    goto bb_blk_800e;
bb_blk_800e:;
    goto bb_blk_8012;
bb_blk_8012:;
    or_fail("unresolved indirect jump");
    return;
}

static void fn_fn_8018(void) {
bb_blk_8018:;
    g_r[5] = ((g_r[5]) + (UINT64_C(1))) & or_mask(16u);
    g_r[5] = ((g_r[5]) & (UINT64_C(255))) & or_mask(16u);
    g_r[6] = (((g_r[5]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[5]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    return;
}

void openrecomp_run(void) {
    for (size_t i = 0; i < 7u; ++i) g_r[i] = UINT64_C(0);
    g_failed = 0;
    g_error = "";
    fn_fn_8000();
}
int openrecomp_failed(void) { return g_failed; }
const char *openrecomp_error(void) { return g_error; }
size_t openrecomp_register_count(void) { return 7u; }
uint64_t openrecomp_register_value(size_t index) {
    return index < 7u ? g_r[index] : UINT64_C(0);
}
