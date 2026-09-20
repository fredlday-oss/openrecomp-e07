# P8-04 result: translation frontier closure

Status: `PASS` (29 checks)

Markers:

- `OPENRECOMP_P8_04=PASS`
- `OPENRECOMP_PHASE8_TRANSLATION_CLOSURE_V1=PASS tests=29`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase8_translation_v1.py`.

## Additive shared-emitter extensions (`openrecomp/host_emitter.py`)

The minimum gaps measured at P8-02 were closed additively; the default
configuration remains byte-compatible with the frozen P2-07 output:

- `HostLoad` gained explicit `width_bits` and `signed` (byte/halfword loads
  with sign or zero extension); `HostStore` gained explicit `width_bits`;
- a new `HostSelect` operation expresses conditional-select semantics
  (`movz`/`movn`-class) using the existing comparison vocabulary;
- an opt-in folded delay-slot protocol
  (`HostEmitterConfig.delay_slot_metadata_key`) executes the delay-slot
  instruction declared by control-instruction metadata before the transfer on
  every path;
- an opt-in link-register contract
  (`HostEmitterConfig.link_register`) materializes the architecture return
  address (`address + 8`) at call sites, before the delay slot.

`HOST_EMITTER_VERSION` is unchanged because the default-format output is
byte-identical; the extension is opt-in. Direct dependency gates
`tools/test_host_emitter_v1.py` and `tools/test_mips32_end_to_end_v1.py`
re-pass unchanged (exit 0, empty stderr, markers present).

## Closed MIPS32 semantic rule table

New module `.openrecomp-phase8/src/p8_mips32_semantics_v1.py` declares
exactly the reachable fixture ops: `addiu addu andi beq bne j jal jr lb lbu
lui lw movz nop or ori sb sll sra srl sw xor`. Unsupported MIPS32 forms
(`div`, `divu`, `mult`, `multu`, `mul`, `movn`, `jalr`, `swl`, `swr`, `lwl`,
`lwr`, `lh`, `lhu`, `sh`) have no rule and fail closed with
`HostEmitterError`; a rule-flow disagreement and a folded delay slot on a
non-control instruction are also rejected.

## Full-fixture emission coverage

The frozen 486-instruction neutral structure emits successfully with the
closed table: every instruction has a rule, every rule flow agrees, all 23
folded delay sites are exercised, and two independent emissions are
byte-identical (97,830-byte C source, fingerprint
`6a957bd1639cebf8b702725682b3423accf0e01191a5fa73e9dc9849c9ff3294`). The
emitted text contains width-8 reads/writes, sign extension, conditional
select, link-register writes and the generic runtime ABI surface, and no
guest machine code.

## Differential execution of the new semantics

A synthetic MIPS32 program exercising byte loads/stores, word round-trip,
`movz`, folded non-nop delay slots on taken/not-taken/call/return paths and
the `$ra` save/clobber/restore pattern was emitted, compiled with the
existing deterministic build pipeline (`EXECUTABLE_REPRODUCIBLE`), executed,
and compared against an independently written Python MIPS32 reference model:

- registers: `r7 = 0xffffff80` (`lb` sign extension) vs `r6 = 0x80`, `r8 =
  0x7f`, `r9 = 0x7f` (`lbu`/positive `lb`), `r10 = 0xffffff80` (word
  round-trip), `r12 = 5` (`movz` taken once, not taken once);
- delay-slot order: `r13 = 0x11` (taken-branch delay), `r16 = 0x44` (call
  delay), `r18 = 0x66` (return delay), `r20 = 0x99` (callee return delay);
- not-taken path correctly skipped: `r15 = 0`, `r21 = 0`;
- link register: memory `[8..11] = 58 10 00 00`, i.e. the callee saved
  `$ra = 0x1058` (the `jal` continuation) even after clobbering `$31` as
  scratch;
- native exit code 0, `failed=0`, and every native register/byte equals the
  independent model.

## Official runs

Command `python tools/test_phase8_translation_v1.py`, exit 0, empty stderr,
both runs byte-identical: stdout 1132 bytes, raw sha256
`7a5369d9efc5633708b11d8fdc090e386c62a6498a0bb1391029b9921f938682`, LF
sha256 `37008ca0f36f025a01f4f73b7cd71966d973d9cc38a039a19dd8406aa682f262`.

Sidecar identities: `translation_closure.json`
`613af7cb756ede1cfc7770353bba082fee5f74e2188bf088b0ee2cb77e10b35f`,
`p8_04_tests.json`
`f4fe8ac6cff4882408409b4a2619289ed26ea906b343a6dce3fd410d97c2b250`.

## Claim-ledger delta

- New evidence: every reachable instruction of the frozen fixture is proven
  translatable through the existing neutral emitter, with the new semantics
  independently verified and unsupported forms still fail-closed.
- The full fixture has not yet been built or executed as a native program;
  the terminal marker remains reserved `NOT_PROVEN`.

## Limitations

- The rule table is closed to this fixture's reachable op set; it is not a
  general MIPS32 translation claim.
- Halfword accesses, partial-word stores, division/HI-LO, `movn`, branch-likely
  forms and coprocessor/FPU forms remain unimplemented and fail closed.
- Delay-slot folding requires the P8 bridge metadata; raw shared-model
  programs without it keep the original non-delay-slot behaviour.

## Next stage

P8-05: validate the fixture's static memory and runtime contract (executable
memory, `.rodata`, `.data`, zero-filled `.bss`, stack, bounded guest access
and the explicit output host service) by reusing the existing memory/runtime
architecture.
