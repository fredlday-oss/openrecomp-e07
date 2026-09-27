# Controller review — P17-90 (whole Phase-17 regression suite)

Candidate: `53528956b3276e8bc3f954dc141049bb7ab7c74b` (1 commit atop
`c784fc75b0dbed7f7e4c66d23a40a53b8ab818f2`; 19 files, 2552 insertions).
**Verdict: ACCEPT.**

## 1. Provenance and structure

- `5352895^ == c784fc7`, `git rev-list --count` = 1. No merge, no history rewrite.
- Worker worktree `coder-deepseek-p17-90-r1` is clean; no uncommitted residue.
- The previously reported stale-evidence digest mismatch was resolved *before*
  commit: the manifest expectation `93d1f52d…` was updated to the actual test
  digest `5e050648…`, evidence was regenerated, and the old copies were moved to
  `/home/fred/OpenRecomp/.p17-preserve/P17-90-stale-evidence/` rather than
  deleted. The expected authority `c784fc7` is intact and unmodified.

## 2. Independent reproduction

I did not take the worker's determinism claim on trust. In a separate
controller review worktree I re-ran the stage runner:

| Run | Private build root | rc | Artifacts identical | stderr |
|-----|--------------------|----|---------------------|--------|
| Controller run 1 | default `P17-04R` root | 0 | true | empty |
| Controller run 2 | **fresh** `P17-90-controller-fresh-20260927T124550Z` | 0 | true | empty |

All 12 evidence JSON documents are byte-identical in both cases, and
`run1.txt` is byte-identical to the committed `run1.txt`.

**This is the decisive test of the central claim.** Run 2 used a private build
root that has never been used by any prior run, so it is a genuine build-root
perturbation rather than a re-read of the same inputs. The evidence being
byte-identical across it and the default root is the mechanical proof that the
gate's output does not depend on the build root.

## 3. The two classified divergences

The gate allows exactly two non-strict comparisons. I verified each is
re-derived live rather than restated, and that everything else fails closed.

**`PATH_DEPENTENT_BUILD_ROOT` (`linkage_exclusion.inspection_digest`).**
`objdump -T` echoes the artifact's absolute path in its first output line and
`p17_linkage_exclusion_v1` hashes that raw stdout, so the digest is a function of
the build root. Measured in `live_divergence_proof.json`:

- raw digests genuinely differ: `10ddf9a5…` (run 1) vs `252fd1fc…` (run 2);
- root-invariant digest identical: `7957450e…`, `root_invariant_digest_agrees=true`;
- `probes_identical 5/6`, sole divergent probe `objdump_dynamic_symbols`;
- normalisation rejects a perturbed artifact: **true**.

The normaliser is a targeted regex over the `<path>: file format …` header
line only. All other lines — the actual symbol and relocation content — are
preserved verbatim, so a real change to the inspected binary still diverges.
Note this is the *sound* half: because the digest is opaque, normalising the
finished JSON would be unsound; the worker instead normalises at hash time and
hashes the normalised text, which is why the proof is checkable.

**`RUNNER_GENERATED_FILE_COUNT`.** The gate body scans its evidence directory
before the stage runner writes `official_runs.json` and `determinism.json`, so a
fresh run reports 9 where the committed record says 11. `file_count_expectation`
re-derives this as an exact set relation (committed = gate-time ∪ exactly those
two documents) and hard-fails on any other addition or removal. The `hits`
member, which carries the actual public-safety verdict, is compared strictly
and is empty.

## 4. Controller-authored adversarial testing

I wrote 12 tamper cases against `classify_artifact_divergence` rather than
relying on the worker's own negative controls. 10 behaved correctly. Two are
worth recording precisely, because a naive reading would call them defects:

| Case | Expected | Actual | Assessment |
|------|----------|--------|------------|
| attacker-chosen `inspection_digest` (`deadbeef` instead of a path echo) | reject | **accept** | in-policy |
| path echo to a *differently named* artifact | reject | **accept** | in-policy |

**Both are consequences of the policy being deliberately narrow, and neither is
an exploitable fail-open at gate time.** They are artifacts of testing
`classify_artifact_divergence` in isolation:

1. `inspection_digest` is an *opaque sha256*. The policy classifies that exact
   JSON path, so by construction any value is accepted there. This is
   unavoidable and is not a weakness: the classified field carries no semantics
   by definition, and the policy's integrity rests entirely on the **live**
   re-derivation in §3, not on comparing the opaque value. A gate that "caught"
   an arbitrary digest change would have to recompute the digest — which
   §3's `root_invariant_linkage_digest` does.
2. The artifact-name case: the echo regex is keyed to the `<path>: file format`
   header shape, not to a name allowlist. The artifacts probed are fixed
   constants in the emitter (`PERSISTED_ARTIFACTS`, `or_title_runtime_v1.so` /
   `or_title_runtime_v1`), so a different artifact name cannot arise from a
   build-root change. Re-probed: near-miss prefixes (extra trailing content,
   changed format string) *are* correctly rejected, so the mask is not broad.

The remaining 10 cases — `forbidden_hit_count` 0→1, `inspected_line_count`
438→437, `excluded` True→False, `record_count` drift, `status` PASS→FAIL,
path-echo-plus-extra-content, readelf content change, empty-vs-nonempty echo —
all fail closed as required. Critically, **the fields that carry the actual
linkage safety verdict are not classified and are compared strictly.**

I accept the policy as specified, with this characterisation recorded so the
narrowness is a documented decision rather than an accident.

## 5. Semantic re-derivation (independent of the worker's helper)

Re-running the chain from the fixture, deliberately *not* using the test's own
helper, reproduces the committed numbers exactly:

```
rederived record_count : 8340      committed total     : 8340    match
provenance digests    : 8340
regions               : 4
region log match      : True
committed per-region  : {mainexe: 1345, title: 6995, total: 8340}
```

This is real re-derivation from the fixture at
`/home/fred/OpenRecomp/fixtures/psx/hercules`, not a digest comparison.

## 6. Proof boundaries — unchanged, and that is the point

P17-90 is a *consistency* gate. It proves the chain reproduces; it proves
nothing new about emulation. Verified unchanged in `RESULT.json`:

- `FIRST_FRAME_READY=NO`
- `OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN`
- `OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`

All 8 chain stages report PASS; no malformed markers; `P17-90_CHECKS=114`;
source integrity PASS with 31 entries on canonical git blobs.

The stage's own honesty about its limits is also on record in
`live_divergence_proof.json.coverage_boundary`: the linkage digest covers the six
probed symbol/dynamic/relocation surfaces, not every byte of the image, and a
mutation confined to the ELF section header table would leave all six outputs
unchanged. Whole-file checks are recorded separately.

## 7. Disposition

**ACCEPT.** Integrate `5352895` by fast-forward, then run **P17-91**
(evidence closure & source manifest audit) and **P17-99** (final Phase-17
verdict). Do not begin Phase 18.
