# PHASE2_EVIDENCE_INDEX

Authoritative Phase-2 evidence index (P2-91 closure).

Scope: every completed Phase-2 stage from the frozen Phase-1 boundary
(`openrecomp-phase1-pass` at `46c2f971e1a42cf49bd936bad94697b81bf31002`) through
the P2-90 whole-project regression. Stage markers, gate markers and check counts
in this index are canonical: they are re-verified against the frozen per-stage
evidence and the P2-90 audit tables by
`tools/test_phase2_evidence_closure_v1.py`.

The final Phase-2 verdict marker
`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF` was issued as
`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` by the P2-99 terminal verdict
on the audited terminal tree; the stage rows below are the frozen per-stage
records that the verdict re-verified, and none of them individually claimed the
marker at stage time.

## Summary

| Stage | Name | Stage marker | Gate marker | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| P2-00 | Baseline + control plane | `OPENRECOMP_P2_00=PASS` | n/a (baseline; Phase-1 host gates) | n/a | `.openrecomp-phase2/evidence/P2-00/` |
| P2-01 | Shared program model V1 | `OPENRECOMP_P2_01=PASS` | `OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49` | 49 | `.openrecomp-phase2/evidence/P2-01/` |
| P2-02 | CFG construction V1 | `OPENRECOMP_P2_02=PASS` | `OPENRECOMP_CFG_V1=PASS tests=82` | 82 | `.openrecomp-phase2/evidence/P2-02/` |
| P2-03 | Function discovery V1 | `OPENRECOMP_P2_03=PASS` | `OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67` | 67 | `.openrecomp-phase2/evidence/P2-03/` |
| P2-04 | Call-graph recovery V1 | `OPENRECOMP_P2_04=PASS` | `OPENRECOMP_CALL_GRAPH_V1=PASS tests=61` | 61 | `.openrecomp-phase2/evidence/P2-04/` |
| P2-05 | Translation units V1 | `OPENRECOMP_P2_05=PASS` | `OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104` | 104 | `.openrecomp-phase2/evidence/P2-05/` |
| P2-06 | Indirect-control-flow classification V1 | `OPENRECOMP_P2_06=PASS` | `OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134` | 134 | `.openrecomp-phase2/evidence/P2-06/` |
| P2-07 | Host emitter V1 | `OPENRECOMP_P2_07=PASS` | `OPENRECOMP_HOST_EMITTER_V1=PASS tests=106` | 106 | `.openrecomp-phase2/evidence/P2-07/` |
| P2-08 | Generic runtime ABI V1 | `OPENRECOMP_P2_08=PASS` | `OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests=169` | 169 | `.openrecomp-phase2/evidence/P2-08/` |
| P2-09 | Deterministic build pipeline | `OPENRECOMP_P2_09=PASS` | `OPENRECOMP_DETERMINISTIC_BUILD_V1=PASS tests=120` | 120 | `.openrecomp-phase2/evidence/P2-09/` |
| P2-10 | Tiny MIPS32 end-to-end proof | `OPENRECOMP_P2_10=PASS` | `OPENRECOMP_MIPS32_END_TO_END_V1=PASS tests=108` | 108 | `.openrecomp-phase2/evidence/P2-10/` |
| P2-11 | MIPS32 calls/stack/memory | `OPENRECOMP_P2_11=PASS` | `OPENRECOMP_MIPS32_CALLS_MEMORY_V1=PASS tests=77` | 77 | `.openrecomp-phase2/evidence/P2-11/` |
| P2-12 | MIPS32 direct CFG stress | `OPENRECOMP_P2_12=PASS` | `OPENRECOMP_MIPS32_DIRECT_CFG_V1=PASS tests=96` | 96 | `.openrecomp-phase2/evidence/P2-12/` |
| P2-13 | Runtime-host boundary | `OPENRECOMP_P2_13=PASS` | `OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1=PASS tests=80` | 80 | `.openrecomp-phase2/evidence/P2-13/` |
| P2-14 | Larger MIPS32 open fixture | `OPENRECOMP_P2_14=PASS` | `OPENRECOMP_MIPS32_LARGER_FIXTURE_V1=PASS tests=82` | 82 | `.openrecomp-phase2/evidence/P2-14/` |
| P2-20 | NES6502 program bridge | `OPENRECOMP_P2_20=PASS` | `OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1=PASS tests=86` | 86 | `.openrecomp-phase2/evidence/P2-20/` |
| P2-21 | NES6502 host emitter path | `OPENRECOMP_P2_21=PASS` | `OPENRECOMP_NES6502_HOST_EMITTER_V1=PASS tests=74` | 74 | `.openrecomp-phase2/evidence/P2-21/` |
| P2-22 | NES runtime bridge | `OPENRECOMP_P2_22=PASS` | `OPENRECOMP_NES_RUNTIME_BRIDGE_V1=PASS tests=66` | 66 | `.openrecomp-phase2/evidence/P2-22/` |
| P2-23 | NES end-to-end proof | `OPENRECOMP_P2_23=PASS` | `OPENRECOMP_NES_END_TO_END_V1=PASS tests=50` | 50 | `.openrecomp-phase2/evidence/P2-23/` |
| P2-30 | Cross-architecture neutrality audit | `OPENRECOMP_P2_30=PASS` | `OPENRECOMP_CROSS_ARCHITECTURE_NEUTRALITY_V1=PASS tests=14` | 14 | `.openrecomp-phase2/evidence/P2-30/` |
| P2-40 | Generic runtime integration audit | `OPENRECOMP_P2_40=PASS` | `OPENRECOMP_GENERIC_RUNTIME_INTEGRATION_V1=PASS tests=181` | 181 | `.openrecomp-phase2/evidence/P2-40/` |
| P2-50 | Build/package reproducibility | `OPENRECOMP_P2_50=PASS` | `OPENRECOMP_BUILD_PACKAGE_REPRODUCIBILITY_V1=PASS tests=174` | 174 | `.openrecomp-phase2/evidence/P2-50/` |
| P2-90 | Whole-project regression | `OPENRECOMP_P2_90=PASS` | `OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1=PASS tests=361 gates=22 gate_tests=1990` | 361 | `.openrecomp-phase2/evidence/P2-90/` |

