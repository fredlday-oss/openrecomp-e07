# OpenRecomp Phase 8 State

PHASE=8
BRANCH=phase8/mips32-end-to-end-native-v1
BASELINE_TAG=openrecomp-phase7-pass
BASELINE_TAG_OBJECT=b07e0f691262ed3ae0bc2fd6ebb3e3d3c5222800
BASELINE_COMMIT=2917aa6549ab975cffdeb50120514c1723f7e493
BASELINE_TREE=59529c130d759ceb1ca9e6c65a510fa373656b01
BASELINE_TERMINAL=OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=PASS
BASELINE_GENERAL=OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
BASELINE_TAG_STATUS=ABSENT_RECONCILED
BASELINE_TAG_RECONCILIATION=P7-99 records that the frozen Phase-6 control policy required and created no terminal tag; the authoritative Phase-6 terminal boundary is the P6-99 verdict commit 1643817d43196c43155805249137e4b4e4a21eb1, tree cda3f535be43dc6f3d4b457d11d356ae39ea34af. No tag is fabricated.
PHASE7_V2_LINE=OUTSIDE_BASELINE
CURRENT_STAGE=P8-90
LAST_PASSED_STAGE=P8-12
STATUS=ACTIVE
QUEUE_FREEZE=FROZEN
QUEUE_FREEZE_STAGES=P8-01..P8-99
FINAL_VERDICT=NOT_PROVEN
OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN
OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

## Baseline rule

The Phase-7 annotated tag `openrecomp-phase7-pass` and its commit/tree
identity above, together with all frozen Phase-1 through Phase-7 evidence, are
immutable. Phase 8 is additive and begins from that exact identity. The
separately tagged `openrecomp-phase7-pass-v2` hardening line and branch
`phase7/hardening-v2` are outside this phase's baseline and are neither used
nor modified.

## Toolchains recorded at P8-00

| Tool | Version / identity | Path |
|---|---|---|
| Python | 3.11.9 | `python` on PATH |
| Git | 2.55.0.windows.3 | `git` on PATH |
| clang / clang-cl | 22.1.8 (`ca7933e47d3a3451d81e72ac174dcb5aa28b59d1`) | LLVM on PATH |
| lld-link / ld.lld | 22.1.8 (`ca7933e47d3a3451d81e72ac174dcb5aa28b59d1`) | LLVM on PATH |
| Ninja | 1.13.2 | `ninja` on PATH |
| CMake | 4.4.3 | `cmake` on PATH |
| Zig (Phase-3 toolchain residue, untracked) | 0.13.0 | `.openrecomp-phase3/tools/zig/zig.exe` |

Exact observed version strings are recorded in
`.openrecomp-phase8/evidence/P8-00/toolchains.json`.

## Control-plane policies

- `.openrecomp-phase8/CONTROL_POLICY.md` - phase rules and stop markers.
- `.openrecomp-phase8/ACCELERATION_POLICY.md` - fast/terminal gate policy, the
  `openrecomp-phase8-analysis-cache-v1` cache key contract, and the
  incremental-build policy.
- `.openrecomp-phase8/SCOPE.md` - terminal claim, permanent non-claims, and
  the required proof boundary.
- `.openrecomp-phase8/FIXTURE_POLICY.md` - real/synthetic/private fixture
  policy.
- `.openrecomp-phase8/EVIDENCE_SCHEMA.md` - evidence and determinism rules.

## Queue freeze record (P8-00 boundary)

- Frozen contract: `.openrecomp-phase8/STAGE_QUEUE.md` rows `P8-01` .. `P8-99`
  exactly as listed, effective before any P8-01 implementation work.
- No stage status changed at the freeze: each stage becomes active only when
  its own gate is executed.
- The freeze is a control-plane record only: no capability claim, no change to
  the frozen Phase-1 through Phase-7 boundaries, and no promotion of the
  terminal Phase-8 marker.

## Stage ledger

