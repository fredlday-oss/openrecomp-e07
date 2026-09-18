# OpenRecomp Phase 4 Handoff

STATUS: Phase 4 `ACTIVE` — P4-00 (Phase-4 boundary) `PASS`; P4-01 (Generic
Runtime ABI V1) `PASS`; P4-02 (Guest memory/runtime model) `PASS`; P4-03
(Runtime service mediation) `PASS`; P4-04 (Deterministic I/O, timing and
input) `PASS`; P4-05 (Platform Adapter Interface V1) `PASS` with a
stage-internal repair recorded in `STATE.md`; P4-06 (Graphics/audio
abstraction boundary) `PASS`; P4-07 (Interactive legally-clean fixture)
`PASS`; P4-08 (First platform-adapter execution proof) `PASS`; P4-09
(End-to-end generic-runtime native proof) `PASS`; P4-10 (Reproducible
Phase-4 package) `PASS`; P4-90 (Phase-4 whole regression audit) `PASS`;
P4-91 (Evidence index + limitations) is the executing stage. The frozen
Phase-4 queue (`P4-01` .. `P4-99`) is frozen by `.openrecomp-phase4/STAGE_QUEUE.md`
(`## Queue freeze`) at the P4-00 `PASS` boundary, before any P4-01
implementation work. Phase 3 is complete and frozen at annotated tag
`openrecomp-phase3-pass` (object
`ac31524504b1b5cc63aabcfd5132a3eb4275e8e9`) =
`e16e4b29b90f379615f1af97e47747cd1d531796`, tree
`a940f0d84a32adaf191f7ff2bebfb24cc855cde0`, with
`OPENRECOMP_P3_99=PASS`,
`OPENRECOMP_PHASE3_FINAL_VERDICT_V1=PASS tests=46` and
`OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=PASS` for the bounded audited claim.

Phase 4 objective (`NOT_PROVEN` until P4-99): make the bounded Phase-3
real-ELF recompilation path reusable as an architecture-neutral generic
runtime / platform layer with explicit generated-code <-> runtime,
guest-memory, runtime-service, deterministic-I/O/timing/input,
platform-adapter and graphics/audio-boundary contracts, and a materially more
demanding legally clean fixture executed end-to-end through the generic
runtime.

Reserved markers:

- `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN` (P4-99 may issue PASS
  for the bounded claim only)
- `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN` (never promoted)

## P4-90 outcome (PASS)

Markers: `OPENRECOMP_P4_90=PASS`,
`OPENRECOMP_PHASE4_WHOLE_REGRESSION_V1=PASS tests=78`; terminal and general
compatibility markers reserved as `NOT_PROVEN`.

- Frozen Phase-1/Phase-2/Phase-3 boundaries re-verified (tags, manifests,
  P3-99 identities, descent) and the committed P4-00/P4-08/P4-09/P4-10
  boundary records checked PASS with no failure.
- P4-00 re-ran under the dynamic frozen-boundary hygiene and reproduced
  `953312d0...`; its internal P3-99 re-run exercises the complete
  Phase-1/Phase-2/Phase-3 chain.
- All Phase-4 stage gates P4-01..P4-10 re-ran with empty stderr and
  byte-identical official stdout, including the native build, end-to-end
  execution and package rebuild.
- Two official audit runs byte-identical raw (`f7bd0e30...`) and LF, empty
  stderr, exit 0; `p4_90_tests.json` identical across runs.
- Gate hardening recorded: modified `tools/test_phase4_*` held out; binary-safe
  `git show` restore. Evidence: `.openrecomp-phase4/evidence/P4-90/`.

## P4-10 outcome (PASS)

Markers: `OPENRECOMP_P4_10=PASS`,
`OPENRECOMP_PHASE4_PACKAGE_REGRESSION_V1=PASS tests=71`; terminal and general
compatibility markers reserved as `NOT_PROVEN`.

- New files: `.openrecomp-phase4/src/p4_package_v1.py` (deterministic ZIP
  builder with fail-closed content policy and member manifest) and
  `tools/test_phase4_package_regression_v1.py`; the Phase-4 manifest grew
  additively to 29 entries.