## Stage detail

### P2-00 — Baseline + control plane
- PASS marker: `OPENRECOMP_P2_00=PASS`
- Gate marker: `n/a (baseline stage; Phase-1 host gates 44 PASS / 0 FAIL / 2 SKIPPED over 46 inventoried gates)`
- Test/check count: `n/a`
- Evidence directory: `.openrecomp-phase2/evidence/P2-00/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-00/RESULT.md`
- Fixture/input identity: n/a (no guest fixture; baseline of the frozen Phase-1 tag `openrecomp-phase1-pass` at `46c2f971e1a42cf49bd936bad94697b81bf31002`)
- Generated/executable/package identity: n/a (no generated artifacts); recorded host-gates JSON `dc063ef0a3ab0bce4eb98a3ba82ba53be10ba8fcf286629ceaf7f5e9f6ba6d68`
- Deterministic-run identity: host-gates JSON sha256 `dc063ef0a3ab0bce4eb98a3ba82ba53be10ba8fcf286629ceaf7f5e9f6ba6d68`; Phase-1 host gates `PASS=44 FAIL=0 SKIPPED=2`
- Claim boundary: baseline verification of the Phase-1 freeze and inventory of reusable infrastructure only; no semantic change and no Phase-2 behavior.

### P2-01 — Shared program model V1
- PASS marker: `OPENRECOMP_P2_01=PASS`
- Gate marker: `OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49`
- Test/check count: `49`
- Evidence directory: `.openrecomp-phase2/evidence/P2-01/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-01/RESULT.md`
- Fixture/input identity: synthetic/original in-gate models (`linear64`, `nes-branch`, `nes-call`, `unresolved`); sample artifact `sample_nes_call.program.json`
- Generated/executable/package identity: n/a (structural model stage; no host emission, no build)
- Deterministic-run identity: gate stdout sha256 `c52847e67a35e8890bc1e9e2c7c474e2e8dfe7bce567190018b459fb8645b9df` (two byte-identical runs)
- Claim boundary: versioned architecture-neutral program/function/block/instruction representation with canonical serialization and PROVEN/CANDIDATE provenance only; no CFG recovery, no IR lowering and no host execution.

