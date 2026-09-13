# OpenRecomp Phase 2 State

PHASE=2
BASELINE_TAG=openrecomp-phase1-pass
BASELINE_COMMIT=46c2f97
CURRENT_STAGE=P2-01
LAST_PASSED_STAGE=P2-00
STATUS=READY
FINAL_VERDICT=NOT_YET_EVALUATED

## Stage ledger

| ID | Stage | Status | Evidence |
| --- | --- | --- | --- |
| P2-00 | Baseline + control plane | `PASS` | `.openrecomp-phase2/evidence/P2-00/RESULT.md` |

## P2-00 result (PASS)

- Phase-1 tag `openrecomp-phase1-pass` (annotated object `8dbbd79…`, commit
  `46c2f971e1a42cf49bd936bad94697b81bf31002`) verified; `HEAD` equals the freeze
  and `git merge-base --is-ancestor 46c2f97 HEAD` is satisfied.
- No Phase-1 semantic source changed. Only `SOURCE_SHA256SUMS.txt` was repaired
  (5 stale/line-ending-inconsistent hashes regenerated via `update_sums.py`;
  109 entries before and after). `AGENTS.md` is the installer's Phase-2 control block.
- Full host gate suite on this fresh Phase-2 worktree: `44 PASS / 0 FAIL / 2
  SKIPPED` (`OPENRECOMP_PHASE1_HOST_GATES_V1=PASS`), matching the Phase-1 record.
  Skipped: `e07-hardened-end-to-end`, `external-repro-v1` (missing `clang`/`gcc`/POSIX).
- Baseline defect found and repaired: the frozen `SOURCE_SHA256SUMS.txt` did not
  match the committed files (CRLF-origin hashes for 3 files; never-committed working
  bytes for 2). See `evidence/P2-00/RESULT.md`.
- Reusable components and P2-01 coupling blockers inventoried in
  `evidence/P2-00/RESULT.md`.

## Next exact action

Begin P2-01 — persistent program representation: add a new versioned
architecture-neutral program/function/block/instruction schema with deterministic
serialization, keeping frozen IR V1 / Module Image V1 unchanged. Preserve the
`direct_call_graph` (direct calls only) vs unresolved-indirect separation and
PROVEN vs CANDIDATE provenance. Do not modify Phase-1 semantic source.

## Carried-forward findings

- `update_sums.py` globs `schemas/*.json` while the directory is `schema/`, so
  `schema/*.json` is not covered by `SOURCE_SHA256SUMS.txt` (pre-existing; deferred).
- Toolchain-gated gates remain unexecutable on this host.
- Future integration point: accept later PS2/R5900 evidence through the adapter/frontend
  descriptor seam without duplicating or anticipating the other PC's unmerged work.

## Git status (short)

- Modified: `AGENTS.md` (installer), `SOURCE_SHA256SUMS.txt` (P2-00 repair).
- Untracked: `.openrecomp-phase2/`, plus generated `artifacts/mips32_translation_v1/`
  and `artifacts/mips32_translation_evidence_closure_v1/` from the MIPS32 gate run.
- No commit created.
