# OpenRecomp Phase 8 Scope

Primary terminal claim (reserved `NOT_PROVEN` until P8-99):

`OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF`

Permanent broader marker (never promoted, even if P8-99 passes):

`OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN`

Permanent Phase-8 non-claims:

- arbitrary MIPS32 ELF compatibility;
- complete MIPS32 ISA support;
- complete o32 ABI support;
- arbitrary Linux binaries;
- dynamic linking;
- exceptions;
- floating point;
- coprocessors;
- privileged execution;
- arbitrary indirect-control-flow recovery;
- PS1 or PS2 compatibility;
- game or commercial-binary compatibility.

## Purpose

Phase 8 proves one bounded real MIPS32 end-to-end native recompilation path:

```
legally redistributable real MIPS32 ELF
  -> existing ELF ingestion
  -> existing MIPS32 decode/semantics
  -> shared ProgramModel / CFG / function recovery
  -> architecture-neutral translation
  -> host source emission
  -> OpenRecomp generic runtime / host interfaces
  -> native executable
  -> deterministic execution
  -> independently structured reference equivalence
```

The phase reuses the existing MIPS32 infrastructure and extends it only where
real Phase-8 evidence demonstrates a gap. It does not restart ELF32 ingestion,
the MIPS32 target policy, MIPS32 decoding, already-proven reachable semantics,
the shared ProgramModel/CFG/function/call-graph layers, the generic runtime,
the host emitter, or the native ABI infrastructure.

Phase 3 proved this shape of claim for one audited CoreMark `-O1` build using a
Phase-3-specific whole-image emitter. Phase 8 targets a different, frozen,
legally redistributable compiler-produced MIPS32 ELF and drives it through the
existing architecture-neutral translation and host-emission path. Phase 3
remains the frozen authority for its own bounded claim; Phase 8 neither
inherits nor weakens it.

## Required proof boundary

A Phase-8 terminal `PASS` requires all of the following on one audited tree,
for exactly one frozen bounded fixture and its audited behaviour:

1. the exact frozen Phase-7 baseline identity is verified (annotated tag
   object, commit, tree, branch descent, and unchanged Phase-7 terminal
   evidence);
2. one legally redistributable, compiler-produced real MIPS32 ELF is frozen
   with recorded source/provenance, licence, acquisition/build path, SHA-256,
   ELF identity (class, endianness, machine, type, ABI, ISA, entry, segments,
   sections) and immutable fixture identity;
3. the fixture is driven through the existing ELF ingestion, target policy,
   decode, semantics inventory, executable-region discovery and reachable-code
   frontier, and the complete current frontier is deterministically
   characterized into explicit classes (already supported, recognized but
   unsupported, unresolved control flow, ABI/runtime gap, memory-image gap,
   translation gap, host-emission gap, toolchain/build gap);
4. the real ELF is driven through the existing neutral ProgramModel, CFG,
   function discovery, call graph and translation-unit structure; indirect
   control flow is either an exact target, a finite evidence-supported set, or
   explicitly unresolved/fail-closed, with no guessed targets;
5. every reachable translated instruction for the bounded fixture is either
   proven translatable or explicitly unresolved; any unresolved reachable
   instruction blocks the native proof;
6. static memory and runtime contract closure is proven for the fixture's
   executable memory, `.rodata`, initialized `.data`, zero-filled `.bss`, stack
   requirements, bounded guest memory access and host-service requirements,
   reusing the existing memory/runtime architecture; a Linux kernel is not
   emulated unless the fixture genuinely requires it, and then only as an
   explicit bounded contract;
7. host-source emission is deterministic through the existing host emitter:
   unchanged input produces byte-identical generated output, generated
   filenames are stable, content hashes are recorded, and no original MIPS32
   machine code executes at runtime;
8. the generated host program compiles through the existing host-native
   toolchain/runtime boundary with explicit toolchain provenance; one clean
   build path is recorded for terminal verification;
9. native execution is deterministic over a bounded observable record (exit
   value, agreed-boundary guest registers, guest memory digest, output/service
   transcript, operation/event counts, relevant runtime state) run twice with
   identical results;
10. an independently structured MIPS32 reference path (not merely the same
    translated semantics compared with itself) agrees with the native result
    over all required observables; any intentional difference is explicitly
    characterized, justified, proven bounded, and included in evidence, with
    no unexplained semantic delta;
11. a deterministic reusable workflow exists for the proven bounded path
    (ELF -> classification -> analysis -> translation -> host generation ->
    native build -> execution -> result evidence) with explicit fail-closed
    failure categories;
12. focused negative/fail-closed tests cover the new Phase-8 mechanisms
    (malformed or unsupported cases, deterministic rejection, no guessed
    recovery, no silent compatibility widening, no stale-cache acceptance, no
    generated-code execution after a required earlier classification failure);
13. deterministic evidence, whole-regression coherence, and an explicit
    `PROVEN` / `BOUNDED` / `UNPROVEN` / `UNSUPPORTED` / `NOT TESTED` claim
    ledger are complete, and no public evidence contains unauthorized or
    private binary material.

A `PASS` at P8-99 authorizes only this exact bounded audited fixture and
behaviour. It never authorizes the permanent non-claims listed above.

## Out of scope

Arbitrary MIPS32 ELF support; general MIPS32 compatibility; complete ISA or
o32 ABI support; Linux kernel emulation beyond an explicitly required bounded
host-service contract; dynamic linking; PIC; self-modifying code; exceptions;
floating point; coprocessors; privileged behaviour; cycle accuracy; console
hardware emulation; game or commercial-binary compatibility; PS1 or PS2
compatibility; performance claims; and any compatibility beyond the exact
audited fixture, toolchain profile, and observable contract.