- Package `phase4_package_v1.zip`: two builds byte-identical, member
  manifest verified, completeness checks for control plane, sources, gates,
  fixture, generated translation sources, evidence `P4-00`..`P4-09` and
  `REPRODUCE.md`.
- Bounded regressions pass (P2-08, P4-01..P4-07, host gates, public safety)
  and the committed P4-00/P4-08/P4-09 boundary records verify.
- Two official runs byte-identical raw (`8a9769d7...`) and LF, empty stderr,
  exit 0; `p4_10_tests.json` identical across runs.
- Evidence: `.openrecomp-phase4/evidence/P4-10/`; package at
  `.openrecomp-phase4/package/phase4_package_v1.zip`.

## P4-09 outcome (PASS)

Markers: `OPENRECOMP_P4_09=PASS`,
`OPENRECOMP_PHASE4_END_TO_END_NATIVE_PROOF_V1=PASS tests=55`; terminal and
general compatibility markers reserved as `NOT_PROVEN`.

- New files: `.openrecomp-phase4/src/p4_reference_fixture_v1.py` (independent
  loader/decoder/executor and canonical observable) and
  `tools/test_phase4_generic_runtime_proof_v1.py`; the Phase-4 manifest grew
  additively to 27 entries.
- The nine-stage pipeline is executed and recorded (fixture/input, ingestion,
  774-instruction/142-block/9-function recovery with no unresolved edges,
  translation `abd138ea...`, host emission, reproducible native build
  `c966e185...`, generic runtime, platform adapter, deterministic execution).
- The independent reference matches the native observable on every compared
  field, including `ticks_start=19`, `ticks_end=6691`, `steps=6784`,
  `pc=0x1bf4` and `state_fnv1a64=0x5185479717fe4020`, and fails closed on
  unsupported instructions, step limits, out-of-region stores and unaligned
  indirect jumps.
- Two official runs byte-identical raw (`8ab7d3fa...`) and LF, empty stderr,
  exit 0; `p4_09_tests.json` identical across runs.
- Regressions: P2-08 `PASS tests=169`, P4-01..P4-08 all PASS, Phase-1 host
  gates `PASS=44 FAIL=0 SKIPPED=2`, public safety `PASS`, P4-00
  `PASS tests=74` (`953312d0...`).
- Evidence: `.openrecomp-phase4/evidence/P4-09/`.

## P4-08 outcome (PASS)

Markers: `OPENRECOMP_P4_08=PASS`,
`OPENRECOMP_PHASE4_ADAPTER_EXECUTION_V1=PASS tests=73`; terminal and general
compatibility markers reserved as `NOT_PROVEN`.

- New files: `.openrecomp-phase4/src/p4_fixture_exec_v1.py` (fixture identity,
  decode-frontier analysis, architecture-neutral emission through the frozen
  instruction emitter, declared fixture instance profile, runtime support with
  checked memory, typed service dispatch, deterministic input/output and the
  P4-01 canonical observable) and `tools/test_phase4_adapter_execution_v1.py`;
  the Phase-4 manifest grew additively to 25 entries.
- Native execution of the translated fixture reproduces the model transcript
  exactly (`fib10=55`, `checksum=0xd43e5ba6`, `ticks_start=19`,
  `ticks_end=6691`, `steps=6784`, `pc=0x1bf4`,
  `state_fnv1a64=0x5185479717fe4020`), byte-reproducible executable
  `c966e185...`, and a `BoundPlatform` fixture adapter mediates the same
  declared services fail-closed; negative programs fail closed on unmapped
  stores and step-limit exhaustion.
- Two official runs byte-identical raw (`4449d842...`) and LF, empty stderr,
  exit 0; `p4_08_tests.json` identical across runs.
- Regressions: P2-08 `PASS tests=169`, P4-01..P4-07 all PASS, Phase-1 host
  gates `PASS=44 FAIL=0 SKIPPED=2`, public safety `PASS`, P4-00
  `PASS tests=74` (`953312d0...`).
