/* Deterministic OpenRecomp normalized IR V1 -> portable C output. */
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <limits.h>

typedef int (*openrecomp_host_callback)(const char *, const uint64_t *, size_t, uint64_t *, int *);
static openrecomp_host_callback g_host_callback = NULL;
static uint64_t g_state[31];
static uint8_t g_memory[262144];
static uint64_t g_operations;
static int g_failed;
static const char *g_error;
static uint64_t g_entry_return;
static int g_entry_has_return;
static const uint64_t g_max_operations = UINT64_C(200000);

static uint64_t or_mask(unsigned bits) { return bits >= 64u ? UINT64_MAX : ((UINT64_C(1) << bits) - UINT64_C(1)); }
static void or_fail(const char *message) { if (!g_failed) g_error = message; g_failed = 1; }
static int or_step(void) {
    g_operations += UINT64_C(1);
    if (g_operations > g_max_operations) { or_fail("operation limit exceeded"); return 0; }
    return 1;
}
static const uint64_t g_state_masks[31] = {UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295), UINT64_C(4294967295)};
static const char *g_state_names[31] = {"gpr:r1", "gpr:r2", "gpr:r3", "gpr:r4", "gpr:r5", "gpr:r6", "gpr:r7", "gpr:r8", "gpr:r9", "gpr:r10", "gpr:r11", "gpr:r12", "gpr:r13", "gpr:r14", "gpr:r15", "gpr:r16", "gpr:r17", "gpr:r18", "gpr:r19", "gpr:r20", "gpr:r21", "gpr:r22", "gpr:r23", "gpr:r24", "gpr:r25", "gpr:r26", "gpr:r27", "gpr:r28", "gpr:r29", "gpr:r30", "gpr:r31"};
static uint64_t or_fn_0(const uint64_t *, size_t, int *, uint32_t);
static uint64_t or_fn_0(const uint64_t *args, size_t argc, int *has_return, uint32_t depth) {
    uint64_t v[4] = {0};
    (void)v;
    if (depth > 1024u) { or_fail("call-depth limit exceeded"); return 0; }
    if (argc != 0u) { or_fail("argument count mismatch"); return 0; }
    *has_return = 0;
    (void)args;
    goto or_f0_b0;
or_f0_b0:
    if (!or_step()) return 0;
    v[0] = (((UINT64_C(0)) + (UINT64_C(52)))) & or_mask(32);
    if (!or_step()) return 0;
    g_state[1] = (v[0]) & g_state_masks[1];
    if (!or_step()) return 0;
    v[1] = (((UINT64_C(0)) + (UINT64_C(8)))) & or_mask(32);
    if (!or_step()) return 0;
    g_state[2] = (v[1]) & g_state_masks[2];
    if (!or_step()) return 0;
    v[2] = g_state[1];
    if (!or_step()) return 0;
    v[3] = (((v[2]) + (UINT64_C(3)))) & or_mask(32);
    if (!or_step()) return 0;
    g_state[1] = (v[3]) & g_state_masks[1];
    if (!or_step()) return 0;
    return 0;
}
void openrecomp_set_host_callback(openrecomp_host_callback callback) { g_host_callback = callback; }
static void or_reset(void) {
    memset(g_state, 0, sizeof(g_state)); memset(g_memory, 0, sizeof(g_memory));
    g_operations = 0; g_failed = 0; g_error = ""; g_entry_return = 0; g_entry_has_return = 0;
}
int openrecomp_run(void) {
    or_reset();
    g_entry_return = or_fn_0(NULL, 0u, &g_entry_has_return, 0u);
    return g_failed ? 0 : 1;
}
uint64_t openrecomp_observed_state(void) { return g_state[1] & or_mask(32u); }
uint64_t openrecomp_function_return(void) { return g_entry_return; }
int openrecomp_function_has_return(void) { return g_entry_has_return; }
uint64_t openrecomp_operations(void) { return g_operations; }
const char *openrecomp_error(void) { return g_error; }
size_t openrecomp_state_count(void) { return 31u; }
const char *openrecomp_state_name(size_t i) { return i < 31u ? g_state_names[i] : NULL; }
uint64_t openrecomp_state_value(size_t i) { return i < 31u ? g_state[i] : UINT64_C(0); }
size_t openrecomp_memory_size(void) { return 262144u; }
int openrecomp_memory_read(uint64_t a, size_t n, uint8_t *out) {
    const uint64_t total = UINT64_C(262144);
    if (!out || a > total || (uint64_t)n > total - a) return 0;
    memcpy(out, g_memory + a, n); return 1;
}
