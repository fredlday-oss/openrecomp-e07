# P8-03 result: real-ELF ProgramModel / CFG integration

Status: `PASS` (52 checks)

Markers:

- `OPENRECOMP_P8_03=PASS`
- `OPENRECOMP_PHASE8_PROGRAM_STRUCTURE_V1=PASS tests=52`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase8_structure_v1.py`.

## Implementation (additive, P8-specific)

New module `.openrecomp-phase8/src/p8_structure_v1.py` bridges the frozen
P3-03 frontier records of the P8-01 fixture into the existing shared
architecture-neutral layers (`openrecomp.program_model`, `cfg`, `functions`,
`call_graph`, `translation_units`, `indirect_control_flow`). No shared or
frozen module was modified.

Delay slots are modelled exactly by *folding*: the delay-slot record is
removed from the neutral instruction stream, the control instruction's
`size_bytes` becomes 8 so the shared continuation logic lands on
`address + 8`, and the delay-slot decode fields are attached to the control
instruction metadata under `delay_slot`. The model fails closed if a delay
slot is missing, non-adjacent, unreachable, itself a control transfer or trap,
or if any transfer targets a delay-slot address. `jr $ra` is a structural
return only where the frozen record carries the return terminator; any other
indirect transfer becomes an explicit unresolved site with no target.

## Structure facts

- neutral instructions 486 = 509 reachable words - 23 folded delay slots;
- folded delay slots 23 (16 non-nop: 6 `addiu`/`or`-class uses plus the
  documented non-nop set `{addiu, or, sb}`; 7 `nop`);
- CFG 27 blocks / 25 edges (5 `BRANCH_TAKEN`, 5 `BRANCH_NOT_TAKEN`,
  8 `CALL_RETURN`, 4 `FALLTHROUGH`, 3 `JUMP`);
- 7 functions, 7 translation units, 0 shared blocks, 0 unowned blocks;
- 8 internal direct call edges exactly equal to the frozen frontier's `jal`
  sites/targets; 0 external call edges; 0 unresolved call edges;
- flows: 463 NORMAL, 5 BRANCH, 8 CALL, 3 JUMP, 7 RETURN; no indirect flow,
  no trap;
- entry function `fn_2490`, entry unit `tu_fn_2490`;
- 0 unresolved indirect sites; every CFG target is a neutral instruction and
  none is a delay-slot address;
- fingerprints: program model
  `718f538ed53acacafb81ebe00d4effa29ab827ae2a5654de6662a62c46c8b60c`, CFG
  `8c51308cd9ad9bd7987f57637e23ab94bbfbf0a9eeac10fa73d259ac0a689e71`, call
  graph `8508c599d2869d1d32a24949c4b113112bf21a57c7c3c04a7a255c581220cd5b`,
  unit set `50034a80e085b9a80c9742dffd50521d24d1b76dfbc29e5dd6066c3f519ac33b`,
  discovery `2a9835556a8a3db0433060a2fe81d3647cc2cf1babdb234367f8b1a816fa528d`;
  two independent derivations produce identical summaries and fingerprints.

## Fail-closed coverage

Rejected with stable codes: unreachable delay slot (`DELAY_SLOT_UNREACHABLE`),
delay slot rewritten as a control transfer (`DELAY_SLOT_IS_CONTROL`), branch
target rewritten into a delay slot (`TARGET_INTO_DELAY_SLOT`), return record
whose register is not `$ra` (`RETURN_NOT_RA`), malformed analysis
(`INVALID_ANALYSIS`). A synthetic indirect-jump rewrite of a return record is
classified `UNRESOLVED_INDIRECT_JUMP` with no invented target.

## Official runs

Command `python tools/test_phase8_structure_v1.py`, exit 0, empty stderr, both
runs byte-identical: stdout 1841 bytes, raw sha256
`42385791c9384a814c09dbf6c9ebd5367843f0d45f0bd38fef9f817d60c45307`, LF
sha256 `32432dec71830ed2bbf479ad9e4234ad0b23b91cd35319e40b443e20c059e0ad`.

Sidecar identities: `structure_summary.json`
`ba4d98f20b915ee7c6d1d5e98c891abc54d39ffcc0920da2b014f156e419c7a1`,
`p8_03_tests.json`
`dd1404d3708bddd12867a0468b33c745dc45defad25f09ae54a53811d9ed8155`.

## Claim-ledger delta

- New evidence: the frozen real ELF has a complete, deterministic, neutral
  ProgramModel/CFG/function/call-graph/translation-unit structure with
  delay-slot folding and no guessed indirect targets.
- The structure is not yet translated, emitted, built or executed; the
  terminal marker remains reserved `NOT_PROVEN`.

## Limitations

- Delay-slot folding is exact for this fixture's reachable pattern (delay
  slots are non-control, non-trap, adjacent, and never transfer targets);
  other MIPS32 patterns remain unsupported and fail closed.
- The structural RETURN mapping relies on the frozen `jr $ra` terminator
  evidence; explicit non-`$ra` returns fail closed.
- Function identity is structural, not symbol-based; no symbol table is used.

## Next stage

P8-04: close the translation frontier gaps demonstrated at P8-02/P8-03
(byte-width memory forms, the `movz` semantic, the delay-slot emission
protocol and the o32 link-register contract) so that every reachable
translated instruction is proven translatable.