### P2-02 — CFG construction V1
- PASS marker: `OPENRECOMP_P2_02=PASS`
- Gate marker: `OPENRECOMP_CFG_V1=PASS tests=82`
- Test/check count: `82`
- Evidence directory: `.openrecomp-phase2/evidence/P2-02/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-02/RESULT.md`
- Fixture/input identity: synthetic/original in-gate instruction models; sample artifact `sample_cfg.json`
- Generated/executable/package identity: n/a (structural stage; no generated host code or executable)
- Deterministic-run identity: gate stdout sha256 `483df98e4ecb6a64441d22692ddcd54777ec52956dc041dae44242cb32886e70` (two byte-identical runs)
- Claim boundary: deterministic basic-block and CFG construction over the P2-01 model; no function recovery, no call-graph reconstruction and no execution.

### P2-03 — Function discovery V1
- PASS marker: `OPENRECOMP_P2_03=PASS`
- Gate marker: `OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67`
- Test/check count: `67`
- Evidence directory: `.openrecomp-phase2/evidence/P2-03/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-03/RESULT.md`
- Fixture/input identity: synthetic/original in-gate CFG models; sample artifact `sample_functions.discovery.json`
- Generated/executable/package identity: n/a (structural stage)
- Deterministic-run identity: gate stdout sha256 `05218d8d1db991e2ff93679340490d59dcea24add7c3c8d2faee0bf26cbe39a8` (two byte-identical runs)
- Claim boundary: entry/ownership partition with explicit unknown/unresolved regions and shared-block evidence; no call-graph recovery and no semantic proof of guest functions.

### P2-04 — Call-graph recovery V1
- PASS marker: `OPENRECOMP_P2_04=PASS`
- Gate marker: `OPENRECOMP_CALL_GRAPH_V1=PASS tests=61`
- Test/check count: `61`
- Evidence directory: `.openrecomp-phase2/evidence/P2-04/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-04/RESULT.md`
- Fixture/input identity: synthetic/original in-gate function/CFG models; sample artifact `sample_call_graph.json`
- Generated/executable/package identity: n/a (structural stage)
- Deterministic-run identity: gate stdout sha256 `ee4602245dfad5301385b958826dca112c0b600d7e418a37954d39172ea9b374` (two byte-identical runs)
- Claim boundary: direct-call graph only; unresolved `jalr`/indirect sites are preserved separately and no indirect target is guessed; not ABI recovery.

### P2-05 — Translation units V1
- PASS marker: `OPENRECOMP_P2_05=PASS`
- Gate marker: `OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104`
- Test/check count: `104`
- Evidence directory: `.openrecomp-phase2/evidence/P2-05/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-05/RESULT.md`
- Fixture/input identity: synthetic/original in-gate models; test record `translation_units_tests.json`; no guest binary
- Generated/executable/package identity: n/a (structural packaging only; no IR lowering)
- Deterministic-run identity: gate stdout sha256 `7209c6ff6bc40d131af0e04eae3c48d48d785ce864de46d0e406d81dbdbbc24a` (two byte-identical runs; canonical round-trip byte identity)
- Claim boundary: exactly one deterministic translation unit per discovered function with structural dependencies and residual evidence; no IR, no host code.

### P2-06 — Indirect-control-flow classification V1
- PASS marker: `OPENRECOMP_P2_06=PASS`
- Gate marker: `OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134`
- Test/check count: `134`
- Evidence directory: `.openrecomp-phase2/evidence/P2-06/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-06/RESULT.md`
- Fixture/input identity: synthetic/original in-gate classification models; test record `indirect_control_flow_tests.json`
- Generated/executable/package identity: n/a (classification stage; no emission)
- Deterministic-run identity: gate stdout sha256 `866d290a59228e5bd01f5bc026d2a2b1ca5558e28e9165b2dea42e00464d72a2` (two byte-identical runs)
- Claim boundary: classification of already-observed indirect sites only; targets are never recovered or guessed, bounded candidate sets are never promoted, and unowned control flow stays residual evidence.

### P2-07 — Host emitter V1
- PASS marker: `OPENRECOMP_P2_07=PASS`
- Gate marker: `OPENRECOMP_HOST_EMITTER_V1=PASS tests=106`
- Test/check count: `106`
- Evidence directory: `.openrecomp-phase2/evidence/P2-07/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-07/RESULT.md`
- Fixture/input identity: synthetic/original in-gate 8-bit fixtures; sample emitted sources `sample_generated_arith.c`, `sample_generated_branch.c`, `sample_generated_call.c`, `sample_generated_resolved_call_set.c`, `sample_generated_unresolved_boundary.c`
- Generated/executable/package identity: sample host C only (no committed executable); native smoke test observed `44 0`
- Deterministic-run identity: gate stdout sha256 `fb6e6e2c6ba660a5c3df75602a59c0501bf86ca53e0371e4942c0c76108c45d5` (two byte-identical runs)
- Claim boundary: deterministic portable host C for the bounded rule-proven semantic subset only; unsupported ops/sites fail closed; no runtime ABI and no guest execution.

