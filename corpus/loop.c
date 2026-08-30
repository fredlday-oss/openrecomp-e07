typedef unsigned int u32;
volatile u32 g_state = 2u;
__attribute__((noinline)) u32 fixture_main(void) { u32 i=0u; while(i<6u){ g_state = g_state * 3u + i; i=i+1u; } return g_state; }
void _start(void) { (void)fixture_main(); for (;;) {} }
