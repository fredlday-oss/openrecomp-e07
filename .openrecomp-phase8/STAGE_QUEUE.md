# OpenRecomp Phase 8 Stage Queue

Only one stage may be active at a time. Rows `P8-01` .. `P8-99` are frozen at
the P8-00 `PASS` boundary, effective before any P8-01 implementation work.

| Stage | Name | Status | Required outcome |
|---|---|---|---|
| P8-00 | Phase-8 boundary + acceleration control plane | PASS | Verify the exact frozen Phase-7 baseline and clean Phase-8 branch boundary, record compiler/toolchain versions, establish the Phase-8 control plane, freeze the stage queue, define the fast-gate vs terminal-gate policy, the analysis-cache key contract and the incremental-build policy, and verify the Phase-7 terminal evidence remains untouched. No substantive MIPS implementation |
| P8-01 | Real redistributable MIPS32 ELF fixture | QUEUED | Select and freeze one legally redistributable compiler-produced MIPS32 ELF: legitimate redistribution licence, documented source/provenance, SHA-256, ELF identity (endian/ABI/entry/segments/sections), reproducible acquisition/build path where practical, no proprietary SDK dependency. Prefer a fixture complex enough to exercise real compiler-produced behaviour but small enough to keep the loop fast |
| P8-02 | Existing MIPS32 pipeline re-derivation | QUEUED | Run the frozen fixture through the existing ELF ingestion, target policy, decode, semantics inventory, executable-region discovery and reachable-code frontier. Classify the exact current frontier into already supported, recognized but unsupported, unresolved control flow, ABI/runtime gap, memory-image gap, translation gap, host-emission gap and toolchain/build gap. Produce a deterministic frontier report. PASS means the frontier is completely and reproducibly characterized, not that the ELF is executable |
| P8-03 | Real-ELF ProgramModel / CFG integration | QUEUED | Drive the real ELF through the existing neutral ProgramModel, CFG, function discovery, call graph and translation-unit structure. Fix only evidence-demonstrated gaps. Indirect control flow must be exact, a finite evidence-supported set, or unresolved/fail-closed. No guessed targets |
| P8-04 | Translation frontier closure | QUEUED | Close the minimum translation/semantics gaps required by the reachable real fixture: architecture-neutral fixes where possible, no mutation of frozen IR V1 semantics, use existing later feature contracts where applicable, independent tests/reference vectors for new semantic behaviour. Every reachable translated instruction is proven translatable or explicitly unresolved (in which case Phase 8 cannot advance to native proof) |
| P8-05 | Static memory + runtime contract closure | QUEUED | Validate the fixture's executable memory, `.rodata`, initialized `.data`, zero-filled `.bss`, stack requirements, bounded guest memory access and host-service requirements. Reuse the existing memory/runtime architecture. Do not emulate a Linux kernel unless the fixture genuinely requires one; prefer a bounded fixture with explicit host requirements |
| P8-06 | Host-source emission | QUEUED | Feed the bounded real MIPS32 program through the existing architecture-neutral host emitter: deterministic generated source, stable generated filenames, content hashes, unchanged input => byte-identical output, no original MIPS32 machine code executed at runtime, generated host code only |
| P8-07 | Incremental native build | QUEUED | Compile the generated host program through the existing host-native toolchain/runtime boundary using incremental build/caching during development, and record one clean build path for later terminal verification: deterministic build inputs, existing warning policy, explicit toolchain provenance, no source-ROM/binary embedding beyond permitted initialized data required by the fixture's redistribution licence |
| P8-08 | Deterministic native execution | QUEUED | Execute the generated native program and define a bounded observable record (exit value, guest registers at an agreed boundary, guest memory digest, output/service transcript, operation/event counts, relevant runtime state). Run the official gate twice and require deterministic result evidence |
| P8-09 | Independent reference equivalence | QUEUED | Build/use an independently structured MIPS32 reference path that does not merely call the same translated semantics implementation and compare it with itself. Compare the bounded native result against the reference over all required observables. Any intentional difference must be explicitly characterized, justified, proven bounded and included in evidence. No unexplained semantic delta is permitted for PASS |
| P8-10 | Reusable real-MIPS32 ELF-to-native workflow | QUEUED | Create a deterministic reusable workflow for the proven bounded path (ELF -> classification -> analysis -> translation -> host generation -> native build -> execution -> result evidence). Unsupported cases fail closed with explicit categories including unsupported ELF/container feature, unsupported ISA/semantic feature, unsupported ABI requirement, unresolved indirect control flow, unsupported memory/runtime requirement, toolchain unavailable, build failure and reference mismatch |
| P8-11 | Fail-closed hardening | QUEUED | Add focused negative tests for Phase-8 mechanisms, including malformed/unsupported cases related to the new work. Verify deterministic rejection, no guessed recovery, no silent compatibility widening, no stale-cache acceptance, and no generated-code execution after a required earlier classification failure. Not a general fuzzing project |
| P8-12 | Phase-8 evidence closure | QUEUED | Re-run the bounded public MIPS32 path from clean inputs and verify fixture identity, analysis-cache correctness, generated-source identity, native result identity, reference equivalence, workflow reproducibility and source/manifests/evidence consistency. Record explicitly if zero implementation delta is needed |
| P8-90 | Whole-project regression | QUEUED | Run the expensive historical frozen regression chain: verify Phase-1 through Phase-7 frozen behaviour plus all Phase-8 official gates. Do not optimize this gate at the expense of audit strength. Capture exact test/gate counts and deterministic evidence |
| P8-91 | Evidence index + proof matrix | QUEUED | Build the final Phase-8 evidence index separating PROVEN (the exact public Phase-8 real-ELF bounded native path), BOUNDED/PASS (specific ISA/ABI/memory/runtime behaviours actually exercised) and NOT_PROVEN (general MIPS32 compatibility, arbitrary ELF compatibility, unsupported ISA families, broader ABI/OS/runtime claims). Verify no public evidence contains unauthorized/private binary material |
| P8-99 | Final bounded verdict | QUEUED | Audit every Phase-8 stage; require all required stage records PASS, P8-90 and P8-91 PASS, exact frozen public fixture provenance, native/reference agreement and general-compatibility scope guards. Only then emit `OPENRECOMP_P8_99=PASS`, `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=PASS` and `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`. Otherwise emit `OPENRECOMP_P8_99=FAIL`, the terminal proof `NOT_PROVEN` and the general marker `NOT_PROVEN`. Do not soften a failed audit |

