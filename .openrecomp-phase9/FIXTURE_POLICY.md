# OpenRecomp Phase 9 Fixture Policy

## Public proof input

Any public Phase-9 terminal claim requires a legally redistributable PS1
fixture constructed or selected for this phase:

- an OpenRecomp-authored original PS-X EXE built by a deterministic,
  recorded generator (preferred), or an openly licensed PS1 program with a
  legitimate redistribution licence;
- source, generator/toolchain, flags, build path and exact output hashes are
  recorded;
- the fixture exercises only the bounded PS1 platform/runtime boundary the
  phase claims, and remains a bounded audit fixture, never a supported
  workload;
- no BIOS image, firmware, console key, ROM, disc image, proprietary console
  asset, SDK material or unknown precompiled binary may be used, committed,
  packaged or copied into evidence.

## Private Hercules fixture

The private `SLUS_005.29` fixture is a legally obtained local validation
input used for frontier detection and bounded end-to-end validation only.

- it is never a public `PASS` criterion on its own;
- it is never committed, packaged, copied or byte-referenced into the
  repository or evidence;
- only derived, non-reconstructive metadata may be recorded: hashes, sizes,
  header field values, offsets, region classifications, instruction/control
  flow counts, diagnostics, and the identity of the first unresolved blocker;
- no payload bytes, disassembly excerpts, strings, tables or any
  reconstructive derived data;
- failure or success of the private fixture never promotes
  `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY` or
  `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY`, which remain `NOT_PROVEN`.

## Synthetic fixtures

Small original fixtures may be added to isolate a specific, already observed
gap (PS-X EXE form, address-space region, instruction, delay-slot,
control-flow, service-boundary or fail-closed behaviour). Their source,
generator, flags and exact output hashes must be recorded. Synthetic fixtures
never replace the explicit private-fixture validation record.

## BIOS boundary

The PS1 BIOS/service boundary is a typed, versioned host-side service
contract. No BIOS image or BIOS-derived code is loaded, executed or emulated.
Unknown BIOS calls fail closed with an explicit unresolved record.
