# OpenRecomp Phase 4 fixture (P4-07)

Original work authored for OpenRecomp. Licensed under the repository
`LICENSE` (Apache License 2.0). No third-party, console, commercial or
generated-asset material is used, and no proprietary system software,
firmware, keys or vendor SDK content is referenced.

## Files

- `p4_fixture.h` - interaction windows and unit prototypes.
- `p4_fixture_util.c` - const tables, initialised globals, zero-fill storage,
  recursion, checksum mixing and the bounded static bump allocator.
- `p4_fixture_main.c` - MMIO interaction helpers, transcript writer, `main()`.
- `p4_start.S` - freestanding entry stub (`_start`).
- `p4_fixture.ld` - single-image linker script based at `0x00001000`.
- `input_plan.json` - the declared deterministic input plan and interaction
  contract.

## Interaction contract

- Output window `0x20000000`: one byte per write (low 8 bits).
- Input window `0x20000004`: one byte per read (low 8 bits). The input loop
  terminates on `0xff`; the declared input plan always includes it.
- Exit window `0x20000008`: 32-bit write; terminates the run with that status.
- Ticks window `0x2000000c`: 32-bit read of the deterministic virtual clock.
  The runtime must never substitute a host clock; the declared tick policy is
  recorded in `input_plan.json`.
- Transcript: fixed ASCII lines ending with `\n`, emitted in the source
  order. `checksum` is a 32-bit FNV-1a-style mix in lower-case hex.

## Build (recorded by the P4-07 gate)

Compiled with the same toolchain and bounded flags as the Phase-3 fixture
(`zig cc` 0.13.0, `--target=mipsel-linux-musl`, `-march=mips32 -mabi=32
-msoft-float -mno-abicalls -G0 -ffreestanding -fno-builtin
-fno-stack-protector -fomit-frame-pointer -fno-pic -O1 -nostdlib -static`),
linked with `zig ld.lld -m elf32ltsmip` and the local linker script. Two
isolated build roots must produce a byte-identical ELF.