## Queue freeze

Frozen at the P8-00 `PASS` boundary, before any P8-01 implementation work.
The rows `P8-01` .. `P8-99` above are the complete frozen contract: stage IDs,
names, ordering and required-outcome scope. The freeze does not change any
stage status: each row becomes active only when its own gate is executed.

Frozen-queue rules:

1. No renumbering, insertion, merging, splitting or silent redefinition of a
   frozen stage is permitted.
2. A frozen stage may change only if a genuine technical dependency makes the
   existing frozen stage impossible to execute as written. Such a change must
   fail closed: the stage stops with an explicit
   `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` /
   `BLOCKED_BY_MISSING_EXTERNAL_TOOLCHAIN` /
   `QUEUE_RECONCILIATION_REQUIRED` record instead of silently adapting, the
   forcing evidence is captured, and the frozen rows are updated explicitly in
   the reconciliation log below.
3. A stage gate must not silently relax a frozen stage's required outcome.
4. The freeze is a control-plane record only. It adds no capability claim and
   changes no frozen Phase-1 through Phase-7 boundary.

## Reconciliation log

- Phase-6 baseline tag (documented at P7-00 and re-verified at P8-00): the
  mission baseline names an annotated tag `openrecomp-phase6-pass`, but the
  frozen Phase-6 P6-99 record states that no terminal tag was created or
  required. Phase 7 records `BASELINE_TAG_STATUS=ABSENT_RECONCILED`. Phase 8
  inherits that reconciliation and does not fabricate or create a Phase-6 tag.
- Phase-7 authority (documented at P8-00): the Phase-8 baseline is the
  annotated tag `openrecomp-phase7-pass` -> commit
  `2917aa6549ab975cffdeb50120514c1723f7e493` -> tree
  `59529c130d759ceb1ca9e6c65a510fa373656b01`. The separately tagged
  `openrecomp-phase7-pass-v2` hardening line (branch `phase7/hardening-v2`) is
  outside this baseline and is neither used nor modified.
- Queue freeze (control-plane only, documented): the P8-00 `PASS` boundary
  froze rows `P8-01` .. `P8-99` exactly as written above.
- No other reconciliation has been required.

## Success markers

- `OPENRECOMP_P8_00=PASS`
- terminal Phase-8 marker (reserved `NOT_PROVEN` at every stage before P8-99):
  `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF`
- permanent general marker (never promoted):
  `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`
- P8-99 verdict markers:
  `OPENRECOMP_P8_99=PASS` only with
  `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=PASS` for the exact audited
  bounded fixture/behaviour; otherwise `OPENRECOMP_P8_99=FAIL`,
  `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`.
