typedef unsigned int u32;
volatile u32 g_state = 9u;
volatile u32 g_counter = 0u;
__attribute__((noinline)) u32 bump(u32 x){ g_counter=g_counter+1u; return x+g_counter; }
__attribute__((noinline)) u32 fixture_main(void){ u32 a=bump(g_state); u32 b=bump(a); g_state=a^b; return g_state; }
void _start(void){ (void)fixture_main(); for(;;){} }