| ID | Stage | Status | Evidence |
| --- | --- | --- | --- |
| P8-00 | Phase-8 boundary + acceleration control plane | PASS | `.openrecomp-phase8/evidence/P8-00/` |
| P8-01 | Real redistributable MIPS32 ELF fixture | PASS | `.openrecomp-phase8/evidence/P8-01/` |
| P8-02 | Existing MIPS32 pipeline re-derivation | PASS | .openrecomp-phase8/evidence/P8-02/ |
| P8-03 | Real-ELF ProgramModel / CFG integration | PASS | .openrecomp-phase8/evidence/P8-03/ |
| P8-04 | Translation frontier closure | PASS | .openrecomp-phase8/evidence/P8-04/ |
| P8-05 | Static memory + runtime contract closure | PASS | .openrecomp-phase8/evidence/P8-05/ |
| P8-06 | Host-source emission | PASS | .openrecomp-phase8/evidence/P8-06/ |
| P8-07 | Incremental native build | PASS | .openrecomp-phase8/evidence/P8-07/ |
| P8-08 | Deterministic native execution | PASS | .openrecomp-phase8/evidence/P8-08/ |
| P8-09 | Independent reference equivalence | PASS | `.openrecomp-phase8/evidence/P8-09/` |
| P8-10 | Reusable real-MIPS32 ELF-to-native workflow | PASS | .openrecomp-phase8/evidence/P8-10/ |
| P8-11 | Fail-closed hardening | PASS | .openrecomp-phase8/evidence/P8-11/ |
| P8-12 | Phase-8 evidence closure | PASS | .openrecomp-phase8/evidence/P8-12/ |
| P8-90 | Whole-project regression | QUEUED | - |
| P8-91 | Evidence index + proof matrix | QUEUED | - |
| P8-99 | Final bounded verdict | QUEUED | - |

## P8-00 acceptance criteria

1. The frozen Phase-7 baseline is verified exactly: annotated tag
   `openrecomp-phase7-pass` (tag object `b07e0f69...`) -> commit
   `2917aa65...` -> tree `59529c13...`, and the Phase-8 branch is at that
   commit with the recorded tree.
2. The Phase-7 terminal evidence is untouched: the pinned P7-99 terminal
   artefacts and the Phase-7 control-plane hashes re-verify on disk, no
   tracked file under `.openrecomp-phase1` .. `.openrecomp-phase7` changed
   against the baseline commit, and no untracked residue was added there.
3. The historical Phase-6 tag `openrecomp-phase6-pass` is absent and the
   frozen `ABSENT_RECONCILED` record is present in the Phase-7 state.
4. Compiler/toolchain versions are recorded deterministically in
   `evidence/P8-00/toolchains.json`.
5. The Phase-8 control plane exists (STATE, HANDOFF, STAGE_QUEUE, SCOPE,
   CONTROL_POLICY, ACCELERATION_POLICY, EVIDENCE_SCHEMA, FIXTURE_POLICY,
   evidence/README.md, source manifest helper) and is deterministic.
6. The queue rows `P8-00` .. `P8-99` are frozen in the exact order.
7. The terminal marker is still reserved as
   `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN` and the
   permanent general marker is present.
8. The Phase-8 source manifest verifies, and the working tree has no
   unexpected new untracked paths beyond the documented Phase-2/Phase-3
   residue and the Phase-8 control plane.

## P8-00 result

PASS. Gate `tools/test_phase8_boundary_v1.py` (run twice, byte-identical
stdout, empty stderr, exit 0). Evidence:
`.openrecomp-phase8/evidence/P8-00/`. Markers issued:

- `OPENRECOMP_P8_00=PASS`
- `OPENRECOMP_PHASE8_BOUNDARY_V1=PASS`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`

The boundary gate was made re-runnable at later stages
(`branch:boundary-tree-identical` is emitted unconditionally and is vacuously
satisfied for descendant HEADs; `LAST_PASSED_STAGE` / `CURRENT_STAGE` are
checked for the `P8-NN` shape). The official boundary stdout is unchanged
(68 checks, raw sha256 `8bc1af62...`, 2871 bytes, LF `9b078c87...`). The
committed P8-00 sidecars are the boundary-time records
(`boundary_mode=AT_BOUNDARY`). Later stages re-run the gate with
`--verify-only`, which performs all checks without rewriting the committed
P8-00 evidence sidecars.

## Frozen real-ELF fixture identity (P8-01)

- Program: upstream `tiny-AES-c` AES-128-ECB, repository
  `https://github.com/kokke/tiny-AES-c`, pinned commit
  `23856752fbd139da0b8ca6e471a13d5bcc99a08d`.
