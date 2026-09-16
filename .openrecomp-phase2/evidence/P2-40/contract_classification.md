# P2-40 Generic Runtime Contract Classification

Every runtime-facing concept audited in P2-40 is assigned exactly one primary
layer. The classification is also machine-readable in
`p2_40_tests.json` (`findings.concept_classification`) and in
`static_isolation.json`.

Layers:

- **neutral** = architecture-neutral runtime contract (lives in the shared
  generic runtime layer; must not know any console/architecture/backend).
- **adapter** = platform adapter responsibility (fills the generic contract
  with platform-specific mapping/behavior).
- **frontend** = architecture/frontend responsibility (guest ISA facts:
  widths, registers, control flow, service sites).
- **host** = host implementation responsibility (process/toolchain/backend
  integration outside the shared ABI).

| # | Concept | Layer | Contract / reference | P2-40 evidence |
|---|---------|-------|----------------------|----------------|
| 1 | Guest memory image and checked byte/word access | neutral | `RuntimeMemory` read/write/read_bytes/write_bytes, explicit widths 8/16/32/64, explicit endianness | `memory-*` checks; 16/20/24-bit spaces; no wrap/alias |
| 2 | Guest address space size, endianness and segment layout | adapter | adapter supplies `RuntimeMemory(size_bytes, endianness, segments)` | `memory-20bit-segment-*`, `memory-24bit-*`, NES adapter 64 KiB bus |
| 3 | Guest address width declaration | frontend | `ProgramSource.address_width_bits`; emitter `word_bits` | fixture declares 32-bit; NES path declares 16 via its adapter/emitter config |
| 4 | Guest register file ownership | frontend | emitter `register_names` derived from adapter decode fields | fixture yields `r0,r4,r5,r6,r7`; NES fixture yields `a,x,c,z,n,tmp,ea` |
| 5 | Digital/analog input snapshot transport | neutral | `RuntimeInputSnapshot` (ordered booleans + unsigned analog at `analog_bits`) | `input-*` checks; canonicalization and round-trip |
| 6 | Device button/axis layout and serial protocol | adapter | NES adapter maps channels to the NES controller bit order and `$4016` serial protocol | `nes-adapter-input-mapping` (bits `10110001`) |
| 7 | Physical input device acquisition | host | host process feeds a `RuntimeInputSnapshot` | synthetic adapter and NES adapter both accept the same snapshot type |
| 8 | Frame geometry/format/payload transport | neutral | `RuntimeFrame(width, height, pixel_format, payload, sequence)` | `frame-*` checks; five non-NES geometries, five formats |
| 9 | Platform pixel format ids and rendering | adapter | adapter-local format id maps (`FRAME_FORMATS`) translate guest ids to `RuntimePixelFormat` | synthetic adapter id `1 = RGBA8`; NES adapter id `0 = RGBA8` (different mapping, same contract) |
| 10 | Frame presentation backend selection | host | host backend consumes `RuntimeFrame` submissions | no backend API is referenced by any audited module |
| 11 | Audio sample format/rate/channel/payload transport | neutral | `RuntimeAudio(sample_format, sample_rate, channels, frames, payload, sequence)` | `audio-*` checks; all six sample formats, rates 8 kHz-96 kHz, 1/2/4/6 channels |
| 12 | Platform audio format ids and synthesis | adapter | adapter-local format id maps; DSP stays outside the ABI | synthetic id `0 = U8`; NES id `0 = U8` / `1 = S16LE` |
| 13 | Audio device backend selection | host | host backend consumes `RuntimeAudio` submissions | no audio API is referenced by any audited module |
| 14 | Host service identity, arity and dispatch | neutral | `RuntimeService`, `RuntimeServiceTable.dispatch` | `services-*` checks; two disjoint tables share one dispatch implementation |
| 15 | Platform service names and implementations | adapter | adapter-declared ids (`nes.frame.submit`, `synthetic.frame.submit`, ...) | `nes-service-names-adapter-local`; static service-name scan empty |
| 16 | Which guest site invokes which service | frontend | P2-06 `EXTERNAL_OR_RUNTIME_MEDIATED` evidence + explicit `HostCallOperation` rule | `pipeline-classification-*`; no guessed targets, no-evidence emission fails closed |
| 17 | Runtime lifecycle, step budget and failure latch | neutral | `RuntimeConfig`, `RuntimeState` (`steps`, `failed`, `failure`, `trap`) | `state-*` checks; step trap latches `TRAP`; first failure wins |
| 18 | Deterministic RNG hook | neutral | `RuntimeState.next_random` seeded only from `RuntimeConfig.seed` | `state-random-seeded-deterministic`; no clock/OS/random imports |
| 19 | ABI identity and versioning | neutral | `RuntimeAbiVersion` / `RUNTIME_ABI` (`openrecomp-generic-runtime-abi 1.0.0`) | `runtime-abi-*`, `abi-version-*`, `config-abi-mismatch` |
| 20 | Generated host -> runtime boundary | host | emitter emits only `or_rt_memory_read/write`, `or_rt_host_call`, `or_rt_failure_reason` declarations; host provides the implementation | `emitter-boundary-declarations-only`; native support implements all three |
| 21 | Build, launch and artifact reproducibility | host | `build_pipeline` + host toolchain (`clang-cl`/`lld-link` `/Brepro`) | `build-*`, `native-*`; `EXECUTABLE_REPRODUCIBLE` |

## Bound versus assumption

The generic contracts contain explicit *bounds* (memory size <= 2^64,
widths {8,16,32,64}, frame dimension <= 16384, <= 256 digital channels,
<= 64 analog channels, <= 64 audio channels, step budget) and explicit
*enumerations* (pixel/sample formats, endianness). These are capability limits
of the shared contract, not console assumptions:

- no memory map (no mirroring, no regions, no bank windows) is baked into
  `RuntimeMemory`;
- no guest address width is assumed (8/16/32/64-bit values are all usable and
  the 64-bit address space is checked);
- no frame geometry or audio format is assumed (all enumerations are accepted
  and validated against the payload);
- no controller/PPU/APU/NROM concept, platform bus address, backend API or
  platform service name appears in the audited modules (static scans empty).

## Static isolation summary

- Prohibited platform imports in audited generic modules: **none**.
- Prohibited platform identifiers/strings/service names: **none**.
- Prohibited NES/GB/SMS bus-address literals: **none**.
- Host-state imports (`os`, `time`, `random`, `uuid`, ...) in `runtime_abi`
  and `runtime`: **none**.
- Scanner self-test: planted leak (`nes.frame.submit`, `PPU`, `CONTROLLER`,
  `0x2000`, `0x4016`) detected; generic source not flagged.
- The only allowed non-shared import is `openrecomp.module` ->
  `tools.validate_ir_v1` (frozen Phase-1 generic IR schema validator).
