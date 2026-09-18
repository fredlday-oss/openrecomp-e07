# OpenRecomp Phase 4 State

PHASE=4
BASELINE_TAG=openrecomp-phase3-pass
BASELINE_COMMIT=e16e4b29b90f379615f1af97e47747cd1d531796
BASELINE_TREE=a940f0d84a32adaf191f7ff2bebfb24cc855cde0
CURRENT_STAGE=P4-04
LAST_PASSED_STAGE=P4-03
STATUS=ACTIVE
GENERIC_RUNTIME_STATUS=NOT_PROVEN
FINAL_VERDICT=NOT_PROVEN
QUEUE_FREEZE=FROZEN
QUEUE_FREEZE_STAGES=P4-01..P4-99

## Phase-3 frozen boundary identities

- Tag `openrecomp-phase3-pass` (annotated, object
  `ac31524504b1b5cc63aabcfd5132a3eb4275e8e9`) resolves to commit
  `e16e4b29b90f379615f1af97e47747cd1d531796`, tree
  `a940f0d84a32adaf191f7ff2bebfb24cc855cde0`.
- Phase-3 terminal markers on the frozen tree:
  `OPENRECOMP_P3_99=PASS`,
  `OPENRECOMP_PHASE3_FINAL_VERDICT_V1=PASS tests=46`,
  `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=PASS`.
- Frozen integrity identities:
  - `SOURCE_SHA256SUMS.txt` sha256
    `76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095`
    (134 manifest entries)
  - `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` sha256
    `a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488`
    (24 manifest entries)
  - `.openrecomp-phase3/evidence/P3-99/RESULT.json` sha256
    `c893250b539cf1e82f368c09fe848f8f695ebece17f7735713c5367a3d93c1cf`
  - `tools/test_phase3_final_verdict_v1.py` sha256
    `ba5814902797d9848614e08b6bd655c00061dfb0d2dc90fec30da60382d558fa`
  - terminal P3-99 gate stdout: 2498 bytes, raw sha256
    `953ec70c312c7203022ba98f763aabf270409e2f39a9a7fa2ac90d887ae087bc`,
    LF sha256
    `4974d03fdd02ef76e1fa6506d230cd2c9be9e1cfe55bb9d5d4851f7525c72dd5`
  - CoreMark fixture ELF sha256
    `16a0a0aa0f62344d8c0f309b755450f09c330e7c5a7c355785662d7a141f7669`
    (31184 bytes)
- Phase-2 boundary `openrecomp-phase2-pass` =
  `01b1d7cba8c931fca95d041389cfb1902b7c89fe`; Phase-1 boundary
  `openrecomp-phase1-pass` = `46c2f971e1a42cf49bd936bad94697b81bf31002`.
- Documented untracked residue preserved from Phase 2/3:
  `.openrecomp-phase2/backups/`, `.openrecomp-phase2/scratch/`,
  `artifacts/mips32_translation_v1/`,
  `artifacts/mips32_translation_evidence_closure_v1/`, the 28 frozen
  verification-context files, the Phase-3 external source/toolchain/build
  sets, and the Phase-3 platform-line-ending captures recorded in the Phase-3
  control plane.

## Queue freeze record (P4-00 boundary)

- Frozen contract: `.openrecomp-phase4/STAGE_QUEUE.md` `## Queue freeze`, rows
  `P4-01` .. `P4-99` exactly as listed, effective before any P4-01
  implementation work.
- Rules (see the queue section): no renumber/insert/merge/split/silent
  redefinition; a change requires a genuine technical dependency, must fail
  closed with an explicit blocker record, and must be documented in the
  reconciliation log with the forcing evidence.
- No stage status changed at the freeze: `P4-01` .. `P4-99` stay `QUEUED`
  until their own gates pass.
- The freeze is a control-plane record only: no capability claim, no change to
  the frozen Phase-1/Phase-2/Phase-3 boundaries and no promotion of the
  Phase-4 terminal marker.

## Stage ledger

