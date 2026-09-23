# P12-20 — Runtime / fail-closed hardening

Verdict: **PASS** (7 checks, deterministic twice).

Stage marker: `OPENRECOMP_P12_20=PASS`.

A public synthetic fixture exercises the composed Phase-12 dispatcher with
malformed and unsupported inputs:

| Input | Result |
|---|---|
| unknown host service id | status `6` (`UNKNOWN_HOST_SERVICE`) |
| `B0:0x57` with `argc=1` | status `13` (refused) |
| `B0:0x5b` with mode `2` | status `13` (refused) |
| `B0:0x5b` with `argc=0` | status `13` (refused) |
| `A0:0x44` with `argc=1` | status `13` (refused) |
| null guest target read (`0`) | status `1` (out of range) |
| unknown `B0` entry `0x10` | `0x00000000` |

`service_calls=5`, `service_failures=4`. The production runtime contains no
private-fixture path and still ends in `return P9_RT_UNKNOWN_HOST_SERVICE;`
(no permissive fallback).

Evidence: `hardening.json`, `p12_20_tests.json`, `RESULT.json`,
`official_runs.json`, `determinism.json`, run stdout/stderr.
