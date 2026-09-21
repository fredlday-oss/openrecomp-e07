# OpenRecomp Phase 10 Stage Queue

Only one stage may be active at a time. Rows `P10-01` .. `P10-99` are frozen at
the P10-00 `PASS` boundary, effective before any P10-01 implementation work.

| Stage | Name | Status | Required outcome |
|---|---|---|---|
| P10-00 | Phase-10 boundary + fixture/control plane | PASS | Verify the exact Phase-9 terminal commit/tree/evidence and Phase-1..9 frozen integrity, capture private executable/CUE/BIN identity and the CUE->BIN, ISO9660 and SYSTEM.CNF boot relationships, reproduce the inherited Hercules frontier (4068 reachable words, `break` at `0x80013390`, `CONTROL_WITHOUT_DELAY_SLOT`), capture toolchains, create the `.openrecomp-phase10` control plane/policies/schema/STATE/HANDOFF/queue and run two deterministic official gate runs. No substantive compatibility implementation |
| P10-01 | BREAK semantic classification | PASS | Classify the `break` at `0x80013390` exactly: encoding, reachable predecessor, architectural BREAK semantics, why Hercules reaches it, exception-vector expectation, continuation expectation and whether the path is genuinely required. Build independent public test evidence. Do not implement generic exception machinery merely to make the site pass; PASS means an exact evidence-supported classification and bounded handling strategy |
| P10-02 | CONTROL_WITHOUT_DELAY_SLOT reconciliation | PASS | Determine the exact cause (structure recovery, code ownership, TU construction, BREAK control semantics, unreachable/non-code bytes, control folding, or a genuinely missing reachable instruction) and resolve it without manufacturing a delay slot. Re-run the Hercules structure analysis and record the new exact frontier |
| P10-03 | Hercules CPU/control frontier iteration | PASS | Advance from the resolved starting blocker and repeatedly classify the next genuine reachable CPU/control-flow blocker until a stable new frontier is obtained. New CPU semantics require independent vectors, architecture-neutral implementation where possible, fail-closed negatives, and only reachable requirements |
| P10-04 | Hercules BIOS frontier | PASS | From the inherited 3 B0 candidates / 19 unknowns, classify the dynamically/reachably required Hercules BIOS calls, reuse the Phase-9 typed service boundary, implement only calls required to advance, and keep unknown calls fail-closed |
| P10-05 | Native execution entry | PASS | Generate and build Hercules-derived native host code (original MIPS machine code must not execute at runtime) and establish deterministic entry into translated game code. Record guest entry PC, initial registers, stack state, memory-image identity, translated control-flow trace identity, first host/service transition and termination/blocker category. Graphics/playability not required |
| P10-06 | Dynamic PS1 I/O discovery | PASS | Discover I/O-range accesses from actual reachable execution/reference behaviour and classify them into GPU, DMA, interrupt controller, timers, SIO/controller, SPU, CD-ROM, memory control and other PS1 MMIO. Do not implement complete devices speculatively |
| P10-07 | GPU command execution frontier | PASS | Advance Hercules through the first actually reachable GPU operations, reusing the Phase-9 GPU boundary, classifying required GP0/GP1 commands, DMA interactions and VRAM state required for progress, with deterministic GPU-command evidence/transcript. No complete GPU implementation unless demanded by reachable evidence |
| P10-08 | Interrupt / DMA / timing frontier | PASS | Implement the minimum proven Hercules requirements for interrupts, acknowledgement, DMA, timers, event progression and deterministic virtual time. Do not claim PS1 cycle accuracy; document timing abstractions explicitly |
| P10-09 | CUE/BIN CD-ROM + filesystem + streaming frontier | PASS | Use the discovered CUE as the authoritative private disc-image entry point, re-verify CUE/BIN/track/filesystem/SYSTEM.CNF identity, classify which Hercules behaviour requires ISO9660 access, sector reads, CD-ROM commands, overlays, resource loading, streaming, XA/audio or asynchronous CD events, and implement only reachable requirements. Never extract or commit proprietary assets, sectors or reconstructed disc data |
| P10-10 | SPU / controller / game-loop frontier | PASS | Advance actual required controller input, scripted deterministic input, SPU/audio interactions and frame/event loop behaviour. Audio output is not required unless its absence blocks execution; input evidence must be deterministic and replayable |
| P10-11 | Highest Hercules milestone | PASS | Attempt the strongest evidence-supported milestone (A..G), record the highest actually demonstrated, never fabricate progress and never infer playability from a screenshot alone. If G is reached, require deterministic scripted-input evidence demonstrating actual game-state progression. PASS means the achieved bounded milestone was rigorously established, not necessarily that G was reached |
| P10-12 | Hardening + reproducibility | PASS | Focused safety/negative tests for every Phase-10 mechanism: malformed inputs reject deterministically, unsupported BREAK/exception behaviour fails closed, unresolved control flow fails closed, unknown BIOS calls fail closed, unknown MMIO fails closed, stale cache rejected, changed disc/executable identity invalidates cached analysis, CUE/BIN material never enters evidence, no original guest machine code executes at runtime, clean native rebuild succeeds, repeated execution is deterministic and transcript/state identities repeat exactly |
| P10-90 | Whole-project regression | PASS | Re-run frozen Phase-1 through Phase-9 behaviour plus every completed Phase-10 official gate using documented historical reconstruction mechanisms where frozen gates require them, without weakening audit coverage. Capture exact gate count, exact test count, deterministic stdout hashes, stderr state and evidence sidecar identities |
| P10-91 | Evidence closure + proof matrix | PASS | Create the final Phase-10 evidence index and proof matrix separating PROVEN / BOUNDED / NOT_PROVEN / NOT_TESTED, recording exact private fixture identities, the exact highest Hercules milestone, native execution state and the CPU/BIOS/GPU/DMA-timing/CD-filesystem/SPU-input frontiers, deliberate exclusions and unresolved blockers. Verify all sidecar hashes, manifests, stage records, claim markers, no private bytes and no reconstructive commercial data |
| P10-99 | Final bounded verdict | PASS | Audit every Phase-10 stage; require required stages `PASS`, `P10-90` `PASS`, `P10-91` `PASS`, frozen history unchanged, fixture identities exact, evidence hashes valid, deterministic execution evidence and scope guards intact. Issue `OPENRECOMP_P10_99=PASS`; promote `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=PASS` only if translated/native Hercules execution was actually demonstrated, and `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=PASS` only if milestone G was explicitly and reproducibly demonstrated. Always retain `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` |

