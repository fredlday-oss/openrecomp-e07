/*
 * OpenRecomp Phase 8 - minimal freestanding <string.h> shim for the fixture
 * (OpenRecomp-authored).  Declares only the functions provided by the
 * OpenRecomp-authored port support; there is no libc in the image.
 */
#ifndef OPENRECOMP_P8_STRING_H
#define OPENRECOMP_P8_STRING_H

#include <stddef.h>

void *memcpy(void *dest, const void *src, size_t count);
void *memmove(void *dest, const void *src, size_t count);
void *memset(void *dest, int value, size_t count);

#endif