- Licence: The Unlicense (public-domain dedication), upstream
  `unlicense.txt`.
- OpenRecomp-authored freestanding port under `.openrecomp-phase8/fixture/`
  (entry stub, linker script, bounded port support, FIPS-197 AES-128
  known-answer harness, minimal `string.h` shim).
- Toolchain: Zig 0.13.0 (clang 18.1.5 / LLD 18.1.6) at the Phase-3 recorded
  archive/executable identity; profile `-O1`, freestanding, non-PIC,
  soft-float, static, `mipsel-linux-musl`, `-march=mips32 -mabi=32`.
- ELF: SHA-256
  `0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65`,
  12904 bytes, ELF32 little-endian `EM_MIPS` `ET_EXEC`, flags `0x50001001`,
  entry `0x2490`; `.text` `0x1000`+5300, `.rodata` `0x24c0`+571, `.data`
  `0x2700`+8, `.bss` `0x2710`+16384.
- Frontier: 509 reachable words (508 supported + 1 `movz` at `0x2440`), 816
  unreachable, 23 delay slots (16 non-nop), 5 branches / 8 direct calls /
  3 jumps / 7 returns, no indirect control flow, no unresolved sites.
- Upstream sources and the built ELF remain untracked and are represented by
  provenance, metadata and hashes only.

## P8-01 result

PASS. Gate `tools/test_phase8_fixture_v1.py` (89 checks, run twice,
byte-identical stdout, empty stderr, exit 0). Evidence:
`.openrecomp-phase8/evidence/P8-01/`. Markers issued:

- `OPENRECOMP_P8_01=PASS`
- `OPENRECOMP_PHASE8_REAL_ELF_FIXTURE_V1=PASS tests=89`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`

## P8-02 result

PASS. Gate `tools/test_phase8_frontier_v1.py` (43 checks, run twice,
byte-identical stdout, empty stderr, exit 0). Evidence:
`.openrecomp-phase8/evidence/P8-02/`. Markers issued:

- `OPENRECOMP_P8_02=PASS`
- `OPENRECOMP_PHASE8_FRONTIER_REDERIVATION_V1=PASS tests=43`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`

Frozen frontier classification (509 reachable words, each exactly once):
`EMITTER_READY` 215, `EMITTER_READY_32BIT_MEMORY` 48,
`EMITTER_READY_CONTROL_DELAY_SLOT` 15,
`EMITTER_READY_CONTROL_DELAY_SLOT_LINK_REGISTER` 8,
`HOST_EMITTER_WIDTH_GAP` 222, `TRANSLATION_SEMANTICS_GAP` 1 (`movz`).
Measured gaps: translation semantics 1, emitter width 222, delay slots 23
(16 non-nop), o32 link-register 8 call sites, runtime host service 1,
memory-image contract 1, native toolchain 0, unresolved control flow 0. The
reused Phase-3 module hashes equal their frozen manifest entries.

## P8-03 result

PASS. Gate `tools/test_phase8_structure_v1.py` (52 checks, run twice,
byte-identical stdout, empty stderr, exit 0). Evidence:
`.openrecomp-phase8/evidence/P8-03/`. Markers issued:

- `OPENRECOMP_P8_03=PASS`
- `OPENRECOMP_PHASE8_PROGRAM_STRUCTURE_V1=PASS tests=52`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`

The additive P8 bridge `.openrecomp-phase8/src/p8_structure_v1.py` folds the
23 delay slots (16 non-nop) into their control instructions and derives the
shared neutral structure: 486 instructions, 27 blocks, 25 edges, 7 functions,
7 translation units, 8 internal call edges, 0 unresolved sites, 0 unowned
blocks, entry `fn_2490`/`tu_fn_2490`, with deterministic fingerprints and
fail-closed mutations.

## P8-04 result

PASS. Gate `tools/test_phase8_translation_v1.py` (29 checks, run twice,
byte-identical stdout, empty stderr, exit 0). Evidence:
`.openrecomp-phase8/evidence/P8-04/`. Markers issued:

- `OPENRECOMP_P8_04=PASS`
- `OPENRECOMP_PHASE8_TRANSLATION_CLOSURE_V1=PASS tests=29`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`

