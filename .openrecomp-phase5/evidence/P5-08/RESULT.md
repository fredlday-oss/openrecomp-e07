# P5-08 Host Emission + NES Platform Adapter - Result

Verdict: `PASS`

## Baseline

- Branch `phase5/nes-platform-v1` at commit `08db673` (P5-07 boundary).

## Objective (frozen queue)

Emit deterministic native host code for the proven NES CPU subset and connect
it through the Phase-4 runtime/platform adapter interfaces. No direct original
6502 guest execution on the host.

## Delivered

- `.openrecomp-phase5/src/p5_emit_v1.py`: deterministic switch-over-PC C
  emitter for the fixture's 231 neutral instructions:
  - documented 6502 semantics for the reachable subset (loads/stores, ALU with
    N/V/Z/C, compares, RMW, implied/flag ops, stack, JSR/RTS with the
    documented return convention, BRK/RTI, conditional branches, page wrap,
    JMP-indirect page wrap);
  - the single declared indirect site maps to the declared `p5.exit` host
    service through the typed runtime ABI; any other indirect site or
    undocumented opcode fails closed at emission;
  - NMI entry is generated host logic (push PC/P with B clear, set I, vector
    `$FFFA`) executed at instruction boundaries when the platform reports a
    due delivery; original guest code is never executed on the host.
- `.openrecomp-phase5/src/p5_support_v1.py`: bounded NES runtime support in C
  (P5-05 bus, P5-06 PPU semantics, P5-07 frame/vblank/input scheduling, typed
  `or_rt_*` services) plus a canonical observable and the shared Phase-2
  `build_generated_host` build call.
- New `tools/test_phase5_host_emit_v1.py` gate.

## Verification

- Emission deterministic (program and support byte-identical across runs);
  231 switch cases; only typed `or_rt_*` externs; no forbidden host calls
  (`system`, `popen`, `exec`, `fork`, `dlopen`, `LoadLibrary`,
  `CreateProcess`); no function-pointer execution of guest bytes.
- Fail-closed emission: undeclared indirect site, wrong-site binding and an
  undocumented opcode all raise `HostEmitError`.
- Reproducible native build through the shared pipeline
  (`EXECUTABLE_REPRODUCIBLE`, clang-cl.exe + lld-link.exe).
- Three identical native runs of the fixture: `failed=0`, `exit=1`,
  `steps=90904`, `pc=0xC0FD`, `a=0x00 x=0x08 y=0x01 sp=0xFF p=0x27`,
  `frames=11`, `nmi=8`, `clock=298327`, `exit_arg=0xC0FD`,
  `ram_fnv1a64=0x2FC4A54B3F0C22CF`, `ppu_fnv1a64=0xCF103950DA2AD813`,
  `state_fnv1a64=0x440A095E452B3BA9`, and the exact 11-line frame transcript
  (input byte plus tile-space/PPU digests per frame).

## ABI / platform boundary

- Generated code reaches the host only through `or_rt_memory_read`,
  `or_rt_memory_write`, `or_rt_host_call` and `or_rt_failure_reason`; the
  run-exit service is the declared profile service `p5.exit` (numeric id
  emitted by the ABI contract).
- The support mediates every external interaction (guest memory, PPU, APU
  latches, controllers, timing, host service) and fails closed on unmapped
  accesses.

## Official gate

- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 1958 bytes raw, raw sha256
    `96004f1228941292482e9c4ab8dd8b0f96487b9090a46444f770bb2c9510d4aa`,
    LF sha256
    `732ad76760159ef46da5be03cb6c3893958740c8354c96d3c742e73be0969e0f`.
  - `p5_08_tests.json` sha256
    `edb65ad5575519b899b83b570f3ebfcf1a110a773e65d94a8d2c77a5170ed5d8`.
- Markers: `OPENRECOMP_P5_08=PASS`,
  `OPENRECOMP_PHASE5_HOST_EMIT_V1=PASS tests=48`; terminal/general reserved
  as `NOT_PROVEN`.
- Gate sha256 `41cf26fad27c3a4d0edb6d33caa7bd7040d3a6d2aa35c3acb254b98d8dd95896`;
  Phase-5 manifest verifies all twenty-two entries.

## Regressions

`tools/test_host_emitter_v1.py` and `tools/test_build_pipeline_v1.py` re-pass
with empty stderr (recorded in `regressions.json`).

## Limitations

- The emitted subset is exactly the audited public fixture path; other 6502
  programs are not accepted by this emitter unless separately proven.
- The timing model is the bounded P5-07 model, not cycle accuracy.
- The frame observable is the bounded tile-space/PPU digest, not rendered
  video.

## Evidence files

`RESULT.md`, `p5_08_tests.json`, `official_runs.json`, `determinism.json`,
`emission.json`, `observable.json`, `regressions.json`, `run1.txt`,
`run2.txt`, `run1.err.txt`, `run2.err.txt`.

## Next stage

P5-09 - Native execution of legal NES fixture.
