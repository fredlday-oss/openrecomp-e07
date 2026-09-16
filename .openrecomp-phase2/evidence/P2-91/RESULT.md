# P2-91 — Phase-2 evidence index, limitations and final-claim preparation

VERDICT: `PASS`

SUCCESS MARKERS:

```text
OPENRECOMP_P2_91=PASS
OPENRECOMP_PHASE2_EVIDENCE_CLOSURE_V1=PASS tests=882
OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=NOT_PROVEN
```

Stage: `OPENRECOMP_PHASE2_EVIDENCE_CLOSURE_V1`. Branch: `phase2/opencode-v1`.
P2-91 is a closure/documentation/evidence stage: it adds no architecture feature
and broadens no compatibility claim.

## Objective

Create the authoritative Phase-2 evidence index and limitations record, resolve
the nine pre-existing host-path occurrences identified by P2-90 without
invalidating frozen PASS evidence, add a recurrence guard, and prepare the
repository for the P2-99 final verdict. The final verdict marker stays reserved
for P2-99 and remains `NOT_PROVEN`.

## Deliverables

- `PHASE2_EVIDENCE_INDEX.md` / `PHASE2_EVIDENCE_INDEX.json`: authoritative index
  of all 23 completed stages (P2-00, P2-01..P2-14, P2-20..P2-23, P2-30, P2-40,
  P2-50, P2-90). Every stage records its PASS marker, gate marker, check count,
  evidence directory, principal RESULT file, fixture/input identity,
  generated/executable/package identity, deterministic-run identity and claim
  boundary. Every indexed identity is re-verified against frozen stage evidence;
  every indexed reference resolves.
- `PHASE2_LIMITATIONS.md`: authoritative bounded/unproven claims record with the
  shared 23-key claim vocabulary and the explicit final-marker reservation.
- `PHASE2_CLAIM_MATRIX.md`: every major public-facing claim mapped to supporting
  evidence and a claim boundary. The eighteen P2-90 claims keep their audited
  classification; five closure claims are added (deterministic
  ProgramModel/CFG/function/call-graph/translation pipeline; fail-closed
  unsupported-service behavior; provenance and legal-asset policy enforcement;
  arbitrary mapper support; production-ready universal console runtime).
- `host_path_audit.md` + `host_path_occurrences.json`: complete classification
  and safe handling of the nine frozen host-path occurrences, plus two
  hash-pinned pre-existing installer-metadata files.
- `portable_derivatives/`: host-neutral derivatives of the two unpinned
  raw-capture occurrences (originals remain frozen).
- `p2_90_rerun.txt`, `p2_90_rerun/`, `p2_90_rerun.json`,
  `p2_90_capture_preservation.*`: the P2-90 whole-project regression rerun
  capture and the frozen-capture preservation proof.
- `p2_91_tests.json`, `legal_policy_audit.json`, `source_integrity.txt`,
  `changed_files.txt`, `gate_determinism.txt`, `p2_91_run1.txt`,
  `p2_91_run2.txt`: deterministic gate record, policy captures and changed
  files.

## Evidence index and reference validity

- All 23 stages are indexed with every required field; the marker, gate marker
  and check count of every stage match the canonical P2-90 tables and the
  frozen per-stage evidence.
- All fixture, generated-source, executable, package and deterministic-run
  identities indexed are re-verified to exist in the frozen stage evidence
  (including the P2-90-audited current stdout hashes for the stages whose
  cross-stage guards were legitimately adjusted).
- Every repository reference in the index, limitations and claim matrix
  resolves to an existing artifact.

## Limitations and claim-matrix coverage

- `PHASE2_LIMITATIONS.md` contains all 13 proven/bounded-proven claims and all
  10 unproven/out-of-scope boundaries with the exact terminal claim vocabulary
  shared with the claim matrix; the final marker statement is explicit.
- `PHASE2_CLAIM_MATRIX.md` contains exactly the 23-key vocabulary; all 18 P2-90
  claims keep their audited classification (`PROVEN`, `BOUNDED_PROVEN`,
  `NOT_PROVEN`, `OUT_OF_SCOPE`) and all five closure claims are present. No
  document states or implies `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`;
  that marker is not claimed and remains `NOT_PROVEN`.

## Host-path resolution (the nine P2-90 occurrences)

The audit classification is complete and preserves historical evidence:

- Seven occurrences are historical absolute-path evidence that must remain
  frozen; six of them are hash-pinned by frozen PASS-stage artifacts or recorded
  stdout claims, and rewriting them would invalidate those pins or the P2-90
  fresh-capture reproduction. No frozen file was modified.
- Two occurrences (`P2-07/native_compile.txt`, `P2-08/determinism.txt`) are
  safely relocatable toolchain-detection metadata; both remain frozen
  byte-identically and host-neutral derivatives are provided.
