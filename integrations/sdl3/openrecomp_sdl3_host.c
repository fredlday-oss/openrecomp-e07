/* SPDX-License-Identifier: Apache-2.0 */
#include "openrecomp_sdl3_host.h"

#include <SDL3/SDL.h>
#include <string.h>

bool openrecomp_sdl_host_init(OpenRecompSDLHost *host,
                              const char *title, int width, int height,
                              bool hidden)
{
    if (host == NULL || host->initialized || title == NULL ||
        width <= 0 || height <= 0) {
        return false;
    }
    if (!SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS | SDL_INIT_GAMEPAD)) {
        return false;
    }
    SDL_Window *window = SDL_CreateWindow(
        title, width, height, hidden ? SDL_WINDOW_HIDDEN : SDL_WINDOW_RESIZABLE);
    if (window == NULL) {
        SDL_Quit();
        return false;
    }

    host->window = window;
    host->initialized = 1;
    host->delivered_events = 0;
    host->gamepad = NULL;

    int count = 0;
    SDL_JoystickID *ids = SDL_GetGamepads(&count);
    if (ids != NULL) {
        if (count > 0) {
            host->gamepad = SDL_OpenGamepad(ids[0]);
        }
        SDL_free(ids);
    }
    return true;
}

bool openrecomp_sdl_host_poll(OpenRecompSDLHost *host,
                              OpenRecompSDLEvent *out_event)
{
    if (host == NULL || !host->initialized || out_event == NULL) {
        return false;
    }
    SDL_Event event;
    while (SDL_PollEvent(&event)) {
        memset(out_event, 0, sizeof(*out_event));
        switch (event.type) {
            case SDL_EVENT_QUIT:
            case SDL_EVENT_WINDOW_CLOSE_REQUESTED:
                out_event->kind = OPENRECOMP_SDL_EVENT_QUIT;
                break;
            case SDL_EVENT_KEY_DOWN:
            case SDL_EVENT_KEY_UP:
                out_event->kind = (event.type == SDL_EVENT_KEY_DOWN)
                    ? OPENRECOMP_SDL_EVENT_KEY_DOWN
                    : OPENRECOMP_SDL_EVENT_KEY_UP;
                out_event->code = (int32_t)event.key.scancode;
                out_event->repeat = event.key.repeat;
                break;
            case SDL_EVENT_GAMEPAD_ADDED:
                if (host->gamepad == NULL) {
                    host->gamepad = SDL_OpenGamepad(event.gdevice.which);
                }
                out_event->kind = OPENRECOMP_SDL_EVENT_GAMEPAD_ADDED;
                out_event->device_id = (uint32_t)event.gdevice.which;
                break;
            case SDL_EVENT_GAMEPAD_REMOVED:
                if (host->gamepad != NULL &&
                    SDL_GetGamepadID((SDL_Gamepad *)host->gamepad) ==
                        event.gdevice.which) {
                    SDL_CloseGamepad((SDL_Gamepad *)host->gamepad);
                    host->gamepad = NULL;
                }
                out_event->kind = OPENRECOMP_SDL_EVENT_GAMEPAD_REMOVED;
                out_event->device_id = (uint32_t)event.gdevice.which;
                break;
            case SDL_EVENT_GAMEPAD_BUTTON_DOWN:
            case SDL_EVENT_GAMEPAD_BUTTON_UP:
                out_event->kind = (event.type == SDL_EVENT_GAMEPAD_BUTTON_DOWN)
                    ? OPENRECOMP_SDL_EVENT_GAMEPAD_BUTTON_DOWN
                    : OPENRECOMP_SDL_EVENT_GAMEPAD_BUTTON_UP;
                out_event->device_id = (uint32_t)event.gbutton.which;
                out_event->code = (int32_t)event.gbutton.button;
                break;
            case SDL_EVENT_GAMEPAD_AXIS_MOTION:
                out_event->kind = OPENRECOMP_SDL_EVENT_GAMEPAD_AXIS;
                out_event->device_id = (uint32_t)event.gaxis.which;
                out_event->code = (int32_t)event.gaxis.axis;
                out_event->value = (int32_t)event.gaxis.value;
                break;
            default:
                continue;
        }
        host->delivered_events++;
        return true;
    }
    return false;
}

void openrecomp_sdl_host_shutdown(OpenRecompSDLHost *host)
{
    if (host == NULL || !host->initialized) {
        return;
    }
    if (host->gamepad != NULL) {
        SDL_CloseGamepad((SDL_Gamepad *)host->gamepad);
    }
    SDL_DestroyWindow((SDL_Window *)host->window);
    SDL_Quit();
    memset(host, 0, sizeof(*host));
}

const char *openrecomp_sdl_host_last_error(void)
{
    return SDL_GetError();
}