### P2-08 — Generic runtime ABI V1
- PASS marker: `OPENRECOMP_P2_08=PASS`
- Gate marker: `OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests=169`
- Test/check count: `169`
- Evidence directory: `.openrecomp-phase2/evidence/P2-08/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-08/RESULT.md`
- Fixture/input identity: synthetic/original fixture `synthetic_runtime_fixture.txt` sha256 `c6ec839d4ba876f6eace922c6f5f51e06342bb204a6dbb8b6b7088ffb9aa97d2`; sample emitted source `sample_generated_runtime_host_call.c` sha256 `b75d7656517de8a75c5730fa22b7ea69dff9292be20a6f73d0bd49cf64705e24`
- Generated/executable/package identity: sample host C only; native smoke test observed `42 0`
- Deterministic-run identity: gate stdout sha256 `3c0abaf52efa534b2dc639efceb15cd6e5aa17a4ec218d5515b1160f260809a8` (two byte-identical runs)
- Claim boundary: versioned architecture-neutral runtime ABI contracts and a bounded host-call seam only; no runtime implementation, no console API and no guest execution engine.

### P2-09 — Deterministic build pipeline
- PASS marker: `OPENRECOMP_P2_09=PASS`
- Gate marker: `OPENRECOMP_DETERMINISTIC_BUILD_V1=PASS tests=120`
- Test/check count: `120`
- Evidence directory: `.openrecomp-phase2/evidence/P2-09/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-09/RESULT.md`
- Fixture/input identity: synthetic/original in-gate generated fixture; build manifest schema `openrecomp-build-manifest-v1`
- Generated/executable/package identity: generated source `generated.c` sha256 `b75d7656517de8a75c5730fa22b7ea69dff9292be20a6f73d0bd49cf64705e24`; executable `program.exe` sha256 `de03764e429a6e31d46037c72cd08db126fab18f2838b037b8ecee7deea81368`; manifest sha256 `22d8fd9bac9bca61c8f2920b6274a6076a518e59082e5f7965cee1dad348df77`
- Deterministic-run identity: gate stdout sha256 `db055b5cd622a7ef188901ef8da65898e2dac0cacb03c0ee2fb6caeec5b3e273`; classification `EXECUTABLE_REPRODUCIBLE` (COFF `TimeDateStamp=0`)
- Claim boundary: reproducibility is demonstrated for the detected `clang-cl`/`lld-link` 22.1.8 toolchain on this host for bounded synthetic fixtures only; other toolchains are classified honestly and not claimed.

### P2-10 — Tiny MIPS32 end-to-end proof
- PASS marker: `OPENRECOMP_P2_10=PASS`
- Gate marker: `OPENRECOMP_MIPS32_END_TO_END_V1=PASS tests=108`
- Test/check count: `108`
- Evidence directory: `.openrecomp-phase2/evidence/P2-10/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-10/RESULT.md`
- Fixture/input identity: synthetic/original 13-instruction MIPS32 fixture (52 bytes) sha256 `b33b597c28eb7f7239ee5079728c7f3e447387d4ed34525c445cf8c1e9234975`
- Generated/executable/package identity: generated source sha256 `8570ea4a11321118a3fff270e0dc9756d2a4ee7a52421ece1d2d892384118fbb`; executable `program.exe` sha256 `f94c95d2e86fca83f56e5e87a98bccaa1e2a4ced3fd9222aef29608592810f4e`
- Deterministic-run identity: P2-90-audited gate stdout sha256 `82378376b952c9c396fcf5f95a389348bff5ba444f2d8dbb3aa86776d0774560`; two independent `/Brepro` builds byte-identical; stage-time hash `5327f11c...` is historical (superseded by the documented cross-stage guard replacement)
- Claim boundary: one bounded synthetic MIPS32 fixture through the shared pipeline with observable equality on the declared observable set; no general MIPS32 support.

