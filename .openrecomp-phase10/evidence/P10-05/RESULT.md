# P10-05 result: native execution entry

Status: `PASS` (30 checks)

Markers:

- `OPENRECOMP_P10_05=PASS`
- `OPENRECOMP_PHASE10_NATIVE_ENTRY_V1=PASS tests=30`
- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase10_native_v1.py`.

## Generated native program

The private executable was translated through the existing architecture-neutral
emitter with the Phase-10 rule table and the Phase-10 runtime:

| Unit | Bytes | Role |
|---|---|---|
| `program.c` | 520039 | generated host C for 110 translated functions |
| `p9_image_v1.c` | 750534 | the 2 MiB guest RAM window with the loaded payload as inert data |
| `p9_runtime_support.c` | 28870 | the frozen Phase-9 platform runtime with three anchored Phase-10 substitutions |
| `p9_driver.c` | 6983 | the additive Phase-10 observable driver (frozen Phase-9 driver + bounded-execution counters + typed event transcripts) |

Original MIPS machine code never executes:

- the guest payload bytes are absent from `program.c`;
- `program.c` contains no opcode dispatch (no decode loop) and does not include
  the image unit;
- the guest image is emitted as inert data and loaded into the RAM window by
  the runtime's `p9_runtime_init`.

Build: two isolated runs, both `OK`; executable SHA-256
`937b359907e09cf802e95fef9ed75fb6a06b787d7e2c454b2f3354930dd70581`; repeated
execution byte-identical (stdout sha256 `16efd5a6…`).

## Recorded entry state

| Observable | Value |
|---|---|
| guest entry PC | `0x800132e8` |
| initial register state | all 32 guest registers zero-initialised by the generated entry |
| declared stack pointer (PS-X EXE) | `0x801ffff0` |
| observed `$sp` after the crt0 prefix | `0x801ffe00` |
| observed `$fp` | `0x80200000` |
| observed `$gp` | `0x8002ed78` |
| RAM window | 2 MiB, loaded-image digest `0x…` differs from the post-run digest |

The crt0 effect is directly observable: the guest's own entry function
zero-fills its BSS, materialises `$gp` (`0x8002ed78`), computes the stack
pointer from its stack table (`$fp` = `0x80200000`, `$sp` = `$fp - 0x200`) and
then calls the application entry. All of that happened as generated host code.

## Execution and termination

| Observable | Value |
|---|---|
| failed / error | `1` / `unresolved indirect jump` |
| exit status | `0x00000000` |
| guest RAM reads / writes | 982859 / 799023 |
| denied accesses | 11 |
| host service calls (Phase-10 MIPS services) | 79 |
| GPU / input / SPU / CD-ROM recorded events | 4096 (capped) / 4096 (capped) / 5 / 38 |
| access budget | 2000000 |
| access count | 2000005 |
| budget denials | 5 (exceeded) |
| accounted accesses (lower bound) | 1790128 (per-device transcripts are capped at 4096) |
| termination category | `UNRESOLVED_INDIRECT_JUMP` |

The run is bounded by the explicit deterministic memory-access budget injected
by the third anchored runtime substitution. The FIRST recorded failure is real
game code (an executed unresolved indirect jump); the budget was subsequently
exceeded (access count 2000005 vs budget 2000000, 5 budget denials), which is
what finally bounded progress.

The first fail-closed transition is an executed unresolved indirect jump: one
of the 18 reachable `jr`/`jr_indirect` sites. Its exact address is not
observable with the frozen Phase-9 driver (recorded as a limitation), so the
complete candidate set is recorded instead of a guessed site.

## Milestone

Milestone `A` - translated native execution begins - is established:

- the program built from the private executable runs deterministically to a
  fail-closed blocker;
- the guest crt0 effect is observable in the register file;
- over 1.78 million guest memory accesses executed and the guest RAM digest
  changed, so translated guest code really ran;
- the FIRST recorded failure is an explicit unresolved indirect jump, so the
  first fail-closed transition is real game code;
- the bounded-execution budget was subsequently reached, which bounded further
  post-failure progress;
- GPU/controller/SPU/CD-ROM port traffic was observed, which grounds the
  `P10-06` dynamic I/O discovery.

Not claimed: milestone B or beyond (no proof that initialisation completes), and
no rendering, audio, input or gameplay behaviour.

## Official runs

Command `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage P10-05
--script tools/test_phase10_native_v1.py --evidence-dir
.openrecomp-phase10/evidence/P10-05 --tests-json p10_05_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 1129 bytes (LF), sha256
`786c78009f58ea48c2a4a2ea9b0168be56b6df74657e9f3cadfef46aae6429ea`; generated
evidence sidecars byte-identical across both runs.

Sidecar identities:

- `emission.json` `bc5944628a99c4747a3902fa53e3a21b05a970c4fa5828efa7fa10507d2a93b9`;
- `native_entry.json` `ef7b834293e4e5ff1067c78154ccbbeac218276bea1375000bd380e3cb6c05e9`;
- `p10_05_tests.json` `468d8428ce9f127c02ec532035dbb00f00cc998ed2ffe1458be4bed34cfc25dc`;
- `official_runs.json` `d33448246917ff33c64138fd3327cdfbbb9614df0e5f4197d0a6dc9f3cd777e2`;
- `determinism.json` `ca85a5696ca53b62aec80f4dcb3cab5a0585ca9c2983845171e536d2ab43e613`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Public safety

The committed record contains hashes, addresses, register values, counts,
classification names and digests only. Generated sources and the built
executable remain untracked build products; no payload bytes, no disassembly
and no disc material is committed.

## Claim-ledger delta

`PROVEN`: deterministic translated native execution of the private
executable's entry and initialisation prefix, and the exact fail-closed
termination category. `BOUNDED` (private only): the execution record.
Native execution of the whole program, initialization completion, rendering,
playability and general PS1 compatibility remain `NOT_PROVEN`.

## Next stage

`P10-06` - dynamic PS1 I/O discovery from the reachable execution observed here.

## Re-issue notes (documented, not silent)

Second re-issue: the run now uses the additive Phase-10 observable driver, so
the exact bounded-execution counters are observable. The access count
(2000005) exceeds the budget (2000000), so the budget *was* reached after the
first failure; the earlier record derived a lower bound from the capped
event counters and wrongly reported the budget as not reached.

First re-issue: corrected the failure-semantics description. A fail-closed failure in
the generated code aborts the *current translated function* and is recorded as
the first failure; the caller then continues. Therefore the recorded traffic
(982859 reads, 799023 writes, the platform events and the 11 denied accesses)
includes progress after the first failure, and the first failure - an executed
unresolved indirect jump - is the termination category. The earlier wording
("the run stopped at ...") overstated the stopping behaviour; no observable
value changed and the gate was re-run twice with byte-identical stdout.
