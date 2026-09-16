# P2-40 — Generic Runtime Integration Audit (`OPENRECOMP_P2_40`)

Verdict: **PASS**

Markers:

```text
OPENRECOMP_P2_40=PASS
OPENRECOMP_GENERIC_RUNTIME_INTEGRATION_V1=PASS tests=181
```

## Baseline

- Branch: `phase2/opencode-v1`
- `HEAD`: `2fc27bfd80ef36b62ab3dc854562bbb4d0ce82db` (P2-14 boundary commit)
- Phase-1 reference tag verified unchanged: `openrecomp-phase1-pass^{commit}`
  = `46c2f971e1a42cf49bd936bad94697b81bf31002`
  (annotated tag object `8dbbd79ac3c7104bfa0374aecf2d9093be89c6c7`)
- No implementation source was modified by this stage. The stage adds one
  audit gate plus evidence and control-plane updates.

## Objective

Prove that the Phase-2 generic runtime layer is genuinely architecture-neutral
and reusable across guest architectures/platform adapters, in the same way
P2-30 proved it for the shared recompilation pipeline. Audit the runtime-facing
side: guest memory, input, frame/output, audio, host-call/service dispatch,
runtime lifecycle/state, the translated-host boundary and build/launch
integration; distinguish generic runtime capability from NES-specific platform
behavior; exercise the contracts with the existing NES path and with at least
one non-NES runtime fixture; add a deterministic regression gate that detects
future runtime architecture leakage or contract regressions.

## Audited modules

Generic runtime layer:

- `openrecomp/runtime_abi.py` (P2-08): memory, input, frame, audio, host
  calls, configuration/lifecycle, ABI version, generated-C boundary.
- `openrecomp/runtime.py` (Phase-1): generic normalized-IR core runtime
  (`GuestState`, `GuestMemory`, `HostBinding`).
- `openrecomp/module.py` (Phase-1): generic module-image memory segments.
- `openrecomp/host_emitter.py` (P2-07): translated-host runtime boundary.
- `openrecomp/build_pipeline.py` (P2-09): build/launch integration.

Architecture-specific boundary modules reviewed (not modified):

- `openrecomp/frontends/nes_runtime.py` (P2-22 NES platform adapter).
- `openrecomp/frontends/nes6502.py` (P2-20 NES6502 program bridge).
- Phase-1 headless platform layers `tools/nes_platform_v1.py`,
  `tools/gb_platform_v1.py`, `tools/sms_platform_v1.py` (documented extension
  inputs; not wired to the P2 generic contracts yet).

## Changes

- **New gate** `tools/test_generic_runtime_integration_v1.py` (deterministic,
  181 checks in the default regression run; `--skip-regressions` exists for
  development only and was not used for committed evidence).
- `SOURCE_SHA256SUMS.txt`: the new gate added via `update_sums.py`
  (129 -> 130 manifest entries; no existing entry changed).
- Evidence under `.openrecomp-phase2/evidence/P2-40/`.
- Control-plane updates: `STATE.md`, `HANDOFF.md`, `STAGE_QUEUE.md`.

**No corrections to generic runtime code were required**: no architecture
leakage was found, so no shared contract was changed, preserving compatibility
with every previously passing stage.

## Static isolation results (findings empty)

- Prohibited platform imports in the audited generic modules:
  `adapters.*`, `openrecomp.frontends.*`, `tools.*` -> **none**
  (single documented allowance: `openrecomp.module` imports the frozen Phase-1
  generic IR validator `tools.validate_ir_v1`).
- Prohibited platform identifiers/strings (NES/6502/PPU/APU/NROM/cartridge/
  mapper/controller/joypad/PS2/Xbox/RT64/Vulkan/D3D/SDL/XAudio/WASAPI/...):
  **none**.
- Prohibited platform service names (`nes.`, `gb.`, `sms.`, ...):
  **none**.
- Prohibited NES/GB/SMS bus-address literals
  (`0x2000`, `0x4016`, `0x4017`, `0x6000`, `0x8000`, `0x10000`, ...):
  **none**.
- Host-state imports (`os`, `time`, `random`, `uuid`, `socket`, ...) in
  `runtime_abi.py` / `runtime.py`: **none**.
- Scanner self-test: a planted leak (`NES_PPU_BASE = 0x2000`,
  `CONTROLLER_STROBE = 0x4016`, `"nes.frame.submit"`, `read_controller`) is
  detected as `platform_identifier` / `platform_string` /
  `platform_service_name` / `platform_bus_address`; a clean generic source is
  not flagged. The scanner cannot silently degrade to a no-op.

## Contract classification

All 21 audited runtime concepts are classified as one of: architecture-neutral
runtime contract (13), platform adapter responsibility (5),
architecture/frontend responsibility (3), host implementation responsibility
(4, including build/launch and backend selection). Full table with evidence
pointers: `contract_classification.md` and
`p2_40_tests.json -> findings.concept_classification`.

