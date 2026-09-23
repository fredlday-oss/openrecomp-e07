# P12-40 — Deterministic end-to-end replay

Verdict: **PASS** (4 checks, deterministic twice).

Stage marker: `OPENRECOMP_P12_40=PASS`.
Target marker: `OPENRECOMP_PHASE12_END_TO_END_REPLAY_V1=PASS`.

The bounded Hercules initialization (fixture entry through the B0 pad-patch to
the current exact frontier) was run twice. The declared deterministic fields
(block-event count/digest, register file, RAM digest, device transcripts,
non-RAM signatures, counters) and the raw stdout are byte-identical; the replay
digest is stable. Intentionally nondeterministic metadata (host paths,
timestamps, process identity) is excluded.

Evidence: `replay.json`, `p12_40_tests.json`, `RESULT.json`,
`official_runs.json`, `determinism.json`, run stdout/stderr.
