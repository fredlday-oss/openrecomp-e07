# P3-06 result (PASS)

Stage: `P3-06` static data/global reconstruction (frozen queue row).
Gate: `tools/test_phase3_static_data_v1.py` (123 checks).
Evidence: `.openrecomp-phase3/evidence/P3-06/`.

Markers issued:

- Stage marker: `OPENRECOMP_P3_06=PASS`
- Gate marker: `OPENRECOMP_PHASE3_STATIC_DATA_V1=PASS tests=123`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

## Scope

P3-06 reconstructs the audited image's static data and its reachable global
access model on top of the P3-02 guest image and the P3-05 neutral structure.
New Phase-3 files only; no shared layer, frozen adapter, Phase-1/Phase-2 file,
gate or frozen manifest was modified:

- `.openrecomp-phase3/src/p3_static_data_v1.py` — fail-closed static-data model
  (sections, zero-fill, symbols) and block-local exact-constant global access
  analysis with provenance and explicit `RUNTIME_BASE` classification;
- `tools/test_phase3_static_data_v1.py` — the P3-06 gate;
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` — grown additively from twelve to
  fourteen entries. The P3-02/P3-03/P3-04/P3-05 gates' expected entry set grew
  12 -> 14 additively and their stdout is unchanged.

## Static data model

| section | vaddr | size | role | permissions | sha256 |
| --- | --- | --- | --- | --- | --- |
| `.text` | `0x1000` | 13948 | CODE | r-x | `c7b48c7c...` |
| `.MIPS.abiflags` | `0x4680` | 24 | METADATA | r-- | `e1e61890...` |
| `.reginfo` | `0x4698` | 24 | METADATA | r-- | `46530814...` |
| `.rodata` | `0x46b0` | 1864 | RODATA | r-- | `0fa7bd67...` |
| `.data` | `0x4e00` | 40 | DATA | rw- | `89a1e02a...` |
| `.bss` | `0x4e30` | 18416 | BSS | rw- | `c7d9a612...` |

Every section hash is cross-checked against the P3-02 `region_hashes.json`
(`section_hashes`, `bss_zero_fill_sha256`, `readonly_sha256` including the ELF
header region, `writable_initialized_sha256`, `executable_sha256`). `.bss` is
exactly zero-fill. Symbol layout is diagnostic only: the five seed globals
(`seed1/2` `0x5600`/`0x5604`, `seed3/4` `0x4e10`/`0x4e14`, `seed5` `0x5608`),
`static_memblk` (`0x4e30`+2000), `p3_stack` (`0x5620`+16384), `mem_name`,
`default_num_contexts`, the p3 timer/UART counters and `_gp = 0xcdf0`.

## Global access model

Block-local exact-constant propagation over every reachable block:

- **283 constant formations** (all `IMMEDIATE_CHAIN`) with exact provenance
  chains and recorded uses (`base` or `argument`), 25 with uses;
- **505 memory accesses**: 10 `RESOLVED_STATIC` (3 `lw` of
  `default_num_contexts` in `.data`; `p3_tick`, `p3_start_time_val`,
  `p3_stop_time_val`, `p3_uart_byte_count` in `.bss` — 5 loads and 2 stores),
  2 `RESOLVED_OUTSIDE_IMAGE` stores to the port UART (`0x10000000`,
  `0x10000008`), and **493 `RUNTIME_BASE`** accesses that carry no address
  claim (stack frames, pointer arguments, heap);
- no store resolves into a read-only static section (fail-closed rule); no
  resolved access targets any seed global; no cross-section or unclassified
  region access occurs;
- 13 direct-call argument materialisations are live at the call site, of which
  the static-range ones are proven addresses in use (`.rodata` string and
  table pointers); all other values are recorded as constants, never called
  addresses.

## GP / SP model

- `_start` (`0x4650`) initialises `$28 = 0xcdf0` (`= _gp`, sites
  `0x4650`+`0x4654`) and `$29 = 0x9620` (the top of `p3_stack`/`.bss`, sites
  `0x4658`+`0x465c`), both proven by immediate-chain provenance;
- **no reachable instruction uses `$28` as a memory base** (0 GP-relative
  accesses), and the register is reused as a general scratch register at four
  sites (`0x2dc8`, `0x3108`, `0x3558`, `0x3564`), so
  `GP_STATUS=NOT_REQUIRED_BY_REACHABLE_CODE`;
- GP-relative addressing is therefore explicitly modelled as *not required*,
  and every resolved global access is absolute. No unresolved address is
  guessed either way.

## Seed pointer chain

`get_seed_32` (`fn_33d0`) is reconstructed from static evidence only:

- the `.rodata` table base `0x4c50` is materialised at `0x33e8`
  (`lui@0x33e4` + `addiu@0x33e8`);
- the index is guarded by `sltiu $1, (index-1), 5` at `0x33d4` + `beq` at
  `0x33d8` (exit `0x33f8`), so `1 <= index <= 5`;
- the five 4-byte entries at `0x4c50..0x4c64` are exactly the pointers
  `seed1 -> 0x5600`, `seed2 -> 0x5604`, `seed3 -> 0x4e10`, `seed4 -> 0x4e14`,
  `seed5 -> 0x5608`; the sixth slot (`0x4c64 = 0x3804`) is a `.text` address
  and is excluded by the guard;
- the two-level load shape (`lw` table slot at `0x33f0`, `lw` value at
  `0x33f4`) matches the finite target set. The initial values
  `0, 0, 0x66, 0x3e8, 0` match the P3-04 exception-frontier fixture constants
  exactly.

## Verification

- 123 gate checks: source integrity (root manifest 134 entries frozen,
  Phase-3 manifest 14 entries), section/region/symbol model, exact access and
  materialisation counts, the GP/SP model, the seed chain, P3-02/P3-04
  cross-checks and fail-closed negatives.
- 9 negative/synthetic panels: unmapped/cross-section/end-boundary reads,
  invalid size, unclassified op, store-to-read-only static, synthetic resolved
  static store, synthetic outside-image rejection.
- Determinism: two consecutive official runs byte-identical (4294 bytes raw,
  raw sha256
  `23d2f1c25ccf6d7e25b6f3ea7d86a0b6e9cd378a56c65f98ae053aa69b8f1c97`, LF
  sha256 `c4a1d4ff9a0b4fc96266188c0e0422837274b2d5218d8239278c4d0c9e5521ad`,
  empty stderr, exit 0); a second isolated ingest/structure/analysis build
  reproduces every section hash, materialisation, access and GP fact.
- Regressions (all exit 0, empty stderr, stdout byte-identical to their
  recorded captures): P2-99 `PASS tests=202` (`66913e57...`), P3-00
  `PASS tests=61` (`a039bbff...`), P3-01 `PASS tests=76` (`81eede03...`),
  P3-02 `PASS tests=197` (`f24f4cef...`), P3-03 `PASS tests=201`
  (`15e20a2c...`), P3-04 `PASS tests=126` (`412544a4...`), P3-05
  `PASS tests=202` (`12bf87d7...`), Phase-1 host gates
  `PASS=44 FAIL=0 SKIPPED=2` (`2a9d1bba...`), public safety `PASS`
  (`ad022ff1...`).

## Claim boundary

P3-06 proves only the static-data reconstruction of the audited CoreMark image
and the reachable global access model listed above. It does not execute or
translate CoreMark, does not resolve the 493 runtime-base accesses, does not
perform alias analysis (runtime-base stores are never assumed to miss any
object), and claims no arbitrary MIPS32, PS1 or PS2 compatibility.
`COREMARK_STATUS=NOT_PROVEN`.
