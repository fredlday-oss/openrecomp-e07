/* OpenRecomp deterministic host emitter V1 (P2-07). */
/* architecture: mips32-bounded-v1; word_bits: 32; entry: fn_1000 */
/* emitter_version: 1.0.0 */
/* input_sha256: ed3a37ccff1756b54570eb88cf3adc6e1b51636c638ea6a11ff25e158e1862b8 */
#include <stdint.h>
#include <stddef.h>

static uint64_t g_r[8];
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

static void fn_fn_1000(void) {
bb_blk_1000:;
    g_r[1] = ((g_r[0]) + (UINT64_C(7))) & or_mask(32u);
    g_r[2] = ((g_r[0]) + (UINT64_C(5))) & or_mask(32u);
    if (((g_r[1]) == (g_r[2]))) goto bb_blk_1014; else goto bb_blk_100c;
bb_blk_100c:;
    g_r[4] = ((g_r[0]) + (UINT64_C(3))) & or_mask(32u);
    goto bb_blk_1014;
bb_blk_1014:;
    g_r[4] = ((g_r[4]) + (UINT64_C(1))) & or_mask(32u);
    if (((g_r[4]) != (g_r[1]))) goto bb_blk_1020; else goto bb_blk_101c;
bb_blk_101c:;
    goto bb_blk_1020;
bb_blk_1020:;
    g_r[5] = ((g_r[4]) + (g_r[1])) & or_mask(32u);
    g_r[6] = ((g_r[5]) - (g_r[2])) & or_mask(32u);
    g_r[7] = ((or_signed((g_r[6]), 32u) < or_signed((g_r[1]), 32u))) ? UINT64_C(1) : UINT64_C(0);
    return;
}

void openrecomp_run(void) {
    for (size_t i = 0; i < 8u; ++i) g_r[i] = UINT64_C(0);
    g_failed = 0;
    g_error = "";
    fn_fn_1000();
}
int openrecomp_failed(void) { return g_failed; }
const char *openrecomp_error(void) { return g_error; }
size_t openrecomp_register_count(void) { return 8u; }
uint64_t openrecomp_register_value(size_t index) {
    return index < 8u ? g_r[index] : UINT64_C(0);
}
