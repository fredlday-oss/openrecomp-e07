#include <stddef.h>
#include <stdint.h>

#ifndef OPENRECOMP_EXPECTED_STATE
#error OPENRECOMP_EXPECTED_STATE must be defined
#endif

typedef int (*openrecomp_host_callback)(const char *, const uint64_t *, size_t, uint64_t *, int *);

void openrecomp_set_host_callback(openrecomp_host_callback callback);
int openrecomp_run(void);
uint64_t openrecomp_observed_state(void);
uint64_t openrecomp_function_return(void);
int openrecomp_function_has_return(void);
uint64_t openrecomp_operations(void);

int main(void) {
    const uint64_t expected = (uint64_t)OPENRECOMP_EXPECTED_STATE;
    openrecomp_set_host_callback((openrecomp_host_callback)0);
    if (!openrecomp_run()) return 2;
    if (openrecomp_observed_state() != expected) return 3;
    if (!openrecomp_function_has_return()) return 4;
    if (openrecomp_function_return() != expected) return 5;
    if (openrecomp_operations() == UINT64_C(0)) return 6;
    return 0;
}
