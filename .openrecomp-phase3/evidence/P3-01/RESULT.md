# P3-01 — CoreMark MIPS32 fixture acquisition/build

VERDICT: `PASS`

Stage: `OPENRECOMP_PHASE3_COREMARK_MIPS32_FIXTURE_V1`. Branch:
`phase3/mips32-real-elf-v1`. Gate:
`tools/test_phase3_coremark_fixture_v1.py` (76 checks).

## Markers

```text
OPENRECOMP_P3_01=PASS
OPENRECOMP_PHASE3_COREMARK_MIPS32_FIXTURE_V1=PASS tests=76
OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN
```

## Source provenance

- Repository: `https://github.com/eembc/coremark`
- Pinned commit: `1f483d5b8316753a742cbf5590caf5bd0a4e4777` (upstream `main`;
  last release tag `v1.01`)
- License: Apache-2.0 per the upstream source-file headers; the repository
  `LICENSE.md` is the EEMBC CoreMark Acceptable Use Agreement covering the
  COREMARK trademark and result reporting. No public CoreMark score is
  produced or published by this stage.
- Retained upstream sources (verbatim commit blobs, LF line endings):
  `coremark.h`, `core_list_join.c`, `core_main.c`, `core_matrix.c`,
  `core_state.c`, `core_util.c`, `coremark.md5`, `LICENSE.md`, `README.md`,
  `barebones/core_portme.h`, `barebones/ee_printf.c` under
  `.openrecomp-phase3/external/coremark/` (sha256 per file in
  `source_provenance.json`).
- Five of the six upstream `coremark.md5` reference entries reproduce exactly
  at the pinned commit; the `coremark.h` entry in the upstream md5 list is
  stale upstream (listed `8ca974c0...`, actual `b0ec69b6...`; the same stale
  entry exists at the commit that last updated `coremark.md5` and at tag
  `v1.01`). Recorded, not patched.
- P3 port files (OpenRecomp-authored except the documented derivative):
  - `ports/coremark_mips32/p3_port_support.c` (original; deterministic
    seeds, synthetic tick source, memory-mapped UART/exit hooks, minimal
    freestanding `memcpy`/`memmove`/`memset`)
  - `ports/coremark_mips32/p3_start.S` (original; freestanding `_start`)
  - `ports/coremark_mips32/p3_mips32.ld` (original; linker script)
  - `ports/coremark_mips32/p3_ee_printf.c` (derived from upstream
    `barebones/ee_printf.c`; only the `uart_send_char` stub is replaced, with
    an in-file derivation notice)

## Toolchain identity

- Compiler: `zig cc` 0.13.0 (clang 18.1.5) targeting `mipsel-linux-musl`
- Linker: LLD 18.1.6 (`zig ld.lld`, `-m elf32ltsmip`)
- Acquisition: official `https://ziglang.org/download/0.13.0/zig-windows-x86_64-0.13.0.zip`,
  79163968 bytes, sha256
  `d859994725ef9402381e557c60bb57497215682e355204d754ee3df75ee3c158`
  (verified against the published hash). The toolchain is not committed;
  the worktree copy under `.openrecomp-phase3/tools/zig/` is untracked and
  its `zig.exe` sha256 is
  `2e44af5bbf7a72ef8cbdae370284687c95d65a19affa469d2ad0364d905b8e84`.
- Flags: `-march=mips32 -mabi=32 -msoft-float -mno-abicalls -G0
  -ffreestanding -fno-builtin -fno-stack-protector -fomit-frame-pointer
  -fno-pic -O1 -nostdlib -static -include stddef.h` plus
  `-DTOTAL_DATA_SIZE=2000 -DITERATIONS=1000 -DHAS_FLOAT=0 -DHAS_TIME_H=0
  -DUSE_CLOCK=0 -DHAS_STDIO=0 -DHAS_PRINTF=0 -DMEM_METHOD=0
  -DMAIN_HAS_NOARGC=1` and recorded compiler/flags/memory-location strings.
- Link: `-m elf32ltsmip -T p3_mips32.ld --strip-debug --build-id=none`.

## Reproducibility

Two isolated build roots (`.openrecomp-phase3/build/P3-01/candidate-a` and
`candidate-b`) with per-root Zig caches produce byte-identical ELF images:

- sha256 `16a0a0aa0f62344d8c0f309b755450f09c330e7c5a7c355785662d7a141f7669`
- size 31184 bytes
- classification `EXECUTABLE_REPRODUCIBLE` (no post-processing)

## ELF characterisation

- ELF32, little-endian, `EM_MIPS`, `ET_EXEC`, flags `0x50001001`
  (`EF_MIPS_ABI_O32 | EF_MIPS_ARCH_32 | EF_MIPS_NOREORDER`, non-PIC)
- entry `0x00004650` = symbol `_start`; single executable segment at
  `0x1000`
- sections: `.text` 13948, `.rodata` 1864, `.data` 40, `.bss` 18416
  (plus `.MIPS.abiflags`/`.reginfo` 24 each)
- 3487 instruction words in `.text`
- no dynamic section, no dynamic program header, zero relocations, zero
  undefined symbols; imported/external requirements: none (static
  freestanding image)
- symbol table retained (`.symtab`), `.comment` compiler identity retained

## Instruction / unsupported inventory

Decoded every `.text` word through the existing bounded OpenRecomp MIPS32
adapter (`adapters.mips32.decode`); nothing in OpenRecomp was modified.

- supported: 3397 words
- unsupported by the bounded adapter: 90 words, exactly:
  - `movz` 35, `movn` 12 (conditional moves)
  - `mul` (SPECIAL2 funct 0x02) 22
  - `divu` 4 with `teq` 4 (compiler divide-by-zero trap guard pairs)
  - `swl` 2, `swr` 2 (unaligned stores)
  - `jalr` 1 (SVR4 abicalls indirect call site at `0x1958`)
  - `0x04170001` alignment padding 8 (never-decoded filler at function
    boundaries; not a valid MIPS32 encoding)

This inventory defines the evidence-supported later stages: decode expansion
(P3-03) must cover exactly these classes, and the `teq` guard and `jalr`
indirect call require explicit fail-closed/classification treatment (P3-03 /
P3-04), not inference.

## Fixture retention

The ELF is regenerable byte-identically from the recorded sources, toolchain
identity and flags; it is retained only in the untracked build directory and
by hash in this evidence. No external toolchain binaries are committed and no
OpenRecomp source was changed.

## Determinism

Two consecutive official gate runs produced byte-identical stdout (3108
bytes, raw sha256
`81eede037e04ab14cb23747c8186ca1e8121e464f956683eb57dd0bcbfa17621`,
LF sha256
`6560923f68cd5d3ac71a2b368557745024b10ca41646a2df290527e0f2e8395e`) with
empty stderr; captures `run1.txt`, `run2.txt`, `run1.err.txt`,
`run2.err.txt`.

## Evidence in this directory

- `RESULT.md` (this record)
- `p3_01_tests.json`: machine-readable gate record
- `source_provenance.json`, `toolchain_identity.json`
- `build_reproducibility.json` (commands, roots, hashes)
- `elf_characterisation.json`, `instruction_inventory.json`
- `run1.txt`, `run2.txt`, `run1.err.txt`, `run2.err.txt`

## Next stage

P3-02 — ELF ingestion + section/data image: fail-closed ELF32 MIPS ingestion
based on this characterisation, with a deterministic bounds-checked guest
data image. CoreMark remains `NOT_PROVEN`.
