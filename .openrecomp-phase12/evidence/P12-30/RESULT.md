# P12-30 — Direct / indirect BIOS path consistency

Verdict: **PASS** (10 checks, deterministic twice).

Stage marker: `OPENRECOMP_P12_30=PASS`.

The direct `B0:0x5B` stub (`0x80015f3c`) and the `B0:0x57 GetB0Table` ->
entry `0x5B` indirect path converge on the single bounded implementation
`p12_bios_set_change_clear_pad`, with no fabricated BIOS address. All seven
known Hercules callers (`0x80015c3c`, `0x80015cc8`, `0x80015d28`, `0x80016198`,
`0x8001670c`, `0x80026d74`, `0x80026dd0`) are accounted for, and the synthetic
table entry `0x5B` equals the synthetic target `0x1f001000`.

Evidence: `consistency.json`, `p12_30_tests.json`, `RESULT.json`,
`official_runs.json`, `determinism.json`, run stdout/stderr.
