# P12-01 — B0:0x5B ChangeClearPAD service V1

Verdict: **PASS** (35 checks, deterministic twice).

Markers: `OPENRECOMP_P12_01=PASS`,
`OPENRECOMP_PHASE12_B0_5B_CHANGECLEARPAD_V1=PASS`.

## Objective

Implement the minimum documented `ps1.bios.B0.5b` `ChangeClearPAD(int)`
semantics through the existing typed runtime/service mediation architecture,
with positive and fail-closed coverage.

## Implementation (additive, `.openrecomp-phase12/`)

- `src/p12_services_v1.py`: installs the documented Phase-12 B0 surface into the
  in-memory Phase-11 tables (`0x57` GetB0Table, `0x5b` ChangeClearPAD) and
  defines the synthetic project-owned window (`0x1f000000`, size `0x2000`).
- `src/p12_semantics_v1.py`: one explicit host-call rule per resolved BIOS site,
  supporting both `INDIRECT_JUMP` (`jr`) and `INDIRECT_CALL` (`jalr`) sites.
- `src/p12_runtime_v1.py` + `runtime/p12_bios_extension_v1.c`: the synthetic B0
  object window and the Phase-12 dispatcher chained after the Phase-11
  dispatcher; guest reads/writes route through the synthetic window first.
- `src/p12_emission_v1.py` + `src/p12_trace_v1.py`: the Phase-12 emission set and
  an additive observable-driver layer printing the `p12_*` observables.

## Semantics

- `ps1.bios.B0.5b` `ChangeClearPAD(mode)`: records the documented pad/card
  clear auto-acknowledge mode. Only `mode` in `{0,1}` is accepted; any other
  value or a wrong argument count fails closed (`status 13`). No SIO, interrupt,
  DMA or device behaviour is modelled.
- The fixture's seven direct callers use `a0 in {0,1}` (reconnaissance), so the
  proven path is fully supported; broader values fail closed.

## What the gate verifies

1. Service identity: exactly two B0 entries (`0x57`, `0x5b`), correct
   signature/return/name; no unrelated B0 entry implemented.
2. `service:synthetic-not-bios-address`: the synthetic window is outside every
   modelled RAM/IO/BIOS segment (it is not a recovered BIOS address).
3. Emitter path for modes 0 and 1: one resolved site, one rule, native build
   reproducible, deterministic, `p12_change_clear_pad` correct, void return
   preserved (`r2` sentinel) and continuation reached (`r16`).
4. Unrelated B0 entry `0x58` stays `BIOS_VECTOR_NOT_IMPLEMENTED` / `FAIL_CLOSED`
   with no service id.
5. Direct production dispatcher: GetB0Table returns the synthetic table base and
   entry `0x5B` equals the synthetic target; ChangeClearPAD mode 0/1 sets state;
   mode `2` and arity `0` fail closed (`status 13`, two service failures) while
   state is preserved; exact observable record.

## Reserved markers

```
OPENRECOMP_PHASE12_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_FRAME_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
OPENRECOMP_PHASE12_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
```

## Evidence

`service_surface.json`, `public_emitter.json`, `direct_dispatch.json`,
`p12_01_tests.json`, `RESULT.json`, `official_runs.json`, `determinism.json`,
`run1.txt`/`run2.txt`, `run1.err.txt`/`run2.err.txt`.

## Next stage

`P12-02` — complete B0:0x5B caller coverage.
