# OpenRecomp Phase 7 Stage Queue

Only one stage may be active at a time. The remaining queue (`P7-01` ..
`P7-99`) is frozen at the P7-00 `PASS` boundary; see `## Queue freeze` below.
The freeze is effective before any P7-01 implementation work.

| Stage | Name | Status | Required outcome |
|---|---|---|---|
| P7-00 | Phase-7 boundary | COMPLETE | Verify the exact frozen Phase-6 terminal boundary (commit/tree and the recorded absence of a Phase-6 terminal tag), re-run the Phase-6 final verdict gate deterministically in its reconstructed pre-verdict context, establish the Phase-7 control plane and freeze the Phase-7 queue rows `P7-01` .. `P7-99`. No new translation/control-flow capability claimed yet |
| P7-01 | TMNT frontier re-derivation | COMPLETE | Reproduce the Phase-6 private TMNT frontier from scratch with deterministic, byte-identical or equivalently deterministic classifications; confirm undocumented opcode `0x7C` at `0xC570`, unresolved `$E2` indirect sites `0x86E8`/`0x8956`/`0x8F3C` and the bank-window candidate frontier; prove no mapper blocker has returned. No translation changes in this stage |
| P7-02 | Undocumented opcode 0x7C classification | COMPLETE | Determine exactly what the `0x7C` byte represents in this binary/context from evidence (surrounding decoded instructions, CPU variant assumptions, control-flow context, independently structured reference research/tests, public documentation where legally and technically appropriate). Classify as `SUPPORTED_PROVEN`, `RECOGNIZED_UNSUPPORTED`, `DATA_NOT_CODE`, `UNREACHABLE`, `AMBIGUOUS` or another explicitly justified fail-closed category. No universal undocumented-opcode claim |
| P7-03 | Public undocumented-opcode proof fixture | COMPLETE | If P7-02 establishes a real instruction-semantics requirement, create an original Apache-2.0 public fixture exercising exactly that instruction/semantic form, implement the semantics additively and differential-verify against an independently structured oracle including edge cases, flags, addressing, memory effects and negative cases. If P7-02 proves the byte is data/unreachable/not an executable instruction, create an equivalent public proof fixture demonstrating the classification mechanism instead of adding false semantics |
| P7-04 | Bank-aware cartridge reachability model | COMPLETE | Model executable reachability across MMC1 PRG bank states, track fixed and switchable windows explicitly, associate code addresses with cartridge bank state where required, never merge different physical bank contents that share CPU address ranges, and fail closed when bank provenance is ambiguous |
| P7-05 | Bank-aware ProgramModel / CFG integration | QUEUED | Extend the neutral program representation only as needed to distinguish banked code identities, recover CFG/function/translation-unit structure without fabricating cross-bank edges, preserve architecture-neutral boundaries where possible, and include a public redistributable bank-switching fixture |
| P7-06 | Indirect jump evidence model | QUEUED | Build deterministic analysis for the three `$E2` indirect sites tracking pointer writes, reads, bank state, memory provenance and feasible target sets. Never guess targets. Represent `RESOLVED_EXACT`, `RESOLVED_FINITE_SET`, `UNRESOLVED` and `IMPOSSIBLE` as explicit states |
| P7-07 | Public indirect-control-flow proof fixture | QUEUED | Original Apache-2.0 fixture covering the supported indirect-resolution mechanism, exercising exact single target, multiple feasible targets if supported, the unresolved/fail-closed case and the relevant bank switching, with differential/reference verification |
| P7-08 | Translation frontier integration | QUEUED | Integrate proven P7-02..P7-07 results into the static recompilation pipeline, recompute the reachable/dead/unsupported frontier, emit host code only for proven executable paths, and keep unknown control flow fail closed |
| P7-09 | Native execution of public Phase-7 fixture | QUEUED | Build and run generated native host code exercising the newly proven instruction/classification behaviour, bank-aware control flow, indirect target resolution and runtime/platform interaction. No original guest execution |
| P7-10 | Independent reference equivalence | QUEUED | Compare generated native execution against independently structured reference execution over CPU state, RAM, mapper/bank state, PPU state where relevant, controller transcript, interrupt counts, indirect-control-flow transcript, translation/service transcript and bounded final state; require exact bounded equivalence |
| P7-11 | Private TMNT frontier run | QUEUED | Re-run TMNT using the new Phase-7 translation/control-flow support. Never copy ROM bytes; record only hashes, metadata and derived evidence. Determine whether the `0xC570` blocker disappears, the three `$E2` sites become resolved, the reachable bank-window frontier expands, translation completes, the generated native build becomes possible, or native execution is reached. TMNT playability is not required for Phase-7 PASS |
| P7-12 | Evidence-driven translation closure | QUEUED | Add ONLY translation/control-flow behaviour demonstrated necessary by P7-11. Do not add speculative platform behaviour. Every new semantic/control-flow capability requires deterministic independent verification. Allow a documented zero-delta PASS when no further translation behaviour is justified |
| P7-13 | Second private TMNT run | QUEUED | Re-run the complete pipeline, record the exact new frontier, whether native execution becomes reachable, and any meaningful interactive behaviour only as a private bounded observation; if platform behaviour becomes the blocker, classify it precisely for the next phase |
| P7-14 | Reusable bank-aware ROM-to-native workflow | QUEUED | Extend the Phase-6 workflow to support the proven Phase-7 bank-aware translation and control-flow mechanisms. Input: local ROM path. Output: inventory, compatibility classification, bank-aware frontier, indirect-control-flow classification, generated native source/build when supported, or an explicit fail-closed blocker. Never copy or package the source ROM |
| P7-90 | Whole regression | QUEUED | Re-run the required Phase-1 through Phase-7 gates from the audited tree, re-verify the frozen boundaries, require deterministic outputs, and modify no frozen history |
| P7-91 | Evidence index and compatibility matrix | QUEUED | Produce the complete PROVEN / BOUNDED / UNPROVEN / UNSUPPORTED / NOT TESTED ledger, keeping the Phase-5 NROM proof, the Phase-6 MMC1 proof, the Phase-7 translation/control-flow proof, the private TMNT observations and general NES compatibility separate; record all remaining limitations |
| P7-99 | Final Phase-7 verdict | QUEUED | Issue `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=PASS` only if the exact bounded public translation/control-flow claim is proven. Always retain `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`; TMNT playability remains `NOT_PROVEN` unless actual generated-native, meaningful interactive execution has been demonstrated. The general final verdict remains NOT_PROVEN for arbitrary/general compatibility |