## Queue freeze

Frozen at the P10-00 `PASS` boundary, before any P10-01 implementation work.
The rows `P10-01` .. `P10-99` above are the complete frozen contract: stage IDs,
names, ordering and required-outcome scope. The freeze does not change any
stage status: each row becomes active only when its own gate is executed.

Frozen-queue rules:

1. No renumbering, insertion, merging, splitting or silent redefinition of a
   frozen stage is permitted.
2. A frozen stage may change only if a genuine technical dependency makes the
   existing frozen stage impossible to execute as written. Such a change must
   fail closed: the stage stops with an explicit
   `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` / `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN`
   / `QUEUE_RECONCILIATION_REQUIRED` record instead of silently adapting, the
   forcing evidence is captured, and the frozen rows are updated explicitly in
   the reconciliation log below.
3. A stage gate must not silently relax a frozen stage's required outcome.
4. The freeze is a control-plane record only. It adds no capability claim and
   changes no frozen Phase-1 through Phase-9 boundary.

## Reconciliation log

- Phase-9 baseline authority (documented at P10-00): the Phase-9 terminal
  boundary is commit `08c639d9032a364163f2985432744be420d402eb`, tree
  `900dccf06ce3d5df7b499a9f05a6ceea060114d7`, on branch
  `phase8/mips32-end-to-end-native-v1`. Phase 9 created no annotated terminal
  tag; none is fabricated. Phase 10 hosts its work on branch
  `phase10/ps1-commercial-game-native-v1` based exactly on that commit.
- Phase-6/Phase-7/Phase-8 reconciliations are inherited unchanged from
  `.openrecomp-phase9/STAGE_QUEUE.md`: the historical tag
  `openrecomp-phase6-pass` is absent (`ABSENT_RECONCILED`), the Phase-7
  annotated tag `openrecomp-phase7-pass` (object
  `b07e0f691262ed3ae0bc2fd6ebb3e3d3c5222800`, commit
  `2917aa6549ab975cffdeb50120514c1723f7e493`, tree
  `59529c130d759ceb1ca9e6c65a510fa373656b01`) is frozen and untouched, the
  `phase7/hardening-v2` line remains outside every baseline, and no Phase-8
  terminal tag exists.
- Documented pre-existing working-tree residue at the P10-00 boundary: tracked
  Phase-3 evidence files `.openrecomp-phase3/evidence/P3-00/p3_00_tests.json`
  and `.openrecomp-phase3/evidence/P3-00/residue_manifest.txt` are modified by
  a historical Phase-3 verification-context re-run, and untracked residue
  exists under `.openrecomp-phase2/`, `.openrecomp-phase3/`, `artifacts/` and
  `tools/test_build_package_reproducibility_v1.py`. This residue is preserved
  untouched, is excluded from every Phase-10 commit, and does not change any
  frozen Phase-1..9 committed evidence hash.
- No other reconciliation has been required.

## Success markers

- `OPENRECOMP_P10_00=PASS`
- reserved terminal marker (never promoted before P10-99):
  `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF`
- reserved playability marker (promotable only at P10-99 with milestone G):
  `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY`
- permanent general marker (never promoted):
  `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`
