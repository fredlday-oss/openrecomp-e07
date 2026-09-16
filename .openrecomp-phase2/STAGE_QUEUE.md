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
| P2-13 | Runtime-host boundary | COMPLETE | Deterministic host-call ABI; unsupported service handling fails closed |
| P2-14 | Larger MIPS32 open fixture | COMPLETE | Larger synthetic/open program with deterministic recompilation and replay |
| P2-20 | NES6502 program bridge | COMPLETE | Feed NES6502 through same persistent program and translation-unit layers |
| P2-21 | NES6502 host emitter path | COMPLETE | Generated host code for proven 6502 semantics |
| P2-22 | NES runtime bridge | COMPLETE | Generic runtime memory/input/frame/audio contracts connected to NES platform layer |
| P2-23 | NES end-to-end proof | COMPLETE | Synthetic/open NROM fixture → host executable → deterministic observable equivalence |
| P2-30 | Cross-architecture neutrality audit | COMPLETE | Prove shared P2 layers have no MIPS/NES platform leakage |
| P2-40 | Generic runtime integration audit | COMPLETE | Prove backend neutrality; document GB/GBC/SMS and future RT64-like extension points |
| P2-50 | Build/package reproducibility | COMPLETE | Clean-tree rebuild of generated outputs from committed inputs |
| P2-90 | Whole-project regression | COMPLETE | Phase-1 + Phase-2 gates; deterministic proof reruns where practical |
| P2-91 | Evidence index + limitations | COMPLETE | Complete index and explicit bounded/unproven claims |
| P2-99 | Final verdict | COMPLETE | Final verdict issued: `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` after all required stages passed |

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
calls/stack/memory), `P2-12` (MIPS32 direct CFG stress), `P2-13` (Runtime-host boundary),
`P2-14` (Larger MIPS32 open fixture), `P2-20` (NES6502 program bridge), `P2-21`
(NES6502 host emitter path), `P2-22` (NES runtime bridge) and `P2-23` (NES end-to-end
proof) are `COMPLETE`. `P2-22` and `P2-23` started and completed in one session; `P2-30`
(cross-architecture neutrality audit) and `P2-40` (generic runtime integration audit) are
`COMPLETE`. `P2-50` (build/package reproducibility) is `COMPLETE`; `P2-90`
(whole-project regression and evidence audit) is `COMPLETE` and passed with byte-identical
repeated audit output; `P2-91` (evidence index + limitations) is `COMPLETE` and passed with
the authoritative evidence index, limitations record, claim matrix, host-path resolution and
re-verified P2-90 regression; `P2-99` (final verdict) is `COMPLETE` and issued
`OPENRECOMP_P2_99=PASS` and `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` on the audited
terminal tree after the terminal whole-project regression re-run, the P2-91 closure re-run,
source integrity, the legal/content policy and the claim/limitation consistency all passed.
The marker is issued only for the bounded claim recorded in
`.openrecomp-phase2/evidence/P2-99/RESULT.md` and
`.openrecomp-phase2/evidence/P2-99/final_claim_boundary.md`; it does not imply arbitrary
NES ROM, MIPS32, commercial-game, complete-console, cycle-accurate, PS1/PS2/Xbox,
universal-console or future-architecture compatibility.

Success marker (issued):

`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`

Failure value (not issued):

`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN`
