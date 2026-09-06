#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

extern int openrecomp_run(void);
extern size_t openrecomp_state_count(void);
extern const char *openrecomp_state_name(size_t i);
extern uint64_t openrecomp_state_value(size_t i);

int main(void) {
    if (!openrecomp_run()) {
        printf("failed run\\n");
        return 1;
    }
    uint32_t r2 = 0, r3 = 0;
    for(size_t i=0; i<openrecomp_state_count(); ++i) {
        if (strcmp(openrecomp_state_name(i), "gpr:r2") == 0) r2 = (uint32_t)openrecomp_state_value(i);
        if (strcmp(openrecomp_state_name(i), "gpr:r3") == 0) r3 = (uint32_t)openrecomp_state_value(i);
    }
    printf("r2=%u r3=%u\\n", r2, r3);
    return 0;
}
