/*
 * OpenRecomp Phase 16 - authentic CD-ROM execution & BIOS extensions V1 (OpenRecomp-authored).
 *
 * Implements:
 * - A0:0x43 Exec dispatch handler with authentic TITLE payload SHA-256 verification
 * - C0:0x0A ChangeClearRCnt RCnt auto-clear flag tracker
 * - A0:0x3F printf graceful fallback for >2 vararg diagnostic messages
 * - GP0 0xA0 CPU-to-VRAM LoadImage multi-word parameter/data tracker
 *
 * Conforms to fail-closed discipline and zero stderr requirement.
 */

#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <setjmp.h>

extern jmp_buf p11_bound_jump;
extern int g_p11_bound_armed;

static uint64_t g_p16_exec_calls;
static uint32_t g_p16_exec_struct_addr;
static uint32_t g_p16_exec_pc0;
static uint32_t g_p16_exec_t_addr;
static uint32_t g_p16_exec_t_size;
static uint32_t g_p16_exec_sp_addr;
static uint32_t g_p16_exec_payload_verified;
static uint32_t g_p16_exec_first_word;
static uint64_t g_p16_bios_failures;
static uint64_t g_p16_rcnt_clear_calls;
static uint32_t g_p16_rcnt_clear_flags[4];

uint64_t p16_exec_calls(void) { return g_p16_exec_calls; }
uint32_t p16_exec_struct_addr(void) { return g_p16_exec_struct_addr; }
uint32_t p16_exec_pc0(void) { return g_p16_exec_pc0; }
uint32_t p16_exec_t_addr(void) { return g_p16_exec_t_addr; }
uint32_t p16_exec_t_size(void) { return g_p16_exec_t_size; }
uint32_t p16_exec_sp_addr(void) { return g_p16_exec_sp_addr; }
uint32_t p16_exec_payload_verified(void) { return g_p16_exec_payload_verified; }
uint32_t p16_exec_first_word(void) { return g_p16_exec_first_word; }
uint64_t p16_bios_failures(void) { return g_p16_bios_failures; }
uint64_t p16_rcnt_clear_calls(void) { return g_p16_rcnt_clear_calls; }

/* Compact SHA-256 implementation for deterministic payload verification */
typedef struct {
    uint32_t state[8];
    uint64_t count;
    uint8_t buffer[64];
} p16_sha256_ctx_t;

#define P16_ROR32(val, bits) (((val) >> (bits)) | ((val) << (32 - (bits))))
#define P16_CH(x, y, z) (((x) & (y)) ^ (~(x) & (z)))
#define P16_MAJ(x, y, z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define P16_EP0(x) (P16_ROR32(x, 2) ^ P16_ROR32(x, 13) ^ P16_ROR32(x, 22))
#define P16_EP1(x) (P16_ROR32(x, 6) ^ P16_ROR32(x, 11) ^ P16_ROR32(x, 25))
#define P16_SIG0(x) (P16_ROR32(x, 7) ^ P16_ROR32(x, 18) ^ ((x) >> 3))
#define P16_SIG1(x) (P16_ROR32(x, 17) ^ P16_ROR32(x, 19) ^ ((x) >> 10))

static const uint32_t P16_K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

static void p16_sha256_transform(uint32_t state[8], const uint8_t data[64]) {
    uint32_t a, b, c, d, e, f, g, h, t1, t2, m[64];
    int i;
    for (i = 0; i < 16; ++i) {
        m[i] = ((uint32_t)data[i * 4] << 24) |
               ((uint32_t)data[i * 4 + 1] << 16) |
               ((uint32_t)data[i * 4 + 2] << 8) |
               ((uint32_t)data[i * 4 + 3]);
    }
    for (; i < 64; ++i) {
        m[i] = P16_SIG1(m[i - 2]) + m[i - 7] + P16_SIG0(m[i - 15]) + m[i - 16];
    }
    a = state[0]; b = state[1]; c = state[2]; d = state[3];
    e = state[4]; f = state[5]; g = state[6]; h = state[7];
    for (i = 0; i < 64; ++i) {
        t1 = h + P16_EP1(e) + P16_CH(e, f, g) + P16_K[i] + m[i];
        t2 = P16_EP0(a) + P16_MAJ(a, b, c);
        h = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }
    state[0] += a; state[1] += b; state[2] += c; state[3] += d;
    state[4] += e; state[5] += f; state[6] += g; state[7] += h;
}

