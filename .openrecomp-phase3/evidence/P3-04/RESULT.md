# P3-04 — CoreMark reachable MIPS32 semantics (PASS)

Stage: `OPENRECOMP_PHASE3_COREMARK_REACHABLE_SEMANTICS_V1`
Gate: `tools/test_phase3_reachable_semantics_v1.py` (126 checks)
Evidence: `.openrecomp-phase3/evidence/P3-04/`

Markers:

```
OPENRECOMP_P3_04=PASS
OPENRECOMP_PHASE3_COREMARK_REACHABLE_SEMANTICS_V1=PASS tests=126
OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN
```

## What this stage proves

P3-03 decoded the complete CoreMark executable frontier and identified 82
recognized-but-semantically-unsupported instruction words, 55 of them on the
reachable path. P3-04 implements exact, fail-closed MIPS32 semantics for that
bounded class and verifies every audited site against an independently written
reference model. After P3-04 the reachable semantic gap in the audited classes
is zero: 2178/2178 reachable words are semantically supported.

It does **not** prove complete CoreMark translation or execution, does not
recover the unresolved `jr $at` jump tables, and claims no arbitrary MIPS32,
PS1 or PS2 compatibility. `COREMARK_STATUS=NOT_PROVEN`.

## Implementation (new Phase-3 files only)

- `.openrecomp-phase3/src/p3_semantics_mips32_v1.py` — the semantics model.
  It never modifies the frozen decode layer (`p3_decode_mips32_v1`) or the
  frontier engine (`p3_code_frontier_v1`): the 82 words keep their
  `RECOGNIZED_UNSUPPORTED` classification and semantic support is an explicit
  overlay. `$zero` writes are discarded; `jalr` semantics does not resolve
  static targets.
- `tools/test_phase3_reachable_semantics_v1.py` — the gate.
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` — additive growth from 8 to 10
  entries (sha256 `e4db427b5d7cdee3a631236050b690874570ed822ddbec248feccc89b1f484e5`).
- Documented contract growth: `tools/test_phase3_elf_ingestion_v1.py` and
  `tools/test_phase3_decode_frontier_v1.py` accept the 10-entry registry
  (additive; both still emit byte-identical stdout to their recorded
  captures). Refreshed P3-00..P3-02 evidence artifacts only differ in the
  registry listing.

## Audited semantic classes

| Class | Form | Implemented behaviour | Fail-closed conditions |
|---|---|---|---|
| `movz` | `movz rd, rs, rt` | `rd = rs` when `rt == 0`, otherwise unchanged; `rd = 0` discarded | — |
| `movn` | `movn rd, rs, rt` | `rd = rs` when `rt != 0`, otherwise unchanged; `rd = 0` discarded | — |
| `mul` | `mul rd, rs, rt` | signed 32x32 product low 32 bits into `rd`; `rd = 0` discarded | reading HI/LO before a defining operation (`HI_LO_UNPREDICTABLE`) |
| `divu` | `divu rs, rt` | unsigned `LO = rs // rt`, `HI = rs % rt` | divisor zero (`DIVIDE_BY_ZERO`) |
| `teq` | `teq rs, rt` | taken only when `rs == rt`; encoded trap code preserved | taken trap (`TRAP_TAKEN`, exception delivery not modelled) |
| `swl` | `swl rt, off(base)` | little-endian partial store in the aligned word; 1-4 bytes selected by the two low address bits; no alignment exception | unmapped aligned word (`MEMORY_FAULT`), read-only target (`WRITE_PROTECTED`), big-endian target (`ENDIANNESS_UNSUPPORTED`) |
| `swr` | `swr rt, off(base)` | mirror of `swl` | same as `swl` |
| `jalr` | `jalr rd, rs` | target latched from `GPR[rs]` before the delay slot; `GPR[rd] = address + 8` when `rd != 0` | unaligned target (`UNALIGNED_TARGET`); static target never resolved |

`mul` leaves HI/LO architecturally UNPREDICTABLE; the model does not invent a
value, marks them undefined and refuses to read them until `divu` (or another
defining operation) writes them. The `swl`/`swr` semantics are the MIPS32
little-endian definition; both the module's mask formulation and the gate's
independent byte-level formulation were validated against the compiler idiom
`swl rt, 3(base); swr rt, 0(base)`, which composes to a plain unaligned
32-bit little-endian store for every alignment (24 idiom checks).

The complete bounded class (all eight P3-01 classes) is implemented rather
than only the seven reachable ones, because the class is small, the prompt
requires `jalr` link-register/delay-slot edge-case coverage, and implementing
the class does not resolve any control-flow frontier.

