# SDL3 as OpenRecomp's shared interactive host runtime

**Decision:** adopt SDL3 as the preferred cross-platform *interactive* host
runtime for native recompiled outputs, subject to staged implementation and
evidence gates. Preserve a dependency-free headless/reference host for all
proof, verification and batch-processing workflows.

**Implementation status:** V0 SDL3 lifecycle/input scaffold exists in
`integrations/sdl3/`; full native-module integration, audio and GPU frame
presentation are **CANDIDATE / NOT PROVEN**.

## Boundary

```text
guest-specific frontend (PS1 / PS2 / Xbox / 8-bit platforms / ...)
       -> normalized IR / Module Image
       -> reference execution or portable native AOT
       -> frozen Native AOT ABI V1 and explicit host callbacks
       -> guest-specific devices + graphics-command translator
       -> architecture-independent host services
             |-> headless / deterministic evidence host (unchanged)
             |-> optional SDL3 interactive host
                    |-> window and lifecycle
                    |-> mapped keyboard + controller input
                    |-> PCM audio sink [planned]
                    |-> software framebuffer [planned]
                    |-> SDL_GPU 3D presentation [planned]
```

SDL3 never decodes guest instructions or interprets console-specific GPU
registers. Translation of Xbox D3D8/NV2A state or PS2 GS/VU/VIF/GIF
semantics remains in separate console adapters. SDL_GPU provides host
rendering primitives, not a free graphics-compatibility implementation.

## Non-negotiable constraints

1. No changes to the frozen IR V1 schema, Module Image semantics or Native
   AOT ABI V1 as part of SDL3 adoption.
2. SDL3 remains an optional build dependency; `RUN.sh`,
   `EXTERNAL_REPRO_V1.sh`, CI proof gates and headless execution must work
   when SDL3 is absent.
3. SDL event order and wall time are host observations, not deterministic
   evidence or guest-cycle sources. Inputs are explicitly translated and
   recorded before guest consumption.
4. No title-keyed compatibility behaviour, invented hardware responses,
   implicit success fallbacks or relaxation of existing fail-closed gates.
5. Console-specific tests use synthetic/homebrew redistributable fixtures.
   Keep games, BIOS/firmware, console SDKs, keys and customer IP out of the
   public repository.
6. Keep Unreal Engine integration independent. Unreal and SDL3 are
   alternative Native AOT ABI host consumers, not mandatory layers of one
   another.

## Admission stages

| Stage | Required evidence | Status |
| --- | --- | --- |
| V0: lifecycle | SDL3 system-package build, window creation, input validation, teardown, no-SDL headless baseline | CANDIDATE; source scaffold only |
| V1: input | synthetic keyboard/gamepad mapping, hotplug, replay and determinism boundary | NOT PROVEN |
| V2: 2D/audio | known-frame hash before presentation, audio PCM checksum before playback; headless vs SDL3 equivalence | NOT PROVEN |
| V3: GPU | SDL_GPU rendering, resize, device failure/recovery, known-frame tests on intended backends | NOT PROVEN |
| V4: native module | load the existing Native AOT ABI V1 module without ABI changes; bound failure/negative tests | NOT PROVEN |
| Platform adapters | console-specific graphics/device contract and bounded title-independent fixtures for each guest | NOT PROVEN |

Each stage needs its own reproducible build/run output and independent
review. Source presence, a local smoke run, and generic SDL3 API support
must not be advertised as guest playability or console compatibility.

## Platform-specific sequencing

- First reuse SDL3 in whichever existing 2D guest adapter has a verified,
  isolated frame buffer; do not switch all existing adapters at once.
- For original Xbox, adapt the current D3D8 -> modern rendering work to the
  SDL3 host while keeping NV2A compatibility separate.
- For PS2, add a GS-targeted adapter and only then connect it to the SDL3
  presentation target. SDL3 alone cannot implement GS, VU, VIF, GIF or DMA.
- Preserve PS1 ongoing execution/frontier work independently; do not
  contaminate Phase 31 or its certified history with runtime refactoring.

## Licensing / portability

SDL3 is available under the zlib license and may be used commercially.
Retain its required license notice in distributions containing SDL3.
Use the installed `SDL3::SDL3` CMake target and pin/test the actual
package version when gathering release evidence. The optional V0 adapter
requires SDL3 >= 3.2, and no third-party source is vendored.
