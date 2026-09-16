# HOST_PATH_AUDIT

P2-91 host-path audit and resolution report.

## Scope and method

The audit scans every Phase-2 evidence file, every Phase-2 control-plane
document, the shared `openrecomp/**` and `adapters/**` sources (release-artifact
inputs), the P2-50 release packages and all P2-91-owned artifacts with the same
absolute-local-host-path detector used by the P2-90 whole-project audit. The
detector recognizes drive-letter path prefixes, UNC prefixes, the file URL
scheme, POSIX temporary and user-home roots, and the Windows temporary,
roaming-data and user-profile prefixes. (The literal token spellings are
intentionally not reproduced in this report so that the report itself stays
clean under the detector.)

Raw capture/backup residue under `.openrecomp-phase2/scratch/` and
`.openrecomp-phase2/backups/` is excluded by design: it is pre-existing
untracked residue, never treated as evidence, and the P2-90 audit writes its raw
nested gate captures there. `.openrecomp-phase2/INSTALL_INFO.txt` and
`.openrecomp-phase2/P2_00_START_PROMPT.txt` are pre-existing installer metadata
(not evidence); they are documented and hash-pinned below but are not part of
the portable-evidence set.

## The nine P2-90-identified occurrences: classification and resolution

P2-90 identified exactly nine frozen evidence files containing absolute
host-environment identifiers (P2-90 corrections report C4). P2-91 classifies and
resolves each one:

| File | Occurrence | Pinning | Classification | Resolution |
| --- | --- | --- | --- | --- |
| `P2-00/RESULT.md` | baseline working-copy path row | frozen baseline RESULT, no direct hash pin | historical absolute-path evidence that must remain frozen | freeze; documented exception |
| `P2-07/host_emitter_tests.json` | detected compiler executable path | pinned by `P2-07/RESULT.json` `artifacts_sha256` and `P2-07/determinism.txt` | historical absolute-path evidence that must remain frozen | freeze; documented exception |
| `P2-07/native_compile.txt` | detected compiler executable path (raw capture) | unpinned raw capture | safely relocatable metadata | freeze; portable derivative `portable_derivatives/P2-07_native_compile.portable.txt` |
| `P2-08/determinism.txt` | detected compiler executable path (raw capture) | unpinned raw capture | safely relocatable metadata | freeze; portable derivative `portable_derivatives/P2-08_determinism.portable.txt` |
| `P2-08/runtime_abi_tests.json` | detected compiler executable path | pinned by `P2-08/RESULT.json` `artifacts_sha256` and `P2-08/changed_files.txt` | historical absolute-path evidence that must remain frozen | freeze; documented exception |
| `P2-40/run1.txt` | interpreter path in captured gate stdout (recorded determinism run) | pinned by `P2-40/RESULT.json` `gate_stdout_sha256`, `RESULT.md` and `determinism.txt` | historical absolute-path evidence that must remain frozen | freeze; documented exception |
| `P2-40/run2.txt` | interpreter path in captured gate stdout (recorded determinism run) | pinned by `P2-40/RESULT.json` `gate_stdout_sha256`, `RESULT.md` and `determinism.txt` | historical absolute-path evidence that must remain frozen | freeze; documented exception |
| `P2-50/regression_tools_test_cross_architecture_neutrality_v1.txt` | interpreter path in nested regression capture | pinned by `P2-50/RESULT.json` `evidence_hashes`; re-verified by the P2-90 audit | historical absolute-path evidence that must remain frozen | freeze; documented exception |
| `P2-50/regression_tools_test_generic_runtime_integration_v1.txt` | interpreter path in nested regression capture | pinned by `P2-50/RESULT.json` `evidence_hashes`; re-verified by the P2-90 audit | historical absolute-path evidence that must remain frozen | freeze; documented exception |

Summary: seven occurrences are historical absolute-path evidence that must
remain frozen (six of them hash-pinned by frozen PASS evidence); two are safely
relocatable toolchain-detection metadata with portable derivatives; zero are
generated evidence that can be regenerated portably; zero are genuine
portability defects requiring correction.

