# OpenRecomp Phase 2 Stage Queue

Only one stage may be active at a time.

| Stage | Name | Required outcome |
|---|---|---|
| P2-00 | Baseline + control plane | Verify Phase-1 freeze, inventory reusable infrastructure, no semantic change |
| P2-01 | Persistent program representation | Versioned architecture-neutral program/function/block/instruction schema with deterministic serialization |
| P2-02 | Basic-block recovery | Deterministic direct-control-flow block discovery; malformed/ambiguous cases fail closed |
| P2-03 | Function recovery | Entry/function ownership model with explicit unknown/unresolved regions |
| P2-04 | Direct CFG recovery | Deterministic fallthrough/branch/call/return edge model |
| P2-05 | Indirect-control-flow classification | Classify resolvable versus unresolved indirect sites without guessing targets |
| P2-06 | Translation-unit model | Stable host-independent units and dependencies |
| P2-07 | Host emitter V1 | Deterministic generated host code for a bounded proven subset |
| P2-08 | Generic runtime ABI V1 | Architecture-neutral CPU/memory/host-call/input/frame/audio/runtime contracts |
| P2-09 | Deterministic build pipeline | Reproducible generated-source/object/executable metadata and hashing |
| P2-10 | Tiny MIPS32 end-to-end proof | Synthetic/open MIPS32 guest → generated host executable → observable equivalence |
| P2-11 | MIPS32 calls/stack/memory | Multiple functions, stack frames, loads/stores through end-to-end path |
| P2-12 | MIPS32 direct CFG stress | Branches, loops, calls, returns, bounded switch/direct-table proof where evidence exists |
| P2-13 | Runtime-host boundary | Deterministic host-call ABI; unsupported service handling fails closed |
| P2-14 | Larger MIPS32 open fixture | Larger synthetic/open program with deterministic recompilation and replay |
| P2-20 | NES6502 program bridge | Feed NES6502 through same persistent program and translation-unit layers |
| P2-21 | NES6502 host emitter path | Generated host code for proven 6502 semantics |
| P2-22 | NES runtime bridge | Generic runtime memory/input/frame/audio contracts connected to NES platform layer |
| P2-23 | NES end-to-end proof | Synthetic/open NROM fixture → host executable → deterministic observable equivalence |
| P2-30 | Cross-architecture neutrality audit | Prove shared P2 layers have no MIPS/NES platform leakage |
| P2-40 | Generic runtime integration audit | Prove backend neutrality; document GB/GBC/SMS and future RT64-like extension points |
| P2-50 | Build/package reproducibility | Clean-tree rebuild of generated outputs from committed inputs |
| P2-90 | Whole-project regression | Phase-1 + Phase-2 gates; deterministic proof reruns where practical |
| P2-91 | Evidence index + limitations | Complete index and explicit bounded/unproven claims |
| P2-99 | Final verdict | Issue final verdict only if all required stages pass |

Success marker:

`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`

Otherwise:

`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN`
