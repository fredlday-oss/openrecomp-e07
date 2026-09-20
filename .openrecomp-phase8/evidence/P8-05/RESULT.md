# P8-05 result: static memory and runtime contract closure

Status: `PASS` (36 checks)

Markers:

- `OPENRECOMP_P8_05=PASS`
- `OPENRECOMP_PHASE8_RUNTIME_CONTRACT_V1=PASS tests=36`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase8_runtime_v1.py`.

## Contract (reusing existing architecture)

New module `.openrecomp-phase8/src/p8_memory_contract_v1.py` derives the
contract from the existing `p3_elf_image_v1` guest image and the existing
`openrecomp.runtime_abi` memory architecture:

- flat guest image window `0x0..0x6710` (`P8_IMAGE_SIZE` 26384), SHA-256
  `5bbf4bf5e520102be8b26d5735a95eb3fc1473ef71e9083fb4495a4241cd805e`,
  contract digest
  `4769aa4b16c566754651f721a4b18edc520f300fa5fd84cafffacde722d5d0ce`;
- load regions: `0x0`+244 `r--` (ELF headers), `0x1000`+5300 `r-x` (`.text`),
  `0x24c0`+571 `r--` (`.rodata`), `0x2700`+16400 `rw-` (`.data` + zero-filled
  `.bss`);
- `.data` initialized bytes `00 00 00 00 00 00 00 80`; `.bss` is `SHT_NOBITS`
  and the flat image is exactly 16384 zero bytes; `.rodata` is file-backed
  with its recorded section hash;
- 16 KiB static stack `p8_stack` at `0x2710..0x6710` (top `0x6710`), matching
  the entry stub's `$sp` initialization;
- single write-only byte output window `0x10000000` mapped to the
  `p8_uart_write` host service (arity 1); termination is guest return to the
  host boundary (address 0) with the status value in `$v0`;
- static, non-PIC, no dynamic section, no relocations, no kernel service, no
  `syscall`/`break` anywhere in the frontier.

## Reachable access model

All 270 reachable memory accesses (`lw` 22, `sw` 26, `lb` 2, `lbu` 132,
`sb` 88) are register-based with explicit offsets; none is GP-relative (the
linker `_gp` value lies outside the loaded image, so GP-relative access would
fail closed at runtime); 48 accesses are `$sp`-relative with a maximum
absolute offset of `0x104`, well inside the 16 KiB stack region. The runtime
enforces region membership and permissions for every access.

## Native differential memory-contract test

The gate generates the deterministic image translation unit
(`p8_image_v1.c`, header + image; hashes recorded), composes it with the
OpenRecomp-authored runtime support
(`.openrecomp-phase8/runtime/p8_runtime_support.c`), builds a native
memory-contract driver through the existing deterministic build pipeline, and
executes an explicit vector of reads/writes. Every outcome and the access
counters (5 successful reads, 3 successful writes, 8 denied accesses,
1 host call) and the output transcript (`0x41`) equal the independently
written Python memory model
(`p8_memory_contract_v1.PythonMemoryModel`, backed by
`openrecomp.runtime_abi.RuntimeMemory`). Denied cases cover read-only writes
(`OR_RT_UNSUPPORTED_OPERATION`), out-of-range access
(`OR_RT_MEMORY_OUT_OF_RANGE`), unsupported widths
(`OR_RT_MEMORY_WIDTH_UNSUPPORTED`), output-window reads and non-byte output
writes.

## Official runs

Command `python tools/test_phase8_runtime_v1.py`, exit 0, empty stderr, both
runs byte-identical: stdout 1124 bytes, raw sha256
`03581cad9183a094d25add494542159edea84ab95d9565b975ceae81662c4231`, LF
sha256 `d9b7201099fdefa164b0b09279c521869090991ebcb47154cd6f8f0c007d154f`.

Sidecar identities: `memory_contract.json`
`499b4ffeec7572fbe4aec38bebdc7b47211a9142acf82370ff4e03802d2a958f`,
`p8_05_tests.json`
`3628a47b74c9a3bb6a4edeecd7c8b48d825c1594a445cd56446d15dc9c58166c`.

## Claim-ledger delta

- New evidence: the frozen fixture's static memory image, permissions, stack,
  bounded access model and single host service are explicit, validated, and
  differentially verified between the native runtime support and an
  independent Python model.
- No host program has been executed yet; the terminal marker remains reserved
  `NOT_PROVEN`.

## Limitations

- The contract covers this fixture's image window and one output service; it
  is not a general MIPS32 memory map or platform runtime claim.
- 16-bit accesses are supported by the runtime but unused by the fixture.
- Region permissions are enforced by the bounded support implementation; there
  is no MMU, TLB, cache or privileged-memory model (and none is claimed).

## Next stage

P8-06: feed the bounded real program through the existing architecture-neutral
host emitter to deterministic generated source with stable filenames and
content hashes.
