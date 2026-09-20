# OpenRecomp Phase 9 Scope

Phase 9 is the bounded PS1 platform/runtime integration effort. It starts from
the frozen Phase-8 terminal boundary on branch
`phase8/mips32-end-to-end-native-v1` at commit
`61136fc37cf0810e64241addd8f57a91872bc0af`, tree
`f9262497b82fe0027c3b23432ba7bd8cbccdf433`.

Primary terminal claim (reserved `NOT_PROVEN` until P9-99):

`OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF`

Permanent broader markers (never promoted, even if P9-99 passes):

`OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`

`OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN`

## Purpose

Phase 9 proves one bounded PS1 platform/runtime integration path by reusing the
existing Phase-8 MIPS32 end-to-end native pipeline:

```
PS-X EXE
  -> PS-X EXE ingestion / load-image reconstruction
  -> existing MIPS32 decode
  -> shared ProgramModel / CFG / functions / call graph / translation units
  -> existing host emitter
  -> PS1 platform runtime adapter
  -> deterministic native build / execution
  -> bounded validation
```

Phase 9 does not restart or fork the MIPS32 pipeline: it reuses the existing
ELF-independent decode, semantics, structure, emitter, runtime-ABI, build and
reference infrastructure, and adds only the PS1-specific ingestion, address
space, platform-service boundary and validation evidence that real evidence
demonstrates is required.

## Public versus private evidence

The private Hercules `SLUS_005.29` fixture is a legally obtained local
validation input. It is never a public `PASS` criterion on its own, is never
committed, copied or byte-referenced into the repository, and only
non-reconstructive metadata (hashes, sizes, offsets, classifications, counts,
diagnostics) may appear in evidence.

Any public terminal claim requires a legally redistributable, OpenRecomp-
authored or otherwise openly licensed PS1 fixture constructed for this phase.
Its source, deterministic build path and exact hashes are recorded.

No BIOS image, firmware, console key, ROM or disc-image bytes are ever used,
committed or emulated. The PS1 BIOS/service boundary is a typed, versioned
host-side service contract, not a BIOS implementation.

## Required proof boundary

A Phase-9 terminal `PASS` requires all of the following on one audited tree:

1. the exact frozen Phase-8 terminal boundary (commit, tree, branch descent,
   terminal verdict evidence) is verified and every frozen Phase-1 through
   Phase-8 file and evidence record is unchanged;
2. PS-X EXE ingestion is exact, deterministic and fail-closed: magic, header
   layout, entry PC, GP, load address, payload size, memory requirements and
   hashes are validated; malformed or unsupported forms are rejected with
   stable categories and no guessed recovery;
3. the PS-X EXE payload is mapped into an explicit PS1 guest address-space
   model with named regions, permissions, stack and explicit KSEG handling;
   no silent address masking and no invented mappings;
4. the reachable executable frontier is fed through the existing Phase-8
   MIPS32 decode / ProgramModel / CFG / function / call-graph /
   translation-unit stack, with recorded instruction/block/function/call/
   control-flow counts, and unresolved indirect control flow fails closed;
5. every reachable instruction is classified exactly once; semantics are
   reused from the Phase-8 paths where valid, and only directly required,
   independently verified semantics are added; COP0/GTE and unusual MIPS-I
   forms are explicitly classified if encountered;
6. reachable BIOS/system-service calls are discovered and represented by an
   explicit typed, versioned service boundary; only services required by the
   bounded fixture are implemented; unknown services fail closed;
7. GPU/GP0/GP1-facing behaviour is identified behind a clean platform adapter
   boundary; full GPU emulation is not attempted unless evidence requires it;
   unknown commands remain explicit unresolved blockers;
8. controller, timer, event and interrupt requirements are classified, with
   deterministic virtual-time/input/event interfaces added only as required;
9. reachable audio/SPU interactions are classified behind an explicit audio
   service/runtime contract; unsupported behaviour fails closed;
10. disc/file/streaming requirements reachable from the fixture are
    classified; only bounded required services are implemented; disc-image
    bytes stay outside the repository and evidence;
11. native host code is emitted through the existing architecture-neutral
    path, built reproducibly, and executed repeatedly with byte-identical
    deterministic observables (state, transcript, counters);
12. the private Hercules fixture is run through the complete bounded path and
    the exact reachable frontier and first unresolved blocker (if any) are
    recorded; private-fixture success never implies public or general
    compatibility;
13. negative/fail-closed tests, cache/stale-evidence tests, clean rebuilds,
    repeated deterministic execution and source/evidence manifest
    re-verification are complete;
14. an explicit `PROVEN` / `BOUNDED` / `NOT_PROVEN` / `NOT_TESTED` claim
    ledger separates the exact evidence-supported PS1 integration claim from
    every unproven area.

## Out of scope

General PS1 compatibility; PS1 BIOS emulation; any real commercial game
playability claim; GPU/SPU/CD-ROM/controller hardware emulation beyond the
bounded service contract; PS2 compatibility; complete MIPS-I/MIPS32 ISA or
o32 ABI support; COP0/GTE execution; exceptions and interrupt delivery;
cycle accuracy; performance claims; and any compatibility beyond the exact
audited fixtures, toolchain profile and observable contract.