| ID | Stage | Status | Evidence |
| --- | --- | --- | --- |
| P4-00 | Phase-4 boundary | PASS | `.openrecomp-phase4/evidence/P4-00/` |
| P4-01 | Generic Runtime ABI V1 | PASS | `.openrecomp-phase4/evidence/P4-01/` |
| P4-02 | Guest memory/runtime model | PASS | `.openrecomp-phase4/evidence/P4-02/` |
| P4-03 | Runtime service mediation | PASS | `.openrecomp-phase4/evidence/P4-03/` |
| P4-04 | Deterministic I/O, timing and input | QUEUED | `.openrecomp-phase4/evidence/P4-04/` |
| P4-05 | Platform Adapter Interface V1 | QUEUED | `.openrecomp-phase4/evidence/P4-05/` |
| P4-06 | Graphics/audio abstraction boundary | QUEUED | `.openrecomp-phase4/evidence/P4-06/` |
| P4-07 | Interactive legally-clean fixture | QUEUED | `.openrecomp-phase4/evidence/P4-07/` |
| P4-08 | First platform-adapter execution proof | QUEUED | `.openrecomp-phase4/evidence/P4-08/` |
| P4-09 | End-to-end generic-runtime native proof | QUEUED | `.openrecomp-phase4/evidence/P4-09/` |
| P4-10 | Reproducible Phase-4 package | QUEUED | `.openrecomp-phase4/evidence/P4-10/` |
| P4-90 | Phase-4 whole regression audit | QUEUED | `.openrecomp-phase4/evidence/P4-90/` |
| P4-91 | Evidence index + limitations | QUEUED | `.openrecomp-phase4/evidence/P4-91/` |
| P4-99 | Final Phase-4 verdict | QUEUED | `.openrecomp-phase4/evidence/P4-99/` |

## P4-00 acceptance criteria

1. Phase-3 frozen tag `openrecomp-phase3-pass` (annotated) resolves to the
   recorded commit and tree, and the Phase-4 branch descends from that
   boundary (`merge-base` is the boundary commit).
2. Phase-3 final evidence is unchanged: the frozen integrity identities above
   re-verify on disk.
3. `python tools/test_phase3_final_verdict_v1.py` re-passes on this tree with
   exit code 0, empty stderr, the exact terminal markers and stdout
   byte-identical to the recorded official capture.
4. The Phase-4 control plane exists (STATE, HANDOFF, STAGE_QUEUE, SCOPE,
   CONTROL_POLICY, EVIDENCE_SCHEMA, evidence/) and is deterministic.
5. The frozen queue `P4-01` .. `P4-99` is complete and no new runtime
   capability is claimed: `GENERIC_RUNTIME_STATUS=NOT_PROVEN` and the
   terminal/general compatibility markers stay reserved as `NOT_PROVEN`.
6. The working tree has no unexpected untracked paths beyond the documented
   Phase-2/Phase-3 sets and the Phase-4 control plane itself.

## P4-03 result (PASS)

Stage: \OPENRECOMP_PHASE4_RUNTIME_SERVICES_V1\. Evidence:
\.openrecomp-phase4/evidence/P4-03/\. Gate:
\	ools/test_phase4_runtime_services_v1.py\ (86 checks, sha256 \ea5f22d6...\).

Markers issued:

- Stage marker: \OPENRECOMP_P4_03=PASS- Gate marker: \OPENRECOMP_PHASE4_RUNTIME_SERVICES_V1=PASS tests=86- Terminal marker (reserved): \OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN- General compatibility marker (never promoted):
  \OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN
Delivered (additive Phase-4 files only; no frozen file modified):

- \.openrecomp-phase4/src/p4_runtime_services_v1.py\: architecture-neutral
  interface catalog (\or.runtime.exit\, \or.runtime.stream_write\),
  versioned \ServiceRegistry\, declarative \ServiceAlias\ mappings with
  bound arguments (the frozen instance handling becomes data), fail-closed
  \RuntimeServiceMediator\ (unknown/version/arity/typed/missing-handler/
  handler-failure codes, first-failure latch, explicit termination,
  deterministic call log), \AbiHostCallBridge\ for declared profile numeric
  ids, and a generic bounded byte sink.
- \	ools/test_phase4_runtime_services_v1.py\; Phase-4 manifest grown
  additively to ten entries.

Verified: all mediation failure modes return the exact stable codes; the
exact frozen external interaction from P3-08 evidence (499 output bytes plus
exit status 0) replays byte-identically through the generic mediator and
fails closed without the declared aliases; the generated source passes the
P4-01 verifier and can reach only declared service macros; the module has no
ambient host capability tokens. Two official runs byte-identical (3135 bytes
raw \cc2f73da...\, empty stderr, exit 0) with \p4_03_tests.json\ identical
across runs (\59e9879...\).

Regressions: P2-08 \PASS tests=169\, P4-01 \PASS tests=156(\81c96314...\), P4-02 \PASS tests=113\ (cfc58f1...\), Phase-1 host
gates \PASS=44 FAIL=0 SKIPPED=2\, public safety \PASS\, P4-00
\PASS tests=74\ (\953312d0...\) with the documented boundary-context
hygiene.

