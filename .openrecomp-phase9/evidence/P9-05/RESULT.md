# P9-05 result: PS1 BIOS/service boundary

Status: `PASS` (88 checks)

Markers:

- `OPENRECOMP_P9_05=PASS`
- `OPENRECOMP_PHASE9_BIOS_BOUNDARY_V1=PASS tests=88`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase9_bios_v1.py`.

## Implementation

`.openrecomp-phase9/src/p9_bios_boundary_v1.py` defines an explicit, typed,
versioned host-side service boundary. No BIOS image, BIOS code or firmware is
used anywhere (`bios_image: none`).

- The boundary declares the three BIOS jump-table vectors (A0/B0/C0) as
  recognized but unimplemented services; any invocation fails closed with
  `UNIMPLEMENTED_SERVICE`, and any unknown service id fails closed with
  `UNKNOWN_SERVICE`.
- Reachable indirect call sites are discovered from the frontier records and
  classified by a bounded (8-instruction, basic-block-limited) backward scan
  of the call register definition:
  - `BIOS_TABLE_CALL_CANDIDATE` only when an immediate A0/B0/C0 value is
    loaded into the call register immediately before the call;
  - `INDIRECT_TARGET_IMMEDIATE_NOT_BIOS` for other immediate values;
  - `INDIRECT_TARGET_FROM_MEMORY_UNRESOLVED` for memory-sourced targets;
  - `INDIRECT_TARGET_COMPUTED_UNRESOLVED` for computed targets;
  - `INDIRECT_TARGET_UNKNOWN` when no definition is found in the bounded
    window. Targets are never guessed.

## Public fixture

The original public fixture reaches no BIOS/service call: 0 sites, 0
candidates, `requirement: not-required-by-public-fixture`.

An injected BIOS-style A0 call (`addiu v0, zero, 0xA0; jalr v0`) is
discovered as exactly one `BIOS_TABLE_CALL_CANDIDATE` with vector `A0`, and
invoking `bios-A0` fails closed (`UNIMPLEMENTED_SERVICE`).

## Private fixture classification (metadata only)

All 22 reachable indirect call sites are classified exactly:

| Class | Sites |
|---|---|
| `BIOS_TABLE_CALL_CANDIDATE` (B0) | 3 |
| `INDIRECT_TARGET_UNKNOWN` | 19 |

The three BIOS B0 candidates are at `0x80015fa4`, `0x80026ebc`, `0x80026f74`
(each defined by `addiu $t2, $zero, 0xb0` immediately before the call). They
are candidates only: no BIOS function is implemented and each would fail
closed. The remaining 19 sites have no call-register definition inside the
bounded basic-block window and are explicitly unresolved. No payload bytes are
present in the evidence; the fixture is explicitly `is_pass_criterion: false`.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-05
--script tools/test_phase9_bios_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-05 --tests-json p9_05_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 3063 bytes (LF), sha256
`1e50dfe3446a95aa55cfc5498416b5d55933a14ac62e4ab83eb30ecc96701667`.

Sidecar identities:

- `p9_05_tests.json` `d4ebe808a6a49a13df46db33f333e4eb7114caecc19a1486bb044a1c27a5af6a`;
- `public_bios.json` `b77973b3d3fc6edc437059dc29b1961bc2fcf556d177793c97262bfc7454747b`;
- `private_bios.json` `d8705b228b30ad0e26466114919f6950ecc5b548e1e697f3e7b44a210f365dd2`;
- `official_runs.json` `dbfa75e225b5e81fbcde4806a84f21bb64dee9677c8ff60b1b1aafa2a22a1c1c`;
- `determinism.json` `8538cc3a92163de76028973368cbf355a8438ba7282196036e1af8ed1b6eda58`;
- `run1.txt` = `run2.txt` `1e50dfe3446a95aa55cfc5498416b5d55933a14ac62e4ab83eb30ecc96701667`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Claim-ledger delta

`BOUNDED`: a typed, versioned, fail-closed BIOS/service boundary exists; the
public fixture requires no BIOS service, and the private fixture's reachable
indirect call sites are classified into BIOS B0 candidates (3) and explicit
unknowns (19) with no BIOS implementation. No GPU, input/timer, SPU or CD-ROM
service is claimed here.

## Next stage

`P9-06` - PS1 GPU/runtime boundary: identify reachable GPU/GP0/GP1-facing
behaviour, create a clean platform adapter boundary, do not attempt full GPU
emulation unless evidence requires it, and keep unknown commands explicit
unresolved blockers.
