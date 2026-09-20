# OpenRecomp Phase 8 Fixture Policy

## Frozen real MIPS32 ELF fixture

Phase 8 freezes exactly one legally redistributable, compiler-produced real
MIPS32 ELF (selected and recorded at P8-01).

- the source tree or upstream artefact must carry a legitimate redistribution
  licence and be pinned by repository identity and revision;
- the acquisition/build path is recorded and reproducible where practical;
- the ELF SHA-256, size, class, endianness, machine, type, ABI, ISA, entry,
  segments and sections are frozen as immutable fixture identity;
- a fixture built during the phase is produced twice in isolated roots and the
  two executables must be byte-identical;
- upstream sources, toolchain distributions, ELF files and build roots remain
  untracked and are represented only by provenance, metadata and hashes;
- no proprietary SDK, console, firmware, BIOS, key, ROM or unknown precompiled
  binary material may be used, committed, packaged, or copied into evidence;
- symbols may support evidence, but correctness may not silently depend on
  them;
- the fixture remains a bounded audit fixture, never a supported workload.

## Synthetic fixtures

Small original fixtures may be added only to isolate a specific, already
observed gap (instruction, delay-slot, control-flow, o32 ABI, memory, runtime
or fail-closed behaviour). Their source, generator/toolchain, flags and exact
output hashes must be recorded. Phase 8 is not designed around synthetic
instructions: the primary fixture is always the real frozen ELF.

## Private or commercial inputs

Private or commercial binaries are never a Phase-8 `PASS` criterion and are
never committed, packaged, copied or byte-referenced into evidence. If one is
used as a frontier detector, only derived classifications, hashes and metadata
may be recorded, and Phase-8 `PASS` must not depend on its success.
