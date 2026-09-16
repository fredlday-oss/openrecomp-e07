/* OpenRecomp deterministic host emitter V1 (P2-07). */
/* architecture: nes6502; word_bits: 16; entry: fn_8000 */
/* emitter_version: 1.0.0 */
/* input_sha256: 9ed4a49204198bb01ffa4e74b849906d65bb3ef5b492bcf5e1c7f04d94e9f40b */
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

#define OR_RT_SERVICE_NES_AUDIO_SUBMIT UINT64_C(1)
#define OR_RT_SERVICE_NES_FRAME_SUBMIT UINT64_C(2)

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
static void fn_fn_8089(void);
static void fn_fn_808c(void);

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
    g_r[5] = ((g_r[5]) + (UINT64_C(1))) & or_mask(16u);
    g_r[5] = ((g_r[5]) & (UINT64_C(255))) & or_mask(16u);
    g_r[6] = (((g_r[5]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[5]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[0] = (UINT64_C(1)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(16406)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(0)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(16406)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[2] = (UINT64_C(16406)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        uint64_t or_value = UINT64_C(0);
        if (or_rt_memory_read(or_addr, 16u, &or_value) != OR_RT_OK) {
            or_fail("runtime memory read failed");
            return;
        }
        g_r[0] = or_value & or_mask(16u);
    }
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(1280)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(255)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(512)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(0)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(513)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(0)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(514)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(255)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(515)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(0)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(516)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(255)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(517)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(0)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(518)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(255)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(519)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(0)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(520)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(0)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(521)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(255)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(522)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(255)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(523)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(255)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(524)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(255)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(525)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(255)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(526)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(0)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(527)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    fn_fn_8089();
    goto bb_blk_806f;
bb_blk_806f:;
    g_r[0] = (UINT64_C(16)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(788)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(32)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(789)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(48)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(790)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    g_r[0] = (UINT64_C(64)) & or_mask(16u);
    g_r[6] = (((g_r[0]) == (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[3] = ((g_r[0]) & (UINT64_C(128))) & or_mask(16u);
    g_r[3] = (((g_r[3]) != (UINT64_C(0)))) ? UINT64_C(1) : UINT64_C(0);
    g_r[2] = (UINT64_C(791)) & or_mask(16u);
    {
        const uint64_t or_addr = ((g_r[2]) + (UINT64_C(0))) & or_mask(16u);
        if (or_rt_memory_write(or_addr, 16u, g_r[0]) != OR_RT_OK) {
            or_fail("runtime memory write failed");
            return;
        }
    }
    fn_fn_808c();
    goto bb_blk_8086;
bb_blk_8086:;
    goto bb_blk_808f;
bb_blk_808f:;
    return;
}

static void fn_fn_8089(void) {
bb_blk_8089:;
    {
        const uint64_t or_call_args[4] = { UINT64_C(512), UINT64_C(2), UINT64_C(2), UINT64_C(0) };
        uint64_t or_call_result = UINT64_C(0);
        if (or_rt_host_call(OR_RT_SERVICE_NES_FRAME_SUBMIT, 4u, or_call_args, &or_call_result) != OR_RT_OK) {
            or_fail("runtime host service nes.frame.submit failed");
            return;
        }
    }
    return;
}

static void fn_fn_808c(void) {
bb_blk_808c:;
    {
        const uint64_t or_call_args[5] = { UINT64_C(788), UINT64_C(8000), UINT64_C(1), UINT64_C(4), UINT64_C(0) };
        uint64_t or_call_result = UINT64_C(0);
        if (or_rt_host_call(OR_RT_SERVICE_NES_AUDIO_SUBMIT, 5u, or_call_args, &or_call_result) != OR_RT_OK) {
            or_fail("runtime host service nes.audio.submit failed");
            return;
        }
    }
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
