# P11-06 — GPU/DMA/VRAM semantic closure

Status: **PASS**

`OPENRECOMP_P11_06=PASS`

`OPENRECOMP_PHASE11_GPU_SEMANTIC_CLOSURE_V1=PASS tests=75`

`OPENRECOMP_PHASE11_HERCULES_GPU_COMMAND_PROOF=PROVEN`

`OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN`

`OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN`

`OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN`

`OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`

## Result

The P11-05 target value `0x8001a7dc` is independently explained by the exact
RAM pointer chain and is a valid decoded entry. Extending the frozen frontier
from it adds 10 reachable words, one function and one block. The existing
`EXACT_CONSTANT_TARGET` machinery emits a guarded dispatch at `0x8001882c`;
any runtime value other than the proven target still fails closed.

No GPU, DMA or VRAM semantics were added. The newly translated guest function
loads the statically initialized `0x1f801814` GP1 pointer and performs an
ordinary guest store. That store crosses the existing checked memory boundary,
where the frozen Phase-9 classifier records command `0x03000001` as known GP1
class `DISPLAY_ENABLE`. The function then performs one guest RAM bookkeeping
byte write and returns.

## Target provenance

| Field | Proven value |
|---|---|
| unresolved site | `0x8001882c` (`jalr $v0`) |
| runtime target | `0x8001a7dc` |
| base pointer address | `0x8002a284` |
| stable base pointer | `0x8002a244` |
| field offset | 16 |
| effective field address | `0x8002a254` |
| initial field value | `0x8001a7dc` |
| decoded target extent | 10 reachable words |
| resolution | `EXACT_CONSTANT_TARGET`, guarded |

The committed evidence records addresses, counts and classifications only. It
contains no private payload bytes, raw instruction words, reconstructive
disassembly or private paths.

## Controlled causal A/B

At block budget 468322, A (P11-05) and B (guarded target resolution) have
byte-identical stdout. Both report 468323 block events with digest
`0xea6f643720ff69b9`; therefore there is no pre-frontier semantic or runtime
state divergence.

At the full identical budgets:

- A exactly reproduces every committed P11-05 observable and fails first at
  `0x8001882c`, block index 468323;
- B emits the existing P11-05 GP0 NOP first, then the new GP1
  `DISPLAY_ENABLE` event, with event/write sequence `[0, 1]`;
- both commands are known and neither is emulated; there are zero GPU blocker
  writes;
- host and service calls remain 84 in both variants, proving there is no host
  shortcut;
- guest RAM writes increase from 721768 to 721769, exactly the translated
  target's bookkeeping byte;
- no renderer, DMA behavior, VRAM behavior, interrupt delivery or other GPU
  state is fabricated.

Original public synthetic fixtures independently prove the known GP1
`DISPLAY_ENABLE` classification and the fail-closed unknown-GP1 path. Both are
built twice and run twice with deterministic output; known execution returns
through its continuation and neither fixture mutates RAM.

## New exact frontier

| Field | Value |
|---|---|
| site | `0x80015fa4` |
| operation | unresolved indirect call (`jalr`) |
| vector source | `0x000000b0` |
| vector/index | `B0:0x57` |
| classification | `BIOS_VECTOR_NOT_IMPLEMENTED` / `FAIL_CLOSED` |
| block | `blk_80015fa0` |
| function | `fn_80015f90` (entry context `0x80015f18`) |
| block index | 468341 |

No identity or behavior is inferred for `B0:0x57`; the current documented
service surface does not include it.

## Regression and determinism

The unchanged P11-05 gate was run twice through the stage runner inside the
P11-06 evidence directory: **294/294 checks PASS**, byte-identical stdout and
JSON sidecars, empty stderr and exit 0. Its LF stdout SHA-256 remains
`7a860bea311a4795280121cf8a207de60b33b350f540b90b1068eae708ac50a8`.

The P11-06 gate itself ran twice through the stage runner:

- 75/75 checks PASS;
- exit 0 and empty stderr for both runs;
- byte-identical raw and LF-normalized stdout;
- LF stdout SHA-256
  `e93cf4cc7b54982e7c9c290ed58bea0927341e88bc6595b611662fbed2ac9c5c`;
- all generated JSON sidecars are byte-identical.

See `target_provenance.json`, `causal_ab.json`, `frontier.json`,
`p11_06_tests.json`, `determinism.json`, `official_runs.json`, and the nested
`p11-05-regression/` evidence.

## Next action

P11-07 begins at the exact fail-closed `B0:0x57` boundary. It must establish
the service identity and contract from public documentation before any
implementation. If that evidence is unavailable, record
`BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`; do not bypass the call or infer a
service from surrounding GPU activity.
