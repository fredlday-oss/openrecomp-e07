# P4-00 result (PASS)

Stage: `P4-00` Phase-4 boundary (frozen queue row).
Gate: `tools/test_phase4_boundary_v1.py` (74 checks, sha256
`5be5c7d2a004a82b74203acf3c58bcd2cda1a9d21d6ab60fe4c91c91f1a379e7`).
Evidence: `.openrecomp-phase4/evidence/P4-00/`.

Markers issued:

- Stage marker: `OPENRECOMP_P4_00=PASS`
- Gate marker: `OPENRECOMP_PHASE4_BOUNDARY_V1=PASS tests=74`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted by Phase 4):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

## Boundary proof

- `openrecomp-phase3-pass` is annotated (tag object
  `ac31524504b1b5cc63aabcfd5132a3eb4275e8e9`) and resolves to commit
  `e16e4b29b90f379615f1af97e47747cd1d531796`, tree
  `a940f0d84a32adaf191f7ff2bebfb24cc855cde0`.
- Branch `phase4/generic-runtime-v1` was created from that exact commit; the
  merge base with the boundary is the boundary commit itself.
- Phase-2 (`01b1d7cba8c931fca95d041389cfb1902b7c89fe`) and Phase-1
  (`46c2f971e1a42cf49bd936bad94697b81bf31002`) reference boundaries re-verified.

## Frozen Phase-3 evidence (unchanged)

- Root `SOURCE_SHA256SUMS.txt`: `76f77bbc...` (134 entries).
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt`: `a7d0953c...` (24 entries).
- `.openrecomp-phase3/evidence/P3-99/RESULT.json`: `c893250b...`.
- `tools/test_phase3_final_verdict_v1.py`: `ba581490...`.
- CoreMark fixture ELF: `16a0a0aa...`, 31184 bytes.

## Phase-3 final gate re-run (independent, in the frozen verification context)

`python tools/test_phase3_final_verdict_v1.py` was re-run by the P4-00 gate
with exit 0, empty stderr and 2498-byte stdout byte-identical to the frozen
official capture (raw `953ec70c...`, LF `4974d03f...`), emitting
`OPENRECOMP_P3_99=PASS`,
`OPENRECOMP_PHASE3_FINAL_VERDICT_V1=PASS tests=46` and
`OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=PASS`.

The frozen Phase-3 chain cannot run verbatim from a Phase-4 branch: the frozen
P3-00 gate inside that regression predates Phase 4 (it requires the current
branch to be named `phase3/*`, and its untracked-path allowlist rejects any
non-Phase-3 untracked path). The gate therefore reconstructs the exact frozen
Phase-3 verification context for the re-run only:

- a temporary local branch `phase3/p4-00-verification-context` is created at
  the same commit for the duration of the re-run and deleted afterwards;
- untracked Phase-4 material (`.openrecomp-phase4/`,
  `tools/test_phase4_...`) is held outside the worktree during the re-run and
  restored byte-identically afterwards (2 entries held, 2 restored);
- the committed P3-99 verdict record is restored from HEAD if a failed re-run
  overwrote it (pre-run: no restoration needed; post-run: none needed).

No frozen file is modified, no history is rewritten and no gate is weakened.
Captures: `p3_99_reverify_stdout.txt` (LF, sha256 `4974d03f...`),
`p3_99_reverify_stderr.txt` (empty).

## Determinism

- Two consecutive official gate runs: exit 0, empty stderr, stdout
  byte-identical raw and LF (3186 bytes; raw `953312d0...`, LF
  `03fa4c3a...`).
- `p4_00_tests.json` byte-identical across both runs
  (`1c86cebd...`), including the full 74-check record and findings.
- `determinism.json` and `official_runs.json` record both runs.

## Control plane, queue freeze and claim discipline

- Phase-4 control plane complete (CONTROL_POLICY, EVIDENCE_SCHEMA, SCOPE,
  STAGE_QUEUE, STATE, HANDOFF, evidence/) and deterministic: no host paths,
  timestamps, UUIDs or process identity; no premature claim markers.
- Frozen queue `P4-01` .. `P4-99` present, in order, with exact names; the
  queue `COMPLETE` set equals the STATE ledger `PASS` set; at most one stage
  active; `QUEUE_FREEZE=FROZEN`.
- `GENERIC_RUNTIME_STATUS=NOT_PROVEN`; the terminal and general compatibility
  markers stay reserved as `NOT_PROVEN`. No runtime capability is claimed by
  this stage.

## Worktree and provenance

- Untracked paths: the documented Phase-2/Phase-3 working sets and residue
  plus the Phase-4 control plane; no unexpected untracked paths; no deleted,
  renamed or staged paths.
- Modified tracked files: only
  `.openrecomp-phase3/evidence/P3-00/p3_00_tests.json` and
  `.openrecomp-phase3/evidence/P3-00/residue_manifest.txt`, both refreshed as
  re-run artifacts of the frozen gate re-execution. They are deliberately not
  committed; the committed Phase-3 evidence is unchanged.
- Residue set documented and present (275 files under the recorded prefixes).
- No console magics or proprietary assets under the Phase-4 control plane.

## Development note (gate hardening)

During gate development, one run failed with a spurious
`phase3-gate:verification-branch-deleted` error: `git branch -d` returned a
transient nonzero exit even though the branch had actually been deleted. The
gate was hardened to verify the end state (branch absence, branch checked out)
with bounded retries; the two official runs of the final gate then passed with
identical stdout and identical artifacts. No frozen artifact was affected.

## Limitations

- Phase-4 terminal/general compatibility remains `NOT_PROVEN`; this stage adds
  no runtime capability.
- The frozen Phase-3 gates cannot be re-run verbatim from a Phase-4 branch;
  P4-00 reconstructs the exact Phase-3 verification context instead. Later
  whole-regression stages must apply the same documented context
  reconstruction (or verify the frozen gate by its committed boundary record,
  as Phase 3 did for P3-10).
- Two tracked Phase-3 evidence sidecars remain refreshed in the working tree
  as re-run artifacts and are intentionally left uncommitted.
- The `commits_since_boundary` value recorded by the frozen P3-00 gate changes
  as Phase-4 commits accumulate; the frozen committed record is unaffected.

## Next stage

P4-01 — Generic Runtime ABI V1.