- Evidence: `.openrecomp-phase4/evidence/P4-08/`.

## P4-07 outcome (PASS)

Markers: `OPENRECOMP_P4_07=PASS`,
`OPENRECOMP_PHASE4_FIXTURE_V1=PASS tests=48`; terminal and general
compatibility markers reserved as `NOT_PROVEN`.

- New original Apache-2.0 fixture under `.openrecomp-phase4/fixture/`
  (7 files) exercising code/data/bss/stack/heap-like arena, runtime
  service windows (output/input/exit/ticks), deterministic input plan
  `0512ab34ff` and an observable transcript.
- Reproducible build: `zig cc` 0.13.0 with the recorded bounded flags; two
  isolated roots produce a byte-identical 9884-byte ELF, sha256
  `acb4f4e5...`.
- Frontier inventory: 774 reachable words, no unknown/invalid encodings, no
  indirect control flow, reachable recognized-unsupported ops only `movn`
  (1) and `mul` (4) from the bounded P3-04 semantic class.
- Preliminary model-derived fields: `fib10=55`, `primes_sum=381`,
  `bss_sum=4028012831`, `heap_sum=3784880468`, `checksum=0xd43e5ba6`
  (tick fields remain policy-dependent; independent confirmation is P4-09).
- Two official runs byte-identical raw (`e7ece97b...`, 1839 bytes) and LF,
  empty stderr, exit 0; `p4_07_tests.json` identical across runs
  (`65e8635a...`).
- Regressions: P2-08 `PASS tests=169`, P4-01..P4-06 all PASS, Phase-1 host
  gates `PASS=44 FAIL=0 SKIPPED=2`, public safety `PASS`, P4-00
  `PASS tests=74` (`953312d0...`) with the dynamic boundary-context hygiene.
- Evidence: `.openrecomp-phase4/evidence/P4-07/`.

## P4-06 outcome (PASS)

Markers: `OPENRECOMP_P4_06=PASS`,
`OPENRECOMP_PHASE4_GRAPHICS_AUDIO_V1=PASS tests=72`; terminal and general
compatibility markers reserved as `NOT_PROVEN`.

- New files: `.openrecomp-phase4/src/p4_graphics_audio_v1.py` (graphics/audio
  capability declarations over the P2-08 neutral formats, adapter interfaces,
  deterministic headless reference boundaries with bounded ledgers,
  accept-nothing null boundaries, P4-05 hook routing, no-mandatory-backend
  contract claims) and `tools/test_phase4_graphics_audio_v1.py`; the Phase-4
  manifest grew additively to sixteen entries.
- P4-05 stage-internal repair (found by this stage): `bind_platform` handler
  merging fixed at the source; P4-05 gate re-ran twice with byte-identical
  stdout (`849af7fd...`), affected pins refreshed and recorded in
  `P4-05/repair_record.json`, `P4-05/RESULT.md` and `STATE.md`.
- P4-00 boundary hygiene refined to hold out every modified tracked Phase-4
  path; P4-00 re-passed byte-identically (`953312d0...`).
- Two official runs byte-identical raw (`d2a59e4a...`, 2783 bytes) and LF,
  empty stderr, exit 0; `p4_06_tests.json` identical across runs
  (`7e7bd2d5...`).
- Regressions: P2-08 `PASS tests=169`, P4-01..P4-05 all PASS
  (`81c96314...`, `5cfc58f1...`, `cc2f73da...`, `e55ad6cb...`,
  `849af7fd...`), Phase-1 host gates `PASS=44 FAIL=0 SKIPPED=2`, public
  safety `PASS`, P4-00 `PASS tests=74` (`953312d0...`).
- Evidence: `.openrecomp-phase4/evidence/P4-06/`.

## P4-05 outcome (PASS)

Markers: `OPENRECOMP_P4_05=PASS`,
`OPENRECOMP_PHASE4_PLATFORM_ADAPTER_V1=PASS tests=76`; terminal and general
compatibility markers reserved as `NOT_PROVEN`.

