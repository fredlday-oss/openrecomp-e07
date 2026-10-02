/* Optional SDL3 interactive host adapter. No guest-architecture dependencies.
 * Copyright OpenRecomp contributors. SPDX-License-Identifier: Apache-2.0
 */
#ifndef OPENRECOMP_SDL3_HOST_H
#define OPENRECOMP_SDL3_HOST_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum OpenRecompSDLEventKind {
    OPENRECOMP_SDL_EVENT_NONE = 0,
    OPENRECOMP_SDL_EVENT_QUIT,
    OPENRECOMP_SDL_EVENT_KEY_DOWN,
    OPENRECOMP_SDL_EVENT_KEY_UP,
    OPENRECOMP_SDL_EVENT_GAMEPAD_ADDED,
    OPENRECOMP_SDL_EVENT_GAMEPAD_REMOVED,
    OPENRECOMP_SDL_EVENT_GAMEPAD_BUTTON_DOWN,
    OPENRECOMP_SDL_EVENT_GAMEPAD_BUTTON_UP,
    OPENRECOMP_SDL_EVENT_GAMEPAD_AXIS
} OpenRecompSDLEventKind;

/* Codes are SDL3 scancodes, gamepad buttons or gamepad axes. Guest adapters
 * must explicitly map them into the guest's own controller/key semantics.
 * A gamepad axis value is in SDL3's signed 16-bit range.
 */
typedef struct OpenRecompSDLEvent {
    OpenRecompSDLEventKind kind;
    int32_t code;
    int32_t value;
    uint32_t device_id;
    bool repeat;
} OpenRecompSDLEvent;

/* Initialize with a zeroed object. The host owns the SDL lifecycle and
 * creates one window. Do not use with another owner of SDL_Init/SDL_Quit.
 * window and gamepad are intentionally opaque to callers.
 */
typedef struct OpenRecompSDLHost {
    void *window;
    void *gamepad;
    uint32_t initialized;
    uint64_t delivered_events;
} OpenRecompSDLHost;

bool openrecomp_sdl_host_init(OpenRecompSDLHost *host,
                              const char *title, int width, int height,
                              bool hidden);

/* Returns true when a mapped event is delivered; false if the queue is empty
 * (or an invalid argument is supplied). Drain once per host-loop iteration.
 */
bool openrecomp_sdl_host_poll(OpenRecompSDLHost *host,
                              OpenRecompSDLEvent *out_event);

void openrecomp_sdl_host_shutdown(OpenRecompSDLHost *host);
const char *openrecomp_sdl_host_last_error(void);

#ifdef __cplusplus
}
#endif
#endif