### P2-11 — MIPS32 calls/stack/memory
- PASS marker: `OPENRECOMP_P2_11=PASS`
- Gate marker: `OPENRECOMP_MIPS32_CALLS_MEMORY_V1=PASS tests=77`
- Test/check count: `77`
- Evidence directory: `.openrecomp-phase2/evidence/P2-11/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-11/RESULT.md`
- Fixture/input identity: synthetic/original 16-instruction MIPS32 fixture (64 bytes) sha256 `4ce3fdab7f9e622648eb74eff676fd79712c2043b8e35e752e84e26712e6d309`
- Generated/executable/package identity: generated source sha256 `4637ba676e99ba74e0c1708f100ba81b9506f1689fbee3d736364a6f821ceaf3`; executable `program.exe` sha256 `bd719060f38793a349271358e121730206f0799d67bd771c1a8ca6a31eba27c6`
- Deterministic-run identity: P2-90-audited gate stdout sha256 `d16107cd1740220f6f187856fcb9e04f7416ab1c003dbed01c89a72c5d6dd4c1`; two independent `/Brepro` builds byte-identical; stage-time hash `c0b39d65...` is historical (documented cross-stage guard replacement)
- Claim boundary: bounded multi-function fixture with an o32-style `$ra` save/restore and word-aligned `lw`/`sw` through the generic memory boundary only; general `$ra` dataflow and other load/store widths are not recovered.

### P2-12 — MIPS32 direct CFG stress
- PASS marker: `OPENRECOMP_P2_12=PASS`
- Gate marker: `OPENRECOMP_MIPS32_DIRECT_CFG_V1=PASS tests=96`
- Test/check count: `96`
- Evidence directory: `.openrecomp-phase2/evidence/P2-12/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-12/RESULT.md`
- Fixture/input identity: synthetic/original 35-instruction MIPS32 fixture (140 bytes) sha256 `2e3309f310a6f23c145ba7b95a22f10e3d81f32ec19afb966a9044395c066c84`
- Generated/executable/package identity: generated source sha256 `36ba17c8a1edcd22148c9789abe9348f68e9b6cd02912a9a94481de93a3009c9`; executable `program.exe` sha256 `3d92fc274ddb94190292fb9630243f7b064a42733406ecaf7cab2d85a5f2f266`
- Deterministic-run identity: P2-90-audited gate stdout sha256 `915df670bf88aded03deab9bc09ca1e96c055e196eb2c6dd7b7a61da101b8504`; two independent `/Brepro` builds byte-identical; stage-time hash `d01ec8f0...` is historical (documented cross-stage guard replacement)
- Claim boundary: bounded loop/branch/direct-call/bounded-dispatch fixture; dispatch target sets come from explicit evidence and out-of-set selectors fail closed.

### P2-13 — Runtime-host boundary
- PASS marker: `OPENRECOMP_P2_13=PASS`
- Gate marker: `OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1=PASS tests=80`
- Test/check count: `80`
- Evidence directory: `.openrecomp-phase2/evidence/P2-13/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-13/RESULT.md`
- Fixture/input identity: synthetic/original 5-instruction MIPS32 fixture (20 bytes) sha256 `7c9ba624b7503ccb31e0cd4b82b2c0316674b2c094945df84524503e34eb19b6`
- Generated/executable/package identity: generated source sha256 `8c602b35e47f90d5edf9fd6cad566b4b378c3ffc69574f63b80c48bdb55367ef`; executable `program.exe` sha256 `8ab94ab0f186e33778ddb6464f31c492045e6b612abeb523547b2aaa92a940a1`
- Deterministic-run identity: P2-90-audited gate stdout sha256 `ca82230b84a623f52f63f1f4a5d27c73ca137061c0674362334d1d111a362f24`; two independent `/Brepro` builds byte-identical; stage-time hash `8617ed85...` is historical (documented cross-stage guard replacement)
- Claim boundary: one declared runtime service on one bounded fixture with native fail-closed behavior for unsupported services; no general service surface.

