# P4-03 result (PASS)

Stage: `P4-03` Runtime service mediation (frozen queue row).
Gate: `tools/test_phase4_runtime_services_v1.py` (86 checks, sha256
`ea5f22d636cbac4cdaa275cdb43fccf321257b45d91171cc25ff1de263973b26`).
Evidence: `.openrecomp-phase4/evidence/P4-03/`.

Markers issued:

- Stage marker: `OPENRECOMP_P4_03=PASS`
- Gate marker: `OPENRECOMP_PHASE4_RUNTIME_SERVICES_V1=PASS tests=86`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

## Objective (frozen queue)

Replace fixture-specific external handling with explicit typed/versioned
runtime service interfaces. Unknown or unsupported services fail closed.
Generated code must not silently call arbitrary host functionality.

## Implementation (additive Phase-4 files only)

- `.openrecomp-phase4/src/p4_runtime_services_v1.py`:
  - architecture-neutral interface catalog `or.runtime.exit` (typed `u32`,
    terminating) and `or.runtime.stream_write` (typed `u32,u32`);
  - `ServiceRegistry` with bounded, versioned resolution;
  - declarative `ServiceAlias` mappings with bound arguments, so the frozen
    instance's `p3.exit` / `p3.uart_write` handling becomes data
    (`p3.exit -> or.runtime.exit`; `p3.uart_write -> or.runtime.stream_write`
    stream 0);
  - `RuntimeServiceMediator` with fail-closed mediation (unknown /
    version-mismatch / arity / typed-argument / missing-handler /
    handler-failure codes, first-failure latch, explicit termination) and a
    deterministic call log;
  - `AbiHostCallBridge` exposing only the numeric services of a declared
    profile over the mediator;
  - a generic bounded byte sink usable as the stream handler.
- `tools/test_phase4_runtime_services_v1.py` — the P4-03 gate.
- `.openrecomp-phase4/SOURCE_SHA256SUMS.txt` — grown additively to ten
  entries.

No frozen Phase-1/Phase-2/Phase-3 file, gate, evidence byte or tag was
modified.

## Verification highlights

- `interfaces:*` / `reject:*`: catalog shape, core namespace, typed and
  versioned interfaces, exactly one terminating interface, invalid interface
  constructions rejected (outside namespace, unbounded types, incompatible
  version, empty description).
- `registry:*`: bounded resolution, version matching, duplicate/empty/bad
  entries rejected, deterministic document/fingerprint, and the registry
  document contains no fixture tokens.
- `aliases:*` / `mediator:*`: declared alias table exactly maps the frozen
  service ids; the mediator adapts arguments, logs calls deterministically,
  terminates on exit with the status preserved, fails closed after
  termination and after the first failure, and returns the exact failure codes
  for unknown service, version mismatch, arity, typed overflow/negative,
  missing handler and handler exception.
- `bridge:*`: numeric mapping for the frozen profile, unknown numeric id,
  arity/typed violations, and the exact status-code values (0, 6, 7, 8, 12,
  13, 14).
- `replay:*`: the exact frozen external interaction from the P3-08 native
  execution evidence (499 output bytes and exit status 0) is replayed through
  the generic mediator and the bounded sink; the mediated output is
  byte-identical, the call count is exact, the log document and fingerprint
  are deterministic across two runs, and the same calls fail closed when the
  declared aliases are absent.
- `capability:*`: the mediation module has no ambient host capability tokens;
  the frozen generated source passes the P4-01 verifier (externs/accessors/
  macros bounded); the only service macros the generated code can reach are
  exactly the declared profile services.

## Determinism

- Two consecutive official gate runs: exit 0, empty stderr, stdout
  byte-identical raw (3135 bytes, `cc2f73da...`) and LF (`a6705aec...`), and
  `p4_03_tests.json` byte-identical across both runs (`f59e9879...`).
- Evidence: `official_runs.json`, `determinism.json`.

## Regressions

- `tools/test_runtime_abi_v1.py` (P2-08) `PASS tests=169`.
- `tools/test_phase4_runtime_abi_v1.py` (P4-01) `PASS tests=156`,
  stdout byte-identical (`81c96314...`).
- `tools/test_phase4_guest_memory_v1.py` (P4-02) `PASS tests=113`,
  stdout byte-identical (`5cfc58f1...`).
- `tools/phase1_host_gates_v1.py` `PASS=44 FAIL=0 SKIPPED=2`.
- `tools/public_safety_scan.py` `OPENRECOMP_PUBLIC_SAFETY=PASS`.
- `tools/test_phase4_boundary_v1.py` (P4-00) `PASS tests=74`, stdout
  byte-identical (`953312d0...`), re-run with the documented frozen-gate
  boundary-context hygiene (`regression_hygiene.json`).

## Limitations

- The mediator is verified as a layer; the frozen Phase-3 native executable
  still runs its frozen support path, and adopting the mediator in an
  execution path is later-stage scope (P4-08/P4-09).
- The generic catalog currently declares control and byte-stream interfaces
  only; deterministic I/O channels, timing and input/event services are
  P4-04's frozen scope.
- `GENERIC_RUNTIME_STATUS=NOT_PROVEN`; the terminal and general compatibility
  markers stay reserved.

## Next stage

P4-04 — Deterministic I/O, timing and input.
