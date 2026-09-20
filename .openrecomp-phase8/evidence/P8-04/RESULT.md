# P8-04 result: translation frontier closure

Status: `PASS` (30 checks)

Markers:

- `OPENRECOMP_P8_04=PASS`
- `OPENRECOMP_PHASE8_TRANSLATION_CLOSURE_V1=PASS tests=30`
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
`3df423e0efdd1b6d0c91ce9f95bd33d0b58f08833226314bd43aff407751c704`). The
emitted text contains width-8 reads/writes, sign extension, conditional
select, link-register writes and the generic runtime ABI surface, and no
guest machine code.

## Correction: `movz` operand roles (found while preparing P8-09)

The first revision of the `movz` rule implemented the condition on `rs` and
the moved value from `rt`, which is inverted from the MIPS32 definition
(`if GPR[rt] == 0 then GPR[rd] = GPR[rs]`). The synthetic differential vector
originally used the same inverted convention in its Python model, so both
sides agreed and the defect was not observable. The rule and the reference
model are corrected to the architectural definition, and the synthetic vector
now distinguishes the two conventions (`r12 = 7` with `r13 = 0`, `r14 = 7`).

This changed the emitted program fingerprint from `6a957bd1...` to
`3df423e0...`; the P8-06..P8-08 evidence was regenerated against the
corrected emission (recorded in the corresponding stage records). The frozen
fixture's audited run has no `movz` mismatch path, so its observable record is
unchanged apart from the corrected rule's effect on the emitted text.

## Differential execution of the new semantics

A synthetic MIPS32 program exercising byte loads/stores, word round-trip,
`movz`, folded non-nop delay slots on taken/not-taken/call/return paths and
the `$ra` save/clobber/restore pattern was emitted, compiled with the
existing deterministic build pipeline (`EXECUTABLE_REPRODUCIBLE`), executed,
and compared against an independently written Python MIPS32 reference model:

- registers: `r7 = 0xffffff80` (`lb` sign extension) vs `r6 = 0x80`, `r8 =
  0x7f`, `r9 = 0x7f` (`lbu`/positive `lb`), `r10 = 0xffffff80` (word
  round-trip), `r12 = 7` (`movz` not taken once with `r11 = 5`, then taken
  with `r0 = 0` moving `r14 = 7`);
- delay-slot order: `r15 = 0x11` (taken-branch delay), `r18 = 0x44` (call
  delay), `r20 = 0x66` (return delay), `r22 = 0x99` (callee return delay);
- not-taken path correctly skipped: `r16 = 0`, `r17 = 0`;
- link register: memory `[8..11] = 60 10 00 00`, i.e. the callee saved
  `$ra = 0x1060` (the `jal` continuation) even after clobbering `$31` as
  scratch;
- native exit code 0, `failed=0`, and every native register/byte equals the
  independent model.

## Official runs (post-correction)

Command `python tools/test_phase8_translation_v1.py`, exit 0, empty stderr,
both runs byte-identical: stdout 1168 bytes, raw sha256
`0cd067e19ae98a3cfb726d31d1bd17049e236521f9e3432dbc983fd0f40c97d3`, LF
sha256 `08933cbfd0d18c2a643cfda803f45ce41ec2c2d650fe321cff140150f6ac2929`.

Sidecar identities: `translation_closure.json`
`30738072d9694504102d24a6fc53a5db916b703e7e3581a9c88a556cb1cef32f`,
`p8_04_tests.json`
`a4b28dd96c4d47dc8d9090a86b44f299034e6c118602afa8f069acb211dfd00e`.

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