### P2-14 — Larger MIPS32 open fixture
- PASS marker: `OPENRECOMP_P2_14=PASS`
- Gate marker: `OPENRECOMP_MIPS32_LARGER_FIXTURE_V1=PASS tests=82`
- Test/check count: `82`
- Evidence directory: `.openrecomp-phase2/evidence/P2-14/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-14/RESULT.md`
- Fixture/input identity: synthetic/original 4-function, 57-instruction MIPS32 fixture (228 bytes) sha256 `1c233f56528cb3fe20a7b806ce40e8bef6fc66a8cf8c0fd15d8b7b49bce547eb`
- Generated/executable/package identity: generated source sha256 `25d8d85ff88d2009443a6c67db40855df5e0876cb2b0aef8505d12d500204203`; executable `program.exe` sha256 `1e81bf8cd32b60cd5b3acae26c8f9dc23c0f801cf46b0c49ccb348ebc5eb2ab4`
- Deterministic-run identity: P2-90-audited gate stdout sha256 `197a6c5e5c5578ee6fced2eb45b937359bbd612dab8ec11bb4d5c2e6b717da51`; recompilation `recompilation.txt` and replay `replay.txt` sha256 `5a44a08c3bc1fd16044fa4309ed128f277586184f6661b6757b68e69a1517baa`; frozen pre-adjustment capture `P2-14/p2_14_gate.txt` (`115c2c8a...`) is historical
- Claim boundary: one bounded 57-instruction fixture with deterministic recompilation/replay and declared observable equality; saved-`$ra` RAM bytes are excluded from the observable.

### P2-20 — NES6502 program bridge
- PASS marker: `OPENRECOMP_P2_20=PASS`
- Gate marker: `OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1=PASS tests=86`
- Test/check count: `86`
- Evidence directory: `.openrecomp-phase2/evidence/P2-20/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-20/RESULT.md`
- Fixture/input identity: synthetic/original 15-instruction NES6502 region (26 bytes) sha256 `0a236023c59fd5363d0ebdd6ffb18d9b4e792ebeaa11a72ca513b183539fa398`
- Generated/executable/package identity: n/a (structural bridge only; no host emission); model fingerprints program `0dfbf094`, CFG `2924881e`, functions `7b83a827`, call graph `e99dce4b`, units `d0062fed`, classification `67113cc1`
- Deterministic-run identity: gate stdout sha256 `d104147c5bbc176af44499aed94320e095350f8e9e7f6fafbab8667d33025f03`; two independent `bridge_program` calls byte-identical
- Claim boundary: structural program bridge for one bounded synthetic NES6502 region; no host code, no execution and no NES equivalence.

### P2-21 — NES6502 host emitter path
- PASS marker: `OPENRECOMP_P2_21=PASS`
- Gate marker: `OPENRECOMP_NES6502_HOST_EMITTER_V1=PASS tests=74`
- Test/check count: `74`
- Evidence directory: `.openrecomp-phase2/evidence/P2-21/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-21/RESULT.md`
- Fixture/input identity: synthetic/original 15-instruction NES6502 region (26 bytes) sha256 `0a236023c59fd5363d0ebdd6ffb18d9b4e792ebeaa11a72ca513b183539fa398`
- Generated/executable/package identity: generated source sha256 `7d42947f658f0e7dcb146f3c5f2dd19c742c94bb8cf3e6b2ae8feb789758fd74`; executable `program.exe` sha256 `dbba1e3a86274d2944a38de575faee48d04e7748e8a150c93a5adbb0325e35f8`; native replay stdout sha256 `99848de179b0b120e42eed2e4b68e6e14a2dfa950d1065ac615dd8a845d27f3c`
- Deterministic-run identity: stage gate stdout sha256 `e66406e043b9dab859f5cf56ea537f333be7b59619e8c7bbb06bad4fd45f57e4` (P2-90 re-run records LF sha256 `774155ab...`); two native executions byte-identical; `EXECUTABLE_REPRODUCIBLE`
- Claim boundary: bounded 6502 semantic subset emitted through the shared pipeline; the fixture's `jsr`/`rts` stack effects are not modeled and the unresolved indirect jump fails closed.

### P2-22 — NES runtime bridge
- PASS marker: `OPENRECOMP_P2_22=PASS`
- Gate marker: `OPENRECOMP_NES_RUNTIME_BRIDGE_V1=PASS tests=66`
- Test/check count: `66`
- Evidence directory: `.openrecomp-phase2/evidence/P2-22/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-22/RESULT.md`
- Fixture/input identity: synthetic/original 42-byte NES6502 fixture sha256 `cc57bba3124f264cb6f4ec2b0e83cb82d3a9eeea551d18c098278c7eef827763` (P2-21 core region preserved)
- Generated/executable/package identity: n/a (adapter/runtime bridge stage; no host executable)
- Deterministic-run identity: gate stdout sha256 `4ae725be384b991c58d5e072930603b93c72c939df89c18f07749ae5c3db7b5c`; adapter state fingerprint `55da1916e5f56b3e663beb37ceb6486fba76957cb66027b64db1223f21639759`
- Claim boundary: bounded NROM/mapper-0 CPU bus, input mapping and frame/audio service contracts only; no PPU/APU implementation and no renderer/audio backend.

