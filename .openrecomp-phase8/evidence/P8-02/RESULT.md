# P8-02 result: existing MIPS32 pipeline frontier re-derivation

Status: `PASS` (43 checks)

Markers:

- `OPENRECOMP_P8_02=PASS`
- `OPENRECOMP_PHASE8_FRONTIER_REDERIVATION_V1=PASS tests=43`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase8_frontier_v1.py`.

## Reconnaissance scope

The frozen P8-01 ELF (SHA-256
`0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65`) was
re-driven through the existing frozen layers only:

- `p3_elf_image_v1` ingestion + `p3_target_mips32_v1` O32 policy;
- `p3_decode_mips32_v1` decode/classification;
- `p3_code_frontier_v1` reachability and delay-slot frontier;
- `p3_semantics_mips32_v1` implemented-op inventory.

Every reused module hash equals its frozen Phase-3 manifest entry; no module
was modified and nothing was executed.

## Frontier classification (every reachable word classified exactly once)

| Class | Words | Meaning against the existing layers |
|---|---|---|
| `EMITTER_READY` | 215 | decoded, semantically defined, expressible by the frozen shared host emitter today |
| `EMITTER_READY_32BIT_MEMORY` | 48 | `lw`/`sw` expressible today (word-width guest memory only) |
| `EMITTER_READY_CONTROL_DELAY_SLOT` | 15 | `beq`/`bne`/`j`/`jr` conditions/targets expressible; delay-slot ordering is the gap below |
| `EMITTER_READY_CONTROL_DELAY_SLOT_LINK_REGISTER` | 8 | `jal` call edges expressible; `$ra` link value materialization is the gap below |
| `HOST_EMITTER_WIDTH_GAP` | 222 | `lb`/`lbu`/`sb` need a width/sign-extended load/store form |
| `TRANSLATION_SEMANTICS_GAP` | 1 | `movz` at `0x2440` needs a neutral conditional-select operation |

Frozen category checks: already supported (the five emitter-ready classes),
recognized but unsupported (`movz`), unresolved control flow (none),
ABI/runtime gap, memory-image gap, translation gap, host-emission gap,
toolchain/build gap (none).

## Measured gap vector

| Gap | Sites | Stage |
|---|---|---|
| `TRANSLATION_SEMANTICS_GAP` | 1 (`movz` `0x2440`) | P8-04 |
| `HOST_EMITTER_WIDTH_GAP` | 222 (`lb` 2, `lbu` 132, `sb` 88) | P8-04 |
| `HOST_EMITTER_DELAY_SLOT_GAP` | 23 control sites (16 non-nop) | P8-04 |
| `O32_ABI_LINK_REGISTER_GAP` | 8 `jal` sites; `$ra` saved 4x, restored 4x, used as scratch 3x, zeroed once at the entry boundary | P8-03/P8-04 |
| `RUNTIME_HOST_SERVICE_GAP` | 1 byte-write output window (`0x10000000`) plus the return boundary | P8-05 |
| `MEMORY_IMAGE_CONTRACT_GAP` | 1 image contract (`.text`/`.rodata`/`.data` + 16 KiB zero-filled stack, permissions, MMIO outside the image) | P8-05 |
| `NATIVE_TOOLCHAIN_GAP` | 0 (`clang-cl` 22.1.8 + `lld-link` 22.1.8 discovered through `openrecomp.build_pipeline`) | P8-07 |
| `UNRESOLVED_CONTROL_FLOW_GAP` | 0 | - |

## Other frontier facts

- reachable 509 (508 supported + 1 recognized-unsupported), unreachable 816,
  reachable-invalid 0, exception sites 0, unresolved sites 0;
- memory ops: `lw` 22, `sw` 26, `lb` 2, `lbu` 132, `sb` 88; no `lh`/`sh`,
  no `lwl`/`lwr`/`swl`/`swr`;
- control flow: 5 branches, 3 jumps, 8 direct calls, 7 returns, 0 indirect
  calls/jumps, 0 unsupported control transfers;
- non-nop delay slots use only `addiu`, `or`, `sb`;
- the three unreachable reserved words at `0x2484`/`0x2488`/`0x248c` are
  padding outside any reachable path (`decode_class` null in the record
  projection) and are never treated as code.

## Official runs

Command `python tools/test_phase8_frontier_v1.py`, exit 0, empty stderr, both
runs byte-identical: stdout 1643 bytes, raw sha256
`6a453bc09ea27133eb821462f3ce0838cd00b7b055937aa0901b3c0d06db3043`, LF
sha256 `cd567db99993577a7793a0ebda4e62dc4664338b068a164303a75ea9f3706649`.

Sidecar identities: `pipeline_reuse.json`
`f06f81432880a81eef0a08fd4d593dc1fc54cb1257ccc888854e15c472ffec52`,
`frontier_classification.json`
`58197a27ffdec7f46e9c920db82a9991c9d5d3ce578585cd179c6506d9b55301`,
`p8_02_tests.json`
`22117eadaa37ec76ab5d4b9eac476ee268d1fba1a86af8b8acf04f3fba89229c`.

## Claim-ledger delta

- New evidence: the complete current frontier of the frozen real ELF is
  deterministically and reproducibly characterized, with every reachable word
  and every control-flow/delay-slot/ABI/memory site assigned to an explicit
  class and gap.
- No translation, emitter, runtime, build or equivalence capability was added;
  the terminal marker remains reserved `NOT_PROVEN`.

## Limitations

- The classification is evidence for this one fixture only; it is not a claim
  about arbitrary MIPS32 programs, compilers or optimization levels.
- Address-dependent aliasing/indirect analysis is not performed here; the
  frontier contains no indirect control flow to resolve.
- The `movz` semantic overlay exists in the Phase-3 layer but is not part of
  the shared emitter vocabulary; P8-04 must decide the neutral form on
  evidence.

## Next stage

P8-03: drive the real ELF through the existing neutral ProgramModel, CFG,
function discovery, call graph and translation-unit structure, closing only
the structure-level gaps demonstrated here and failing closed on unresolved
control flow.
