typedef unsigned int u32;
volatile u32 g_state = 1u;
__attribute__((noinline)) u32 fixture_main(void) { g_state = g_state + 41u; return g_state; }
void _start(void) { (void)fixture_main(); for (;;) {} }
