# P12-08 — GTE / geometry / OT promotion assessment

Verdict: **PASS** (3 checks, deterministic twice).

Stage marker: `OPENRECOMP_P12_08=PASS`.

Target marker: `OPENRECOMP_PHASE12_GTE_GEOMETRY_V1=NOT_PROVEN`.

The Hercules frame path is unreachable, so no GTE geometry can be promoted. No
GTE coprocessor operation (`cop2`, `lwc2`, `swc2`, `mfc2`, `mtc2`, `cfc2`,
`ctc2`) is present in the production semantic rule table; any such operation
remains fail-closed. RTPT/RTPS/NCLIP and depth-ordered OT insertion are not
reached or modelled.

Evidence: `assessment.json`, `p12_08_tests.json`, `RESULT.json`,
`official_runs.json`, `determinism.json`, run stdout/stderr.
