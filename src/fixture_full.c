/*
 * OpenRecomp E07 synthetic fixture.
 * Original, intentionally small, freestanding RV32I program.
 * No console SDK, firmware, keys, game code, assets, or proprietary formats.
 *
 * The host_* functions are marker symbols. The recompilation runtime intercepts
 * calls to those symbols and supplies deterministic host behavior described in
 * contracts/host_contract.json.
 */
typedef unsigned int u32;
typedef unsigned short u16;

volatile u32 g_state = 3u;
volatile u32 g_counter = 0u;

__attribute__((noinline))
void host_graphics(u32 x, u32 y, u32 value) {
  (void)x;
  (void)y;
  (void)value;
}

__attribute__((noinline))
void host_audio(u32 sample) {
  (void)sample;
}

__attribute__((noinline))
u32 host_input(u32 index) {
  /* Marker body only; the translated runtime replaces this call. */
  return index;
}

__attribute__((noinline))
u32 host_system(u32 operation, u32 value) {
  /* Marker body only; the translated runtime replaces this call. */
  return operation + value;
}

__attribute__((noinline))
u32 fib(u32 n) {
  if (n < 2u) {
    return n;
  }
  return fib(n - 1u) + fib(n - 2u);
}

__attribute__((noinline))
u32 rotate_mix(u32 value, u32 count) {
  u32 out = value;
  u32 i = 0u;
  while (i < count) {
    out = (out * 5u + i) ^ (out >> 1u);
    i = i + 1u;
  }
  return out;
}

__attribute__((noinline))
u32 state_loop(u32 rounds) {
  u32 acc = g_state;
  u32 i = 0u;
  while (i < rounds) {
    u32 scripted = host_input(i);
    acc = (acc * 5u + i) ^ scripted;
    g_counter = g_counter + 1u;
    i = i + 1u;
  }
  g_state = acc;
  return acc;
}

__attribute__((noinline))
u32 render_phase(u32 a, u32 b) {
  u32 pixel = (a + b) & 255u;
  host_graphics(1u, 2u, pixel);
  return pixel;
}

__attribute__((noinline))
u32 audio_phase(u32 a, u32 b) {
  u32 sample = (a ^ b) & 65535u;
  host_audio(sample);
  return sample;
}

__attribute__((noinline))
u32 system_phase(void) {
  u32 value = host_system(2u, g_state);
  g_state = g_state ^ value;
  return value;
}

__attribute__((noinline))
u32 fixture_main(void) {
  u32 recursive = fib(7u);
  u32 looped = state_loop(5u);
  u32 mixed = rotate_mix(looped, 3u);
  u32 pixel = render_phase(recursive, mixed);
  u32 sample = audio_phase(recursive, looped);
  u32 system_value = system_phase();

  g_state = g_state ^ pixel;
  g_state = g_state + sample;
  g_state = g_state ^ system_value;
  g_state = g_state + g_counter;
  return g_state;
}

void _start(void) {
  (void)fixture_main();
  for (;;) {
    /* The E07 runner invokes fixture_main directly; _start is never executed. */
  }
}