Limitations: the mediator is not yet the execution path of the frozen native
program (P4-08/P4-09 scope); the catalog covers control and byte-stream
interfaces only, with deterministic I/O/timing/input services reserved for
P4-04; \GENERIC_RUNTIME_STATUS=NOT_PROVEN\.

## P4-02 result (PASS)

Stage: \OPENRECOMP_PHASE4_GUEST_MEMORY_V1\. Evidence:
\.openrecomp-phase4/evidence/P4-02/\. Gate:
\	ools/test_phase4_guest_memory_v1.py\ (113 checks, sha256 \c015734...\).

Markers issued:

- Stage marker: \OPENRECOMP_P4_02=PASS- Gate marker: \OPENRECOMP_PHASE4_GUEST_MEMORY_V1=PASS tests=113- Terminal marker (reserved): \OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN- General compatibility marker (never promoted):
  \OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN
Delivered (additive Phase-4 files only; no frozen file modified):

- \.openrecomp-phase4/src/p4_guest_memory_v1.py\: explicit guest memory model
  with region kinds (code/rodata/data/bss/stack/heap), declared permissions,
  non-overlap/bounds/W^X validation, widths 8/16/32/64, explicit
  endianness, alignment policies (\llow\, equire-natural\),
  deterministic fail-closed fault kinds mapped totally to the P2-08/P4-01
  ABI failure codes, canonical state document/fingerprint, an
  \AbiMemoryService\ adapter and the pinned frozen Phase-3 instance adapter.
- \	ools/test_phase4_guest_memory_v1.py\; Phase-4 manifest grown additively
  to eight entries.

Verified: the frozen \g_image\ window (sha256 eecfc95...\, 65536 bytes)
and emitted four-region table parse exactly; the permissioned model regions
merge to exactly the emitted coverage; entry word, text/rodata/data reads,
BSS zero-fill, guest stack window inside BSS, and fail-closed writes to
headers/text/rodata are proven; widths/endianness/alignment/bounds/permission
faults are deterministic; fault-to-ABI-code mapping is total; differential
agreement with t.RuntimeMemory\ holds for allowed flat accesses. Two
official runs byte-identical (3855 bytes raw cfc58f1...\, empty stderr,
exit 0) with \p4_02_tests.json\ identical across runs (?f49e22...\).

Regressions: P2-08 \PASS tests=169\, P4-01 \PASS tests=156(\81c96314...\), Phase-1 host gates \PASS=44 FAIL=0 SKIPPED=2\, public
safety \PASS\, P4-00 \PASS tests=74\ (\953312d0...\) with the documented
boundary-context hygiene.

Limitations: the model is not yet the execution backing store of the runtime
(P4-08/P4-09 scope); permission/alignment faults map to
\MEMORY_OUT_OF_RANGE\ at the ABI boundary while the precise fault kind is
preserved in model evidence; \GENERIC_RUNTIME_STATUS=NOT_PROVEN\.

## P4-01 result (PASS)

Stage: \OPENRECOMP_PHASE4_RUNTIME_ABI_V1\. Evidence:
\.openrecomp-phase4/evidence/P4-01/\. Gate:
\	ools/test_phase4_runtime_abi_v1.py\ (156 checks, sha256 \9f2c996...\).

Markers issued:

- Stage marker: \OPENRECOMP_P4_01=PASS- Gate marker: \OPENRECOMP_PHASE4_RUNTIME_ABI_V1=PASS tests=156- Terminal marker (reserved): \OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN- General compatibility marker (never promoted):
  \OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN
Delivered (additive Phase-4 files only; no frozen file modified):

- \.openrecomp-phase4/src/p4_runtime_abi_v1.py\: executable
  architecture-neutral generated-code <-> runtime ABI V1 contract, reusing
  the frozen P2-08 \openrecomp.runtime_abi\ as the single source of truth
  for the ABI name/version, failure codes, widths, endianness and canonical
  sorted service numeric ids.
- \.openrecomp-phase4/contracts/generated_runtime_abi_v1.json\ (machine
  contract), \.openrecomp-phase4/ports/generated_runtime_abi_v1.h\ (C
  boundary header) and the declared instance profile
  \.openrecomp-phase4/ports/generated_runtime_abi_v1_profile_mips32_o32.json  (frozen Phase-3 instance: widths {8,16,32}, 32 registers, \hi\/\lo  aux accessors, services \p3.exit\=1 and \p3.uart_write\=2, pinned
  generated artifacts).
