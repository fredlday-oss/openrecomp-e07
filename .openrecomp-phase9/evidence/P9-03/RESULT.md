# P9-03 result: existing MIPS32 pipeline integration

Status: `PASS` (66 checks)

Markers:

- `OPENRECOMP_P9_03=PASS`
- `OPENRECOMP_PHASE9_PIPELINE_V1=PASS tests=66`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase9_pipeline_v1.py`.

## Implementation

- `.openrecomp-phase9/src/p9_image_bridge_v1.py` feeds a validated PS-X EXE,
  through its explicit PS1 address-space contract, into the frozen pipeline
  `p3_code_frontier_v1.analyze` -> `p8_structure_v1.analyze_structure` ->
  shared ProgramModel / CFG / functions / call graph / translation units. No
  MIPS pipeline is forked or duplicated and no frozen module is modified.
- `.openrecomp-phase9/fixture/p9_public_fixture_v1.py` is the original
  OpenRecomp-authored public fixture: 46 words of direct-call-only MIPS32 that
  reads the controller and timer ports and writes GPU GP0/GP1, SPU and CD-ROM
  command ports, then returns to the host boundary.

Reuse is verified by hash against the frozen manifests:
`p3_code_frontier_v1.py` `f02c4e75...`, `p3_decode_mips32_v1.py`
`c808a23a...`, `p8_structure_v1.py` `24109660...`.

## Public fixture pipeline (exact counts)

| Quantity | Value |
|---|---|
| region / reachable words | 46 / 46 |
| reachable supported / unsupported / invalid | 46 / 0 / 0 |
| delay slots / non-nop | 7 / 0 |
| branches / direct calls / returns | 2 / 2 / 3 |
| indirect calls / jumps / unsupported transfers | 0 / 0 / 0 |
| unresolved sites | 0 |
| neutral instructions | 39 |
| folded delay slots | 7 |
| blocks / edges | 9 / 8 |
| functions / translation units | 3 / 3 |
| internal / external / unresolved call edges | 2 / 0 / 0 |
| unowned / shared blocks | 0 / 0 |
| entry function / unit | `fn_80010000` / `tu_fn_80010000` |

Fingerprints: program model `99024c48...`, CFG `e35974b4...`, call graph
`542d69e7...`, units `aa5614f9...`, discovery `fff9df3a...`. Two analyses
produce the same digest.

## Fail-closed indirect control flow

An injected `jalr` in an appended reachable function produces exactly one
unresolved site at `0x800100b8` (`indirect-call`), a non-empty
`unresolved_sites` classification (`INDIRECT_CALL`, `UNRESOLVED_*`) and is
never guessed. The public fixture itself contains no indirect control flow.

## Private fixture pipeline (non-reconstructive metadata only)

The private Hercules fixture frontier: 4068 reachable words (3972 supported,
96 recognized-unsupported, 0 invalid), 3 exception sites, 22 indirect calls,
18 indirect jumps, 3 external traps; first unresolved blocker is a `break`
(external trap) at `0x80013390`. The frozen structure bridge fails closed at
that site with `CONTROL_WITHOUT_DELAY_SLOT` and no structure is fabricated.
No payload bytes are present in the evidence; the fixture is explicitly
`is_pass_criterion: false`.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-03
--script tools/test_phase9_pipeline_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-03 --tests-json p9_03_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 2783 bytes (LF), sha256
`9aab9c109059808c5024c8dc55280377aa4cfc879338968da1b57bc8216f63e6`.

Sidecar identities:

- `p9_03_tests.json` `09d375e141be16931d8b26c8e47d1dfeec51dba71db1ca32929f3b5a68c08a8d`;
- `public_pipeline.json` `470bd1c5e2fa63498fae84b1ada4086328dcc8c04bd4ec8b16e5d32b620041db`;
- `private_pipeline.json` `2617c57dc7239c6c01a8d724494695bc6ba3fea607571f09bb523e750764e127`;
- `official_runs.json` `0c3fed93e86aa503ee8f5ee317505b43c2c71f87d1965512c89ebf694877659c`;
- `determinism.json` `0f24dfc39c9f35a2af5bd21277bc4634ad91a03c4908b69362f4bc5eb5372491`;
- `run1.txt` = `run2.txt` `9aab9c109059808c5024c8dc55280377aa4cfc879338968da1b57bc8216f63e6`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Claim-ledger delta

`BOUNDED`: the frozen MIPS32 ProgramModel/CFG/function/call-graph/TU stack
consumes PS1 PS-X EXE code through the explicit PS1 address space for the
original public fixture (complete, deterministic) and characterizes the
private fixture frontier with a fail-closed first blocker. No translation,
emission, platform service or execution is claimed yet.

## Next stage

`P9-04` - reachable translation-frontier closure: classify every reachable
instruction exactly once, reuse the Phase-8 semantics/emitter paths, add only
directly required and independently verified semantics, and explicitly
classify unusual MIPS-I/COP0/GTE forms if encountered.