- Zero occurrences are generated evidence that can be regenerated portably
  without changing a frozen generating gate; zero genuine portability defects
  were found among the nine.
- No new absolute local-host path exists in Phase-2 evidence, the Phase-2
  control-plane narrative, shared `openrecomp/**`/`adapters/**` sources or the
  P2-50 release packages. The two pre-existing installer-metadata files
  (`.openrecomp-phase2/INSTALL_INFO.txt`, `.openrecomp-phase2/P2_00_START_PROMPT.txt`)
  are documented and hash-pinned outside the portable-evidence scope.

## P2-90 regression rerun

- The P2-90 whole-project audit was re-executed through
  `tools/test_phase2_evidence_closure_v1.py --run-regression` after all P2-91
  evidence/documentation changes; the official execution passed with exit 0,
  `OPENRECOMP_PHASE2_EVIDENCE_CLOSURE_V1=PASS tests=884` (the two extra checks
  are `p2-90-rerun:executed` and `p2-90-rerun:preserved`) in ~5315 s with empty
  stderr (`p2_91_regression_run.txt`, sha256 `4433d1c7...`).
- Result: `OPENRECOMP_P2_90=PASS`,
  `OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1=PASS tests=361 gates=22 gate_tests=1990`,
  0 failures, empty stderr, final marker preserved as `NOT_PROVEN`.
- The rerun stdout content is identical to the frozen P2-90 capture
  (`P2-90/p2_90_run1.txt`, recorded capture sha256
  `74e9eadaf0e17ca4a97790e4239f40883cc745cd9817c172f7fa6e2663ce1ee7`; LF-normalized
  content sha256
  `00675593b278c8b660e2e4b00165e434057549a91263ba15b046150d82d00903`).
- The P2-90 audit rewrites its own phase-1 capture files as a side effect; the
  six frozen files were snapshotted, the 133-entry regenerations captured, and
  the originals restored byte-identically (`p2_90_capture_preservation.json`,
  all `restored_byte_identical_to_before = true`). Only the expected manifest
  count line differs in the regenerated captures (132 -> 133).
- A first development execution of `--run-regression` failed the closure gate's
  own stdout-identity check because the check compared the LF-normalized hash
  against the recorded CRLF capture hash; the nested P2-90 audit itself passed
  in that run. The check was corrected before any official run (content identity
  by LF normalization, recorded capture hash verified separately); the
  development capture is retained as
  `p2_91_regression_run_development_fail.txt` with the correction recorded in
  `gate_determinism.txt`. No frozen prior-stage evidence was modified.

## Source integrity and legal/content policy

- `python tools/phase1_host_gates_v1.py --only source-integrity`: PASS,
  `verified 133 manifest entries` (the P2-91 closure gate is registered).
- Manifest delta is exactly additive: removing the closure-gate line reproduces
  the P2-90-recorded manifest sha256
  `1bf21db59bf11f4ff19d60bbe4e37afd8e4b8ca5f1391296d882c1149cc08fca`; no
  pre-existing entry changed.
- Legal/content policy: tracked tree clean (no console-image magic, forbidden
  asset suffix or public-safety marker), P2-50 release packages pass the release
  content policy, and all P2-91-owned artifacts are host-path-free.

## Recurrence guard

`tools/test_phase2_evidence_closure_v1.py` fails closed on any new absolute
host path in the Phase-2 control plane (excluding the raw capture/backup areas
`scratch/` and `backups/`), the shared `openrecomp/**`/`adapters/**` sources,
the P2-50 release packages or P2-91-owned artifacts. It also fails if any frozen
historical occurrence is modified (exact SHA-256 pins) and if the P2-91 closure
gate leaves the source-integrity manifest delta non-additive.

## Determinism

Two consecutive canonical full closure-gate runs (`p2_91_run1.txt`,
`p2_91_run2.txt`) produced byte-identical stdout, sha256
`78b33d0cee634f0ce7327d22cedcbf6d84246951410c3aae1ecdc82e71d10048` (40674 bytes
each, empty stderr); the comparison and the regression-mode capture hashes are
recorded in `gate_determinism.txt`. The official `--run-regression` execution
that refreshed the P2-90 capture is recorded in `p2_91_regression_run.txt`
(sha256 `4433d1c7...`, `tests=884`). The gate prints no host path, timestamp,
random or process identity.

## Claim boundary of this stage

P2-91 proves the completeness, reference validity, internal consistency and
host-path hygiene of the Phase-2 evidence closure on the audited tree, and that
the whole-project regression still passes after the closure changes. It does not
add capabilities, does not upgrade any bounded stage claim, and does not issue
the final Phase-2 verdict. `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF` remains
`NOT_PROVEN` and is reserved for P2-99.

## Next stage

Per `.openrecomp-phase2/STAGE_QUEUE.md`, P2-91 is `COMPLETE` and the next active
stage is `P2-99` (final verdict), which may issue the final marker only if all
required stages pass.
