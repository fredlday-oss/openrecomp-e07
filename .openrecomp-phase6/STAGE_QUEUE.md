# OpenRecomp Phase 6 Stage Queue

Only one stage may be active at a time. The remaining queue (`P6-01` ..
`P6-99`) is frozen at the P6-00 `PASS` boundary; see `## Queue freeze` below.
The freeze is effective before any P6-01 implementation work.

| Stage | Name | Status | Required outcome |
|---|---|---|---|
| P6-00 | Phase-6 boundary | COMPLETE | Verify the exact Phase-5 PASS boundary, rerun the Phase-5 final verdict deterministically, establish the Phase-6 control plane, public/private fixture separation and the frozen queue. No new MMC1 capability claimed yet |
| P6-01 | MMC1 requirements and fixture inventory | COMPLETE | Define the supported MMC1 subset. Inventory mapper 1 requirements. Establish an original Apache-2.0 public MMC1 fixture. Inventory the private TMNT image by metadata/hash only. Do not copy private ROM bytes |
| P6-02 | MMC1 serial register protocol | COMPLETE | Implement deterministic five-write shift-register semantics, reset-bit behaviour, register selection and the consecutive/write-edge behaviours required by the audited fixtures. Malformed/unsupported states fail closed. Differential tests against an independent reference |
| P6-03 | MMC1 PRG banking | COMPLETE | Implement the required 32 KiB and 16 KiB PRG modes, fixed-first/fixed-last behaviour and the bank masking required by the proven cartridge configuration. Exhaustive bounded reference vectors |
| P6-04 | MMC1 CHR banking and mirroring | COMPLETE | Implement required 8 KiB / 4 KiB CHR banking and one-screen lower/upper, vertical and horizontal mirroring as required. Differential PPU address-mapping verification |
| P6-05 | MMC1 PRG-RAM and variant boundary | QUEUED | Implement the PRG-RAM behaviour required by the supported fixture. Explicitly classify unsupported MMC1 board variants/features. Do not infer board wiring not proven by cartridge evidence |
| P6-06 | Public MMC1 proof fixture | QUEUED | Build the original Apache-2.0 MMC1 NES fixture deterministically. Record exact source revision, assembler/toolchain, ROM hash, PRG/CHR configuration, vectors and mapper metadata. Include bank switching, CHR switching, mirroring, input and graphics behaviour sufficient to exercise the supported MMC1 contract |
| P6-07 | MMC1 static-recompilation integration | QUEUED | Ingest the real public MMC1 fixture, recover reachable code, build ProgramModel/CFG/functions/translation units, and integrate the mapper service through the Phase-4/5 runtime contracts. No fabricated indirect targets or hardware behaviour |
| P6-08 | Native execution of public MMC1 fixture | QUEUED | Emit host-native code and execute through the generic runtime/platform adapter. Demonstrate meaningful deterministic behaviour involving bank switching, CPU, memory, PPU, input and timing. Never execute original 6502 guest code directly |
| P6-09 | Independent MMC1 reference equivalence | QUEUED | Run identical deterministic input plans through the generated native result and an independently structured reference implementation. Compare CPU state, RAM, mapper state, PRG/CHR bank state, mirroring, frame/state digest, input transcript, interrupt counts, services and bounded final state. Require exact equivalence for the bounded proof |
| P6-10 | Private TMNT compatibility run | QUEUED | Use only the existing private local TMNT path. Re-run the ingestion/frontier/translation/runtime pipeline now that MMC1 exists. Record only hashes, metadata, counts, addresses, classifications and stop reasons. Determine exactly what next blocks execution. TMNT playability is not required for Phase-6 PASS |
| P6-11 | Evidence-driven platform expansion | QUEUED | Add only PPU/APU/input/timing/runtime behaviour demonstrated necessary by the private compatibility evidence and/or the public proof fixture. Every addition requires an explicit deterministic reference test. No broad full-hardware implementation by assumption |
| P6-12 | Reusable ROM-to-native workflow | QUEUED | Provide one deterministic command/workflow that accepts a local ROM path, performs inventory and compatibility classification, statically recompiles supported binaries, generates native source/build artifacts, builds the native target and reports exact fail-closed blockers. Never package the source ROM. Unsupported mapper/hardware paths terminate with explicit reasons |
| P6-13 | Second private TMNT compatibility run | QUEUED | Re-run the complete local pipeline. Record whether generated native execution is reached. If interactive/playable behaviour occurs, record it as a private bounded observation only. If not, produce the exact remaining compatibility frontier |
| P6-90 | Whole regression | QUEUED | Re-run the required Phase-1, Phase-2, Phase-3, Phase-4, Phase-5 and Phase-6 gates from the audited tree. Preserve frozen historical evidence. Require deterministic outputs |
| P6-91 | Evidence index and compatibility matrix | QUEUED | Produce a complete PROVEN / BOUNDED / UNPROVEN / UNSUPPORTED / NOT TESTED ledger. Separate the public NROM proof, the public MMC1 proof, the private TMNT observations and general NES compatibility. Record every remaining limitation |
| P6-99 | Final Phase-6 verdict | QUEUED | Issue `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS` only if the exact audited public MMC1 static-recompilation claim is proven. Always retain `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`. A PASS must not imply all MMC1 boards/revisions, all NES games, commercial-game compatibility, cycle accuracy, full PPU/APU accuracy, FDS compatibility or arbitrary 6502 compatibility |

## Queue freeze

Frozen at the P6-00 `PASS` boundary, before any P6-01 implementation work.
The rows `P6-01` .. `P6-99` above are the complete frozen contract: stage IDs,
names, ordering and required-outcome scope. The freeze does not change any
stage status: `P6-01` .. `P6-99` remain `QUEUED` until their own gates pass.

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
   changes no frozen Phase-1/Phase-2/Phase-3/Phase-4/Phase-5 boundary.

## Reconciliation log

- Queue freeze (control-plane only, documented): the P6-00 `PASS` boundary
  froze rows `P6-01` .. `P6-99` exactly as written above. No stage was
  renumbered, inserted, merged, split or redefined by the freeze.

## Success markers

- queue freeze: rows `P6-01` .. `P6-99` are frozen by the `## Queue freeze`
  section above (P6-00 `PASS` boundary, control-plane record)
- `OPENRECOMP_P6_00=PASS`
- terminal Phase-6 marker: `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF` - reserved
  as `NOT_PROVEN` until P6-99 may issue `PASS` for the bounded audited public
  MMC1 claim only
- general NES compatibility marker (never promoted by Phase 6):
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`

## Terminal state

- Reserved at P6-00: `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN` until
  the P6-99 verdict.
- `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` is permanent for
  Phase 6: no general NES, mapper, board-revision, game, commercial-title,
  cycle-accuracy, full-PPU/APU or arbitrary-6502 compatibility is claimed at
  any Phase-6 stage.