### Why the frozen files are not rewritten

- The six hash-pinned files are referenced by recorded SHA-256 values in their
  own stage evidence (`artifacts_sha256`, `evidence_hashes`, `changed_files.txt`)
  or by a recorded stdout determinism claim (`P2-40` `gate_stdout_sha256`,
  `P2-50` nested capture hashes that the P2-90 audit re-verifies against fresh
  runs). Rewriting any of them would either falsify a frozen hash pin or break
  the P2-90 fresh-capture reproduction, because re-running the generating gates
  on this host necessarily reproduces the same interpreter/compiler identity.
- `P2-00/RESULT.md` is the frozen Phase-2 baseline RESULT; its working-copy row
  is a factual historical record of the audited tree.
- `P2-07/native_compile.txt` and `P2-08/determinism.txt` are raw detection
  captures. Their originals stay frozen; the portable derivatives above carry
  the same information with the host path replaced by `<host-compiler-path>`.
- The occurrences are host-environment identifiers only: no secret, credential,
  key, console asset, ROM byte or proprietary material is involved, and none of
  them appears in any release package, generated source or executable.

### Occurrences that are generated evidence and portable regeneration

No occurrence among the nine is regenerable portably without changing a frozen
generating gate, which the Phase-2 control policy forbids. P2-91 demonstrates
that *new* stage evidence is generated portably: the P2-90 whole-regression
rerun captured in `p2_90_rerun.txt` and `p2_90_rerun/` contains no absolute host
path because the audit normalizes command identity (interpreter shown as
`python`) before recording it. P2-91-owned artifacts are verified clean on every
gate run.

## Pre-existing Phase-2 control-plane installer metadata

| File | SHA-256 | Nature | Resolution |
| --- | --- | --- | --- |
| `.openrecomp-phase2/INSTALL_INFO.txt` | `7564ff729689bc6aed3ccd4a3a2d7e2ffbfb4c27a609c734c03d264fac84868a` | installer-recorded project root | documented, hash-pinned, out of portable-evidence scope |
| `.openrecomp-phase2/P2_00_START_PROMPT.txt` | `ef23c6306335091cfbee3935baa88f7c077699ece1074f6ba43e5851411b7759` | installer-recorded project path | documented, hash-pinned, out of portable-evidence scope |

## Broader repository note (outside the Phase-2 closure scope)

Absolute host paths also exist in pre-existing tracked material that is not
Phase-2 evidence and predates this closure stage: frozen Phase-1 evidence,
`artifacts/**` build residue, several `tools/**` rejection-test strings and
detector implementations, `.github/**` workflow examples, `docs/**`,
`integrations/**` and `EXTERNAL_REPRO_V1.sh`. These are frozen Phase-1/tooling
artifacts outside the Phase-2 portable-evidence and release-artifact scope;
they are not modified by P2-91 and are not counted among the nine P2-90
Phase-2 evidence occurrences. Should a later stage touch them, the same
classification discipline applies.

## Recurrence guard

`tools/test_phase2_evidence_closure_v1.py` enforces, on every run:

- the nine frozen files still exist, still contain their documented occurrence,
  and still hash to the exact values pinned in `host_path_occurrences.json`;
- the two installer metadata files still hash to their pinned values;
- no file in the scan scope (Phase-2 control plane without `scratch/` and
  `backups/`, plus `openrecomp/**` and `adapters/**`, plus P2-50 release
  packages, plus all P2-91-owned artifacts) contains a new absolute host path;
- the P2-91-owned artifacts (`PHASE2_EVIDENCE_INDEX.md`,
  `PHASE2_EVIDENCE_INDEX.json`, `PHASE2_LIMITATIONS.md`,
  `PHASE2_CLAIM_MATRIX.md`, this report, the register and the regression rerun
  capture) are completely free of absolute host paths, including the portable
  derivatives.

Any new occurrence fails the gate; any attempt to rewrite a frozen occurrence,
even silently, fails the hash pin.

## Final marker

`OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF` remains `NOT_PROVEN`; the final
Phase-2 verdict is reserved for P2-99.