- \	ools/test_phase4_runtime_abi_v1.py\; Phase-4 manifest grown additively
  to six entries.

Verified: runtime entries (\or_rt_memory_read/write/host_call/
failure_reason\) and generated accessors (\openrecomp_*\) with exact
signatures; typed, versioned service descriptors; reserved core namespace
\or.runtime.*\ with a terminating \or.runtime.exit\; 14 P2-08 failure
codes with first-failure latching; fail-closed reference model semantics
(memory, arity, typed arguments, version, handler failure, termination,
entry-return fault, output capacity); deterministic observable state
(document + FNV-1a 64 digest, sensitive to every covered field); the frozen
\coremark_program.c\ ()99e2f0...\) and \coremark_support.c(\c5c69054...\) are compliant instances; negative sources are rejected;
the contract core surface has no fixture or platform tokens. Two official
runs byte-identical (6199 bytes raw \81c96314...\, empty stderr, exit 0)
with \p4_01_tests.json\ identical across runs (4da953d...\).

Regressions: P2-08 \PASS tests=169\, Phase-1 host gates
\PASS=44 FAIL=0 SKIPPED=2\, public safety \PASS\, P4-00 boundary
\PASS tests=74\ (byte-identical stdout \953312d0...\) re-run with the
documented frozen-gate boundary-context hygiene.

Limitations: the ABI is defined and verified but not yet implemented as a
new execution path; the fixture-specific service set is declared profile data
and is replaced by generic services in P4-03; no observable equivalence claim
is made; \GENERIC_RUNTIME_STATUS=NOT_PROVEN\.

## P4-00 result (PASS)

Stage: `OPENRECOMP_PHASE4_BOUNDARY_V1`. Evidence:
`.openrecomp-phase4/evidence/P4-00/`. Gate:
`tools/test_phase4_boundary_v1.py` (74 checks, sha256 `5be5c7d2...`).

Markers issued:

- Stage marker: `OPENRECOMP_P4_00=PASS`
- Gate marker: `OPENRECOMP_PHASE4_BOUNDARY_V1=PASS tests=74`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

Verified on branch `phase4/generic-runtime-v1` (commit
`e16e4b29b90f379615f1af97e47747cd1d531796`, the frozen Phase-3 boundary
commit):

- `openrecomp-phase3-pass` (annotated, object `ac315245...`) resolves to the
  recorded commit/tree; the branch descends from that boundary and the merge
  base is the boundary commit.
- Frozen Phase-3 evidence re-verified byte-for-byte on disk: root manifest
  `76f77bbc...` (134 entries), Phase-3 manifest `a7d0953c...` (24 entries),
  P3-99 `RESULT.json` `c893250b...`, P3-99 gate `ba581490...`, fixture
  `16a0a0aa...` (31184 bytes).
- `python tools/test_phase3_final_verdict_v1.py` independently re-passed in
  the reconstructed frozen Phase-3 verification context (temporary
  `phase3/p4-00-verification-context` branch at the same commit, untracked
  Phase-4 material held outside the worktree and restored, committed verdict
  record restored if a failed re-run overwrote it): exit 0, empty stderr,
  2498-byte stdout byte-identical to the frozen official capture (raw
  `953ec70c...`, LF `4974d03f...`), markers `OPENRECOMP_P3_99=PASS`,
  `OPENRECOMP_PHASE3_FINAL_VERDICT_V1=PASS tests=46`,
  `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=PASS`.
- Phase-4 control plane complete and deterministic; frozen queue
  `P4-01` .. `P4-99` complete and consistent with the ledger;
  `GENERIC_RUNTIME_STATUS=NOT_PROVEN`.
- Two consecutive official gate runs byte-identical raw and LF (3186 bytes,
  raw `953312d0...`, LF `03fa4c3a...`, empty stderr, exit 0) with the
  `p4_00_tests.json` artifact byte-identical across both runs
  (`1c86cebd...`).
- Worktree: only the documented Phase-2/Phase-3 untracked sets plus the
  Phase-4 control plane; the two refreshed Phase-3 evidence sidecars
  (`P3-00/p3_00_tests.json`, `P3-00/residue_manifest.txt`) are re-run
  artifacts deliberately left uncommitted.

Limitations are recorded in `.openrecomp-phase4/evidence/P4-00/RESULT.md`
(frozen-gate verification-context reconstruction; uncommitted re-run
sidecars; reserved terminal/compatibility markers).
