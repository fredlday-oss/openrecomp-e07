# P2-08 — Generic Runtime ABI V1

VERDICT: `PASS`

STAGE MARKER: `OPENRECOMP_P2_08=PASS`
GATE MARKER: `OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests=169`

## Baseline

| Item | Value |
| --- | --- |
| Stage | `OPENRECOMP_P2_08_GENERIC_RUNTIME_ABI_V1` |
| Branch | `phase2/opencode-v1` |
| Starting commit | `30b4321011b963efce19b321c72b97f886ba2b3d` (`30b4321 phase2: complete P2-07 host emitter v1`; `HEAD` at stage start) |
| Phase-1 freeze | tag `openrecomp-phase1-pass` -> `46c2f971e1a42cf49bd936bad94697b81bf31002` (verified unchanged) |
| Prior gates | P2-07 `106`, P2-06 `134`, P2-05 `104`, P2-04 `61`, P2-03 `67`, P2-02 `82`, P2-01 `49` |

Pre-flight: branch correct; `HEAD` equals the P2-07 boundary; the Phase-1 tag
resolves to the frozen commit; only the excluded untracked residue
(`.openrecomp-phase2/backups/`, `artifacts/mips32_translation_v1/`,
`artifacts/mips32_translation_evidence_closure_v1/`) was present and was left
untouched.

## Objective

Implement and validate the first **architecture-neutral** Generic Runtime ABI for
OpenRecomp: deterministic contracts between generated host code (P2-07) and
runtime services for memory, host calls, input, frame/video, audio, failure/trap
and deterministic runtime state, with an explicit ABI version. It must not become
a console-specific runtime, must not implement the P2-09 deterministic build
pipeline, and must not claim end-to-end recompilation.

## Files added

| File | Role |
| --- | --- |
| `openrecomp/runtime_abi.py` | Neutral P2-08 runtime ABI: `RuntimeAbiVersion`, `RuntimeMemory`/`RuntimeMemorySegment`, `RuntimeService`/`RuntimeServiceTable`, `RuntimeHostCallRequest`/`RuntimeHostCallRecord`, `RuntimeInputSnapshot`, `RuntimeFrame`, `RuntimeAudio`, `RuntimeFailure`/`RuntimeFailureCode`/`RuntimeResult`, `RuntimeConfig`/`RuntimeAbiConfig`, `RuntimeState`, `abi_c_declarations`/`abi_c_source`. |
| `tools/test_runtime_abi_v1.py` | Deterministic 169-check gate with optional `--json` and an optional native compile/run check. |
| `.openrecomp-phase2/evidence/P2-08/*` | This evidence bundle, including a synthetic generated-C fixture and scenario output. |

## Files modified

| File | Change |
| --- | --- |
| `openrecomp/host_emitter.py` | Bounded, additive/opt-in P2-08 integration (see "Emitter integration"). Default (`runtime_abi=None`) output is unchanged. |
| `SOURCE_SHA256SUMS.txt` | Registered `tools/test_runtime_abi_v1.py` via `update_sums.py` (117 -> 118 entries). No existing hash changed. |
| `.openrecomp-phase2/STATE.md`, `HANDOFF.md` | Stage transition (P2-08 PASS -> P2-09). |
| `.openrecomp-phase2/STAGE_QUEUE.md` | Control-plane status only: P2-08 `COMPLETE`, P2-09 `NEXT`. |

No P2-00..P2-07 implementation source was modified except `host_emitter.py`
(additive/opt-in only). No prior test was weakened.

## Runtime ABI version

- name: `openrecomp-generic-runtime-abi`
- version: `1.0.0` (`RUNTIME_ABI_VERSION`)
- structured: `RuntimeAbiVersion(name, major, minor, patch)` with `parse`,
  `current`, `version_string`, `to_document`.
- compatibility: same name **and** same `major` are compatible; an incompatible
  version is rejected with `ABI_VERSION_MISMATCH` at `RuntimeConfig` /
  `RuntimeAbiConfig` construction, so future incompatible ABI changes are
  detectable.

## Memory model (`RuntimeMemory`)

