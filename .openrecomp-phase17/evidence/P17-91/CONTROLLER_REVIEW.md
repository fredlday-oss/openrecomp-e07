# Controller review — P17-91 (evidence closure & source manifest audit)

Candidate (worker): `84e3e8ae19bcab79ef819e937d1b1361f5628b0c` — 2 commits atop
`724d3d4c8ff9a58702d05a5f5fb7aaf503bf5649`; worker branch
`agent/deepseek-phase17-p17-91-r1`; candidate tree
`992862fb456ddfe579b24c40352b737d108a5dc4` (21 files, 5109 insertions).
Integrated authority: controller branch `phase17/ps1-title-overlay-recompile-v1`;
pre-integration controller HEAD `69c4611c276596f62be616934e4495a66a5b3ba1` (tree
`4166d05d05fa2feefeb5758f5376f5991febc266`).
**Verdict: ACCEPT.**

## 1. Provenance and structure

- `84e3e8a^ == a34f686`, `a34f686^ == 724d3d4`; `git rev-list --count` = 2. No
  merge, no history rewrite, no rebase.
- The worker commits (`a34f686` module/gate, `84e3e8a` regenerated evidence) are
  already ancestors of the controller branch.
- The worker touched only `.openrecomp-phase17/src/p17_evidence_closure_v1.py`
  (new, +960), `tools/test_phase17_evidence_closure_v1.py` (new, +297),
  `.openrecomp-phase17/SOURCE_SHA256SUMS.txt` (+2 lines) and its own
  `.openrecomp-phase17/evidence/P17-91/*`. No other stage's evidence, no
  Phase-1..16 file, and no other stage source was modified
  (`git diff --name-only 724d3d4..HEAD -- '*/src' '*/evidence/*'` reduces to
  P17-91 paths and the manifest).
- Worker worktree `coder-p17-91-r1` is clean; no uncommitted residue.

## 2. The worker's reported finding, and its resolution

P17-91 is the first Phase-17 stage whose scan surface includes the controller's
own review prose. The worker's audit reported, and did **not** silently waive, a
real public-safety violation in a document it was forbidden to modify:

- `P17-90/CONTROLLER_REVIEW.md` contained two literal `/home/<user>/…` paths
  (a preserve-directory path and the private fixture root), a violation of the
  `EVIDENCE_SCHEMA.md` rule that committed evidence must not carry private host
  paths. Reported with `severity: REPORTED_NOT_GATING` and an explicit reason,
  because the file is controller-authored and outside the P17-91 write scope.

The controller confirmed the report and fixed it in `69c4611`: the two paths
were replaced with `a preserve directory outside the repository` and
`the read-only private fixture root`, and the P17-91 evidence was regenerated so
the committed evidence matches the tree. After the fix:

- `public_safety.json.review_document_findings == []`;
- `RESULT.json.findings == []`;
- an independent controller grep of the whole committed evidence tree for
  `/home/<user>/` and `/Users/<user>/` returns hits only in `P17-00`, whose six
  strings are the fabricated synthetic placeholders of the P17-00 path-rejector
  negative control (each recorded with `rejected: true`) and are the only
  private-path allowlisting P17-91 performs.

This is the correct behaviour: a genuine finding was surfaced rather than
allow-listed, and the responsible author — not the worker — made the fix.

## 3. Independent reproduction

I did not take the determinism claim on trust. In a separate review worktree
(`controller-review-p17-91`, detached at `69c4611`) I re-ran the official
stage runner:

```
python3 .openrecomp-phase17/src/p17_stage_runner_v1.py --stage P17-91 \
  --script tools/test_phase17_evidence_closure_v1.py \
  --evidence-dir <fresh-dir> --tests-json p17_91_tests.json
```

| Check | Result |
|-------|--------|
| rc (both runs) | 0 |
| stderr (both runs) | empty |
| `run1.txt` vs `run2.txt` | byte-identical |
| fresh-run `run1.txt` vs committed `run1.txt` | byte-identical |
| `sha256(run1.txt)` | `6ad7f44153a35483827c0c8e206eadbc1e140c1354f386bc6dca8ccd9e190f83` |
| `gate_sha256` | `6d3f040b69a44b3004412209a537ada51ac9b446f32c3af39a7041af24904a83` |
| checks | 153 PASS, 0 FAIL (`P17-91_CHECKS=153`) |
| markers | `OPENRECOMP_P17_91=PASS`, `OPENRECOMP_PHASE17_EVIDENCE_CLOSURE_V1=PASS`, four `NOT_PROVEN`, `FIRST_FRAME_READY=NO` |

