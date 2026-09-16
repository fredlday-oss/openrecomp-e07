# P2-90 corrections report

Stage: `OPENRECOMP_PHASE2_WHOLE_REGRESSION_AUDIT_V1`.
Verdict: **PASS with corrections applied before the two official audit runs**.

The P2-90 audit found three control-plane consistency defects and one bounded
evidence-hygiene limitation. All findings are classified below. No Phase-2
implementation source, gate or semantic behavior was changed by this stage;
the gate file itself was adjusted during development before the official runs.

## C1 - stale P2-50 archive and source-state claims in the control plane

*Evidence*: `STATE.md` and `HANDOFF.md` claimed release archives
`084b1c2c...`, `7feaab35...`, `68cc619e...` and source-state fingerprint
`9dd81a78...`. The frozen `.openrecomp-phase2/evidence/P2-50/` artifacts
(`package_hashes.txt`, `release_manifest_*.json`, the package ZIPs,
`source_state.txt`, `RESULT.json`) record and reproduce
`fa72b5d1...`, `1c1dac0e...`, `71847f9d...` and `5d93971b...`.

*Classification*: control-plane documentation staleness. The values were
superseded when the P2-50 evidence was regenerated inside the P2-50 session;
the API/package semantics did not change. The P2-90 re-run of the P2-50 gate
reproduced every executable, build manifest, package and release manifest
byte-identically.

*Correction*: `STATE.md` and `HANDOFF.md` now state the evidence-derived
values. The P2-90 gate now requires those values and rejects the superseded
tokens (`control-plane:no-superseded-p2-50-claims`).

*Re-run evidence*: P2-90 regression matrix `P2-50` (tests=174) plus package
byte-identity; `artifact`-level identities unchanged.

## C2 - undocumented P2-14 cross-stage guard replacement and stale stdout hash

*Evidence*: `tools/test_mips32_larger_fixture_v1.py` (P2-14 gate) was changed
during the P2-20 session: the obsolete build-state guard
`no-p2-20-evidence-directory` was replaced by the genuine P2-14 property
`no-nes6502-dependency-in-p2-14`. The replacement is visible in the
P2-20..P2-50 regression captures and the working-tree diff against commit
`2fc27bf`; it was not recorded in the P2-14 evidence, and `STATE.md`/
`HANDOFF.md` still claimed P2-14's stdout hash was unchanged
(`115c2c8a...`), which is the pre-adjustment capture
(`P2-14/p2_14_gate.txt`).

*Classification*: documentation/annotation gap. The code replacement is a
legitimate, count-preserving guard fix of the same kind documented by
P2-11..P2-14 (`no-<stage>-evidence-directory` guards asserted build state, not
stage properties, and necessarily fail once the stage is authorized). P2-14
semantics, observables and test count (82) are unchanged.

*Correction*: `STATE.md`/`HANDOFF.md` now document the replacement and the
current P2-14 stdout hash
(`197a6c5e5c5578ee6fced2eb45b937359bbd612dab8ec11bb4d5c2e6b717da51`).
The P2-90 audit verifies the fresh P2-14 run against the frozen capture with
exactly this one-line delta (`capture:P2-14:...`).

## C3 - stale source-integrity count in the control-plane gate block

*Evidence*: the `STATE.md` gate block claimed `verified 130 manifest entries`;
the manifest held 131 entries before P2-90 and 132 after registering
`tools/test_phase2_whole_regression_v1.py`.

*Classification*: control-plane documentation staleness (a count one or two
registrations behind the manifest).

*Correction*: the gate block is updated to 132 entries. The P2-90 audit
verifies the reported count against the manifest itself
(`source-integrity:count-matches-manifest`) and that the audit gate is
registered (`source-integrity:audit-gate-registered`).

## C4 - bounded evidence-hygiene limitation (documented, not rewritten)

*Evidence*: nine frozen evidence files from completed stages contain
absolute host paths: `P2-00/RESULT.md` (working-copy path),
`P2-07/host_emitter_tests.json`, `P2-07/native_compile.txt`,
`P2-08/determinism.txt`, `P2-08/runtime_abi_tests.json`,
`P2-40/run1.txt`, `P2-40/run2.txt`,
`P2-50/regression_tools_test_cross_architecture_neutrality_v1.txt`,
`P2-50/regression_tools_test_generic_runtime_integration_v1.txt`
(detected compiler/interpreter executable paths and evidence paths embedded in
captured gate stdout).

*Classification*: bounded, pre-existing evidence-hygiene limitation. These are
host-environment identifiers, not secrets, credentials, console assets or
proprietary material. They do not appear in the shared implementation source,
in generated output or in any release package. Several are hash-pinned by the
evidence of their PASS stages (`P2-50/evidence_hashes`), so rewriting them
would invalidate frozen PASS evidence.

*Correction*: none to the frozen files. P2-90 records the exact file list,
enforces that no *new* host-path occurrence appears anywhere
(`legal:frozen-evidence-findings-documented`), keeps all P2-90-owned artifacts
host-path-free (`legal:p2-90-artifacts-clean`), and leaves sanitization of the
frozen files to the P2-91 evidence index with this report as evidence.

## No-regression statement

All 22 gates (1990 gate checks), 34 recorded identity checks, 7 frozen capture
comparisons, 138 evidence checks, the Phase-1 host gates (`PASS=44 FAIL=0
SKIPPED=2`) and source integrity (132 entries) passed in both official P2-90
runs with byte-identical output. No gate was weakened, skipped or rewritten;
no prior test was deleted or relaxed; no prior evidence file was modified.