- Bounded guest address space; a guest address is an index into an internal
  byte buffer and is **never** reinterpreted as a host pointer.
- Checked `read`/`write` (and `try_read`/`try_write` returning `RuntimeResult`).
- Explicit width: 8/16/32/64 bits. Explicit endianness: per-memory default
  (little/big) with an explicit per-access override.
- Deterministic failures: `MEMORY_OUT_OF_RANGE`, `MEMORY_WIDTH_UNSUPPORTED`,
  `MEMORY_ADDRESS_OVERFLOW`, `MEMORY_ENDIANNESS_UNSUPPORTED`,
  `MEMORY_SEGMENT_OVERLAP`.
- `address + width` overflow/wrap is rejected explicitly (including addresses
  beyond the 64-bit space and at `2^64-1`).
- No unchecked unaligned host-pointer casts and no undefined host-language
  behavior: byte access uses bounded slicing + `int.from_bytes`/`to_bytes`.
- Byte access (`read_bytes`, `snapshot`) returns immutable `bytes` copies; no
  public `data`/`buffer` attribute and no `memoryview`/`ctypes` mechanism exists.

## Host-call model

- `RuntimeHostCallRequest(service, args)` with a stable service identity and
  explicit unsigned 64-bit argument tuple.
- `RuntimeServiceTable(services, handlers)` validates that every declared
  service has a handler and that no handler is registered for an undeclared
  service. Canonical service ids are sorted and assigned stable numeric ids for
  generated C (`OR_RT_SERVICE_<ID>`).
- `dispatch`: unknown service -> `UNKNOWN_HOST_SERVICE`; wrong arity ->
  `HOST_CALL_ARITY`; handler exception -> `HOST_SERVICE_FAILED` (deterministic,
  no exception text); non-unsigned return -> `HOST_SERVICE_FAILED`.
- `RuntimeHostCallRecord(sequence, service, args, result)` preserves arguments
  and result deterministically in `RuntimeState.host_calls`.
- No console API implementations are invented.

## Input model (`RuntimeInputSnapshot`)

- Generic, layout-free ordered `digital` boolean channels (<=256) and `analog`
  unsigned channels (<=64) at an explicit `analog_bits` width (8/16/32/64).
- No Xbox/PlayStation/Nintendo controller layout is assumed; platform mappings
  belong outside the shared ABI.
- Canonicalization: trailing default channels (`False`/`0`) are trimmed on
  construction, so logically identical states compare and hash identically.
- Validation fails closed (`INPUT_INVALID`) on non-boolean digital values,
  over-width/negative analog values, excessive channel counts, bad `analog_bits`
  and malformed documents.

## Frame model (`RuntimeFrame`)

- Generic descriptor: `width`, `height`, `pixel_format`, opaque `payload`,
  monotonic `sequence`.
- Neutral pixel formats: `RGBA8`, `BGRA8`, `RGB565`, `INDEX8`, `GRAY8`.
  Payload length is validated against geometry/format.
- `checksum()` = sha256(payload); `fingerprint()` = sha256(canonical descriptor
  including the checksum). Deterministic serialization round-trips.
- No D3D/Vulkan/OpenGL/SDL/RT64/console GPU implementation.

## Audio model (`RuntimeAudio`)

- Generic submission boundary: `sample_format`, `sample_rate`, `channels`,
  `frames`, opaque `payload`, `sequence`.
- Neutral sample formats: `U8`, `S16LE`, `S16BE`, `S32LE`, `F32LE`, `F32BE`.
  Payload length is validated against format/channels/frames.
- `checksum()` = sha256(payload); `fingerprint()` deterministic; serialization
  round-trips.
- No XAudio2/SDL audio/WASAPI/console DSP implementation.

## Failure model

- `RuntimeResult(ok, value, failure)` and
  `RuntimeFailure(code, detail, address, width_bits)`.
- Stable `RuntimeFailureCode` values (14) emitted verbatim in generated C as
  `OR_RT_<CODE>`.
- Unsupported behavior terminates through an explicit failure/trap; nothing is
  silently continued. `RuntimeState.trap`/`record_failure` latch the first
  deterministic failure.

