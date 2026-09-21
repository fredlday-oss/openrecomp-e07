/*
 * OpenRecomp Phase 11 - opt-in deterministic execution trace (OpenRecomp-authored).
 *
 * This fragment is appended to the composed Phase-10 runtime support translation
 * unit. It provides the definitions of the opt-in instrumentation hooks that the
 * architecture-neutral host emitter can emit (`HostInstrumentation`):
 *
 *   - `p11_trace_function(entry_address)`  - one emitted function entered;
 *   - `p11_trace_block(block_address)`     - one emitted basic block entered;
 *   - `p11_trace_indirect_failure(site, source_value, message)` - a fail-closed
 *     indirect control site reached, with the indirect source register value.
 *
 * The trace is bounded, deterministic and host-local: it never touches guest
 * memory, never changes guest semantics (the generated code still calls
 * `or_fail`), has a fixed capacity with explicit overflow counters, and exposes
 * only guest addresses, counts and digests. It contains no guest payload bytes,
 * no disassembly excerpts and no reconstructive derived data.
 *
 * Storage:
 *   - a first-window of the first `P11_TRACE_FIRST_CAPACITY` block entries;
 *   - a ring buffer of the last `P11_TRACE_RING_CAPACITY` block entries;
 *   - an open-addressed count table for distinct block addresses;
 *   - an open-addressed count table for distinct function addresses;
 *   - the first failure site/message/context and a failure counter;
 *   - an FNV-1a digest over the ordered block-address stream.
 *
 * Deterministic execution bound:
 *   The block hook also enforces an explicit, deterministic block-entry budget.
 *   The bounded-execution access budget bounds guest *memory accesses*, so a
 *   guest loop that performs no memory access after truncation cannot be
 *   interrupted (recorded as a Phase-10 limitation). The block budget closes
 *   that gap: when the budget is exceeded the hook records the denial and, if
 *   the host driver has armed the bound, unwinds to the driver's saved context
 *   with `longjmp`. The guest program is unchanged; the bound is a host-side
 *   execution harness with a fixed, recorded limit.
 */

#include <setjmp.h>

#define P11_TRACE_FIRST_CAPACITY 256u
#define P11_TRACE_RING_CAPACITY 4096u
#define P11_TRACE_TABLE_CAPACITY 8192u
#define P11_TRACE_FAILURE_WINDOW 64u
#define P11_BLOCK_BUDGET_DEFAULT UINT64_C(8000000)

jmp_buf p11_bound_jump;

static uint64_t g_p11_block_budget = P11_BLOCK_BUDGET_DEFAULT;
static uint64_t g_p11_block_denials;
static int g_p11_bound_armed;

void p11_bound_arm(uint64_t budget)
{
    g_p11_block_budget = budget;
    g_p11_block_denials = UINT64_C(0);
    g_p11_bound_armed = 1;
}

void p11_bound_disarm(void)
{
    g_p11_bound_armed = 0;
}

uint64_t p11_bound_budget(void) { return g_p11_block_budget; }
uint64_t p11_bound_denials(void) { return g_p11_block_denials; }
int p11_bound_reached(void) { return g_p11_block_denials != UINT64_C(0); }

static uint64_t g_p11_trace_block_events;
static uint64_t g_p11_trace_function_events;
static uint64_t g_p11_trace_block_digest = UINT64_C(0xcbf29ce484222325);

static uint32_t g_p11_trace_first[P11_TRACE_FIRST_CAPACITY];
static uint32_t g_p11_trace_ring[P11_TRACE_RING_CAPACITY];
static uint32_t g_p11_trace_ring_head;
static uint32_t g_p11_trace_ring_count;

static uint32_t g_p11_trace_recent[P11_TRACE_FAILURE_WINDOW];
static uint32_t g_p11_trace_recent_count;
static uint32_t g_p11_trace_failure_before[P11_TRACE_FAILURE_WINDOW];
static uint32_t g_p11_trace_failure_before_count;
static uint32_t g_p11_trace_failure_after[P11_TRACE_FAILURE_WINDOW];
static uint32_t g_p11_trace_failure_after_count;

static uint32_t g_p11_trace_block_keys[P11_TRACE_TABLE_CAPACITY];
static uint64_t g_p11_trace_block_counts[P11_TRACE_TABLE_CAPACITY];
static uint32_t g_p11_trace_block_used;
static uint64_t g_p11_trace_block_overflow;

static uint32_t g_p11_trace_function_keys[P11_TRACE_TABLE_CAPACITY];
static uint64_t g_p11_trace_function_counts[P11_TRACE_TABLE_CAPACITY];
static uint32_t g_p11_trace_function_used;
static uint64_t g_p11_trace_function_overflow;

