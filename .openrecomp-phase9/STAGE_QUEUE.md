# OpenRecomp Phase 9 Stage Queue

Only one stage may be active at a time. Rows `P9-01` .. `P9-99` are frozen at
the P9-00 `PASS` boundary, effective before any P9-01 implementation work.

| Stage | Name | Status | Required outcome |
|---|---|---|---|
| P9-00 | Phase-9 boundary + acceleration control plane | PASS | Verify the exact Phase-8 terminal parent commit/tree/evidence, establish the `.openrecomp-phase9` control plane, policies, evidence schema, STATE, HANDOFF and fixed queue, capture toolchains, and run two deterministic official gate runs. No substantive PS1 implementation |
| P9-01 | PS-X EXE ingestion | PASS | Parse and validate the private SLUS_005.29 PS-X EXE. Record header fields, entry PC, GP, load address, payload size, memory requirements and SHA-256. Fail closed on malformed/unsupported PS-X EXE forms. Do not commit executable bytes |
| P9-02 | PS1 executable image + memory-map contract | PASS | Map the PS-X EXE payload into an explicit PS1 guest address-space model. Define RAM, stack, executable/data regions and access permissions. Classify any KSEG address handling explicitly. No silent address masking or invented mappings |
| P9-03 | Existing MIPS32 pipeline integration | PASS | Feed reachable executable code into the existing Phase-8 MIPS32 decode/ProgramModel/CFG/function/call-graph/TU stack. Reuse existing components rather than creating a second MIPS pipeline. Record instruction/block/function/call/control-flow counts. Fail closed on unresolved indirect control flow |
| P9-04 | Reachable translation-frontier closure | PASS | Classify every reachable instruction exactly once. Reuse Phase-8 semantics/emitter paths where valid. Add only semantics directly required and independently verified. Do not invent unsupported PS1/MIPS behaviour. Explicitly classify COP0/GTE or unusual MIPS-I forms if encountered |
| P9-05 | PS1 BIOS/service boundary | PASS | Discover reachable BIOS/system-service calls. Build an explicit typed/versioned service boundary. Implement only services required by the bounded fixture. Unknown BIOS calls fail closed |
| P9-06 | PS1 GPU/runtime boundary | PASS | Identify reachable GPU/GP0/GP1-facing behaviour. Create a clean platform adapter boundary. Do not attempt full GPU emulation unless evidence requires it. Unknown commands remain explicit unresolved blockers |
| P9-07 | Input/timer/event boundary | PASS | Classify controller, timer, event and interrupt requirements. Add deterministic virtual-time/input/event interfaces as required |
| P9-08 | SPU/audio boundary | PASS | Classify reachable audio/SPU interactions. Establish explicit audio service/runtime contract. Unsupported behaviour fails closed |
| P9-09 | CD-ROM/file-service boundary | PASS | Classify disc/file/streaming requirements reachable from the fixture. Implement only bounded required services. Keep disc-image bytes outside repository/evidence |
| P9-10 | Native build + deterministic execution | PASS | Emit native host code using the existing architecture-neutral path. Build reproducibly. Run repeatedly with byte-identical deterministic observables. Capture state/transcript/runtime counters |
| P9-11 | Private Hercules validation | PASS | Run the private SLUS_005.29 fixture through the complete bounded path. Record exact reachable frontier and first unresolved blocker if any. Private fixture success does NOT imply public/general compatibility. No proprietary bytes or reconstructive derived data committed |
| P9-12 | Hardening + reproducibility | PASS | Negative malformed-input tests. Cache/stale-evidence tests. Clean rebuild and repeated deterministic execution. Re-verify source/evidence manifests |
| P9-90 | Whole-project regression | QUEUED | Re-run applicable frozen Phase-1 through Phase-8 gates and all completed Phase-9 official gates. Preserve historical reconstruction mechanisms where required. Exact counts and deterministic evidence |
| P9-91 | Evidence closure + claim ledger | QUEUED | Verify all sidecar hashes, manifests, stage records and evidence indexes. Classify all Phase-9 claims as PROVEN / BOUNDED / NOT_PROVEN / NOT_TESTED |
| P9-99 | Final bounded verdict | QUEUED | Issue PASS only for the exact evidence-supported PS1 integration claim. Emit the terminal marker, the permanent general PS1 non-claim and the permanent Hercules playability non-claim; otherwise fail closed |

## Queue freeze

Frozen at the P9-00 `PASS` boundary, before any P9-01 implementation work.
The rows `P9-01` .. `P9-99` above are the complete frozen contract: stage IDs,
names, ordering and required-outcome scope. The freeze does not change any
stage status: each row becomes active only when its own gate is executed.

Frozen-queue rules:

1. No renumbering, insertion, merging, splitting or silent redefinition of a
   frozen stage is permitted.
2. A frozen stage may change only if a genuine technical dependency makes the
   existing frozen stage impossible to execute as written. Such a change must
   fail closed: the stage stops with an explicit
   `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` /
   `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN` / `QUEUE_RECONCILIATION_REQUIRED`
   record instead of silently adapting, the forcing evidence is captured, and
   the frozen rows are updated explicitly in the reconciliation log below.
3. A stage gate must not silently relax a frozen stage's required outcome.
4. The freeze is a control-plane record only. It adds no capability claim and
   changes no frozen Phase-1 through Phase-8 boundary.

## Reconciliation log

- Phase-8 baseline authority (documented at P9-00): Phase 8 created no
  annotated terminal tag. The authoritative Phase-8 terminal boundary is the
  P8-99 verdict commit `61136fc37cf0810e64241addd8f57a91872bc0af`, tree
  `f9262497b82fe0027c3b23432ba7bd8cbccdf433`, on branch
  `phase8/mips32-end-to-end-native-v1`. No tag is fabricated.
- Phase-6/Phase-7 reconciliation is inherited unchanged: the historical tag
  `openrecomp-phase6-pass` is absent (`ABSENT_RECONCILED`), and the Phase-7
  annotated tag `openrecomp-phase7-pass` (object
  `b07e0f691262ed3ae0bc2fd6ebb3e3d3c5222800`, commit
  `2917aa6549ab975cffdeb50120514c1723f7e493`, tree
  `59529c130d759ceb1ca9e6c65a510fa373656b01`) is frozen and untouched. The
  `phase7/hardening-v2` line remains outside every baseline.
- Queue freeze (control-plane only, documented): the P9-00 `PASS` boundary
  froze rows `P9-01` .. `P9-99` exactly as written above.
- No other reconciliation has been required.

## Success markers

- `OPENRECOMP_P9_00=PASS`
- terminal Phase-9 marker (reserved `NOT_PROVEN` at every stage before P9-99):
  `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF`
- permanent general marker (never promoted):
  `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`
- permanent private-fixture marker (never promoted):
  `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN`
- P9-99 verdict markers: `OPENRECOMP_P9_99=PASS` only with
  `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=PASS` for the exact audited
  bounded fixture/behaviour; otherwise `OPENRECOMP_P9_99=FAIL`,
  `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN`, and both
  permanent non-claims remain `NOT_PROVEN`.

## Terminal state

- Pending. No Phase-9 claim is issued before P9-99.
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` and
  `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` are permanent: no
  general PS1, BIOS, GPU/SPU/CD-ROM hardware, PS2, commercial-game,
  cycle-accuracy or cross-platform compatibility is claimed at any Phase-9
  stage or by the terminal verdict.