Additive host-emitter extensions (`HostLoad` width/sign, `HostStore` width,
`HostSelect`, opt-in folded delay-slot protocol, opt-in link register) plus
the closed P8 MIPS32 rule table
(`.openrecomp-phase8/src/p8_mips32_semantics_v1.py`). The full 486-instruction
real structure emits deterministically (fingerprint `6a957bd1...`), and the
new semantics pass differential native-vs-independent-reference execution.
Direct dependency gates re-pass unchanged.

## P8-05 result

PASS. Gate `tools/test_phase8_runtime_v1.py` (36 checks, run twice,
byte-identical stdout, empty stderr, exit 0). Evidence:
`.openrecomp-phase8/evidence/P8-05/`. Markers issued:

- `OPENRECOMP_P8_05=PASS`
- `OPENRECOMP_PHASE8_RUNTIME_CONTRACT_V1=PASS tests=36`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`

The contract module `.openrecomp-phase8/src/p8_memory_contract_v1.py` and the
OpenRecomp-authored runtime support
`.openrecomp-phase8/runtime/p8_runtime_support.c` define the flat image
window `0x0..0x6710`, explicit region permissions, the 16 KiB stack at
`0x2710..0x6710`, the single write-only byte output window at `0x10000000`
(`p8_uart_write`) and return-to-host termination. A native driver compiled
through the existing build pipeline matches the independent Python memory
model over the full read/write/denial vector, counters and transcript.

## P8-06 result

PASS. Gate `tools/test_phase8_emission_v1.py` (25 checks, run twice,
byte-identical stdout, empty stderr, exit 0). Evidence:
`.openrecomp-phase8/evidence/P8-06/`. Markers issued:

- `OPENRECOMP_P8_06=PASS`
- `OPENRECOMP_PHASE8_HOST_EMISSION_V1=PASS tests=25`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`

Emission set (stable filenames and content hashes): `program.c`
`6a957bd1...` (continuity with P8-04), `p8_image_v1.c` `d5d95845...`,
`p8_runtime_support.c` `9b5e70f5...`, `p8_driver.c` `e918de64...`. The guest
image is embedded as inert data; all executed semantics are generated C.

## P8-07 result

PASS. Gate `tools/test_phase8_native_build_v1.py` (24 checks, run twice,
byte-identical stdout, empty stderr, exit 0). Evidence:
`.openrecomp-phase8/evidence/P8-07/`. Markers issued:

- `OPENRECOMP_P8_07=PASS`
- `OPENRECOMP_PHASE8_NATIVE_BUILD_V1=PASS tests=24`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`

Clean audited build `EXECUTABLE_REPRODUCIBLE`: `program.exe` 226304 bytes,
SHA-256 `612cad0e9f59a3e334fa6c1d76d6d3c43bfeda71dd1de533d4c216589697429c`;
incremental content-hash cache: cold 4 compiled, warm 4 reused, corrupted
entry 1 recompiled/3 reused, executable byte-stable.

## P8-08 result

PASS. Gate `tools/test_phase8_native_execution_v1.py` (26 checks, run twice,
byte-identical stdout, empty stderr, exit 0). Evidence:
`.openrecomp-phase8/evidence/P8-08/`. Markers issued:

- `OPENRECOMP_P8_08=PASS`
- `OPENRECOMP_PHASE8_NATIVE_EXECUTION_V1=PASS tests=26`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`

Native execution is byte-identical across three runs: `failed=0`,
`exit_status=0x00000000`, all 32 registers with digest `0x7ee0f4a187050726`,
memory digest `0x231c4a49e79c5e56`, transcript 33 bytes with digest
`0xca6dcb87f8ac9814` (the FIPS-197 AES-128 known-answer line), reads 1136,
writes 681, host calls 33, denied 0.

## Documented correction: `movz` operand roles (P8-09 preparation)