### P2-23 — NES end-to-end proof
- PASS marker: `OPENRECOMP_P2_23=PASS`
- Gate marker: `OPENRECOMP_NES_END_TO_END_V1=PASS tests=50`
- Test/check count: `50`
- Evidence directory: `.openrecomp-phase2/evidence/P2-23/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-23/RESULT.md`
- Fixture/input identity: synthetic/original 59-instruction NES6502 fixture (144 bytes) sha256 `dfadcbe759121b0705f2a7db3295127b7adceb403a6254897caee85f8a1c44c2`
- Generated/executable/package identity: generated source `generated_source.c` sha256 `9819b40e9909b4056211f6f452297b502b99bc4be4f96fe797cdcdfd6aaf2b78`; executable `program.exe` sha256 `5afd387d048299d53eb1cbc0534e9d01c373ccb9a370ca712bd01bef0b4c2207`
- Deterministic-run identity: stage gate stdout sha256 `96dbf5965310bc17a21bfc9fdd38042d30067b1efe7eae41522033dcc2ad1540` (P2-90 re-run records LF sha256 `5933b817...`); three native executions byte-identical (`c53c8ae8606b236c80d7c3fcd10d24da4f00752e15d933dcbdeb2f2882e81f82`); `EXECUTABLE_REPRODUCIBLE`
- Claim boundary: one synthetic 59-instruction NROM fixture compared on a declared observable set; no commercial ROM, no mapper support beyond 0 and no whole-guest equivalence.

### P2-30 — Cross-architecture neutrality audit
- PASS marker: `OPENRECOMP_P2_30=PASS`
- Gate marker: `OPENRECOMP_CROSS_ARCHITECTURE_NEUTRALITY_V1=PASS tests=14`
- Test/check count: `14`
- Evidence directory: `.openrecomp-phase2/evidence/P2-30/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-30/RESULT.md`
- Fixture/input identity: synthetic/original 8-instruction MIPS32 fixture exercised through P2-01..P2-07
- Generated/executable/package identity: generated host source sha256 `be52ef25060e22f8c4677c2e87a2e89180f82ae88833c4d910ec11fe1881b9f6` (no executable; two emissions byte-identical)
- Deterministic-run identity: gate stdout sha256 `49a2a255e714d17ab00d224dc3f6f218df8eb0e00d26d60ecfc71c89404abb54` (recorded UTF-16LE-BOM/CRLF convention)
- Claim boundary: static import/symbol isolation and one non-NES exercise over the audited shared modules only; future-architecture integrability is not proven.

### P2-40 — Generic runtime integration audit
- PASS marker: `OPENRECOMP_P2_40=PASS`
- Gate marker: `OPENRECOMP_GENERIC_RUNTIME_INTEGRATION_V1=PASS tests=181`
- Test/check count: `181`
- Evidence directory: `.openrecomp-phase2/evidence/P2-40/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-40/RESULT.md`
- Fixture/input identity: synthetic/original 11-instruction MIPS32 fixture sha256 `9323f24533ec6c31cf954c8315fd674ac8efc8c803e960eb9b1a902891cfe237`; fixture record `fixture.txt`
- Generated/executable/package identity: generated host source sha256 `c0a76e0f19217aeed017fca9f2abc82ef644563c1374d046987452800679246a`; executable `program.exe` sha256 `96676becf33f2251fcbc0b097ad8fa7ea2c100f4754617a4a5dcbdac1ecaf5b2`
- Deterministic-run identity: gate stdout sha256 `405c90d1c867495b3ac568a62b0d7c7e9234ca5ef469cdc2510d307b8d148228` (recorded LF form with the frozen evidence-dir prefix reconstructed); two full runs byte-identical; `EXECUTABLE_REPRODUCIBLE`
- Claim boundary: audited generic runtime contracts are neutral for the supported paths and one bounded non-NES exercise; GB/GBC/SMS are documented extension points only and no complete console emulation is claimed.

