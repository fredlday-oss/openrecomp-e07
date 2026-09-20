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
| region / reachable words | 48 / 48 |
| reachable supported / unsupported / invalid | 48 / 0 / 0 |
| delay slots / non-nop | 7 / 0 |
| branches / direct calls / returns | 2 / 2 / 3 |
| indirect calls / jumps / unsupported transfers | 0 / 0 / 0 |
| unresolved sites | 0 |
| neutral instructions | 41 |
| folded delay slots | 7 |
| blocks / edges | 9 / 8 |
| functions / translation units | 3 / 3 |
| internal / external / unresolved call edges | 2 / 0 / 0 |
| unowned / shared blocks | 0 / 0 |
| entry function / unit | `fn_80010000` / `tu_fn_80010000` |

Fingerprints: program model `9592d14e...`, CFG `21ff2339...`, call graph
`55c6696e...`, units `133e2e35...`, discovery `32d85c4c...`. Two analyses
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

- `p9_03_tests.json` `80c6c26ffe5c5e50c9c70271193c29f468bd7f90407edd64d92a947fade08ce2`;
- `public_pipeline.json` `e7a0f8c43f53de030fb8f4a7396e42fb7d1835d0bfa41118e1a6d47eea94b586`;
- `private_pipeline.json` `2617c57dc7239c6c01a8d724494695bc6ba3fea607571f09bb523e750764e127`;
- `official_runs.json` `bbf5713eff65164c4c9cca0ace460039cb7acaa283b57c31b1cd73e2f5305f06`;
- `determinism.json` `308b182db6c1948a2cbb47e32d09a48a515f1c2cb4fe5678c57e84dc3354a444`;
- `run1.txt` = `run2.txt` `9aab9c109059808c5024c8dc55280377aa4cfc879338968da1b57bc8216f63e6`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Documented fixture correction (P9-10 preparation)

While preparing P9-10 it was found that the original public fixture relied on
an initial stack pointer that the frozen Phase-8 emitter does not provide (the
generated program starts all guest registers at zero). The fixture was
corrected to initialize `$sp` itself at entry (`lui $sp, 0x801f; ori $sp,
$sp, 0xfff0`), which is the standard freestanding entry pattern. The change is
additive (two instructions) and does not alter the fixture's platform
behaviour. The affected pinned counts/fingerprints in this stage were updated
and the official runs were re-issued on the corrected tree; the official
stdout identity is unchanged (`9aab9c10...`).

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
