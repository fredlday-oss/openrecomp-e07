# OpenRecomp Phase 9 State

PHASE=9
BRANCH=phase8/mips32-end-to-end-native-v1
BASELINE_PHASE=8
BASELINE_COMMIT=61136fc37cf0810e64241addd8f57a91872bc0af
BASELINE_TREE=f9262497b82fe0027c3b23432ba7bd8cbccdf433
BASELINE_TAG_STATUS=ABSENT_RECONCILED
BASELINE_TAG_RECONCILIATION=Phase 8 created no annotated terminal tag. The authoritative Phase-8 terminal boundary is the P8-99 verdict commit 61136fc37cf0810e64241addd8f57a91872bc0af, tree f9262497b82fe0027c3b23432ba7bd8cbccdf433, on branch phase8/mips32-end-to-end-native-v1. No tag is fabricated.
BASELINE_TERMINAL=OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=PASS
BASELINE_GENERAL=OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN
PHASE7_V2_LINE=OUTSIDE_BASELINE
CURRENT_STAGE=P9-10
LAST_PASSED_STAGE=P9-10
STATUS=IN_PROGRESS
QUEUE_FREEZE=FROZEN
QUEUE_FREEZE_STAGES=P9-01..P9-99
FINAL_VERDICT=PENDING
OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN
OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN

## Baseline rule

The Phase-8 terminal commit and tree above, together with all frozen
Phase-1 through Phase-8 evidence, are immutable. Phase 9 is additive and
begins from that exact identity. The Phase-8 terminal claim
(`OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=PASS`) applies only to the
exact bounded audited Phase-8 fixture and behaviour; Phase 9 neither inherits
nor weakens it. The separately tagged `openrecomp-phase7-pass-v2` hardening
line and branch `phase7/hardening-v2` remain outside every baseline and are
neither used nor modified.

## Toolchains recorded at P9-00

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
`.openrecomp-phase9/evidence/P9-00/toolchains.json`.

## Control-plane policies

- `.openrecomp-phase9/CONTROL_POLICY.md` - phase rules and stop markers.
- `.openrecomp-phase9/ACCELERATION_POLICY.md` - fast/terminal gate policy, the
  `openrecomp-phase9-analysis-cache-v1` cache key contract, the
  incremental-build policy, and private-fixture cache handling.
- `.openrecomp-phase9/SCOPE.md` - terminal claim, permanent non-claims, public
  versus private evidence, and the required proof boundary.
- `.openrecomp-phase9/FIXTURE_POLICY.md` - public/private/synthetic fixture
  policy and the BIOS boundary rule.
- `.openrecomp-phase9/EVIDENCE_SCHEMA.md` - evidence, determinism and
  private-fixture evidence rules.

## Queue freeze record (P9-00 boundary)

- Frozen contract: `.openrecomp-phase9/STAGE_QUEUE.md` rows `P9-01` .. `P9-99`
  exactly as listed, effective before any P9-01 implementation work.
- No stage status changed at the freeze: each stage becomes active only when
  its own gate is executed.
- The freeze is a control-plane record only: no capability claim, no change to
  the frozen Phase-1 through Phase-8 boundaries, and no promotion of the
  terminal Phase-9 marker.

## Private fixture policy summary

The private Hercules `SLUS_005.29` fixture is a legally obtained local
validation input. It is never a public `PASS` criterion on its own, is never
committed or byte-referenced, and contributes only non-reconstructive metadata
to evidence. Public terminal claims require a legally redistributable
OpenRecomp-authored or openly licensed PS1 fixture.

## Stage ledger

| ID | Stage | Status | Evidence |
| --- | --- | --- | --- |
| P9-00 | Phase-9 boundary + acceleration control plane | PASS | `.openrecomp-phase9/evidence/P9-00/` |
| P9-01 | PS-X EXE ingestion | PASS | `.openrecomp-phase9/evidence/P9-01/` |
| P9-02 | PS1 executable image + memory-map contract | PASS | `.openrecomp-phase9/evidence/P9-02/` |
| P9-03 | Existing MIPS32 pipeline integration | PASS | `.openrecomp-phase9/evidence/P9-03/` |
| P9-04 | Reachable translation-frontier closure | PASS | `.openrecomp-phase9/evidence/P9-04/` |
| P9-05 | PS1 BIOS/service boundary | PASS | `.openrecomp-phase9/evidence/P9-05/` |
| P9-06 | PS1 GPU/runtime boundary | PASS | `.openrecomp-phase9/evidence/P9-06/` |
| P9-07 | Input/timer/event boundary | PASS | `.openrecomp-phase9/evidence/P9-07/` |
| P9-08 | SPU/audio boundary | PASS | `.openrecomp-phase9/evidence/P9-08/` |
| P9-09 | CD-ROM/file-service boundary | PASS | `.openrecomp-phase9/evidence/P9-09/` |
| P9-10 | Native build + deterministic execution | PASS | `.openrecomp-phase9/evidence/P9-10/` |
| P9-11 | Private Hercules validation | QUEUED | - |
| P9-12 | Hardening + reproducibility | QUEUED | - |
| P9-90 | Whole-project regression | QUEUED | - |
| P9-91 | Evidence closure + claim ledger | QUEUED | - |
| P9-99 | Final bounded verdict | QUEUED | - |

