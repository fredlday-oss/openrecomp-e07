# P3-90 result (PASS)

Stage: `P3-90` Phase-3 whole regression (frozen queue row).
Gate: `tools/test_phase3_whole_regression_v1.py` (30 checks).
Evidence: `.openrecomp-phase3/evidence/P3-90/`.

Markers issued:

- Stage marker: `OPENRECOMP_P3_90=PASS`
- Gate marker: `OPENRECOMP_PHASE3_WHOLE_REGRESSION_V1=PASS tests=30`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

## Scope

P3-90 audits the completed Phase-3 path together with the preserved Phase-1 and
Phase-2 gates. New Phase-3 file only
(`tools/test_phase3_whole_regression_v1.py`); no shared layer, frozen adapter,
Phase-1/Phase-2 file, gate or frozen manifest was modified. The Phase-3
manifest grew additively from twenty-one to twenty-two entries; the earlier
gates expect twenty-two entries and still emit byte-identical stdout.

## Frozen boundary re-verification

- `openrecomp-phase2-pass` is an annotated tag resolving to commit
  `01b1d7cb...` / tree `6513eefa...`; the branch descends from that boundary;
  `openrecomp-phase1-pass` = `46c2f971...`.
- P2-99 `RESULT.json` `880d2596...`, P2-99 gate `8d6a42d5...` and the frozen
  P2-90 capture `74e9eada...` all re-hash exactly.
- CoreMark fixture `16a0a0aa...` (31184 bytes) and the P3-01
  unsupported-encoding histogram (`movz` 35, `mul` 22, `movn` 12, `divu` 4,
  `teq` 4, `swl`/`swr` 2/2, `jalr` 1) are unchanged.

## Package audit

The committed P3-10 package `phase3_package_v1.zip` verifies from its bytes:
sha256 `cf9ab795...`, manifest fingerprint `9050a117...`, 287 entries
(5376636 raw bytes), member-by-member hashes, and the P3-10 boundary record and
capture (`43474910...`) match. The committed package is the P3-10 boundary
snapshot of the tracked Phase-3 path; later tracked additions are not
retroactively included by design.

## Whole regression

The deterministic gate set ran to completion and all thirteen gates passed
with exit 0, empty stderr and byte-identical (LF-normalized) stdout against
their recorded captures: P2-99 `PASS tests=202`, P3-00 `PASS tests=61`,
P3-01 `PASS tests=76`, P3-02 `PASS tests=197`, P3-03 `PASS tests=201`,
P3-04 `PASS tests=126`, P3-05 `PASS tests=202`, P3-06 `PASS tests=123`,
P3-07 `PASS tests=68`, P3-08 `PASS tests=55`, P3-09 `PASS tests=39` (full
independent reference re-execution), Phase-1 host gates
`PASS=44 FAIL=0 SKIPPED=2`, public safety `PASS`.

The P3-10 gate itself is verified by its committed boundary capture and package
record rather than re-run, because it performs this whole-regression audit by
design; this is recorded explicitly in `whole_regression.json`.

## Verification

- 30 gate checks: source integrity, frozen boundary identities, fixture and
  inventory identity, package verification, the thirteen-gate regression audit
  and deterministic artifact hashing.
- Official runs: two consecutive gate invocations byte-identical (raw sha256
  `5d86ba0564a30e28d8fdffc890e9e93afb17481c03991a5c4a10e6e054697bea`, 2052
  bytes, empty stderr, exit 0).
- The terminal marker remains reserved and `NOT_PROVEN`; P3-90 audits only.

## Claim boundary

P3-90 adds no capability claim. It confirms that the completed Phase-3 stages
and the preserved Phase-1/Phase-2 gates pass together deterministically. The
terminal verdict is issued only by P3-99 after P3-91 records limitations.
`COREMARK_STATUS=NOT_PROVEN`.