Bound-versus-assumption analysis (widths {8,16,32,64}, memory <= 2^64, frame
dimension <= 16384, channel caps) is in `contract_classification.md`. No guest
memory map, address width, register file, controller layout, PPU/APU behavior,
mapper, frame geometry, audio format, backend API or platform service name is
assumed by the generic layer.

## Platform-vs-generic responsibility analysis

`responsibility_analysis.md` documents the layer model and the
GB/GBC/SMS/RT64-like extension points. All four future-backend entries require
**no generic ABI change**; each platform maps to adapter responsibilities while
the generic contracts stay unchanged. Machine-readable:
`p2_40_tests.json -> findings.backend_extension_points`.

## Non-NES runtime exercise (translated host -> generic runtime, native)

Synthetic/original little-endian MIPS32 fixture (11 instructions, 44 bytes,
SHA-256 `9323f24533ec6c31cf954c8315fd674ac8efc8c803e960eb9b1a902891cfe237`).
It computes 20-bit guest pointers, performs two generic 32-bit memory writes,
then invokes three platform-declared services through fixture-explicit rules:

- `jr r4` (P2-06 `EXTERNAL_OR_RUNTIME_MEDIATED`, no guessed targets) ->
  `synthetic.frame.submit(0x10200, 2, 2, 1)`
- `ori` trigger -> `synthetic.audio.submit(0x10210, 8000, 1, 4, 0)`
- `xori` trigger -> `synthetic.input.poll()` -> `r6 = 141`, `r7 = 148`

Pipeline traversal: adapter decode -> P2-01 ProgramModel -> P2-02 CFG
(`blk_1000`, `blk_101c`) -> P2-03 (`fn_1000`) -> P2-04 -> P2-05
(`tu_fn_1000`) -> P2-06 (`EXTERNAL_OR_RUNTIME_MEDIATED`,
`EXTERNAL_RUNTIME_EVIDENCE`, no targets) -> P2-07 emission -> P2-08 generic
runtime ABI -> P2-09 deterministic build.

Generated `generated_source.c` SHA-256
`c0a76e0f19217aeed017fca9f2abc82ef644563c1374d046987452800679246a`; emitted
code references only `or_rt_memory_read`, `or_rt_memory_write`,
`or_rt_host_call`, `or_rt_failure_reason` (4 externs), the declared service
macros, and no pointer casts. Two emissions are byte-identical.

The generated program was compiled and executed natively (clang-cl/lld-link,
`/Brepro`); the same source was built twice in independent directories:
`EXECUTABLE_REPRODUCIBLE`, executable SHA-256
`96676becf33f2251fcbc0b097ad8fa7ea2c100f4754617a4a5dcbdac1ecaf5b2`.

Independent expected observable (Python reference driving `RuntimeState` +
`RuntimeMemory` + `RuntimeServiceTable` + `RuntimeFrame`/`RuntimeAudio`
contracts, plus a hand-built post-run memory image) equals the native
observable exactly (`expected_vs_actual.txt`):

```text
failed=0 error= register_count=5 reg[0]=0 reg[1]=66048 reg[2]=66064 reg[3]=141 reg[4]=148
mem_words=66048,66064
frame_count=1 frame[0]=2x2 format=RGBA8 checksum=16987283610251169330
audio_count=1 audio[0]=8000Hz channels=1 frames=4 format=U8 checksum=1557537621830222089
input_poll=141 memory_checksum=10954747769631612134
```

Frame/audio/input/memory are all transported through the generic contracts; the
synthetic adapter uses its own service names and its own format-id mapping
(`1 = RGBA8`, `0 = U8`), demonstrating that platform ids are adapter-defined.

## NES runtime path exercise (same generic contracts)

`NESRuntimeAdapter` (P2-22) was exercised through the same generic classes and
dispatch code path: controller bits `10110001` read via `$4016` from the same
`RuntimeInputSnapshot` type; one `RuntimeFrame` and one `RuntimeAudio`
submitted via `RuntimeState.host_call` with adapter-declared services
(`nes.audio.submit`, `nes.frame.submit`); arity mismatch and unsupported format
ids fail closed with stable codes; unsupported mapper, PPU register access and
expansion-area access raise `NESRuntimeError`. Both the NES table and the
synthetic table share `RuntimeServiceTable.dispatch` unchanged
(`nes_path_exercise.txt`).

## Fail-closed behavior (native and contract levels)

- Native unsupported-service run: declared-but-unsupported
  `synthetic.audio.submit` -> `failed=1`,
  `error=runtime host service synthetic.audio.submit failed`, `audio_count=0`,
  `input_poll=0`, continuation registers 0; the frame submitted before the
  failure is preserved (`unsupported_service.txt`).
- Unknown service, arity mismatch, handler exception and non-unsigned handler
  returns produce deterministic `RuntimeResult` failures (`UNKNOWN_HOST_SERVICE`,
  `HOST_CALL_ARITY`, `HOST_SERVICE_FAILED`).
- Memory: out-of-range, unsupported width, unsupported endianness, 64-bit
  address overflow, segment overlap, zero size, negative addresses fail; a
  16-bit space does not wrap and 0x800-byte memory does not NES-mirror to 0.
