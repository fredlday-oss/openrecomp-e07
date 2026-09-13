/* OpenRecomp deterministic host emitter V1 (P2-07). */
/* architecture: bounded-synthetic-v1; word_bits: 32; entry: fn_1000 */
/* emitter_version: 1.0.0 */
/* input_sha256: 4959dbf7b7075aaa78df1d4aaefb51da2a0b26a845a10bc3675dd76870bd1682 */
#include <stdint.h>
#include <stddef.h>

static uint64_t g_r[3];
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
    g_r[0] = (UINT64_C(5)) & or_mask(32u);
    g_r[1] = (UINT64_C(7)) & or_mask(32u);
    g_r[2] = ((g_r[0]) + (g_r[1])) & or_mask(32u);
    return;
}

void openrecomp_run(void) {
    for (size_t i = 0; i < 3u; ++i) g_r[i] = UINT64_C(0);
    g_failed = 0;
    g_error = "";
    fn_fn_1000();
}
int openrecomp_failed(void) { return g_failed; }
const char *openrecomp_error(void) { return g_error; }
size_t openrecomp_register_count(void) { return 3u; }
uint64_t openrecomp_register_value(size_t index) {
    return index < 3u ? g_r[index] : UINT64_C(0);
}