## Frontier result

Fixture `16a0a0aa0f62344d8c0f309b755450f09c330e7c5a7c355785662d7a141f7669`
(31184 bytes, `.text` 3487 words, entry `0x4650`).

| Measure | Before | After |
|---|---|---|
| recognized-unsupported words | 82 | 82 (classification unchanged) |
| reachable recognized-unsupported | 55 | 0 semantically unsupported |
| unreachable recognized-unsupported | 27 | 27 (semantics implemented, not required) |
| reachable semantically supported words | 2123 | 2178 of 2178 |
| reachability hash | `c62d54838cbc5fcc7b0ff83cdc9b2f0f47b8851c5e4023ae2ca6d629c8f76edf` | identical |

Per-class sites (total/reachable/unreachable): `movz` 35/21/14, `movn` 12/9/3,
`mul` 22/15/7, `divu` 4/3/1, `teq` 4/3/1, `swl` 2/2/0, `swr` 2/2/0,
`jalr` 1/0/1. Exact per-site tables:
`reachable_unsupported_before.json` and `reachable_unsupported_after.json`
(address, raw encoding, mnemonic, operands, reachability, containing function,
implementation status, coverage status).

Remaining frontier (explicit, unchanged):

- three reachable `jr $at` jump tables at `0x3130`, `0x3830`, `0x39a0` —
  target not statically resolved, no target invented;
- the dead `jalr $ra, $t9` at `0x1958` — unreachable, never targeted;
- boundary successor `0x467c` leaving the executable region;
- 27 unreachable recognized-unsupported words (14 `movz`, 3 `movn`, 7 `mul`,
  1 `divu`, 1 `teq`, 1 `jalr`) inside 22 dead functions;
- eight `0x04170001` reserved non-code padding words.

## Reference testing

- 459 differential vectors (boundary values, fixture-derived values,
  deterministic LCG operands) executed through the decoded instruction record
  on both `p3_semantics_mips32_v1` and a separately written in-gate reference
  (`reference_execute`: explicit signed arithmetic, `divmod`, byte-level
  store-left/right merges). All match, including error codes.
- 24 compiler-idiom `swl`+`swr` composition checks (4 alignments x 6 values)
  proving the pair equals a plain unaligned 32-bit store.
- Every one of the 82 audited sites is executed against both models with
  deterministic per-site register state; no site reports
  `UNSUPPORTED_INSTRUCTION` (`semantic_site_coverage.json`).
- 16 fail-closed negatives (`semantic_negative_results.json`): unsupported
  op, bounded-record contract violations, divide-by-zero, taken trap,
  unaligned `jalr`, unmapped/read-only stores, big-endian refusal, invalid
  state, malformed records, HI/LO read after `mul`, plus state-unchanged
  checks for refused `divu`/`teq` and `$zero` discard.

## HI/LO predictability

All six reachable `mfhi`/`mflo` reads (`0x1a4c`, `0x1b5c`, `0x1f68`, `0x204c`,
`0x2378`, `0x4530`) are proven to be fed by `multu`/`divu` in the same
straight-line region; no reachable read depends on the architecturally
UNPREDICTABLE HI/LO after `mul` (`hi_lo_dependency.json`).

## Exception frontier

Six reachable div/trap sites, all classified with explicit evidence and all
implemented fail-closed in the model (`exception_frontier.json`):

| Site | Op | Classification | Evidence summary |
|---|---|---|---|
| `0x1f60` | `divu` | condition proven false for fixture | `seed5_volatile = 0` -> `movz` sets `execs = 7` -> popcount divisor 3; no target enters the popcount block; `$2`/`$1` stable at the site |
| `0x1f64` | `teq` | condition proven false for fixture | same divisor 3 != 0 |
| `0x2044` | `divu` | proven false on every reaching path | `0x2038 beq $2,$0` dominates the fall-through; block not entered (`iterations = 0x3e8`, `0x1fec bne`) |
| `0x2048` | `teq` | proven false on every reaching path | same guard |
| `0x2370` | `divu` | proven false on every reaching path | pure `time_in_secs($17)` called twice; first result proven nonzero at `0x2350`; argument `$17` stable |
| `0x2374` | `teq` | proven false on every reaching path | same reasoning |

Fixture seed constants (from the audited image): `seed1 = 0`, `seed2 = 0`,
`seed3 = 0x66`, `seed4 = 0x3e8`, `seed5 = 0`, with the seed-pointer table at
`0x4c50 -> {0x5600, 0x5604, 0x4e10, 0x4e14, 0x5608}`; no reachable
instruction materialises a seed address. Zero sites remain unresolved
runtime requirements, and a true condition would still fail closed.