## P9-00 acceptance criteria

1. The Phase-8 terminal boundary is verified exactly: commit
   `61136fc3...`, tree `f9262497...`, branch
   `phase8/mips32-end-to-end-native-v1`, and the Phase-8 branch descends from
   it; no Phase-8 terminal tag exists and none is fabricated.
2. The frozen Phase-8 terminal evidence and control-plane hashes re-verify on
   disk; no tracked file under `.openrecomp-phase1` .. `.openrecomp-phase8`
   changed against the baseline commit outside the documented pre-existing
   Phase-3 residue; no new untracked residue appears in frozen phases.
3. The Phase-8 source manifest re-verifies unchanged, and the inherited
   Phase-6/Phase-7 reconciliation records are present.
4. Compiler/toolchain versions are recorded deterministically in
   `evidence/P9-00/toolchains.json`.
5. The Phase-9 control plane exists (STATE, HANDOFF, STAGE_QUEUE, SCOPE,
   CONTROL_POLICY, ACCELERATION_POLICY, EVIDENCE_SCHEMA, FIXTURE_POLICY,
   evidence/README.md, source manifest helper, stage runner) and is
   deterministic.
6. The queue rows `P9-00` .. `P9-99` are frozen in the exact order.
7. The terminal marker is reserved as
   `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` and both
   permanent non-claim markers are present.
8. The Phase-9 source manifest verifies, and the working tree has no
   unexpected new untracked paths beyond the documented Phase-2/Phase-3
   residue and the Phase-9 control plane.

## P9-00 result

PASS. Gate `tools/test_phase9_boundary_v1.py` (95 checks, run twice via
`p9_stage_runner_v1.py`, byte-identical stdout, empty stderr, exit 0).
Evidence: `.openrecomp-phase9/evidence/P9-00/`. Markers issued:

- `OPENRECOMP_P9_00=PASS`
- `OPENRECOMP_PHASE9_BOUNDARY_V1=PASS tests=95`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

The Phase-8 terminal commit/tree, all fifteen frozen Phase-8 terminal
evidence/control-plane hashes, the Phase-8 source manifest and the inherited
Phase-6/Phase-7 reconciliations were re-verified; no frozen file changed. The
frozen queue is `P9-01` .. `P9-99`; the next stage is `P9-01`.

## P9-01 result

PASS. Gate `tools/test_phase9_ingestion_v1.py` (163 checks, run twice via
`p9_stage_runner_v1.py`, byte-identical stdout, empty stderr, exit 0).
Evidence: `.openrecomp-phase9/evidence/P9-01/`. Markers issued:

- `OPENRECOMP_P9_01=PASS`
- `OPENRECOMP_PHASE9_INGESTION_V1=PASS tests=163`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

The additive ingestion module `.openrecomp-phase9/src/p9_psx_exe_v1.py` and
the original fixture builder
`.openrecomp-phase9/fixture/psx_fixture_builder_v1.py` were established. The
private Hercules fixture was reduced to non-reconstructive metadata only
(file/payload hashes, header fields, reserved-region hash and counts); no
executable bytes are committed, and the fixture is explicitly not a `PASS`
criterion. The next stage is `P9-02`.

## P9-02 result

PASS. Gate `tools/test_phase9_memory_map_v1.py` (128 checks, run twice via
`p9_stage_runner_v1.py`, byte-identical stdout, empty stderr, exit 0).
Evidence: `.openrecomp-phase9/evidence/P9-02/`. Markers issued:

- `OPENRECOMP_P9_02=PASS`
- `OPENRECOMP_PHASE9_MEMORY_MAP_V1=PASS tests=128`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

