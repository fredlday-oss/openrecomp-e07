# OpenRecomp Phase 3 Stage Queue

Only one stage may be active at a time. Stages marked `QUEUED` are provisional;
the P3-01 ELF/instruction inventory defines the evidence-supported boundaries
and acceptance criteria of the later stages and may reconcile this queue
(documented, control-plane only).

The remaining queue (`P3-05` .. `P3-99`) was frozen at the P3-04 `PASS`
boundary; see `## Queue freeze` below. The freeze is effective before any
P3-05 implementation work.

| Stage | Name | Status | Required outcome |
|---|---|---|---|
| P3-00 | Phase-3 boundary | COMPLETE | Phase-2 frozen tag resolves, Phase-3 branch descends from the Phase-2 PASS commit, Phase-2 final evidence unchanged, P2-99 verification re-passes byte-identically, Phase-3 control plane deterministic; CoreMark not treated as proven or supported |
| P3-01 | CoreMark MIPS32 fixture acquisition/build | COMPLETE | CoreMark pinned at `1f483d5b...`; recorded license/hashes, Zig 0.13.0 toolchain identity and exact flags; reproducible ELF32 LE O32 static soft-float non-PIC `-O1` build (`16a0a0aa...`); full ELF/section/data/symbol/relocation/instruction/unsupported inventory |
| P3-02 | ELF ingestion + section/data image | COMPLETE | Fail-closed ELF32 MIPS ingestion; validated class/endian/machine/entry/program headers/sections; deterministic guest data image with bounds-checked access |
| P3-03 | MIPS32 decode expansion | COMPLETE | Inventory-driven decode coverage for the P3-01 unsupported classes (`movz`, `movn`, `mul`, `divu`+`teq`, `swl`/`swr`, `jalr`, padding); unsupported encodings stay classified and fail closed |
| P3-04 | CoreMark reachable MIPS32 semantics | COMPLETE | Exact table of the 82 recognized-unsupported words with reachability/function/implementation status; exact MIPS32 semantics implemented and reference-verified for the instruction classes required by the reachable CoreMark path; the six reachable exception-frontier sites classified with evidence; unresolved indirect-control-flow `jr $at` frontiers and the dead `jalr` carried forward, never guessed |
| P3-05 | ProgramModel/CFG/functions/call graph/translation units on the real ELF | ACTIVE | Shared Phase-2 layers exercised on the real program with unchanged shared-layer neutrality; indirect targets never guessed |
| P3-06 | Static data/global reconstruction | QUEUED | `.rodata`/`.data`/`.bss` and GP-relative/absolute global access modelled explicitly and verifiably |
| P3-07 | Host emission for CoreMark semantics | QUEUED | Deterministic generated host code for the proven subset; unsupported or external behaviour fails closed or is explicitly runtime-mediated |
| P3-08 | Native build + generic runtime execution | QUEUED | Deterministic native host build of the generated program; execution through the generic runtime ABI with bounded I/O and deterministic benchmark inputs |
| P3-09 | Independent MIPS32 reference + equivalence | QUEUED | Independent MIPS32 reference execution and deterministic observable equivalence against the native host executable |
| P3-10 | Reproducible package + whole regression | QUEUED | Byte-reproducible package for the Phase-3 path; Phase-1, Phase-2 and Phase-3 gates pass together |
| P3-90 | Phase-3 whole regression | QUEUED | Deterministic whole-project regression audit of the completed Phase-3 stages plus preserved Phase-1/Phase-2 gates |
| P3-91 | Evidence index + limitations | QUEUED | Complete Phase-3 evidence index and explicit bounded/unproven claim record |
| P3-99 | Final verdict | QUEUED | Phase-3 verdict issued only if the bounded end-to-end real-ELF claim is proven on the audited tree |

## Queue freeze

Frozen at the P3-04 `PASS` boundary, before any P3-05 implementation work. The
rows `P3-05` .. `P3-99` above are the complete frozen contract: stage IDs,
names, ordering and required-outcome scope. The freeze does not change any stage
status: `P3-05` is the stage being executed and `P3-06` .. `P3-99` remain
`QUEUED` until their own gates pass.

Frozen-queue rules:

1. No renumbering, insertion, merging, splitting or silent redefinition of a
   frozen stage is permitted.
2. A frozen stage may change only if a genuine technical dependency makes the
   existing frozen stage technically impossible to execute as written. Such a
   change must fail closed: the stage stops with an explicit
   `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` / `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN`
   record instead of silently adapting, the forcing evidence is captured, and
   the frozen rows are updated explicitly in the reconciliation log below.
3. A stage gate must not silently relax a frozen stage's required outcome; a
   gate that cannot satisfy the frozen contract fails closed.
4. The freeze is a control-plane record only. It adds no capability claim and
   changes no Phase-1/Phase-2 frozen boundary.

## Reconciliation log

- Queue freeze (control-plane only, documented): the P3-04 `PASS` boundary
  froze rows `P3-05` .. `P3-99` exactly as written above. No stage was
  renumbered, inserted, merged, split or redefined by the freeze.
- P3-04 (control-plane only, documented): the pre-P3-04 queue assigned P3-04 to
  "ProgramModel/CFG/functions/call graph/translation units on the real ELF".
  The P3-03 evidence established the exact reachable MIPS32 semantic frontier
  (55 reachable recognized-but-unsupported instructions in the P3-01 classes
  plus three unresolved `jr $at` jump-table frontiers) and, under the queue's
  own reconciliation clause, P3-04 is the reachable-semantics stage. The queued
  structure stage moves to P3-05 and the provisional stages after it shift by
  one ID (static data P3-06, host emission P3-07, native build/runtime P3-08,
  independent reference P3-09, reproducible package P3-10). P3-90/P3-91/P3-99
  are unchanged. No completed stage evidence is affected.

## Success markers

- queue freeze: rows `P3-05` .. `P3-99` are frozen by the `## Queue freeze`
  section above (P3-04 `PASS` boundary, control-plane record)
- `OPENRECOMP_P3_00=PASS`
- `OPENRECOMP_PHASE3_BOUNDARY_V1=PASS tests=<count>`
- `OPENRECOMP_P3_04=PASS`
- `OPENRECOMP_PHASE3_COREMARK_REACHABLE_SEMANTICS_V1=PASS tests=<count>`
- terminal Phase-3 marker: reserved, value `NOT_PROVEN`

## Failure values (not issued)

- `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN` (current terminal state)