static uint32_t g_p11_trace_current_function;
static uint32_t g_p11_trace_failure_site;
static uint32_t g_p11_trace_failure_function;
static uint64_t g_p11_trace_failure_source;
static const char *g_p11_trace_failure_message = "";
static uint64_t g_p11_trace_failure_count;
static uint64_t g_p11_trace_failure_block_index;

static uint32_t p11_trace_slot(uint32_t address)
{
    uint32_t hash = address * UINT32_C(2654435761);
    return (hash >> 13u) % P11_TRACE_TABLE_CAPACITY;
}

static void p11_trace_count_block(uint32_t address)
{
    uint32_t slot = p11_trace_slot(address);
    uint32_t probes;
    for (probes = 0; probes < P11_TRACE_TABLE_CAPACITY; ++probes) {
        uint32_t index = (slot + probes) % P11_TRACE_TABLE_CAPACITY;
        if (g_p11_trace_block_counts[index] == UINT64_C(0)) {
            g_p11_trace_block_keys[index] = address;
            g_p11_trace_block_counts[index] = UINT64_C(1);
            ++g_p11_trace_block_used;
            return;
        }
        if (g_p11_trace_block_keys[index] == address) {
            ++g_p11_trace_block_counts[index];
            return;
        }
    }
    ++g_p11_trace_block_overflow;
}

static void p11_trace_count_function(uint32_t address)
{
    uint32_t slot = p11_trace_slot(address);
    uint32_t probes;
    for (probes = 0; probes < P11_TRACE_TABLE_CAPACITY; ++probes) {
        uint32_t index = (slot + probes) % P11_TRACE_TABLE_CAPACITY;
        if (g_p11_trace_function_counts[index] == UINT64_C(0)) {
            g_p11_trace_function_keys[index] = address;
            g_p11_trace_function_counts[index] = UINT64_C(1);
            ++g_p11_trace_function_used;
            return;
        }
        if (g_p11_trace_function_keys[index] == address) {
            ++g_p11_trace_function_counts[index];
            return;
        }
    }
    ++g_p11_trace_function_overflow;
}

void p11_trace_function(uint64_t address)
{
    uint32_t value = (uint32_t)address;
    ++g_p11_trace_function_events;
    g_p11_trace_current_function = value;
    p11_trace_count_function(value);
}

void p11_trace_block(uint64_t address)
{
    uint32_t value = (uint32_t)address;
    unsigned byte;
    if (g_p11_trace_block_events < (uint64_t)P11_TRACE_FIRST_CAPACITY) {
        g_p11_trace_first[g_p11_trace_block_events] = value;
    }
    g_p11_trace_ring[g_p11_trace_ring_head] = value;
    g_p11_trace_ring_head = (g_p11_trace_ring_head + 1u) % P11_TRACE_RING_CAPACITY;
    if (g_p11_trace_ring_count < P11_TRACE_RING_CAPACITY) {
        ++g_p11_trace_ring_count;
    }
    if (g_p11_trace_recent_count < P11_TRACE_FAILURE_WINDOW) {
        g_p11_trace_recent[g_p11_trace_recent_count] = value;
        ++g_p11_trace_recent_count;
    } else {
        uint32_t position;
        for (position = 1u; position < P11_TRACE_FAILURE_WINDOW; ++position) {
            g_p11_trace_recent[position - 1u] = g_p11_trace_recent[position];
        }
        g_p11_trace_recent[P11_TRACE_FAILURE_WINDOW - 1u] = value;
    }
    if (g_p11_trace_failure_count != UINT64_C(0)
        && g_p11_trace_failure_after_count < P11_TRACE_FAILURE_WINDOW) {
        g_p11_trace_failure_after[g_p11_trace_failure_after_count] = value;
        ++g_p11_trace_failure_after_count;
    }
    for (byte = 0; byte < 4u; ++byte) {
        g_p11_trace_block_digest ^= (uint64_t)((value >> (8u * byte)) & 0xFFu);
        g_p11_trace_block_digest *= UINT64_C(0x100000001b3);
    }
    ++g_p11_trace_block_events;
    p11_trace_count_block(value);
    if (g_p11_block_budget != UINT64_C(0)
        && g_p11_trace_block_events > g_p11_block_budget) {
        ++g_p11_block_denials;
        if (g_p11_bound_armed) {
            g_p11_bound_armed = 0;
            longjmp(p11_bound_jump, 1);
        }
    }
}

