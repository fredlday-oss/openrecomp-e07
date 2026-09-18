# OpenRecomp Phase 4 State

PHASE=4
BASELINE_TAG=openrecomp-phase3-pass
BASELINE_COMMIT=e16e4b29b90f379615f1af97e47747cd1d531796
BASELINE_TREE=a940f0d84a32adaf191f7ff2bebfb24cc855cde0
CURRENT_STAGE=P4-10
LAST_PASSED_STAGE=P4-09
STATUS=ACTIVE
GENERIC_RUNTIME_STATUS=NOT_PROVEN
FINAL_VERDICT=NOT_PROVEN
QUEUE_FREEZE=FROZEN
QUEUE_FREEZE_STAGES=P4-01..P4-99

## Phase-3 frozen boundary identities

- Tag `openrecomp-phase3-pass` (annotated, object
  `ac31524504b1b5cc63aabcfd5132a3eb4275e8e9`) resolves to commit
  `e16e4b29b90f379615f1af97e47747cd1d531796`, tree
  `a940f0d84a32adaf191f7ff2bebfb24cc855cde0`.
- Phase-3 terminal markers on the frozen tree:
  `OPENRECOMP_P3_99=PASS`,
  `OPENRECOMP_PHASE3_FINAL_VERDICT_V1=PASS tests=46`,
  `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=PASS`.
- Frozen integrity identities:
  - `SOURCE_SHA256SUMS.txt` sha256
    `76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095`
    (134 manifest entries)
  - `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` sha256
    `a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488`
    (24 manifest entries)
  - `.openrecomp-phase3/evidence/P3-99/RESULT.json` sha256
    `c893250b539cf1e82f368c09fe848f8f695ebece17f7735713c5367a3d93c1cf`
  - `tools/test_phase3_final_verdict_v1.py` sha256
    `ba5814902797d9848614e08b6bd655c00061dfb0d2dc90fec30da60382d558fa`
  - terminal P3-99 gate stdout: 2498 bytes, raw sha256
    `953ec70c312c7203022ba98f763aabf270409e2f39a9a7fa2ac90d887ae087bc`,
    LF sha256
    `4974d03fdd02ef76e1fa6506d230cd2c9be9e1cfe55bb9d5d4851f7525c72dd5`
  - CoreMark fixture ELF sha256
    `16a0a0aa0f62344d8c0f309b755450f09c330e7c5a7c355785662d7a141f7669`
    (31184 bytes)
- Phase-2 boundary `openrecomp-phase2-pass` =
  `01b1d7cba8c931fca95d041389cfb1902b7c89fe`; Phase-1 boundary
  `openrecomp-phase1-pass` = `46c2f971e1a42cf49bd936bad94697b81bf31002`.
- Documented untracked residue preserved from Phase 2/3:
  `.openrecomp-phase2/backups/`, `.openrecomp-phase2/scratch/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`, the 28 frozen
  verification-context files, the Phase-3 external source/toolchain/build
  sets, and the Phase-3 platform-line-ending captures recorded in the Phase-3
  control plane.

## Queue freeze record (P4-00 boundary)

- Frozen contract: `.openrecomp-phase4/STAGE_QUEUE.md` `## Queue freeze`, rows
  `P4-01` .. `P4-99` exactly as listed, effective before any P4-01
  implementation work.
- Rules (see the queue section): no renumber/insert/merge/split/silent
  redefinition; a change requires a genuine technical dependency, must fail
  closed with an explicit blocker record, and must be documented in the
  reconciliation log with the forcing evidence.
- No stage status changed at the freeze: `P4-01` .. `P4-99` stay `QUEUED`
  until their own gates pass.
- The freeze is a control-plane record only: no capability claim, no change to
  the frozen Phase-1/Phase-2/Phase-3 boundaries and no promotion of the
  Phase-4 terminal marker.

## Stage ledger

