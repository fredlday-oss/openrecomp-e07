# P8-01 result: real redistributable MIPS32 ELF fixture

Status: `PASS` (89 checks)

Markers:

- `OPENRECOMP_P8_01=PASS`
- `OPENRECOMP_PHASE8_REAL_ELF_FIXTURE_V1=PASS tests=89`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase8_fixture_v1.py`.

## Frozen fixture

- program: upstream `tiny-AES-c` AES-128-ECB implementation, repository
  `https://github.com/kokke/tiny-AES-c`, pinned commit
  `23856752fbd139da0b8ca6e471a13d5bcc99a08d`;
- licence: The Unlicense (public-domain dedication), upstream file
  `unlicense.txt`; the fixture is a bounded audit input, not a supported AES
  product;
- OpenRecomp-authored freestanding port files
  (`.openrecomp-phase8/fixture/`): `p8_start.S` entry stub, `p8_mips32.ld`
  linker script, `p8_port_support.c` bounded output/stack/shim support,
  `p8_aes_main.c` FIPS-197 known-answer harness, and a minimal
  `include/string.h` freestanding shim;
- toolchain: Zig 0.13.0 (clang 18.1.5 / LLD 18.1.6), the Phase-3
  provenance-recorded archive and executable identity;
- profile: `--target=mipsel-linux-musl -march=mips32 -mabi=32 -msoft-float
  -mno-abicalls -G0 -ffreestanding -fno-builtin -fno-stack-protector
  -fomit-frame-pointer -fno-pic -O1 -nostdlib -static`, freestanding, no PIC,
  no dynamic linking;
- build: two isolated build roots, byte-identical ELF;
- ELF identity: SHA-256
  `0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65`,
  12904 bytes, ELF32 little-endian `EM_MIPS` `ET_EXEC`, flags
  `0x50001001` (O32 / MIPS32 / non-PIC), entry `0x2490`;
- memory image: `.text` `0x1000`+5300 `r-x`, `.rodata` `0x24c0`+571 `r--`,
  `.data` `0x2700`+8 `rw-`, `.bss` `0x2710`+16384 `rw-` (stack).

The upstream tree and the built ELF remain untracked; only provenance,
metadata and hashes are committed.

## Existing-pipeline reconnaissance (reuse, no rewrite)

The gate drives the frozen ELF through the existing Phase-3 layers only:
`p3_elf_image_v1` ingestion + `p3_target_mips32_v1` O32 policy, then
`p3_code_frontier_v1` decode/reachability (which uses
`p3_decode_mips32_v1`). No existing module was modified.

Frontier facts (deterministic):

- `.text` 1325 words; decoded 1322 (supported 1321,
  recognized-unsupported 1, reserved 3, unknown 0, invalid 3 -- all invalid
  words unreachable);
- reachable 509: 508 supported + 1 recognized-unsupported (`movz` at
  `0x00002440`); unreachable 816;
- reachable op histogram: `addiu` 38, `addu` 30, `andi` 22, `beq` 3,
  `bne` 2, `j` 3, `jal` 8, `jr` 7, `lb` 2, `lbu` 132, `lui` 13, `lw` 22,
  `movz` 1, `nop` 7, `or` 11, `ori` 4, `sb` 88, `sll` 9, `sra` 4, `srl` 6,
  `sw` 26, `xor` 71;
- control flow: 5 conditional branches, 8 direct calls, 3 jumps, 7 returns,
  0 indirect calls, 0 indirect jumps, 0 unsupported control transfers,
  0 unresolved sites;
- delay slots: 23 (16 non-nop, every one exactly owner+4); no branch target
  into a delay slot and no delay slot reached by fallthrough;
- exception sites: 0; no `div`/`divu`, no HI/LO use, no `syscall`/`break`,
  no floating point, no coprocessor use on the reachable path.

The frozen inventory is recorded in `frontier_inventory.json`; the fixture
identity and provenance are recorded in `fixture_identity.json`.

## Official runs

Command `python tools/test_phase8_fixture_v1.py`, exit 0, empty stderr, both
runs byte-identical: stdout 2753 bytes, raw sha256
`747559538a5ceb244f14bdb325f1ab7e3fdbc645a90dd95923f75a6b2550f6f1`, LF
sha256 `d668cf1a65eeed1dfdba12e71be885a9b510afd213ad08f7bb6676820992e2c7`.

Sidecar identities: `fixture_identity.json`
`fe025eeab0c294852713436522435869f5d90199d1f7fbff72099b35356a5140`,
`frontier_inventory.json`
`010bf94a8c92d0e9637d8d35102adca5b03aae311b79a5b6a96df0c27393e655`,
`p8_01_tests.json`
`d1b6546d4ae0e1b798fb3019b91332cef001992219be5253b1a119aa6763b2d1`.

## Reproducibility note

The audited build passes repo-relative source paths to the compiler. An
otherwise identical build that passes absolute host paths produces two
differing bytes and a different ELF hash; the frozen identity is the
repo-relative build, which is what the official gate reproduces. The
`zig cc` small-data/abicalls and `ld.lld` abicalls-mix warnings are
deterministic and recorded as warning kinds only.

## Claim-ledger delta

- New evidence: one frozen legally redistributable compiler-produced real
  MIPS32 ELF with recorded provenance, licence, toolchain and immutable
  identity, plus its complete reproducible frontier characterization.
- The ELF is not yet translated, built natively or executed; the terminal
  marker remains reserved `NOT_PROVEN`. No general MIPS32, AES, or
  arbitrary-ELF compatibility is claimed.

## Limitations

- The fixture is one bounded audit input; nothing here generalizes to
  arbitrary AES programs, compilers, optimization levels or MIPS32 binaries.
- The reachable path contains one recognized-unsupported instruction
  (`movz`); the shared host emitter has no rule for it yet (P8-04 evidence).
- 16 reachable delay slots are non-nop; delay-slot execution semantics must be
  closed by evidence at P8-04.

## Next stage

P8-02: re-derive the complete current pipeline frontier for this frozen
fixture through the existing ELF ingestion, target policy, decode, semantics
inventory, executable-region discovery and reachable-code frontier, and
classify every gap into the frozen categories.
