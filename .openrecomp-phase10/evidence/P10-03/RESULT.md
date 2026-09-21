# P10-03 result: Hercules CPU/control frontier iteration

Status: `PASS` (144 checks)

Markers:

- `OPENRECOMP_P10_03=PASS`
- `OPENRECOMP_PHASE10_SEMANTICS_V1=PASS tests=144`
- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase10_semantics_v1.py`.

## Added semantics (additive, no redefinition)

24 reachable op types without a frozen Phase-8 rule gained rules, and the
`jr_indirect` classification op (the frozen frontier's indirect-jump
classification of a `jr` whose source register is not `$ra`) gained its own
`INDIRECT_JUMP` rule; 47 rules total:
`addi`, `and`, `bgez`, `bgtz`, `blez`, `bltz`, `break`, `jalr`, `lh`, `lhu`,
`lwl`, `lwr`, `mfhi`, `mult`, `sh`, `slt`, `slti`, `sltiu`, `sltu`, `subu`,
`swl`, `swr`, `syscall`, `xori` (22 frozen + 25 added).

- the frozen Phase-8 rules are reused byte-identically and no frozen op is
  redefined;
- scalar forms use the existing architecture-neutral vocabulary
  (`HostBinop`/`HostCompare`/`HostLoad`/`HostStore`/`HostComparison`);
- forms the bounded scalar vocabulary cannot express exactly use explicit host
  services declared by the rule table:
  `openrecomp.mips.lwl`, `.lwr`, `.swl`, `.swr`, `.mult`, `.mfhi`,
  `.add.overflow.check`;
- no rule is added for any op type outside the reachable frontier (`div`,
  `divu`, `mul`, `movn`, `mflo`, `mthi`, `mtlo`, `tge`, `teq` remain
  unruled);
- `break`/`syscall` are `InstructionFlow.TRAP` terminal rules; `jalr` is an
  `INDIRECT_CALL` rule with the target register as its indirect source, and a
  fail-closed precondition rejects any `jalr` that does not use `$ra`.

## Runtime reuse, not a parallel runtime

`.openrecomp-phase10/runtime/p10_mips_extension_v1.c` is spliced into the
frozen Phase-9 bounded PS1 platform runtime translation unit by
`.openrecomp-phase10/src/p10_runtime_v1.py`:

- the frozen source SHA-256 is verified against the frozen Phase-9 source
  manifest before any substitution
  (`59507a2c…` = manifest value);
- exactly one anchored block (the `or_rt_host_call` stub) is replaced
  (one occurrence, anchor SHA-256 recorded);
- the composed source equals the frozen source with that single substitution,
  so the guest address translation, platform port boundary, virtual
  time/input, counters and event transcript are the Phase-9 runtime verbatim;
- the extension reuses the Phase-9 static helpers directly because it is in
  the same translation unit.

## Independent reference agreement

An independently structured bounded MIPS32 interpreter
(`.openrecomp-phase10/src/p10_reference_mips_v1.py`: own decoder, own memory
model, own delay-slot order, no emitter/rule-table/runtime-ABI import) executed
the synthetic PS-X EXE that exercises every added non-trap op.

Native build: 2 isolated runs, both `OK`; executable SHA-256 recorded; the
driver stdout is byte-identical across repeated executions. All 32 guest
registers, the guest RAM digest, the exit status and the not-failed state match
the reference exactly. Recorded fixture: 84 words, 81 executed steps, exit
status `0x00001eee` (the branch-direction marker sum).

Unaligned merges were independently cross-checked against the frozen Phase-3
`swl`/`swr` byte-level model for 20 vector cases (4 alignments x 5 values)
including the round trip; all pass. `mult`/`mfhi` (signed 32x32 -> HI/LO
`0xffffffff:0xffffffeb` for `-3 * 7`) and the `addi` overflow boundary were
also checked in the reference.

## Fail-closed negatives (native, all build and run)

| Negative | Result |
|---|---|
| execute `break 1` | `failed=1` |
| execute `syscall 0` | `failed=1` |
| `addi` signed overflow | `failed=1` |
| executed unresolved `jalr` (indirect call) | `failed=1` |
| `lwl` at an unmapped address | `failed=1` |

No exception delivery, no fabricated continuation, no guessed indirect target
and no host-filesystem substitution is introduced. Signed `addi` overflow fails
closed with an explicit runtime failure instead of wrapping silently.

## Private frontier closure

The private Hercules structure satisfies every Phase-10 semantics
precondition: 22 `jalr` sites, all with `$ra` as the link destination, all 635
folded delay slots have rules, and no reachable op type is left without a rule
(`unruled_ops` empty) - i.e. the whole reachable program is now emittable
through the existing architecture-neutral emitter.

## Official runs

Command `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage P10-03
--script tools/test_phase10_semantics_v1.py --evidence-dir
.openrecomp-phase10/evidence/P10-03 --tests-json p10_03_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 4129 bytes (LF), sha256
`9e6acd76aa3bfef6d5c9415266f61552bacaee4688ccc70600dbd6a8d8aae078`; generated
evidence sidecars byte-identical across both runs.

Sidecar identities:

- `emission.json` `b88281c14ae0ff4f70683b9dd03e89926fedc2fe93780ff480baa0fe2f059c3c`;
- `native_comparison.json` `03c251707d3e0c7706974733e69e1c62cb462f9b79f4db3a4393ed6b7166ec5c`;
- `fail_closed_negatives.json` `0405e41d1c75aac9b609958e69eb0b7ce0b2ef8637ae08dcf6b7f71b72211a44`;
- `frontier_closure.json` `45db1afda03320f217e7bd8389003d82176a779dde7063678e18737379186de4`;
- `p10_03_tests.json` `ceb067ab3e4c8e27524ba13b40be406a75e40374c2727daf89fdd69e3aaeea87`;
- `official_runs.json` `4e317d113ffc17748e20289aad478720a03e7802673f57e3831d3d2b83e909e9`;
- `determinism.json` `cb426e30a8d33bae20997d94ec07cdaca3c21f93f439fef3aee8da9a9d1c4fe5`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Public safety

Only OpenRecomp-authored fixture words and non-reconstructive metadata are
recorded. The private-record sidecar contains the private PS-X EXE identity
metadata (hashes, header fields, addresses, counts) only; no payload bytes, no
disassembly and no disc material.

## Claim-ledger delta

`PROVEN`: the additive semantic rules, the exact unaligned/HI-LO/overflow
behaviour, the fail-closed negatives and the native/reference agreement for the
exercised op set. `BOUNDED` (private only): the frontier closure record.
Indirect control flow remains unresolved and fail-closed at runtime; native
execution, playability and general PS1 compatibility remain `NOT_PROVEN`.

## Next stage

`P10-04` - Hercules BIOS frontier.

## Re-issue note (documented, not silent)

Re-issued during the `P10-05` boundary: the guest run is now bounded by an
explicit memory-access budget (a third anchored substitution in the Phase-10
runtime composition), the neutral indirect-jump classification op
`jr_indirect` gained its own rule, and the runtime composition checks were
generalised to the full anchored-substitution list. The semantics, the
independent reference agreement and the fail-closed negatives are unchanged;
the gate was re-run twice with byte-identical stdout (149 checks).
