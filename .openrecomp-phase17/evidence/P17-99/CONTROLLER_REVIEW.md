# Controller review — P17-99 (terminal Phase-17 closure)

Candidate (worker): `8886f2d2e07f903cddb9c5ae6aade9bfe956dbde` — 10 commits
atop `b1bace7c6c39403c49b9168a880082b91b168553`; worker branch
`agent/deepseek-phase17-p17-99-r1`; candidate tree
`1770c180e275709d5544e1edc2b538f3a373e5a7` (27 files added/changed).
Integrated authority: controller branch `phase17/ps1-title-overlay-recompile-v1`;
pre-integration controller HEAD `b1bace7c6c39403c49b9168a880082b91b168553` (tree
`920e3b785fda92d027f783ee50b82d578e82c01a`).
**Verdict: ACCEPT.** Integrated by fast-forward (no merge commit).

## 1. Provenance and structure

- `git rev-list --count b1bace7..8886f2d` = 10. Linear; no merge, no history
  rewrite, no rebase.
- Changed files are strictly additive under `.openrecomp-phase17/` plus the two
  new Phase-17 sources: `p17_terminal_closure_v1.py` (new src module),
  `tools/test_phase17_terminal_closure_v1.py` (new gate), the regenerated
  `P17-99/` evidence directory, the manifest, and the four Phase-17 control
  documents (STATE/HANDOFF/STAGE_QUEUE/REVIEW_REQUIRED). No Phase-1..16 file,
  no prior-stage evidence file, and no shared runtime file was modified.
- Worker worktree `coder-deepseek-p17-99-r1` is clean; no uncommitted residue.

## 2. The canonical terminal marker

The mission warned against inventing the marker name and told me to discover the
repository-defined one. Discovery:

- `p17_contracts_v1.py` defines `TERMINAL_VERDICT_MARKER = "OPENRECOMP_P17_99"`
  as the stage marker, but no `OPENRECOMP_PHASE17_TERMINAL_V1` token existed
  anywhere in the repository or its history (`git grep` across every ref, and a
  filesystem search, both empty).
- There is therefore **no** pre-existing `..._TERMINAL_V1` token to adopt.
  The mission's "expected conceptually" value `OPENRECOMP_PHASE17_TERMINAL_V1`
  is the only Phase-17-family terminal token consistent with the historical
  naming convention (`OPENRECOMP_PHASE16_*`, `OPENRECOMP_PHASE17_*_V1`) and is
  recorded here with that explicit provenance rather than being passed off as a
  previously-defined marker. `supporting stage marker = OPENRECOMP_P17_99`.

This is an honest, documented naming decision, not an invented pre-existing
token, and both markers are emitted by the gate and recorded in RESULT.json.

## 3. Independent reproduction

I did not take the determinism claim on trust. In a separate review worktree
(`controller-review-p17-99`, detached at the candidate) I re-ran the official
stage runner with a **fresh private build root**:

- runner_status PASS, `identical_raw` / `identical_lf` true,
  `returncode_zero_both` true, `stderr_empty_both` true,
  `markers_present_both` true, `tests_json_present_both` true;
- the regenerated 22-file evidence directory is **byte-identical** to the
  committed evidence (`diff -rq` empty), and the review worktree's
  `git status --porcelain` stayed empty;
- run1 sha256
  `92087d57b37b8136e56acf966d619395426c05e02b30ee4b335a1d22cdcc03e8`,
  identical run-to-run;
- `P17-99_CHECKS=105`, zero `FAIL:` lines.

Two divergences were found by the controller during review and repaired by the
worker before acceptance, not waived:

1. the *first* generation embedded the live `gate_head`/`gate_tree` in
   RESULT/verdict/terminal_binding, which made the evidence a function of the
   commit that contains it and diverged on in-place regeneration — replaced by
   a commit-independent binding (certified authority commit+tree, live HEAD is a
   descendant of the authority);
2. the verdict echoed the *live branch name*, which differed between the worker
   worktree and the detached review worktree — the branch echo was dropped.

After both fixes the controller's fresh-root run reproduces the committed
evidence byte-for-byte.

## 4. What the terminal gate independently establishes

- **Stage chain:** P17-00, P17-01, P17-02, P17-03, P17-04R, P17-05R, P17-06R,
  P17-07R, P17-90, P17-91 all `status=PASS` with their required markers and an
  unbroken `next_stage` chain (the P17-03 `next_stage: P17-04` is the recorded
  alias for its reviewed successor P17-04R).
- **Prior-phase integrity:** `git log` over `.openrecomp-phase1..16` since the
  Phase-16 baseline is empty; all **16** tree object ids equal the baseline;
  the worktree is clean over those paths. No Phase 1..16 evidence modification.
- **Provenance chain:** each certified commit (P17-04R `0ab4e7e`, P17-05R
  `b18fd4b`, P17-06R `2701415`, P17-07R `b553f70`, P17-90 `5352895`, P17-91
  `84e3e8a`) resolves and is an ancestor of the authority commit.
- **Manifest:** 43 tracked Phase-17 sources re-derived from `git ls-files` with
  matching digests; the terminated-source check is exact.
- **Marker ledger:** every protected claim marker is `NOT_PROVEN` and
  `FIRST_FRAME_READY=NO` across all stage RESULT.json files, STATE, and
  STAGE_QUEUE; no marker promoted.
- **REVIEW_REQUIRED:** the historical P17-04..P17-07 stop is retired
  (`REVIEW_REQUIRED_TERMINAL_STATE=RETIRED`), and the check fails closed if the
  historical "required next action" sentence is still active without that
  declaration.
- **Terminal binding:** certified authority commit resolves to exactly the
  recorded tree; live HEAD is a descendant.
- **Marker syntax:** clean over STATE/STAGE_QUEUE/REVIEW_REQUIRED and the stage
  transcripts (no `NAME=PASS=PASS`, no `NOT_PROVEN=PASS`).
- **Public safety:** 155 committed corpus documents scanned; zero unallowlisted
  private host paths; zero reconstructive keys; controller-review prose clean.
- **Cited terminal evidence:** the P17-06R transcript digest
  `d7e222c87726748ced23dd60c2b1ba138625227c984dac587be6a5761695fd3a` is
  re-derived and matches the P17-07R binding and its 8340 provenance digests.
- **Negative controls:** 10 terminal tamper cases, all detected (missing stage,
  non-PASS status, promoted marker, stale review action, corrupted manifest
  digest, non-ancestor provenance, unresolvable binding, promoted marker syntax,
  fabricated private path, unresolvable prior baseline).

## 5. Honesty boundaries preserved

No proof marker is promoted. `FIRST_FRAME_READY=NO`;
`OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF`,
`..._FRAME_PROOF`, `..._PLAYABILITY_PROOF` and
`OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY` remain `NOT_PROVEN`. The accepted
runtime conclusion is unchanged and bounded: the checked device frontier is
dominated by a zero-returning GPUSTAT wait-poll (1586 of 1590 recorded device
events). `next_stage=NONE`, `PHASE18_STARTED=NO`.

## 6. Decision

ACCEPT and INTEGRATE by fast-forward. The complete Phase-17 chain is internally
consistent and terminally closed. Phase 18 is not started.
