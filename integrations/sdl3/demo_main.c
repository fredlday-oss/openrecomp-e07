/* Isolated SDL3 smoke host. No recompilation or console compatibility claim.
 * SPDX-License-Identifier: Apache-2.0
 */
#include "openrecomp_sdl3_host.h"
#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv)
{
    OpenRecompSDLHost host = {0};
    const bool smoke = argc == 2 && strcmp(argv[1], "--smoke") == 0;
    const bool invalid = argc == 2 && strcmp(argv[1], "--test-invalid") == 0;
    if (argc > 2 || (argc == 2 && !smoke && !invalid)) {
        fprintf(stderr, "Usage: openrecomp_sdl3_smoke [--smoke|--test-invalid]\n");
        return 2;
    }
    if (invalid) {
        if (openrecomp_sdl_host_init(&host, "invalid", -1, 48, true)) {
            openrecomp_sdl_host_shutdown(&host);
            return 1;
        }
        puts("OPENRECOMP_SDL3_INVALID_INPUT=PASS");
        return 0;
    }
    if (!openrecomp_sdl_host_init(&host, "OpenRecomp SDL3 host", 640, 480,
                                  smoke)) {
        fprintf(stderr, "SDL3 initialization failed: %s\n",
                openrecomp_sdl_host_last_error());
        return 1;
    }
    if (smoke) {
        OpenRecompSDLEvent event;
        while (openrecomp_sdl_host_poll(&host, &event)) { }
        openrecomp_sdl_host_shutdown(&host);
        puts("OPENRECOMP_SDL3_LIFECYCLE=PASS");
        return 0;
    }
    bool running = true;
    while (running) {
        OpenRecompSDLEvent event;
        while (openrecomp_sdl_host_poll(&host, &event)) {
            if (event.kind == OPENRECOMP_SDL_EVENT_QUIT) {
                running = false;
            }
        }
        SDL_Delay(8); /* UI only: never guest clock or proof time source. */
    }
    openrecomp_sdl_host_shutdown(&host);
    return 0;
}
