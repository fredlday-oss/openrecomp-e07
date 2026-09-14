# OpenRecomp Phase 2 Stage Queue

Only one stage may be active at a time.

| Stage | Name | Status | Required outcome |
|---|---|---|---|
| P2-00 | Baseline + control plane | COMPLETE | Verify Phase-1 freeze, inventory reusable infrastructure, no semantic change |
| P2-01 | Persistent program representation | COMPLETE | Versioned architecture-neutral program/function/block/instruction schema with deterministic serialization |
| P2-02 | Basic-block / CFG recovery | COMPLETE | Deterministic direct-control-flow block discovery; malformed/ambiguous cases fail closed |
| P2-03 | Function recovery | COMPLETE | Entry/function ownership model with explicit unknown/unresolved regions |
| P2-04 | Call-graph recovery | COMPLETE | Deterministic direct-call graph with internal/external/unresolved call classification; indirect targets never guessed |
| P2-05 | Translation-unit model | COMPLETE | One deterministic TranslationUnit per discovered function; stable host-independent units and dependencies; structural packaging only, no IR lowering |
| P2-06 | Indirect-control-flow classification | COMPLETE | Classify resolvable versus unresolved indirect sites without guessing targets |
| P2-07 | Host emitter V1 | COMPLETE | Deterministic generated host code for a bounded proven subset |
| P2-08 | Generic runtime ABI V1 | COMPLETE | Architecture-neutral CPU/memory/host-call/input/frame/audio/runtime contracts |
| P2-09 | Deterministic build pipeline | COMPLETE | Reproducible generated-source/object/executable metadata and hashing |
| P2-10 | Tiny MIPS32 end-to-end proof | COMPLETE | Synthetic/open MIPS32 guest → generated host executable → observable equivalence |
| P2-11 | MIPS32 calls/stack/memory | COMPLETE | Multiple functions, stack frames, loads/stores through end-to-end path |
| P2-12 | MIPS32 direct CFG stress | COMPLETE | Branches, loops, calls, returns, bounded switch/direct-table proof where evidence exists |
| P2-13 | Runtime-host boundary | NEXT | Deterministic host-call ABI; unsupported service handling fails closed |
| P2-14 | Larger MIPS32 open fixture | QUEUED | Larger synthetic/open program with deterministic recompilation and replay |
| P2-20 | NES6502 program bridge | QUEUED | Feed NES6502 through same persistent program and translation-unit layers |
| P2-21 | NES6502 host emitter path | QUEUED | Generated host code for proven 6502 semantics |
| P2-22 | NES runtime bridge | QUEUED | Generic runtime memory/input/frame/audio contracts connected to NES platform layer |
| P2-23 | NES end-to-end proof | QUEUED | Synthetic/open NROM fixture → host executable → deterministic observable equivalence |
| P2-30 | Cross-architecture neutrality audit | QUEUED | Prove shared P2 layers have no MIPS/NES platform leakage |
| P2-40 | Generic runtime integration audit | QUEUED | Prove backend neutrality; document GB/GBC/SMS and future RT64-like extension points |
| P2-50 | Build/package reproducibility | QUEUED | Clean-tree rebuild of generated outputs from committed inputs |
| P2-90 | Whole-project regression | QUEUED | Phase-1 + Phase-2 gates; deterministic proof reruns where practical |
| P2-91 | Evidence index + limitations | QUEUED | Complete index and explicit bounded/unproven claims |
| P2-99 | Final verdict | QUEUED | Issue final verdict only if all required stages pass |

## Queue reconciliation (control-plane only)

This queue originally described `P2-04 Direct CFG recovery`, `P2-05
Indirect-control-flow classification` and `P2-06 Translation-unit model`. The frozen
implementation history is:

1. `1b40269` P2-00 baseline intake
2. `a0c4830` P2-01 shared program model
3. `65386e4` P2-02 CFG construction
4. `aa263bb` P2-03 function discovery
5. `ea954d6` P2-04 call-graph recovery
6. `ce9cd4f` P2-05 translation units

P2-05 preserved unresolved indirect-call and indirect-jump evidence without inventing
targets but did not classify those sites, so the still-uncompleted
indirect-control-flow classification work is assigned to `P2-06`. This reassignment is a
**control-plane reconciliation caused by actual execution order**. It does not change the
semantics, claims or evidence of any frozen prior stage (`P2-00`..`P2-05`).
`P2-07` remains Host emitter V1. `P2-08` (Generic runtime ABI V1), `P2-09`
(Deterministic build pipeline), `P2-10` (Tiny MIPS32 end-to-end proof), `P2-11` (MIPS32
calls/stack/memory) and `P2-12` (MIPS32 direct CFG stress) are `COMPLETE`; `P2-13`
(Runtime-host boundary) is `NEXT`. `P2-13` was not started.

Success marker:

`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`

Otherwise:

`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN`
