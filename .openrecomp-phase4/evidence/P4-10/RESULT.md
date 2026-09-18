# P4-10 result (PASS)

Stage: `P4-10` Reproducible Phase-4 package (frozen queue row).
Gate: `tools/test_phase4_package_regression_v1.py` (71 checks, sha256
`77d4ee6492c6df5c371d41d15810537a1d0a706c4d53314e241b2c3284b3625e`).
Evidence: `.openrecomp-phase4/evidence/P4-10/`.
Package: `.openrecomp-phase4/package/phase4_package_v1.zip`.

Markers issued:

- Stage marker: `OPENRECOMP_P4_10=PASS`
- Gate marker: `OPENRECOMP_PHASE4_PACKAGE_REGRESSION_V1=PASS tests=71`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

## Objective (frozen queue)

Produce a clean byte-reproducible or explicitly reproducibility-bounded
Phase-4 package containing all required source, generated artifacts,
manifests, evidence and exact reproduction instructions. Verify from the
audited tree.

## Package

- `phase4_package_v1.zip`: sha256 `88f508d7971f68e516086b691f4828b247ab67e46441e514eaa6c330b47f5b40`, manifest fingerprint
  `1d417db978f8c1c0b73f8585caa8df08fa42ef542c31186b5c878b41c36cfb46`, 326 members, 2705508 bytes; two builds from the
  audited tree are byte-identical.
- Members: the Phase-4 control plane, all runtime/ABI/memory/service/I/O/
  adapter/graphics-audio/fixture/reference/package sources and the generated
  ABI contract document, C header and instance profile; the original fixture
  sources and input plan; all eleven Phase-4 gates; the generated host
  translation (`p4_fixture_program.c` `abd138ea...`,
  `p4_fixture_support.c` `755a004630...`); the tracked stage evidence
  `P4-00` .. `P4-09`; `evidence/P4-10/REPRODUCE.md` with exact reproduction
  commands; and `P4_PACKAGE_MANIFEST.json` (per-member size/sha256 plus a
  canonical fingerprint).
- Content policy (fail-closed): text only (UTF-8, LF), no host paths,
  timestamps, UUIDs, sensitive markers, or compiled/guest binaries. Two
  documented exceptions are recorded in the package module and checked by the
  gate: host-specific command records are excluded by design
  (`P4-07/build.json` remains tracked in the repository), and gate sources
  plus the package builder are exempt from the needle scans because they
  embed the policy's own detection patterns (they are still UTF-8/LF checked
  and hashed).
- Reproducibility bound: external toolchains (zig 0.13.0; LLVM/clang-cl
  22.1.8 with lld-link) are pinned by recorded identity and not shipped; the
  fixture and native program are rebuilt from source by the gates.

## Verification

- `package:byte-identical`, `package:manifest-identical`,
  `package:manifest-fingerprint`, `package:verify-members`,
  `package:size-bound` and completeness checks for every control file, source
  module, gate, fixture file, evidence stage and the reproduction
  instructions.
- Bounded regression set from the audited tree: P2-08, P4-01..P4-07, Phase-1
  host gates and public safety all pass with empty stderr and their expected
  markers; the committed P4-00/P4-08/P4-09 boundary records verify as PASS
  with no failure. The heavy end-to-end re-execution is the whole-regression
  audit in P4-90.

## Determinism

- Two consecutive official gate runs: exit 0, empty stderr, stdout
  byte-identical raw (`8a9769d7...`) and LF, and `p4_10_tests.json`
  byte-identical across both runs.
- Evidence: `official_runs.json`, `determinism.json`,
  `package_manifest.json`, `package_sha256.txt`.

## Limitations

- Package bytes are reproducible from the same tree state only; the external
  toolchains are not shipped (identity-pinned instead).
- The package snapshot covers evidence through the P4-10 gate run; the
  committed P4-10 gate record itself is written after the snapshot by design.
- Host-specific command records and policy-detection gate sources follow the
  documented exceptions above.
- `GENERIC_RUNTIME_STATUS=NOT_PROVEN`; the terminal verdict remains reserved
  for P4-99.

## Next stage

P4-90 - Phase-4 whole regression audit.
