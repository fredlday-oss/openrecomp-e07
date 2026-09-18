# P4-04 result (PASS)

Stage: `P4-04` Deterministic I/O, timing and input (frozen queue row).
Gate: `tools/test_phase4_deterministic_io_v1.py` (101 checks, sha256
`723d12b83c95fece05be45c0b1b7dad51bc5b1ac45ad5304de2fd7dde63c9538`).
Evidence: `.openrecomp-phase4/evidence/P4-04/`.

Markers issued:

- Stage marker: `OPENRECOMP_P4_04=PASS`
- Gate marker: `OPENRECOMP_PHASE4_DETERMINISTIC_IO_V1=PASS tests=101`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

## Objective (frozen queue)

Provide reusable bounded interfaces for deterministic console/file-style I/O
as required by the fixture, time/timers and input/event delivery. Host
nondeterminism must be explicitly controlled, recorded or rejected.

## Implementation (additive Phase-4 files only)

- `.openrecomp-phase4/src/p4_deterministic_io_v1.py`:
  - deterministic console with bounded output and an explicit input
    exhaustion policy (`EOF` sentinel or `FAULT`);
  - deterministic file-style buffers (bounded, read/write positions,
    read-only mode, digests) that never touch the host filesystem;
  - `VirtualClock` advanced only by explicit ticks (with overflow checks) and
    a bounded `EventQueue` with deterministic virtual-tick ordering
    (byte/key/timer/pointer events);
  - `RecordedInput` (console bytes, file images, event plan, initial tick)
    with a stable fingerprint: the complete declared input set of a run;
  - `IoRuntime` binding console, clock, queue and files, plus a structural
    rejection of ambient host input (`ambient_input` always fails closed);
  - typed/versioned `or.runtime.stream_read`, `or.runtime.clock_ticks` and
    `or.runtime.input_poll` interfaces composed onto the unmodified P4-03
    base catalog, with handlers bound to the `IoRuntime`.
- `tools/test_phase4_deterministic_io_v1.py` — the P4-04 gate.
- `.openrecomp-phase4/SOURCE_SHA256SUMS.txt` — grown additively to twelve
  entries.

No frozen Phase-1/Phase-2/Phase-3 file, gate, evidence byte or tag was
modified, and the P4-03 base catalog is unchanged.

## Verification highlights

- `record:*` / `reject:*`: digest stability and sensitivity, document shape,
  duplicate/invalid file names, non-bytes inputs, negative ticks, invalid
  events.
- `console:*`: byte reads, EOF sentinel, `FAULT` policy, bounded output
  capacity, byte-range validation, document/read tracking.
- `file:*`: reads, EOF, seek, append writes, capacity and read-only
  enforcement, name/capacity validation.
- `clock:*` / `events:*`: explicit advancement only, overflow rejection,
  document source `virtual`, tick ordering with insertion-order ties, no
  early delivery, queue bounds and event validation.
- `runtime:*` / `services:*`: console streams, virtual clock reads, event
  polling, unknown-stream and unknown-file failures, ambient-input rejection,
  the composed five-interface registry, and the unchanged P4-03 base catalog.
- `determinism:*`: the same record and the same scripted call sequence
  produce identical documents, fingerprints, output and event logs; the
  module has no ambient capability tokens (no host clock/random/filesystem/
  process imports).
- `replay:*`: the exact frozen Phase-3 output interaction (499 bytes from the
  P3-08 evidence) replays byte-identically through the I/O-bound mediator and
  no failure occurs.

## Determinism

- Two consecutive official gate runs: exit 0, empty stderr, stdout
  byte-identical raw (3378 bytes, `e55ad6cb...`) and LF (`13f1d323...`), and
  `p4_04_tests.json` byte-identical across both runs (`ad9624d2...`).
- Evidence: `official_runs.json`, `determinism.json`.

## Regressions

- P2-08 `PASS tests=169`; P4-01 `PASS tests=156` (`81c96314...`); P4-02
  `PASS tests=113` (`5cfc58f1...`); P4-03 `PASS tests=86` (`cc2f73da...`).
- `tools/phase1_host_gates_v1.py` `PASS=44 FAIL=0 SKIPPED=2`.
- `tools/public_safety_scan.py` `OPENRECOMP_PUBLIC_SAFETY=PASS`.
- P4-00 `PASS tests=74` (`953312d0...`) with the documented frozen-gate
  boundary-context hygiene (`regression_hygiene.json`).

## Limitations

- The I/O runtime is a declared interface layer; the frozen Phase-3 native
  path does not consume it yet (P4-08/P4-09 scope).
- Input is limited to recorded console bytes and virtual-tick event plans;
  host devices, wall-clock time and real filesystem access are deliberately
  unsupported (no ambient acquisition path exists).
- Event payloads are bounded to 64-bit codes/values; richer input schemas are
  platform-adapter scope (P4-05/P4-06).
- `GENERIC_RUNTIME_STATUS=NOT_PROVEN`; the terminal and general compatibility
  markers stay reserved.

## Next stage

P4-05 — Platform Adapter Interface V1.