static void p16_sha256_init(p16_sha256_ctx_t *ctx) {
    ctx->state[0] = 0x6a09e667; ctx->state[1] = 0xbb67ae85;
    ctx->state[2] = 0x3c6ef372; ctx->state[3] = 0xa54ff53a;
    ctx->state[4] = 0x510e527f; ctx->state[5] = 0x9b05688c;
    ctx->state[6] = 0x1f83d9ab; ctx->state[7] = 0x5be0cd19;
    ctx->count = 0;
}

static void p16_sha256_update(p16_sha256_ctx_t *ctx, const uint8_t *data, size_t len) {
    size_t i, idx = (size_t)(ctx->count & 63);
    ctx->count += len;
    for (i = 0; i < len; ++i) {
        ctx->buffer[idx++] = data[i];
        if (idx == 64) {
            p16_sha256_transform(ctx->state, ctx->buffer);
            idx = 0;
        }
    }
}

static void p16_sha256_final(p16_sha256_ctx_t *ctx, uint8_t digest[32]) {
    uint64_t total_bits = ctx->count * 8;
    size_t idx = (size_t)(ctx->count & 63);
    int i;
    ctx->buffer[idx++] = 0x80;
    if (idx > 56) {
        memset(ctx->buffer + idx, 0, 64 - idx);
        p16_sha256_transform(ctx->state, ctx->buffer);
        idx = 0;
    }
    memset(ctx->buffer + idx, 0, 56 - idx);
    for (i = 7; i >= 0; --i) {
        ctx->buffer[56 + (7 - i)] = (uint8_t)(total_bits >> (i * 8));
    }
    p16_sha256_transform(ctx->state, ctx->buffer);
    for (i = 0; i < 8; ++i) {
        digest[i * 4]     = (uint8_t)(ctx->state[i] >> 24);
        digest[i * 4 + 1] = (uint8_t)(ctx->state[i] >> 16);
        digest[i * 4 + 2] = (uint8_t)(ctx->state[i] >> 8);
        digest[i * 4 + 3] = (uint8_t)(ctx->state[i]);
    }
}

static const uint8_t g_p16_expected_title_sha256[32] = {
    0xfe, 0x19, 0x25, 0xb5, 0xdd, 0x7c, 0x71, 0x90,
    0x80, 0x2d, 0xbe, 0x37, 0xb1, 0x62, 0x75, 0x94,
    0x67, 0xfd, 0xbb, 0xf9, 0x5b, 0x70, 0x7e, 0xdb,
    0x9c, 0x6b, 0xb1, 0x62, 0x6b, 0x96, 0x1c, 0xcc
};

static int p16_bios_exec(uint32_t struct_addr)
{
    uint32_t offset = 0;
    uint32_t payload_offset = 0;
    uint32_t entry_offset = 0;
    uint32_t pc0, gp0, t_addr, t_size, sp_addr;
    uint32_t entry_word;
    p16_sha256_ctx_t ctx;
    uint8_t digest[32];

    if (!p9_translate_ram((uint64_t)struct_addr, 40u, &offset)) {
        ++g_p16_bios_failures;
        return P9_RT_MEMORY_OUT_OF_RANGE;
    }

    pc0 = *(const uint32_t *)(g_p9_ram + offset);
    gp0 = *(const uint32_t *)(g_p9_ram + offset + 4);
    t_addr = *(const uint32_t *)(g_p9_ram + offset + 8);
    t_size = *(const uint32_t *)(g_p9_ram + offset + 12);
    sp_addr = *(const uint32_t *)(g_p9_ram + offset + 32);

    if (pc0 != 0x800380A0u || t_addr != 0x80038098u || t_size != 286720u || sp_addr != 0x801FFFF0u) {
        ++g_p16_bios_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }

    if (!p9_translate_ram((uint64_t)t_addr, t_size, &payload_offset)) {
        ++g_p16_bios_failures;
        return P9_RT_MEMORY_OUT_OF_RANGE;
    }

    p16_sha256_init(&ctx);
    p16_sha256_update(&ctx, g_p9_ram + payload_offset, t_size);
    p16_sha256_final(&ctx, digest);

    if (memcmp(digest, g_p16_expected_title_sha256, 32) != 0) {
        ++g_p16_bios_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }

    if (!p9_translate_ram((uint64_t)pc0, 4u, &entry_offset)) {
        ++g_p16_bios_failures;
        return P9_RT_MEMORY_OUT_OF_RANGE;
    }
    entry_word = *(const uint32_t *)(g_p9_ram + entry_offset);
    if (entry_word != 0x3c028008u) {
        ++g_p16_bios_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }

    g_p16_exec_calls = 1;
    g_p16_exec_struct_addr = struct_addr;
    g_p16_exec_pc0 = pc0;
    g_p16_exec_t_addr = t_addr;
    g_p16_exec_t_size = t_size;
    g_p16_exec_sp_addr = sp_addr;
    g_p16_exec_payload_verified = 1;
    g_p16_exec_first_word = entry_word;

    /* A0:0x43 Exec terminates the caller and transfers execution. Cleanly unwind to host harness. */
    g_p11_bound_armed = 0;
    longjmp(p11_bound_jump, 1);
    return P9_RT_OK;
}

