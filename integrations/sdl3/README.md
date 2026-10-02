# SDL3 shared interactive host (V0 scaffold)

This is the **optional, architecture-neutral host adapter** for OpenRecomp's
interactive native outputs. SDL3 is a host dependency, **not** an IR/frontend
or proof-harness dependency. No proprietary console SDKs, binaries or assets
are needed.

## Current implementation

- Owns one SDL3 window and the SDL lifecycle.
- Pumps quit, keyboard and first-connected-gamepad events into a small,
  SDL-header-free C event interface.
- Preserves guest-specific input mapping outside this adapter.
- Includes a standalone lifecycle smoke program and invalid-input test.
- Does **not** yet present guest frames, render 3D, output PCM audio, load
  Native AOT ABI modules, or implement Xbox/PS2 graphics emulation.

The host V0 API is experimental; it does not change frozen IR V1 or
Native AOT ABI V1, and cannot promote console compatibility claims.

## Build

Install SDL3 3.2+ development files and CMake 3.20+ first:

```sh
cmake -S integrations/sdl3 -B build/sdl3 -DCMAKE_BUILD_TYPE=Release
cmake --build build/sdl3 --config Release
ctest --test-dir build/sdl3 --output-on-failure -C Release
```

If SDL3 is in a custom installation, pass `-DCMAKE_PREFIX_PATH=<prefix>`.
The target uses `SDL3::SDL3` as supported by SDL's own CMake integration.
On Windows with a dynamic SDL3 installation, ensure `SDL3.dll` is next to
the smoke executable or on the executable's DLL search path.

To launch the standalone interactive window, run `openrecomp_sdl3_smoke`
from the build output directory. Close the window to exit. On a configured
display, `openrecomp_sdl3_smoke --smoke` tests lifecycle and immediate
shutdown. On Linux the CTest lifecycle case sets `SDL_VIDEODRIVER=dummy`.

The lifecycle smoke test cannot establish a rendering, audio, controller
mapping or guest-execution PASS.

## Integration rules

- Treat SDL events as nondeterministic host input; map/snapshot them explicitly
  at a guest-visible input boundary.
- Never use SDL timers or frame pacing to calculate deterministic guest cycles.
- Translate console-specific graphics **before** presenting them through an
  SDL3-compatible rendering/presentation implementation.
- Xbox requires its own Direct3D 8/NV2A adapter; PS2 requires its own GS/VU/
  VIF/GIF path. Neither is implemented here.
- Keep the existing noninteractive CLI and proof harness fully operational
  without SDL3.
- Do not infer support from a successful SDL window or lifecycle test.
- Do not merge/promote this adapter into a certified runtime path until its
  separate build, lifecycle, input, audio, graphics and regression gates pass.

See [host adoption plan](../../docs/SDL3_HOST_RUNTIME.md).
