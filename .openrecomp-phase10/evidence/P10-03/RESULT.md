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

24 reachable op types without a frozen Phase-8 rule gained rules:
`addi`, `and`, `bgez`, `bgtz`, `blez`, `bltz`, `break`, `jalr`, `lh`, `lhu`,
`lwl`, `lwr`, `mfhi`, `mult`, `sh`, `slt`, `slti`, `sltiu`, `sltu`, `subu`,
`swl`, `swr`, `syscall`, `xori` (46 rules total: 22 frozen + 24 added).

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
empty stderr, both runs byte-identical: stdout 3793 bytes (LF), sha256
`f84e7febe7c7f818fcae0aaad914c26c5db246274e348a4bbe46f98cb0b43bb2`; generated
evidence sidecars byte-identical across both runs.

Sidecar identities:

- `emission.json` `c200930dcafeb13b2df28159cfe7dbed73cf6e41000c2491ff1fa45193c20453`;
- `native_comparison.json` `2ecb9473b519b0fa68f7921f903f859ecaeb03c089ebd72bc1d681d611d8e941`;
- `fail_closed_negatives.json` `0405e41d1c75aac9b609958e69eb0b7ce0b2ef8637ae08dcf6b7f71b72211a44`;
- `frontier_closure.json` `00fe8082c0202a55477f2643d551a544b399d4934fe7078a7d9336e6f124388d`;
- `p10_03_tests.json` `d7078261166bf59fb3cc2bdc3004bda4d0205b78f74a444be82c77b27af91f81`;
- `official_runs.json` `f0c354095214f7d86b83a1808dd9f949fefb1176aeff3f18f66d923927c1e9be`;
- `determinism.json` `c24d531eb9a1c41f5a1e39db00c5aeb4667a46830040888a1be9ec194763a546`;
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