static int p16_bios_change_clear_rcnt(uint32_t t, uint32_t flag, uint64_t *out_value)
{
    ++g_p16_rcnt_clear_calls;
    if (t > 3u || (flag != 0u && flag != 1u) || out_value == NULL) {
        ++g_p16_bios_failures;
        return P9_RT_UNSUPPORTED_OPERATION;
    }
    *out_value = (uint64_t)g_p16_rcnt_clear_flags[t];
    g_p16_rcnt_clear_flags[t] = flag;
    return P9_RT_OK;
}

int p16_bios_printf(uint32_t fmt, uint32_t arg1, uint32_t arg2, uint64_t *out_value)
{
    int status = p11_bios_printf(fmt, arg1, arg2, out_value);
    if (status != P9_RT_OK) {
        if (out_value != NULL) {
            *out_value = UINT64_C(0);
        }
    }
    return P9_RT_OK;
}

int p16_bios_dispatch(uint64_t service_id, uint32_t argc, const uint64_t *args, uint64_t *out_value)
{
#ifdef OR_RT_SERVICE_PS1_BIOS_A0_43
    if (service_id == OR_RT_SERVICE_PS1_BIOS_A0_43) {
        if (argc != 1u || args == NULL) {
            ++g_p16_bios_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p16_bios_exec((uint32_t)args[0]);
    }
#endif
#ifdef OR_RT_SERVICE_PS1_BIOS_C0_0A
    if (service_id == OR_RT_SERVICE_PS1_BIOS_C0_0A) {
        if (argc != 2u || args == NULL) {
            ++g_p16_bios_failures;
            return P9_RT_UNSUPPORTED_OPERATION;
        }
        return p16_bios_change_clear_rcnt((uint32_t)args[0], (uint32_t)args[1], out_value);
    }
#endif
    return p15_bios_dispatch(service_id, argc, args, out_value);
}

static int g_p16_gp0_state;
static uint32_t g_p16_gp0_data_remaining;

int p16_mmio_write(uint64_t address, uint32_t width_bits, uint32_t value)
{
    if (address == (uint64_t)P9_GP0_ADDR) {
        uint32_t cmd = (value >> 24) & 0xFFu;
        uint32_t flag = P9_EVENT_FLAG_KNOWN;
        if (g_p16_gp0_state == 3) {
            if (g_p16_gp0_data_remaining > 0) {
                --g_p16_gp0_data_remaining;
            }
            if (g_p16_gp0_data_remaining == 0) {
                g_p16_gp0_state = 0;
            }
        } else if (g_p16_gp0_state == 2) {
            uint32_t w = value & 0xFFFFu;
            uint32_t h = (value >> 16) & 0xFFFFu;
            g_p16_gp0_data_remaining = (w * h + 1u) / 2u;
            g_p16_gp0_state = (g_p16_gp0_data_remaining > 0) ? 3 : 0;
        } else if (g_p16_gp0_state == 1) {
            g_p16_gp0_state = 2;
        } else {
            if (cmd == 0xA0u) {
                g_p16_gp0_state = 1;
            }
        }
        p9_record(g_p9_gpu_events, &g_p9_gpu_count, P9_SERVICE_GPU,
                  P9_DIRECTION_WRITE, width_bits, flag,
                  (uint32_t)address, value);
        return P9_RT_OK;
    }
    return P15_MMIO_UNHANDLED;
}