## Determinism

Two consecutive official runs are byte-identical:

- `run1.txt` / `run2.txt` raw sha256
  `412544a413bbe3e55e688bc45e379dccfe4e8b4ebdc299211ccba2a832e39b36`
  (5202 bytes), empty stderr, exit code 0;
- every gate-produced evidence artifact is byte-identical across the two
  runs (`deterministic_runs.json`).

## Regressions (recorded captures in this directory)

| Gate | Result | Capture sha256 |
|---|---|---|
| P3-00 boundary | `PASS tests=61` | `a039bbffa55afd786e7b44427c5aafe0b09aff6f8309e1e6c643ad812b5b7c73` |
| P3-01 fixture | `PASS tests=76` | `81eede037e04ab14cb23747c8186ca1e8121e464f956683eb57dd0bcbfa17621` |
| P3-02 ingestion | `PASS tests=197` | `f24f4cef9182f80b87b3c2c291267000f79d3db78677862844694efca698354a` |
| P3-03 decode frontier | `PASS tests=201` | `15e20a2c9a6e4eba629e67ceb14b70db8bf367c9ffe1d69473be57e7a8091878` |
| P2-99 final verdict | `PASS tests=202` | `66913e5752a9e2b7e399513710b4dce05efce9a714335c3b9908c0e30ea38c28` |
| Phase-1 host gates | `PASS=44 FAIL=0 SKIPPED=2` | `2a9d1bba538b91605d61c3c47d8208cc7012cdfe49042f088c409dc54729cc35` |
| Public safety | `PASS` | `ad022ff195be230e31115124d48b7f6d8ccaae58d97eab2779b8b1ad694dbb2e` |

Source integrity: root `SOURCE_SHA256SUMS.txt` sha256
`76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095` (134
entries) unchanged and fully verified; Phase-3 manifest verified (10
entries). Frozen Phase-2 tracked tree unchanged (`git diff` and
`git diff --cached` empty); frozen P2-99 identities re-verified by P3-00.

## Control-plane reconciliation

Documented in `STAGE_QUEUE.md` (reconciliation log): P3-04 is the
reachable-semantics stage; the ProgramModel/CFG/functions/call
graph/translation-units work moved to P3-05 and the later provisional stage
IDs shifted by one (P3-06 static data, P3-07 host emission, P3-08 native
build/runtime, P3-09 independent reference, P3-10 package). No completed stage
evidence is affected.

## Evidence files

| File | sha256 |
|---|---|
| `reachable_unsupported_before.json` | `815dbadc1cfd7a4e22d990808cdafaa5e9688103b451769671089e694d29c7ad` |
| `reachable_unsupported_after.json` | `d033501f6e08aa477f31200ae2c98ba10f28e72d5618ac89aeaa46745274ad59` |
| `semantic_implementations.json` | `235105953bbcfe3ee8e61d418995a3cf80a1d2706b5636721ba84b88a02573a3` |
| `semantic_reference_vectors.json` | `89b6328c8c6161d351b0ffa8d5b1f00cf75a49962a9a31f830df94dab85d3417` |
| `semantic_site_coverage.json` | `6272f8eccf537980406c548418019053dde19ff42c1f92f2ec121d28c352a27d` |
| `semantic_negative_results.json` | `c4698ad07e9b83bcdfa2b561c71c65e1eb28fc456576dce120acd2d82fc98455` |
| `exception_frontier.json` | `eeb04eb73f6c7737b326a67af7c1e7d0a20dfa6f6252209d8a3688079a8b2eda` |
| `hi_lo_dependency.json` | `2291518ba64ea7ec4f5c6651ecd6b1870aa70d5d583616f1f00fbca08d27f3e2` |
| `coremark_frontier_rerun.json` | `9a54e0212404cbe05fc0ac956a3922392eec0a1bf305ae88543a1d74383ccca9` |
| `determinism.json` | `de83b3a7e2036eb696e90a1270f6b7e9592723594427f19a867e5de218796cbc` |
| `deterministic_runs.json` | present |
| `source_integrity.txt` | `4f74d860bc0bbf3f2302977739e24ecd34e30f7b8afd94e45d6aac5068bc2d62` |
| `changed_files.txt` | present |
| `RESULT.json` | `6bf492e0c2e99bc384a74ef76169d5cd7ba109b6160f0e7bf71381f2d8df11e3` |
