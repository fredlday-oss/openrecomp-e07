# P3-00 — Phase-3 boundary

VERDICT: `PASS`

Stage: `OPENRECOMP_PHASE3_BOUNDARY_V1`. Branch: `phase3/mips32-real-elf-v1`.
Gate: `tools/test_phase3_boundary_v1.py` (61 checks).

## Markers

```text
OPENRECOMP_P3_00=PASS
OPENRECOMP_PHASE3_BOUNDARY_V1=PASS tests=61
OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN
```

## What was proven

1. The Phase-2 frozen tag `openrecomp-phase2-pass` (annotated object
   `1a7f241b69d9500095fe84db16520ec1001db1aa`) resolves to commit
   `01b1d7cba8c931fca95d041389cfb1902b7c89fe`, tree
   `6513eefa5ef59b7d0e127f0179c6fc6c21fdac78`; the Phase-3 branch descends
   from that boundary (`git merge-base` equals the boundary commit); the
   Phase-1 tag remains `46c2f971e1a42cf49bd936bad94697b81bf31002`.
2. Phase-2 final evidence is unchanged on disk: `SOURCE_SHA256SUMS.txt`
   (134 entries, sha256 `76f77bbc...`), `P2-99/RESULT.json`
   (`880d2596...`), the P2-99 gate (`8d6a42d5...`), `P2-99/run1.txt` and
   `run2.txt` (`66913e57...`), the frozen P2-90 capture (`74e9eada...`), the
   LF-normalized terminal P2-99 capture (`ac9c0b8a...`), and the six restored
   P2-90 capture files.
3. `python tools/test_phase2_final_verdict_v1.py` (verify-only) still passes:
   exit 0, empty stderr, stdout byte-identical to the four recorded official
   terminal runs (raw sha256 `66913e57...`, 7799 bytes).
4. The frozen verification context is preserved: the 28 recorded
   verification-context files exist on disk with canonical manifest sha256
   `40e4f23a35f40c5d25da630467d46f5e8ad8409a40efff8412892217447a8349` and
   remain untracked.
5. The Phase-3 control plane (CONTROL_POLICY, SCOPE, STAGE_QUEUE, STATE,
   HANDOFF, evidence/) exists and is deterministic: no absolute host paths,
   timestamps, UUIDs or process identity; `COREMARK_STATUS=NOT_PROVEN`;
   `FINAL_VERDICT=NOT_PROVEN`; the queue reserves the terminal marker.
6. No unexpected untracked paths: only the documented Phase-2 residue
   (275 files, manifest sha256 `18e503bf...`), the frozen
   verification-context files and the Phase-3 control plane.

## Verification context note

The freeze commit `b935699` (Phase-2 close) was followed by
`01b1d7c` (verification-context correction) on this branch: 28 files whose
tracking changes the frozen verification context (27 UTF-16LE captures that
the strict-UTF-8 Phase-1 `public-safety-scan` gate rejects as tracked text,
and `tools/test_build_package_reproducibility_v1.py`, which contains the
literal private-key rejection needle exercised by its own content-policy
test) were removed from the index while their bytes remain on disk,
hash-pinned by the frozen manifest and evidence. With that correction the
full Phase-1 host gate suite passes (`PASS=44 FAIL=0 SKIPPED=2`) and the
P2-99 terminal gate re-passes byte-identically. The tag was moved to the
corrected commit before any Phase-3 implementation work began.

## Determinism

Two consecutive official gate runs produced byte-identical stdout (2675
bytes, raw sha256
`a039bbffa55afd786e7b44427c5aafe0b09aff6f8309e1e6c643ad812b5b7c73`,
LF sha256
`02664e80d78ae03d66767c472fcc8a2cc65b0fb90cf2efdb3cbbf3c6b5efff7c`) with
empty stderr; captures `run1.txt`, `run2.txt`, `run1.err.txt`,
`run2.err.txt` and `gate_determinism.txt`.

## Evidence in this directory

- `RESULT.md` (this record).
- `p3_00_tests.json`: machine-readable gate record (checks and findings).
- `run1.txt`, `run2.txt`, `run1.err.txt`, `run2.err.txt`,
  `gate_determinism.txt`: the two official deterministic runs.
- `p2_99_reverify_stdout.txt`, `p2_99_reverify_stderr.txt`: the byte-exact
  terminal P2-99 re-verification capture.
- `frozen_untracked_manifest.txt`: sha256 manifest of the 28 preserved
  verification-context files.
- `control_plane_manifest.txt`: sha256 manifest of the Phase-3 control plane.
- `residue_manifest.txt`: sha256 manifest of the documented untracked
  Phase-2 residue.

## Next stage

P3-01 — CoreMark MIPS32 fixture acquisition/build. CoreMark remains
`NOT_PROVEN`; no Phase-3 claim is issued by P3-00.