void p11_trace_indirect_failure(uint64_t site, uint64_t source_value, const char *message)
{
    if (g_p11_trace_failure_count == UINT64_C(0)) {
        uint32_t position;
        g_p11_trace_failure_site = (uint32_t)site;
        g_p11_trace_failure_function = g_p11_trace_current_function;
        g_p11_trace_failure_source = source_value;
        g_p11_trace_failure_message = message != NULL ? message : "";
        g_p11_trace_failure_block_index = g_p11_trace_block_events;
        g_p11_trace_failure_before_count = g_p11_trace_recent_count;
        for (position = 0u; position < g_p11_trace_recent_count; ++position) {
            g_p11_trace_failure_before[position] = g_p11_trace_recent[position];
        }
    }
    ++g_p11_trace_failure_count;
}

uint64_t p11_trace_block_events(void) { return g_p11_trace_block_events; }
uint64_t p11_trace_function_events(void) { return g_p11_trace_function_events; }
uint64_t p11_trace_block_digest(void) { return g_p11_trace_block_digest; }
uint32_t p11_trace_ring_count(void) { return g_p11_trace_ring_count; }
uint32_t p11_trace_ring_capacity(void) { return P11_TRACE_RING_CAPACITY; }
uint32_t p11_trace_ring_address(uint32_t position)
{
    uint32_t start;
    if (position >= g_p11_trace_ring_count) {
        return 0u;
    }
    start = (g_p11_trace_ring_head + P11_TRACE_RING_CAPACITY - g_p11_trace_ring_count)
          % P11_TRACE_RING_CAPACITY;
    return g_p11_trace_ring[(start + position) % P11_TRACE_RING_CAPACITY];
}
uint32_t p11_trace_first_count(void)
{
    return g_p11_trace_block_events < (uint64_t)P11_TRACE_FIRST_CAPACITY
        ? (uint32_t)g_p11_trace_block_events : P11_TRACE_FIRST_CAPACITY;
}
uint32_t p11_trace_first_address(uint32_t position)
{
    return position < p11_trace_first_count() ? g_p11_trace_first[position] : 0u;
}
uint32_t p11_trace_table_capacity(void) { return P11_TRACE_TABLE_CAPACITY; }
uint32_t p11_trace_block_used(void) { return g_p11_trace_block_used; }
uint64_t p11_trace_block_overflow(void) { return g_p11_trace_block_overflow; }
uint32_t p11_trace_block_key(uint32_t index)
{
    return index < P11_TRACE_TABLE_CAPACITY && g_p11_trace_block_counts[index] != UINT64_C(0)
        ? g_p11_trace_block_keys[index] : 0u;
}
uint64_t p11_trace_block_count(uint32_t index)
{
    return index < P11_TRACE_TABLE_CAPACITY ? g_p11_trace_block_counts[index] : UINT64_C(0);
}
uint32_t p11_trace_function_used(void) { return g_p11_trace_function_used; }
uint64_t p11_trace_function_overflow(void) { return g_p11_trace_function_overflow; }
uint32_t p11_trace_function_key(uint32_t index)
{
    return index < P11_TRACE_TABLE_CAPACITY && g_p11_trace_function_counts[index] != UINT64_C(0)
        ? g_p11_trace_function_keys[index] : 0u;
}
uint64_t p11_trace_function_count(uint32_t index)
{
    return index < P11_TRACE_TABLE_CAPACITY ? g_p11_trace_function_counts[index] : UINT64_C(0);
}
uint32_t p11_trace_failure_site(void) { return g_p11_trace_failure_site; }
uint32_t p11_trace_failure_function(void) { return g_p11_trace_failure_function; }
uint64_t p11_trace_failure_source(void) { return g_p11_trace_failure_source; }
const char *p11_trace_failure_message(void) { return g_p11_trace_failure_message; }
uint64_t p11_trace_failure_count(void) { return g_p11_trace_failure_count; }
uint64_t p11_trace_failure_block_index(void) { return g_p11_trace_failure_block_index; }
uint32_t p11_trace_current_function(void) { return g_p11_trace_current_function; }
uint32_t p11_trace_failure_before_count(void) { return g_p11_trace_failure_before_count; }
uint32_t p11_trace_failure_before_address(uint32_t position)
{
    return position < g_p11_trace_failure_before_count ? g_p11_trace_failure_before[position] : 0u;
}
uint32_t p11_trace_failure_after_count(void) { return g_p11_trace_failure_after_count; }
uint32_t p11_trace_failure_after_address(uint32_t position)
{
    return position < g_p11_trace_failure_after_count ? g_p11_trace_failure_after[position] : 0u;
}
