# P12-02 — Complete B0:0x5B caller coverage

Verdict: **PASS** (22 checks, deterministic twice).

Marker: `OPENRECOMP_P12_02=PASS`.

## Objective

Independently re-derive every currently known B0:0x5B dependency on the private
fixture, classify direct/GetB0Table/trampoline/reachability, and test that all
reachable required paths resolve consistently with the Phase-12 service surface.

## Independently re-derived facts (private fixture bytes)

- Two `B0:0x57` `GetB0Table` sites: bases `0x80015fa0`, `0x80026f70`, `jalr`
  call sites `0x80015fa4`, `0x80026f74`, entry reads at `0x80015fac`,
  `0x80026f7c` (32-bit `lw` at offset `0x16c`). **Both are reachable** in the
  merged analysis and classify as `ps1.bios.B0.57` / `EXACT_EXTERNAL_SERVICE`.
- Direct `B0:0x5B` stub at `0x80015f38` (words `0x240a00b0`, `0x01400008`,
  `0x2409005b`), `jr` at `0x80015f3c`. **Reachable and resolved** as
  `ps1.bios.B0.5b` / `INDIRECT_JUMP` / `EXACT_EXTERNAL_SERVICE`.
- Seven direct callers via `jal 0x80015f38`: `0x80015c3c`, `0x80015cc8`,
  `0x80015d28`, `0x80016198`, `0x8001670c`, `0x80026d74`, `0x80026dd0`; five of
  the seven are reachable in the merged analysis.
- All other reachable B0 vector sites (indices 18, 19, 23, 25, 63, 74, 75, 86)
  stay `BIOS_VECTOR_NOT_IMPLEMENTED` / `FAIL_CLOSED` with no service id.

## What the gate verifies

1. The raw-byte inventory (bases, call sites, entry reads, stub words, callers)
   matches the independently expected identities exactly.
2. Both `B0:0x57` sites are reachable and resolved; the direct stub is reachable
   and resolved; unknown B0 entries remain fail-closed.
3. The composed runtime defines both B0 service-id macros and chains the
   Phase-11 dispatcher; the emitted semantics carry exactly the `B0.57`
   (`INDIRECT_CALL`, result `bios_ret`) and `B0.5b` (`INDIRECT_JUMP`, no result)
   rules and no unknown-B0 rule.
4. Committed evidence is public-safe (no payload sample, no raw words, no private
   path).

## Direct/indirect convergence

- direct `B0:0x5B` (`jr` stub) and
- `B0:0x57 GetB0Table` -> table entry `0x5B`

both reach the same `p12_bios_dispatch` behaviour (bypass vs. synthetic table
entry `0x5B` pointing at the synthetic target).

## Reserved markers

```
OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
```

## Evidence

`inventory.json`, `coverage.json`, `p12_02_tests.json`, `RESULT.json`,
`official_runs.json`, `determinism.json`, run stdout/stderr.

## Next stage

`P12-03` — GetB0Table indirect service mediation.