While preparing the independent reference, the P8-04 `movz` rule was found to
invert the MIPS32 operand roles (`if GPR[rt] == 0 then GPR[rd] = GPR[rs]`).
The synthetic differential vector had used the same inverted convention in its
model, so the defect was invisible there. The rule and the reference model are
corrected, the synthetic vector now distinguishes the conventions
(`r12 = 7`, `r13 = 0`, `r14 = 7`), and P8-04, P8-06, P8-07 and P8-08 were
re-run officially with regenerated evidence. The emitted program fingerprint
is now `3df423e0...` (was `6a957bd1...`), the clean executable is
`fb98c8a6...` (was `612cad0e...`), and the frozen fixture's observable record
is unchanged (`exit_status=0x00000000`, register digest
`0x7ee0f4a187050726`, memory digest `0x231c4a49e79c5e56`, transcript digest
`0xca6dcb87f8ac9814`, reads 1136, writes 681, host calls 33, denied 0). No
frozen Phase-1..Phase-7 artifact was modified.

## P8-09 result

PASS. Gate `tools/test_phase8_reference_equivalence_v1.py` (24 checks, run
twice, byte-identical stdout, empty stderr, exit 0). Evidence:
`.openrecomp-phase8/evidence/P8-09/`. Markers issued:

- `OPENRECOMP_P8_09=PASS`
- `OPENRECOMP_PHASE8_REFERENCE_EQUIVALENCE_V1=PASS tests=24`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`

The independent reference `.openrecomp-phase8/src/p8_reference_mips32_v1.py`
(own loader, decoder, interpreter and runtime contract; no recompilation
imports) executed the frozen ELF for 4572 instructions and matches the native
record exactly on every observable: exit status, all 32 registers, register
digest `0x7ee0f4a187050726`, memory digest `0x231c4a49e79c5e56`, transcript
33 bytes / digest `0xca6dcb87f8ac9814`, reads 1136, writes 681, host calls
33, denied 0, with no excluded observables.

## P8-10 result

PASS. Gate `tools/test_phase8_workflow_v1.py` (15 checks, run twice,
byte-identical stdout, empty stderr, exit 0). Evidence:
`.openrecomp-phase8/evidence/P8-10/`. Markers issued:

- `OPENRECOMP_P8_10=PASS`
- `OPENRECOMP_PHASE8_WORKFLOW_V1=PASS tests=15`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`

The workflow module `.openrecomp-phase8/src/p8_workflow_v1.py` runs
classification, analysis, structure, memory contract, emission, native build,
execution and reference equivalence deterministically, with explicit
fail-closed categories verified on seven malformed/unsupported inputs.

## P8-11 result

PASS. Gate `tools/test_phase8_hardening_v1.py` (47 checks, run twice,
byte-identical stdout, empty stderr, exit 0). Evidence:
`.openrecomp-phase8/evidence/P8-11/`. Markers issued:

- `OPENRECOMP_P8_11=PASS`
- `OPENRECOMP_PHASE8_HARDENING_V1=PASS tests=47`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`

Eight malformed/unsupported inputs are rejected deterministically before
emission/build/execution with explicit categories; the closed rule table,
the new immutable-hash analysis cache
(`.openrecomp-phase8/src/p8_analysis_cache_v1.py`) and the content-hash
object cache all reject stale/corrupted state; the frozen fixture still
completes with equivalence under the hardened path.

## P8-12 result

PASS. Gate `tools/test_phase8_evidence_closure_v1.py` (130 checks, run twice,
byte-identical stdout, empty stderr, exit 0). Evidence:
`.openrecomp-phase8/evidence/P8-12/`. Markers issued:

- `OPENRECOMP_P8_12=PASS`
- `OPENRECOMP_PHASE8_EVIDENCE_CLOSURE_V1=PASS tests=130`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`

Implementation delta `none`. All twelve completed stages' run captures and
sidecar hashes verify; the analysis cache rejects stale keys; the clean
re-run reproduces the emission, executable, observable and reference
identities exactly, twice.

## Current boundary

P8-00..P8-12 are complete. The remaining frozen stages are the whole-project
regression (P8-90), the evidence index and proof matrix (P8-91) and the final
bounded verdict (P8-99); the terminal objective remains unproven. P8-90 is
active.
