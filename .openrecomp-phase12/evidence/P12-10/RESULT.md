# P12-10 — Hercules first-frame proof

Verdict: **PASS** (8 checks, deterministic twice).

Stage marker: `OPENRECOMP_P12_10=PASS`.

Target marker: `OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF=NOT_PROVEN`.

The P12-00 frame contract is evaluated from the committed P12-05/P12-09
evidence. `FRAME-PREDECESSOR` fails (initialization not proven),
`FRAME-PRIMITIVE`/`FRAME-OT`/`FRAME-SUBMIT` fail (no frame boundary), and
`FRAME-DETERMINISTIC`/`FRAME-NOT-PLAYABILITY` hold, so the contract is not
satisfied. The frame proof remains `NOT_PROVEN`; an initialization callback is
explicitly not a frame.

Reserved markers remain `NOT_PROVEN`:
`OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF`,
`OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY`.

Evidence: `frame_proof.json`, `p12_10_tests.json`, `RESULT.json`,
`official_runs.json`, `determinism.json`, run stdout/stderr.