- Input/frame/audio validation rejects malformed payloads, limits, wrong types
  and unsupported formats.
- Runtime step budget latches `TRAP`; the first failure is preserved.
- Emitter: missing runtime ABI, undeclared service, host call without external
  evidence, invalid word width and empty service ids are rejected
  (`HostEmitterError`); without explicit P2-06 evidence the site stays
  `UNRESOLVED_INDIRECT_CALL` with no targets.

## Deterministic gate output

- Two full consecutive gate runs produced byte-identical stdout:
  `sha256 405c90d1c867495b3ac568a62b0d7c7e9234ca5ef469cdc2510d307b8d148228`
  (`run1.txt`, `run2.txt`; 181/181 checks pass, 20/20 regressions pass,
  0 failures).
- In-gate determinism: two emissions byte-identical
  (`emitter-deterministic`), pipeline fingerprints stable
  (`pipeline-deterministic`), state fingerprints stable
  (`state-snapshot-deterministic`), build manifests byte-identical
  (`build-manifest-deterministic`), native output stable across two
  executions (`native-output-stable`).
- Deterministic failure matrix above; no wall-clock, randomness, host identity,
  absolute path, temporary path or Python identity enters the record.

## Regressions

Re-run inside the gate (all returncode 0; `regression_results.json` records the
stdout SHA-256 of each run): P2-01..P2-14, P2-20..P2-23, P2-30, the runtime ABI
(P2-08), host emitter (P2-07), deterministic build (P2-09), NES runtime bridge
(P2-22), NES end-to-end (P2-23), the NES platform contract, Phase-1 host gates
(`PASS=44 FAIL=0 SKIPPED=2`, toolchain-gated skips never counted as passes),
and source integrity (`verified 130 manifest entries`).

## Commands and exit codes

```text
python tools/test_generic_runtime_integration_v1.py \
    --evidence-dir .openrecomp-phase2/evidence/P2-40 \
    --json .openrecomp-phase2/evidence/P2-40/p2_40_tests.json
exit code 0; OPENRECOMP_P2_40=PASS; OPENRECOMP_GENERIC_RUNTIME_INTEGRATION_V1=PASS tests=181

python update_sums.py                     (adds the new gate; 129 -> 130 entries)
python tools/phase1_host_gates_v1.py --only source-integrity
    PASS source-integrity  verified 130 manifest entries
```

## Evidence artifacts

`.openrecomp-phase2/evidence/P2-40/`: `RESULT.md`, `RESULT.json`,
`contract_classification.md`, `responsibility_analysis.md`,
`dependency_findings.txt`, `changed_files.txt`, `determinism.txt`,
`fixture.txt`, `pipeline_cfg.txt`, `pipeline_functions.txt`,
`pipeline_translation_units.txt`, `pipeline_indirect_control_flow.txt`,
`generated_source.c`, `generated_source_sha256.txt`,
`runtime_abi_contract.txt`, `static_isolation.json`, `build_manifest.json`,
`build_run_1.txt`, `build_run_2.txt`, `native_execution.txt`,
`expected_vs_actual.txt`, `unsupported_service.txt`, `nes_path_exercise.txt`,
`regression_results.json`, `source_integrity.txt`, `host_gates.json`,
`p2_40_tests.json`, `run1.txt`, `run2.txt`.

## Limitations / non-claims

- This PASS proves that the *audited* OpenRecomp runtime contracts are
  architecture-neutral for the supported Phase-2 paths. It does not prove
  complete generic console emulation, arbitrary future-architecture
  compatibility, complete NES PPU/APU behavior, arbitrary commercial-game
  runtime compatibility, cycle accuracy or full hardware emulation.
- The non-NES exercise uses a bounded synthetic MIPS32 fixture (11
  instructions) plus a gate-local synthetic platform adapter; the native
  equivalence claim covers exactly that fixture, its three declared services,
  the frame/audio/input payloads and the memory image.
- The generic runtime remains a contract surface: no runtime implementation is
  generated; `RuntimeState` is a deterministic contract/state object, not a
  guest execution engine.
- GB/GBC/SMS support is documented as extension points only; no GB/GBC/SMS
  adapter was implemented, and RT64-like backends remain optional later work.
- Toolchain-gated Phase-1 gates (`e07-hardened-end-to-end`,
  `external-repro-v1`) remain skipped on this host and are never counted as
  passes.
- `openrecomp/*.py` (including `runtime_abi.py`) remain outside
  `SOURCE_SHA256SUMS.txt` due to the pre-existing `update_sums.py` glob gap
  (`schemas/` vs `schema/`); their hashes are recorded in `changed_files.txt`
  and `RESULT.json`.

## Repository side effects

See `changed_files.txt`. No proprietary ROM/BIOS/firmware/keys/SDK material is
used: all fixtures are synthetic/original and generated in-tree. No existing
gate or claim boundary was weakened; no commit was created.

## Next stage

Per the authoritative `.openrecomp-phase2/STAGE_QUEUE.md`, the next queued
stage is **P2-50 — Build/package reproducibility** (clean-tree rebuild of
generated outputs from committed inputs).