- New files: `.openrecomp-phase4/src/p4_platform_adapter_v1.py` (identity,
  memory map, virtual timing, generic-catalog-only service profile with
  aliases/handlers, optional graphics/audio hooks, fail-closed validation and
  binding composing P4-02/P4-03/P4-04 into a `BoundPlatform` with explicit
  capabilities and negative compatibility claims) and
  `tools/test_phase4_platform_adapter_v1.py`; the Phase-4 manifest grew
  additively to fourteen entries.
- The contract contains no console/renderer/audio-backend names; invalid
  adapters fail closed; the synthetic reference adapter binds and records
  `console_compatibility=false`/`arbitrary_binary_compatibility=false`.
- Two official runs byte-identical raw (`849af7fd...`, 2631 bytes) and LF,
  empty stderr, exit 0; `p4_05_tests.json` identical across runs
  (`50e1bfb5...`).
- Regressions: P2-08 `PASS tests=169`, P4-01 `PASS tests=156`
  (`81c96314...`), P4-02 `PASS tests=113` (`5cfc58f1...`), P4-03
  `PASS tests=86` (`cc2f73da...`), P4-04 `PASS tests=101` (`e55ad6cb...`),
  Phase-1 host gates `PASS=44 FAIL=0 SKIPPED=2`, public safety `PASS`,
  P4-00 `PASS tests=74` (`953312d0...`) with the documented boundary-context
  hygiene.
- Evidence: `.openrecomp-phase4/evidence/P4-05/`.

## P4-04 outcome (PASS)

Markers: `OPENRECOMP_P4_04=PASS`,
`OPENRECOMP_PHASE4_DETERMINISTIC_IO_V1=PASS tests=101`; terminal and general
compatibility markers reserved as `NOT_PROVEN`.

- New files: `.openrecomp-phase4/src/p4_deterministic_io_v1.py` (bounded
  deterministic console, file-style buffers, virtual clock, virtual-tick
  event queue, `RecordedInput` snapshot, `IoRuntime`, ambient-input
  rejection, and `or.runtime.stream_read`/`clock_ticks`/`input_poll`
  interfaces composed onto the unmodified P4-03 base catalog) and
  `tools/test_phase4_deterministic_io_v1.py`; the Phase-4 manifest grew
  additively to twelve entries.
- The exact frozen Phase-3 output interaction (499 bytes from P3-08) replays
  byte-identically through the I/O-bound mediator; no host
  clock/random/filesystem/process capability exists in the module.
- Two official runs byte-identical raw (`e55ad6cb...`, 3378 bytes) and LF,
  empty stderr, exit 0; `p4_04_tests.json` identical across runs
  (`ad9624d2...`).
- Regressions: P2-08 `PASS tests=169`, P4-01 `PASS tests=156`
  (`81c96314...`), P4-02 `PASS tests=113` (`5cfc58f1...`), P4-03
  `PASS tests=86` (`cc2f73da...`), Phase-1 host gates
  `PASS=44 FAIL=0 SKIPPED=2`, public safety `PASS`, P4-00 `PASS tests=74`
  (`953312d0...`) with the documented boundary-context hygiene.
- Evidence: `.openrecomp-phase4/evidence/P4-04/`.

## P4-03 outcome (PASS)

Markers: `OPENRECOMP_P4_03=PASS`,
`OPENRECOMP_PHASE4_RUNTIME_SERVICES_V1=PASS tests=86`; terminal and general
compatibility markers reserved as `NOT_PROVEN`.

- New files: `.openrecomp-phase4/src/p4_runtime_services_v1.py` (typed and
  versioned `or.runtime.*` interface catalog, registry, declarative aliases
  with bound arguments, fail-closed mediator with deterministic call log, ABI
  host-call bridge, bounded byte sink) and
  `tools/test_phase4_runtime_services_v1.py`; the Phase-4 manifest grew
  additively to ten entries.
- Frozen external handling replaced as data: `p3.exit -> or.runtime.exit`,
  `p3.uart_write -> or.runtime.stream_write` stream 0. The exact frozen
  P3-08 external interaction (499 output bytes + exit status 0) replays
  byte-identically through the generic mediator and fails closed without the
  declared aliases.