Twelve of the fourteen generated JSON documents are **byte-identical** to the
committed evidence (`RESULT.json`, `audit.json`, `closure.json`,
`determinism.json`, `manifest_audit.json`, `marker_ledger.json`,
`negative_controls.json`, `next_stage.json`, `p17_91_tests.json`,
`prior_phase_integrity.json`, `public_safety.json`, `stage_metadata.json`,
`transcript_binding.json`), and `run1.txt` is byte-identical.

**The one classified divergence.** `official_runs.json` differs from the
committed copy in exactly two fields: the `--evidence-dir` argument recorded in
each run's `command`. This is a runner-metadata echo of the invocation, not a
gate verdict; every substantive field is identical
(`identical_raw/identical_lf/returncode_zero_both/stderr_empty_both/
markers_present_both/artifacts_identical = true`, `next_stage = P17-99`), and
the diff is confined to the two literal path strings. It is mechanically
explained and is not a fail-open.

**Clean/understood root.** Re-running the runner against the *committed* evidence
directory (the clean root), the runner reports
`runner_status: PASS` with `artifacts_identical: true` and, crucially,
`git status --porcelain` is **empty** afterwards: regenerating in place
reproduces the committed bytes exactly. The gate's output is a function of the
committed corpus, not of where it is run.

## 4. Independent verification of each audit claim

I re-derived the key claims without using the worker's helper functions.

**Public safety.** `audit.public_safety_scan(evidence_root)` → `ok = True`,
`documents_scanned = 137`, `documents_failed = []`, `review_document_findings = []`.
The allowlist is tiny and named (7 entries, all in P17-00 negative-control
artifacts and one P17-07 check-name token); the reconstructive-key rule
(`payload_bytes, raw_instruction, bios_bytes, instruction_word, …`) is never
waived, and an independent grep for those JSON keys across the committed
evidence tree returns nothing.

**Source manifest.** `python3 .openrecomp-phase17/src/p17_source_manifest_v1.py`
→ `OPENRECOMP_PHASE17_SOURCE_INTEGRITY=PASS entries=41`. `sha256sum -c
SOURCE_SHA256SUMS.txt` passes every entry. The manifest is exact: no missing,
extra or duplicate entry, and the audit re-proves the digest *basis* per entry
(git-blob content == working-tree bytes) rather than assuming it.

**Evidence closure.** `closure.json` → `ok = True`, 13 stage directories checked,
each with the schema-required documents and a schema-conformant `RESULT.json`;
no stage reports a missing document.

**Dual-run determinism.** `determinism.json` → 12 dual-run stages all
byte-identical with empty stderr and recorded digests matching.

**Marker ledger.** `marker_ledger.json` → `ok = True`, `promoted_markers = []`;
all five protected markers are `NOT_PROVEN`/`NO` in every stage `RESULT.json`,
and STATE.md / STAGE_QUEUE.md each declare all five.

**Prior-phase integrity.** `prior_phase_integrity.json` → `ok = True`,
`commits_touching_prior_phases = []`, 16 prior-phase trees identical to the
frozen baseline `a0c26e88…`.

## 5. Negative controls

The gate's own `negative_controls.json` records 7 tamper cases, 7 detected
(`ok = True`): corrupted manifest digest, removed manifest entry, missing
required evidence document, divergent dual run, fabricated private host path,
forbidden key in an allowlisted file still caught, promoted `NOT_PROVEN` marker;
plus the `baseline_manifest_is_clean` sanity case.

I independently reproduced two of them through the audit API directly, bypassing
the gate harness: a single corrupted manifest digest is detected
(`digest_mismatches = 1`, naming the exact path), and a removed manifest entry is
detected (`missing_entries = ['.openrecomp-phase17/src/p17_authentic_execute_v1.py']`).
Each case re-runs the real audit function on a mutated copy of real input rather
than asserting a constant, so a future fail-open would be caught.

## 6. Scope boundary

P17-91 is a terminal **consistency** gate. It proves that the committed Phase-17
evidence corpus is internally consistent, complete, schema-conformant, publicly
safe, and that the source manifest is exact. It proves nothing new about
emulation and promotes no proof marker. `FIRST_FRAME_READY=NO` and the four
`NOT_PROVEN` markers are unchanged. The gate's own design note records that it
excludes its own evidence directory from the scan set so that the scanned-file
count cannot become a function of run order — it audits the committed prior
corpus, not its own output.

## 7. Decision

ACCEPT and INTEGRATE. The candidate is sound, the reported finding was real and
was fixed by its author, the audit fails closed, and its output is a
byte-reproducible function of the committed corpus. Integration is recorded in
this review and in STATE.md / STAGE_QUEUE.md / HANDOFF.md / REVIEW_REQUIRED.md.
Remaining stage: P17-99 (final Phase-17 verdict). Do not begin Phase 18.
