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
CURRENT_STAGE=P8-05
LAST_PASSED_STAGE=P8-04
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
| P8-05 | Static memory + runtime contract closure | QUEUED | - |
| P8-06 | Host-source emission | QUEUED | - |
| P8-07 | Incremental native build | QUEUED | - |
| P8-08 | Deterministic native execution | QUEUED | - |
| P8-09 | Independent reference equivalence | QUEUED | - |
| P8-10 | Reusable real-MIPS32 ELF-to-native workflow | QUEUED | - |
| P8-11 | Fail-closed hardening | QUEUED | - |
| P8-12 | Phase-8 evidence closure | QUEUED | - |
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

## Current boundary

P8-00 established the control plane, P8-01 froze the real-ELF fixture and its
reproducible build, P8-02 characterized the frontier, P8-03 derived the
neutral structure, and P8-04 proved every reachable instruction translatable
with the new semantics independently verified. The full fixture has not yet
been built and executed natively; the terminal objective remains unproven.
P8-05 (static memory + runtime contract closure) is active.
