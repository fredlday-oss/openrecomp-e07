# P10-01 result: BREAK semantic classification

Status: `PASS` (111 checks)

Markers:

- `OPENRECOMP_P10_01=PASS`
- `OPENRECOMP_PHASE10_BREAK_V1=PASS tests=111`
- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase10_break_v1.py`.

## Instruction encoding

Two independent implementations agree: the OpenRecomp-authored bit-level
extraction (`.openrecomp-phase10/src/p10_exception_v1.py`) and the frozen
Phase-3 decoder.

| Word | Independent | Frozen |
|---|---|---|
| `break 0` | opcode 0, funct `0x0d`, code 0 | `break`, `external-trap`, no delay slot |
| `break 1` | opcode 0, funct `0x0d`, code 1 | `break`, `external-trap`, no delay slot |
| `syscall 0` | opcode 0, funct `0x0c`, code 0 | `syscall`, `external-trap`, no delay slot |
| `syscall 7` | opcode 0, funct `0x0c`, code 7 | `syscall`, `external-trap`, no delay slot |

The private site's encoding is `break` with code field 1 (`RECOGNIZED_UNSUPPORTED`,
`control_flow` true, `terminator` `external-trap`, `delay_slot` false,
`exception_transfer` true, no target).

## Architectural BREAK semantics

- `SYSCALL` (funct `0x0c`) and `BREAK` (funct `0x0d`) raise synchronous
  exceptions, not control transfers: no branch delay slot, no jump;
- `Cause.ExcCode` 8 = `Sys` (syscall) and 9 = `Bp` (break);
- for a synchronous fault `EPC` holds the address of the faulting instruction
  and `Cause.BD` = 0 unless the faulting instruction occupies a delay slot;
- the PS1 general-exception vector is `0x80000080` (BEV=0) and `0xBFC00180`
  (BEV=1);
- whether a handler ever returns to or past the faulting instruction is
  handler-specific and is explicitly NOT modelled.

## Public synthetic evidence

OpenRecomp-authored PS-X EXE fixtures (`psx_fixture_builder_v1`, unchanged)
isolate the behaviour:

- trap fixture (`beq`-taken reaches `syscall`; `jal` fall-through reaches
  `break`): the frozen frontier marks both sites reachable, records exactly two
  `external-trap` sites with "flow stopped", and reaches the direct call target
  and its delay slot normally;
- trap-terminator fixture (`break` followed by three non-target words): only
  one word is reachable - no fall-through successor is fabricated past a trap;
- trap-free twin fixture: the frozen Phase-8 structure bridge succeeds and
  reports no unresolved site, proving the failure is specific to the trap
  record;
- the frozen Phase-8 structure bridge on the trap fixture fails closed with
  `CONTROL_WITHOUT_DELAY_SLOT` at `0x80010010` - the exact Phase-9 blocker
  class, now shown to be structural (a trap record has no delay slot by
  definition and must not require one);
- delay-slot trap fixture (`break` in the delay slot of `jal`): the frontier
  records `control-transfer-in-delay-slot`, does not reach or fold the trap,
  and invents no call successor.

## Fail-closed classification negatives

`classify_trap_site` rejects, with stable codes: a non-trap record
(`NOT_A_TRAP_RECORD`), inconsistent trap flags (`TRAP_FLAG_MISMATCH`), a trap
that carries a delay slot (`TRAP_HAS_DELAY_SLOT`), a trap that carries a target
(`TRAP_HAS_TARGET`) and a recorded code field that disagrees with the encoded
word (`TRAP_CODE_OUT_OF_RANGE`).

## Private site context (non-reconstructive)

- site `0x80013390`, code field 1, exception `Bp`, `EPC` = site, `BD` = 0, no
  successor, vectors `0x80000080` / `0xbfc00180`;
- region start `0x800132e8` = the PS-X EXE entry point; no reachable function
  return exists between the region start and the site, so the site lies in the
  entry function body;
- reached only by fall-through (`inbound_target_count` 0); the predecessor
  chain is the direct-call continuation at `0x80013388` followed by its
  delay-slot word at `0x8001338c`;
- the region contains consecutive zero stores (`sw` with `rt` = `$zero`) and
  self-incrementing `addiu` address arithmetic, and its two direct call targets
  are `0x80011af0` and `0x800119c8`; the word after the site is not reachable
  code;
- role classification: `entry-function-terminator-after-application-entry-call`.
  Assertion/debugger semantics, BIOS handler behaviour and continuation after
  the exception are explicitly NOT claimed;
- dynamic reachability: `NOT_YET_DETERMINED` (static:
  `REQUIRED_BY_FALLTHROUGH`), to be resolved by bounded native execution at
  `P10-05`.

The three reachable trap sites classify as one `break` and two `syscall`
sites; the `break` code field is 1.

## Bounded handling strategy

- static: the trap becomes an explicit terminal exception site
  (`InstructionFlow.TRAP`, no successor, no delay slot, no fabricated
  fall-through);
- dynamic: executing such a site fails closed with an explicit `GUEST_BREAK` /
  `GUEST_SYSCALL` category; no exception delivery, no BIOS handler, no
  continuation and no vector dispatch is invented;
- a trap inside a delay slot (BD = 1) is a different case and is rejected as
  unsupported rather than folded.

No generic exception machinery was added: the shared OpenRecomp layers
(`openrecomp`, `adapters`, `src`, `include`, `contracts`, `schema`) are
unchanged from the Phase-9 terminal commit, and the classification module
exposes no handler-installation, vector-dispatch or exception-delivery entry
point.

## Official runs

Command `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage P10-01
--script tools/test_phase10_break_v1.py --evidence-dir
.openrecomp-phase10/evidence/P10-01 --tests-json p10_01_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 10274 bytes (LF), sha256
`1b5cb8143fd090f4b70850220135682b9b9fbfc0f3d0aab809d2feec08b4e4e1`; generated
evidence sidecars byte-identical across both runs.

Sidecar identities:

- `break_classification.json` `9ec6fc593537127ea4425087f637487a451add0db820d635c7cdb0ea2d316f38`;
- `p10_01_tests.json` `9af15f142d6c7a23ac0c2792b6950d7b6dc075c88a8f4c8c4fb2131d225d9cc4`;
- `official_runs.json` `1117aa419566c568b7795b4eac1bc973ced1781ec54c35f622c75585f2be8045`;
- `determinism.json` `808cf333b43c473c9016a2b3547d796f52d16075308218325a3af47ba7dbc271`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Public safety

The committed classification record was leak-checked against the private
payload (no payload hex, no base64, no ASCII payload run, no string over 128
characters). Only encodings, addresses, classification names, counts and
exception-vector facts are recorded.

## Claim-ledger delta

`PROVEN`: the architectural BREAK/SYSCALL classification and the bounded
handling strategy. `BOUNDED` (private only): the exact site context and role
classification. Dynamic reachability, native execution, playability and
general PS1 compatibility remain `NOT_PROVEN`.

## Next stage

`P10-02` - reconcile `CONTROL_WITHOUT_DELAY_SLOT` without manufacturing a
delay slot, and re-run the Hercules structure analysis for the new frontier.