| ID | Stage | Status | Evidence |
| --- | --- | --- | --- |
| P4-00 | Phase-4 boundary | PASS | `.openrecomp-phase4/evidence/P4-00/` |
| P4-01 | Generic Runtime ABI V1 | PASS | `.openrecomp-phase4/evidence/P4-01/` |
| P4-02 | Guest memory/runtime model | PASS | `.openrecomp-phase4/evidence/P4-02/` |
| P4-03 | Runtime service mediation | PASS | `.openrecomp-phase4/evidence/P4-03/` |
| P4-04 | Deterministic I/O, timing and input | PASS | `.openrecomp-phase4/evidence/P4-04/` |
| P4-05 | Platform Adapter Interface V1 | PASS | `.openrecomp-phase4/evidence/P4-05/` |
| P4-06 | Graphics/audio abstraction boundary | PASS | `.openrecomp-phase4/evidence/P4-06/` |
| P4-07 | Interactive legally-clean fixture | PASS | `.openrecomp-phase4/evidence/P4-07/` |
| P4-08 | First platform-adapter execution proof | PASS | `.openrecomp-phase4/evidence/P4-08/` |
| P4-09 | End-to-end generic-runtime native proof | PASS | `.openrecomp-phase4/evidence/P4-09/` |
| P4-10 | Reproducible Phase-4 package | QUEUED | `.openrecomp-phase4/evidence/P4-10/` |
| P4-90 | Phase-4 whole regression audit | QUEUED | `.openrecomp-phase4/evidence/P4-90/` |
| P4-91 | Evidence index + limitations | QUEUED | `.openrecomp-phase4/evidence/P4-91/` |
| P4-99 | Final Phase-4 verdict | QUEUED | `.openrecomp-phase4/evidence/P4-99/` |

## P4-00 acceptance criteria

1. Phase-3 frozen tag `openrecomp-phase3-pass` (annotated) resolves to the
   recorded commit and tree, and the Phase-4 branch descends from that
   boundary (`merge-base` is the boundary commit).
2. Phase-3 final evidence is unchanged: the frozen integrity identities above
   re-verify on disk.
3. `python tools/test_phase3_final_verdict_v1.py` re-passes on this tree with
   exit code 0, empty stderr, the exact terminal markers and stdout
   byte-identical to the recorded official capture.
4. The Phase-4 control plane exists (STATE, HANDOFF, STAGE_QUEUE, SCOPE,
   CONTROL_POLICY, EVIDENCE_SCHEMA, evidence/) and is deterministic.
5. The frozen queue `P4-01` .. `P4-99` is complete and no new runtime
   capability is claimed: `GENERIC_RUNTIME_STATUS=NOT_PROVEN` and the
   terminal/general compatibility markers stay reserved as `NOT_PROVEN`.
6. The working tree has no unexpected untracked paths beyond the documented
   Phase-2/Phase-3 sets and the Phase-4 control plane itself.

## P4-05 stage-internal repair record (P4-06 boundary)