### P2-50 — Build/package reproducibility
- PASS marker: `OPENRECOMP_P2_50=PASS`
- Gate marker: `OPENRECOMP_BUILD_PACKAGE_REPRODUCIBILITY_V1=PASS tests=174`
- Test/check count: `174`
- Evidence directory: `.openrecomp-phase2/evidence/P2-50/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-50/RESULT.md`
- Fixture/input identity: three representative fixtures — `generic-runtime-pipeline` `9323f24533ec6c31cf954c8315fd674ac8efc8c803e960eb9b1a902891cfe237`, `mips32-larger` `1c233f56528cb3fe20a7b806ce40e8bef6fc66a8cf8c0fd15d8b7b49bce547eb`, `nes-nrom-end-to-end` `dfadcbe759121b0705f2a7db3295127b7adceb403a6254897caee85f8a1c44c2`; canonical source-state fingerprint `5d93971b102b24e56b2c98bf4c6b6486f58e6c174700af1c77cf969f85024c54`
- Generated/executable/package identity: executables `96676becf33f2251fcbc0b097ad8fa7ea2c100f4754617a4a5dcbdac1ecaf5b2`, `1e81bf8cd32b60cd5b3acae26c8f9dc23c0f801cf46b0c49ccb348ebc5eb2ab4`, `5afd387d048299d53eb1cbc0534e9d01c373ccb9a370ca712bd01bef0b4c2207`; release archives `fa72b5d169ad0f8f97c03578e18d1d0e4b810b9aa6281e154e947d9b2803888c`, `1c1dac0ea9942a9a31d0780c187c52b7e6bc18d6708f6599a76dca350079ef17`, `71847f9d7ffd126456cca96dea406884d4221b2c6fa86a2e4f15b6462d4c8745`
- Deterministic-run identity: gate stdout+stderr sha256 `0616da411e9b3b12e485b43056981e5fc269565ac932d556912ff9e82e63c92d`; all three targets `EXECUTABLE_REPRODUCIBLE`, nondeterminism classification `BYTE_DETERMINISTIC_NO_NORMALIZATION`
- Claim boundary: reproducible builds and deterministic release packaging are proven only for the three audited representative fixtures, the detected toolchain and the audited canonical ZIP path on this host.

### P2-90 — Whole-project regression
- PASS marker: `OPENRECOMP_P2_90=PASS`
- Gate marker: `OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1=PASS tests=361 gates=22 gate_tests=1990`
- Test/check count: `361`
- Evidence directory: `.openrecomp-phase2/evidence/P2-90/`
- Principal RESULT: `.openrecomp-phase2/evidence/P2-90/RESULT.md`
- Fixture/input identity: n/a (verification stage over the frozen Phase-2 tree); re-runs the frozen stage fixtures and identities listed above
- Generated/executable/package identity: n/a (verification stage); re-verifies every recorded fixture, generated-source, object, executable and package identity
- Deterministic-run identity: audit stdout capture sha256 `74e9eadaf0e17ca4a97790e4239f40883cc745cd9817c172f7fa6e2663ce1ee7` (CRLF capture convention; two byte-identical audit runs); LF-normalized audit content sha256 `00675593b278c8b660e2e4b00165e434057549a91263ba15b046150d82d00903` re-verified identical to the frozen capture by the P2-91 regression rerun; 22 gates, 1990 gate checks, Phase-1 host gates `PASS=44 FAIL=0 SKIPPED=2`, 132 manifest entries at P2-90 time (133 at P2-91 rerun time)
- Claim boundary: proves that the completed Phase-2 stages still pass together and that cross-stage evidence is internally consistent on the audited tree; it does not upgrade any bounded stage claim and does not claim the final proof marker.

## Index verification

- Every `PASS marker`, `Gate marker` and check count above is re-checked against
  the frozen per-stage evidence and the canonical P2-90 audit tables by
  `tools/test_phase2_evidence_closure_v1.py`.
- Every backticked repository reference in this index is checked to resolve to
  an existing file or directory.
- The host-path audit is recorded in `host_path_audit.md`: the nine frozen
  host-path occurrences identified by P2-90 remain byte-identical, documented
  exceptions; no new absolute host path is permitted in portable Phase-2
  evidence, control-plane narrative or release artifacts.
- The limitations record is `PHASE2_LIMITATIONS.md`; the claim-to-evidence
  mapping is `PHASE2_CLAIM_MATRIX.md`.
- `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` was issued by the P2-99
  terminal verdict (`.openrecomp-phase2/evidence/P2-99/RESULT.md`); the final
  verdict is no longer pending, and the pre-terminal
  `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN` records in the frozen
  stage evidence remain historical stage-time records.