## Deterministic runtime state

- `RuntimeState` combines bounded memory, an explicit host-service table, an
  input snapshot, frame/audio submission logs, a failure latch and a step
  counter. `snapshot()` is canonical JSON and `fingerprint()` is its sha256.
- No dependence on wall-clock time, random host state, process ids, memory
  addresses, filesystem ordering, locale or environment variables. The only
  pseudo-random surface is `RuntimeState.next_random`, a deterministic hook
  seeded solely from `RuntimeConfig.seed`.

## Emitter integration (bounded, evidence-backed)

- `HostEmitterConfig.runtime_abi: RuntimeAbiConfig | None` (default `None`) and
  `HostInstructionSemantics.host_call: HostCallOperation | None`.
- A host call is emitted **only** when a trusted semantic rule explicitly names a
  service that the configured runtime ABI declares. The service identity is never
  inferred from an address, opcode, mnemonic or reason string.
- On an indirect site the P2-06 classification must be
  `EXTERNAL_OR_RUNTIME_MEDIATED`; a host call on a `RESOLVED`, `BOUNDED_CANDIDATES`
  or `UNRESOLVED_*` site fails closed.
- Undeclared service, missing `runtime_abi` config, or a host call on a
  non-external indirect site all raise `HostEmitterError`.
- Generated C contains only declarations (`extern or_rt_*`) plus the stable
  failure-code enum and service macros. No platform implementation is generated.
- `runtime_abi=None` reproduces the exact P2-07 output (no `or_rt_` surface,
  unchanged includes), so P2-07 fail-closed behaviour is intact and no guest
  semantic coverage is broadened. Concretely, the default arithmetic fixture
  fingerprint is `e155689cb6220ce07ce016ce69082137cf33f47795284e3de85274109a132716`,
  byte-identical to the value recorded in
  `.openrecomp-phase2/evidence/P2-07/host_emitter_tests.json`.

## Synthetic runtime fixture

`.openrecomp-phase2/evidence/P2-08/sample_generated_runtime_host_call.c` is a
synthetic generated host fixture exercising the host-call boundary
(`li r1=6`, `li r2=7`, explicit `demo.mul` host call -> `r3`).
`synthetic_runtime_fixture.txt` records a deterministic `RuntimeState` scenario
(memory write/read, input snapshot, host call, frame, audio, deterministic RNG)
with its fingerprint. No copyrighted guest binary is used.

## Optional native compile/run

A native compiler is detected (never assumed). On this host `clang` was found;
the gate compiled the generated host-call fixture together with a hand-written
`or_rt_host_call` stub, executed it, and observed `42 0` (expected `42 0`). This
is a **bounded synthetic runtime execution proof**, **not** a guest/host
equivalence proof. If no compiler is available, the check is a documented
toolchain skip and the semantic gate still passes.

## Test totals

```text
python tools/test_runtime_abi_v1.py
OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests=169
```

Coverage includes: ABI version stability/parse/compatibility/document; runtime
construction and repeated-run identity; memory read/write, 8/16/32/64 widths,
endianness and per-access override, address-zero and end-of-memory boundaries,
out-of-bounds read/write, address overflow at `2^64` and `2^64-1`, invalid width,
invalid endianness, segment overlap/out-of-range, deterministic failure results;
unknown-service rejection, known synthetic dispatch, arity failure, handler
failure, argument/result preservation, service macro/numeric id; input
canonicalization and malformed-input rejection; frame/audio descriptor and
checksum determinism, payload-sensitive checksums and round-trip identity;
trap/failure latch and stable failure codes; config/ABI-config serialization;
no wall-clock/random/pid/environment dependency; no host-pointer mechanism; no
P2-09 build pipeline; and bounded P2-07 emitter integration including
undeclared-service, no-config, non-external and "does not broaden semantics"
fail-closed cases.

## Upstream regression totals

```text
OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests=169
OPENRECOMP_HOST_EMITTER_V1=PASS tests=106
OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
OPENRECOMP_CFG_V1=PASS tests=82
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
PASS source-integrity  verified 118 manifest entries
```

