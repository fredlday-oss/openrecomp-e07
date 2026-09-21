# OpenRecomp Phase 11 Fixture Policy

## Private commercial fixture

The legally obtained local PlayStation fixture lives outside version control in
the private fixture directory (repository-relative discovery, never a committed
absolute path):

```
<workspace>/fixtures/psx/hercules/
```

It contains:

- the primary executable `SLUS_005.29` (PS-X EXE), used as the frontier
  fixture;
- a CUE sheet, used as the authoritative disc-image entry point for
  CD-ROM/filesystem/streaming analysis;
- the BIN track image referenced by the CUE.

Rules:

- the CUE is the logical entry point; the BIN is never treated as the logical
  disc entry point when a valid CUE describes the track layout;
- CUE and BIN filenames are discovered from the directory, never assumed or
  hard-coded;
- the fixture is never committed, packaged, copied, redistributed or
  byte-referenced into the repository, evidence, tests, fixtures or generated
  code;
- no payload bytes, disassembly excerpts, strings, jump tables, sectors, files,
  framebuffers, VRAM content, textures, palettes or any reconstructive derived
  data are committed, in any encoding;
- only non-reconstructive metadata may be recorded: hashes, sizes, filenames,
  PS-X EXE header fields, track layout metadata, ISO9660 filesystem metadata,
  load/entry addresses, instruction/control-flow classifications, counts,
  function/block identifiers, BIOS/service identifiers, MMIO classifications,
  sector/file access classifications, bounded execution transcripts, failure
  categories, state digests and runtime observables;
- the private fixture is never a public `PASS` criterion on its own and never
  promotes `OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY` or
  `OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF`;
- a stage that touches the private fixture must include a public-safety check
  proving the committed evidence contains no private binary material and no
  private host path.

## Public reproducers

Where a newly discovered mechanism needs a public reproducer, construct the
smallest legal synthetic or openly licensed fixture that isolates exactly that
mechanism. Its source, generator, flags and exact output hashes are recorded.
Synthetic fixtures never replace the private-fixture validation record and are
never treated as supported workloads.

## Prohibited material

No BIOS image, firmware, console key, ROM, disc image, proprietary console
asset, SDK material, unknown precompiled binary, toolchain distribution,
generated executable, native build product or upstream source tree may be
committed, packaged or copied into evidence.

## BIOS boundary

The PS1 BIOS/service boundary is a typed, versioned host-side service contract.
No BIOS image or BIOS-derived code is loaded, executed or emulated. Unknown
BIOS calls fail closed with an explicit unresolved record.
