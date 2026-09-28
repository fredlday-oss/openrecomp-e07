# P18-90 Controller Review — Integrated Regression

## Scope
Recovered and completed the in-flight P18-90 work. The controller inspected
the live worktree before touching anything, classified the two inherited
uncommitted edits, preserved valid work, and repaired only what was incomplete.

## Inherited state (as found)
- `M .openrecomp-phase18/SOURCE_SHA256SUMS.txt` — added the two new P18-90
  source files. **Legitimate integrity bookkeeping** (the manifest is the
  Phase-18 source-integrity source-of-truth and must list every tracked
  `src/*.py` and `tools/test_phase18_*.py`).
- `M .openrecomp-phase18/evidence/P18-06/FRESH_ROOT_REPRODUCTION.md` — the
  committed procedure line named a real `/home/fred/OpenRecomp/private-build/...`
  path; the edit masks it to `<private-build-root>`. **Legitimate public-safety
  repair** (no semantic change to the recorded result or digests).
- `?? .openrecomp-phase18/src/p18_regression_v1.py`, `?? tools/test_phase18_whole_regression_v1.py`,
  `?? .openrecomp-phase18/evidence/P18-90/` — the in-flight P18-90 regression
  helpers, gate and dual-run evidence.

## Adversarial findings and repairs
1. **Stale pre-repair digest presented as current authority.** `STATE.md:114`
   and `HANDOFF.md:78,88` still declared the *pre-repair* P18-04 frontier
   digest `297a5493...be58b` as the current value, contradicting the recovery
   note in the same documents. Repaired: those lines now carry the repaired
   digest `a009003b...bfe9` (or are explicitly marked as superseded history).
2. **The inherited gate did not audit the failure mode the brief calls out.**
   It verified frontier digests but never checked that the stale digest is
   absent from authoritative evidence, never checked STATE/HANDOFF/STAGE_QUEUE
   agreement, and never asserted that the P18-05/P18-06 revalidations remain
   valid. Added three read-only audits (`audit_control_documents`,
   `audit_stale_frontier_digest`, `audit_revalidation`) and wired them into the
   gate, each with non-vacuous negative controls.

## What P18-90 verifies
- P18-00..P18-07 each PASS with schema-conformant `RESULT.json`, correct
  stage/next_stage chaining and the frozen authority commit.
- Source-manifest exactness: 27 entries, no missing/extra/duplicate, all
  digests verify.
- Repaired P18-04 authority is used: P18-04/05/06 frontier JSON digests match
  their recorded `.sha256` and the P18-07 consumer's `frontier_digests`.
- No stale pre-repair digest survives in any authoritative JSON evidence, and
  no control document cites it without an explicit supersession marker.
- Phase 1..17 namespaces untouched vs the frozen terminal commit; the
  `openrecomp-phase17-pass` tag resolves to the terminal commit.
- Marker ledger: no protected claim promoted; all `OPENRECOMP_PHASE18_*`
  claims `NOT_PROVEN`, `FIRST_FRAME_READY=NO`; Phase-17 markers preserved.
- Public safety: no private host paths or reconstructive keys in JSON evidence.
- Negative controls (14) all fail closed.

## Independent re-runs (controller-owned)
- Authoritative dual-run stage runner: `runner_status=PASS`, identical raw and
  LF stdout, empty stderr both runs, byte-identical artifacts, `P18-90_CHECKS=142`.
- Fresh/private-root reproduction: byte-identical on every semantic artifact;
  the sole divergence is the runner's self-recorded output-directory string in
  `official_runs.json` (non-semantic, same exclusion class as P18-07).

## Verdict
P18-90 PASSES. It promotes no broader proof claim: `FIRST_FRAME_READY=NO` and
the initialization/frame/playability/general-compatibility markers remain
`NOT_PROVEN`. next_stage: P18-91.
