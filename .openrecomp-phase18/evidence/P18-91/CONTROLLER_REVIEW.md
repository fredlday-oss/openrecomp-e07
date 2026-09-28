# P18-91 Controller Review — Independent Reproduction

## Scope
Authored and executed P18-91 (independent reproduction) end to end, then audited
the result adversarially. P18-91 is a **read-only meta-stage**: it re-executes
every prior Phase-18 gate (P18-00..P18-07) from a fresh evidence root and
requires each to reproduce its committed artifacts byte-for-byte. It must never
mutate a certified stage's own evidence, and it must never promote a proof
claim.

## Inherited state (as found)
- `M .openrecomp-phase18/SOURCE_SHA256SUMS.txt` — adds
  `tools/test_phase18_independent_reproduction_v1.py`. **Legitimate integrity
  bookkeeping**: the manifest is the Phase-18 source-integrity source of truth
  and must list every tracked `src/*.py` and `tools/test_phase18_*.py`. The added
  digest `21a51a45...600` matches the gate file on disk and the
  `gate_sha256` the stage recorded for itself.
- `?? tools/test_phase18_independent_reproduction_v1.py` — the in-flight P18-91 gate.
- `?? .openrecomp-phase18/evidence/P18-91/` — the dual-run evidence.

The gate file is itself manifest-tracked, so I made **no source edits at all
during the dual run**; the run was started against a fixed tree and left alone
to completion.

## Adversarial findings
1. **Prose private-path findings are not real private paths — but must stay
   visible.** `public_safety.json` reports 4 prose findings, all labelled
   `unix-tmp-path` with `allowlisted: false`:
   `P18-00/CONTROLLER_REVIEW.md`, `P18-02/CONTROLLER_REVIEW.md`,
   `P18-03/CONTROLLER_REVIEW.md`, `P18-07/FRESH_ROOT_REPRODUCTION.md`.
   I checked each: every hit is a generic `/tmp/<repro-scratch>` reproduction
   scratch path with **no username component** (e.g. `/tmp/p1802-repro-build`,
   `/tmp/p18_recovery/P18-07-freshroot`). They are recorded repro commands, not
   host-identifying paths, and `violations: []` — the gate correctly reports
   them separately instead of silently passing or failing them. No repair needed;
   masking them would have destroyed a signal that is working as designed.
2. **Independent re-derivation, not gate self-report.** I did not accept the
   gate's own integrity record. I recomputed from the worktree:
   - `sha256sum -c SOURCE_SHA256SUMS.txt` → **28/28 OK, 0 failures**.
   - Re-hashed all 14 artifacts in `determinism.json` → **0 mismatches**.
   - `grep -r "/home/fred|/Users/|private-build" evidence/P18-91/` → **empty**
     (no private host path, no fixture bytes, no ROM content in this stage).
   - Confirmed each certified stage's own marker is present in its committed
     `run1.txt` (P18-00..P18-07 and P18-90), and that every stage's
     `declared_next_stage == result_next_stage` (the `closure.json` chain).
3. **Prior-phase integrity re-derived independently.** `prior_phase_integrity.json`
   reports `untouched: true`, `changed_paths: []`, `dirty_paths: []`,
   `tag_resolves_to_terminal: true` against the frozen authority commit
   `d7cc5d09...` — Phase 1..17 namespaces remain byte-frozen under this stage.

## What P18-91 verifies
- Re-executes all 8 upstream gates (P18-00..P18-07) from a fresh evidence root.
  All 8 reproduce their committed artifacts **byte-for-byte identical**
  (`stages_reproduced_identical: true`, `reproduction.all_ok = true`).
- Independent re-run of the P18-90 integrated regression's own dual-run corpus
  (`dual_run_corpus.json ok: true`): for each stage, the recorded dual-run
  artifacts and transcripts match across both official runs.
- Transcript hash-binding: P18-02 `transcript.json` and P18-03
  `causal_transcript.json` digests bound to their recorded values.
- Source-manifest exactness: 28 entries, no missing/extra/duplicate, all digests
  verify against the live tree.
- Prior-phase integrity and marker ledger: no protected claim promoted; all
  `OPENRECOMP_PHASE18_*` claims `NOT_PROVEN`, `FIRST_FRAME_READY=NO`; Phase-17
  markers preserved.
- Public safety: no private host path or reconstructive key in this stage's
  evidence.
- 8 fail-closed negative controls, all correctly detecting tamper
  (artifact, manifest-digest, frontier-digest, marker-promotion,
  stale-digest) and correctly *not* forgiving integrity/semantic tampering.

## Independent re-runs (controller-owned)
- **Authoritative dual-run stage runner** on the final tree:
  `runner_status=PASS`, `EXIT=0`; both runs rc=0, stdout byte-identical
  (`fbe18578...` raw *and* LF), stderr empty in both, tests-JSON present and
  identical in both, 14 artifacts byte-identical. Gate `P18-91_CHECKS=94`, 0 failed.
- The two official runs are separated in time by ~39 minutes on independent
  process trees, so the determinism claim is not an artifact of a single
  warm-cache pass.

## Verdict
P18-91 PASSES. As required for a read-only meta-stage, it **promotes no broader
proof claim**: `FIRST_FRAME_READY=NO` and the
initialization/frame/playability/general-compatibility markers remain
`NOT_PROVEN`. It certifies that the Phase-18 evidence corpus is independently
reproducible, not that anything about PS1 emulation is proven.
`promotes_no_proof_marker: true`, `proves_nothing_about_emulation: true`.
next_stage: **P18-99** (terminal closure).
