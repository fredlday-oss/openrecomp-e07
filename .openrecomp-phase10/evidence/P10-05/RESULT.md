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
| `p9_driver.c` | 7895 | the frozen Phase-9 observable driver |

Original MIPS machine code never executes:

- the guest payload bytes are absent from `program.c`;
- `program.c` contains no opcode dispatch (no decode loop) and does not include
  the image unit;
- the guest image is emitted as inert data and loaded into the RAM window by
  the runtime's `p9_runtime_init`.

Build: two isolated runs, both `OK`; executable SHA-256
`972a0ebb21b52971325b05aea4325e7950c1dbdf3b42b06f96686fc955d77b0b`; repeated
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
| accounted accesses | 1790128 (budget NOT reached) |
| termination category | `UNRESOLVED_INDIRECT_JUMP` |

The run is bounded by the explicit deterministic memory-access budget injected
by the third anchored runtime substitution; the budget was not reached, so the
first recorded failure is real game code and not truncation.

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
- the FIRST recorded failure is an explicit unresolved indirect jump (not a
  budget and not a host error);
- GPU/controller/SPU/CD-ROM port traffic was observed, which grounds the
  `P10-06` dynamic I/O discovery.

Not claimed: milestone B or beyond (no proof that initialisation completes), and
no rendering, audio, input or gameplay behaviour.

## Official runs

Command `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage P10-05
--script tools/test_phase10_native_v1.py --evidence-dir
.openrecomp-phase10/evidence/P10-05 --tests-json p10_05_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 1040 bytes (LF), sha256
`16efd5a639b0da54cabe21486247b021e305d4ad7c4509a2f72d772d1da72749`; generated
evidence sidecars byte-identical across both runs.

Sidecar identities:

- `emission.json` `bc5944628a99c4747a3902fa53e3a21b05a970c4fa5828efa7fa10507d2a93b9`;
- `native_entry.json` `8d7bc00ce95943809e409d48051a0f9cac60835cf4c68cae453cffefca815d21` (re-issued);
- `p10_05_tests.json` `3fcc99144156d3736a76325aad666234f49bd9a222a9809a577bb5cc5799da99`;
- `official_runs.json` `9fe66e1405c63efe3c7e53b4867cd897215f4d8034f3c45609e1d686d1fc8e1c` (re-issued);
- `determinism.json` `bc07dcb75fad1b4dc104efeda2415accbd498551f1bdd209d46e4027fcc49ba8` (re-issued);
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

## Re-issue note (documented, not silent)

Re-issued to correct the failure-semantics description. A fail-closed failure in
the generated code aborts the *current translated function* and is recorded as
the first failure; the caller then continues. Therefore the recorded traffic
(982859 reads, 799023 writes, the platform events and the 11 denied accesses)
includes progress after the first failure, and the first failure - an executed
unresolved indirect jump - is the termination category. The earlier wording
("the run stopped at ...") overstated the stopping behaviour; no observable
value changed and the gate was re-run twice with byte-identical stdout.