- Two official runs byte-identical raw (`cc2f73da...`, 3135 bytes) and LF,
  empty stderr, exit 0; `p4_03_tests.json` identical across runs
  (`f59e9879...`).
- Regressions: P2-08 `PASS tests=169`, P4-01 `PASS tests=156`
  (`81c96314...`), P4-02 `PASS tests=113` (`5cfc58f1...`), Phase-1 host gates
  `PASS=44 FAIL=0 SKIPPED=2`, public safety `PASS`, P4-00 `PASS tests=74`
  (`953312d0...`) with the documented boundary-context hygiene.
- Evidence: `.openrecomp-phase4/evidence/P4-03/`.

## P4-02 outcome (PASS)

Markers: `OPENRECOMP_P4_02=PASS`,
`OPENRECOMP_PHASE4_GUEST_MEMORY_V1=PASS tests=113`; terminal and general
compatibility markers reserved as `NOT_PROVEN`.

- New files: `.openrecomp-phase4/src/p4_guest_memory_v1.py` (explicit region
  model with permissions, W^X, bounds, widths 8/16/32/64, endianness,
  alignment policy, deterministic fault kinds mapped to the ABI codes,
  `AbiMemoryService` adapter and the pinned frozen Phase-3 instance adapter)
  and `tools/test_phase4_guest_memory_v1.py`; the Phase-4 manifest grew
  additively to eight entries.
- Frozen instance verified: `g_image` `3eecfc95...` (65536 bytes), emitted
  four-region table reproduced exactly, model coverage merges to the emitted
  ranges, entry/text/rodata/data reads and BSS zero-fill proven, writes to
  headers/text/rodata fail closed, guest stack window inside BSS exercised.
- Two official runs byte-identical raw (`5cfc58f1...`, 3855 bytes) and LF,
  empty stderr, exit 0; `p4_02_tests.json` identical across runs
  (`77f49e22...`).
- Regressions: P2-08 `PASS tests=169`, P4-01 `PASS tests=156`
  (`81c96314...`), Phase-1 host gates `PASS=44 FAIL=0 SKIPPED=2`, public
  safety `PASS`, P4-00 `PASS tests=74` (`953312d0...`) with the documented
  boundary-context hygiene.
- Evidence: `.openrecomp-phase4/evidence/P4-02/`.

## P4-01 outcome (PASS)

Markers: `OPENRECOMP_P4_01=PASS`,
`OPENRECOMP_PHASE4_RUNTIME_ABI_V1=PASS tests=156`; terminal and general
compatibility markers reserved as `NOT_PROVEN`.

- New files: `.openrecomp-phase4/src/p4_runtime_abi_v1.py` (executable
  generated-code <-> runtime ABI V1 contract, extending the frozen P2-08
  `openrecomp.runtime_abi`), deterministic
  `.openrecomp-phase4/contracts/generated_runtime_abi_v1.json`,
  `.openrecomp-phase4/ports/generated_runtime_abi_v1.h`, the declared
  instance profile
  `.openrecomp-phase4/ports/generated_runtime_abi_v1_profile_mips32_o32.json`,
  and `tools/test_phase4_runtime_abi_v1.py`; the Phase-4 manifest grew
  additively to six entries.
- The contract covers execution state, calls, returns/exits, faults, memory
  service boundaries, typed/versioned services and deterministic observable
  state; the frozen Phase-3 generated instance is verified compliant
  (`coremark_program.c` `5199e2f0...`, `coremark_support.c` `c5c69054...`);
  negative sources are rejected; the core surface has no fixture/platform
  tokens.
- Two official runs byte-identical raw (`81c96314...`, 6199 bytes) and LF,
  empty stderr, exit 0; `p4_01_tests.json` identical across runs
  (`64da953d...`).
- Regressions: P2-08 `PASS tests=169`, Phase-1 host gates
  `PASS=44 FAIL=0 SKIPPED=2`, public safety `PASS`, P4-00 boundary
  `PASS tests=74` with byte-identical stdout (`953312d0...`) using the
  documented frozen-gate boundary-context hygiene
  (`evidence/P4-01/regression_hygiene.json`).