The additive contract module `.openrecomp-phase9/src/p9_memory_map_v1.py`
defines the 2 MiB main-RAM window, KSEG0/KSEG1 mirrors, named regions with
explicit permissions, the explicit bounded stack window, and fail-closed
classifications for KUSEG/scratchpad/I/O/BIOS/KSEG2. The private fixture
contributed a non-reconstructive contract summary only. The next stage is
`P9-03`.

## P9-03 result

PASS. Gate `tools/test_phase9_pipeline_v1.py` (66 checks, run twice via
`p9_stage_runner_v1.py`, byte-identical stdout, empty stderr, exit 0).
Evidence: `.openrecomp-phase9/evidence/P9-03/`. Markers issued:

- `OPENRECOMP_P9_03=PASS`
- `OPENRECOMP_PHASE9_PIPELINE_V1=PASS tests=66`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

The additive bridge `.openrecomp-phase9/src/p9_image_bridge_v1.py` and the
original public fixture `.openrecomp-phase9/fixture/p9_public_fixture_v1.py`
were established. The public fixture reaches a complete neutral structure
(46 reachable words, 39 neutral instructions, 9 blocks, 3 functions, 3
translation units, 2 internal call edges, no unresolved sites); an injected
`jalr` fails closed as an unresolved indirect call; the private Hercules
frontier is characterized (4068 reachable, first blocker `break` at
`0x80013390`, structure bridge fail-closed `CONTROL_WITHOUT_DELAY_SLOT`).
The next stage is `P9-04`.

## P9-04 result

PASS. Gate `tools/test_phase9_translation_v1.py` (31 checks, run twice via
`p9_stage_runner_v1.py`, byte-identical stdout, empty stderr, exit 0).
Evidence: `.openrecomp-phase9/evidence/P9-04/`. Markers issued:

- `OPENRECOMP_P9_04=PASS`
- `OPENRECOMP_PHASE9_TRANSLATION_CLOSURE_V1=PASS tests=31`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

`.openrecomp-phase9/src/p9_semantics_v1.py` reuses the frozen Phase-8 rule
table unchanged. All 39 neutral instructions of the public fixture are
covered exactly once (no uncovered sites, no flow mismatches) and emit
deterministically (fingerprint `78d099ed...`); an injected `lwl` fails closed;
the private fixture's 96 reachable recognized-unsupported words are classified
into five explicit categories with no unknown op and no reachable COP0/GTE
form. The next stage is `P9-05`.

## P9-05 result

PASS. Gate `tools/test_phase9_bios_v1.py` (88 checks, run twice via
`p9_stage_runner_v1.py`, byte-identical stdout, empty stderr, exit 0).
Evidence: `.openrecomp-phase9/evidence/P9-05/`. Markers issued:

- `OPENRECOMP_P9_05=PASS`
- `OPENRECOMP_PHASE9_BIOS_BOUNDARY_V1=PASS tests=88`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

`.openrecomp-phase9/src/p9_bios_boundary_v1.py` declares a typed, versioned,
fail-closed service boundary with no BIOS image. The public fixture requires
no BIOS service (0 sites); an injected A0 call is discovered and fails closed;
the private fixture's 22 reachable indirect call sites classify as 3 BIOS B0
candidates and 19 explicit unknowns, with no BIOS function implemented. The
next stage is `P9-06`.

## P9-06 result

PASS. Gate `tools/test_phase9_gpu_v1.py` (102 checks, run twice via
`p9_stage_runner_v1.py`, byte-identical stdout, empty stderr, exit 0).
Evidence: `.openrecomp-phase9/evidence/P9-06/`. Markers issued:

- `OPENRECOMP_P9_06=PASS`
- `OPENRECOMP_PHASE9_GPU_BOUNDARY_V1=PASS tests=102`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

`.openrecomp-phase9/src/p9_io_discovery_v1.py` (shared bounded I/O access
discovery) and `.openrecomp-phase9/src/p9_gpu_boundary_v1.py` (non-emulating
GPU adapter with typed event transcript, unknown-command blockers and
labelled read stubs) were established. The public fixture's two reachable GPU
writes (GP0 `NOP`, GP1 `RESET_GPU`) are discovered and classified exactly;
the private reachable frontier contains no discoverable GPU-range access. The
next stage is `P9-07`.

## P9-07 result

PASS. Gate `tools/test_phase9_input_timer_v1.py` (64 checks, run twice via
`p9_stage_runner_v1.py`, byte-identical stdout, empty stderr, exit 0).
Evidence: `.openrecomp-phase9/evidence/P9-07/`. Markers issued:

- `OPENRECOMP_P9_07=PASS`
- `OPENRECOMP_PHASE9_INPUT_TIMER_V1=PASS tests=64`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

`.openrecomp-phase9/src/p9_input_timer_v1.py` provides deterministic virtual
input (fixed button state), virtual time (counter read returns tick then
advances), labelled status/config stubs and explicit not-modelled interrupt
blockers. The public fixture's two reachable reads (JOY_DATA, TIMER0) are
served deterministically; the private reachable frontier contains no
discoverable access in these ranges. The next stage is `P9-08`.

## P9-08 result

PASS. Gate `tools/test_phase9_spu_v1.py` (60 checks, run twice via
`p9_stage_runner_v1.py`, byte-identical stdout, empty stderr, exit 0).
Evidence: `.openrecomp-phase9/evidence/P9-08/`. Markers issued:

- `OPENRECOMP_P9_08=PASS`
- `OPENRECOMP_PHASE9_SPU_BOUNDARY_V1=PASS tests=60`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

`.openrecomp-phase9/src/p9_spu_boundary_v1.py` provides the explicit audio
service/runtime contract with bounded SPU register ranges, typed event
recording and no synthesis. The public fixture's single reachable SPU write
(`0x1f801daa` = `0xc0`) is classified and recorded; unknown registers fail
closed; the private frontier has no discoverable SPU access. The next stage is
`P9-09`.

## P9-09 result

PASS. Gate `tools/test_phase9_cdrom_v1.py` (73 checks, run twice via
`p9_stage_runner_v1.py`, byte-identical stdout, empty stderr, exit 0).
Evidence: `.openrecomp-phase9/evidence/P9-09/`. Markers issued:

- `OPENRECOMP_P9_09=PASS`
- `OPENRECOMP_PHASE9_CDROM_BOUNDARY_V1=PASS tests=73`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

`.openrecomp-phase9/src/p9_cdrom_boundary_v1.py` provides the explicit bounded
disc/file-service contract (`disc_image: none`, `file_service: none`). The
public fixture's single reachable CD-ROM command write (`0x19` = `TEST`) is
classified and recorded; unknown commands fail closed; the private frontier
has no discoverable CD-ROM access. The next stage is `P9-10`.

## Documented fixture correction (P9-10 preparation)

While preparing P9-10, the public fixture was found to rely on an initial
stack pointer that the frozen Phase-8 emitter does not provide (generated
programs start all guest registers at zero). The fixture was corrected to
initialize `$sp` itself at entry (`lui $sp, 0x801f; ori $sp, $sp, 0xfff0`).
The change is additive (two instructions, same platform behaviour). The
affected pinned counts/fingerprints/access-site offsets in P9-03, P9-04,
P9-06, P9-07, P9-08 and P9-09 were updated, their official runs were
re-issued on the corrected tree, and their RESULT.md records carry the
correction note. The official stdout identity of every affected gate is
unchanged; the corrected public fixture SHA-256 is
`17466bc17edde54f4d371ae22281b9fb31cd9114c3c293aa7da103751c32c3da`
(2240 bytes; recorded in the P9-10 evidence).

## P9-10 result

PASS. Gate `tools/test_phase9_native_v1.py` (49 checks, run twice via
`p9_stage_runner_v1.py`, byte-identical stdout, empty stderr, exit 0).
Evidence: `.openrecomp-phase9/evidence/P9-10/`. Markers issued:

- `OPENRECOMP_P9_10=PASS`
- `OPENRECOMP_PHASE9_NATIVE_EXECUTION_V1=PASS tests=49`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

`.openrecomp-phase9/src/p9_emission_v1.py`, the OpenRecomp-authored runtime
`.openrecomp-phase9/runtime/p9_runtime_support.c` and
`.openrecomp-phase9/runtime/p9_observable_driver.c`, and the independent
reference `.openrecomp-phase9/src/p9_reference_psx_v1.py` were established.
The public fixture emits deterministically, builds reproducibly (executable
`5c016be2...`) and executes with byte-identical output; the native and
reference observables agree exactly (exit `0x00000002`, registers digest
`0x17f2292e1363f17f`, memory digest `0x28d892afac2d8496`, GPU/input/SPU/
CD-ROM event digests `0x6a326cbc...`/`0xe35ba754...`/`0x55788edb...`/
`0x0dc54fdf...`, reads 1, writes 4, denied 0, no excluded observables). The
next stage is `P9-11`.
