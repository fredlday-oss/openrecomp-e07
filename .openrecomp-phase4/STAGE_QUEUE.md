# OpenRecomp Phase 4 Stage Queue

Only one stage may be active at a time. The remaining queue (`P4-01` ..
`P4-99`) is frozen at the P4-00 `PASS` boundary; see `## Queue freeze` below.
The freeze is effective before any P4-01 implementation work.

| Stage | Name | Status | Required outcome |
|---|---|---|---|
| P4-00 | Phase-4 boundary | COMPLETE | Prove descent from the exact Phase-3 PASS boundary; independently rerun the Phase-3 final gate; establish deterministic Phase-4 control plane, scope, evidence schema and frozen stage queue. No new runtime capability claimed yet |
| P4-01 | Generic Runtime ABI V1 | COMPLETE | Define and verify an architecture-neutral generated-code <-> runtime ABI covering execution state, calls, returns/exits, faults, memory service boundaries, host/runtime services and deterministic observable state. No CoreMark-specific shortcuts in the ABI |
| P4-02 | Guest memory/runtime model | COMPLETE | Implement and verify explicit guest memory regions and access semantics including code/data/BSS/stack/heap where applicable, permissions, bounds, alignment, endian handling and deterministic fault behaviour. Invalid/unmapped accesses fail closed |
| P4-03 | Runtime service mediation | COMPLETE | Replace fixture-specific external handling with explicit typed/versioned runtime service interfaces. Unknown or unsupported services fail closed. Generated code must not silently call arbitrary host functionality |
| P4-04 | Deterministic I/O, timing and input | QUEUED | Provide reusable bounded interfaces for deterministic console/file-style I/O as required by the fixture, time/timers and input/event delivery. Host nondeterminism must be explicitly controlled, recorded or rejected |
| P4-05 | Platform Adapter Interface V1 | QUEUED | Define an architecture-neutral platform-adapter contract through which future platform-specific implementations can provide memory maps, services, timing, input, graphics/audio hooks or other platform behaviour without contaminating the recompiler core. Do NOT claim support for any console merely because the adapter interface exists |
| P4-06 | Graphics/audio abstraction boundary | QUEUED | Define reusable graphics and audio adapter boundaries suitable for later backend implementations. Do not make RT64, SDL, Vulkan, Direct3D or any particular renderer/audio system mandatory to the OpenRecomp core. Backend-specific integrations may be future adapters only unless explicitly required and proven by this phase |
| P4-07 | Interactive legally-clean fixture | QUEUED | Introduce or build a legally clean/open fixture materially more demanding than CoreMark and exercising a meaningful subset of code, static/global data, stack, heap if required, runtime services, deterministic input/events, timing and observable output. Record license, provenance, exact source/toolchain/build flags and hashes. Do not use proprietary ROMs, commercial game binaries, copyrighted game assets or unverified fixtures for the Phase-4 proof |
| P4-08 | First platform-adapter execution proof | QUEUED | Run the Phase-4 fixture through a real implementation of the new platform-adapter/runtime contracts, with generated code remaining architecture-neutral and unsupported behaviour failing closed |
| P4-09 | End-to-end generic-runtime native proof | QUEUED | Demonstrate the bounded pipeline: fixture/input -> ingestion -> program recovery -> translation -> host emission -> native build -> generic runtime -> platform adapter -> deterministic execution. Verify the observable against an independent reference/model where technically appropriate. No target or behaviour may be guessed merely to achieve execution |
| P4-10 | Reproducible Phase-4 package | QUEUED | Produce a clean byte-reproducible or explicitly reproducibility-bounded Phase-4 package containing all required source, generated artifacts, manifests, evidence and exact reproduction instructions. Verify from the audited tree |
| P4-90 | Phase-4 whole regression audit | QUEUED | Run the complete required Phase-1, Phase-2, Phase-3 and Phase-4 regression set from the audited Phase-4 tree. Frozen earlier proof boundaries must remain valid |
| P4-91 | Evidence index + limitations | QUEUED | Create a complete Phase-4 evidence index and explicit claim ledger separating: PROVEN, BOUNDED, UNPROVEN, UNSUPPORTED, NOT TESTED. Record every material limitation |
| P4-99 | Final Phase-4 verdict | QUEUED | Issue a Phase-4 PASS only if the exact bounded generic-runtime/platform claim is supported by the audited tree and evidence. A Phase-4 PASS MUST NOT silently imply: arbitrary binary compatibility; arbitrary MIPS32 compatibility; PS1/PS2/N64/PSP/etc compatibility; game compatibility; commercial-title compatibility; cycle accuracy; hardware emulation; universal runtime completeness |

## Queue freeze

Frozen at the P4-00 `PASS` boundary, before any P4-01 implementation work.
The rows `P4-01` .. `P4-99` above are the complete frozen contract: stage IDs,
names, ordering and required-outcome scope. The freeze does not change any
stage status: `P4-01` .. `P4-99` remain `QUEUED` until their own gates pass.

Frozen-queue rules:

1. No renumbering, insertion, merging, splitting or silent redefinition of a
   frozen stage is permitted.
2. A frozen stage may change only if a genuine technical dependency makes the
   existing frozen stage technically impossible to execute as written. Such a
   change must fail closed: the stage stops with an explicit
   `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` /
   `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN` record instead of silently
   adapting, the forcing evidence is captured, and the frozen rows are updated
   explicitly in the reconciliation log below.
3. A stage gate must not silently relax a frozen stage's required outcome; a
   gate that cannot satisfy the frozen contract fails closed.
4. The freeze is a control-plane record only. It adds no capability claim and
   changes no Phase-1/Phase-2/Phase-3 frozen boundary.

## Reconciliation log

- Queue freeze (control-plane only, documented): the P4-00 `PASS` boundary
  froze rows `P4-01` .. `P4-99` exactly as written above. No stage was
  renumbered, inserted, merged, split or redefined by the freeze.

## Success markers

- queue freeze: rows `P4-01` .. `P4-99` are frozen by the `## Queue freeze`
  section above (P4-00 `PASS` boundary, control-plane record)
- `OPENRECOMP_P4_00=PASS`
- `OPENRECOMP_PHASE4_BOUNDARY_V1=PASS tests=74`
- `OPENRECOMP_P4_01=PASS`
- `OPENRECOMP_PHASE4_RUNTIME_ABI_V1=PASS tests=156`
- `OPENRECOMP_P4_02=PASS`
- `OPENRECOMP_PHASE4_GUEST_MEMORY_V1=PASS tests=113`
- `OPENRECOMP_P4_03=PASS`
- `OPENRECOMP_PHASE4_RUNTIME_SERVICES_V1=PASS tests=86`
- terminal Phase-4 marker (reserved at P4-00 .. P4-91):
  `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- general compatibility marker (never promoted by Phase 4):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

## Terminal state

- Reserved until P4-99: `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`.
  P4-99 may issue `PASS` only for the exact bounded generic-runtime/platform
  claim recorded in `SCOPE.md`.
- `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN` is permanent for
  Phase 4: no console, game, commercial-title, arbitrary-binary or
  arbitrary-MIPS32 compatibility is claimed at any Phase-4 stage.