- Evidence: `.openrecomp-phase4/evidence/P4-01/`.

## P4-00 outcome (PASS)

Markers: `OPENRECOMP_P4_00=PASS`,
`OPENRECOMP_PHASE4_BOUNDARY_V1=PASS tests=74`; terminal and general
compatibility markers reserved as `NOT_PROVEN`.

- Branch `phase4/generic-runtime-v1` descends from the frozen Phase-3 boundary
  commit `e16e4b2...`; tag object `ac315245...`, tree `a940f0d8...`.
- The frozen P3-99 final-verdict gate independently re-passed with
  byte-identical stdout (raw `953ec70c...`, LF `4974d03f...`, exit 0, empty
  stderr) in the reconstructed Phase-3 verification context (temporary
  `phase3/p4-00-verification-context` branch; untracked Phase-4 material held
  outside the worktree and restored; committed verdict record preserved).
  Frozen evidence unchanged: root manifest `76f77bbc...` (134), Phase-3
  manifest `a7d0953c...` (24), P3-99 `RESULT.json` `c893250b...`, gate
  `ba581490...`, fixture `16a0a0aa...`.
- Two consecutive official gate runs of
  `tools/test_phase4_boundary_v1.py` (74 checks, sha256 `5be5c7d2...`)
  byte-identical raw and LF (3186 bytes, raw `953312d0...`, empty stderr,
  exit 0) with `p4_00_tests.json` byte-identical across runs
  (`1c86cebd...`).
- Frozen queue `P4-01` .. `P4-99` recorded and consistent with the STATE
  ledger; `GENERIC_RUNTIME_STATUS=NOT_PROVEN`; no runtime capability claimed.
- Re-run artifacts deliberately left uncommitted:
  `.openrecomp-phase3/evidence/P3-00/p3_00_tests.json` (commit count 12 -> 13)
  and `.openrecomp-phase3/evidence/P3-00/residue_manifest.txt` (rebuilt
  binary hashes). The committed Phase-3 evidence is unchanged.
- Evidence: `.openrecomp-phase4/evidence/P4-00/`
  (`RESULT.md`, `p4_00_tests.json`, `official_runs.json`, `determinism.json`,
  `p3_99_reverify_stdout.txt`, `control_plane_manifest.txt`,
  `changed_files.txt`, `run1.txt`/`run2.txt` and empty stderr captures).

## Frozen boundary identities

- Phase-3 tag object: `ac31524504b1b5cc63aabcfd5132a3eb4275e8e9`
- Phase-3 commit: `e16e4b29b90f379615f1af97e47747cd1d531796`
- Phase-3 tree: `a940f0d84a32adaf191f7ff2bebfb24cc855cde0`
- Phase-3 source manifest sha256: `a7d0953c...` (24 entries)
- Root source manifest sha256: `76f77bbc...` (134 entries, frozen)
- P3-99 RESULT.json sha256: `c893250b...`
- P3-99 gate sha256: `ba581490...`
- P3-99 official stdout: 2498 bytes, raw `953ec70c...`, LF `4974d03f...`
- Phase-2 boundary: `openrecomp-phase2-pass` =
  `01b1d7cba8c931fca95d041389cfb1902b7c89fe`
- Phase-1 boundary: `openrecomp-phase1-pass` =
  `46c2f971e1a42cf49bd936bad94697b81bf31002`

## Exact next action

Execute P4-91 (Evidence index + limitations): create the complete Phase-4
evidence index and the explicit claim ledger separating PROVEN, BOUNDED,
UNPROVEN, UNSUPPORTED and NOT TESTED, recording every material limitation.
Then P4-99 (final verdict).

## Constraints

Do not modify, rewrite or mutate the frozen Phase-1/Phase-2/Phase-3 evidence,
gates, control planes, verdicts, histories or tags. Do not treat CoreMark as a
supported target. Do not commit proprietary ROM/BIOS/firmware/SDK material or
console assets. Backends (RT64/SDL/Vulkan/Direct3D) are never mandatory to the
core.