The two toolchain-gated Phase-1 gates (`e07-hardened-end-to-end`,
`external-repro-v1`) remain unexecutable on this host (missing `gcc`, `posix`)
and are never counted as pass.

## Source integrity

`PASS source-integrity  verified 118 manifest entries`. The only manifest change
is the additive `tools/test_runtime_abi_v1.py` entry; no existing hash changed.
`openrecomp/*.py` (including the new `runtime_abi.py` and the modified
`host_emitter.py`) remain outside `SOURCE_SHA256SUMS.txt` due to the pre-existing
`update_sums.py` glob gap (`schemas/` vs `schema/`); their hashes are recorded in
`changed_files.txt` and `RESULT.json`.

## Determinism hashes

- P2-08 gate stdout (two runs byte-identical):
  `sha256 3c0abaf52efa534b2dc639efceb15cd6e5aa17a4ec218d5515b1160f260809a8`
- RuntimeState scenario fingerprint:
  `308fad595e5215ea32cd0ebc540f6541f3db0d0d2e75d2374efd3d5a820a868b`
- `RuntimeAbiConfig(services=[demo.mul, demo.noop])` fingerprint:
  `fb9f90f2ea3fec568f29ad2a4939f9d90c73b45615ba0a9c5446371f15eb932a`
- Generated host-call fixture source fingerprint:
  `b75d7656517de8a75c5730fa22b7ea69dff9292be20a6f73d0bd49cf64705e24`

## Explicit confirmations

- architecture-neutral shared ABI: **confirmed** (no console register naming or
  console/Windows/POSIX/emulator/graphics/audio API in the shared contract).
- no unchecked guest -> host pointers: **confirmed** (bounded indices; immutable
  byte copies; overflow/width/endianness checked).
- unknown services fail closed: **confirmed** (`UNKNOWN_HOST_SERVICE`).
- no console-specific runtime implementation: **confirmed** (no BIOS/HLE, PPU/APU,
  kernel/XAPI, filesystem, GPU, controller backend, audio device or window).
- no P2-09 implementation: **confirmed** (no build/link/object pipeline).
- final Phase-2 proof not claimed: **confirmed**
  (`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF` remains unclaimed).

## Known limitations

- `RuntimeState` is a deterministic contract surface for fixtures, not a guest
  execution engine; it does not execute generated host code.
- The generated-C boundary is declarations only; no runtime implementation is
  generated (platform runtime integration is later work).
- The embedded/AHB-relative offsets and any platform memory mapping are adapter
  concerns outside the shared ABI.
- `schema/*.json` and `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt`
  (pre-existing `update_sums.py` glob gap).
- Toolchain-gated Phase-1 gates remain skipped on this host.
- The native compile/run proves only that a synthetic fixture compiles and
  returns one host-call result; it is not an equivalence proof.

## Boundary rule

No P2-08 git commit was created. The coherent P2-08 changes are left in the
working tree for independent review and boundary commit. P2-09 (Deterministic
build pipeline) was **not** started.

## Git status (short)

```text
 M SOURCE_SHA256SUMS.txt
 M openrecomp/host_emitter.py
?? .openrecomp-phase2/backups/
?? .openrecomp-phase2/evidence/P2-08/
?? artifacts/mips32_translation_evidence_closure_v1/
?? artifacts/mips32_translation_v1/
?? openrecomp/runtime_abi.py
?? tools/test_runtime_abi_v1.py
```

Current HEAD: `30b4321011b963efce19b321c72b97f886ba2b3d` (frozen P2-07 boundary).

## Final verdict

`PASS` — the first architecture-neutral Generic Runtime ABI is implemented and
validated: memory is bounds/width/endianness/overflow checked with no
guest-to-host pointer exposure; unknown host services fail closed; input, frame,
audio and failure contracts are generic rather than console-specific; runtime
state and serialization are deterministic and versioned; the P2-07 emitter
integration is bounded, explicit and evidence-backed; and every mandatory
upstream regression and source-integrity check passes.

OPENRECOMP_P2_08=PASS
OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests=169
