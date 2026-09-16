# P2-40 Platform-vs-Generic Responsibility Analysis

## Layer model

```text
        generated host code (per-architecture, per-fixture)
                 |
                 v   (only generic symbols)
   or_rt_memory_read / or_rt_memory_write / or_rt_host_call / or_rt_failure_reason
                 |
                 v
   generic runtime contracts            <- audited here (P2-40)
   RuntimeMemory / RuntimeInputSnapshot / RuntimeFrame / RuntimeAudio
   RuntimeService / RuntimeServiceTable / RuntimeConfig / RuntimeState /
   RuntimeAbiVersion
                 |
                 v
   platform adapters                    <- own the platform behavior
   e.g. openrecomp/frontends/nes_runtime.py (NES bus),
        synthetic test adapter (P2-40 fixture),
        future gb/gbc/sms adapters
                 |
                 v
   host implementation                  <- process, toolchain, devices, backends
   build_pipeline (clang-cl/lld-link), native executable, presentation/audio
```

## Findings

1. **Generic layer.** `openrecomp/runtime_abi.py` names only generic operations
   and capability bounds. It has no memory-map knowledge, no register naming, no
   controller/PPU/APU/NROM concepts, no fixed geometry/format, no console or
   backend API, and no platform service names. `RUNTIME_WIDTHS` and the
   memory/frame/audio bounds are validated capability limits, not console
   assumptions (proven by the 16/20/24-bit memory checks, five frame geometries,
   all six audio formats and the 0..2^64-1 address checks).

2. **Platform adapters.** All platform behavior observed in P2-40 lives in
   adapters:
   - `openrecomp/frontends/nes_runtime.py`: CPU bus decoding, RAM mirrors,
     PRG-ROM window, `$4016` controller serial protocol, `nes.frame.submit` /
     `nes.audio.submit` services, NROM-only mapper with fail-closed rejection.
   - P2-40 synthetic adapter (gate-local): a 0x20000-byte memory image with
     payload segments at 0x10200/0x10210, its own service names
     (`synthetic.frame.submit`, `synthetic.audio.submit`,
     `synthetic.input.poll`) and its own format id mapping (1 = RGBA8, 0 = U8).
   Both adapters use the same generic classes and the same
   `RuntimeServiceTable.dispatch` code path; neither required a change to the
   shared runtime ABI. The two format-id mappings differ on purpose, proving the
   contract does not prescribe platform ids.

3. **Architecture/frontend.** The guest ISA facts (address width, word width,
   register naming, control flow, which site is a runtime service) come from the
   adapter/fixture pipeline (`ProgramSource`, P2-06 evidence, emitter rules) and
   are passed into the generic contracts by configuration, never read from them.

4. **Host implementation.** The generated C is compiled and run by the host
   toolchain; the host provides `or_rt_*` implementations. `build_pipeline`
   records toolchain provenance and reproducibility without any platform
   knowledge (no NES/GB/SMS strings in its source; static scan empty).

## Extension points for additional backends

Machine-readable form: `p2_40_tests.json` -> `findings.backend_extension_points`.
All four entries require **no generic ABI change**.

### GB / GBC (`gb`, `gbc`)

- Address width: 16-bit guest space (adapter-configured `RuntimeMemory`).
- Adapter responsibilities: ROM-only/MBC banking, JOYP input protocol, 2bpp
  tile-to-pixel expansion, 4-channel APU mixing/resampling, CGB VRAM/WRAM
  banking and palette expansion.
- Generic contracts used unchanged: `RuntimeMemory`, `RuntimeInputSnapshot`,
  `RuntimeFrame`, `RuntimeAudio`, `RuntimeServiceTable`, `RuntimeState`.
- Phase-1 already contains a headless GB/GBC platform layer
  (`tools/gb_platform_v1.py`, `tools/sm83_frontend_v1.py`); it is an
  independent platform surface today. A P2 adapter would wrap it and expose
  `gb.frame.submit` / `gb.audio.submit` through the generic service table, and
  route guest memory through `RuntimeMemory` segments.

### SMS (`sms`)

- Address width: 16-bit guest space; Z80 I/O ports map to adapter-defined
  services and memory-side registers.
- Adapter responsibilities: Sega mapper banking, controller-port decoding, VDP
  palette expansion, PSG synthesis.
- Phase-1 already contains a headless SMS platform layer
  (`tools/sms_platform_v1.py`, `tools/z80_frontend_v1.py`), again usable as an
  adapter input without touching the generic ABI.

### RT64-like presentation backend

- A rendering backend is a **host** concern: it consumes `RuntimeFrame`
  submissions (geometry/format/payload) and `RuntimeAudio` submissions. No GPU,
  windowing or audio API is present in the shared ABI, and none may be added
  there without a new evidence-backed stage. The extension point is a host-side
  consumer of the generic submission contracts, optionally reached through an
  adapter-declared service.

## What was deliberately *not* done

- No generic ABI change was required or made (no corrections were needed).
- No existing implementation source was modified; the stage adds one audit gate
  (`tools/test_generic_runtime_integration_v1.py`) and evidence.
- No GB/GBC/SMS adapter was implemented here; only the mapping onto the generic
  contracts is documented and asserted to require no ABI change.