## Queue freeze

Frozen at the P7-00 `PASS` boundary, before any P7-01 implementation work.
The rows `P7-01` .. `P7-99` above are the complete frozen contract: stage IDs,
names, ordering and required-outcome scope. The freeze does not change any
stage status: `P7-01` .. `P7-99` remain `QUEUED` until their own gates pass.

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
   changes no frozen Phase-1/Phase-2/Phase-3/Phase-4/Phase-5/Phase-6 boundary.

## Reconciliation log

- Phase-6 baseline tag (documented at P7-00): the mission baseline names an
  annotated tag `openrecomp-phase6-pass`, but the frozen Phase-6 P6-99 record
  states that no terminal tag was created or required by the Phase-6 control
  policy. The authoritative Phase-6 baseline is commit
  `1643817d43196c43155805249137e4b4e4a21eb1`, tree
  `cda3f535be43dc6f3d4b457d11d356ae39ea34af`, with terminal marker
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=PASS` (bounded public MMC1 claim
  only). No frozen artifact is created or modified; no tag is fabricated.
- Queue freeze (control-plane only, documented): the P7-00 `PASS` boundary
  froze rows `P7-01` .. `P7-99` exactly as written above. No stage was
  renumbered, inserted, merged, split or redefined by the freeze.

## Success markers

- queue freeze: rows `P7-01` .. `P7-99` are frozen by the `## Queue freeze`
  section above (P7-00 `PASS` boundary, control-plane record)
- `OPENRECOMP_P7_00=PASS`
- terminal Phase-7 marker: `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF` -
  reserved as `NOT_PROVEN` until P7-99 may issue `PASS` for the exact bounded
  public translation/control-flow claim only
- general NES compatibility marker (never promoted by Phase 7):
  `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`
- private TMNT playability marker (never promoted without actual
  generated-native meaningful interactive execution):
  `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN`

## Terminal state

- Reserved at P7-00: `OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN`
  until the P7-99 verdict.
- `OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN` is permanent for
  Phase 7: no general NES, mapper, board-revision, game, commercial-title,
  cycle-accuracy, full-PPU/APU or arbitrary-6502 compatibility is claimed at
  any Phase-7 stage.
- `OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN` is permanent unless actual
  generated-native meaningful interactive execution has been demonstrated and
  recorded as a private bounded observation.
