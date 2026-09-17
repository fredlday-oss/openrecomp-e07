# P3-10 result (PASS)

Stage: `P3-10` reproducible package + whole regression (frozen queue row).
Gate: `tools/test_phase3_package_regression_v1.py` (20 checks).
Evidence: `.openrecomp-phase3/evidence/P3-10/`.

Markers issued:

- Stage marker: `OPENRECOMP_P3_10=PASS`
- Gate marker: `OPENRECOMP_PHASE3_PACKAGE_REGRESSION_V1=PASS tests=20`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

## Scope

P3-10 packages the tracked Phase-3 path reproducibly and runs the whole
Phase-1/Phase-2/Phase-3 gate set together. New Phase-3 files only:

- `.openrecomp-phase3/src/p3_package_v1.py` — deterministic ZIP builder and
  verifier with a fail-closed content policy;
- `tools/test_phase3_package_regression_v1.py` — the P3-10 gate;
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` — grown additively from nineteen
  to twenty-one entries; the earlier gates now expect twenty-one entries and
  still emit byte-identical stdout.

## Package

`phase3_package_v1.zip` (5482951 bytes, sha256 `cf9ab795...`, manifest
fingerprint `9050a117...`) contains 287 tracked files (5376636 raw bytes):

- the Phase-3 control plane and source manifest;
- all Phase-3 source modules and gates;
- the OpenRecomp-authored CoreMark port files;
- the generated host program/support C (`coremark_program.c`,
  `coremark_support.c`);
- the tracked Phase-3 evidence through P3-09, including the native observable,
  the reference observable and the equivalence record.

Determinism: two independent builds from the same tracked state are
byte-identical; the embedded manifest is verified member-by-member (membership,
sizes, hashes and fingerprint) and the archive is read back from disk bytes.
Content policy: no compiled artifacts or guest binaries, no host absolute
paths or timestamps or UUIDs in evidence entries, and no sensitive markers.
Host-specific command records (`official_runs.json`,
`regression_summary.json`, the P3-01 build-command records) are excluded from
the package by design and remain tracked evidence; the toolchain, external
CoreMark sources and build roots are excluded as well.

## Whole regression

All thirteen gates ran to completion in one audit and passed with exit 0,
empty stderr and byte-identical (LF-normalized) stdout against their recorded
captures:

| gate | result |
| --- | --- |
| P2-99 | `PASS tests=202` |
| P3-00 | `PASS tests=61` |
| P3-01 | `PASS tests=76` |
| P3-02 | `PASS tests=197` |
| P3-03 | `PASS tests=201` |
| P3-04 | `PASS tests=126` |
| P3-05 | `PASS tests=202` |
| P3-06 | `PASS tests=123` |
| P3-07 | `PASS tests=68` |
| P3-08 | `PASS tests=55` |
| P3-09 | `PASS tests=39` (full independent reference re-execution) |
| Phase-1 host gates | `PASS=44 FAIL=0 SKIPPED=2` |
| public safety scan | `PASS` |

## Verification

- 20 gate checks: source integrity, package presence/counts, content policy,
  reproducibility, manifest verification, the whole-regression audit and
  deterministic artifact hashing.
- Official runs: two consecutive gate invocations byte-identical (raw sha256
  `84dcd13981007d77d12811018eb7ea375f1e907391fa32ac2ebc8703febf2b1e`, 1713
  bytes, empty stderr, exit 0).
- The terminal marker remains reserved and `NOT_PROVEN`: P3-10 does not issue
  the Phase-3 verdict (that is P3-90/P3-91/P3-99).

## Claim boundary

P3-10 proves reproducible packaging and whole-regression coherence of the
audited Phase-3 path. It adds no new capability claim and does not promote the
terminal marker. `COREMARK_STATUS=NOT_PROVEN`.