`bind_platform` (P4-05) merged every P4-04 deterministic-I/O handler into
the mediator unconditionally, so a platform adapter with a minimal service
profile failed to bind with `unknown runtime service` instead of binding
with only its declared interfaces. Found while binding the P4-06
graphics/audio boundary hooks. Repaired at the source on the Phase-4 branch
(handlers filtered to the bound registry's interfaces), the frozen P4-05
gate re-ran twice with byte-identical stdout and the same 76 checks, and the
affected P4-05 pins were refreshed (`determinism.json`, `changed_files.txt`,
`repair_record.json`, `repair_run1/2.txt`). No stage contract, queue row or
claim changed, and the historical Phase-3 tag is untouched.

## P4-09 result (PASS)

Stage: `P4-09` End-to-end generic-runtime native proof (frozen queue row).
Gate: `tools/test_phase4_generic_runtime_proof_v1.py` (55 checks, sha256
`6827d66856764d87631bbb0e6f673c9ff85d56c2f8b810d2f3e418782a35e3a1`).
Evidence: `.openrecomp-phase4/evidence/P4-09/`.

Markers issued:

- Stage marker: `OPENRECOMP_P4_09=PASS`
- Gate marker: `OPENRECOMP_PHASE4_END_TO_END_NATIVE_PROOF_V1=PASS tests=55`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

## Objective (frozen queue)

Demonstrate the bounded pipeline: fixture/input -> ingestion -> program
recovery -> translation -> host emission -> native build -> generic runtime ->
platform adapter -> deterministic execution. Verify the observable against an
independent reference/model where technically appropriate. No target or
behaviour may be guessed merely to achieve execution.

## Implementation (additive Phase-4 files only)

- `.openrecomp-phase4/src/p4_reference_fixture_v1.py`: an independently
  written ELF32 loader (program headers parsed directly), raw-word decoder and
  executor for the fixture instruction set with the delay-slot protocol, the
  four MMIO windows, the declared deterministic input plan and the
  one-tick-per-retired-instruction policy; it produces the P4-01 canonical
  observable (transcript, exit status, steps, PC, output and the FNV-1a 64
  state digest over the contract layout).
- `tools/test_phase4_generic_runtime_proof_v1.py`: the pipeline gate.
- `.openrecomp-phase4/SOURCE_SHA256SUMS.txt`: grown additively to 27 entries.

## Pipeline demonstration (each stage executed and recorded)

1. fixture/input: pinned fixture ELF `acb4f4e5...` and input plan
   `0512ab34ff`.
2. ingestion: frozen Phase-3 ingestion identity (ELF32 `EM_MIPS` `ET_EXEC`,
   O32, static, entry `0x1c00`, `.text` `0x1000`+3104); the independent
   loader agrees on entry and all four segment ranges.
3. program recovery: the frozen neutral structure layer recovers 774
   instructions, 142 blocks, 9 functions, 14 internal call edges with one
   recursive function (`fn_1010`), entry unit `tu_fn_1c00`, zero indirect
   sites and zero unresolved edges; fingerprints recorded.
4. translation / host emission: generated program `abd138ea...` and support
   `755a004630...` (P4-01-ABI compliant, verified in P4-08).
5. native build: `EXECUTABLE_REPRODUCIBLE`, executable `c966e185...`,
   deterministic manifest.
6. generic runtime / platform adapter: `BoundPlatform` fixture adapter with
   the declared memory map, generic service aliases and explicit negative
   compatibility claims; services driven fail-closed.
7. deterministic execution: three identical native replays with the exact
   transcript, `steps=6784`, `pc=0x1bf4`, `state_fnv1a64=0x5185479717fe4020`
   and no failure.

## Independent reference equivalence

The independent reference ran the same input plan twice with identical
documents and matched the native observable on every compared field:
transcript (all 11 lines including `ticks_start=19`/`ticks_end=6691`), exit
status 0, steps 6784, PC `0x1bf4`, no failure, output byte-identical and the
state digest `0x5185479717fe4020` (whose layout covers the image, all
registers, HI/LO, PC, steps, exit status and output). The reference also
fails closed on unsupported instructions, step-limit exhaustion, out-of-region
stores and unaligned indirect jumps.

## Determinism

- Two consecutive official gate runs: exit 0, empty stderr, stdout
  byte-identical raw (1815 bytes, `8ab7d3fa...`) and LF, and
  `p4_09_tests.json` byte-identical across both runs.
- Evidence: `official_runs.json`, `determinism.json`, `pipeline.json`,
  `equivalence.json`.

## Regressions

- P2-08 `PASS tests=169`; P4-01..P4-08 all PASS.
- `tools/phase1_host_gates_v1.py` `PASS=44 FAIL=0 SKIPPED=2`.
- `tools/public_safety_scan.py` `OPENRECOMP_PUBLIC_SAFETY=PASS`.
- P4-00 `PASS tests=74` (`953312d0...`) with the documented dynamic
  boundary-context hygiene.

## Limitations

- The proof is bounded to the audited fixture, profile and declared tick
  policy; it is not arbitrary MIPS32, console, game or commercial
  compatibility.
- The native runtime support is the concrete adapter implementation for this
  fixture; no universal runtime completeness is claimed.
- The reference covers exactly the fixture instruction set and fails closed
  otherwise; no target or behaviour was guessed to achieve execution.
- `GENERIC_RUNTIME_STATUS=NOT_PROVEN`; the terminal verdict remains reserved
  for P4-99.

## Next stage

P4-10 - Reproducible Phase-4 package.

## P4-08 result (PASS)

Stage: `OPENRECOMP_PHASE4_ADAPTER_EXECUTION_V1`. Evidence:
`.openrecomp-phase4/evidence/P4-08/`. Gate:
`tools/test_phase4_adapter_execution_v1.py` (73 checks, sha256
`7a2424747ee212542dd7123445040acbbb3fbd96f287c59512d4abda5349c4e0`).

Markers issued:

- Stage marker: `OPENRECOMP_P4_08=PASS`
- Gate marker: `OPENRECOMP_PHASE4_ADAPTER_EXECUTION_V1=PASS tests=73`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

Delivered (additive Phase-4 files only; frozen modules used read-only):

- `.openrecomp-phase4/src/p4_fixture_exec_v1.py`: fixture rebuild/pinned
  identity, region/image extraction, frozen decode-frontier analysis,
  architecture-neutral emission of every reachable word through the frozen
  instruction emitter, the declared fixture instance profile
  (`fixture.exit`=1, `fixture.in`=2, `fixture.out`=3, `fixture.ticks`=4) and
  the runtime support implementing checked memory, typed service dispatch,
  the deterministic input plan, bounded output, virtual ticks and the P4-01
  canonical observable.
- `tools/test_phase4_adapter_execution_v1.py`; Phase-4 manifest grown
  additively to 25 entries.

Verified: 774 reachable words emitted; reserved padding not emitted;
unsupported records fail closed at emission; generated program/support pass
the P4-01 ABI verifier against the fixture profile; deterministic
`EXECUTABLE_REPRODUCIBLE` build (program `abd138ea...`, support
`755a004630...`, executable `c966e185...`); three identical native replays
producing the exact P4-07-model transcript (`input_bytes=4`, `input_xor=136`,
`fib10=55`, `prime_count=16`, `primes_sum=381`, `bss_sum=4028012831`,
`heap_sum=3784880468`, `checksum=0xd43e5ba6`), pinned tick fields
(`ticks_start=19`, `ticks_end=6691`), `steps=6784`, `pc=0x1bf4`,
`state_fnv1a64=0x5185479717fe4020`, no failure; the `BoundPlatform` fixture
adapter (memory map, generic service aliases, recorded input, boundary hooks)
exposes the same declared service profile and mediates fail-closed
(post-exit and unknown services); tiny negative programs fail closed on an
unmapped store and on step-limit exhaustion.

Two official runs byte-identical raw (1779 bytes `4449d842...`, empty
stderr, exit 0) with `p4_08_tests.json` identical across runs.

Regressions: P2-08 `PASS tests=169`, P4-01..P4-07 all PASS, Phase-1 host
gates `PASS=44 FAIL=0 SKIPPED=2`, public safety `PASS`, P4-00
`PASS tests=74` (`953312d0...`) with the documented dynamic boundary-context
hygiene.

Limitations: the proof is bounded to the audited fixture and profile; the
native support is the concrete adapter/runtime implementation for this
fixture (not a universal runtime); tick values depend on the declared
one-tick-per-retired-instruction policy; independent-reference equivalence is
P4-09 scope; `GENERIC_RUNTIME_STATUS=NOT_PROVEN`.

## P4-07 result (PASS)

Stage: `OPENRECOMP_PHASE4_FIXTURE_V1`. Evidence:
`.openrecomp-phase4/evidence/P4-07/`. Gate:
`tools/test_phase4_fixture_v1.py` (48 checks, sha256 `964fdd89...`).

Markers issued:

- Stage marker: `OPENRECOMP_P4_07=PASS`
- Gate marker: `OPENRECOMP_PHASE4_FIXTURE_V1=PASS tests=48`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

Delivered (original Apache-2.0 fixture under `.openrecomp-phase4/fixture/`):

- Program: recursion, loops/branches, direct calls, const tables, initialised
  globals, zero-fill storage, stack window, bounded static bump arena,
  byte output/input, exit and virtual ticks windows, fixed-format transcript
  and a 32-bit FNV-1a-style checksum; deterministic input plan
  `0512ab34ff`.
- Gate: builds the fixture twice with the recorded `zig cc` 0.13.0 bounded
  flags and `zig ld.lld -m elf32ltsmip` (byte-identical 9884-byte ELF,
  sha256 `acb4f4e5...`), verifies provenance/license, ingests through the
  frozen Phase-3 ELF layer, and inventories the complete decode frontier.
- Frontier: 776 words; 774 reachable; reachable recognized-unsupported ops
  only `movn` (1) and `mul` (4) from the bounded P3-04 semantic class; no
  unknown encodings, no reachable invalid words, no indirect control flow and
  no unresolved successors.
- Preliminary model-derived transcript fields (to be independently confirmed
  by P4-09): `fib10=55`, `primes_sum=381`, `bss_sum=4028012831`,
  `heap_sum=3784880468`, `checksum=0xd43e5ba6`.

Two official runs byte-identical (1839 bytes raw `e7ece97b...`, empty
stderr, exit 0) with `p4_07_tests.json` identical across runs
(`65e8635a...`).

Regressions: P2-08 `PASS tests=169`, P4-01..P4-06 all PASS, Phase-1 host
gates `PASS=44 FAIL=0 SKIPPED=2`, public safety `PASS`, P4-00
`PASS tests=74` (`953312d0...`) with the documented dynamic
boundary-context hygiene.

Limitations: the fixture is not yet translated or executed (P4-08/P4-09
scope); the transcript mirror is model-derived, not independent; the fixture
deliberately stays inside the bounded proven frontier;
`GENERIC_RUNTIME_STATUS=NOT_PROVEN`.

## P4-06 result (PASS)

Stage: \OPENRECOMP_PHASE4_GRAPHICS_AUDIO_V1\. Evidence:
\.openrecomp-phase4/evidence/P4-06/\. Gate:
\	ools/test_phase4_graphics_audio_v1.py\ (72 checks, sha256 \c4b8698a...\).

Markers issued:

- Stage marker: \OPENRECOMP_P4_06=PASS- Gate marker: \OPENRECOMP_PHASE4_GRAPHICS_AUDIO_V1=PASS tests=72- Terminal marker (reserved): \OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN- General compatibility marker (never promoted):
  \OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN
Delivered (additive Phase-4 files only; the P4-05 repair is recorded above):

- \.openrecomp-phase4/src/p4_graphics_audio_v1.py\: graphics/audio
  capability declarations over the P2-08 neutral formats, adapter interfaces
  with fail-closed submission validation, deterministic headless reference
  boundaries with bounded presentation ledgers, accept-nothing null
  boundaries, P4-05 hook routing, and a contract document recording
  enderer_backend_mandatory: false\ / \udio_backend_mandatory: false\.
- \	ools/test_phase4_graphics_audio_v1.py\; Phase-4 manifest grown
  additively to sixteen entries.

Verified: capability validation and bounded ledgers with exact checksums,
fail-closed rejections for unsupported formats/dimensions/rates/capacity,
deterministic documents/fingerprints, hook routing through a bound platform
adapter, and no backend tokens or imports anywhere in the module. Two
official runs byte-identical (2783 bytes raw \d2a59e4a...\, empty stderr,
exit 0) with \p4_06_tests.json\ identical across runs (e7bd2d5...\).

Regressions: P2-08 \PASS tests=169\, P4-01 \PASS tests=156(\81c96314...\), P4-02 \PASS tests=113\ (cfc58f1...\), P4-03
\PASS tests=86\ (\cc2f73da...\), P4-04 \PASS tests=101(\e55ad6cb...\), P4-05 \PASS tests=76\ (\849af7fd...\, post-repair),
Phase-1 host gates \PASS=44 FAIL=0 SKIPPED=2\, public safety \PASS\,
P4-00 \PASS tests=74\ (\953312d0...\) with the refined boundary-context
hygiene (all modified tracked Phase-4 paths held out).

Limitations: contract and deterministic headless reference boundaries only;
no real renderer/audio backend is integrated or required; rendering/audio
correctness and device output are not claimed;
\GENERIC_RUNTIME_STATUS=NOT_PROVEN\.

## P4-05 result (PASS)

Stage: \OPENRECOMP_PHASE4_PLATFORM_ADAPTER_V1\. Evidence:
\.openrecomp-phase4/evidence/P4-05/\. Gate:
\	ools/test_phase4_platform_adapter_v1.py\ (76 checks, sha256 łf3130...\).

Markers issued:

- Stage marker: \OPENRECOMP_P4_05=PASS- Gate marker: \OPENRECOMP_PHASE4_PLATFORM_ADAPTER_V1=PASS tests=76- Terminal marker (reserved): \OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN- General compatibility marker (never promoted):
  \OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN
Delivered (additive Phase-4 files only; no frozen file modified; the
P4-01..P4-04 modules and catalogs are unchanged):

- \.openrecomp-phase4/src/p4_platform_adapter_v1.py\: \AdapterIdentity\,
  \MemoryMap\ (P4-02 region model), \TimingProfile\ (virtual only),
  \ServiceProfile\ restricted to the approved generic catalog with
  declarative aliases/handlers, optional graphics/audio \PlatformHooks  over the P2-08 frame/audio contracts, fail-closed
  \alidate_adapter\/\ind_platform\ composing the P4-02 memory model,
  P4-04 I/O runtime and P4-03 mediator into a \BoundPlatform\ with explicit
  capabilities and explicit negative compatibility claims.
- \	ools/test_phase4_platform_adapter_v1.py\; Phase-4 manifest grown
  additively to fourteen entries.

Verified: the contract contains no console/renderer/audio-backend names;
invalid identities, host timing, invalid memory maps and unbindable service
profiles fail closed; the synthetic reference adapter binds to the generic
layers, aliases raw output onto the generic stream interface, and records
\console_compatibility=false\/\rbitrary_binary_compatibility=false\.
Two official runs byte-identical (2631 bytes raw \849af7fd...\, empty
stderr, exit 0) with \p4_05_tests.json\ identical across runs
((e1bfb5...\).

Regressions: P2-08 \PASS tests=169\, P4-01 \PASS tests=156(\81c96314...\), P4-02 \PASS tests=113\ (cfc58f1...\), P4-03
\PASS tests=86\ (\cc2f73da...\), P4-04 \PASS tests=101(\e55ad6cb...\), Phase-1 host gates \PASS=44 FAIL=0 SKIPPED=2\, public
safety \PASS\, P4-00 \PASS tests=74\ (\953312d0...\) with the
documented boundary-context hygiene.

Limitations: V1 admits platform-specific behaviour only through the approved
generic interfaces (aliases/handlers); adapter-defined interface names are
rejected; only a synthetic reference adapter is exercised and no console
support is claimed; graphics/audio hook boundaries are P4-06 scope;
\GENERIC_RUNTIME_STATUS=NOT_PROVEN\.

## P4-04 result (PASS)

Stage: \OPENRECOMP_PHASE4_DETERMINISTIC_IO_V1\. Evidence:
\.openrecomp-phase4/evidence/P4-04/\. Gate:
\	ools/test_phase4_deterministic_io_v1.py\ (101 checks, sha256 Ǔd12b8...\).

Markers issued:

- Stage marker: \OPENRECOMP_P4_04=PASS- Gate marker: \OPENRECOMP_PHASE4_DETERMINISTIC_IO_V1=PASS tests=101- Terminal marker (reserved): \OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN- General compatibility marker (never promoted):
  \OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN
Delivered (additive Phase-4 files only; no frozen file modified; the P4-03
base catalog is unchanged):

- \.openrecomp-phase4/src/p4_deterministic_io_v1.py\: bounded deterministic
  console (explicit EOF/FAULT input policy), deterministic file-style buffers
  with no host filesystem access, a virtual clock advanced only by explicit
  ticks, a bounded virtual-tick event queue, an explicit \RecordedInput  snapshot with a stable fingerprint, an \IoRuntime\ binding them, a
  structural rejection of ambient host input (\mbient_input\ always fails
  closed), and typed/versioned \or.runtime.stream_read\,
  \or.runtime.clock_ticks\, \or.runtime.input_poll\ interfaces composed
  onto the unmodified P4-03 base catalog.
- \	ools/test_phase4_deterministic_io_v1.py\; Phase-4 manifest grown
  additively to twelve entries.

Verified: input/output capacity and exhaustion policies, virtual-only time,
deterministic event ordering and delivery, record-document stability and
sensitivity, the composed service registry, and the exact frozen Phase-3
output interaction (499 bytes from P3-08) replaying byte-identically through
the I/O-bound mediator. The module has no host clock/random/filesystem/
process capability. Two official runs byte-identical (3378 bytes raw
\e55ad6cb...\, empty stderr, exit 0) with \p4_04_tests.json\ identical
across runs (\d9624d2...\).

Regressions: P2-08 \PASS tests=169\, P4-01 \PASS tests=156(\81c96314...\), P4-02 \PASS tests=113\ (cfc58f1...\), P4-03
\PASS tests=86\ (\cc2f73da...\), Phase-1 host gates
\PASS=44 FAIL=0 SKIPPED=2\, public safety \PASS\, P4-00 \PASS tests=74(\953312d0...\) with the documented boundary-context hygiene.

Limitations: the I/O layer is not yet consumed by the frozen native path
(P4-08/P4-09 scope); input is limited to recorded console bytes and
virtual-tick event plans; host devices, wall-clock time and real filesystem
access are deliberately unsupported; \GENERIC_RUNTIME_STATUS=NOT_PROVEN\.

## P4-03 result (PASS)

Stage: \OPENRECOMP_PHASE4_RUNTIME_SERVICES_V1\. Evidence:
\.openrecomp-phase4/evidence/P4-03/\. Gate:
\	ools/test_phase4_runtime_services_v1.py\ (86 checks, sha256 \ea5f22d6...\).

Markers issued:

- Stage marker: \OPENRECOMP_P4_03=PASS- Gate marker: \OPENRECOMP_PHASE4_RUNTIME_SERVICES_V1=PASS tests=86- Terminal marker (reserved): \OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN- General compatibility marker (never promoted):
  \OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN
Delivered (additive Phase-4 files only; no frozen file modified):

- \.openrecomp-phase4/src/p4_runtime_services_v1.py\: architecture-neutral
  interface catalog (\or.runtime.exit\, \or.runtime.stream_write\),
  versioned \ServiceRegistry\, declarative \ServiceAlias\ mappings with
  bound arguments (the frozen instance handling becomes data), fail-closed
  \RuntimeServiceMediator\ (unknown/version/arity/typed/missing-handler/
  handler-failure codes, first-failure latch, explicit termination,
  deterministic call log), \AbiHostCallBridge\ for declared profile numeric
  ids, and a generic bounded byte sink.
- \	ools/test_phase4_runtime_services_v1.py\; Phase-4 manifest grown
  additively to ten entries.

Verified: all mediation failure modes return the exact stable codes; the
exact frozen external interaction from P3-08 evidence (499 output bytes plus
exit status 0) replays byte-identically through the generic mediator and
fails closed without the declared aliases; the generated source passes the
P4-01 verifier and can reach only declared service macros; the module has no
ambient host capability tokens. Two official runs byte-identical (3135 bytes
raw \cc2f73da...\, empty stderr, exit 0) with \p4_03_tests.json\ identical
across runs (\59e9879...\).

Regressions: P2-08 \PASS tests=169\, P4-01 \PASS tests=156(\81c96314...\), P4-02 \PASS tests=113\ (cfc58f1...\), Phase-1 host
gates \PASS=44 FAIL=0 SKIPPED=2\, public safety \PASS\, P4-00
\PASS tests=74\ (\953312d0...\) with the documented boundary-context
hygiene.

Limitations: the mediator is not yet the execution path of the frozen native
program (P4-08/P4-09 scope); the catalog covers control and byte-stream
interfaces only, with deterministic I/O/timing/input services reserved for
P4-04; \GENERIC_RUNTIME_STATUS=NOT_PROVEN\.

## P4-02 result (PASS)

Stage: \OPENRECOMP_PHASE4_GUEST_MEMORY_V1\. Evidence:
\.openrecomp-phase4/evidence/P4-02/\. Gate:
\	ools/test_phase4_guest_memory_v1.py\ (113 checks, sha256 \c015734...\).

Markers issued:

- Stage marker: \OPENRECOMP_P4_02=PASS- Gate marker: \OPENRECOMP_PHASE4_GUEST_MEMORY_V1=PASS tests=113- Terminal marker (reserved): \OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN- General compatibility marker (never promoted):
  \OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN
Delivered (additive Phase-4 files only; no frozen file modified):

- \.openrecomp-phase4/src/p4_guest_memory_v1.py\: explicit guest memory model
  with region kinds (code/rodata/data/bss/stack/heap), declared permissions,
  non-overlap/bounds/W^X validation, widths 8/16/32/64, explicit
  endianness, alignment policies (\llow\, equire-natural\),
  deterministic fail-closed fault kinds mapped totally to the P2-08/P4-01
  ABI failure codes, canonical state document/fingerprint, an
  \AbiMemoryService\ adapter and the pinned frozen Phase-3 instance adapter.
- \	ools/test_phase4_guest_memory_v1.py\; Phase-4 manifest grown additively
  to eight entries.

Verified: the frozen \g_image\ window (sha256 eecfc95...\, 65536 bytes)
and emitted four-region table parse exactly; the permissioned model regions
merge to exactly the emitted coverage; entry word, text/rodata/data reads,
BSS zero-fill, guest stack window inside BSS, and fail-closed writes to
headers/text/rodata are proven; widths/endianness/alignment/bounds/permission
faults are deterministic; fault-to-ABI-code mapping is total; differential
agreement with t.RuntimeMemory\ holds for allowed flat accesses. Two
official runs byte-identical (3855 bytes raw cfc58f1...\, empty stderr,
exit 0) with \p4_02_tests.json\ identical across runs (?f49e22...\).

Regressions: P2-08 \PASS tests=169\, P4-01 \PASS tests=156(\81c96314...\), Phase-1 host gates \PASS=44 FAIL=0 SKIPPED=2\, public
safety \PASS\, P4-00 \PASS tests=74\ (\953312d0...\) with the documented
boundary-context hygiene.

Limitations: the model is not yet the execution backing store of the runtime
(P4-08/P4-09 scope); permission/alignment faults map to
\MEMORY_OUT_OF_RANGE\ at the ABI boundary while the precise fault kind is
preserved in model evidence; \GENERIC_RUNTIME_STATUS=NOT_PROVEN\.

## P4-01 result (PASS)

Stage: \OPENRECOMP_PHASE4_RUNTIME_ABI_V1\. Evidence:
\.openrecomp-phase4/evidence/P4-01/\. Gate:
\	ools/test_phase4_runtime_abi_v1.py\ (156 checks, sha256 \9f2c996...\).

Markers issued:

- Stage marker: \OPENRECOMP_P4_01=PASS- Gate marker: \OPENRECOMP_PHASE4_RUNTIME_ABI_V1=PASS tests=156- Terminal marker (reserved): \OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN- General compatibility marker (never promoted):
  \OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN
Delivered (additive Phase-4 files only; no frozen file modified):

- \.openrecomp-phase4/src/p4_runtime_abi_v1.py\: executable
  architecture-neutral generated-code <-> runtime ABI V1 contract, reusing
  the frozen P2-08 \openrecomp.runtime_abi\ as the single source of truth
  for the ABI name/version, failure codes, widths, endianness and canonical
  sorted service numeric ids.
- \.openrecomp-phase4/contracts/generated_runtime_abi_v1.json\ (machine
  contract), \.openrecomp-phase4/ports/generated_runtime_abi_v1.h\ (C
  boundary header) and the declared instance profile
  \.openrecomp-phase4/ports/generated_runtime_abi_v1_profile_mips32_o32.json  (frozen Phase-3 instance: widths {8,16,32}, 32 registers, \hi\/\lo  aux accessors, services \p3.exit\=1 and \p3.uart_write\=2, pinned
  generated artifacts).
- \	ools/test_phase4_runtime_abi_v1.py\; Phase-4 manifest grown additively
  to six entries.

Verified: runtime entries (\or_rt_memory_read/write/host_call/
failure_reason\) and generated accessors (\openrecomp_*\) with exact
signatures; typed, versioned service descriptors; reserved core namespace
\or.runtime.*\ with a terminating \or.runtime.exit\; 14 P2-08 failure
codes with first-failure latching; fail-closed reference model semantics
(memory, arity, typed arguments, version, handler failure, termination,
entry-return fault, output capacity); deterministic observable state
(document + FNV-1a 64 digest, sensitive to every covered field); the frozen
\coremark_program.c\ ()99e2f0...\) and \coremark_support.c(\c5c69054...\) are compliant instances; negative sources are rejected;
the contract core surface has no fixture or platform tokens. Two official
runs byte-identical (6199 bytes raw \81c96314...\, empty stderr, exit 0)
with \p4_01_tests.json\ identical across runs (4da953d...\).

Regressions: P2-08 \PASS tests=169\, Phase-1 host gates
\PASS=44 FAIL=0 SKIPPED=2\, public safety \PASS\, P4-00 boundary
\PASS tests=74\ (byte-identical stdout \953312d0...\) re-run with the
documented frozen-gate boundary-context hygiene.

Limitations: the ABI is defined and verified but not yet implemented as a
new execution path; the fixture-specific service set is declared profile data
and is replaced by generic services in P4-03; no observable equivalence claim
is made; \GENERIC_RUNTIME_STATUS=NOT_PROVEN\.

## P4-00 result (PASS)

Stage: `OPENRECOMP_PHASE4_BOUNDARY_V1`. Evidence:
`.openrecomp-phase4/evidence/P4-00/`. Gate:
`tools/test_phase4_boundary_v1.py` (74 checks, sha256 `5be5c7d2...`).

Markers issued:

- Stage marker: `OPENRECOMP_P4_00=PASS`
- Gate marker: `OPENRECOMP_PHASE4_BOUNDARY_V1=PASS tests=74`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

Verified on branch `phase4/generic-runtime-v1` (commit
`e16e4b29b90f379615f1af97e47747cd1d531796`, the frozen Phase-3 boundary
commit):

- `openrecomp-phase3-pass` (annotated, object `ac315245...`) resolves to the
  recorded commit/tree; the branch descends from that boundary and the merge
  base is the boundary commit.
- Frozen Phase-3 evidence re-verified byte-for-byte on disk: root manifest
  `76f77bbc...` (134 entries), Phase-3 manifest `a7d0953c...` (24 entries),
  P3-99 `RESULT.json` `c893250b...`, P3-99 gate `ba581490...`, fixture
  `16a0a0aa...` (31184 bytes).
- `python tools/test_phase3_final_verdict_v1.py` independently re-passed in
  the reconstructed frozen Phase-3 verification context (temporary
  `phase3/p4-00-verification-context` branch at the same commit, untracked
  Phase-4 material held outside the worktree and restored, committed verdict
  record restored if a failed re-run overwrote it): exit 0, empty stderr,
  2498-byte stdout byte-identical to the frozen official capture (raw
  `953ec70c...`, LF `4974d03f...`), markers `OPENRECOMP_P3_99=PASS`,
  `OPENRECOMP_PHASE3_FINAL_VERDICT_V1=PASS tests=46`,
  `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=PASS`.
- Phase-4 control plane complete and deterministic; frozen queue
  `P4-01` .. `P4-99` complete and consistent with the ledger;
  `GENERIC_RUNTIME_STATUS=NOT_PROVEN`.
- Two consecutive official gate runs byte-identical raw and LF (3186 bytes,
  raw `953312d0...`, LF `03fa4c3a...`, empty stderr, exit 0) with the
  `p4_00_tests.json` artifact byte-identical across both runs
  (`1c86cebd...`).
- Worktree: only the documented Phase-2/Phase-3 untracked sets plus the
  Phase-4 control plane; the two refreshed Phase-3 evidence sidecars
  (`P3-00/p3_00_tests.json`, `P3-00/residue_manifest.txt`) are re-run
  artifacts deliberately left uncommitted.

Limitations are recorded in `.openrecomp-phase4/evidence/P4-00/RESULT.md`
(frozen-gate verification-context reconstruction; uncommitted re-run
sidecars; reserved terminal/compatibility markers).
